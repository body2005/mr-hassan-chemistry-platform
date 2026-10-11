// Local disposable chemistryqa stack only. This is a bounded smoke load, not
// a capacity claim or a replacement for a distributed production test.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createConnection } from "node:net";
import { performance } from "node:perf_hooks";

const origin = "http://127.0.0.1:18080";
const api = `${origin}/api/v1`;
const stamp = Date.now();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const percentile = (sorted, fraction) => sorted.length ? sorted[Math.ceil(sorted.length * fraction) - 1] : null;

// Login throttling and video limits remain enabled. Remove only stale counters
// from this disposable QA stack before setup; the run starts from zero.
async function resetQaLoginWindow() {
  const script = "local n=0; for _,pattern in ipairs({'rate-limit:auth:ip:*','video-session:*'}) do local keys=redis.call('KEYS',pattern); if #keys>0 then redis.call('UNLINK',unpack(keys)); n=n+#keys end end; return n";
  const args = ["EVAL", script, "0"];
  const wire = `*${args.length}\r\n${args.map((arg) => `$${Buffer.byteLength(arg)}\r\n${arg}\r\n`).join("")}`;
  await new Promise((resolve, reject) => {
    const socket = createConnection({ host: "127.0.0.1", port: 16379 });
    socket.setTimeout(3000, () => socket.destroy(new Error("QA Redis timeout")));
    socket.once("connect", () => socket.write(wire));
    socket.once("data", (reply) => {
      socket.end();
      if (reply[0] === 58) resolve();
      else reject(new Error(reply.toString()));
    });
    socket.once("error", reject);
  });
}

async function request(path, { token, cookie, csrf, method = "GET", json, body, headers = {} } = {}) {
  const response = await fetch(`${api}/${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(cookie ? { Cookie: cookie } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...(json ? { "content-type": "application/json" } : {}),
      ...headers,
    },
    body: json ? JSON.stringify(json) : body,
    signal: AbortSignal.timeout(10000),
  });
  const raw = await response.text();
  if (!response.ok) throw new Error(`${method} ${path}: ${response.status} ${raw.slice(0, 160)}`);
  try { return JSON.parse(raw); } catch { return raw; }
}

async function login(email, password) {
  const response = await fetch(`${api}/auth/login`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password, institution_slug: "demo" }),
  });
  if (!response.ok) throw new Error(`QA login ${email}: ${response.status}`);
  const { token } = await response.json();
  const cookie = response.headers.getSetCookie().map((value) => value.split(";")[0]).join("; ");
  const csrf = cookie.match(/(?:^|; )matgar_csrf=([^;]+)/)?.[1];
  if (!cookie || !csrf) throw new Error(`QA login ${email}: session cookies absent`);
  return { token, cookie, csrf };
}

function summarize(label, concurrency, records, seconds) {
  const sorted = records.map((record) => record.ms).sort((a, b) => a - b);
  const errors = records.filter((record) => record.error || record.status >= 400).length;
  return {
    label, concurrency, seconds, requests: records.length,
    rps: Number((records.length / seconds).toFixed(2)),
    p95Ms: percentile(sorted, 0.95), p99Ms: percentile(sorted, 0.99),
    errors, errorRate: records.length ? errors / records.length : null,
    statusCounts: Object.fromEntries([...new Set(records.map((record) => record.status ?? "network"))]
      .map((status) => [status, records.filter((record) => (record.status ?? "network") === status).length])),
  };
}

async function timedPhase(label, concurrency, seconds, action) {
  const deadline = performance.now() + seconds * 1000;
  const records = [];
  await Promise.all(Array.from({ length: concurrency }, async (_, index) => {
    while (performance.now() < deadline) {
      const started = performance.now();
      try {
        const response = await action(index);
        await response.arrayBuffer();
        records.push({ ms: Number((performance.now() - started).toFixed(1)), status: response.status });
      } catch (error) {
        records.push({ ms: Number((performance.now() - started).toFixed(1)), error: String(error) });
      }
      await sleep(200);
    }
  }));
  return summarize(label, concurrency, records, seconds);
}

await resetQaLoginWindow();
const teacher = (await login("teacher@demo.com", "qa-teacher-pass")).token;
const course = await request("courses", {
  method: "POST", token: teacher, json: { code: `QALOAD${stamp}`, title: "QA Bounded Load" },
});
const module = await request(`courses/${course.id}/modules`, {
  method: "POST", token: teacher, json: { title: "Load Unit", position: 1 },
});
const videoLesson = await request(`modules/${module.id}/lessons`, {
  method: "POST", token: teacher, json: { title: "Load Video", kind: "video", position: 1, price_egp: 0 },
});
const documentLesson = await request(`modules/${module.id}/lessons`, {
  method: "POST", token: teacher, json: { title: "Load Documents", kind: "article", position: 2, content: "QA", price_egp: 0 },
});
const video = readFileSync(join(process.cwd(), "scratch", "qa-video.webm"));
const videoForm = new FormData();
videoForm.append("file", new Blob([video], { type: "video/webm" }), "qa-video.webm");
await request(`lessons/${videoLesson.id}/video`, { method: "POST", token: teacher, body: videoForm });
await request(`courses/${course.id}/publish`, { method: "POST", token: teacher });

await resetQaLoginWindow();
const students = [];
for (let number = 1; number <= 10; number += 1) {
  const email = `student${String(number).padStart(2, "0")}@demo.com`;
  const { token, cookie, csrf } = await login(email, "qa-student-pass");
  await request(`courses/${course.id}/enroll`, { method: "POST", token });
  const stream = await request(`lessons/${videoLesson.id}/video-token`, { method: "POST", token, cookie, csrf });
  students.push({ token, cookie, streamUrl: new URL(stream.stream_url, origin).href });
}

const results = [];
const browsing = ["courses", "bootstrap", "progress/me", "lessons/me/access-requests", "notifications"];
for (const concurrency of [1, 5, 10]) {
  let sequence = 0;
  results.push(await timedPhase("student-browsing", concurrency, 10, (index) =>
    fetch(`${api}/${browsing[(sequence++) % browsing.length]}`, {
      headers: { Authorization: `Bearer ${students[index].token}` }, signal: AbortSignal.timeout(5000),
    })));
}
for (const concurrency of [1, 5, 10]) {
  results.push(await timedPhase("protected-video-range", concurrency, 10, (index) =>
    fetch(students[index].streamUrl, {
      headers: { Authorization: `Bearer ${students[index].token}`, Cookie: students[index].cookie, Range: "bytes=0-99" },
      signal: AbortSignal.timeout(5000),
    })));
}

const pdf = readFileSync(join(process.cwd(), "apps", "api", "tests", "fixtures", "blind_inputs", "01_physics_text_pdf.pdf"));
for (const concurrency of [1, 2, 4]) {
  const records = [];
  const startedPhase = performance.now();
  await Promise.all(Array.from({ length: concurrency }, async (_, index) => {
    for (let repeat = 0; repeat < 3; repeat += 1) {
      const form = new FormData();
      form.append("file", new Blob([pdf], { type: "application/pdf" }), `load-${stamp}-${index}-${repeat}.pdf`);
      const started = performance.now();
      try {
        const response = await fetch(`${api}/lessons/${documentLesson.id}/materials`, {
          method: "POST", headers: { Authorization: `Bearer ${teacher}` }, body: form,
          signal: AbortSignal.timeout(15000),
        });
        await response.arrayBuffer();
        records.push({ ms: Number((performance.now() - started).toFixed(1)), status: response.status });
      } catch (error) {
        records.push({ ms: Number((performance.now() - started).toFixed(1)), error: String(error) });
      }
    }
  }));
  results.push(summarize("valid-pdf-upload", concurrency, records, (performance.now() - startedPhase) / 1000));
}
console.log(JSON.stringify({
  disclaimer: "Local bounded QA smoke load only; not evidence for 1000 active users.",
  videoBytes: video.length, uploadBytes: pdf.length, results,
}, null, 2));
if (results.some((result) => result.errors)) process.exitCode = 1;

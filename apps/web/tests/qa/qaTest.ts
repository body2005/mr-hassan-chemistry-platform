import { createConnection } from "node:net";
import { execFileSync } from "node:child_process";
import { expect, test as base } from "@playwright/test";

function resetQaTestCounters(): Promise<void> {
  const script = "local n=0; for _,pattern in ipairs({'rate-limit:auth:ip:*','video-session:*'}) do local keys=redis.call('KEYS',pattern); if #keys>0 then redis.call('UNLINK',unpack(keys)); n=n+#keys end end; return n";
  const parts = ["EVAL", script, "0"];
  if (process.env.QA_REDIS_CONTAINER) {
    if (process.env.QA_REDIS_CONTAINER !== "chemistryprodlocal-redis-1") {
      throw new Error("QA may only clear counters in the isolated production-local project");
    }
    execFileSync(process.env.QA_DOCKER || "docker", ["exec", process.env.QA_REDIS_CONTAINER, "redis-cli", ...parts], { timeout: 5000 });
    return Promise.resolve();
  }
  const command = `*${parts.length}\r\n${parts.map((part) => `$${Buffer.byteLength(part)}\r\n${part}\r\n`).join("")}`;
  return new Promise((resolve, reject) => {
    const socket = createConnection({ host: "127.0.0.1", port: 16379 });
    socket.setTimeout(3000, () => socket.destroy(new Error("QA Redis isolation timed out")));
    socket.once("connect", () => socket.write(command));
    socket.once("data", (reply) => {
      socket.end();
      if (reply[0] === 58) resolve();
      else reject(new Error(`QA Redis isolation failed: ${reply.toString()}`));
    });
    socket.once("error", reject);
  });
}

// All QA specs share one local reverse-proxy IP and reusable demo accounts.
// Keep the real login/video limits active within each test while giving each
// serial test fresh counters. Only this disposable QA Redis is touched.
export const test = base.extend<{ isolatedLoginWindow: void }>({
  isolatedLoginWindow: [async ({ browser }, use) => {
    if (!browser.isConnected()) throw new Error("QA browser is not connected");
    await resetQaTestCounters();
    await use();
  }, { auto: true }],
});

export { expect };

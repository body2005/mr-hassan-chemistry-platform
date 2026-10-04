import { createConnection } from "node:net";
import { execFileSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { expect, test as base } from "@playwright/test";

function resetQaTestCounters(): Promise<void> {
  const script = "local keys=redis.call('KEYS','rate-limit:auth:ip:*'); if #keys>0 then redis.call('UNLINK',unpack(keys)); end; return #keys";
  const parts = ["EVAL", script, "0"];
  if (process.env.QA_REDIS_CONTAINER) {
    if (!["chemistryprodlocal-redis-1", "chemistryaudit2-redis-1"].includes(process.env.QA_REDIS_CONTAINER)) {
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

async function waitForReusableQaAuthWindow(): Promise<void> {
  const target = process.env.QA_REDIS_CONTAINER;
  if (!target) return;
  if (!["chemistryprodlocal-redis-1", "chemistryaudit2-redis-1"].includes(target)) throw new Error("Not an isolated QA Redis");
  // Old journey specs reuse demo users. WAIT for their real rolling window;
  // never erase user rate-limit keys or relax the production limits. New
  // publication cases additionally use a distinct synthetic teacher per case.
  const script = "local ms=0; for _,k in ipairs(redis.call('KEYS','rate-limit:auth:*')) do if not string.find(k,':ip:',1,true) and redis.call('ZCARD',k)>=8 then ms=math.max(ms,redis.call('PTTL',k)) end end; return ms";
  const output = execFileSync(process.env.QA_DOCKER || "docker", ["exec", target, "redis-cli", "EVAL", script, "0"], { encoding: "utf8", timeout: 5000 });
  const ms = Number(output.trim());
  if (!Number.isFinite(ms) || ms > 65_000) throw new Error("Unexpected QA auth window; inspect it without bypassing it");
  if (ms > 0) await delay(ms + 100);
}

// All QA specs share one local reverse-proxy IP and reusable demo accounts.
// Keep real limits active inside each case. Only the shared-IP login window
// is isolated between serial cases. Never erase video/admission/session ledgers.
export const test = base.extend<{ isolatedLoginWindow: void }>({
  isolatedLoginWindow: [async ({ browser, context }, use) => {
    if (!browser.isConnected()) throw new Error("QA browser is not connected");
    await waitForReusableQaAuthWindow();
    await resetQaTestCounters();
    await use();
    const cookies = await context.cookies();
    const csrf = cookies.find((cookie) => cookie.name === "matgar_csrf")?.value;
    if (csrf && cookies.some((cookie) => cookie.name === "matgar_session")) {
      const result = await context.request.post(`${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/auth/logout`, {
        headers: { "X-CSRF-Token": csrf },
      });
      expect(result.status(), "QA cleanup must use real session revocation").toBe(204);
    }
  }, { auto: true, timeout: 90_000 }],
});

export { expect };

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { setTimeout as delay } from "node:timers/promises";
import { expect, test as base } from "@playwright/test";

const runDocker = promisify(execFile);

async function waitForReusableQaAuthWindow(): Promise<void> {
  const target = process.env.QA_REDIS_CONTAINER;
  if (!target) return;
  if (!["chemistryprodlocal-redis-1", "chemistryaudit2-redis-1"].includes(target)) throw new Error("Not an isolated QA Redis");
  // Old journey specs reuse demo users. WAIT for their real rolling window;
  // never erase user rate-limit keys or relax the production limits. New
  // publication cases additionally use a distinct synthetic teacher per case.
  const script = "local ms=0; for _,p in ipairs({'rate-limit:auth:*','rate-limit:auth_refresh:*','rate-limit:login_ip:*','rate-limit:login_account:*','rate-limit:login_retry:*'}) do for _,k in ipairs(redis.call('KEYS',p)) do local cap=string.find(p,'login_retry',1,true) and 4 or (string.find(p,'login_account',1,true) and 15 or 8); if redis.call('ZCARD',k)>=cap then ms=math.max(ms,redis.call('PTTL',k)) end end end; return ms";
  // Docker Desktop's control-plane delay is not an application assertion.
  // One bounded async probe (no retries) leaves browser/runner event loops
  // responsive. Still fail if the CLI/backend cannot respond within15s.
  const { stdout } = await runDocker(process.env.QA_DOCKER || "docker", ["exec", target, "redis-cli", "EVAL", script, "0"], { encoding: "utf8", timeout: 15_000 });
  if (!/^\d+$/.test(stdout.trim())) throw new Error("Unexpected QA auth-window response");
  const ms = Number(stdout.trim());
  if (!Number.isFinite(ms) || ms > 305_000) throw new Error("Unexpected QA auth window; inspect it without bypassing it");
  if (ms > 0) await delay(ms + 100);
}

// All QA specs share one local reverse-proxy IP and reusable demo accounts.
// Keep real limits active: wait for rolling windows, never erase counters or
// video/admission/session ledgers. New cases use distinct synthetic identities.
export const test = base.extend<{ isolatedLoginWindow: void }>({
  isolatedLoginWindow: [async ({ browser, context }, use) => {
    if (!browser.isConnected()) throw new Error("QA browser is not connected");
    await waitForReusableQaAuthWindow();
    await use();
    const cookies = await context.cookies();
    const csrf = cookies.find((cookie) => cookie.name === "matgar_csrf")?.value;
    if (csrf && cookies.some((cookie) => cookie.name === "matgar_session")) {
      const result = await context.request.post(`${process.env.QA_BASE_URL || "http://127.0.0.1:18080"}/api/v1/auth/logout`, {
        headers: { "X-CSRF-Token": csrf },
      });
      // A cleanup failure still fails the test, but must not replace the
      // original journey error and hide where the application actually failed.
      expect.soft(result.status(), "QA cleanup must use real session revocation").toBe(204);
    }
  }, { auto: true, timeout: 370_000 }],
});

export { expect };

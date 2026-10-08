export interface BootstrapFailure {
  status?: number;
  code?: string;
  retryAfterMs?: number;
}

// At most three automatic identity probes for a temporary outage. Rate-limit
// and policy errors require an explicit user action, never a timer replay.
export function bootstrapRetryDelay(failure: BootstrapFailure | null, attempts: number): number | null {
  if (!failure || !Number.isInteger(attempts) || attempts < 0 || attempts >= 3) return null;
  const transient = [408, 502, 503, 504].includes(failure.status ?? 0)
    || ['NETWORK_ERROR', 'REQUEST_TIMEOUT'].includes(failure.code ?? '');
  if (failure.status === 429 || !transient) return null;
  const serverDelay = failure.retryAfterMs ?? 0;
  // Do not shorten an origin's long Retry-After merely to fit the local budget.
  if (!Number.isFinite(serverDelay) || serverDelay > 30_000 || serverDelay < 0) return null;
  return Math.max(2000 * Math.pow(1.5, attempts), serverDelay);
}

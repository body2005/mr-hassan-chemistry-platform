import { describe, expect, it } from 'vitest';
import { bootstrapRetryDelay } from './bootstrapRecovery';

describe('bounded bootstrap recovery', () => {
  it('bounds a transient outage to three automatic probes', () => {
    expect([0, 1, 2, 3, 50].map(attempt => bootstrapRetryDelay({ status: 503 }, attempt)))
      .toEqual([2000, 3000, 4500, null, null]);
  });
  it('never automatically replays a rate-limited bootstrap', () => {
    expect(bootstrapRetryDelay({ status: 429, retryAfterMs: 2000 }, 0)).toBeNull();
  });
  it('respects the server delay without shortening a longer cooldown', () => {
    expect(bootstrapRetryDelay({ status: 503, retryAfterMs: 6000 }, 0)).toBe(6000);
    expect(bootstrapRetryDelay({ status: 503, retryAfterMs: 60_000 }, 0)).toBeNull();
  });
  it('allows bounded transport and timeout recovery', () => {
    expect(bootstrapRetryDelay({ code: 'NETWORK_ERROR', status: 0 }, 0)).toBe(2000);
    expect(bootstrapRetryDelay({ code: 'REQUEST_TIMEOUT', status: 0 }, 2)).toBe(4500);
  });
  it('does not replay policy errors or unclassified exceptions', () => {
    for (const status of [400, 401, 403, 404, 422]) expect(bootstrapRetryDelay({ status }, 0)).toBeNull();
    expect(bootstrapRetryDelay(null, 0)).toBeNull();
    expect(bootstrapRetryDelay({}, 0)).toBeNull();
  });
  it('rejects malformed attempt counts and server delays', () => {
    for (const attempts of [-1, 0.5, NaN]) expect(bootstrapRetryDelay({ status: 503 }, attempts)).toBeNull();
    for (const retryAfterMs of [Infinity, -1, NaN]) {
      expect(bootstrapRetryDelay({ status: 503, retryAfterMs }, 0)).toBeNull();
    }
  });
});

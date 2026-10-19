import { describe, it, expect } from 'vitest';
// @ts-expect-error Server-only JS middleware is tested outside the browser bundle.
import { assertionHeaders } from '../../middleware.js';

describe('Vercel client address assertions', () => {
  it('overrides forged assertions and binds IP, method, path and query', () => {
    const r = new Request('https://site.example/api/v1/courses?page=1', {headers:{
      'x-forwarded-for':'198.51.100.42','x-chemistry-client-ip':'forged',
      'x-chemistry-client-signature':'forged','x-vercel-forwarded-for':'1.1.1.1'}});
    const a = assertionHeaders(r, 'a'.repeat(64), 1700000000000);
    expect(a.get('x-chemistry-client-ip')).toBe('198.51.100.42');
    expect(a.get('x-chemistry-client-time')).toBe('1700000000');
    expect(a.get('x-chemistry-client-signature')).toMatch(/^[a-f0-9]{64}$/);
    const b = assertionHeaders(new Request('https://site.example/api/v1/courses?page=2', {headers:r.headers}), 'a'.repeat(64), 1700000000000);
    expect(b.get('x-chemistry-client-signature')).not.toBe(a.get('x-chemistry-client-signature'));
  });
  it('never signs a forwarding chain or passes a supplied assertion without a key', () => {
    const r = new Request('https://site.example/api/v1/courses', {headers:{
      'x-forwarded-for':'8.8.8.8, 1.1.1.1','x-chemistry-client-signature':'forged'}});
    expect(assertionHeaders(r, 'a'.repeat(64)).has('x-chemistry-client-signature')).toBe(false);
    expect(assertionHeaders(r, undefined).has('x-chemistry-client-signature')).toBe(false);
  });
});

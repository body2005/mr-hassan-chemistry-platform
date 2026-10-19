// Runs on Vercel, never included in the Vite browser bundle.
import { createHmac } from 'node:crypto';
import { isIP } from 'node:net';
import { next } from '@vercel/functions';

export const config = { matcher: '/api/:path*', runtime: 'nodejs' };

export function assertionHeaders(request, secret, now = Date.now()) {
  const headers = new Headers(request.headers);
  for (const name of ['x-chemistry-client-ip', 'x-chemistry-client-time', 'x-chemistry-client-signature']) {
    headers.delete(name);
  }
  if (!secret || secret.length < 32) return headers;
  // Vercel overwrites XFF with the incoming client address. Do not use the
  // client-supplied x-vercel-forwarded-for observed on external rewrites.
  const ip = request.headers.get('x-forwarded-for')?.trim();
  if (!ip || !isIP(ip)) return headers;
  const url = new URL(request.url);
  const stamp = String(Math.floor(now / 1000));
  const message = `client-ip-v1\n${stamp}\n${request.method.toUpperCase()}\n${url.pathname}${url.search}\n${ip}`;
  headers.set('x-chemistry-client-ip', ip);
  headers.set('x-chemistry-client-time', stamp);
  headers.set('x-chemistry-client-signature', createHmac('sha256', secret).update(message).digest('hex'));
  return headers;
}

export default function middleware(request) {
  const secret = process.env.PROXY_ASSERTION_SECRET;
  // Staged rollout: absent key retains the existing external rewrite. Once
  // configured, a malformed platform address fails closed rather than signing
  // an arbitrary forwarding chain. Never return the key in response headers.
  const headers = assertionHeaders(request, secret);
  if (secret && !headers.has('x-chemistry-client-signature')) {
    return new Response('Client identity temporarily unavailable', { status: 503 });
  }
  return next({ request: { headers } });
}

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import https from 'node:https';
import { expect, test } from './qaTest';

test('QA browser and API validate the installed local certificate, not blanket TLS exceptions', async ({ page }) => {
  if (process.env.QA_TRUSTED_BROWSER !== 'true') throw new Error('Run this gate through run-trusted-browser.ps1');
  const response = await page.goto(process.env.QA_BASE_URL!);
  expect(response?.status()).toBe(200);
  const security = await response!.securityDetails();
  expect(security?.issuer).toBeTruthy();
  expect(security!.validTo * 1000).toBeGreaterThan(Date.now());
  expect((await page.request.get('/healthz')).status()).toBe(200);
  // A second, untrusted CA must still fail in BOTH clients. Synthetic fixture
  // keys never leave the runner or enter a report/repository artifact.
  const folder = mkdtempSync(path.join(tmpdir(), 'qa-negative-tls-'));
  let server: https.Server | undefined;
  try {
    execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
      '-keyout', path.join(folder, 'key.pem'), '-out', path.join(folder, 'cert.pem'), '-subj', '/CN=127.0.0.1',
      '-addext', 'subjectAltName=IP:127.0.0.1'], { stdio: 'ignore' });
    server = https.createServer({ key: readFileSync(path.join(folder, 'key.pem')), cert: readFileSync(path.join(folder, 'cert.pem')) },
      (_request, reply) => { reply.end('untrusted fixture'); });
    await new Promise<void>(resolve => server!.listen(0, '127.0.0.1', resolve));
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Negative TLS fixture did not bind');
    const url = `https://127.0.0.1:${address.port}/`;
    await expect(page.request.get(url)).rejects.toThrow(/self.signed|certificate/i);
    await expect(page.goto(url)).rejects.toThrow(/ERR_CERT_AUTHORITY_INVALID/);
  } finally {
    if (server) { server.closeAllConnections(); await new Promise<void>(resolve => server!.close(() => resolve())); }
    rmSync(folder, { recursive: true, force: true });
  }
});

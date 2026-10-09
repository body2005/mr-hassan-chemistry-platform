import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AuthView } from './AuthView';
import { PasswordChangeWizard } from '../components/PasswordChangeWizard';

const mocks = vi.hoisted(() => ({ features: vi.fn(), change: vi.fn(), request: vi.fn() }));
vi.mock('../services/lmsService', () => ({ authService: {
  getFeatures: mocks.features, changePassword: mocks.change, requestPasswordReset: mocks.request,
} }));
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  mocks.features.mockReset().mockResolvedValue({ password_reset_enabled: false });
  mocks.change.mockReset().mockResolvedValue(undefined); mocks.request.mockReset();
  window.history.replaceState({}, '', '/#auth');
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

function login() {
  return <AuthView lang="ar" theme="dark" onLoginSuccess={vi.fn()} onToggleLang={vi.fn()} onToggleTheme={vi.fn()} />;
}
const recoveryButtons = () => [...host.querySelectorAll('button')].filter(button => button.textContent?.includes('نسيت'));

it('keeps sign-in available without offering disabled email recovery', async () => {
  await act(async () => root.render(login()));
  expect(recoveryButtons()).toHaveLength(0);
  expect(host.textContent).toContain('تواصل مع إدارة المنصة');
  expect(host.querySelector('input[autocomplete="current-password"]')).not.toBeNull();
  expect(mocks.request).not.toHaveBeenCalled();
});
it('offers email recovery when the server enables its configured provider', async () => {
  mocks.features.mockResolvedValue({ password_reset_enabled: true });
  await act(async () => root.render(login()));
  expect(recoveryButtons()).toHaveLength(1);
  await act(async () => recoveryButtons()[0].click());
  expect(host.querySelector('#reset-email')).not.toBeNull();
});
it('does not promise email delivery when feature discovery fails', async () => {
  mocks.features.mockRejectedValue(new Error('Synthetic network outage'));
  await act(async () => root.render(login()));
  expect(recoveryButtons()).toHaveLength(0);
  expect(mocks.request).not.toHaveBeenCalled();
});
it('still changes a password with the current password when email is disabled', async () => {
  const changed = vi.fn();
  await act(async () => root.render(<PasswordChangeWizard email="student@example.test" lang="ar" onClose={vi.fn()} onChanged={changed} />));
  expect(recoveryButtons()).toHaveLength(0);
  async function fill(index: number, value: string) {
    const input = host.querySelectorAll('input')[index];
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }
  async function submit() {
    await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  }
  await fill(0, 'Current-password-2026'); await submit();
  await fill(0, 'Replacement-password-2026'); await fill(1, 'Replacement-password-2026'); await submit();
  expect(mocks.change).toHaveBeenCalledWith('Current-password-2026', 'Replacement-password-2026');
  expect(changed).toHaveBeenCalledOnce();
  expect(mocks.request).not.toHaveBeenCalled();
});

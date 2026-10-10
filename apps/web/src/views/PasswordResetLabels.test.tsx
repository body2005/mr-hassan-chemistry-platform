import { ToastProvider } from '../components/ToastProvider';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { AuthView } from './AuthView';
const mocks = vi.hoisted(() => ({ request: vi.fn(), confirm: vi.fn(), features: vi.fn(), login: vi.fn() }));
vi.mock('../services/lmsService', () => ({ authService: {
  requestPasswordReset: mocks.request, confirmPasswordReset: mocks.confirm,
  getFeatures: mocks.features,
  login: mocks.login,
} }));
let root: Root, host: HTMLDivElement;
const originalScrollTo = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTo');
beforeEach(() => {
  Object.defineProperty(Element.prototype, 'scrollTo', { configurable: true, value: vi.fn() });
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  window.history.replaceState({}, '', '/#auth');
  mocks.request.mockReset(); mocks.confirm.mockReset();
  mocks.login.mockReset();
  mocks.features.mockReset().mockResolvedValue({ password_reset_enabled: true });
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals();
  if (originalScrollTo) Object.defineProperty(Element.prototype, 'scrollTo', originalScrollTo);
  else Reflect.deleteProperty(Element.prototype, 'scrollTo');
});
async function render() {
  await act(async () => root.render(<ToastProvider><AuthView lang="ar" theme="dark" onLoginSuccess={vi.fn()}
    onToggleLang={vi.fn()} onToggleTheme={vi.fn()} /></ToastProvider>));
}

it('starts with an email placeholder and shows rejected student sign-in in the global toast', async () => {
  await render();
  const identity = host.querySelector<HTMLInputElement>('#auth-signin-identity')!;
  expect(identity.value).toBe('');
  expect(identity.placeholder).toBe('teacher@demo.com');
  mocks.login.mockResolvedValueOnce({ success: false, error: 'البريد الإلكتروني أو كلمة المرور غير صحيحة.' });
  await fill('auth-signin-identity', 'student01@demo.com');
  await fill('auth-signin-password', 'Synthetic-invalid-password');
  await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(document.body.querySelector('.toast-danger')?.textContent).toContain('كلمة المرور غير صحيحة');
  expect(host.querySelector('.toast-stack')).toBeNull();
});
async function fill(id: string, value: string) {
  const input = host.querySelector('#' + id)!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
async function submit() {
  await act(async () => host.querySelector('.password-reset-form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
}
it('restores registration after reload without persisting any form data', async () => {
  window.history.replaceState({}, '', '/#auth?tab=register');
  await render();
  expect(host.textContent).toContain('الاسم الأول');
  const signIn = [...host.querySelectorAll('button')].find(b => b.textContent?.trim() === 'تسجيل الدخول')!;
  await act(async () => signIn.click());
  expect(window.location.hash).toBe('#auth?tab=signin');
  await act(async () => { root.unmount(); root = createRoot(host); });
  await render();
  expect(host.querySelector('input[autocomplete="current-password"]')).not.toBeNull();
});
it('follows browser navigation between auth tabs and prioritizes password reset links', async () => {
  await render();
  await act(async () => {
    window.history.replaceState({}, '', '/#auth?tab=register');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
  expect(host.textContent).toContain('الاسم الأول');
  await act(async () => {
    window.history.replaceState({}, '', '/#auth?tab=register&reset_token=synthetic-reset-token-1234567890');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
  expect(host.querySelector('#reset-password')).not.toBeNull();
});
it('shows a visible reset email label and associates persistent validation with its input', async () => {
  await render();
  const forgot = [...host.querySelectorAll('button')].find(b => b.textContent?.includes('نسيت'))!;
  await act(async () => forgot.click());
  expect(host.querySelector('label[for="reset-email"]')!.textContent).toBe('بريد الاسترجاع');
  const email = host.querySelector('#reset-email')!;
  expect(email.getAttribute('autocomplete')).toBe('email');
  await fill('reset-email', 'invalid'); await submit();
  expect(email.getAttribute('aria-invalid')).toBe('true');
  expect(email.getAttribute('aria-describedby')).toBe('reset-email-error');
  expect(host.querySelector('#reset-email-error')!.textContent).toContain('صحيح');
  expect(mocks.request).not.toHaveBeenCalled();
});
it('shows password and confirmation labels, requirements and separate linked errors', async () => {
  window.history.replaceState({}, '', '/#auth?reset_token=synthetic-reset-token-1234567890');
  await render();
  expect(host.querySelector('label[for="reset-password"]')!.textContent).toBe('كلمة المرور الجديدة');
  expect(host.querySelector('label[for="reset-confirm"]')!.textContent).toBe('تأكيد كلمة المرور الجديدة');
  expect(host.querySelector('#reset-password-help')!.textContent).toContain('10 إلى 128');
  await fill('reset-password', 'short'); await fill('reset-confirm', 'different'); await submit();
  expect(host.querySelector('#reset-password')!.getAttribute('aria-describedby')).toContain('reset-password-error');
  expect(host.querySelector('#reset-confirm')!.getAttribute('aria-describedby')).toBe('reset-confirm-error');
  expect(host.querySelectorAll('input[autocomplete="new-password"]')).toHaveLength(2);
  expect(mocks.confirm).not.toHaveBeenCalled();
});
it('keeps server failures visible and clears a consumed reset token only after success', async () => {
  const token = 'synthetic-reset-token-1234567890';
  window.history.replaceState({}, '', '/#auth?reset_token=' + token);
  await render(); await fill('reset-password', 'Long-synthetic-password'); await fill('reset-confirm', 'Long-synthetic-password');
  mocks.confirm.mockRejectedValueOnce(new Error('تعذر الاتصال بالخادم. أعد المحاولة.'));
  await submit();
  expect(host.querySelector('#auth-error')!.textContent).toContain('أعد المحاولة');
  expect(window.location.hash).toContain('reset_token');
  mocks.confirm.mockResolvedValueOnce(undefined);
  await submit();
  expect(window.location.hash).toBe('#auth');
  expect(mocks.confirm).toHaveBeenCalledWith(token, 'Long-synthetic-password');
});

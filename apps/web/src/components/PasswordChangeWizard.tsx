import { useEffect, useRef, useState } from 'react';
import { KeyRound, Mail, X } from 'lucide-react';
import { authService } from '../services/lmsService';
import { usePasswordResetAvailability } from '../hooks/usePasswordResetAvailability';

export function PasswordChangeWizard({ email, lang, onClose, onChanged }: {
  email: string; lang: string; onClose: () => void; onChanged: () => void;
}) {
  const ar = lang === 'ar';
  const passwordResetAvailable = usePasswordResetAvailability();
  const [step, setStep] = useState<'current' | 'new' | 'reset' | 'sent'>('current');
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [resetEmail, setResetEmail] = useState(email);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef<HTMLDivElement>(null);
  const locked = useRef(false);
  const dismiss = useRef(onClose);
  dismiss.current = onClose;

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !locked.current) dismiss.current();
      if (event.key !== 'Tab') return;
      const nodes = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), [tabindex="0"]') ?? []);
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener('keydown', keydown);
    return () => { document.removeEventListener('keydown', keydown); previous?.focus(); };
  }, []);

  function move(next: typeof step) { setError(''); setStep(next); }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (locked.current) return;
    setError('');
    if (step === 'current') { move('new'); return; }
    if (step === 'new' && (password.length < 10 || password !== confirmation || password === current)) {
      setError(ar ? 'استخدم كلمة مرور مختلفة من 10 أحرف على الأقل، وتأكد من تطابق التأكيد.' : 'Use a different password of at least 10 characters and a matching confirmation.');
      return;
    }
    locked.current = true; setBusy(true);
    try {
      if (step === 'reset') {
        if (!passwordResetAvailable) {
          setError(ar ? 'استعادة كلمة المرور بالإيميل غير متاحة. تواصل مع إدارة المنصة.' : 'Email recovery is unavailable. Contact the platform administration.');
          return;
        }
        await authService.requestPasswordReset(resetEmail); move('sent');
      }
      else if (step === 'new') { await authService.changePassword(current, password); onChanged(); }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (ar ? 'تعذر إكمال الطلب. حاول مرة أخرى.' : 'Could not complete the request. Please retry.'));
    } finally { locked.current = false; setBusy(false); }
  }
  return <div className="password-wizard-overlay">
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="password-wizard-title" tabIndex={-1} className="password-wizard" dir={ar ? 'rtl' : 'ltr'}>
      <button type="button" className="password-wizard-close" aria-label={ar ? 'إغلاق' : 'Close'} disabled={busy} onClick={onClose}><X size={20} /></button>
      <div className="password-wizard-icon"><KeyRound size={26} /></div>
      <h2 id="password-wizard-title">{ar ? 'تغيير كلمة المرور' : 'Change password'}</h2>
      <p className="password-wizard-description">{step === 'current' ? (ar ? 'الخطوة 1 من 2 — أدخل كلمة المرور الحالية.' : 'Step 1 of 2 — enter your current password.') : step === 'new' ? (ar ? 'الخطوة 2 من 2 — اختر كلمة مرور جديدة. بعد حفظها ستحتاج لتسجيل الدخول مجددًا على أجهزتك.' : 'Step 2 of 2 — choose a new password. After saving, sign in again on your devices.') : (ar ? 'استرجاع الحساب عبر البريد الإلكتروني.' : 'Recover your account by email.')}</p>
      {error && <p role="alert" className="password-wizard-error">{error}</p>}
      {step === 'sent' ? <>
        <p role="status">{ar ? 'إذا كان البريد مرتبطًا بحساب، ستصلك رسالة تحتوي على رابط إعادة التعيين. تحقق من الوارد والبريد غير المرغوب فيه.' : 'If the email belongs to an account, you will receive a reset link. Check your inbox and spam folder.'}</p>
        <button className="security-primary-button" type="button" onClick={onClose}>{ar ? 'تم' : 'Done'}</button>
      </> : <form onSubmit={submit}>
        {step === 'current' && <>
          <label>{ar ? 'كلمة المرور الحالية' : 'Current password'}<input type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} required disabled={busy} /></label>
          {passwordResetAvailable === true && <button className="security-text-button" type="button" onClick={() => move('reset')}><Mail size={16} />{ar ? 'نسيت كلمة المرور الحالية؟' : 'Forgot your current password?'}</button>}
          {passwordResetAvailable === false && <p>{ar ? 'لو نسيت كلمة المرور، تواصل مع إدارة المنصة.' : 'Forgot your password? Contact the platform administration.'}</p>}
        </>}
        {step === 'new' && <>
          <label>{ar ? 'كلمة المرور الجديدة' : 'New password'}<input type="password" autoComplete="new-password" minLength={10} value={password} onChange={e => setPassword(e.target.value)} required disabled={busy} /></label>
          <label>{ar ? 'تأكيد كلمة المرور الجديدة' : 'Confirm new password'}<input type="password" autoComplete="new-password" minLength={10} value={confirmation} onChange={e => setConfirmation(e.target.value)} required disabled={busy} /></label>
        </>}
        {step === 'reset' && <label>{ar ? 'البريد الإلكتروني' : 'Email address'}<input type="email" autoComplete="email" value={resetEmail} onChange={e => setResetEmail(e.target.value)} required disabled={busy} /></label>}
        <div className="password-wizard-actions">
          <button className="security-primary-button" type="submit" disabled={busy}>{busy ? (ar ? 'جارٍ التنفيذ…' : 'Working…') : step === 'current' ? (ar ? 'متابعة' : 'Continue') : step === 'reset' ? (ar ? 'إرسال رابط الاسترجاع' : 'Send reset link') : (ar ? 'حفظ كلمة المرور الجديدة' : 'Save new password')}</button>
          {step !== 'current' && <button className="security-text-button" type="button" disabled={busy} onClick={() => move('current')}>{ar ? 'رجوع' : 'Back'}</button>}
        </div>
      </form>}
    </div>
  </div>;
}

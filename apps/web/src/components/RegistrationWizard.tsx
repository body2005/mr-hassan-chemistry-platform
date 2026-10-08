import { useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, GraduationCap, Moon, Phone, Sun, User } from 'lucide-react';
import { authService } from '../services/lmsService';
import type { CurrentUser } from '../types/lms';
import type { Language } from '../utils/i18n';
import { emptyRegistration, GOVERNORATES, normalizePhone, validateRegistration } from '../utils/registration';
import type { RegistrationData, RegistrationErrors } from '../utils/registration';
import './RegistrationWizard.css';

type Props = {
  lang: Language; theme: 'light' | 'dark'; onToggleLang: () => void;
  onToggleTheme: () => void; onSignIn: () => void; onBack?: () => void;
  onSuccess: (user: CurrentUser) => void;
  embedded?: boolean;
};

export function RegistrationWizard({ lang, theme, onToggleLang, onToggleTheme, onSignIn, onBack, onSuccess, embedded = false }: Props) {
  const ar = lang === 'ar';
  const tr = (arabic: string, english: string) => ar ? arabic : english;
  const [step, setStep] = useState(1);
  const [data, setData] = useState<RegistrationData>({ ...emptyRegistration });
  const [errors, setErrors] = useState<RegistrationErrors>({});
  const [serverError, setServerError] = useState('');
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [visible, setVisible] = useState({ password: false, confirmation: false });
  const heading = useRef<HTMLHeadingElement>(null);
  const prefix = useId();
  const titles = [tr('البيانات الشخصية', 'Personal details'), tr('التواصل وإنشاء الحساب', 'Contact and create account')];
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    // Keep the shared sign-in/register switch and progress steps visible when
    // the long form moves between steps inside the split-screen scroll panel.
    heading.current?.closest('.auth-form-panel')?.scrollTo({ top: 0 });
  }, [step]);
  const id = (key: keyof RegistrationData) => prefix + key;
  function update<K extends keyof RegistrationData>(key: K, value: RegistrationData[K]) {
    setData(previous => ({ ...previous, [key]: value }));
    setErrors(previous => ({ ...previous, [key]: undefined }));
    setServerError('');
  }
  const description = (key: keyof RegistrationData) => errors[key] ? id(key) + '-error' : undefined;
  const feedback = (key: keyof RegistrationData) => errors[key]
    ? <span className="registration-error" id={description(key)}>{errors[key]}</span> : null;
  function field(key: keyof RegistrationData, label: string, options: { type?: string; optional?: boolean; autocomplete?: string; max?: number; suggestions?: readonly string[] } = {}) {
    const password = key === 'password' || key === 'confirmation';
    return <div className="registration-field" key={key}>
      <label htmlFor={id(key)}>{label}{!options.optional && <span aria-hidden="true"> *</span>}</label>
      <div className="registration-input-wrap">
        <input id={id(key)} name={key} value={data[key]} type={password ? (visible[key] ? 'text' : 'password') : options.type || 'text'}
          required={!options.optional} maxLength={options.max || (password ? 128 : 100)}
          autoComplete={options.autocomplete} dir={options.type === 'email' || options.type === 'tel' || password ? 'ltr' : undefined}
          inputMode={options.type === 'tel' ? 'tel' : undefined}
          list={options.suggestions?.length ? id(key) + '-suggestions' : undefined}
          aria-invalid={!!errors[key]} aria-describedby={description(key)}
          onChange={event => update(key, event.target.value as RegistrationData[typeof key])} />
        {password && <button className="registration-eye" type="button"
          aria-label={visible[key] ? tr('إخفاء كلمة المرور', 'Hide password') : tr('إظهار كلمة المرور', 'Show password')}
          aria-pressed={visible[key]} onClick={() => setVisible(previous => ({ ...previous, [key]: !previous[key] }))}>
          {visible[key] ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>}
      </div>{options.suggestions?.length ? <datalist id={id(key) + '-suggestions'}>
        {options.suggestions.map(value => <option key={value} value={value} />)}
      </datalist> : null}{feedback(key)}
    </div>;
  }
  function select<K extends keyof RegistrationData>(key: K, label: string, choices: readonly (readonly [string, string])[], placeholder?: string) {
    return <div className="registration-field">
      <label htmlFor={id(key)}>{label}<span aria-hidden="true"> *</span></label>
      <select id={id(key)} name={key} value={data[key]} required
        aria-invalid={!!errors[key]} aria-describedby={description(key)}
        onChange={event => update(key, event.target.value as RegistrationData[K])}>
        {placeholder && <option value="">{placeholder}</option>}
        {choices.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select>{feedback(key)}
    </div>;
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    const nextErrors = validateRegistration(data, step === 1 ? 1 : 'all', ar);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      document.getElementById(id(Object.keys(nextErrors)[0] as keyof RegistrationData))?.focus();
      return;
    }
    if (step === 1) { setStep(2); return; }
    if (!data.gender || !data.academicYear) { setStep(1); return; }
    inFlight.current = true;
    setBusy(true);
    setServerError('');
    try {
      const result = await authService.register({
        name: [data.firstName, data.middleName, data.lastName].map(name => name.trim()).join(' '),
        email: data.email.trim(), password: data.password, gender: data.gender, academicYear: data.academicYear,
        studentPhone: normalizePhone(data.studentPhone), guardianPhone: normalizePhone(data.guardianPhone),
        motherPhone: normalizePhone(data.motherPhone), governorate: data.governorate,
        city: data.city.trim(), schoolName: data.schoolName.trim(),
        educationDivision: data.educationDivision, specialization: data.specialization,
      });
      if (!result.success || !result.user) setServerError(result.error || tr('تعذر إنشاء الحساب. حاول مرة أخرى.', 'Could not create account. Try again.'));
      else onSuccess(result.user);
    } catch {
      setServerError(tr('تعذر الاتصال. بياناتك محفوظة هنا؛ حاول مرة أخرى.', 'Connection failed. Your form is preserved; try again.'));
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <main className={'registration-page' + (embedded ? ' registration-page-embedded' : '')} data-theme={theme} dir={ar ? 'rtl' : 'ltr'}>
    {!embedded && <nav className="registration-tools" aria-label={tr('إعدادات الصفحة', 'Page settings')}>
      {onBack && <button type="button" onClick={onBack}>{tr('الرئيسية', 'Home')}</button>}
      <button type="button" onClick={onToggleLang}>{ar ? 'English' : 'العربية'}</button>
      <button type="button" onClick={onToggleTheme} aria-label={tr('تغيير المظهر', 'Change theme')}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
    </nav>}
    <div className="registration-container">
      {!embedded && <header className="registration-brand"><div className="registration-brand-icon"><GraduationCap size={36} /></div>
        <div><strong>{tr('منصة مستر حسن شعبان', 'Mr Hassan Shaaban Platform')}</strong><p>{tr('إنشاء حساب طالب جديد', 'Create a student account')}</p></div>
      </header>}
      <ol className="registration-steps" aria-label={tr('خطوات التسجيل', 'Registration steps')}>
        {titles.map((title, index) => <li key={title} className={step > index + 1 ? 'done' : step === index + 1 ? 'current' : ''}
          aria-current={step === index + 1 ? 'step' : undefined}><span>{step > index + 1 ? <Check size={19} /> : index + 1}</span><small>{title}</small></li>)}
      </ol>
      <section className="registration-card" aria-labelledby={prefix + 'heading'}>
        <h1 id={prefix + 'heading'} ref={heading} tabIndex={-1}>{step === 1 ? <User size={22} /> : <Phone size={22} />}{titles[step - 1]}</h1>
        <p className="registration-intro">{step === 1 ? tr('أدخل بياناتك الشخصية بشكل صحيح', 'Enter your personal details accurately') :
          tr('أدخل بيانات التواصل وكلمة المرور لإنشاء حسابك', 'Enter contact details and password to create your account')}</p>
        {serverError && <p className="registration-server-error" role="alert">{serverError}</p>}
        <form noValidate onSubmit={submit} aria-busy={busy}>
          {step === 1 && <>
            <div className="registration-columns">{field('firstName', tr('الاسم الأول', 'First name'), { autocomplete: 'given-name', max: 50 })}{field('middleName', tr('الاسم الأوسط', 'Middle name'), { autocomplete: 'additional-name', max: 50 })}</div>
            {field('lastName', tr('الاسم الأخير', 'Last name'), { autocomplete: 'family-name', max: 50 })}
            <fieldset className="registration-gender" id={id('gender')} tabIndex={-1} aria-describedby={description('gender')}>
              <legend>{tr('النوع', 'Gender')} <span aria-hidden="true">*</span></legend>
              <div className="registration-columns">{(['MALE', 'FEMALE'] as const).map(value => <label key={value} className={data.gender === value ? 'selected' : ''}>
                <input type="radio" name="gender" value={value} checked={data.gender === value} onChange={() => update('gender', value)} />
                {value === 'MALE' ? tr('ذكر', 'Male') : tr('أنثى', 'Female')}
              </label>)}</div>{feedback('gender')}
            </fieldset>
            {select('academicYear', tr('السنة الدراسية', 'School year'), [
              ['1st_secondary', tr('أولى ثانوي', 'Secondary 1')], ['2nd_secondary', tr('ثانية ثانوي', 'Secondary 2')], ['3rd_secondary', tr('ثالثة ثانوي', 'Secondary 3')]], tr('اختر السنة الدراسية', 'Select school year'))}
            {select('educationDivision', tr('الشعبة', 'Education division'), [['GENERAL', tr('عام', 'General')], ['AZHAR', tr('أزهر', 'Azhar')]])}
            {select('specialization', tr('التخصص', 'Specialization'), [['SCIENCE', tr('علمي علوم', 'Science')], ['MATH', tr('علمي رياضة', 'Mathematics')]])}
          </>}
          {step === 2 && <>
            {field('studentPhone', tr('رقم تليفونك الشخصي', 'Student phone'), { type: 'tel', autocomplete: 'tel', max: 20 })}
            <div className="registration-columns">{field('guardianPhone', tr('رقم ولي الأمر', 'Guardian phone'), { type: 'tel', max: 20 })}{field('motherPhone', tr('رقم الأم (اختياري)', 'Mother phone (optional)'), { type: 'tel', optional: true, max: 20 })}</div>
            {select('governorate', tr('المحافظة', 'Governorate'), GOVERNORATES.map(([code, arabic, english]) => [code, tr(arabic, english)] as const), tr('اختر المحافظة', 'Select governorate'))}
            {field('city', tr('المدينة أو المنطقة', 'City or district'), { autocomplete: 'address-level2',
              // Suggestions from the supplied reference, not an exhaustive
              // administrative catalogue. Other areas remain editable.
              suggestions: ar && data.governorate === 'CAIRO' ? ['15 مايو', 'الأزبكية', 'البساتين', 'التبين', 'الخليفة', 'الدراسة', 'الدرب الأحمر', 'الزاوية الحمراء', 'الزيتون', 'الساحل', 'السلام', 'السيدة زينب', 'الشرابية', 'مدينة الشروق', 'الظاهر', 'القاهرة الجديدة', 'المرج', 'عزبة النخل'] : undefined })}
            {field('schoolName', tr('اسم المدرسة', 'School name'), { max: 200 })}
            {field('email', tr('البريد الإلكتروني', 'Email'), { type: 'email', autocomplete: 'email', max: 160 })}
            <p className="registration-hint">{tr('البريد الإلكتروني مطلوب لتسجيل الدخول واسترجاع كلمة المرور.', 'Email is required for sign-in and password recovery.')}</p>
            {field('password', tr('كلمة المرور', 'Password'), { autocomplete: 'new-password' })}
            <p className="registration-hint">{tr('استخدم 10 أحرف على الأقل، وتجنب الكلمات الشائعة.', 'Use at least 10 characters; avoid common passwords.')}</p>
            {field('confirmation', tr('تأكيد كلمة المرور', 'Confirm password'), { autocomplete: 'new-password' })}
            <p className="registration-hint">{tr('لن نرسل SMS. رقم الهاتف وسيلة تواصل، وليس رقمًا موثقًا.', 'No SMS is sent. The phone is a contact number, not a verified number.')}</p>
          </>}
          <button className="registration-primary" disabled={busy} type="submit">{busy ? tr('جاري إنشاء الحساب…', 'Creating account…') : step === 2 ? tr('إنشاء حسابي', 'Create my account') : tr('التالي', 'Next')}{ar ? <ArrowLeft size={18} /> : <ArrowRight size={18} />}</button>
          {step > 1 && <button className="registration-secondary" disabled={busy} type="button" onClick={() => { setStep(step - 1); setErrors({}); setServerError(''); }}>{tr('السابق', 'Previous')}{ar ? <ArrowRight size={18} /> : <ArrowLeft size={18} />}</button>}
        </form>
      </section>
      <p className="registration-signin">{tr('عندك حساب؟', 'Already have an account?')} <button disabled={busy} type="button" onClick={onSignIn}>{tr('سجل دخول', 'Sign in')}</button></p>
    </div>
  </main>;
}

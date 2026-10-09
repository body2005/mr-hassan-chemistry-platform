import { PageLoadingScreen } from "../components/PageLoadingScreen";
import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  GraduationCap,
  Moon,
  Sparkles,
  Sun,
  UserPlus,
  LogIn,
} from "lucide-react";
import { CurrentUser } from "../types/lms";
import { Language, translations } from "../utils/i18n";
import { authService } from "../services/lmsService";
import { RegistrationWizard } from "../components/RegistrationWizard";
import { usePasswordResetAvailability } from "../hooks/usePasswordResetAvailability";
import { authTabHash, readAuthTab, type AuthTab } from "../services/authNavigation";



interface AuthViewProps {
  initialTab?: "signin" | "register";
  onLoginSuccess: (user: CurrentUser) => void;
  onBackToLanding?: () => void;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export const AuthView: React.FC<AuthViewProps> = ({
  initialTab = "signin",
  onLoginSuccess,
  onBackToLanding,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
}) => {
  const t = translations[lang];
  const passwordResetAvailable = usePasswordResetAvailability();
  const [activeTab, setActiveTab] = useState<AuthTab>(() => readAuthTab(window.location.hash, initialTab));

  // Sign In State
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [showSignInPassword, setShowSignInPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.hash.split("?", 2)[1] || "").get("reset_token") || "");
  const [resetMode, setResetMode] = useState<"none" | "request" | "confirm">(resetToken ? "confirm" : "none");
  const [resetEmail, setResetEmail] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [resetBusy, setResetBusy] = useState(false);
  const [resetErrors, setResetErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const syncResetLink = () => {
      const token = new URLSearchParams(window.location.hash.split("?", 2)[1] || "").get("reset_token") || "";
      setResetToken(token);
      setActiveTab(readAuthTab(window.location.hash));
      setResetMode(token ? "confirm" : "none");
    };
    window.addEventListener("hashchange", syncResetLink);
    window.addEventListener("popstate", syncResetLink);
    return () => {
      window.removeEventListener("hashchange", syncResetLink);
      window.removeEventListener("popstate", syncResetLink);
    };
  }, []);

  function selectTab(tab: AuthTab) {
    setActiveTab(tab);
    setResetMode("none");
    setResetToken("");
    setError("");
    setSuccessMsg("");
    window.location.hash = authTabHash(tab);
  }



  // Handle Strict Validated Sign In via authService
  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccessMsg("");

    setIsSubmitting(true);
    try {
      const res = await authService.login(signInEmail, signInPassword);
      if (!res.success) {
        setIsSubmitting(false);
        setError(res.error || (lang === "ar" ? "تعذر تسجيل الدخول" : "Login failed"));
        return;
      }

      if (res.user) {
        onLoginSuccess(res.user);
      }
    } catch {
      setIsSubmitting(false);
      setError(lang === "ar" ? "تعذر تسجيل الدخول، يرجى المحاولة ثانية" : "Login error");
    }
  }



  async function handlePasswordReset(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    const invalid: Record<string, string> = {};
    if (resetMode === 'request' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(resetEmail.trim()))
      invalid.email = lang === 'ar' ? 'أدخل بريدًا إلكترونيًا صحيحًا.' : 'Enter a valid email address.';
    if (resetMode === 'confirm' && (resetPassword.length < 10 || resetPassword.length > 128))
      invalid.password = lang === 'ar' ? 'كلمة المرور يجب أن تكون من 10 إلى 128 حرفًا.' : 'Use 10–128 characters.';
    if (resetMode === 'confirm' && resetPassword !== resetConfirmPassword)
      invalid.confirm = lang === 'ar' ? 'كلمتا المرور غير متطابقتين.' : 'Passwords do not match.';
    setResetErrors(invalid);
    if (Object.keys(invalid).length) return;
    setResetBusy(true);
    try {
      if (resetMode === "request") {
        if (!passwordResetAvailable) {
          setError(lang === "ar" ? "استعادة كلمة المرور بالإيميل غير متاحة. تواصل مع إدارة المنصة." : "Email recovery is unavailable. Contact the platform administration.");
          return;
        }
        await authService.requestPasswordReset(resetEmail);
        setSuccessMsg(lang === "ar" ? "إذا كان الحساب موجودًا، ستصلك رسالة الاسترجاع." : "If the account exists, a reset email will arrive.");
      } else if (resetMode === "confirm") {
        await authService.confirmPasswordReset(resetToken, resetPassword);
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#auth`);
        setResetToken("");
        setResetMode("none");
        setSuccessMsg(lang === "ar" ? "تم تغيير كلمة المرور. سجّل الدخول بالكلمة الجديدة." : "Password changed. Sign in with the new password.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : (lang === "ar" ? "تعذر إكمال الطلب" : "Unable to complete the request"));
    } finally {
      setResetBusy(false);
    }
  }

  // Animation directions based on RTL/LTR and activeTab
  const isRtl = lang === "ar";
  // In RTL: Default (signin) Form is on Right (0%), Hero is on Left (0%).
  // When Register: Form moves to Left (translate -100%), Hero moves to Right (translate +100%).
  const formTransform = isRtl
    ? activeTab === "signin" ? "translateX(0%)" : "translateX(-100%)"
    : activeTab === "signin" ? "translateX(0%)" : "translateX(100%)";

  const heroTransform = isRtl
    ? activeTab === "signin" ? "translateX(0%)" : "translateX(100%)"
    : activeTab === "signin" ? "translateX(0%)" : "translateX(-100%)";

  if (isSubmitting) {
    return <PageLoadingScreen brandTitle="منصة الكيمياء التعليمية — مستر حسن شعبان" />;
  }

  const registrationView = (
    <RegistrationWizard embedded lang={lang} theme={theme} onToggleLang={onToggleLang}
      onToggleTheme={onToggleTheme} onSignIn={() => selectTab("signin")}
      onBack={onBackToLanding} onSuccess={onLoginSuccess} />
  );

  return (
    <div
      className="auth-page-shell"
      style={{
        width: "100vw",
        minHeight: "100dvh",
        height: "100dvh",
        margin: 0,
        padding: 0,
        position: "relative",
        overflowX: "hidden",
        overflowY: "auto",
        backgroundColor: "var(--bg-surface)",
      }}
    >
      {/* ===================== TOP FIXED TOOLBAR & TOGGLE PILL ===================== */}
      {/* 1. Language + Theme Toggle */}
      <div
        style={{
          position: "absolute",
          top: "18px",
          [lang === "ar" ? "left" : "right"]: "24px",
          zIndex: 80,
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <button
          onClick={onToggleTheme}
          style={{
            width: "38px",
            height: "38px",
            borderRadius: "10px",
            background: theme === "dark" ? "rgb(17, 24, 39)" : "rgba(255, 255, 255, 0.85)",
            backdropFilter: "blur(10px)",
            border: theme === "dark" ? "1px solid rgb(55, 65, 81)" : "1px solid var(--border-color)",
            color: theme === "dark" ? "#f3f4f6" : "var(--text-main)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            boxShadow: theme === "dark" ? "0 2px 10px rgba(0,0,0,0.4)" : "0 2px 10px rgba(0,0,0,0.06)",
          }}
          title={theme === "dark" ? t.toggleThemeLight : t.toggleThemeDark}
          aria-label={lang === "ar" ? "تغيير المظهر" : "Change theme"}
        >
          {theme === "dark" ? <Sun size={16} style={{ color: "#f59e0b" }} /> : <Moon size={16} />}
        </button>

        <button
          onClick={onToggleLang}
          style={{
            height: "38px",
            borderRadius: "10px",
            background: theme === "dark" ? "rgb(17, 24, 39)" : "rgba(255, 255, 255, 0.85)",
            backdropFilter: "blur(10px)",
            border: theme === "dark" ? "1px solid rgb(55, 65, 81)" : "1px solid var(--border-color)",
            color: theme === "dark" ? "#f3f4f6" : "var(--text-main)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            padding: "0 14px",
            fontSize: "13px",
            fontWeight: 800,
            letterSpacing: "0.05em",
            boxShadow: theme === "dark" ? "0 2px 10px rgba(0,0,0,0.4)" : "0 2px 10px rgba(0,0,0,0.06)",
          }}
          title="Switch Language / تغيير اللغة"
        >
          {lang === "ar" ? "AR" : "EN"}
        </button>
      </div>

      {/* 2. Return to Landing Button */}
      {onBackToLanding && (
        <button
          onClick={onBackToLanding}
          style={{
            position: "absolute",
            top: "18px",
            [lang === "ar" ? "right" : "left"]: "24px",
            zIndex: 80,
            background: theme === "dark" ? "rgb(17, 24, 39)" : "rgba(255, 255, 255, 0.85)",
            backdropFilter: "blur(10px)",
            border: theme === "dark" ? "1px solid rgb(55, 65, 81)" : "1px solid var(--border-color)",
            color: theme === "dark" ? "#f3f4f6" : "var(--text-main)",
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "12px",
            fontWeight: 800,
            padding: "8px 16px",
            borderRadius: "30px",
            boxShadow: theme === "dark" ? "0 2px 10px rgba(0,0,0,0.4)" : "0 2px 10px rgba(0,0,0,0.06)",
          }}
        >
          {lang === "ar" ? <ArrowRight size={14} /> : <ArrowLeft size={14} />}
          <span>{lang === "ar" ? "الرئيسية" : "Home"}</span>
        </button>
      )}

      {/* ===================== SLIDING SPLIT-SCREEN CONTAINER ===================== */}
      <div
        className="auth-split-box"
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          position: "relative",
        }}
      >
        {/* ===================== PANEL 1: FORM CONTAINER (Sliding Panel) ===================== */}
        <div
          className="auth-form-panel"
          style={{
            position: "absolute",
            top: 0,
            [isRtl ? "right" : "left"]: 0,
            width: "50%",
            height: "100%",
            background: "var(--bg-surface)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-start",
            alignItems: "center",
            padding: "60px 48px 30px",
            boxSizing: "border-box",
            overflowY: "auto",
            zIndex: 10,
            transform: formTransform,
            transition: "transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          <div style={{ maxWidth: "540px", width: "100%", margin: "auto 0", flexShrink: 0 }}>
            {/* Tab Switcher Pill (Moved down into the form header area) */}
            <div
              dir="rtl"
              aria-label={lang === "ar" ? "نوع الدخول" : "Account access"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: theme === "dark" ? "rgb(17, 24, 39)" : "var(--bg-surface-secondary, #f1f5f9)",
                border: theme === "dark" ? "1.5px solid rgb(55, 65, 81)" : "1.5px solid var(--border-color-strong, #cbd5e1)",
                padding: "4px",
                borderRadius: "32px",
                marginBottom: "22px",
                gap: "4px",
                width: "fit-content",
                marginInline: "auto",
                boxShadow: theme === "dark" ? "0 4px 14px rgba(0, 0, 0, 0.3)" : "0 2px 10px rgba(0, 0, 0, 0.05)",
              }}
            >
              {/* Sign In Toggle Button */}
              <button
                type="button"
                aria-pressed={activeTab === "signin"}
                onClick={() => {
                  selectTab("signin");
                  setError("");
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 18px",
                  borderRadius: "24px",
                  border: "none",
                  background: activeTab === "signin" ? "#0f392b" : "transparent",
                  color: activeTab === "signin" ? "#ffffff" : (theme === "dark" ? "#9ca3af" : "var(--text-muted, #64748b)"),
                  fontSize: "13px",
                  fontWeight: 800,
                  cursor: "pointer",
                  transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                  boxShadow: activeTab === "signin" ? "0 2px 8px rgba(15, 57, 43, 0.3)" : "none",
                }}
              >
                <LogIn size={14} />
                <span>{lang === "ar" ? "تسجيل الدخول" : "Sign In"}</span>
              </button>

              {/* Register Toggle Button */}
              <button
                type="button"
                aria-pressed={activeTab === "register"}
                onClick={() => {
                  selectTab("register");
                  setError("");
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 18px",
                  borderRadius: "24px",
                  border: "none",
                  background: activeTab === "register" ? "#0f392b" : "transparent",
                  color: activeTab === "register" ? "#ffffff" : (theme === "dark" ? "#9ca3af" : "var(--text-muted, #64748b)"),
                  fontSize: "13px",
                  fontWeight: 800,
                  cursor: "pointer",
                  transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                  boxShadow: activeTab === "register" ? "0 2px 8px rgba(15, 57, 43, 0.3)" : "none",
                }}
              >
                <UserPlus size={14} />
                <span>{lang === "ar" ? "تسجيل جديد" : "Register"}</span>
              </button>
            </div>

            {/* Header Brand Info */}
            <div style={{ marginBottom: "20px", textAlign: "right" }}>
              <span style={{ fontSize: "14px", fontWeight: 900, color: "var(--text-main)", display: "block", marginBottom: "2px" }}>
                {t.brandTitle}
              </span>
              <h2 style={{ fontSize: "24px", fontWeight: 900, color: "var(--text-main)", margin: "0 0 4px" }}>
                {activeTab === "signin"
                  ? lang === "ar" ? "تسجيل الدخول للمنصة" : "Sign In to Platform"
                  : lang === "ar" ? "تسجيل حساب جديد" : "Create Account"}
              </h2>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.5" }}>
                {activeTab === "signin"
                  ? lang === "ar" ? "أدخل بريدك الإلكتروني وكلمة المرور المسجلة للمتابعة." : "Enter your registered email and password to continue."
                  : lang === "ar" ? "سجل بياناتك كطالب للانضمام إلى منصة الكيمياء المعتمدة مع مستر حسن شعبان." : "Register your student details to join the accredited chemistry platform with Mr. Hassan Shaaban."}
              </p>
            </div>

            {/* Error & Success Messages */}
            {error && (
              <div
                id="auth-error"
                role="alert"
                style={{
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#dc2626",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: 700,
                  marginBottom: "14px",
                  lineHeight: "1.4",
                }}
              >
                {error}
              </div>
            )}

            {successMsg && (
              <div
                style={{
                  background: "#ecfdf5",
                  border: "1px solid #a7f3d0",
                  color: "#065f46",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: 700,
                  marginBottom: "14px",
                }}
              >
                {successMsg}
              </div>
            )}

            {/* ===================== VIEW A: SIGN IN FORM ===================== */}
            {activeTab === "signin" && resetMode !== "none" ? (
              <form className="password-reset-form" noValidate onSubmit={handlePasswordReset}
                aria-describedby={error ? 'auth-error' : undefined}
                style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <h3>{resetMode === "request" ? (lang === "ar" ? "استرجاع كلمة المرور" : "Reset your password") : (lang === "ar" ? "كلمة مرور جديدة" : "Set a new password")}</h3>
                {resetMode === "request" ? (
                  <div>
                  <label htmlFor="reset-email">{lang === 'ar' ? 'بريد الاسترجاع' : 'Reset email'}</label>
                  <input id="reset-email"
                    aria-label={lang === "ar" ? "بريد الاسترجاع" : "Reset email"}
                    type="email"
                    required
                    value={resetEmail}
                    onChange={(event) => setResetEmail(event.target.value)}
                    autoComplete="email"
                    dir="ltr"
                    aria-invalid={Boolean(resetErrors.email)}
                    aria-describedby={resetErrors.email ? 'reset-email-error' : undefined}
                  />
                  {resetErrors.email && <p id="reset-email-error" role="alert">{resetErrors.email}</p>}
                  </div>
                ) : (
                  <>
                    <div>
                    <label htmlFor="reset-password">{lang === 'ar' ? 'كلمة المرور الجديدة' : 'New password'}</label>
                    <p id="reset-password-help">{lang === 'ar' ? 'استخدم من 10 إلى 128 حرفًا، واختر كلمة لا تستخدمها في مواقع أخرى.' : 'Use 10–128 characters and a password unique to this site.'}</p>
                    <input id="reset-password"
                      aria-label={lang === "ar" ? "كلمة المرور الجديدة" : "New password"}
                      type="password"
                      required
                      minLength={10}
                      maxLength={128}
                      value={resetPassword}
                      onChange={(event) => setResetPassword(event.target.value)}
                      autoComplete="new-password"
                      aria-invalid={Boolean(resetErrors.password)}
                      aria-describedby={`reset-password-help${resetErrors.password ? ' reset-password-error' : ''}`}
                    />
                    {resetErrors.password && <p id="reset-password-error" role="alert">{resetErrors.password}</p>}
                    </div>
                    <div>
                    <label htmlFor="reset-confirm">{lang === 'ar' ? 'تأكيد كلمة المرور الجديدة' : 'Confirm new password'}</label>
                    <input id="reset-confirm"
                      aria-label={lang === "ar" ? "تأكيد كلمة المرور الجديدة" : "Confirm new password"}
                      type="password"
                      required
                      minLength={10}
                      maxLength={128}
                      value={resetConfirmPassword}
                      onChange={(event) => setResetConfirmPassword(event.target.value)}
                      autoComplete="new-password"
                      aria-invalid={Boolean(resetErrors.confirm)}
                      aria-describedby={resetErrors.confirm ? 'reset-confirm-error' : undefined}
                    />
                    {resetErrors.confirm && <p id="reset-confirm-error" role="alert">{resetErrors.confirm}</p>}
                    </div>
                  </>
                )}
                <button type="submit" className="btn-primary" disabled={resetBusy}>
                  {resetBusy ? (lang === "ar" ? "جارٍ الإرسال..." : "Sending...") : resetMode === "request" ? (lang === "ar" ? "إرسال رابط الاسترجاع" : "Send reset link") : (lang === "ar" ? "تغيير كلمة المرور" : "Change password")}
                </button>
                <button type="button" onClick={() => {
                  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#auth`);
                  setResetToken("");
                  setResetMode("none");
                  setError("");
                  setResetErrors({});
                }}>
                  {lang === "ar" ? "العودة لتسجيل الدخول" : "Back to sign in"}
                </button>
              </form>
            ) : activeTab === "signin" ? (
              <form onSubmit={handleSignIn} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label htmlFor="auth-signin-identity" style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "5px", textTransform: "uppercase" }}>
                    {lang === "ar" ? "البريد الإلكتروني أو اسم المستخدم" : "Email or Username"}
                  </label>
                  <input
                    id="auth-signin-identity"
                    autoComplete="username"
                    type="text"
                    required
                    value={signInEmail}
                    onChange={(e) => setSignInEmail(e.target.value)}
                    placeholder={lang === "ar" ? "مثال: teacher@demo.com أو اسم المستخدم" : "e.g. teacher@demo.com or username"}
                    style={{
                      width: "100%",
                      padding: "11px 14px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "10px",
                      fontSize: "13px",
                      background: "var(--bg-surface-secondary)",
                      color: "var(--text-main)",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div>
                  <label htmlFor="auth-signin-password" style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "5px", textTransform: "uppercase" }}>
                    {t.passwordLabel}
                  </label>
                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                    <input
                      id="auth-signin-password"
                      autoComplete="current-password"
                      type={showSignInPassword ? "text" : "password"}
                      required
                      value={signInPassword}
                      onChange={(e) => setSignInPassword(e.target.value)}
                      placeholder="••••••••"
                      style={{
                        width: "100%",
                        padding: isRtl ? "11px 40px 11px 14px" : "11px 14px 11px 40px",
                        border: "1px solid var(--border-color-strong)",
                        borderRadius: "10px",
                        fontSize: "13px",
                        background: "var(--bg-surface-secondary)",
                        color: "var(--text-main)",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowSignInPassword(!showSignInPassword)}
                      style={{
                        position: "absolute",
                        [isRtl ? "left" : "right"]: "12px",
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        padding: "4px",
                      }}
                      title={showSignInPassword ? (lang === "ar" ? "إخفاء كلمة المرور" : "Hide password") : (lang === "ar" ? "إظهار كلمة المرور" : "Show password")}
                    >
                      {showSignInPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  style={{
                    width: "100%",
                    justifyContent: "center",
                    padding: "12px",
                    borderRadius: "10px",
                    fontSize: "14px",
                    fontWeight: 800,
                    marginTop: "4px",
                  }}
                >
                  {lang === "ar" ? "تسجيل الدخول للمنصة" : "Sign In to Platform"}
                </button>

                {passwordResetAvailable === true && <button
                  type="button"
                  onClick={() => { setResetMode("request"); setError(""); setSuccessMsg(""); }}
                  style={{ background: "none", border: "none", color: "#059669", cursor: "pointer", fontWeight: 700 }}
                >
                  {lang === "ar" ? "نسيت كلمة المرور؟" : "Forgot password?"}
                </button>}
                {passwordResetAvailable === false && <p style={{ color: "var(--text-muted)", fontSize: "14px" }}>
                  {lang === "ar" ? "لو نسيت كلمة المرور، تواصل مع إدارة المنصة." : "Forgot your password? Contact the platform administration."}
                </p>}

                <div style={{ textAlign: "center", marginTop: "8px" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    {lang === "ar" ? "طالب جديد ليس لديك حساب؟ " : "New student without an account? "}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      selectTab("register");
                      setError("");
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#059669",
                      fontWeight: 800,
                      fontSize: "12px",
                      cursor: "pointer",
                    }}
                  >
                    {lang === "ar" ? "إنشاء حساب الآن" : "Register now"}
                  </button>
                </div>
              </form>
            ) : (
              /* ===================== VIEW B: STUDENT REGISTER FORM ===================== */
              registrationView
            )}
          </div>
        </div>

        {/* ===================== PANEL 2: BRANDING HERO (Sliding Panel) ===================== */}
        <div
          className="auth-overlay-panel"
          style={{
            position: "absolute",
            top: 0,
            [isRtl ? "left" : "right"]: 0,
            width: "50%",
            height: "100%",
            background: "#0f392b",
            color: "#ffffff",
            padding: "60px 48px 30px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            boxSizing: "border-box",
            overflow: "hidden",
            zIndex: 10,
            transform: heroTransform,
            transition: "transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          {/* Geometric Background Circles */}
          <div style={{ position: "absolute", top: "-15%", right: "-20%", width: "650px", height: "650px", borderRadius: "50%", border: "1.5px solid rgba(255, 255, 255, 0.08)", pointerEvents: "none" }} />
          <div style={{ position: "absolute", top: "-5%", right: "-10%", width: "500px", height: "500px", borderRadius: "50%", border: "1.5px solid rgba(255, 255, 255, 0.06)", pointerEvents: "none" }} />
          <div style={{ position: "absolute", bottom: "-20%", left: "-15%", width: "600px", height: "600px", borderRadius: "50%", border: "1.5px solid rgba(255, 255, 255, 0.07)", pointerEvents: "none" }} />

          {/* Top Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: "14px", zIndex: 2 }}>
            <div
              style={{
                width: "46px",
                height: "46px",
                borderRadius: "14px",
                background: "rgba(255, 255, 255, 0.12)",
                backdropFilter: "blur(10px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "1px solid rgba(255, 255, 255, 0.18)",
              }}
            >
              <GraduationCap size={26} fill="white" />
            </div>
            <div>
              <strong style={{ fontSize: "16px", display: "block", letterSpacing: "-0.02em" }}>
                {t.brandTitle}
              </strong>
              <span style={{ fontSize: "11px", opacity: 0.8 }}>{t.brandSubtitle}</span>
            </div>
          </div>

          {/* Middle Value Props */}
          <div style={{ zIndex: 2, margin: "auto 0" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "20px",
                background: "rgba(255, 255, 255, 0.12)",
                fontSize: "12px",
                fontWeight: 700,
                marginBottom: "16px",
                border: "1px solid rgba(255, 255, 255, 0.15)",
              }}
            >
              <Sparkles size={14} style={{ color: "#34d399" }} />
              {lang === "ar" ? "بيئة تعليمية ذكية متكاملة للمناهج الدراسية" : "Smart Learning Ecosystem"}
            </span>

            <h1 style={{ fontSize: "28px", fontWeight: 900, lineHeight: "1.3", margin: "0 0 14px" }}>
              {activeTab === "signin"
                ? lang === "ar"
                  ? "انضم الآن إلى المنصة التعليمية المعتمدة للثانوية العامة"
                  : "Welcome Back to the Accredited Learning Platform"
                : lang === "ar"
                  ? "سجّل حسابك وابدأ رحلة التفوق الدراسي"
                  : "Register Today & Master High School Curricula"}
            </h1>

            <p style={{ fontSize: "13px", opacity: 0.85, lineHeight: "1.6", margin: "0 0 24px" }}>
              {lang === "ar"
                ? "شروحات فيديو تفاعلية، مذكرات حصرية، واختبارات وواجبات إلكترونية مع تصحيح مباشر من المعلم."
                : "Interactive video lessons, exclusive study guides, and online quizzes & homework graded directly by your teacher."}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {[
                lang === "ar" ? "فيديوهات شروحات متطورة ومذكرات PDF حصرية" : "Advanced video lectures & exclusive PDF notes",
                lang === "ar" ? "تنبيهات مجدولة وإشعارات دقيقة لمواعيد صفك" : "Scheduled notifications strictly tied to your class",
                lang === "ar" ? "متابعة مستمرة لدرجاتك ومستوى تقدمك في المنهج" : "Continuous tracking of your grades and progress",
              ].map((item, idx) => (
                <div key={idx} style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "12.5px" }}>
                  <div
                    style={{
                      width: "20px",
                      height: "20px",
                      borderRadius: "50%",
                      background: "rgba(52, 211, 153, 0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <CheckCircle2 size={13} style={{ color: "#34d399" }} />
                  </div>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

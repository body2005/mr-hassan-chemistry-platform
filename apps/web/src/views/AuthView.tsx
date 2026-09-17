import { PageLoadingScreen } from "../components/PageLoadingScreen";
import React, { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  GraduationCap,
  Moon,
  ShieldCheck,
  Sparkles,
  Sun,
  UserPlus,
  LogIn,
} from "lucide-react";
import { CurrentUser } from "../types/lms";
import { Language, translations } from "../utils/i18n";
import { authService } from "../services/lmsService";

const GOVERNORATES = [
  ["ALEXANDRIA", "الإسكندرية", "Alexandria"], ["ASWAN", "أسوان", "Aswan"], ["ASIUT", "أسيوط", "Asiut"],
  ["BEHEIRA", "البحيرة", "Beheira"], ["BENI_SUEF", "بني سويف", "Beni Suef"], ["CAIRO", "القاهرة", "Cairo"],
  ["DAKAHLIA", "الدقهلية", "Dakahlia"], ["DAMIETTA", "دمياط", "Damietta"], ["FAYOUM", "الفيوم", "Fayoum"],
  ["GHARBIA", "الغربية", "Gharbia"], ["GIZA", "الجيزة", "Giza"], ["ISMAILIA", "الإسماعيلية", "Ismailia"],
  ["KAFR_EL_SHEIKH", "كفر الشيخ", "Kafr El Sheikh"], ["LUXOR", "الأقصر", "Luxor"], ["MATROUH", "مطروح", "Matrouh"],
  ["MINYA", "المنيا", "Minya"], ["MONUFIA", "المنوفية", "Monufia"], ["NEW_VALLEY", "الوادي الجديد", "New Valley"],
  ["NORTH_SINAI", "شمال سيناء", "North Sinai"], ["PORT_SAID", "بورسعيد", "Port Said"], ["QALYUBIA", "القليوبية", "Qalyubia"],
  ["QENA", "قنا", "Qena"], ["RED_SEA", "البحر الأحمر", "Red Sea"], ["SHARQIA", "الشرقية", "Sharqia"],
  ["SOHAG", "سوهاج", "Sohag"], ["SOUTH_SINAI", "جنوب سيناء", "South Sinai"], ["SUEZ", "السويس", "Suez"],
] as const;

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
  const [activeTab, setActiveTab] = useState<"signin" | "register">(initialTab);

  // Sign In State
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [showSignInPassword, setShowSignInPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Student Register State
  const [regName, setRegName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [regConfirmPassword, setRegConfirmPassword] = useState("");
  const [showRegConfirmPassword, setShowRegConfirmPassword] = useState(false);
  const [regYear, setRegYear] = useState<"" | "1st_secondary" | "2nd_secondary" | "3rd_secondary">("");
  const [regStudentPhone, setRegStudentPhone] = useState("");
  const [regGuardianPhone, setRegGuardianPhone] = useState("");
  const [regNationalId, setRegNationalId] = useState("");
  const [regGovernorate, setRegGovernorate] = useState("");
  const [regSchoolName, setRegSchoolName] = useState("");
  const [regGender, setRegGender] = useState<"" | "MALE" | "FEMALE">("");
  const [regReligion, setRegReligion] = useState<"" | "MUSLIM" | "CHRISTIAN" | "OTHER" | "PREFER_NOT_TO_SAY">("");

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

  // Handle Student Registration via authService
  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccessMsg("");

    if (regPassword !== regConfirmPassword) {
      setError(lang === "ar" ? "كلمتا المرور غير متطابقتين، يرجى التأكد من تطابق كلمة المرور وتأكيدها." : "Passwords do not match. Please verify confirmation.");
      return;
    }

    if (regPassword.length < 6) {
      setError(lang === "ar" ? "يجب أن تكون كلمة المرور 6 أحرف أو أرقام على الأقل." : "Password must be at least 6 characters.");
      return;
    }

    if (!regYear || !regGovernorate || !regSchoolName.trim() || !regGender || !regReligion) {
      setError(lang === "ar" ? "يرجى استكمال الصف والمحافظة والمدرسة والنوع والديانة." : "Please complete grade, governorate, school, gender, and religion.");
      return;
    }

    const res = await authService.register({
      name: regName,
      email: regEmail,
      password: regPassword,
      academicYear: regYear,
      studentPhone: regStudentPhone,
      guardianPhone: regGuardianPhone,
      nationalId: regNationalId,
      governorate: regGovernorate,
      schoolName: regSchoolName,
      gender: regGender,
      religion: regReligion,
    });

    if (!res.success) {
      setError(res.error || (lang === "ar" ? "تعذر إنشاء الحساب" : "Registration failed"));
      return;
    }

    if (res.user) {
      setSuccessMsg(lang === "ar" ? "تم إنشاء الحساب بنجاح! جاري الدخول..." : "Account created successfully! Logging in...");
      setTimeout(() => {
        onLoginSuccess(res.user!);
      }, 600);
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
            justifyContent: "center",
            alignItems: "center",
            padding: "60px 48px 30px",
            boxSizing: "border-box",
            overflowY: "auto",
            zIndex: 10,
            transform: formTransform,
            transition: "transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          <div style={{ maxWidth: "440px", width: "100%", margin: "auto 0" }}>
            {/* Tab Switcher Pill (Moved down into the form header area) */}
            <div
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
                onClick={() => {
                  setActiveTab("signin");
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
                onClick={() => {
                  setActiveTab("register");
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
            {activeTab === "signin" ? (
              <form onSubmit={handleSignIn} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "5px", textTransform: "uppercase" }}>
                    {lang === "ar" ? "البريد الإلكتروني أو اسم المستخدم" : "Email or Username"}
                  </label>
                  <input
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
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "5px", textTransform: "uppercase" }}>
                    {t.passwordLabel}
                  </label>
                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                    <input
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

                <div style={{ textAlign: "center", marginTop: "8px" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    {lang === "ar" ? "طالب جديد ليس لديك حساب؟ " : "New student without an account? "}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("register");
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
              <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                    {lang === "ar" ? "اسم الطالب رباعي:" : "Full Student Name:"}
                  </label>
                  <input
                    type="text"
                    required
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    placeholder={lang === "ar" ? "مثال: عمر زيدان عبد الرحمن" : "e.g. Omar Zeidan Abdelrahman"}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "8px",
                      fontSize: "13px",
                      background: "var(--bg-surface-secondary)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                    {t.emailLabel}:
                  </label>
                  <input
                    type="email"
                    required
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="student@example.com"
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "8px",
                      fontSize: "13px",
                      background: "var(--bg-surface-secondary)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                {/* Password and Confirm Password Row with Eye Toggles */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                      {t.passwordLabel}:
                    </label>
                    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                      <input
                        type={showRegPassword ? "text" : "password"}
                        required
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        placeholder="••••••••"
                        style={{
                          width: "100%",
                          padding: isRtl ? "9px 34px 9px 10px" : "9px 10px 9px 34px",
                          border: "1px solid var(--border-color-strong)",
                          borderRadius: "8px",
                          fontSize: "13px",
                          background: "var(--bg-surface-secondary)",
                          color: "var(--text-main)",
                          boxSizing: "border-box",
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowRegPassword(!showRegPassword)}
                        style={{
                          position: "absolute",
                          [isRtl ? "left" : "right"]: "8px",
                          background: "none",
                          border: "none",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          padding: "2px",
                        }}
                        title={showRegPassword ? (lang === "ar" ? "إخفاء كلمة المرور" : "Hide password") : (lang === "ar" ? "إظهار كلمة المرور" : "Show password")}
                      >
                        {showRegPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                      {lang === "ar" ? "تأكيد كلمة المرور:" : "Confirm Password:"}
                    </label>
                    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                      <input
                        type={showRegConfirmPassword ? "text" : "password"}
                        required
                        value={regConfirmPassword}
                        onChange={(e) => setRegConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        style={{
                          width: "100%",
                          padding: isRtl ? "9px 34px 9px 10px" : "9px 10px 9px 34px",
                          border: "1px solid var(--border-color-strong)",
                          borderRadius: "8px",
                          fontSize: "13px",
                          background: "var(--bg-surface-secondary)",
                          color: "var(--text-main)",
                          boxSizing: "border-box",
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowRegConfirmPassword(!showRegConfirmPassword)}
                        style={{
                          position: "absolute",
                          [isRtl ? "left" : "right"]: "8px",
                          background: "none",
                          border: "none",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          padding: "2px",
                        }}
                        title={showRegConfirmPassword ? (lang === "ar" ? "إخفاء كلمة المرور" : "Hide password") : (lang === "ar" ? "إظهار كلمة المرور" : "Show password")}
                      >
                        {showRegConfirmPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Academic Year Selection */}
                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                    {lang === "ar" ? "الصف الدراسي (تحدد المواد بناءً عليه):" : "Academic Year:"}
                  </label>
                  <select
                    value={regYear}
                    onChange={(e) => setRegYear(e.target.value as "1st_secondary" | "2nd_secondary" | "3rd_secondary")}
                    required
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "8px",
                      fontSize: "13px",
                      background: "var(--bg-surface-secondary)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                      fontWeight: 700,
                    }}
                  >
                    <option value="" disabled>{lang === "ar" ? "اختر الصف الدراسي" : "Select academic year"}</option>
                    <option value="1st_secondary">{lang === "ar" ? "الصف الأول الثانوي" : "1st Secondary Year"}</option>
                    <option value="2nd_secondary">{lang === "ar" ? "الصف الثاني الثانوي" : "2nd Secondary Year"}</option>
                    <option value="3rd_secondary">{lang === "ar" ? "الصف الثالث الثانوي" : "3rd Secondary Year"}</option>
                  </select>
                </div>

                {/* Phone Numbers */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                      {lang === "ar" ? "هاتف الطالب:" : "Student Phone:"}
                    </label>
                    <input
                      type="tel"
                      inputMode="numeric"
                      maxLength={11}
                      value={regStudentPhone}
                      onChange={(e) => setRegStudentPhone(e.target.value)}
                      placeholder="010XXXXXXXX"
                      style={{
                        width: "100%",
                        padding: "9px 12px",
                        border: "1px solid var(--border-color-strong)",
                        borderRadius: "8px",
                        fontSize: "12px",
                        background: "var(--bg-surface-secondary)",
                        color: "var(--text-main)",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                      {lang === "ar" ? "هاتف ولي الأمر:" : "Guardian Phone:"}
                    </label>
                    <input
                      type="tel"
                      inputMode="numeric"
                      maxLength={11}
                      value={regGuardianPhone}
                      onChange={(e) => setRegGuardianPhone(e.target.value)}
                      placeholder="011XXXXXXXX"
                      style={{
                        width: "100%",
                        padding: "9px 12px",
                        border: "1px solid var(--border-color-strong)",
                        borderRadius: "8px",
                        fontSize: "12px",
                        background: "var(--bg-surface-secondary)",
                        color: "var(--text-main)",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>
                    {lang === "ar" ? "الرقم القومي:" : "National ID:"}
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={14}
                    value={regNationalId}
                    onChange={(e) => setRegNationalId(e.target.value)}
                    placeholder="30608150104892"
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      background: "var(--bg-surface-secondary)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>{lang === "ar" ? "المحافظة:" : "Governorate:"}</label>
                    <select required value={regGovernorate} onChange={(e) => setRegGovernorate(e.target.value)} style={{ width: "100%", padding: "9px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", background: "var(--bg-surface-secondary)", color: "var(--text-main)" }}>
                      <option value="" disabled>{lang === "ar" ? "اختر المحافظة" : "Select governorate"}</option>
                      {GOVERNORATES.map(([code, ar, en]) => <option key={code} value={code}>{lang === "ar" ? ar : en}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>{lang === "ar" ? "المدرسة:" : "School:"}</label>
                    <input required minLength={2} maxLength={200} value={regSchoolName} onChange={(e) => setRegSchoolName(e.target.value)} placeholder={lang === "ar" ? "اسم المدرسة" : "School name"} style={{ width: "100%", padding: "9px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", boxSizing: "border-box", background: "var(--bg-surface-secondary)", color: "var(--text-main)" }} />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>{lang === "ar" ? "النوع:" : "Gender:"}</label>
                    <select required value={regGender} onChange={(e) => setRegGender(e.target.value as "" | "MALE" | "FEMALE")} style={{ width: "100%", padding: "9px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", background: "var(--bg-surface-secondary)", color: "var(--text-main)" }}><option value="" disabled>{lang === "ar" ? "اختر النوع" : "Select gender"}</option><option value="MALE">{lang === "ar" ? "ذكر" : "Male"}</option><option value="FEMALE">{lang === "ar" ? "أنثى" : "Female"}</option></select>
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "3px" }}>{lang === "ar" ? "الديانة:" : "Religion:"}</label>
                    <select required value={regReligion} onChange={(e) => setRegReligion(e.target.value as typeof regReligion)} style={{ width: "100%", padding: "9px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", background: "var(--bg-surface-secondary)", color: "var(--text-main)" }}><option value="" disabled>{lang === "ar" ? "اختر الديانة" : "Select religion"}</option><option value="MUSLIM">{lang === "ar" ? "مسلم" : "Muslim"}</option><option value="CHRISTIAN">{lang === "ar" ? "مسيحي" : "Christian"}</option><option value="OTHER">{lang === "ar" ? "أخرى" : "Other"}</option><option value="PREFER_NOT_TO_SAY">{lang === "ar" ? "أفضل عدم الإفصاح" : "Prefer not to say"}</option></select>
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  style={{
                    width: "100%",
                    justifyContent: "center",
                    padding: "11px",
                    borderRadius: "10px",
                    fontSize: "13.5px",
                    fontWeight: 800,
                    marginTop: "4px",
                  }}
                >
                  {lang === "ar" ? "تسجيل وإنشاء الحساب مباشرة" : "Complete Registration"}
                </button>
              </form>
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
                ? "شروحات فيديو تفاعلية، مذكرات حصرية، تصحيح ذكي للواجبات والمقالات، وتوقعات صعوبة دقيقة للمنهج."
                : "Interactive video lessons, exclusive study guides, AI-assisted grading, and real-time difficulty forecasting."}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {[
                lang === "ar" ? "فيديوهات شروحات متطورة ومذكرات PDF حصرية" : "Advanced video lectures & exclusive PDF notes",
                lang === "ar" ? "تنبيهات مجدولة وإشعارات دقيقة لمواعيد صفك" : "Scheduled notifications strictly tied to your class",
                lang === "ar" ? "مساعد ذكاء اصطناعي تفاعلي للإجابة وتفسير الدروس" : "Interactive AI tutor for instant 24/7 homework help",
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

          {/* Bottom Security Footer */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11.5px", opacity: 0.75, zIndex: 2 }}>
            <ShieldCheck size={16} />
            <span>
              {lang === "ar" ? "نظام آمن ومشفر ومعتمد رسمياً من وزارة التربية والتعليم" : "Secure, encrypted & officially accredited platform"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

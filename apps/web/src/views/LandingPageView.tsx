import React, { useState, useMemo, useEffect } from "react";
import {
  Award,
  CheckCircle2,
  ChevronDown,
  Clock,
  GraduationCap,
  Grid,
  Mail,
  Menu,
  Moon,
  Phone,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
  Video,
  X,
} from "lucide-react";
import { Course } from "../types/lms";
import { Language, translations } from "../utils/i18n";
import { useToast } from "../components/ToastProvider";
import { filterCatalog, readCatalogState, saveCatalogState, type CatalogGrade } from '../services/catalogState';
import { usePublicCatalog } from '../services/usePublicCatalog';

interface LandingPageViewProps {
  courses?: Course[];
  onNavigateToAuth: (tab?: "signin" | "register", course?: Course) => void;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export const LandingPageView: React.FC<LandingPageViewProps> = ({
  courses,
  onNavigateToAuth,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
}) => {
  const toast = useToast();
  const [showYearsDropdown, setShowYearsDropdown] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileYearsOpen, setMobileYearsOpen] = useState(false);
  const [selectedGrade, setSelectedGrade] = useState<CatalogGrade>(() => readCatalogState().grade);
  const t = translations[lang];
  const catalog = usePublicCatalog('', selectedGrade, courses === undefined);

  // A readable, static heading: no typing/deleting timer or blinking cursor.
  const filteredCourses = useMemo(() => courses === undefined ? catalog.courses : filterCatalog(courses, '', selectedGrade),
    [courses, catalog.courses, selectedGrade]);
  const grades = [
    { id: '1st_secondary' as const, label: t.firstSecondary },
    { id: '2nd_secondary' as const, label: t.secondSecondary },
    { id: '3rd_secondary' as const, label: t.thirdSecondary },
  ];
  const changeGrade = (grade: CatalogGrade) => {
    setSelectedGrade(grade); saveCatalogState('', grade);
    setShowYearsDropdown(false); setMobileYearsOpen(false); setMobileMenuOpen(false);
  };

  const subscriptions = filteredCourses.flatMap(course => course.lessons
    .filter(lesson => lesson.hasUploadedVideo)
    .map(lesson => ({ course, lesson })));
  useEffect(() => {
    if (catalog.error) toast(lang === 'ar' ? 'تعذر تحميل الاشتراكات. أعد المحاولة.' : 'Subscriptions could not load. Please retry.', 'danger');
  }, [catalog.error, toast, lang]);

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)", color: "var(--text-main)", display: "flex", flexDirection: "column" }}>
      {/* =========================================================================
          TOP BAR 1: TOP COLORED UTILITY B      {/* =========================================================================
          TOP BAR 1: TOP COLORED UTILITY BAR
         ========================================================================= */}
      <div
        className="landing-top-utility-bar"
        style={{
          background: "#0f392b",
          color: "#ffffff",
          padding: "8px 24px",
          fontSize: "12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "relative",
          zIndex: 40,
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        {/* Left Utility: Contact Info (Hidden on Mobile) */}
        <div className="landing-topbar-contact">
          <a
            href="tel:01554689297"
            style={{
              color: "#dcfce7",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontWeight: 700,
              fontSize: "12px",
            }}
          >
            <Phone size={14} style={{ color: "#34d399" }} />
            <span>01554689297</span>
          </a>

          <a
            href={`mailto:${t.landingTopEmail}`}
            style={{
              color: "rgba(255,255,255,0.85)",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "12px",
            }}
          >
            <Mail size={14} style={{ color: "#34d399" }} />
            <span>{t.landingTopEmail}</span>
          </a>
        </div>

        {/* Center/End Utility: Search Bar, Language, Theme, and Auth Links */}
        <div className="landing-topbar-actions" style={{ display: "flex", alignItems: "center", gap: "10px", marginInlineStart: "auto" }}>

          {/* Theme Toggle Button */}
          <button
            onClick={onToggleTheme}
            style={{
              background: "rgba(255,255,255,0.14)",
              border: "1px solid rgba(255,255,255,0.25)",
              color: "#ffffff",
              borderRadius: "8px",
              padding: "5px 9px",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title={theme === "dark" ? t.toggleThemeLight : t.toggleThemeDark}
          >
            {theme === "dark" ? <Sun size={13} style={{ color: "#f59e0b" }} /> : <Moon size={13} />}
          </button>

          {/* Language Button */}
          <button
            onClick={onToggleLang}
            style={{
              background: "rgba(255, 255, 255, 0.18)",
              border: "1px solid rgba(255, 255, 255, 0.3)",
              color: "#ffffff",
              borderRadius: "8px",
              padding: "4px 10px",
              display: "flex",
              alignItems: "center",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 800,
              letterSpacing: "0.05em",
            }}
            title="Switch Language / تغيير اللغة"
          >
            <span>{lang === "ar" ? "AR" : "EN"}</span>
          </button>

          {/* Auth Action Links in Top Bar */}
          <button
            onClick={() => onNavigateToAuth("signin")}
            style={{
              background: "none",
              border: "none",
              color: "#ffffff",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
              padding: "4px 8px",
            }}
          >
            {t.splitSignInTab}
          </button>

          <span style={{ opacity: 0.4 }}>|</span>

          <button
            onClick={() => onNavigateToAuth("register")}
            style={{
              background: "rgba(255, 255, 255, 0.2)",
              border: "1px solid rgba(255, 255, 255, 0.35)",
              color: "#ffffff",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
              padding: "5px 12px",
              borderRadius: "14px",
            }}
          >
            {t.splitRegisterTab}
          </button>
        </div>
      </div>

      {/* =========================================================================
          MAIN FLOATING NAVIGATION BAR (Pill Bar)
         ========================================================================= */}
      <div className="landing-navbar-wrapper" style={{ position: "relative", zIndex: 30, padding: "0 16px" }}>
        <div
          className="landing-navbar-pill"
          style={{
            maxWidth: "1180px",
            margin: "0 auto",
            marginTop: "12px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "40px",
            boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.12), 0 4px 12px rgba(0, 0, 0, 0.05)",
            padding: "8px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
          }}
        >
          {/* Logo on Right */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
            <div
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "50%",
                background: "#0f392b",
                color: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 4px 10px rgba(15, 57, 43, 0.25)",
                flexShrink: 0,
              }}
            >
              <GraduationCap size={20} fill="white" />
            </div>
            <div style={{ minWidth: 0 }}>
              <strong className="landing-brand-title" style={{ fontSize: "14px", display: "block", color: "var(--text-main)", lineHeight: "1.1" }}>
                {t.brandTitle}
              </strong>
              <span className="landing-brand-sub" style={{ fontSize: "10px", color: "var(--text-muted)" }}>{t.brandSubtitle}</span>
            </div>
          </div>

          {/* Navigation Links with "السنوات الدراسية" & "المكتبة" (Hidden on mobile to prevent overflow) */}
          <nav className="landing-desktop-nav">
            {/* Academic Years Dropdown Pill Button */}
            <div
              style={{ position: "relative" }}
            >
              <button
                type="button"
                onClick={() => setShowYearsDropdown(open => !open)}
                aria-expanded={showYearsDropdown}
                aria-controls="catalog-grade-menu"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  background: showYearsDropdown ? "var(--bg-accent-warm, #fffbeb)" : "var(--bg-accent)",
                  border: showYearsDropdown ? "1px solid #059669" : "1px solid var(--border-accent)",
                  color: "var(--text-main)",
                  padding: "7px 14px",
                  borderRadius: "20px",
                  fontSize: "12px",
                  fontWeight: 800,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <Grid size={14} style={{ color: "#059669" }} />
                <span>{t.landingNavYears}</span>
                <ChevronDown
                  size={13}
                  style={{
                    transform: showYearsDropdown ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                    color: "#059669",
                  }}
                />
              </button>

              {/* Interactive Years Dropdown Menu */}
              <div
                id="catalog-grade-menu"
                aria-hidden={!showYearsDropdown}
                style={{
                  position: "absolute",
                  top: "38px",
                  [lang === "ar" ? "right" : "left"]: 0,
                  width: "230px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "16px",
                  boxShadow: "0 14px 32px rgba(0,0,0,0.14), 0 4px 10px rgba(0,0,0,0.06)",
                  padding: "8px",
                  zIndex: 60,
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  opacity: showYearsDropdown ? 1 : 0,
                  transform: showYearsDropdown ? "translateY(0) scale(1)" : "translateY(-10px) scale(0.96)",
                  pointerEvents: showYearsDropdown ? "auto" : "none",
                  visibility: showYearsDropdown ? "visible" : "hidden",
                  transition: "opacity 0.24s cubic-bezier(0.4, 0, 0.2, 1), transform 0.24s cubic-bezier(0.4, 0, 0.2, 1)",
                  transformOrigin: lang === "ar" ? "top right" : "top left",
                }}
              >
                {[
                  { id: "1st_secondary" as const, label: t.firstSecondary, sub: lang === "ar" ? "مقررات وشروحات الكيمياء للصف الأول الثانوي" : "1st Secondary Chemistry Curriculum" },
                  { id: "2nd_secondary" as const, label: t.secondSecondary, sub: lang === "ar" ? "مقررات وشروحات الكيمياء للصف الثاني الثانوي" : "2nd Secondary Chemistry Curriculum" },
                  { id: "3rd_secondary" as const, label: t.thirdSecondary, sub: lang === "ar" ? "مقررات وشروحات الكيمياء للصف الثالث الثانوي" : "3rd Secondary Chemistry Curriculum" },
                ].map((grade) => (
                  <a
                    key={grade.id}
                    href="#courses"
                    onClick={() => changeGrade(grade.id)}
                    style={{
                      padding: "9px 12px",
                      borderRadius: "10px",
                      color: "var(--text-main)",
                      textDecoration: "none",
                      fontSize: "12px",
                      fontWeight: 700,
                      display: "block",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <strong style={{ display: "block", fontSize: "12.5px" }}>{grade.label}</strong>
                    <small style={{ color: "var(--text-muted)", fontSize: "10.5px" }}>{grade.sub}</small>
                  </a>
                ))}
              </div>
            </div>

            {/* Main Links */}
            <a
              href="#courses"
              style={{ padding: "7px 12px", color: "var(--text-main)", textDecoration: "none", borderRadius: "10px" }}
            >
              {t.landingNavHome}
            </a>

            <a
              href="#about"
              style={{ padding: "7px 12px", color: "var(--text-muted)", textDecoration: "none", borderRadius: "10px" }}
            >
              {t.landingNavTeacher}
            </a>

          </nav>

          {/* Left Actions (Mobile Menu Button + CTA Button) */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {/* Mobile Menu Hamburger Button */}
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="landing-mobile-menu-btn"
              style={{
                background: "var(--bg-accent)",
                border: "1px solid var(--border-accent)",
                borderRadius: "10px",
                padding: "7px 9px",
                color: "#059669",
                cursor: "pointer",
                alignItems: "center",
                justifyContent: "center",
              }}
              title="القائمة"
            >
              <Menu size={18} />
            </button>

            {/* Left CTA Button */}
            <button
              className="btn-primary landing-nav-cta-btn"
              onClick={() => onNavigateToAuth("register")}
              style={{
                padding: "8px 16px",
                borderRadius: "30px",
                fontSize: "12px",
                fontWeight: 800,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              <span>{t.landingStartLearningBtn}</span>
            </button>
          </div>
        </div>
      </div>

      {/* =========================================================================
          MOBILE NAVIGATION DRAWER (Sidebar with Navigation + Phone & Email)
         ========================================================================= */}
      {mobileMenuOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0, 0, 0, 0.55)",
            backdropFilter: "blur(4px)",
            display: "flex",
            justifyContent: lang === "ar" ? "flex-start" : "flex-end",
            transition: "opacity 0.25s ease",
          }}
          onClick={() => setMobileMenuOpen(false)}
        >
          <div
            style={{
              width: "min(320px, 85vw)",
              height: "100%",
              background: "var(--bg-surface)",
              color: "var(--text-main)",
              boxShadow: lang === "ar" ? "4px 0 25px rgba(0,0,0,0.25)" : "-4px 0 25px rgba(0,0,0,0.25)",
              display: "flex",
              flexDirection: "column",
              padding: "20px 18px",
              boxSizing: "border-box",
              overflowY: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header with Logo & Close Button */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px", borderBottom: "1px solid var(--border-color)", paddingBottom: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "50%",
                    background: "#0f392b",
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <GraduationCap size={18} fill="white" />
                </div>
                <div>
                  <strong style={{ fontSize: "14px", display: "block", color: "var(--text-main)", lineHeight: "1.1" }}>
                    {t.brandTitle}
                  </strong>
                  <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{t.brandSubtitle}</span>
                </div>
              </div>

              <button
                onClick={() => setMobileMenuOpen(false)}
                className="modal-close-btn"
                style={{
                  background: "var(--modal-close-bg)",
                  border: "none",
                  borderRadius: "8px",
                  padding: "6px",
                  color: "#ffffff",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Navigation Links inside Mobile Sidebar */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "20px" }}>
              {/* Academic Years Accordion */}
              <div>
                <button
                  type="button"
                  onClick={() => setMobileYearsOpen(!mobileYearsOpen)}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "11px 14px",
                    borderRadius: "12px",
                    border: "1px solid var(--border-accent)",
                    background: "var(--bg-accent)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Grid size={16} style={{ color: "#059669" }} />
                    <span>{t.landingNavYears}</span>
                  </div>
                  <ChevronDown
                    size={15}
                    style={{
                      transform: mobileYearsOpen ? "rotate(180deg)" : "rotate(0deg)",
                      transition: "transform 0.2s ease",
                      color: "#059669",
                    }}
                  />
                </button>

                {mobileYearsOpen && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", padding: "6px 8px 6px 12px", marginTop: "4px" }}>
                    {[
                      { id: "1st_secondary" as const, label: t.firstSecondary },
                      { id: "2nd_secondary" as const, label: t.secondSecondary },
                      { id: "3rd_secondary" as const, label: t.thirdSecondary },
                    ].map((grade) => (
                      <a
                        key={grade.id}
                        href="#courses"
                        onClick={() => changeGrade(grade.id)}
                        style={{
                          padding: "8px 12px",
                          borderRadius: "8px",
                          color: "var(--text-main)",
                          textDecoration: "none",
                          fontSize: "12.5px",
                          fontWeight: 700,
                          background: "var(--bg-surface-secondary)",
                          display: "block",
                        }}
                      >
                        {grade.label}
                      </a>
                    ))}
                  </div>
                )}
              </div>

              {/* Home Link */}
              <a
                href="#courses"
                onClick={() => setMobileMenuOpen(false)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "11px 14px",
                  borderRadius: "12px",
                  color: "var(--text-main)",
                  textDecoration: "none",
                  fontSize: "13px",
                  fontWeight: 800,
                  background: "var(--bg-surface-secondary)",
                }}
              >
                <span>{t.landingNavHome}</span>
              </a>

              {/* About Teacher Link */}
              <a
                href="#about"
                onClick={() => setMobileMenuOpen(false)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "11px 14px",
                  borderRadius: "12px",
                  color: "var(--text-main)",
                  textDecoration: "none",
                  fontSize: "13px",
                  fontWeight: 800,
                  background: "var(--bg-surface-secondary)",
                }}
              >
                <span>{t.landingNavTeacher}</span>
              </a>

            </div>

            {/* Contact Information in Sidebar (Phone & Email) */}
            <div style={{ marginTop: "auto", borderTop: "1px solid var(--border-color)", paddingTop: "14px" }}>
              <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", display: "block", marginBottom: "8px" }}>
                بيانات التواصل والدعم الفني:
              </span>

              {/* Phone */}
              <a
                href="tel:01554689297"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "9px 12px",
                  borderRadius: "10px",
                  background: "var(--bg-accent)",
                  border: "1px solid var(--border-accent)",
                  color: "#0f392b",
                  textDecoration: "none",
                  fontSize: "12px",
                  fontWeight: 800,
                  marginBottom: "6px",
                }}
              >
                <Phone size={15} style={{ color: "#059669" }} />
                <span dir="ltr">01554689297</span>
              </a>

              {/* Email */}
              <a
                href={`mailto:${t.landingTopEmail}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "9px 12px",
                  borderRadius: "10px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-main)",
                  textDecoration: "none",
                  fontSize: "11px",
                  fontWeight: 700,
                  marginBottom: "14px",
                  wordBreak: "break-all",
                }}
              >
                <Mail size={15} style={{ color: "#059669", flexShrink: 0 }} />
                <span>{t.landingTopEmail}</span>
              </a>

              {/* Auth Buttons */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onNavigateToAuth("signin");
                  }}
                  className="btn-secondary"
                  style={{ fontSize: "12px", justifyContent: "center", padding: "8px 4px" }}
                >
                  {t.splitSignInTab}
                </button>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onNavigateToAuth("register");
                  }}
                  className="btn-primary"
                  style={{ fontSize: "12px", justifyContent: "center", padding: "8px 4px" }}
                >
                  {t.splitRegisterTab}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          HERO & PRIMARY COURSES SECTION (Make Courses the Main Home Page Focus)
         ========================================================================= */}
      <section
        id="hero"
        style={{
          padding: "40px 24px 30px",
          textAlign: "center",
          background: "var(--bg-primary)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "12px",
            fontWeight: 800,
            color: "var(--text-main)",
            background: "var(--bg-accent)",
            padding: "6px 14px",
            borderRadius: "30px",
            marginBottom: "14px",
            border: "1px solid var(--border-accent)",
          }}
        >
          <Sparkles size={16} />
          {t.landingHeroBadge}
        </span>

        <h1
          style={{
            fontSize: "clamp(22px, 5.5vw, 36px)",
            fontWeight: 900,
            color: "var(--text-main)",
            maxWidth: "820px",
            lineHeight: "1.4",
            margin: "0 0 12px",
            minHeight: "60px",
          }}
        >
          {t.landingHeroTitle}
        </h1>

        <p
          style={{
            fontSize: "14.5px",
            color: "var(--text-muted)",
            maxWidth: "680px",
            lineHeight: "1.6",
            margin: "0 0 24px",
          }}
        >
          {t.landingHeroSubtitle}
        </p>
      </section>

      {/* =========================================================================
          PRIMARY COURSES CATALOG (The Main Home Hub)
         ========================================================================= */}
      <section
        id="courses"
        style={{
          padding: "20px 24px 60px",
          maxWidth: "1100px",
          margin: "0 auto",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <div className="catalog-grades" aria-label={lang === 'ar' ? 'تصفية الصف الدراسي' : 'Filter by grade'}>
          {[{ id: '' as const, label: lang === 'ar' ? 'كل الصفوف' : 'All grades' }, ...grades].map(grade =>
            <button key={grade.id} type="button" aria-pressed={selectedGrade === grade.id}
              onClick={() => changeGrade(grade.id)}>{grade.label}</button>)}
        </div>
        <h2 className="subscriptions-heading">{lang === 'ar' ? 'الاشتراكات' : 'Subscriptions'}</h2>
        {catalog.loading && <p role="status">{lang === 'ar' ? 'جارٍ تحميل الاشتراكات…' : 'Loading subscriptions…'}</p>}
        {catalog.error && <div className="catalog-error" role="alert">
          <p>{catalog.error === 'rate'
            ? (lang === 'ar' ? 'طلبات كثيرة في وقت قصير. انتظر قليلًا ثم أعد المحاولة.' : 'Too many requests. Wait briefly, then retry.')
            : (lang === 'ar' ? 'تعذر تحميل الاشتراكات. تحقق من اتصالك ثم أعد المحاولة.' : 'Subscriptions could not load. Check your connection, then retry.')}</p>
          <button type="button" className="btn-secondary" onClick={catalog.retry}>
            {lang === 'ar' ? 'إعادة تحميل الاشتراكات' : 'Reload subscriptions'}</button>
        </div>}
        {!catalog.loading && !catalog.error && subscriptions.length === 0 && <p className="catalog-empty">{lang === 'ar'
          ? 'لا توجد اشتراكات منشورة في هذا الصف حاليًا.' : 'No subscriptions are published for this grade yet.'}</p>}
        <div className="subscription-grid">
          {subscriptions.map(({ course, lesson }) => <article className="subscription-card" key={lesson.id}>
            <span className="subscription-grade">{course.academicYearLabel}</span>
            <h3>{lesson.title}</h3>
            {lesson.durationFormatted && <p className="subscription-duration"><Clock size={16} aria-hidden="true" />{lesson.durationFormatted}</p>}
            <div className="subscription-actions">
              <div>
                <strong>{(lesson.price || course.price)
                  ? `${(lesson.price || course.price || 0).toLocaleString(lang === 'ar' ? 'ar-EG' : 'en-US')} ${lang === 'ar' ? 'ج.م' : 'EGP'}`
                  : (lang === 'ar' ? 'مجاني' : 'Free')}</strong>
                {!lesson.price && Boolean(course.price) && <small className="subscription-price-note">
                  {lang === 'ar' ? 'ضمن اشتراك الصف' : 'Included in the course subscription'}</small>}
              </div>
              <button type="button" className="btn-primary" onClick={() => onNavigateToAuth('signin', course)}>
                {lang === 'ar' ? 'اشترك الآن' : 'Subscribe now'}</button>
            </div>
          </article>)}
        </div>
        {!catalog.loading && !catalog.error && courses === undefined && catalog.pages > 1 &&
          <nav className="catalog-grades" aria-label={lang === 'ar' ? 'صفحات الاشتراكات' : 'Subscription pages'} style={{ marginTop: 24 }}>
            <button type="button" disabled={catalog.page <= 1} onClick={() => catalog.setPage(catalog.page - 1)}>
              {lang === 'ar' ? 'الصفحة السابقة' : 'Previous page'}</button>
            <span>{catalog.page} / {catalog.pages}</span>
            <button type="button" disabled={catalog.page >= catalog.pages} onClick={() => catalog.setPage(catalog.page + 1)}>
              {lang === 'ar' ? 'الصفحة التالية' : 'Next page'}</button>
          </nav>}
      </section>

      {/* =========================================================================
          STATISTICS BAR (Real Store Metrics)
         ========================================================================= */}
      <section
        id="stats"
        style={{
          padding: "36px 24px",
          background: "var(--bg-surface)",
          borderTop: "1px solid var(--border-color)",
          borderBottom: "1px solid var(--border-color)",
        }}
      >
        <div style={{ maxWidth: "1100px", margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px", textAlign: "center" }}>
          <div style={{ padding: "16px" }}>
            <Users size={28} style={{ color: "#059669", margin: "0 auto 8px" }} />
            <strong style={{ display: "block", fontSize: "28px", color: "var(--text-main)" }}>148+</strong>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>{t.landingStatStudents}</span>
          </div>

          <div style={{ padding: "16px" }}>
            <Video size={28} style={{ color: "#059669", margin: "0 auto 8px" }} />
            <strong style={{ display: "block", fontSize: "28px", color: "var(--text-main)" }}>24+</strong>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>{t.landingStatLessons}</span>
          </div>

          <div style={{ padding: "16px" }}>
            <Award size={28} style={{ color: "#059669", margin: "0 auto 8px" }} />
            <strong style={{ display: "block", fontSize: "28px", color: "var(--text-main)" }}>3</strong>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>{t.landingStatYears}</span>
          </div>

          <div style={{ padding: "16px" }}>
            <CheckCircle2 size={28} style={{ color: "#059669", margin: "0 auto 8px" }} />
            <strong style={{ display: "block", fontSize: "28px", color: "var(--text-main)" }}>98.4%</strong>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>{t.landingStatSuccess}</span>
          </div>
        </div>
      </section>

      {/* =========================================================================
          ABOUT THE TEACHER SECTION
         ========================================================================= */}
      <section
        id="about"
        style={{
          padding: "50px 20px",
          maxWidth: "1100px",
          margin: "0 auto",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <div className="landing-about-card">
          <div
            className="instructor-badge"
            style={{
              width: "130px",
              height: "130px",
              borderRadius: "20px",
              background: "#0f392b",
              color: "white",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 900,
              fontSize: "32px",
              boxShadow: "0 8px 20px rgba(15, 57, 43, 0.25)",
              flexShrink: 0,
            }}
          >
            <span>CHEM</span>
            <small style={{ fontSize: "12px", opacity: 0.8, marginTop: "4px" }}>{lang === "ar" ? "مستر حسن شعبان" : "Mr. Hassan Shaaban"}</small>
          </div>

          <div>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "4px 10px", borderRadius: "6px" }}>
              {t.landingAboutTeacherBadge}
            </span>
            <h2 style={{ margin: "8px 0 8px", fontSize: "22px", color: "var(--text-main)" }}>
              {t.landingAboutTeacherTitle}
            </h2>
            <p style={{ margin: "0 0 16px", color: "var(--text-muted)", fontSize: "13.5px", lineHeight: "1.6" }}>
              {t.landingAboutTeacherBio}
            </p>

            <div className="experience-list" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {[t.landingTeacherExp1, t.landingTeacherExp2, t.landingTeacherExp3].map((exp, idx) => (
                <div key={idx} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-main)", fontWeight: 600 }}>
                  <ShieldCheck size={16} style={{ color: "#059669", flexShrink: 0 }} />
                  <span>{exp}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          FOOTER
         ========================================================================= */}
      <footer
        id="footer"
        style={{
          marginTop: "auto",
          background: "var(--bg-surface)",
          borderTop: "1px solid var(--border-color)",
          padding: "32px 24px",
          textAlign: "center",
          fontSize: "13px",
          color: "var(--text-muted)",
        }}
      >
        <div style={{ maxWidth: "1100px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <GraduationCap size={18} style={{ color: "#059669" }} />
            <strong style={{ color: "var(--text-main)" }}>{t.brandTitle}</strong>
          </div>
          <span>{t.landingFooterRights}</span>
          <div style={{ display: "flex", gap: "16px", fontWeight: 700 }}>
            <span>{t.firstSecondary}</span>
            <span>{t.secondSecondary}</span>
            <span>{t.thirdSecondary}</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

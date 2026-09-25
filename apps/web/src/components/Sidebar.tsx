import React, { memo } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Bell,
  BookOpen,
  FileQuestion,
  GraduationCap,
  UploadCloud,
  Users,
  WalletCards,
  X,
} from "lucide-react";
import { CurrentUser } from "../types/lms";
import { Language, translations } from "../utils/i18n";

export type NavTab =
  | "MyCourses"
  | "MySubmissions"
  | "LessonManagement"
  | "QuizGen"
  | "Submissions"
  | "Notifications"
  | "Profile"
  | "Payments"
  | "PaymentManagement"
  | "Auth";

interface SidebarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  onHoverTab?: (tab: NavTab) => void;
  menuOpen: boolean;
  onCloseMenu: () => void;
  currentUser: CurrentUser;
  lang: Language;
}

export const Sidebar: React.FC<SidebarProps> = memo(({
  activeTab,
  onSelectTab,
  onHoverTab,
  menuOpen,
  onCloseMenu,
  currentUser,
  lang,
}) => {
  const isStudent = currentUser.role === "student";
  const t = translations[lang];

  const studentNavItems: Array<{ id: NavTab; label: string; sub: string; icon: LucideIcon }> = [
    { id: "MyCourses", label: t.navMyCourses, sub: t.navMyCoursesSub, icon: BookOpen },
    { id: "Payments", label: lang === "ar" ? "الدفع والاشتراكات" : "Payments", sub: lang === "ar" ? "تفعيل الدروس والمحتوى التعليمي" : "Lessons and content access", icon: WalletCards },
    { id: "Notifications", label: lang === "ar" ? "الإشعارات والمواعيد" : "Notifications & Alerts", sub: lang === "ar" ? "جدول إشعارات صفك والدروس" : "Class alerts & deadlines", icon: Bell },
  ];

  const teacherNavItems: Array<{ id: NavTab; label: string; sub: string; icon: LucideIcon }> = [
    { id: "LessonManagement", label: t.navLessonManagement, sub: t.navLessonManagementSub, icon: UploadCloud },
    { id: "QuizGen", label: lang === "ar" ? "صانع وسجل الاختبارات" : "Quizzes & History", sub: lang === "ar" ? "توليد، نشر، وأرشيف الاختبارات" : "Create, publish & quiz history", icon: FileQuestion },
    { id: "Submissions", label: t.navSubmissions, sub: t.navSubmissionsSub, icon: Users },
    { id: "PaymentManagement", label: lang === "ar" ? "المدفوعات والتسعير" : "Payments & Pricing", sub: lang === "ar" ? "مراجعة التحويلات وتحديد الأسعار" : "Review payments and set prices", icon: WalletCards },
    { id: "Notifications", label: lang === "ar" ? "جدول مواعيد الإشعارات" : "Notification Schedules", sub: lang === "ar" ? "مواعيد الإرسال وجدول كل صف" : "Manage broadcast schedules", icon: Bell },
  ];

  const localizedYear =
    isStudent
      ? lang === "ar"
        ? currentUser.academicYearLabel || "الصف الأول الثانوي"
        : currentUser.academicYear === "2nd_secondary"
        ? "2nd Secondary Year"
        : currentUser.academicYear === "3rd_secondary"
        ? "3rd Secondary Year"
        : "1st Secondary Year"
      : currentUser.subject || t.teacherRole;

  return (
    <>
      {/* Mobile Drawer Backdrop */}
      {menuOpen && (
        <div
          className="sidebar-backdrop"
          onClick={onCloseMenu}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar ${menuOpen ? "translate-x-0" : ""}`}>
        {/* Top Header Row with Close Button (X placed in the top corner indicated by arrow) */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            paddingBottom: "14px",
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          {/* Top Bar with X button & role label */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button
              type="button"
              onClick={onCloseMenu}
              className="modal-close-btn"
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "var(--modal-close-bg)",
                border: "none",
                color: "#ffffff",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.15s ease",
              }}
              aria-label="Close Sidebar"
              title="إغلاق القائمة"
            >
              <X size={17} />
            </button>

            <span
              style={{
                fontSize: "11px",
                fontWeight: 800,
                color: "#059669",
                background: "var(--bg-accent)",
                padding: "2px 8px",
                borderRadius: "6px",
                border: "1px solid var(--border-accent)",
              }}
            >
              {isStudent ? t.studentMenu : t.teacherMenu}
            </span>
          </div>

          {/* Brand Logo & Title */}
          <div
            onClick={() => {
              window.dispatchEvent(new CustomEvent("lms:close-overlays"));
              onSelectTab(isStudent ? "MyCourses" : "LessonManagement");
              onCloseMenu();
            }}
            role="button"
            tabIndex={0}
            title={lang === "ar" ? "العودة إلى الصفحة الأولى" : "Go to Home"}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <div className="brand-mark" style={{ width: "38px", height: "38px", borderRadius: "10px" }}>
              <GraduationCap size={20} />
            </div>
            <div>
              <strong style={{ fontSize: "14px", display: "block", color: "var(--text-main)", lineHeight: 1.2 }}>
                {t.brandTitle}
              </strong>
              <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{t.brandSubtitle}</span>
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <nav style={{ overflowY: "auto", flex: 1, marginTop: "12px" }}>
          {(isStudent ? studentNavItems : teacherNavItems).map(({ id, label, sub, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`nav-item ${activeTab === id ? "active" : ""}`}
              onClick={() => {
                window.dispatchEvent(new CustomEvent("lms:close-overlays"));
                onSelectTab(id);
                onCloseMenu();
              }}
              onMouseEnter={() => onHoverTab?.(id)}
              onFocus={() => onHoverTab?.(id)}
              onTouchStart={() => onHoverTab?.(id)}
            >
              <Icon size={18} className="nav-icon" />
              <div style={{ textAlign: "inherit", lineHeight: "1.2" }}>
                <span style={{ display: "block", fontSize: "13px", fontWeight: 700 }}>{label}</span>
                <small style={{ display: "block", fontSize: "10px", opacity: 0.8 }}>{sub}</small>
              </div>
            </button>
          ))}
        </nav>

        {/* Bottom User Card in Sidebar */}
        <div className="sidebar-bottom">
          <button
            type="button"
            className={`profile-button ${activeTab === "Profile" ? "active-profile" : ""}`}
            onClick={() => {
              onSelectTab("Profile");
              onCloseMenu();
            }}
            onMouseEnter={() => onHoverTab?.("Profile")}
            onFocus={() => onHoverTab?.("Profile")}
            onTouchStart={() => onHoverTab?.("Profile")}
          >
            <div
              className="avatar-badge"
              style={{ background: isStudent ? "#2563eb" : "#0f392b" }}
            >
              {currentUser.name.slice(0, 2)}
            </div>
            <div style={{ overflow: "hidden", flex: 1, lineHeight: "1.2" }}>
              <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main)", whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>
                {currentUser.name}
              </strong>
              <small style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>
                {localizedYear}
              </small>
            </div>
          </button>
        </div>
      </aside>
    </>
  );
});

Sidebar.displayName = "Sidebar";

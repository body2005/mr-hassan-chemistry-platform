import React, { useState } from "react";
import {
  ArrowRight,
  Bell,
  Clock,
  ExternalLink,
  FileText,
  GraduationCap,
  Menu,
  Moon,
  Search,
  Sun,
  X,
} from "lucide-react";
import { NotificationItem } from "../types/lms";
import { Language, translations } from "../utils/i18n";

interface HeaderProps {
  onToggleMenu: () => void;
  menuOpen: boolean;
  notifications: NotificationItem[];
  onMarkNotificationRead: (id: string) => void;
  onSelectNotification?: (notif: NotificationItem) => void;
  onNavigateToNotifications?: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  lang: Language;
  onToggleLang: () => void;
  onNavigateHome?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleMenu,
  menuOpen,
  notifications,
  onMarkNotificationRead,
  onSelectNotification,
  onNavigateToNotifications,
  theme,
  onToggleTheme,
  lang,
  onToggleLang,
  onNavigateHome,
}) => {
  const [showNotifDropdown, setShowNotifDropdown] = useState(false);
  const unreadCount = notifications.filter((n) => !n.read).length;
  const t = translations[lang];

  function handleNotificationClick(notif: NotificationItem) {
    onMarkNotificationRead(notif.id);
    setShowNotifDropdown(false);
    if (onSelectNotification) {
      onSelectNotification(notif);
    } else if (onNavigateToNotifications) {
      onNavigateToNotifications();
    }
  }

  return (
    <header className="topbar">
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        {/* Unified Mobile Hamburger / Close button */}
        <button
          className="icon-btn"
          onClick={onToggleMenu}
          aria-label={menuOpen ? "Close Menu" : "Open Menu"}
          title={lang === "ar" ? "القائمة الجانبية" : "Sidebar Menu"}
        >
          {menuOpen ? <X size={18} /> : <Menu size={18} />}
        </button>

        {/* Brand Logo & Name directly next to the sidebar button */}
        <div
          onClick={onNavigateHome}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              onNavigateHome?.();
            }
          }}
          title={lang === "ar" ? "العودة إلى الصفحة الأولى" : "Go to Home"}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginInlineEnd: "8px",
            cursor: onNavigateHome ? "pointer" : "default",
            userSelect: "none",
          }}
        >
          <div
            className="brand-mark"
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "#0f392b",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 6px rgba(15, 57, 43, 0.25)",
              flexShrink: 0,
            }}
          >
            <GraduationCap size={20} />
          </div>
          <div className="topbar-brand-text" style={{ display: "flex", flexDirection: "column", lineHeight: 1.2, minWidth: 0 }}>
            <strong className="topbar-brand-title" style={{ fontSize: "14px", fontWeight: 800, color: "var(--text-main)" }}>
              {t.brandTitle || (lang === "ar" ? "منصة الكيمياء — مستر حسن شعبان" : "Chemistry Platform — Mr. Hassan Shaaban")}
            </strong>
            <span className="topbar-brand-subtitle" style={{ fontSize: "10.5px", color: "var(--text-muted)", fontWeight: 600 }}>
              {t.brandSubtitle || (lang === "ar" ? "المنصة المتخصصة في تدريس الكيمياء" : "Secondary Chemistry Learning Portal")}
            </span>
          </div>
        </div>

        {/* Search Bar with Attached Secondary Quick-Search Icon */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <label className="search-box">
            <Search size={16} />
            <input placeholder={t.searchPlaceholder} aria-label="Search" />
          </label>
          <button
            type="button"
            className="icon-btn topbar-quick-search-btn"
            title={lang === "ar" ? "تصفية وبحث متقدم في المحتوى" : "Quick Search & Filter"}
            aria-label="Filter Search"
            style={{ width: "36px", height: "36px", borderRadius: "10px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)" }}
          >
            <Search size={15} style={{ color: "#059669" }} />
          </button>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", position: "relative" }}>
        {/* Dark Mode / Light Mode Toggle */}
        <button
          className="icon-btn"
          onClick={onToggleTheme}
          title={theme === "dark" ? t.toggleThemeLight : t.toggleThemeDark}
          aria-label="Toggle Theme"
        >
          {theme === "dark" ? <Sun size={18} style={{ color: "#f59e0b" }} /> : <Moon size={18} />}
        </button>

        {/* Simplified AR / EN Language Toggle Button */}
        <button
          className="icon-btn"
          onClick={onToggleLang}
          title="Switch Language / تغيير اللغة"
          style={{
            width: "auto",
            minWidth: "48px",
            padding: "0 10px",
            gap: "4px",
            fontSize: "12px",
            fontWeight: 800,
            letterSpacing: "0.05em",
          }}
        >
          <span>{lang === "ar" ? "AR" : "EN"}</span>
        </button>

        {/* Notifications Dropdown */}
        <div style={{ position: "relative" }}>
          <button
            className="icon-btn"
            onClick={() => setShowNotifDropdown(!showNotifDropdown)}
            aria-label="Notifications"
            title={t.notificationsTitle}
          >
            <Bell size={18} />
            {unreadCount > 0 && <span className="notif-badge" />}
          </button>

          {showNotifDropdown && (
            <div className="notif-dropdown" style={{ width: "360px" }}>
              <div
                style={{
                  padding: "12px 16px",
                  background: "var(--bg-surface-secondary)",
                  borderBottom: "1px solid var(--border-color)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <strong style={{ fontSize: "13px", color: "var(--text-main)" }}>
                  {t.notificationsTitle} ({notifications.length})
                </strong>
                {unreadCount > 0 && (
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 800,
                      color: "#dc2626",
                      background: "#fee2e2",
                      padding: "2px 8px",
                      borderRadius: "10px",
                    }}
                  >
                    {unreadCount} {t.newBadge}
                  </span>
                )}
              </div>

              <div style={{ maxHeight: "320px", overflowY: "auto" }}>
                {notifications.length === 0 ? (
                  <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "12px" }}>
                    لا توجد إشعارات حالياً
                  </div>
                ) : (
                  notifications.map((n, idx) => (
                    <div
                      key={`${n.id}-${idx}`}
                      onClick={() => handleNotificationClick(n)}
                      style={{
                        padding: "12px 16px",
                        borderBottom: "1px solid var(--border-color)",
                        background: n.read ? "transparent" : "var(--bg-accent)",
                        cursor: "pointer",
                        display: "flex",
                        gap: "10px",
                        alignItems: "flex-start",
                        transition: "background 0.15s ease",
                      }}
                    >
                      <div style={{ marginTop: "2px", color: n.type === "assignment" ? "#d97706" : "#059669" }}>
                        {n.type === "assignment" ? <Clock size={16} /> : <FileText size={16} />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <strong style={{ display: "block", fontSize: "12px", color: "var(--text-main)", marginBottom: "2px" }}>
                            {n.title}
                          </strong>
                          <ExternalLink size={12} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                        </div>
                        <p style={{ margin: 0, fontSize: "11px", color: "var(--text-muted)", lineHeight: "1.4" }}>
                          {n.message}
                        </p>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                          {n.dueDate && (
                            <span style={{ fontSize: "10px", fontWeight: 700, color: "#b45309" }}>
                              {n.dueDate}
                            </span>
                          )}
                          <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                            {n.createdAt}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* View Full Notifications & Timetable Page */}
              <div style={{ padding: "8px 12px", background: "var(--bg-surface-secondary)", borderTop: "1px solid var(--border-color)", textAlign: "center" }}>
                <button
                  onClick={() => {
                    setShowNotifDropdown(false);
                    if (onNavigateToNotifications) onNavigateToNotifications();
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#059669",
                    fontWeight: 800,
                    fontSize: "12px",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <span>عرض جميع الإشعارات والجدول الزمني</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

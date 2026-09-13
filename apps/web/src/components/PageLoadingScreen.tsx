import React, { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";

interface PageLoadingScreenProps {
  message?: string;
  brandTitle?: string;
}

export const PageLoadingScreen: React.FC<PageLoadingScreenProps> = ({
  message = "جاري تحميل الصفحة...",
  brandTitle = "منصة الكيمياء التعليمية — مستر حسن شعبان",
}) => {
  const [isDark, setIsDark] = useState(() => {
    if (typeof document !== "undefined") {
      return document.documentElement.getAttribute("data-theme") === "dark";
    }
    return false;
  });

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.getAttribute("data-theme") === "dark");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const bgColor = isDark ? "#111827" : "#ffffff";
  const titleColor = isDark ? "#ffffff" : "#0f172a";
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const spinnerTrack = isDark ? "#334155" : "#e2e8f0";
  const spinnerAccent = isDark ? "#10b981" : "#0f392b";
  const logoBoxBg = isDark ? "#064e3b" : "#0f392b";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100dvh",
        backgroundColor: bgColor,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 99999,
        direction: "rtl",
        fontFamily: "'Cairo', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          gap: "16px",
          padding: "24px",
        }}
      >
        {/* Top: Logo with Top Name Only */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "14px",
            flexWrap: "wrap",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              backgroundColor: logoBoxBg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              boxShadow: isDark
                ? "0 4px 14px rgba(0, 0, 0, 0.4)"
                : "0 4px 12px rgba(15, 57, 43, 0.2)",
              border: isDark ? "1px solid rgba(16, 185, 129, 0.3)" : "none",
              flexShrink: 0,
            }}
          >
            <GraduationCap size={26} strokeWidth={2.2} />
          </div>

          <h2
            style={{
              fontSize: "1.25rem",
              fontWeight: 800,
              color: titleColor,
              margin: 0,
              lineHeight: 1.3,
            }}
          >
            {brandTitle}
          </h2>
        </div>

        {/* Middle: Loading Text */}
        <div
          style={{
            fontSize: "16px",
            fontWeight: 600,
            color: textColor,
            margin: "6px 0 4px",
          }}
        >
          {message}
        </div>

        {/* Bottom: Circular Spinning Loader */}
        <div
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "50%",
            border: `3.5px solid ${spinnerTrack}`,
            borderTopColor: spinnerAccent,
            borderRightColor: "#059669",
            animation: "pageSpinAnimation 0.85s linear infinite",
          }}
          aria-label="جاري التحميل"
        />
      </div>

      <style>{`
        @keyframes pageSpinAnimation {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

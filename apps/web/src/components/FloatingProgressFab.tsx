import React, { useState, useEffect, useRef } from "react";
import { Video, FileCheck, CheckCircle2 } from "lucide-react";
import { Course, CurrentUser } from "../types/lms";
import { courseService } from "../services/lmsService";

export interface FloatingProgressFabProps {
  courses: Course[];
  currentUser: CurrentUser | null;
  theme: "light" | "dark";
}

export const FloatingProgressFab: React.FC<FloatingProgressFabProps> = ({
  courses,
  currentUser,
  theme,
}) => {
  // Only students see course progress FAB
  if (!currentUser || currentUser.role !== "student") {
    return null;
  }

  const [isOpen, setIsOpen] = useState(false);
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null);
  const [completedLessonIds, setCompletedLessonIds] = useState<string[]>([]);
  const [hiddenForVideo, setHiddenForVideo] = useState(false);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const dragInfoRef = useRef<{
    startX: number;
    startY: number;
    initialLeft: number;
    initialTop: number;
    hasMoved: boolean;
  } | null>(null);

  // Check if video is fullscreen or enlarged (e.g. theater mode in VideoLessonPage)
  useEffect(() => {
    const checkVideoEnlarged = () => {
      const isFs = Boolean(
        document.fullscreenElement ||
        (document as unknown as { webkitFullscreenElement?: Element }).webkitFullscreenElement ||
        (document as unknown as { mozFullScreenElement?: Element }).mozFullScreenElement ||
        document.body.getAttribute("data-video-enlarged") === "true"
      );
      setHiddenForVideo(isFs);
    };

    checkVideoEnlarged();
    document.addEventListener("fullscreenchange", checkVideoEnlarged);
    document.addEventListener("webkitfullscreenchange", checkVideoEnlarged);

    const observer = new MutationObserver(checkVideoEnlarged);
    observer.observe(document.body, { attributes: true, attributeFilter: ["data-video-enlarged"] });

    return () => {
      document.removeEventListener("fullscreenchange", checkVideoEnlarged);
      document.removeEventListener("webkitfullscreenchange", checkVideoEnlarged);
      observer.disconnect();
    };
  }, []);

  // Determine current student course
  const currentCourse =
    courses.find((c) => c.academicYear === currentUser?.academicYear) ||
    courses[0] ||
    null;

  // Load lesson progress
  useEffect(() => {
    if (!currentUser?.id) return;
    let disposed = false;

    const loadProgress = () => {
      courseService
        .getLessonProgress()
        .then((items) => {
          if (!disposed) {
            setCompletedLessonIds(
              items.filter((item) => item.completion_percent >= 100).map((item) => item.lesson_id)
            );
          }
        })
        .catch(() => undefined);
    };

    loadProgress();
    window.addEventListener("focus", loadProgress);

    return () => {
      disposed = true;
      window.removeEventListener("focus", loadProgress);
    };
  }, [currentUser?.id, currentCourse?.id]);

  // Close popup when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    window.addEventListener("pointerdown", handleClickOutside);
    return () => {
      window.removeEventListener("pointerdown", handleClickOutside);
    };
  }, [isOpen]);

  // Compute stats
  const courseLessons = currentCourse?.lessons || [];
  const completedLessonsCount = courseLessons.filter((l) => completedLessonIds.includes(l.id)).length;
  const serverAssessments = currentCourse?.assessments || [];
  const serverQuizzes = serverAssessments.filter((a) => a.kind === "quiz");
  const serverAssignments = serverAssessments.filter((a) => a.kind === "assignment");

  const lessonStats = { done: completedLessonsCount, total: courseLessons.length };
  const assignmentStats = {
    done: serverAssignments.filter((a) => (a.attemptsUsed ?? 0) > 0).length,
    total: serverAssignments.length,
  };
  const quizStats = {
    done: serverQuizzes.filter((qz) => (qz.attemptsUsed ?? 0) > 0).length,
    total: serverQuizzes.length,
  };
  const overallDone = lessonStats.done + assignmentStats.done + quizStats.done;
  const overallTotal = lessonStats.total + assignmentStats.total + quizStats.total;
  const overallPercent = overallTotal > 0 ? Math.round((overallDone / overallTotal) * 100) : 0;

  // Dragging logic
  const handlePointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    // Only primary button
    if (e.button !== 0) return;

    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;

    dragInfoRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialLeft: rect.left,
      initialTop: rect.top,
      hasMoved: false,
    };

    const handlePointerMove = (moveEvt: PointerEvent) => {
      if (!dragInfoRef.current) return;
      const dx = moveEvt.clientX - dragInfoRef.current.startX;
      const dy = moveEvt.clientY - dragInfoRef.current.startY;

      if (!dragInfoRef.current.hasMoved && Math.hypot(dx, dy) > 4) {
        dragInfoRef.current.hasMoved = true;
      }

      if (dragInfoRef.current.hasMoved) {
        const fabSize = 64;
        const clampedX = Math.max(12, Math.min(window.innerWidth - fabSize - 12, dragInfoRef.current.initialLeft + dx));
        const clampedY = Math.max(12, Math.min(window.innerHeight - fabSize - 12, dragInfoRef.current.initialTop + dy));
        setCoords({ x: clampedX, y: clampedY });
      }
    };

    const handlePointerUp = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);

      if (dragInfoRef.current && !dragInfoRef.current.hasMoved) {
        setIsOpen((prev) => !prev);
      }
      dragInfoRef.current = null;
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  };

  // If video is fullscreen / theater mode, hide FAB completely
  if (hiddenForVideo) {
    return null;
  }

  // Dark mode detection
  const isDark =
    theme === "dark" ||
    (typeof document !== "undefined" &&
      document.documentElement.getAttribute("data-theme") === "dark");

  // Determine popup placement based on coordinates
  const openDownward = coords !== null && coords.y < 230;
  const alignRight = coords !== null && coords.x > (typeof window !== "undefined" ? window.innerWidth - 270 : 600);

  // Position style: default bottom-left
  const positionStyle: React.CSSProperties = coords
    ? {
        position: "fixed",
        left: `${coords.x}px`,
        top: `${coords.y}px`,
        zIndex: 9999,
      }
    : {
        position: "fixed",
        left: "24px",
        bottom: "24px",
        zIndex: 9999,
      };

  return (
    <div
      ref={containerRef}
      className="floating-progress-fab"
      style={{
        ...positionStyle,
        userSelect: "none",
        touchAction: "none",
      }}
    >
      {/* Circular Progress Button */}
      <button
        type="button"
        onPointerDown={handlePointerDown}
        aria-label="نسبة إنجاز المقرر"
        title="نسبة إنجاز المقرر — اضغط للتفاصيل أو اسحب للتحريك"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          border: isDark ? "2.5px solid #34d399" : "2px solid #059669",
          background: isDark
            ? "linear-gradient(135deg, #059669, #047857)"
            : "rgba(255, 255, 255, 0.98)",
          color: isDark ? "#ffffff" : "#065f46",
          cursor: "grab",
          boxShadow: isDark
            ? "0 6px 20px rgba(5, 150, 105, 0.55), 0 0 14px rgba(16, 185, 129, 0.35)"
            : "0 6px 20px rgba(0, 0, 0, 0.18)",
          transition: "transform 0.15s ease, box-shadow 0.15s ease",
          position: "relative",
          outline: "none",
        }}
      >
        <svg
          width="64"
          height="64"
          viewBox="0 0 64 64"
          style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)", pointerEvents: "none" }}
        >
          <circle
            cx="32"
            cy="32"
            r="27"
            fill="none"
            stroke={isDark ? "rgba(255, 255, 255, 0.25)" : "rgba(5, 150, 105, 0.15)"}
            strokeWidth="5"
          />
          <circle
            cx="32"
            cy="32"
            r="27"
            fill="none"
            stroke={isDark ? "#34d399" : "#059669"}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={2 * Math.PI * 27}
            strokeDashoffset={2 * Math.PI * 27 * (1 - overallPercent / 100)}
            style={{ transition: "stroke-dashoffset 0.4s ease" }}
          />
        </svg>
        <strong style={{ fontSize: "14.5px", fontWeight: 900, pointerEvents: "none" }}>
          {overallPercent}%
        </strong>
      </button>

      {/* Expanded Progress Breakdown Card */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            ...(openDownward ? { top: "72px" } : { bottom: "72px" }),
            ...(alignRight ? { right: 0 } : { left: 0 }),
            background: isDark ? "#064e3b" : "var(--bg-surface, #ffffff)",
            border: isDark ? "1.5px solid #10b981" : "1px solid var(--border-color, #e2e8f0)",
            borderRadius: "16px",
            boxShadow: isDark
              ? "0 16px 36px rgba(0,0,0,0.55), 0 0 16px rgba(5, 150, 105, 0.25)"
              : "0 14px 35px rgba(0,0,0,0.18)",
            padding: "16px 18px",
            minWidth: "245px",
            zIndex: 10000,
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            animation: "fadeIn 0.15s ease-out",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div
            style={{
              fontSize: "13px",
              fontWeight: 800,
              color: isDark ? "#ffffff" : "var(--text-main, #0f172a)",
              borderBottom: isDark ? "1px solid rgba(52, 211, 153, 0.25)" : "1px solid var(--border-color, #e2e8f0)",
              paddingBottom: "8px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>نسبة الإنجاز التفصيلية</span>
            <span style={{ fontSize: "11px", color: isDark ? "#a7f3d0" : "#059669", fontWeight: 700 }}>
              {currentCourse?.title || "المقرر"}
            </span>
          </div>

          {([
            { label: "الدروس", icon: <Video size={14} />, done: lessonStats.done, total: lessonStats.total, color: isDark ? "#38bdf8" : "#0f766e" },
            { label: "الواجبات", icon: <FileCheck size={14} />, done: assignmentStats.done, total: assignmentStats.total, color: isDark ? "#fbbf24" : "#d97706" },
            { label: "الكويزات", icon: <CheckCircle2 size={14} />, done: quizStats.done, total: quizStats.total, color: isDark ? "#34d399" : "#059669" },
          ] as const).map((row) => {
            const pct = row.total > 0 ? Math.round((row.done / row.total) * 100) : 0;
            return (
              <div key={row.label} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ color: row.color, display: "inline-flex" }}>{row.icon}</span>
                <span style={{ fontSize: "12px", fontWeight: 700, color: isDark ? "#ffffff" : "var(--text-main, #0f172a)", flex: 1 }}>
                  {row.label}
                </span>
                <div
                  style={{
                    flex: 1.4,
                    height: "6px",
                    borderRadius: "3px",
                    background: isDark ? "rgba(255, 255, 255, 0.15)" : "var(--progress-track-bg, #e2e8f0)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${pct}%`,
                      background: row.color,
                      borderRadius: "3px",
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 800,
                    color: isDark ? "#cbd5e1" : "var(--text-muted, #64748b)",
                    minWidth: "52px",
                    textAlign: "center",
                  }}
                >
                  ({pct}%) {row.done}/{row.total}
                </span>
              </div>
            );
          })}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              borderTop: isDark ? "1px solid rgba(52, 211, 153, 0.25)" : "1px solid var(--border-color, #e2e8f0)",
              paddingTop: "8px",
            }}
          >
            <span style={{ fontSize: "12px", fontWeight: 800, color: isDark ? "#a7f3d0" : "#059669", flex: 1 }}>
              نسبة المقرر الإجمالية
            </span>
            <strong style={{ fontSize: "15px", fontWeight: 900, color: isDark ? "#34d399" : "#059669" }}>
              {overallPercent}%
            </strong>
          </div>
        </div>
      )}
    </div>
  );
};

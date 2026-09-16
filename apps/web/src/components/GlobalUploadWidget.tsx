import React, { useState, useEffect } from "react";
import {
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  X,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  FileVideo,
  FileText,
} from "lucide-react";
import { uploadManager, UploadTask } from "../services/uploadManager";

interface CircularProgressProps {
  progress: number;
  size?: number;
  strokeWidth?: number;
  trackColor?: string;
  progressColor?: string;
  isProcessing?: boolean;
}

export const CircularProgress: React.FC<CircularProgressProps> = ({
  progress,
  size = 20,
  strokeWidth = 2.5,
  trackColor = "var(--progress-track-bg, rgb(216, 219, 223))",
  progressColor = "#34d399",
  isProcessing = false,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedProgress = Math.min(Math.max(progress, 0), 100);
  const strokeDashoffset = circumference - (clampedProgress / 100) * circumference;

  return (
    <div
      style={{
        position: "relative",
        width: size,
        height: size,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
      className={isProcessing ? "animate-spin" : ""}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{
          transform: "rotate(-90deg)",
          transformOrigin: "center",
          overflow: "visible",
        }}
      >
        {/* Background Track Circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />
        {/* Active Progress Arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={progressColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={
            isProcessing && clampedProgress >= 100
              ? circumference * 0.25
              : strokeDashoffset
          }
          style={{
            transition: isProcessing ? "none" : "stroke-dashoffset 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </svg>
    </div>
  );
};

interface GlobalUploadWidgetProps {
  currentUser?: { role?: string } | null;
  menuOpen?: boolean;
}

export const GlobalUploadWidget: React.FC<GlobalUploadWidgetProps> = ({ currentUser, menuOpen = false }) => {
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);

  // Strictly enforce role: Upload widget is exclusively for teachers
  const role = currentUser?.role;

  useEffect(() => {
    const unsubscribe = uploadManager.subscribe((newTasks) => {
      setTasks(newTasks);
    });
    return () => unsubscribe();
  }, []);

  const activeTasks = tasks.filter(
    (t) => t.status === "uploading" || t.status === "queued" || t.status === "processing"
  );
  const completedTasks = tasks.filter((t) => t.status === "completed");

  const primaryActive = activeTasks[0];

  const [windowWidth, setWindowWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1200
  );

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  if (role !== "teacher") {
    return null;
  }

  const isMobile = windowWidth < 640;
  // Sidebar width is defined as --sidebar-width: 280px in index.css.
  // With the RTL sidebar open, a larger right offset visibly moves the widget left.
  // On mobile (<640px), the sidebar is a full overlay; keep widget visible at bottom-left so it
  // doesn't overlap the drawer and remains accessible.
  const SIDEBAR_WIDTH = 280; // matches --sidebar-width in .sidebar CSS
  const GAP = 24;
  const rightOffset = menuOpen && !isMobile
    ? `${SIDEBAR_WIDTH + GAP}px`
    : isMobile
      ? "16px"
      : "24px";
  const bottomOffset = isMobile ? "16px" : "24px";

  // On mobile with sidebar open, move widget to bottom-left instead of hiding it.
  const mobileOverride = menuOpen && isMobile;

  return (
    <div
      style={{
        position: "fixed",
        bottom: bottomOffset,
        right: mobileOverride ? "auto" : rightOffset,
        left: mobileOverride ? "16px" : "auto",
        zIndex: isExpanded ? 9999 : 95,
        fontFamily: "inherit",
        transition: "right 250ms ease, left 250ms ease, bottom 250ms ease",
      }}
      dir="rtl"
    >
      {/* Collapsed Pill View */}
      {!isExpanded ? (
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px 16px",
            borderRadius: "30px",
            background: activeTasks.length > 0 ? "#0f392b" : "#0f172a",
            color: "#ffffff",
            border: "1.5px solid rgba(255,255,255,0.2)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
            cursor: "pointer",
            fontSize: "12.5px",
            fontWeight: 700,
            transition: "all 0.2s ease",
          }}
        >
          {activeTasks.length > 0 ? (
            <CircularProgress
              progress={primaryActive?.progress ?? 0}
              size={20}
              strokeWidth={2.5}
              progressColor="#34d399"
              trackColor="rgba(255, 255, 255, 0.25)"
              isProcessing={primaryActive?.status === "processing"}
            />
          ) : (
            <CheckCircle2 size={18} style={{ color: "#34d399" }} />
          )}

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "2px" }}>
            <span>
              {activeTasks.length > 0
                ? primaryActive?.status === "processing"
                  ? `جاري المعالجة (${primaryActive?.progress ?? 100}%)`
                  : `جاري الرفع (${primaryActive?.progress ?? 0}%)`
                : "الرفع"}
            </span>
            {activeTasks.length > 1 && (
              <span style={{ fontSize: "10px", opacity: 0.85, fontWeight: 500 }}>
                +{activeTasks.length - 1} ملفات أخرى بالانتظار
              </span>
            )}
          </div>

          <ChevronUp size={16} style={{ marginInlineStart: "4px", opacity: 0.8 }} />
        </button>
      ) : (
        /* Expanded Floating Card */
        <div
          style={{
            width: "380px",
            maxWidth: "calc(100vw - 32px)",
            borderRadius: "16px",
            background: "var(--bg-surface, #ffffff)",
            border: "1px solid var(--border-color, #e2e8f0)",
            boxShadow: "0 12px 36px rgba(0,0,0,0.22)",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "12px 16px",
              background: "#0f392b",
              color: "#ffffff",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {activeTasks.length > 0 ? (
                <CircularProgress
                  progress={primaryActive?.progress ?? 0}
                  size={20}
                  strokeWidth={2.5}
                  progressColor="#34d399"
                  trackColor="rgba(255, 255, 255, 0.25)"
                  isProcessing={primaryActive?.status === "processing"}
                />
              ) : (
                <UploadCloud size={18} style={{ color: "#34d399" }} />
              )}
              <div>
                <strong style={{ fontSize: "13px", display: "block" }}>
                  الرفع
                </strong>
                <span style={{ fontSize: "10.5px", opacity: 0.85 }}>
                  {activeTasks.length > 0
                    ? `${activeTasks.length} قيد المعالجة (${primaryActive?.progress ?? 0}%)`
                    : "جميع العمليات مكتملة"}
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              style={{
                background: "rgba(255,255,255,0.15)",
                border: "none",
                color: "#ffffff",
                borderRadius: "8px",
                padding: "5px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              title="تصغير"
            >
              <ChevronDown size={16} />
            </button>
          </div>

          {/* Tasks List */}
          <div
            style={{
              maxHeight: "260px",
              overflowY: "auto",
              padding: "12px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            {tasks.length === 0 ? (
              <div style={{ textAlign: "center", padding: "26px 14px", color: "var(--text-muted)" }}>
                <UploadCloud size={34} style={{ color: "#059669", opacity: 0.7, margin: "0 auto 8px" }} />
                <div style={{ fontSize: "13px", fontWeight: 800, color: "var(--text-main)" }}>
                  لا توجد عمليات رفع نشطة حالياً
                </div>
                <div style={{ fontSize: "11px", marginTop: "4px", lineHeight: 1.5 }}>
                  عند رفع أي درس، فيديو أو مذكرة، ستظهر حالة ونسبة الرفع والمعالجة هنا لحظياً.
                </div>
              </div>
            ) : (
              tasks.map((task) => {
              const isVideo = task.type === "lesson_video";
              const isUploading = task.status === "uploading";
              const isProcessing = task.status === "processing";
              const isCompleted = task.status === "completed";
              const isError = task.status === "error";

              return (
                <div
                  key={task.id}
                  style={{
                    padding: "10px",
                    borderRadius: "10px",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    background: "var(--bg-surface-secondary, #f8fafc)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
                      <div
                        style={{
                          width: "28px",
                          height: "28px",
                          borderRadius: "8px",
                          background: isVideo ? "#e0f2fe" : "#ecfdf5",
                          color: isVideo ? "#0284c7" : "#059669",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        {isVideo ? <FileVideo size={16} /> : <FileText size={16} />}
                      </div>

                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: "12px",
                            fontWeight: 700,
                            color: "var(--text-main, #0f172a)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={task.title}
                        >
                          {task.title.startsWith("فهرسة:")
                            ? task.title
                            : task.type === "knowledge_source"
                            ? `فهرسة: ${task.fileName || task.title}`
                            : task.title}
                        </div>
                        <div style={{ fontSize: "10px", color: "var(--text-muted, #64748b)" }}>
                          {task.formattedSize}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      {(isUploading || isProcessing) && (
                        <button
                          type="button"
                          onClick={() => uploadManager.cancelUpload(task.id)}
                          style={{
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "none",
                            color: "#ef4444",
                            cursor: "pointer",
                            padding: "4px",
                            borderRadius: "6px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                          title="إيقاف الفهرسة (مع حفظ الملف بالسيرفر)"
                        >
                          <X size={15} />
                        </button>
                      )}
                      {isError && (
                        <button
                          type="button"
                          onClick={() => uploadManager.retryUpload(task.id)}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "#0284c7",
                            cursor: "pointer",
                            padding: "4px",
                          }}
                          title="إعادة المحاولة"
                        >
                          <RefreshCw size={14} />
                        </button>
                      )}
                      {(isCompleted || isError) && (
                        <button
                          type="button"
                          onClick={() => uploadManager.clearTask(task.id)}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "var(--text-muted, #94a3b8)",
                            cursor: "pointer",
                            padding: "4px",
                          }}
                          title="حذف من السجل"
                        >
                          <X size={13} />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {(isUploading || isProcessing) && (
                    <div>
                      <div
                        className="progress-bar-track"
                        style={{
                          height: "6px",
                          borderRadius: "3px",
                          background: "var(--progress-track-bg, rgb(216, 219, 223))",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width: `${task.progress}%`,
                            background: isProcessing ? "#2563eb" : "#059669",
                            borderRadius: "3px",
                            transition: "width 0.2s ease",
                          }}
                        />
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "10px",
                          marginTop: "4px",
                          color: "var(--text-muted, #64748b)",
                        }}
                      >
                        <span>
                          {isProcessing
                            ? "جاري المعالجة بالسيرفر..."
                            : (() => {
                                const totalMB = ((task.fileSizeBytes || 0) / (1024 * 1024)).toFixed(1);
                                const loadedBytes = task.loadedBytes ?? ((task.fileSizeBytes || 0) * (task.progress || 0)) / 100;
                                const loadedMB = (loadedBytes / (1024 * 1024)).toFixed(1);
                                return `جاري رفع الملفات: MB ${loadedMB} من MB ${totalMB}`;
                              })()}
                        </span>
                        <strong style={{ color: isProcessing ? "#0284c7" : "#059669" }}>{task.progress}%</strong>
                      </div>
                    </div>
                  )}

                  {/* Completed State */}
                  {isCompleted && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                        fontSize: "11px",
                        color: "#059669",
                        fontWeight: 600,
                      }}
                    >
                      <CheckCircle2 size={13} />
                      <span>تم اكتمال الرفع والحفظ بالسحابة بنجاح!</span>
                    </div>
                  )}

                  {/* Error State */}
                  {isError && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                        fontSize: "10.5px",
                        color: "#dc2626",
                      }}
                    >
                      <AlertCircle size={13} />
                      <span>{task.error || "تعذر إكمال الرفع"}</span>
                    </div>
                  )}
                </div>
              );
            }))}
          </div>

          {/* Footer */}
          {completedTasks.length > 0 && (
            <div
              style={{
                padding: "8px 14px",
                borderTop: "1px solid var(--border-color, #e2e8f0)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--bg-surface-secondary, #f8fafc)",
              }}
            >
              <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                {completedTasks.length} ملف مكتمل
              </span>
              <button
                type="button"
                onClick={() => uploadManager.clearCompleted()}
                style={{
                  background: "none",
                  border: "none",
                  color: "#0284c7",
                  fontSize: "11px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                مسح المكتمل
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

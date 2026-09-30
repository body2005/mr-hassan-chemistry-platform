import React from "react";
import {
  Video,
  X,
} from "lucide-react";
import { StudentRecord } from "../types/lms";

interface StudentDetailModalProps {
  student: StudentRecord | null;
  onClose: () => void;
}

export const StudentDetailModal: React.FC<StudentDetailModalProps> = ({
  student,
  onClose,
}) => {
  if (!student) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: "720px", padding: "26px", background: "var(--bg-surface)", border: "1px solid var(--border-color)" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px", borderBottom: "1px solid var(--border-color)", paddingBottom: "14px" }}>
          <div>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>
              {student.academicYearLabel} • الرقم القومي: {student.nationalId}
            </span>
            <h2 style={{ margin: "6px 0 2px", fontSize: "20px", color: "var(--text-main)" }}>
              سجل متابعة الطالب: {student.name}
            </h2>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>
              نسبة المتابعة العامة: <strong>{(student.overallAttendanceRatio * 100).toFixed(0)}%</strong> | نسبة تسليم الواجبات: <strong>{(student.assignmentSubmissionRatio * 100).toFixed(0)}%</strong>
            </span>
          </div>

          <button
            onClick={onClose}
            className="modal-close-btn"
            style={{
              background: "var(--modal-close-bg)",
              border: "none",
              color: "#ffffff",
              cursor: "pointer",
              borderRadius: "8px",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Stats Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px", marginBottom: "20px" }}>
          <div style={{ background: "var(--bg-surface-secondary)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>متوسط درجات الكويز</span>
            <strong style={{ fontSize: "18px", color: "var(--text-main)" }}>{student.averageQuizScore}%</strong>
          </div>
          <div style={{ background: "var(--bg-surface-secondary)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>نسبة نجاح الواجبات</span>
            <strong style={{ fontSize: "18px", color: "#059669" }}>{student.homeworkSuccessRate}%</strong>
          </div>
          <div style={{ background: "var(--bg-surface-secondary)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>الفيديوهات المكتملة</span>
            <strong style={{ fontSize: "18px", color: "var(--text-main)" }}>
              {student.watchHistory.filter((v) => v.completionPercentage >= 90).length} / {student.watchHistory.length || 3}
            </strong>
          </div>
        </div>

        {/* Video Watch History & Interactive Viewing Timelines (Requirement 9) */}
        <div>
          <h3 style={{ margin: "0 0 12px", fontSize: "15px", fontWeight: 800, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "6px" }}>
            <Video size={17} style={{ color: "#059669" }} />
            <span>تفاصيل مشاهدة الفيديوهات ومخطط المتابعة الزمني</span>
          </h3>

          {student.watchHistory.length === 0 ? (
            <div style={{ textAlign: "center", padding: "30px", background: "var(--bg-surface-secondary)", borderRadius: "10px", color: "var(--text-muted)", fontSize: "13px" }}>
              لم يقم الطالب بمشاهدة أي فيديو بعد في هذا المقرر.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {student.watchHistory.map((v, idx) => {
                const durationMin = Math.round(v.totalDurationSec / 60);
                const watchedMin = Math.round(v.watchedDurationSec / 60);
                const dropOffMin = Math.round(v.dropOffTimestampSec / 60);

                return (
                  <div
                    key={idx}
                    style={{
                      background: "var(--bg-surface)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "12px",
                      padding: "16px",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                      <div>
                        <strong style={{ display: "block", fontSize: "14px", color: "var(--text-main)" }}>
                          {v.videoTitle}
                        </strong>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                          {v.courseTitle} • آخر مشاهدة: {v.lastWatchedAt}
                        </span>
                      </div>

                      <span
                        style={{
                          fontSize: "12px",
                          fontWeight: 800,
                          padding: "3px 10px",
                          borderRadius: "20px",
                          background: v.completionPercentage >= 90 ? "var(--bg-accent)" : v.completionPercentage >= 50 ? "var(--bg-accent-warm)" : "#fee2e2",
                          color: v.completionPercentage >= 90 ? "#059669" : v.completionPercentage >= 50 ? "#d97706" : "#ef4444",
                        }}
                      >
                        {v.completionPercentage}% إنجاز
                      </span>
                    </div>

                    {/* Timeline Bar Visualizer */}
                    <div style={{ marginTop: "12px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
                        <span>شاهد {watchedMin} دقيقة من أصل {durationMin} دقيقة</span>
                        <span>
                          {v.completionPercentage < 100 ? `توقف عند الدقيقة ${dropOffMin}` : "أكمل مشاهدة الفيديو بالكامل"}
                        </span>
                      </div>

                      <div className="timeline-bar-container">
                        {v.segments.map((seg, sIdx) => {
                          const leftPct = (seg.startTimeSec / v.totalDurationSec) * 100;
                          const widthPct = ((seg.endTimeSec - seg.startTimeSec) / v.totalDurationSec) * 100;
                          return (
                            <div
                              key={sIdx}
                              className={`timeline-segment ${seg.watched ? "" : "unwatched"}`}
                              style={{
                                left: `${leftPct}%`,
                                width: `${widthPct}%`,
                              }}
                              title={`${seg.watched ? "تمت المشاهدة" : "تم التخطي"}: ${Math.round(seg.startTimeSec / 60)}د إلى ${Math.round(seg.endTimeSec / 60)}د`}
                            />
                          );
                        })}
                      </div>

                      <div style={{ display: "flex", gap: "14px", fontSize: "11px", color: "var(--text-muted)", marginTop: "6px" }}>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                          <span style={{ width: "10px", height: "10px", background: "#059669", borderRadius: "2px" }} />
                          مقاطع تمت مشاهدتها
                        </span>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                          <span style={{ width: "10px", height: "10px", background: "#cbd5e1", borderRadius: "2px" }} />
                          مقاطع تم تخطيها
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

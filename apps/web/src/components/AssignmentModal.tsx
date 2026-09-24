import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  Download,
  Eye,
  EyeOff,
  FileCheck2,
  FileText,
  Loader2,
  X,
} from "lucide-react";
import { AssignmentSubmission } from "../types/lms";
import { fetchApiBlob } from "../services/apiClient";

interface AssignmentModalProps {
  submission: AssignmentSubmission | null;
  onClose: () => void;
  onApproveGrade: (submissionId: string, updatedScore: number, teacherNotes: string) => void;
}

export const AssignmentModal: React.FC<AssignmentModalProps> = ({
  submission,
  onClose,
  onApproveGrade,
}) => {
  const [score, setScore] = useState(submission?.finalScore || 0);
  const [previewError, setPreviewError] = useState(false);
  const [showInlinePreview, setShowInlinePreview] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!submission) return;
    setScore(submission.finalScore);
    setPreviewError(false);
    setShowInlinePreview(false);
    setLoadingPreview(false);
  }, [submission]);

  useEffect(() => {
    return () => {
      if (previewBlobUrl) {
        URL.revokeObjectURL(previewBlobUrl);
      }
    };
  }, [previewBlobUrl]);

  async function handleTogglePreview() {
    if (showInlinePreview) {
      setShowInlinePreview(false);
      return;
    }
    if (previewBlobUrl) {
      setShowInlinePreview(true);
      return;
    }
    if (!submission?.fileUrl) return;

    try {
      setLoadingPreview(true);
      setPreviewError(false);
      const blob = await fetchApiBlob(submission.fileUrl);
      const url = URL.createObjectURL(blob);
      setPreviewBlobUrl(url);
      setShowInlinePreview(true);
    } catch {
      setPreviewError(true);
    } finally {
      setLoadingPreview(false);
    }
  }

  if (!submission) return null;

  function handleSave() {
    if (!submission) return;
    onApproveGrade(submission.id, score, "");
    onClose();
  }

  const isPdf = Boolean(submission.fileUrl?.toLowerCase().includes(".pdf"));

  return (
    <div
      className="modal-overlay"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        backgroundColor: "rgba(15, 23, 42, 0.72)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
        boxSizing: "border-box",
      }}
    >
      <div
        className="modal-content"
        style={{
          maxWidth: "760px",
          width: "94%",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          padding: "24px",
          borderRadius: "20px",
          background: "var(--bg-surface, #ffffff)",
          border: "1px solid var(--border-color, #e2e8f0)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.1)",
        }}
      >
        {/* Top Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingBottom: "14px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 800,
                  color: "#059669",
                  background: "var(--bg-accent, #ecfdf5)",
                  padding: "3px 8px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-accent, #a7f3d0)",
                }}
              >
                معاينة وتعديل درجة الواجب
              </span>
              <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                {submission.academicYearLabel} • {submission.submittedAt}
              </span>
            </div>
            <h2 style={{ margin: 0, fontSize: "17px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
              {submission.assignmentTitle}
            </h2>
          </div>

          <button
            onClick={onClose}
            style={{
              background: "var(--bg-surface-secondary, #f1f5f9)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "8px",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-muted, #64748b)",
              cursor: "pointer",
            }}
            title="إغلاق"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ overflowY: "auto", flex: 1, padding: "12px 2px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Student Info Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 16px",
              background: "var(--bg-surface-secondary, #f8fafc)",
              borderRadius: "10px",
              border: "1px solid var(--border-color, #e2e8f0)",
            }}
          >
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
                  fontWeight: 800,
                  fontSize: "13px",
                }}
              >
                {submission.studentName.slice(0, 2)}
              </div>
              <div>
                <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main, #0f172a)" }}>
                  {submission.studentName}
                </strong>
                <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                  {submission.lessonTitle}
                </span>
              </div>
            </div>

            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "#059669",
                background: "var(--bg-accent, #ecfdf5)",
                padding: "4px 10px",
                borderRadius: "6px",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <CheckCircle2 size={13} />
              <span>تم التسليم في الموعد</span>
            </span>
          </div>

          {/* Student Written Answer (If any) */}
          {submission.studentAnswer && (
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                padding: "16px",
                borderRadius: "12px",
                border: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main, #0f172a)", marginBottom: "8px" }}>
                إجابة الطالب المكتوبة:
              </strong>
              <div
                style={{
                  fontSize: "13px",
                  lineHeight: "1.6",
                  color: "var(--text-main, #0f172a)",
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  padding: "12px 14px",
                  borderRadius: "8px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  whiteSpace: "pre-wrap",
                }}
              >
                {submission.studentAnswer}
              </div>
            </div>
          )}

          {/* Student Uploaded Solution File (Safe On-Demand Preview - NO Auto Download) */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              padding: "16px",
              borderRadius: "12px",
              border: "1.5px solid var(--border-color-strong, #cbd5e1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", marginBottom: "12px", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-main, #0f172a)" }}>
                <FileText size={16} style={{ color: "#059669" }} />
                <strong style={{ fontSize: "13px" }}>
                  ورقة الحل المرفوعة من الطالب{submission.version ? ` — نسخة رقم ${submission.version}` : ""}
                </strong>
              </div>

              {submission.hasFile && submission.fileUrl && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={handleTogglePreview}
                    disabled={loadingPreview}
                    className="btn-secondary"
                    style={{
                      fontSize: "12px",
                      padding: "6px 12px",
                      gap: "6px",
                      display: "inline-flex",
                      alignItems: "center",
                      borderColor: showInlinePreview ? "#059669" : undefined,
                      color: showInlinePreview ? "#059669" : undefined,
                      fontWeight: 700,
                    }}
                  >
                    {loadingPreview ? (
                      <>
                        <Loader2 size={13} className="animate-spin" />
                        <span>جاري المعاينة...</span>
                      </>
                    ) : showInlinePreview ? (
                      <>
                        <EyeOff size={13} />
                        <span>إخفاء المعاينة</span>
                      </>
                    ) : (
                      <>
                        <Eye size={13} />
                        <span>معاينة ورقة الحل</span>
                      </>
                    )}
                  </button>

                  <a
                    href={submission.fileUrl}
                    download
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      background: "#0f392b",
                      color: "#ffffff",
                      borderRadius: "8px",
                      padding: "6px 12px",
                      fontSize: "12px",
                      fontWeight: 700,
                      textDecoration: "none",
                    }}
                  >
                    <Download size={13} />
                    <span>تنزيل الملف</span>
                  </a>
                </div>
              )}
            </div>

            {submission.hasFile && submission.fileUrl ? (
              showInlinePreview ? (
                <div
                  style={{
                    width: "100%",
                    maxHeight: "440px",
                    overflow: "auto",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    borderRadius: "10px",
                    background: "var(--bg-surface-secondary, #f8fafc)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "8px",
                    boxSizing: "border-box",
                  }}
                >
                  {previewError ? (
                    <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)" }}>
                      <p style={{ margin: "0 0 8px", fontSize: "13px" }}>تعذر عرض المعاينة التفاعلية داخل الصفحة.</p>
                      <a href={submission.fileUrl} download className="btn-primary" style={{ fontSize: "12px", gap: "6px", textDecoration: "none" }}>
                        <Download size={13} />
                        <span>تنزيل الملف وعرضه</span>
                      </a>
                    </div>
                  ) : isPdf ? (
                    <iframe
                      src={previewBlobUrl || submission.fileUrl}
                      title="ورقة حل الواجب"
                      onError={() => setPreviewError(true)}
                      style={{
                        width: "100%",
                        height: "420px",
                        border: "none",
                        borderRadius: "8px",
                      }}
                    />
                  ) : (
                    <img
                      src={previewBlobUrl || submission.fileUrl}
                      alt="ورقة حل الطالب"
                      onError={() => setPreviewError(true)}
                      style={{
                        maxWidth: "100%",
                        maxHeight: "420px",
                        objectFit: "contain",
                        borderRadius: "8px",
                        display: "block",
                      }}
                    />
                  )}
                </div>
              ) : (
                <div
                  style={{
                    textAlign: "center",
                    padding: "20px 16px",
                    background: "var(--bg-surface-secondary, #f8fafc)",
                    borderRadius: "10px",
                    border: "1px dashed var(--border-color, #cbd5e1)",
                  }}
                >
                  <FileText size={28} style={{ color: "#059669", margin: "0 auto 6px" }} />
                  <p style={{ margin: "0 0 6px", fontSize: "12.5px", fontWeight: 700, color: "var(--text-main, #334155)" }}>
                    تم إرفاق ورقة حل مصورة لهذا الواجب
                  </p>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted, #64748b)" }}>
                    اضغط على زر «معاينة ورقة الحل» أعلاه لمعاينتها فوراً، أو «تنزيل الملف».
                  </span>
                </div>
              )
            ) : (
              <div
                style={{
                  textAlign: "center",
                  padding: "24px",
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  borderRadius: "10px",
                  border: "1px dashed var(--border-color, #cbd5e1)",
                  color: "var(--text-muted, #64748b)",
                  fontSize: "12.5px",
                }}
              >
                لم يرفق الطالب ورقة حل مصورة لهذا الواجب.
              </div>
            )}
          </div>

          {/* ملخص الاعتماد النهائي للدرجة وتعديل الدرجة */}
          <div
            style={{
              background: "var(--bg-surface-secondary, #f8fafc)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "12px",
              padding: "16px",
            }}
          >
            <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main, #0f172a)", marginBottom: "12px" }}>
              ملخص الاعتماد النهائي للدرجة:
            </strong>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", textAlign: "center", marginBottom: "14px" }}>
              <div style={{ background: "var(--bg-surface, #ffffff)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-color, #e2e8f0)" }}>
                <small style={{ display: "block", color: "var(--text-muted, #64748b)", fontSize: "11.5px", marginBottom: "2px" }}>الدرجة العظمى</small>
                <strong style={{ fontSize: "18px", color: "var(--text-main, #0f172a)" }}>{submission.maxScore}</strong>
              </div>
              <div style={{ background: "var(--bg-surface, #ffffff)", padding: "12px", borderRadius: "8px", border: "1.5px solid #059669" }}>
                <small style={{ display: "block", color: "#059669", fontSize: "11.5px", fontWeight: 700, marginBottom: "2px" }}>درجة المعلم المعتمدة</small>
                <strong style={{ fontSize: "18px", color: "#0f392b" }}>{score}</strong>
              </div>
            </div>

            {/* حقل تعديل الدرجة النهائية مباشرة */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--bg-surface, #ffffff)", padding: "10px 14px", borderRadius: "10px", border: "1px solid var(--border-color, #e2e8f0)" }}>
              <label style={{ fontSize: "13px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
                الدرجة النهائية المعتمدة:
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <input
                  type="text"
                  inputMode="numeric"
                  value={score}
                  onChange={(e) => {
                    const num = parseInt(e.target.value.replace(/\D/g, ""), 10);
                    setScore(isNaN(num) ? 0 : Math.min(submission.maxScore, Math.max(0, num)));
                  }}
                  style={{
                    width: "90px",
                    padding: "8px 12px",
                    border: "2px solid #059669",
                    borderRadius: "8px",
                    fontSize: "18px",
                    fontWeight: 900,
                    textAlign: "center",
                    color: "var(--text-main)",
                    background: "var(--bg-surface)",
                    boxSizing: "border-box",
                    outline: "none",
                  }}
                />
                <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-muted)" }}>
                  / {submission.maxScore}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingTop: "14px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <button className="btn-secondary" onClick={onClose} style={{ padding: "8px 18px", fontSize: "12.5px" }}>
            إلغاء
          </button>

          <button
            className="btn-primary"
            onClick={handleSave}
            style={{ padding: "9px 24px", fontSize: "13px", fontWeight: 800, gap: "8px", background: "#059669" }}
          >
            <FileCheck2 size={16} />
            <span>اعتماد وحفظ الدرجة</span>
          </button>
        </div>
      </div>
    </div>
  );
};

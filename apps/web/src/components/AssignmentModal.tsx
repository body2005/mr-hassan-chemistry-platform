import React, { useState, useEffect } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  HelpCircle,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { AssignmentSubmission } from "../types/lms";

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
  // Wizard Step (1: Question & Answer, 2: AI Rubric & Feedback, 3: Final Grading & Notes)
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [score, setScore] = useState(submission?.finalScore || 0);
  const [feedback, setFeedback] = useState(submission?.teacherFeedback || "");

  // Reset step whenever a new submission is opened
  useEffect(() => {
    if (!submission) return;
    setCurrentStep(1);
    setScore(submission.finalScore);
    setFeedback(submission.teacherFeedback || "");
  }, [submission]);

  if (!submission) return null;

  function handleSave() {
    if (!submission) return;
    onApproveGrade(submission.id, score, feedback);
    onClose();
  }

  const steps: Array<{ number: 1 | 2 | 3; label: string; icon: typeof User }> = [
    { number: 1, label: "إجابة الطالب", icon: User },
    { number: 2, label: "تحليل الـ AI والـ Rubric", icon: Sparkles },
    { number: 3, label: "الاعتماد النهائي", icon: FileCheck2 },
  ];

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
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          padding: "26px",
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
                معالج تصحيح الواجبات
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

        {/* Wizard Step Indicator Bar */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "14px 10px",
            background: "var(--bg-surface-secondary, #f8fafc)",
            borderRadius: "12px",
            margin: "16px 0",
            border: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          {steps.map((step, idx) => {
            const isActive = currentStep === step.number;
            const isCompleted = currentStep > step.number;
            const Icon = step.icon;

            return (
              <React.Fragment key={step.number}>
                <button
                  type="button"
                  onClick={() => setCurrentStep(step.number)}
                  style={{
                    background: "none",
                    border: "none",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    cursor: "pointer",
                    padding: "4px 8px",
                    borderRadius: "8px",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div
                    style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "50%",
                      background: isCompleted ? "#059669" : isActive ? "#0f392b" : "var(--border-color-strong, #cbd5e1)",
                      color: "#ffffff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 800,
                      fontSize: "12px",
                    }}
                  >
                    {isCompleted ? <CheckCircle2 size={16} /> : <Icon size={14} />}
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: isActive ? 800 : 600,
                        color: isActive ? "#059669" : "var(--text-muted, #64748b)",
                      }}
                    >
                      الخطوة {step.number}
                    </span>
                    <small
                      style={{
                        display: "block",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: isActive ? "var(--text-main, #0f172a)" : "var(--text-light, #94a3b8)",
                      }}
                    >
                      {step.label}
                    </small>
                  </div>
                </button>

                {idx < steps.length - 1 && (
                  <div
                    style={{
                      flex: 1,
                      height: "2px",
                      background: currentStep > idx + 1 ? "#059669" : "var(--border-color, #e2e8f0)",
                      margin: "0 8px",
                    }}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Wizard Step Body with Smooth Step Animation */}
        <div style={{ overflowY: "auto", flex: 1, padding: "4px 2px", marginBottom: "16px" }}>
          {/* STEP 1: QUESTION & STUDENT SUBMISSION */}
          {currentStep === 1 && (
            <div key="step_1" className="wizard-step-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Student Metadata Card */}
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
                      background: "#334155",
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
                  }}
                >
                  تم التسليم في الموعد
                </span>
              </div>

              {/* Question Prompt */}
              <div
                style={{
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  padding: "16px",
                  borderRadius: "12px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px", color: "#0f392b" }}>
                  <HelpCircle size={16} />
                  <strong style={{ fontSize: "13px" }}>نص السؤال المطلوب من الطالب:</strong>
                </div>
                <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "var(--text-main, #334155)" }}>
                  {submission.questionPrompt}
                </p>
              </div>

              {/* Student Uploaded Solution File (photographed/typed paper) */}
              {submission.hasFile && submission.fileUrl && (
                <div
                  style={{
                    background: "var(--bg-surface, #ffffff)",
                    padding: "16px",
                    borderRadius: "12px",
                    border: "1.5px solid var(--border-color-strong, #cbd5e1)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", marginBottom: "10px", flexWrap: "wrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-main, #0f172a)" }}>
                      <FileText size={16} style={{ color: "#059669" }} />
                      <strong style={{ fontSize: "13px" }}>
                        ورقة الحل المرفوعة من الطالب{submission.version ? ` — نسخة رقم ${submission.version}` : ""}
                      </strong>
                    </div>
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
                        padding: "7px 14px",
                        fontSize: "12.5px",
                        fontWeight: 800,
                        textDecoration: "none",
                      }}
                    >
                      <Download size={14} />
                      <span>تنزيل ورقة الحل</span>
                    </a>
                  </div>
                  <iframe
                    src={submission.fileUrl}
                    title="ورقة حل الواجب"
                    style={{
                      width: "100%",
                      height: "420px",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      borderRadius: "10px",
                      background: "#f8fafc",
                    }}
                  />
                  <small style={{ display: "block", marginTop: "8px", color: "var(--text-muted, #64748b)", fontSize: "11.5px" }}>
                    المعاينة تعمل مع ملفات PDF — للصور استخدم زر التنزيل ثم افتحها من جهازك.
                  </small>
                </div>
              )}

              {/* Student Written Answer */}
              <div
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  padding: "16px",
                  borderRadius: "12px",
                  border: "1.5px solid var(--border-color-strong, #cbd5e1)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px", color: "var(--text-main, #0f172a)" }}>
                  <FileText size={16} style={{ color: "#2563eb" }} />
                  <strong style={{ fontSize: "13px" }}>إجابة الطالب المكتوبة بالتفصيل:</strong>
                </div>
                <div
                  style={{
                    background: "var(--bg-surface-secondary, #f1f5f9)",
                    padding: "14px",
                    borderRadius: "8px",
                    fontSize: "13px",
                    lineHeight: "1.7",
                    color: "var(--text-main, #1e293b)",
                    fontFamily: "monospace, system-ui",
                  }}
                >
                  "{submission.studentAnswer}"
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: AI RUBRIC ANALYSIS & EXPLANATION */}
          {currentStep === 2 && (
            <div key="step_2" className="wizard-step-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* AI Overall Score & Banner */}
              <div
                style={{
                  background: "var(--bg-accent, #f0fdf4)",
                  border: "1.5px solid var(--border-accent, #bbf7d0)",
                  borderRadius: "12px",
                  padding: "16px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "10px",
                      background: "#059669",
                      color: "white",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Sparkles size={22} />
                  </div>
                  <div>
                    <strong style={{ display: "block", fontSize: "14px", color: "#166534" }}>
                      تقييم معايير التصحيح
                    </strong>
                    <span style={{ fontSize: "11px", color: "#15803d" }}>
                      تم تحليل الإجابة وتدقيق خطوات الحل وفق معايير المنهج
                    </span>
                  </div>
                </div>

                <div
                  style={{
                    background: "#0f392b",
                    color: "#ffffff",
                    padding: "6px 14px",
                    borderRadius: "8px",
                    fontSize: "14px",
                    fontWeight: 800,
                  }}
                >
                  درجة الـ AI: {submission.aiScore} / {submission.maxScore}
                </div>
              </div>

              {/* AI Feedback Summary */}
              <div
                style={{
                  background: "var(--bg-surface-secondary, #eff6ff)",
                  border: "1px solid #bfdbfe",
                  borderRadius: "10px",
                  padding: "14px",
                }}
              >
                <strong style={{ display: "block", fontSize: "12px", color: "#1e40af", marginBottom: "4px" }}>
                  التقرير التحليلي للإجابة:
                </strong>
                <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#1e3a8a" }}>
                  {submission.aiFeedbackSummary}
                </p>
              </div>

              {/* Criteria Scores Breakdown */}
              <div>
                <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main, #0f172a)", marginBottom: "8px" }}>
                  تفصيل الدرجات حسب معايير التقييم والـ Rubric:
                </strong>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {submission.criteriaScores.map((crit, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: "var(--bg-surface, #ffffff)",
                        padding: "12px 14px",
                        borderRadius: "10px",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <strong style={{ display: "block", fontSize: "13px", color: "#0f392b" }}>
                          {crit.criterion}
                        </strong>
                        <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                          {crit.notes}
                        </span>
                      </div>

                      <div
                        style={{
                          background: crit.score === crit.max ? "#dcfce7" : "#fef3c7",
                          color: crit.score === crit.max ? "#166534" : "#92400e",
                          padding: "4px 10px",
                          borderRadius: "6px",
                          fontWeight: 800,
                          fontSize: "12px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {crit.score} / {crit.max} درجات
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: TEACHER FINAL APPROVAL & CUSTOM FEEDBACK */}
          {currentStep === 3 && (
            <div key="step_3" className="wizard-step-container" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Summary recap */}
              <div
                style={{
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  borderRadius: "12px",
                  padding: "16px",
                }}
              >
                <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main, #0f172a)", marginBottom: "8px" }}>
                  ملخص الاعتماد النهائي للدرجة:
                </strong>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px", textAlign: "center" }}>
                  <div style={{ background: "var(--bg-surface, #ffffff)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color, #e2e8f0)" }}>
                    <small style={{ display: "block", color: "var(--text-muted, #64748b)", fontSize: "11px" }}>الدرجة العظمى</small>
                    <strong style={{ fontSize: "16px", color: "var(--text-main, #0f172a)" }}>{submission.maxScore}</strong>
                  </div>
                  <div style={{ background: "var(--bg-surface, #ffffff)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color, #e2e8f0)" }}>
                    <small style={{ display: "block", color: "var(--text-muted, #64748b)", fontSize: "11px" }}>اقتراح الـ AI</small>
                    <strong style={{ fontSize: "16px", color: "#059669" }}>{submission.aiScore}</strong>
                  </div>
                  <div style={{ background: "var(--bg-surface, #ffffff)", padding: "10px", borderRadius: "8px", border: "1px solid #059669" }}>
                    <small style={{ display: "block", color: "#059669", fontSize: "11px", fontWeight: 700 }}>درجة المعلم المعتمدة</small>
                    <strong style={{ fontSize: "16px", color: "#0f392b" }}>{score}</strong>
                  </div>
                </div>
              </div>

              {/* Editable Final Score & Notes */}
              <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 800, color: "var(--text-main)", marginBottom: "6px" }}>
                    الدرجة النهائية المعتمدة:
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={score}
                    onChange={(e) => {
                      const num = parseInt(e.target.value.replace(/\D/g, ""), 10);
                      setScore(isNaN(num) ? 0 : Math.min(submission.maxScore, Math.max(0, num)));
                    }}
                    style={{
                      width: "100%",
                      padding: "12px",
                      border: "2px solid #059669",
                      borderRadius: "10px",
                      fontSize: "18px",
                      fontWeight: 900,
                      textAlign: "center",
                      color: "var(--text-main)",
                      background: "var(--bg-surface)",
                      boxSizing: "border-box",
                      outline: "none",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 800, color: "var(--text-main, #0f172a)", marginBottom: "6px" }}>
                    ملاحظات وتوجيهات المعلم للطالب:
                  </label>
                  <textarea
                    rows={3}
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="اكتب توجيهاً، نصيحة، أو إشادة للطالب..."
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      border: "1px solid var(--border-color-strong, #cbd5e1)",
                      borderRadius: "10px",
                      fontSize: "13px",
                      color: "var(--text-main, #0f172a)",
                      background: "var(--bg-surface, #ffffff)",
                      boxSizing: "border-box",
                      outline: "none",
                      lineHeight: "1.5",
                    }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Wizard Footer Navigation Controls */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingTop: "14px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          {/* Previous Button / Cancel */}
          {currentStep > 1 ? (
            <button
              className="btn-secondary"
              onClick={() => setCurrentStep((prev) => (prev === 1 ? 1 : prev - 1) as 1 | 2 | 3)}
              style={{ padding: "8px 16px", fontSize: "12px", gap: "6px" }}
            >
              <ArrowRight size={15} />
              <span>السابق</span>
            </button>
          ) : (
            <button className="btn-secondary" onClick={onClose} style={{ padding: "8px 16px", fontSize: "12px" }}>
              إلغاء
            </button>
          )}

          {/* Next Button / Final Save */}
          {currentStep < 3 ? (
            <button
              className="btn-primary"
              onClick={() => setCurrentStep((prev) => (prev === 3 ? 3 : prev + 1) as 1 | 2 | 3)}
              style={{ padding: "8px 20px", fontSize: "12px", gap: "6px" }}
            >
              <span>التالي</span>
              <ArrowLeft size={15} />
            </button>
          ) : (
            <button
              className="btn-primary"
              onClick={handleSave}
              style={{ padding: "9px 24px", fontSize: "13px", fontWeight: 800, gap: "8px", background: "#059669" }}
            >
              <FileCheck2 size={16} />
              <span>اعتماد الدرجة في كشف الدرجات</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

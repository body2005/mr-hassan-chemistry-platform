import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Award,
  Download,
  FileSpreadsheet,
  FileText,
  Printer,
  Sparkles,
  Loader2,
} from "lucide-react";
import { AssignmentSubmission, CurrentUser } from "../types/lms";
import { submissionService } from "../services/lmsService";
import { exportToCsv, exportToDocx, exportToPrintPdf } from "../utils/exportEngine";

export const MySubmissionsView: React.FC<{ currentUser: CurrentUser }> = ({ currentUser }) => {
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const averageScore = useMemo(() => {
    const graded = submissions.filter((item) => item.maxScore > 0 && item.finalScore >= 0);
    if (!graded.length) return 0;
    return Math.round(
      graded.reduce((sum, item) => sum + (item.finalScore / item.maxScore) * 100, 0) /
        graded.length,
    );
  }, [submissions]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void submissionService.getStudentSubmissions()
      .then((items) => {
        if (active) setSubmissions(items);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setSubmissions([]);
          setError(requestError instanceof Error ? requestError.message : "تعذر تحميل التسليمات");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function getExportPayload() {
    const headers = ["عنوان الواجب", "الدرس", "تاريخ التسليم", "درجة الـ AI", "الدرجة النهائية", "ملاحظات المعلم"];
    const rows = submissions.map((s) => [
      s.assignmentTitle,
      s.lessonTitle,
      s.submittedAt,
      `${s.aiScore} / ${s.maxScore}`,
      `${s.finalScore} / ${s.maxScore}`,
      s.teacherFeedback || "—",
    ]);

    return {
      title: `كشف درجات وواجبات الطالب: ${currentUser.name}`,
      subtitle: "منصة الكيمياء التعليمية",
      headers,
      rows,
      summaryStats: [
        { label: "إجمالي الواجبات المسلمة", value: submissions.length },
        { label: "متوسط الدرجات", value: `${averageScore}%` },
        { label: "المعتمد من المعلم", value: submissions.filter((item) => item.status === "approved").length },
      ],
    };
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 800, color: "#0f392b", background: "#ecfdf5", padding: "3px 8px", borderRadius: "6px" }}>
            كشف الطالب • MY ASSIGNMENTS & QUIZZES
          </span>
          <h1 style={{ margin: "6px 0 2px", fontSize: "24px", color: "#0f172a" }}>
            واجباتي واختباراتي المصححة
          </h1>
          <p style={{ margin: 0, color: "#64748b", fontSize: "13px" }}>
            استعرض درجات الواجبات التي قمت بتسليمها وملاحظات المعلم وتقييم الذكاء الاصطناعي لكل إجابة.
          </p>
        </div>

        {/* Universal Export Button (Requirement 11) */}
        <div style={{ position: "relative" }}>
          <button
            className="btn-primary"
            onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
            style={{ fontSize: "12px", gap: "6px" }}
          >
            <Download size={15} /> تصدير التقرير (Generate Report)
          </button>

          {exportDropdownOpen && (
            <div
              style={{
                position: "absolute",
                left: 0,
                top: "42px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "10px",
                boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
                zIndex: 50,
                width: "220px",
                overflow: "hidden",
              }}
            >
              <button
                onClick={() => {
                  exportToDocx(getExportPayload(), `my_report_card.docx`);
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid #f1f5f9", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
              >
                <FileText size={16} style={{ color: "#2563eb" }} />
                <strong>تصدير Word (.docx حقيقي)</strong>
              </button>

              <button
                onClick={() => {
                  exportToCsv(getExportPayload(), `my_report_card.csv`);
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid #f1f5f9", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
              >
                <FileSpreadsheet size={16} style={{ color: "#059669" }} />
                <strong>تصدير Excel / CSV</strong>
              </button>

              <button
                onClick={() => {
                  exportToPrintPdf(getExportPayload());
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
              >
                <Printer size={16} style={{ color: "#0f392b" }} />
                <strong>تصدير / طباعة PDF</strong>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Submissions List */}
      {loading && (
        <div className="empty-state"><Loader2 size={22} className="spin" /> جاري تحميل تسليماتك...</div>
      )}
      {!loading && error && (
        <div className="empty-state" role="alert"><AlertCircle size={22} /> {error}</div>
      )}
      {!loading && !error && submissions.length === 0 && (
        <div className="empty-state">لا توجد واجبات مسلّمة حتى الآن.</div>
      )}
      {!loading && !error && <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {submissions.map((sub) => (
          <div
            key={sub.id}
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "16px",
              padding: "22px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#0f392b", background: "#ecfdf5", padding: "3px 8px", borderRadius: "6px" }}>
                  {sub.academicYearLabel} • {sub.submittedAt}
                </span>
                <h3 style={{ margin: "6px 0 2px", fontSize: "17px", color: "#0f172a" }}>
                  {sub.assignmentTitle}
                </h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>{sub.lessonTitle}</span>
              </div>

              <div style={{ textAlign: "left", background: "#f8fafc", padding: "8px 16px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
                <span style={{ fontSize: "11px", color: "#64748b", display: "block" }}>الدرجة المرصودة</span>
                <strong style={{ fontSize: "20px", color: "#0f392b" }}>
                  {sub.finalScore} / {sub.maxScore}
                </strong>
              </div>
            </div>

            {/* Question and Answer */}
            <div style={{ background: "#f8fafc", padding: "12px 14px", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "10px", fontSize: "13px" }}>
              <strong style={{ color: "#0f392b", display: "block", marginBottom: "4px" }}>السؤال:</strong>
              <p style={{ margin: 0, color: "#334155" }}>{sub.questionPrompt}</p>
            </div>

            <div style={{ background: "#ffffff", padding: "12px 14px", borderRadius: "8px", border: "1px solid #cbd5e1", marginBottom: "14px", fontSize: "13px" }}>
              <strong style={{ color: "#0f172a", display: "block", marginBottom: "4px" }}>إجابتك المسلمة:</strong>
              <p style={{ margin: 0, color: "#1e293b", fontStyle: "italic" }}>"{sub.studentAnswer}"</p>
            </div>

            {/* AI Rubric Feedback & Teacher Note */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: "12px" }}>
              <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", padding: "12px", borderRadius: "8px", fontSize: "12px" }}>
                <strong style={{ display: "flex", alignItems: "center", gap: "4px", color: "#166534", marginBottom: "4px" }}>
                  <Sparkles size={14} /> ملاحظات المصحح الذكي (AI):
                </strong>
                <p style={{ margin: 0, color: "#1e3a8a", lineHeight: "1.4" }}>
                  {sub.aiFeedbackSummary}
                </p>
              </div>

              <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", padding: "12px", borderRadius: "8px", fontSize: "12px" }}>
                <strong style={{ display: "flex", alignItems: "center", gap: "4px", color: "#1e40af", marginBottom: "4px" }}>
                  <Award size={14} /> تعليق المعلم:
                </strong>
                <p style={{ margin: 0, color: "#1e293b", lineHeight: "1.4" }}>
                  {sub.teacherFeedback || "لم يضف المعلم تعليقًا بعد."}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>}
    </div>
  );
};

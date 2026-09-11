import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileText,
  Plus,
  Printer,
  Sliders,
  Trash2,
} from "lucide-react";
import { AssignmentSubmission, CustomColumn, StudentRecord } from "../types/lms";
import { submissionService, userService } from "../services/lmsService";
import { AssignmentModal } from "../components/AssignmentModal";
import { CustomColumnModal } from "../components/CustomColumnModal";
import { exportToCsv, exportToDocx, exportToPrintPdf } from "../utils/exportEngine";
import { useToast } from "../components/ToastProvider";

export const SubmissionsView: React.FC = () => {
  const toast = useToast();
  const [selectedYear, setSelectedYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">("1st_secondary");
  const [minThreshold, setMinThreshold] = useState<number>(65); // Minimum passing threshold %
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([]);
  const [students, setStudents] = useState<StudentRecord[]>([]);
  const [customColumns, setCustomColumns] = useState<CustomColumn[]>([]);

  const [activeSubmission, setActiveSubmission] = useState<AssignmentSubmission | null>(null);
  const [isCustomColModalOpen, setIsCustomColModalOpen] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);

  React.useEffect(() => {
    void Promise.all([submissionService.getTeacherSubmissions(), userService.getStudents()])
      .then(([serverSubmissions, serverStudents]) => {
        setSubmissions(serverSubmissions);
        setStudents(serverStudents.map((item) => ({
          id: item.id,
          name: item.display_name,
          email: item.email,
          nationalId: "—",
          academicYear: "1st_secondary",
          academicYearLabel: "الصف الأول الثانوي",
          overallAttendanceRatio: 0,
          assignmentSubmissionRatio: 0,
          averageQuizScore: 0,
          homeworkSuccessRate: 0,
          quizSuccessRate: 0,
          totalOverallGrade: 0,
          lastActiveDate: item.created_at.slice(0, 10),
          customFieldValues: {},
          watchHistory: [],
        })));
      })
      .catch(() => {
        setSubmissions([]);
        setStudents([]);
      });
  }, []);

  // Filter students and submissions for selected year
  const yearStudents = students.filter((s) => s.academicYear === selectedYear);
  const yearCustomCols = customColumns.filter(
    (c) => c.tableContext === "submissions" && (c.academicYear === selectedYear || c.academicYear === "all")
  );

  function handleAddCustomColumn(col: CustomColumn) {
    setCustomColumns([...customColumns, col]);
  }

  function handleDeleteCustomColumn(colId: string) {
    setCustomColumns(customColumns.filter((c) => c.id !== colId));
  }

  function handleUpdateCustomValue(studentId: string, colId: string, value: any) {
    setStudents((prev) =>
      prev.map((s) => {
        if (s.id === studentId) {
          return {
            ...s,
            customFieldValues: {
              ...s.customFieldValues,
              [colId]: value,
            },
          };
        }
        return s;
      })
    );
  }

  async function handleApproveGrade(subId: string, updatedScore: number, teacherNotes: string) {
    try {
      const updated = await submissionService.gradeSubmission(subId, updatedScore, teacherNotes);
      setSubmissions((prev) => prev.map((sub) => sub.id === subId ? updated : sub));
    } catch (error) {
      toast(error instanceof Error ? error.message : "تعذر اعتماد الدرجة", "danger");
    }
  }

  // Universal Export Handlers (Requirement 11 & Part 3 Clarification 3)
  function getExportPayload() {
    const headers = [
      "اسم الطالب",
      "الدرجة الكلية",
      "السنة الدراسية",
      "نسبة تسليم الواجبات %",
      "حالة المتابعة",
      ...yearCustomCols.map((c) => c.name),
    ];

    const rows = yearStudents.map((s) => {
      const isBelowMin = s.assignmentSubmissionRatio * 100 < minThreshold;
      return [
        s.name,
        `${s.totalOverallGrade}%`,
        s.academicYearLabel,
        `${(s.assignmentSubmissionRatio * 100).toFixed(0)}%`,
        isBelowMin ? "تنبيه: تحت المعدل الأدنى" : "منتظم ومستقر",
        ...yearCustomCols.map((c) => s.customFieldValues[c.id] ?? "—"),
      ];
    });

    const yearLabel =
      selectedYear === "1st_secondary"
        ? "الصف الأول الثانوي"
        : selectedYear === "2nd_secondary"
        ? "الصف الثاني الثانوي"
        : "الصف الثالث الثانوي";

    return {
      title: `تقرير تسليمات الواجبات والدرجات - ${yearLabel}`,
      subtitle: `الحد الأدنى المعتمد للتسليم: ${minThreshold}% • إجمالي الطلاب: ${yearStudents.length}`,
      headers,
      rows,
      summaryStats: [
        { label: "إجمالي الطلاب", value: yearStudents.length },
        { label: "المعدل الأدنى للواجبات", value: `${minThreshold}%` },
        {
          label: "الطلاب تحت المعدل الأدنى",
          value: yearStudents.filter((s) => s.assignmentSubmissionRatio * 100 < minThreshold).length,
        },
      ],
    };
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>
            متابعة المعلم • ASSIGNMENT SUBMISSIONS & GRADING
          </span>
          <h1 style={{ margin: "6px 0 2px", fontSize: "24px", color: "var(--text-main)" }}>
            متابعة تسليم الواجبات والتصحيح
          </h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13px" }}>
            استعرض كشوف درجات الطلاب لكل سنة دراسية، واعتمد تصحيح الـ AI للواجبات المقالية بنقرة واحدة.
          </p>
        </div>

        {/* Universal Export & Settings Actions (Requirement 11) */}
        <div style={{ display: "flex", gap: "10px", alignItems: "center", position: "relative", flexWrap: "wrap" }}>
          <button
            className="btn-secondary"
            onClick={() => setIsCustomColModalOpen(true)}
            style={{ fontSize: "12px", gap: "6px" }}
          >
            <Plus size={15} /> إضافة عمود مخصص
          </button>

          <div style={{ position: "relative" }}>
            <button
              className="btn-primary"
              onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
              style={{ fontSize: "12px", gap: "6px" }}
            >
              <Download size={15} /> تصدير التقرير
            </button>

            {exportDropdownOpen && (
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: "42px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "10px",
                  boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
                  zIndex: 50,
                  width: "220px",
                  overflow: "hidden",
                }}
              >
                <button
                  onClick={() => {
                    exportToDocx(getExportPayload(), `submissions_${selectedYear}.docx`);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <FileText size={16} style={{ color: "#2563eb" }} />
                  <strong>تصدير Word (.docx حقيقي)</strong>
                </button>

                <button
                  onClick={() => {
                    exportToCsv(getExportPayload(), `submissions_${selectedYear}.csv`);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <FileSpreadsheet size={16} style={{ color: "#059669" }} />
                  <strong>تصدير Excel / CSV</strong>
                </button>

                <button
                  onClick={() => {
                    exportToPrintPdf(getExportPayload());
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <Printer size={16} style={{ color: "#059669" }} />
                  <strong>تصدير / طباعة PDF</strong>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Year Selection Tree & Minimum Progress Setting (Requirement 8) */}
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "14px 16px", marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "13px", fontWeight: 800, color: "var(--text-main)", marginInlineEnd: "4px" }}>السنة الدراسية:</span>
          {[
            { id: "1st_secondary", label: "الأول الثانوي" },
            { id: "2nd_secondary", label: "الثاني الثانوي" },
            { id: "3rd_secondary", label: "الثالث الثانوي" },
          ].map((y) => (
            <button
              key={y.id}
              onClick={() => setSelectedYear(y.id as any)}
              style={{
                padding: "7px 14px",
                borderRadius: "8px",
                border: selectedYear === y.id ? "1.5px solid #0f392b" : "1px solid var(--border-color)",
                background: selectedYear === y.id ? "#0f392b" : "var(--bg-surface)",
                color: selectedYear === y.id ? "#ffffff" : "var(--text-main)",
                fontSize: "12px",
                fontWeight: 700,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {y.label}
            </button>
          ))}
        </div>

        {/* Minimum Threshold Input (Requirement 8: Automated alert when below threshold) */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", background: "var(--bg-surface-secondary)", padding: "6px 12px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
          <Sliders size={15} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-main)" }}>المعدل الأدنى للتسليم:</span>
          <input
            type="number"
            min="0"
            max="100"
            value={minThreshold}
            onChange={(e) => setMinThreshold(parseInt(e.target.value) || 0)}
            style={{ width: "54px", padding: "4px 6px", border: "1px solid var(--border-color)", borderRadius: "6px", fontSize: "13px", fontWeight: 800, textAlign: "center", color: "var(--text-main)", background: "var(--bg-surface)" }}
          />
          <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-muted)" }}>%</span>
        </div>
      </div>

      {/* Submissions & Student Progress Table with Smooth Scrolling */}
      <div className="table-responsive" style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", overflowX: "auto", overflowY: "auto", maxHeight: "560px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
        <table className="lms-table" style={{ minWidth: "880px" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "right", color: "var(--text-main)" }}>اسم الطالب</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>الدرجة الكلية</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>السنة الدراسية</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة تسليم الواجبات</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>حالة المتابعة</th>
              {/* Teacher Custom Columns (Requirement 14) */}
              {yearCustomCols.map((col) => (
                <th key={col.id} style={{ textAlign: "center", width: "16%", color: "var(--text-main)" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                    <span>{col.name}</span>
                    <button
                      onClick={() => handleDeleteCustomColumn(col.id)}
                      style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 0 }}
                      title="حذف هذا العمود المخصص"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </th>
              ))}
              <th style={{ textAlign: "center", width: "16%", color: "var(--text-main)" }}>إجراءات وتصحيح الواجب</th>
            </tr>
          </thead>
          <tbody>
            {yearStudents.length === 0 ? (
              <tr>
                <td
                  colSpan={6 + yearCustomCols.length}
                  style={{
                    textAlign: "center",
                    padding: "36px 20px",
                    color: "var(--text-muted)",
                    fontSize: "13px",
                    fontWeight: 700,
                  }}
                >
                  لا توجد تسليمات أو طلاب في هذه السنة الدراسية حالياً. (ستظهر بياناتهم تلقائياً فور تسجيل الطلاب)
                </td>
              </tr>
            ) : (
              yearStudents.map((student) => {
                const subRatioPct = Math.round(student.assignmentSubmissionRatio * 100);
              const isBelowMin = subRatioPct < minThreshold;
              const studentSub = submissions.find((sub) => sub.studentId === student.id);

              return (
                <tr key={student.id}>
                  <td style={{ textAlign: "right" }}>
                    <strong style={{ display: "block", color: "var(--text-main)", fontSize: "13px" }}>{student.name}</strong>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{student.email}</span>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <strong style={{ fontSize: "14px", color: student.totalOverallGrade >= 75 ? "var(--text-main)" : "#ef4444" }}>
                      {student.totalOverallGrade}%
                    </strong>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{student.academicYearLabel}</span>
                  </td>
                  {/* Independent numeric percentage column */}
                  <td style={{ textAlign: "center" }}>
                    <strong style={{ fontSize: "14px", color: isBelowMin ? "#ef4444" : "#059669" }}>
                      {subRatioPct}%
                    </strong>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {isBelowMin ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "3px 8px", background: "var(--bg-accent-warm)", color: "#ef4444", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                        <AlertTriangle size={12} /> تحت المعدل الأدنى ({minThreshold}%)
                      </span>
                    ) : (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "3px 8px", background: "var(--bg-accent)", color: "#059669", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                        <CheckCircle2 size={12} /> منتظم ومستقر
                      </span>
                    )}
                  </td>

                  {/* Custom Columns Editable Cells (Requirement 14) */}
                  {yearCustomCols.map((col) => (
                    <td key={col.id} style={{ textAlign: "center" }}>
                      {col.dataType === "checkbox" ? (
                        <input
                          type="checkbox"
                          checked={!!student.customFieldValues[col.id]}
                          onChange={(e) => handleUpdateCustomValue(student.id, col.id, e.target.checked)}
                          style={{ width: "16px", height: "16px", accentColor: "#059669" }}
                        />
                      ) : (
                        <input
                          type="text"
                          value={student.customFieldValues[col.id] || ""}
                          onChange={(e) => handleUpdateCustomValue(student.id, col.id, e.target.value)}
                          placeholder="—"
                          style={{ width: "120px", padding: "4px 8px", border: "1px solid var(--border-color)", borderRadius: "6px", fontSize: "12px", textAlign: "center", background: "var(--bg-surface)", color: "var(--text-main)" }}
                        />
                      )}
                    </td>
                  ))}

                  {/* Assignment Modal Trigger (Requirement 8) */}
                  <td style={{ textAlign: "center" }}>
                    {studentSub ? (
                      <button
                        className="btn-secondary"
                        onClick={() => setActiveSubmission(studentSub)}
                        style={{ padding: "6px 12px", fontSize: "12px", gap: "4px", display: "inline-flex", margin: "0 auto" }}
                      >
                        <FileText size={14} /> عرض إجابة وتصحيح الـ AI ({studentSub.finalScore}/{studentSub.maxScore})
                      </button>
                    ) : (
                      <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>لم يسلم الواجب بعد</span>
                    )}
                  </td>
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>

      {/* Assignment Grading Modal (Requirement 8) */}
      <AssignmentModal
        submission={activeSubmission}
        onClose={() => setActiveSubmission(null)}
        onApproveGrade={handleApproveGrade}
      />

      {/* Custom Column Modal (Requirement 14) */}
      <CustomColumnModal
        isOpen={isCustomColModalOpen}
        onClose={() => setIsCustomColModalOpen(false)}
        tableContext="submissions"
        academicYear={selectedYear}
        onAddColumn={handleAddCustomColumn}
      />
    </div>
  );
};

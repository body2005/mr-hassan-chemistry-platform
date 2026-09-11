import React, { useState } from "react";
import {
  Download,
  FileSpreadsheet,
  FileText,
  Plus,
  Printer,
  Trash2,
} from "lucide-react";
import { CustomColumn, StudentRecord } from "../types/lms";
import { userService } from "../services/lmsService";
import { CustomColumnModal } from "../components/CustomColumnModal";
import { exportToCsv, exportToDocx, exportToPrintPdf } from "../utils/exportEngine";

export const StudentAnalyticsView: React.FC = () => {
  const [selectedYear, setSelectedYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">("1st_secondary");
  const [students, setStudents] = useState<StudentRecord[]>([]);
  const [customColumns, setCustomColumns] = useState<CustomColumn[]>([]);
  const [isCustomColModalOpen, setIsCustomColModalOpen] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);

  React.useEffect(() => {
    void userService.getStudents()
      .then((items) => setStudents(items.map((item) => ({
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
        isBlocked: !item.is_active,
        customFieldValues: {},
        watchHistory: [],
      }))))
      .catch(() => setStudents([]));
  }, []);

  const yearStudents = students.filter((s) => s.academicYear === selectedYear);
  const yearCustomCols = customColumns.filter(
    (c) => c.tableContext === "students" && (c.academicYear === selectedYear || c.academicYear === "all")
  );

  // Group Aggregate Metrics (Requirement 9) - Calculated strictly from existing students
  const groupPassingRate =
    yearStudents.length > 0
      ? Math.round(
          yearStudents.reduce((acc, s) => acc + (s.quizSuccessRate + s.homeworkSuccessRate) / 2, 0) /
            yearStudents.length
        )
      : 0;

  const passedStudentsCount =
    yearStudents.filter((s) => (s.quizSuccessRate + s.homeworkSuccessRate) / 2 >= 50).length;

  const groupOverallAttendance =
    yearStudents.length > 0
      ? Math.round(
          (yearStudents.reduce((acc, s) => acc + s.overallAttendanceRatio, 0) / yearStudents.length) * 100
        )
      : 0;

  const groupSubmissionRate =
    yearStudents.length > 0
      ? Math.round(
          (yearStudents.reduce((acc, s) => acc + s.assignmentSubmissionRatio, 0) / yearStudents.length) * 100
        )
      : 0;

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


  // Universal Export Handlers (Requirement 11 & Part 3 Clarification 3)
  function getExportPayload() {
    const headers = [
      "اسم الطالب",
      "الرقم القومي",
      "نسبة المتابعة الشخصية %",
      "نسبة نجاح الواجبات %",
      "نسبة نجاح الاختبارات %",
      "آخر ظهور",
      ...yearCustomCols.map((c) => c.name),
    ];

    const rows = yearStudents.map((s) => [
      s.name,
      s.nationalId,
      `${(s.overallAttendanceRatio * 100).toFixed(0)}%`,
      `${s.homeworkSuccessRate}%`,
      `${s.quizSuccessRate}%`,
      s.lastActiveDate,
      ...yearCustomCols.map((c) => s.customFieldValues[c.id] ?? "—"),
    ]);

    const yearLabel =
      selectedYear === "1st_secondary"
        ? "الصف الأول الثانوي"
        : selectedYear === "2nd_secondary"
        ? "الصف الثاني الثانوي"
        : "الصف الثالث الثانوي";

    return {
      title: `تقرير متابعة ومخطط مشاهدة الطلاب - ${yearLabel}`,
      subtitle: `نسبة نجاح المجموعة: ${groupPassingRate}% • نسبة المتابعة العامة: ${groupOverallAttendance}%`,
      headers,
      rows,
      summaryStats: [
        { label: "إجمالي طلاب المجموعة", value: yearStudents.length },
        { label: "نسبة نجاح المجموعة", value: `${groupPassingRate}%` },
        { label: "نسبة المتابعة والحضور العامة", value: `${groupOverallAttendance}%` },
      ],
    };
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>
            متابعة الطلاب • COHORT TRACKING & VIDEO TIMELINES
          </span>
          <h1 style={{ margin: "6px 0 2px", fontSize: "24px", color: "var(--text-main)" }}>
            متابعة الطلاب ومخطط المشاهدة
          </h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13px" }}>
            نسب النجاح العامة لكل سنة دراسية، مع مخطط زمني تفصيلي لمشاهدة كل طالب لفيديوهات الشرح.
          </p>
        </div>

        {/* Universal Export & Column Customization */}
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
                    exportToDocx(getExportPayload(), `student_cohort_${selectedYear}.docx`);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <FileText size={16} style={{ color: "#2563eb" }} />
                  <strong>تصدير Word (.docx حقيقي)</strong>
                </button>

                <button
                  onClick={() => {
                    exportToCsv(getExportPayload(), `student_cohort_${selectedYear}.csv`);
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

      {/* Year Selection */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px", flexWrap: "wrap", alignItems: "center" }}>
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
              padding: "8px 16px",
              borderRadius: "8px",
              border: selectedYear === y.id ? "1.5px solid #0f392b" : "1px solid var(--border-color)",
              background: selectedYear === y.id ? "#0f392b" : "var(--bg-surface)",
              color: selectedYear === y.id ? "#ffffff" : "var(--text-main)",
              fontSize: "12.5px",
              fontWeight: 700,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {y.label}
          </button>
        ))}
      </div>

      {/* Modern Dashboard Layout: 1 Primary Hero KPI + 3 Compact Secondary Metrics */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "16px",
          marginBottom: "24px",
          alignItems: "stretch",
        }}
      >
        {/* Primary Hero Metric (Large, Prominent KPI - The Number is the Hero) */}
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "10px",
            padding: "22px 24px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "12.5px", color: "var(--text-muted)", fontWeight: 700 }}>
                  معدل النجاح التراكمي للمجموعة
                </span>
                <span
                  style={{
                    fontSize: "10.5px",
                    fontWeight: 700,
                    color: "var(--text-muted)",
                    border: "1px solid var(--border-color)",
                    padding: "2px 6px",
                    borderRadius: "4px",
                  }}
                >
                  الفصل الحالي
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "10px", marginTop: "8px" }}>
                <strong
                  style={{
                    fontSize: "38px",
                    fontWeight: 800,
                    color: "var(--text-main)",
                    fontVariantNumeric: "tabular-nums",
                    lineHeight: 1,
                    letterSpacing: "-0.02em",
                  }}
                >
                  {groupPassingRate}%
                </strong>
                <span
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "#059669",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  ({passedStudentsCount} طالب ناجح)
                </span>
              </div>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "16px",
              borderTop: "1px solid var(--border-color)",
              paddingTop: "10px",
              fontSize: "11.5px",
              color: "var(--text-muted)",
            }}
          >
            <span>متوسط الواجبات والاختبارات المعتمدة</span>
            <span style={{ fontVariantNumeric: "tabular-nums" }}>آخر 30 يوماً</span>
          </div>
        </div>

        {/* 3 Secondary Sub-Metrics (Compact & Sleek) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: "12px",
          }}
        >
          {/* Sub-Metric 1: Overall Attendance */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontSize: "11.5px", color: "var(--text-muted)", fontWeight: 700 }}>
              نسبة المتابعة والحضور
            </span>
            <div style={{ display: "flex", alignItems: "baseline", marginTop: "8px" }}>
              <strong
                style={{
                  fontSize: "22px",
                  fontWeight: 800,
                  color: "var(--text-main)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {groupOverallAttendance}%
              </strong>
            </div>
            <span style={{ fontSize: "10.5px", color: "var(--text-muted)", marginTop: "6px" }}>
              إكمال مشاهدة الدروس
            </span>
          </div>

          {/* Sub-Metric 2: Enrolled Active Students */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontSize: "11.5px", color: "var(--text-muted)", fontWeight: 700 }}>
              الطلاب المقيدين
            </span>
            <div style={{ display: "flex", alignItems: "baseline", marginTop: "8px" }}>
              <strong
                style={{
                  fontSize: "22px",
                  fontWeight: 800,
                  color: "var(--text-main)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {yearStudents.length} طالب
              </strong>
            </div>
            <span style={{ fontSize: "10.5px", color: "var(--text-muted)", marginTop: "6px" }}>
              مسجلين بالسنة الدراسية
            </span>
          </div>

          {/* Sub-Metric 3: Homework Submission Rate */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontSize: "11.5px", color: "var(--text-muted)", fontWeight: 700 }}>
              الالتزام بالواجبات
            </span>
            <div style={{ display: "flex", alignItems: "baseline", marginTop: "8px" }}>
              <strong
                style={{
                  fontSize: "22px",
                  fontWeight: 800,
                  color: "var(--text-main)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {groupSubmissionRate}%
              </strong>
            </div>
            <span style={{ fontSize: "10.5px", color: "var(--text-muted)", marginTop: "6px" }}>
              تسليم المهام بالموعد
            </span>
          </div>
        </div>
      </div>

      {/* Student Evaluation and Progress Table with Hairline Border and Zero Unnecessary Shadows */}
      <div className="table-responsive" style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "10px", overflowX: "auto", overflowY: "auto", maxHeight: "560px" }}>
        <table className="lms-table" style={{ minWidth: "980px" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "right", color: "var(--text-main)" }}>اسم الطالب</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>الرقم القومي</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة المتابعة الشخصية %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة نجاح الواجبات %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة نجاح الاختبارات %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>آخر ظهور</th>
              {/* Custom Columns (Requirement 14) */}
              {yearCustomCols.map((col) => (
                <th key={col.id} style={{ textAlign: "center", color: "var(--text-main)" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                    <span>{col.name}</span>
                    <button
                      onClick={() => handleDeleteCustomColumn(col.id)}
                      style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 0 }}
                      title="حذف العمود المخصص"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </th>
              ))}
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
                  لا يوجد طلاب مسجلون حالياً في هذه السنة الدراسية. (ستظهر بياناتهم ومخطط متابعتهم تلقائياً فور تسجيل أي طالب جديد)
                </td>
              </tr>
            ) : (
              yearStudents.map((student) => {
                const attendancePct = Math.round(student.overallAttendanceRatio * 100);
                const isBlocked = !!student.isBlocked;

                return (
                  <tr key={student.id} style={{ background: isBlocked ? "#fff5f5" : undefined }}>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <strong style={{ color: "var(--text-main)", fontSize: "13px" }}>{student.name}</strong>
                      {isBlocked && (
                        <span style={{ fontSize: "10px", fontWeight: 800, padding: "1px 6px", borderRadius: "4px", background: "#fee2e2", color: "#b91c1c" }}>
                          محظور
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{student.email}</span>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-main)", fontFamily: "monospace" }}>{student.nationalId}</span>
                  </td>
                  {/* Explicit attendance % visible in row */}
                  <td style={{ textAlign: "center" }}>
                    <strong style={{ fontSize: "14px", color: attendancePct >= 75 ? "var(--text-main)" : "#ef4444", fontVariantNumeric: "tabular-nums" }}>
                      {attendancePct}%
                    </strong>
                  </td>
                  {/* Explicit homework success % visible in row */}
                  <td style={{ textAlign: "center" }}>
                    <strong style={{ fontSize: "14px", color: student.homeworkSuccessRate >= 70 ? "#059669" : "#ef4444", fontVariantNumeric: "tabular-nums" }}>
                      {student.homeworkSuccessRate}%
                    </strong>
                  </td>
                  {/* Explicit quiz success % visible in row */}
                  <td style={{ textAlign: "center" }}>
                    <strong style={{ fontSize: "14px", color: student.quizSuccessRate >= 70 ? "#059669" : "#ef4444", fontVariantNumeric: "tabular-nums" }}>
                      {student.quizSuccessRate}%
                    </strong>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{student.lastActiveDate}</span>
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

                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>

      {/* Custom Column Modal (Requirement 14) */}
      <CustomColumnModal
        isOpen={isCustomColModalOpen}
        onClose={() => setIsCustomColModalOpen(false)}
        tableContext="students"
        academicYear={selectedYear}
        onAddColumn={handleAddCustomColumn}
      />
    </div>
  );
};

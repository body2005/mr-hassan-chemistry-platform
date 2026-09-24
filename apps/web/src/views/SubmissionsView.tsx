import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  Plus,
  Printer,
  Search,
  Sliders,
  Trash2,
  X,
} from "lucide-react";
import { AssignmentSubmission, CustomColumn, StudentRecord } from "../types/lms";
import { submissionService, userService } from "../services/lmsService";
import { getCachedData } from "../services/apiClient";
import { AssignmentModal } from "../components/AssignmentModal";
import { ExamGradingModal } from "../components/ExamGradingModal";
import { CustomColumnModal } from "../components/CustomColumnModal";
import { StudentDetailWizard } from "../components/StudentDetailWizard";
import { exportToCsv, exportToDocx, exportToExcel, exportToPrintPdf } from "../utils/exportEngine";
import { useToast } from "../components/ToastProvider";

function mapApiStudentToRecord(item: any): StudentRecord {
  const year: "1st_secondary" | "2nd_secondary" | "3rd_secondary" =
    item.grade_level === "SECONDARY_2"
      ? "2nd_secondary"
      : item.grade_level === "SECONDARY_3"
      ? "3rd_secondary"
      : "1st_secondary";

  const label =
    year === "2nd_secondary"
      ? "الصف الثاني الثانوي"
      : year === "3rd_secondary"
      ? "الصف الثالث الثانوي"
      : "الصف الأول الثانوي";

  return {
    id: item.id,
    name: item.display_name,
    email: item.email,
    nationalId: item.national_id || "—",
    guardianPhone: item.guardian_phone || item.parent_phone || item.phone || "—",
    academicYear: year,
    academicYearLabel: label,
    overallAttendanceRatio: typeof item.overall_attendance_ratio === "number" ? item.overall_attendance_ratio : 0,
    assignmentSubmissionRatio: typeof item.assignment_submission_ratio === "number" ? item.assignment_submission_ratio : 0,
    averageQuizScore: typeof item.average_quiz_score === "number" ? item.average_quiz_score : 0,
    homeworkSuccessRate: typeof item.homework_success_rate === "number" ? item.homework_success_rate : 0,
    quizSuccessRate: typeof item.quiz_success_rate === "number" ? item.quiz_success_rate : 0,
    totalOverallGrade: typeof item.total_overall_grade === "number" ? item.total_overall_grade : 0,
    lastActiveDate: item.last_active_date || (item.created_at ? item.created_at.slice(0, 10) : "—"),
    isBlocked: !item.is_active,
    hasCompletedExam: Boolean(
      (typeof item.quizzes_taken === "number" && item.quizzes_taken > 0) ||
      (typeof item.quiz_attempts_count === "number" && item.quiz_attempts_count > 0) ||
      (typeof item.quiz_success_rate === "number" && item.quiz_success_rate > 0) ||
      (typeof item.average_quiz_score === "number" && item.average_quiz_score > 0) ||
      Boolean(item.has_completed_exam)
    ),
    studentPhone: item.student_phone || item.phone || "—",
    governorate: item.governorate || "—",
    schoolName: item.school_name || "—",
    gender: item.gender || "—",
    religion: item.religion || "—",
    createdAt: item.created_at ? item.created_at.slice(0, 10) : "—",
    examMissedDeadline: Boolean(item.exam_missed_deadline),
    customFieldValues: {},
    watchHistory: [],
  };
}

export const SubmissionsView: React.FC = () => {
  const toast = useToast();
  const [selectedYear, setSelectedYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">("1st_secondary");
  const [minThreshold, setMinThreshold] = useState<number>(65); // Minimum passing threshold %
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>(() => {
    const cached = getCachedData<any[]>("/submissions");
    return Array.isArray(cached) ? cached : [];
  });
  const [students, setStudents] = useState<StudentRecord[]>(() => {
    const cached = getCachedData<any[]>("/users?role=student");
    return Array.isArray(cached) ? cached.map(mapApiStudentToRecord) : [];
  });
  const [loading, setLoading] = useState(() => students.length === 0 || submissions.length === 0);
  const [customColumns, setCustomColumns] = useState<CustomColumn[]>([]);

  const [activeSubmission, setActiveSubmission] = useState<AssignmentSubmission | null>(null);
  const [activeExamStudent, setActiveExamStudent] = useState<StudentRecord | null>(null);
  const [isCustomColModalOpen, setIsCustomColModalOpen] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);

  React.useEffect(() => {
    void Promise.all([submissionService.getTeacherSubmissions(), userService.getStudents()])
      .then(([serverSubmissions, serverStudents]) => {
        setSubmissions(serverSubmissions);
        setStudents(serverStudents.map(mapApiStudentToRecord));
      })
      .catch(() => {
        setSubmissions([]);
        setStudents([]);
      })
      .finally(() => setLoading(false));

    const handleSubmissionEvent = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      // Refresh teacher submissions live
      void submissionService.getTeacherSubmissions().then((updated) => {
        setSubmissions(updated);
        if (detail?.student_name) {
          toast({
            message: `وصل تسليم واجب جديد من الطالب: ${detail.student_name}`,
            tone: "info",
          });
        }
      });
    };

    window.addEventListener("lms_submission_received", handleSubmissionEvent);
    window.addEventListener("lms_submission_graded", handleSubmissionEvent);

    return () => {
      window.removeEventListener("lms_submission_received", handleSubmissionEvent);
      window.removeEventListener("lms_submission_graded", handleSubmissionEvent);
    };
  }, [toast]);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [detailWizardStudent, setDetailWizardStudent] = useState<StudentRecord | null>(null);

  // Filter students and submissions for selected year and search query
  const yearStudents = students.filter((s) => s.academicYear === selectedYear);
  const filteredYearStudents = yearStudents.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    const nameMatch = s.name.toLowerCase().includes(q);
    const phoneMatch = (s.guardianPhone || "").replace(/\s+/g, "").includes(q);
    const emailMatch = s.email.toLowerCase().includes(q);
    const nationalIdMatch = (s.nationalId || "").includes(q);
    return nameMatch || phoneMatch || emailMatch || nationalIdMatch;
  });
  const yearCustomCols = customColumns.filter(
    (c) => (c.tableContext === "submissions" || c.tableContext === "students") && (c.academicYear === selectedYear || c.academicYear === "all")
  );

  // Group Aggregate Metrics (Requirement from Image 2)
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

  function handleUpdateCustomValue(studentId: string, colId: string, value: string | number | boolean) {
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
      setSubmissions((prev) => prev.map((sub) => (sub.id === subId ? updated : sub)));
      toast({
        message: "تم حفظ واعتماد الدرجة بنجاح",
        tone: "success",
      });
    } catch (error) {
      toast({
        message: error instanceof Error ? error.message : "تعذر اعتماد الدرجة",
        tone: "danger",
      });
    }
  }

  function handleApproveExamGrade(studentId: string, updatedExamScore: number, _teacherNotes?: string) {
    setStudents((prev) =>
      prev.map((s) => {
        if (s.id !== studentId) return s;
        const newQuizScore = Math.max(0, Math.min(100, Math.round(updatedExamScore)));
        const newTotal = Math.round((newQuizScore + s.homeworkSuccessRate) / 2);
        return {
          ...s,
          quizSuccessRate: newQuizScore,
          averageQuizScore: newQuizScore,
          totalOverallGrade: newTotal,
        };
      })
    );
    toast({
      message: `تم حفظ واعتماد درجة الامتحان بنجاح (${Math.round(updatedExamScore)}%)`,
      tone: "success",
    });
  }

  // Universal Export Handlers
  function getExportPayload() {
    const headers = [
      "اسم الطالب",
      "رقم ولي الأمر",
      "نسبة المتابعة الشخصية %",
      "نسبة نجاح الواجبات %",
      "نسبة نجاح الاختبارات %",
      "النسبة الكلية %",
      "حالة المتابعة",
      "آخر ظهور",
      ...yearCustomCols.map((c) => c.name),
    ];

    const rows = filteredYearStudents.map((s) => {
      const subRatioPct = Math.round(s.assignmentSubmissionRatio * 100);
      const isBelowMin = subRatioPct < minThreshold;
      return [
        s.name,
        s.guardianPhone || "—",
        `${(s.overallAttendanceRatio * 100).toFixed(0)}%`,
        `${s.homeworkSuccessRate}%`,
        `${s.quizSuccessRate}%`,
        `${s.totalOverallGrade}%`,
        isBelowMin ? "تنبيه: تحت المعدل الأدنى" : "منتظم ومستقر",
        s.lastActiveDate,
        ...yearCustomCols.map((c) => String(s.customFieldValues[c.id] ?? "—")),
      ];
    });

    const yearLabel =
      selectedYear === "1st_secondary"
        ? "الصف الأول الثانوي"
        : selectedYear === "2nd_secondary"
        ? "الصف الثاني الثانوي"
        : "الصف الثالث الثانوي";

    const arabicDate = new Date().toLocaleDateString("ar-EG", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });

    return {
      title: `تقرير متابعة الطالب وتقييم المجموعة - ${yearLabel}`,
      generatedDate: arabicDate,
      headers,
      rows,
      summaryStats: [
        { label: "إجمالي طلاب المجموعة", value: filteredYearStudents.length },
        { label: "نسبة نجاح المجموعة", value: `${groupPassingRate}%` },
        { label: "نسبة المتابعة والحضور", value: `${groupOverallAttendance}%` },
        { label: "الالتزام بالواجبات", value: `${groupSubmissionRate}%` },
        { label: "المعدل الأدنى للواجبات", value: `${minThreshold}%` },
        {
          label: "الطلاب تحت المعدل الأدنى",
          value: filteredYearStudents.filter((s) => s.assignmentSubmissionRatio * 100 < minThreshold).length,
        },
      ],
    };
  }

  const currentYearLabel =
    selectedYear === "1st_secondary"
      ? "الصف الأول الثانوي"
      : selectedYear === "2nd_secondary"
      ? "الصف الثاني الثانوي"
      : "الصف الثالث الثانوي";

  const exportDateStr = new Date().toISOString().slice(0, 10);
  const baseExportFileName = `متابعة طلاب_${currentYearLabel}_${exportDateStr}`;

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>
            متابعة المعلم - متابعة الطالب
          </span>
          <h1 style={{ margin: "6px 0 2px", fontSize: "24px", color: "var(--text-main)" }}>
            متابعة الطالب
          </h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13px" }}>
            متابعة نسب النجاح، الحضور، تسليم الواجبات، وتعيين واعتماد الدرجات.
          </p>
        </div>

        {/* Universal Export & Settings Actions */}
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
                    exportToDocx(getExportPayload(), `${baseExportFileName}.docx`);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <FileText size={16} style={{ color: "#2563eb" }} />
                  <strong>تصدير Word (.docx من اليمين للشمال)</strong>
                </button>

                <button
                  onClick={() => {
                    exportToExcel(getExportPayload(), `${baseExportFileName}.xls`);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <FileSpreadsheet size={16} style={{ color: "#059669" }} />
                  <strong>تصدير Excel (.xls من اليمين للشمال)</strong>
                </button>

                <button
                  onClick={() => {
                    exportToCsv(getExportPayload(), `${baseExportFileName}.csv`);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <FileSpreadsheet size={16} style={{ color: "#0d9488" }} />
                  <strong>تصدير CSV (جدول بيانات)</strong>
                </button>

                <button
                  onClick={() => {
                    exportToPrintPdf(getExportPayload(), baseExportFileName);
                    setExportDropdownOpen(false);
                  }}
                  style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", color: "var(--text-main)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}
                >
                  <Printer size={16} style={{ color: "#059669" }} />
                  <strong>تصدير / طباعة PDF (من اليمين للشمال)</strong>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Year Selection Tree & Minimum Progress Setting */}
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "14px 16px", marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "13px", fontWeight: 800, color: "var(--text-main)", marginInlineEnd: "4px" }}>السنة الدراسية:</span>
          {[
            { id: "1st_secondary" as const, label: "الأول الثانوي" },
            { id: "2nd_secondary" as const, label: "الثاني الثانوي" },
            { id: "3rd_secondary" as const, label: "الثالث الثانوي" },
          ].map((y) => (
            <button
              key={y.id}
              onClick={() => setSelectedYear(y.id)}
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

        {/* Minimum Threshold Input */}
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

      {/* KPI Cards Grid (Requirement: Image 2) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))",
          gap: "14px",
          marginBottom: "24px",
          alignItems: "stretch",
        }}
      >
        {/* Card 1: Primary Hero Metric */}
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "10px",
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
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
                  fontSize: "36px",
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

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "14px",
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

        {/* Card 2: Attendance & Engagement */}
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
                fontSize: "24px",
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

        {/* Card 3: Enrolled Students */}
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
                fontSize: "24px",
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

        {/* Card 4: Homework Submission */}
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
                fontSize: "24px",
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

      {/* Table Search & Toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          marginBottom: "14px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ position: "relative", flex: "1", minWidth: "260px", maxWidth: "460px" }}>
          <Search
            size={16}
            style={{
              position: "absolute",
              right: "12px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-muted)",
              pointerEvents: "none",
            }}
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="بحث باسم الطالب، رقم ولي الأمر، أو البريد الإلكتروني..."
            style={{
              width: "100%",
              padding: "9px 36px 9px 34px",
              border: "1px solid var(--border-color)",
              borderRadius: "10px",
              background: "var(--bg-surface)",
              color: "var(--text-main)",
              fontSize: "13px",
              outline: "none",
              boxSizing: "border-box",
            }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              style={{
                position: "absolute",
                left: "10px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                padding: "2px",
                display: "flex",
                alignItems: "center",
              }}
              title="مسح البحث"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div style={{ fontSize: "12.5px", color: "var(--text-muted)", fontWeight: 700 }}>
          {searchQuery ? (
            <span>
              نتائج البحث: <strong style={{ color: "#059669" }}>{filteredYearStudents.length}</strong> من إجمالي {yearStudents.length} طالب
            </span>
          ) : (
            <span>إجمالي الطلاب بالمجموعة: <strong style={{ color: "var(--text-main)" }}>{yearStudents.length}</strong></span>
          )}
        </div>
      </div>

      {/* Submissions & Student Progress Table (Requirement: Image 1 + Grading Action) */}
      <div className="table-responsive" style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", overflowX: "auto", overflowY: "auto", maxHeight: "560px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
        <table className="lms-table" style={{ minWidth: "1050px" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "right", color: "var(--text-main)" }}>اسم الطالب</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>رقم ولي الأمر</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة المتابعة الشخصية %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة نجاح الواجبات %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>نسبة نجاح الاختبارات %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>النسبة الكلية %</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>حالة المتابعة</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>آخر ظهور</th>
              {/* Teacher Custom Columns */}
              {yearCustomCols.map((col) => (
                <th key={col.id} style={{ textAlign: "center", color: "var(--text-main)" }}>
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
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>إجراءات وتصحيح الواجب</th>
              <th style={{ textAlign: "center", color: "var(--text-main)" }}>إجراءات وتصحيح الامتحان</th>
            </tr>
          </thead>
          <tbody>
            {loading && yearStudents.length === 0 ? (
              [...Array(4)].map((_, i) => (
                <tr key={`skel-sub-${i}`}>
                  <td colSpan={10 + yearCustomCols.length} style={{ padding: "16px 20px" }}>
                    <div
                      style={{
                        height: "22px",
                        background: "var(--bg-surface-secondary)",
                        borderRadius: "6px",
                        animation: "pulse 1.5s infinite ease-in-out",
                      }}
                    />
                  </td>
                </tr>
              ))
            ) : filteredYearStudents.length === 0 ? (
              <tr>
                <td
                  colSpan={10 + yearCustomCols.length}
                  style={{
                    textAlign: "center",
                    padding: "36px 20px",
                    color: "var(--text-muted)",
                    fontSize: "13px",
                    fontWeight: 700,
                  }}
                >
                  {searchQuery ? (
                    <div>
                      <p style={{ margin: "0 0 10px", fontSize: "14px" }}>
                        لا توجد نتائج مطابقة للبحث: «{searchQuery}»
                      </p>
                      <button
                        type="button"
                        onClick={() => setSearchQuery("")}
                        className="btn-secondary"
                        style={{ fontSize: "12px", padding: "6px 14px" }}
                      >
                        مسح البحث وعرض كل الطلاب
                      </button>
                    </div>
                  ) : (
                    "لا توجد بيانات أو طلاب في هذه السنة الدراسية حالياً. (ستظهر بياناتهم تلقائياً فور تسجيل الطلاب)"
                  )}
                </td>
              </tr>
            ) : (
              filteredYearStudents.map((student) => {
                const subRatioPct = Math.round(student.assignmentSubmissionRatio * 100);
                const attendancePct = Math.round(student.overallAttendanceRatio * 100);
                const isBelowMin = subRatioPct < minThreshold;
                const studentSub = submissions.find((sub) => sub.studentId === student.id);
                const isBlocked = !!student.isBlocked;

                const hasSubmittedHomeworkOnTime = Boolean(
                  studentSub &&
                  studentSub.submittedAt &&
                  !studentSub.isLate
                );

                const hasSolvedExamOnTime = Boolean(
                  (student.hasCompletedExam ||
                   (student.quizSuccessRate && student.quizSuccessRate > 0) ||
                   (student.averageQuizScore && student.averageQuizScore > 0)) &&
                  !student.examMissedDeadline
                );

                return (
                  <tr key={student.id} style={{ background: isBlocked ? "rgba(239, 68, 68, 0.05)" : undefined }}>
                    <td
                      style={{ textAlign: "right", cursor: "pointer" }}
                      onDoubleClick={() => setDetailWizardStudent(student)}
                      title="انقر مرتين لعرض كافة بيانات تسجيل الطالب"
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <strong style={{ display: "block", color: "var(--text-main)", fontSize: "13px" }}>{student.name}</strong>
                        {isBlocked && (
                          <span style={{ fontSize: "10px", fontWeight: 800, padding: "1px 6px", borderRadius: "4px", background: "#fee2e2", color: "#b91c1c" }}>
                            محظور
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{student.email}</span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontSize: "12px", color: "var(--text-main)", fontFamily: "monospace", direction: "ltr", display: "inline-block" }}>
                        {student.guardianPhone || "—"}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <strong style={{ fontSize: "14px", color: attendancePct >= 75 ? "var(--text-main)" : "#ef4444", fontVariantNumeric: "tabular-nums" }}>
                        {attendancePct}%
                      </strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <strong style={{ fontSize: "14px", color: student.homeworkSuccessRate >= 70 ? "#059669" : "#ef4444", fontVariantNumeric: "tabular-nums" }}>
                        {student.homeworkSuccessRate}%
                      </strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <strong style={{ fontSize: "14px", color: student.quizSuccessRate >= 70 ? "#059669" : "#ef4444", fontVariantNumeric: "tabular-nums" }}>
                        {student.quizSuccessRate}%
                      </strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <strong style={{ fontSize: "14px", color: student.totalOverallGrade >= 75 ? "var(--text-main)" : "#ef4444" }}>
                        {student.totalOverallGrade}%
                      </strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      {isBelowMin ? (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "3px 8px", background: "var(--bg-accent-warm)", color: "#ef4444", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                          <AlertTriangle size={12} /> تحت المعدل الأدنى
                        </span>
                      ) : (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "3px 8px", background: "var(--bg-accent)", color: "#059669", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                          <CheckCircle2 size={12} /> منتظم ومستقر
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{student.lastActiveDate}</span>
                    </td>

                    {/* Custom Columns Editable Cells */}
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
                            value={String(student.customFieldValues[col.id] ?? "")}
                            onChange={(e) => handleUpdateCustomValue(student.id, col.id, e.target.value)}
                            placeholder="—"
                            style={{ width: "120px", padding: "4px 8px", border: "1px solid var(--border-color)", borderRadius: "6px", fontSize: "12px", textAlign: "center", background: "var(--bg-surface)", color: "var(--text-main)" }}
                          />
                        )}
                      </td>
                    ))}

                    {/* Assignment Modal Trigger */}
                    <td style={{ textAlign: "center" }}>
                      {hasSubmittedHomeworkOnTime && studentSub ? (
                        <button
                          className="btn-secondary"
                          onClick={() => setActiveSubmission(studentSub)}
                          style={{ padding: "6px 12px", fontSize: "12px", gap: "4px", display: "inline-flex", margin: "0 auto" }}
                        >
                          <FileText size={14} /> معاينة وتعديل درجة
                        </button>
                      ) : (
                        <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>لم يسلم الواجب في موعده</span>
                      )}
                    </td>

                    {/* Exam Modal Trigger */}
                    <td style={{ textAlign: "center" }}>
                      {hasSolvedExamOnTime ? (
                        <button
                          className="btn-secondary"
                          onClick={() => setActiveExamStudent(student)}
                          style={{
                            padding: "6px 12px",
                            fontSize: "12px",
                            gap: "4px",
                            display: "inline-flex",
                            margin: "0 auto",
                            borderColor: "#059669",
                            color: "#059669",
                            fontWeight: 700,
                          }}
                        >
                          <FileCheck2 size={14} /> معاينة وتعديل درجة الامتحان
                        </button>
                      ) : (
                        <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>لم يؤدِ الامتحان في موعده</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Assignment Grading Modal */}
      <AssignmentModal
        submission={activeSubmission}
        onClose={() => setActiveSubmission(null)}
        onApproveGrade={handleApproveGrade}
      />

      {/* Exam Grading Modal */}
      <ExamGradingModal
        student={activeExamStudent}
        onClose={() => setActiveExamStudent(null)}
        onApproveGrade={handleApproveExamGrade}
      />

      {/* Custom Column Modal */}
      <CustomColumnModal
        isOpen={isCustomColModalOpen}
        onClose={() => setIsCustomColModalOpen(false)}
        tableContext="submissions"
        academicYear={selectedYear}
        onAddColumn={handleAddCustomColumn}
      />

      {/* Student Detail Wizard on Double-Click */}
      <StudentDetailWizard
        student={detailWizardStudent}
        onClose={() => setDetailWizardStudent(null)}
        onBlock={async (studentId, studentName, isBlocked) => {
          const res = await userService.toggleBlock(studentId);
          setStudents((prev) =>
            prev.map((s) => (s.id === studentId ? { ...s, isBlocked: !res.is_active } : s))
          );
          if (detailWizardStudent && detailWizardStudent.id === studentId) {
            setDetailWizardStudent({ ...detailWizardStudent, isBlocked: !res.is_active });
          }
          toast({
            message: `تم ${isBlocked ? "إلغاء حظر" : "حظر"} الطالب "${studentName}" بنجاح.`,
            tone: isBlocked ? "info" : "warning",
          });
        }}
        onDelete={async (studentId, studentName) => {
          await userService.deleteStudent(studentId);
          setStudents((prev) => prev.filter((s) => s.id !== studentId));
          setDetailWizardStudent(null);
          toast({
            message: `تم حذف الطالب "${studentName}" نهائياً.`,
            tone: "danger",
          });
        }}
      />
    </div>
  );
};

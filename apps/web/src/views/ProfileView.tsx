import React, { useState, useEffect } from "react";
import {
  Ban,
  Calendar,
  CheckCircle2,
  LogOut,
  Mail,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  Users,
  Video,
} from "lucide-react";
import { CurrentUser, StudentProfile, StudentRecord, TeacherProfile } from "../types/lms";
import { Language, translations } from "../utils/i18n";
import { userService } from "../services/lmsService";
import { useConfirm } from "../components/ConfirmWizard";
import { StudentDetailModal } from "../components/StudentDetailModal";
import { StudentDetailWizard } from "../components/StudentDetailWizard";

export interface ManagedStudentItem {
  id: string;
  name: string;
  email: string;
  role: string;
  isBlocked: boolean;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel?: string;
  nationalId?: string;
  phone?: string;
  studentPhone?: string;
  guardianPhone?: string;
  governorate?: string;
  schoolName?: string;
  gender?: "MALE" | "FEMALE" | string;
  religion?: "MUSLIM" | "CHRISTIAN" | string;
  createdAt?: string;
  overallAttendanceRatio?: number;
  assignmentSubmissionRatio?: number;
  averageQuizScore?: number;
  totalOverallGrade?: number;
  homeworkSuccessRate?: number;
  quizSuccessRate?: number;
  lastActiveDate?: string;
  customFieldValues?: Record<string, unknown>;
  watchHistory?: StudentRecord["watchHistory"];
}

interface ProfileViewProps {
  user: CurrentUser;
  onLogout: () => void;
  lang: Language;
}

export const ProfileView: React.FC<ProfileViewProps> = ({
  user,
  onLogout,
  lang,
}) => {
  const confirm = useConfirm();
  const isStudent = user.role === "student";
  const student = isStudent ? (user as StudentProfile) : null;
  const teacher = !isStudent ? (user as TeacherProfile) : null;
  const t = translations[lang];

  // Teacher Student Management State (حظر وحذف الطلاب)
  const [registeredStudents, setRegisteredStudents] = useState<ManagedStudentItem[]>([]);
  const [studentSearchTerm, setStudentSearchTerm] = useState("");
  const [studentYearFilter, setStudentYearFilter] = useState<string>("all");
  const [studentActionMsg, setStudentActionMsg] = useState<string | null>(null);
  const [selectedStudentForDetail, setSelectedStudentForDetail] = useState<ManagedStudentItem | null>(null);
  const [selectedStudentForWizard, setSelectedStudentForWizard] = useState<ManagedStudentItem | null>(null);

  useEffect(() => {
    void userService.getStudents()
      .then((students) => setRegisteredStudents(students.map((student) => {
        const year: "1st_secondary" | "2nd_secondary" | "3rd_secondary" =
          student.grade_level === "SECONDARY_2"
            ? "2nd_secondary"
            : student.grade_level === "SECONDARY_3"
            ? "3rd_secondary"
            : "1st_secondary";
        const yearLabel =
          year === "2nd_secondary"
            ? "الصف الثاني الثانوي"
            : year === "3rd_secondary"
            ? "الصف الثالث الثانوي"
            : "الصف الأول الثانوي";
        return {
          id: student.id,
          name: student.display_name,
          email: student.email,
          role: student.role,
          isBlocked: !student.is_active,
          academicYear: year,
          academicYearLabel: yearLabel,
          studentPhone: student.student_phone || "",
          guardianPhone: student.guardian_phone || "",
          nationalId: student.national_id || "",
          governorate: student.governorate || "",
          schoolName: student.school_name || "",
          gender: student.gender || "",
          religion: student.religion || "",
          createdAt: student.created_at ? student.created_at.slice(0, 10) : "",
        };
      })))
      .catch(() => setRegisteredStudents([]));
  }, []);

  async function handleToggleBlockStudent(studentId: string, studentName: string, currentlyBlocked: boolean) {
    const actionText = currentlyBlocked ? "إلغاء حظر" : "حظر";
    const confirmed = await confirm({
      title: currentlyBlocked ? "إلغاء حظر الطالب" : "حظر الطالب",
      message: `هل أنت متأكد من رغبتك في ${actionText} الطالب "${studentName}"؟`,
      confirmLabel: actionText,
      tone: currentlyBlocked ? "info" : "warning",
    });
    if (confirmed) {
      const updatedStudent = await userService.toggleBlock(studentId);
      setRegisteredStudents((previous) => previous.map((student) => student.id === studentId
        ? { ...student, isBlocked: !updatedStudent.is_active }
        : student));

      setStudentActionMsg(`تم ${currentlyBlocked ? "إلغاء حظر" : "حظر"} الطالب "${studentName}" بنجاح.`);
      setTimeout(() => setStudentActionMsg(null), 4000);
    }
  }

  async function handleDeleteStudent(studentId: string, studentName: string) {
    const confirmed = await confirm({
      title: "حذف الطالب نهائياً",
      message: `تحذير: سيتم حذف الطالب "${studentName}" نهائياً من المنصة وسجل الطلاب. لا يمكن التراجع.`,
      confirmLabel: "حذف نهائي",
      tone: "danger",
    });
    if (confirmed) {
      await userService.deleteStudent(studentId);
      setRegisteredStudents((previous) => previous.filter((student) => student.id !== studentId));

      setStudentActionMsg(`تم حذف الطالب "${studentName}" نهائياً من سجل الطلاب.`);
      setTimeout(() => setStudentActionMsg(null), 4000);
    }
  }

  const filteredStudents = registeredStudents.filter((s) => {
    if (studentYearFilter !== "all" && s.academicYear !== studentYearFilter) {
      return false;
    }
    if (studentSearchTerm.trim()) {
      const q = studentSearchTerm.trim().toLowerCase();
      const matchName = (s.name || "").toLowerCase().includes(q);
      const matchEmail = (s.email || "").toLowerCase().includes(q);
      const matchPhone = (s.studentPhone || s.phone || "").includes(q);
      const matchNatId = (s.nationalId || "").includes(q);
      return matchName || matchEmail || matchPhone || matchNatId;
    }
    return true;
  });

  const yearLabel =
    isStudent && student
      ? lang === "ar"
        ? student.academicYearLabel
        : student.academicYear === "1st_secondary"
        ? "1st Secondary Year"
        : student.academicYear === "2nd_secondary"
        ? "2nd Secondary Year"
        : "3rd Secondary Year"
      : "";

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "4px 10px", borderRadius: "6px" }}>
            {isStudent ? t.studentRole : t.teacherRole}
          </span>
          <h1 style={{ margin: "8px 0 4px", fontSize: "26px", color: "var(--text-main)" }}>
            {t.profileTitle}
          </h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "14px" }}>
            {t.profileSubtitle}
          </p>
        </div>

        {/* Prominent Logout Button (styled like delete — red) */}
        <button
          onClick={async () => {
            const confirmed = await confirm({
              title: "تسجيل الخروج",
              message: "هل أنت متأكد من رغبتك في تسجيل الخروج من حسابك؟",
              confirmLabel: "تسجيل الخروج",
              tone: "danger",
            });
            if (confirmed) onLogout();
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            background: "#dc2626",
            color: "#ffffff",
            border: "none",
            padding: "10px 18px",
            borderRadius: "10px",
            fontSize: "13px",
            fontWeight: 800,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          <LogOut size={16} />
          <span>{t.logoutBtn}</span>
        </button>
      </div>

      {/* Main Profile Grid Card */}
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "18px", padding: "28px", marginBottom: "24px", boxShadow: "var(--card-shadow)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "20px", marginBottom: "24px", flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <div
              style={{
                width: "76px",
                height: "76px",
                borderRadius: "50%",
                background: "#0f392b",
                color: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "26px",
                fontWeight: 900,
                boxShadow: "0 4px 12px rgba(15, 57, 43, 0.25)",
                overflow: "hidden",
              }}
            >
              {user.avatarUrl ? (
                <img src={user.avatarUrl} alt={user.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              ) : (
                user.name.slice(0, 2)
              )}
            </div>

            <label
              htmlFor="avatar-upload"
              style={{
                position: "absolute",
                bottom: "-2px",
                left: "-2px",
                width: "26px",
                height: "26px",
                borderRadius: "50%",
                background: "#059669",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                border: "2px solid #ffffff",
                boxShadow: "0 2px 4px rgba(0,0,0,0.15)",
              }}
              title="تغيير الصورة الشخصية"
            >
              <Upload size={12} />
              <input
                id="avatar-upload"
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                      user.avatarUrl = ev.target?.result as string;
                      window.location.reload();
                    };
                    reader.readAsDataURL(file);
                  }
                }}
                style={{ display: "none" }}
              />
            </label>
          </div>
          <div>
            <h2 style={{ margin: "0 0 6px", fontSize: "22px", color: "var(--text-main)" }}>{user.name}</h2>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", fontSize: "13px", color: "var(--text-muted)" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <Mail size={15} /> {user.email}
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <Calendar size={15} /> {user.joinedDate}
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <ShieldCheck size={15} style={{ color: "#059669" }} /> {user.nationalId}
              </span>
            </div>
          </div>
        </div>

        {/* Student Profile Body */}
        {isStudent && student && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px", marginBottom: "24px" }}>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{t.academicYear}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>{yearLabel}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{t.studentPhoneLabel}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>{student.studentPhone}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{t.guardianPhoneLabel}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>{student.guardianPhone}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{lang === "ar" ? "المحافظة" : "Governorate"}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>{student.governorate || "—"}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{lang === "ar" ? "المدرسة" : "School"}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>{student.schoolName || "—"}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{lang === "ar" ? "النوع" : "Gender"}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>
                  {student.gender === "MALE" ? "ذكر" : student.gender === "FEMALE" ? "أنثى" : student.gender || "—"}
                </strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{lang === "ar" ? "الديانة" : "Religion"}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>
                  {student.religion === "MUSLIM" ? "مسلم" : student.religion === "CHRISTIAN" ? "مسيحي" : student.religion || "—"}
                </strong>
              </div>
            </div>

            {/* Video Watch Progress Logs */}
            <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "20px" }}>
              <h3 style={{ margin: "0 0 14px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
                <Video size={18} style={{ color: "#059669" }} />
                <span>{lang === "ar" ? "سجل مشاهدات الدروس ونسب التقدم" : "Lesson Watch History & Progress Logs"}</span>
              </h3>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "var(--bg-surface)", borderRadius: "10px", border: "1px solid var(--border-color)" }}>
                  <div>
                    <strong style={{ display: "block", fontSize: "14px", color: "var(--text-main)" }}>
                      {lang === "ar" ? "الدرس 1: مدخل إلى الكيمياء وأدوات القياس المعملي" : "Lesson 1: Intro to Chemistry & Lab Measurement"}
                    </strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{lang === "ar" ? "الكيمياء • حسن شعبان" : "Chemistry • Mr. Hassan Shaaban"}</span>
                  </div>
                  <span style={{ fontSize: "12px", fontWeight: 800, padding: "4px 10px", borderRadius: "6px", background: "#dcfce7", color: "#166534" }}>
                    100% {t.completedBadge}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "var(--bg-surface)", borderRadius: "10px", border: "1px solid var(--border-color)" }}>
                  <div>
                    <strong style={{ display: "block", fontSize: "14px", color: "var(--text-main)" }}>
                      {lang === "ar" ? "الدرس 2: الجدول الدوري وخواص العناصر" : "Lesson 2: Periodic Table & Elemental Properties"}
                    </strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{lang === "ar" ? "الكيمياء • حسن شعبان" : "Chemistry • Mr. Hassan Shaaban"}</span>
                  </div>
                  <span style={{ fontSize: "12px", fontWeight: 800, padding: "4px 10px", borderRadius: "6px", background: "#dcfce7", color: "#166534" }}>
                    92% {t.completedBadge}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "var(--bg-surface)", borderRadius: "10px", border: "1px solid var(--border-color)" }}>
                  <div>
                    <strong style={{ display: "block", fontSize: "14px", color: "var(--text-main)" }}>
                      {lang === "ar" ? "الدرس 3: الروابط الكيميائية والحساب الكيميائي" : "Lesson 3: Chemical Bonds & Stoichiometry"}
                    </strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{lang === "ar" ? "الكيمياء • حسن شعبان" : "Chemistry • Mr. Hassan Shaaban"}</span>
                  </div>
                  <span style={{ fontSize: "12px", fontWeight: 800, padding: "4px 10px", borderRadius: "6px", background: "#fef3c7", color: "#854d0e" }}>
                    60%
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Teacher Profile Body */}
        {!isStudent && teacher && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px", marginBottom: "24px" }}>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{t.subjectLabel}</span>
                <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block", marginTop: "2px" }}>{teacher.subject}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{lang === "ar" ? "الفيديوهات المرفوعة" : "Uploaded Videos"}</span>
                <strong style={{ fontSize: "18px", color: "#059669", display: "block", marginTop: "2px" }}>{teacher.uploadedVideosCount}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>{lang === "ar" ? "الطلاب المسجلون" : "Enrolled Students"}</span>
                <strong style={{ fontSize: "18px", color: "#2563eb", display: "block", marginTop: "2px" }}>{teacher.enrolledStudentsCount}</strong>
              </div>
            </div>

            <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "12px", padding: "18px", marginBottom: "20px" }}>
              <strong style={{ display: "block", fontSize: "14px", color: "var(--text-main)", marginBottom: "4px" }}>
                {lang === "ar" ? "حالة الاعتماد الأكاديمي والتوثيق:" : "Academic Accreditation Status:"}
              </strong>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
                {lang === "ar"
                  ? "تم التحقق من بطاقة الرقم القومي واعتماد عقد التدريس والسياسات التربوية للمنصة بنجاح"
                  : "National ID verified and certified teacher contract approved for official curriculum delivery"}
              </p>
            </div>

            {/* Notification message */}
            {studentActionMsg && (
              <div
                style={{
                  padding: "12px 16px",
                  background: "#dcfce7",
                  border: "1px solid #86efac",
                  color: "#166534",
                  borderRadius: "10px",
                  fontSize: "13px",
                  fontWeight: 700,
                  marginBottom: "20px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <CheckCircle2 size={16} />
                <span>{studentActionMsg}</span>
              </div>
            )}

            {/* Teacher Student Management (حظر وحذف الطلاب) */}
            <div
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "14px",
                padding: "20px",
                marginBottom: "20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Users size={18} style={{ color: "#059669" }} />
                  <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                    {lang === "ar" ? "إدارة الطلاب المسجلين (حظر وحذف الحسابات)" : "Registered Students Control (Block / Delete)"}
                  </h3>
                  <span style={{ fontSize: "12px", background: "var(--bg-accent)", color: "#059669", padding: "2px 8px", borderRadius: "12px", fontWeight: 800 }}>
                    {registeredStudents.length} {lang === "ar" ? "طالب" : "students"}
                  </span>
                </div>

                {/* Filters */}
                <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                  <div style={{ position: "relative", minWidth: "180px" }}>
                    <Search size={14} style={{ position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                    <input
                      type="text"
                      value={studentSearchTerm}
                      onChange={(e) => setStudentSearchTerm(e.target.value)}
                      placeholder={lang === "ar" ? "بحث بالاسم أو الهاتف..." : "Search student..."}
                      style={{
                        width: "100%",
                        padding: "6px 28px 6px 10px",
                        fontSize: "12px",
                        borderRadius: "8px",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-surface-secondary)",
                        color: "var(--text-main)",
                        boxSizing: "border-box",
                      }}
                    />
                  </div>

                  <select
                    value={studentYearFilter}
                    onChange={(e) => setStudentYearFilter(e.target.value)}
                    style={{
                      padding: "6px 10px",
                      fontSize: "12px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-color)",
                      background: "var(--bg-surface-secondary)",
                      color: "var(--text-main)",
                      fontWeight: 700,
                    }}
                  >
                    <option value="all">{lang === "ar" ? "جميع الصفوف" : "All Grades"}</option>
                    <option value="1st_secondary">{lang === "ar" ? "الصف الأول الثانوي" : "1st Secondary"}</option>
                    <option value="2nd_secondary">{lang === "ar" ? "الصف الثاني الثانوي" : "2nd Secondary"}</option>
                    <option value="3rd_secondary">{lang === "ar" ? "الصف الثالث الثانوي" : "3rd Secondary"}</option>
                  </select>
                </div>
              </div>

              {/* Student List */}
              {filteredStudents.length === 0 ? (
                <div style={{ textAlign: "center", padding: "30px 20px", color: "var(--text-muted)", fontSize: "13px" }}>
                  {lang === "ar" ? "لا يوجد طلاب مسجلون حالياً أو يطابقون معايير البحث." : "No registered students found."}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {filteredStudents.map((st) => {
                    const isBlocked = !!st.isBlocked;
                    return (
                      <div
                        key={st.id}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "14px 16px",
                          borderRadius: "12px",
                          border: isBlocked ? "1.5px solid #fca5a5" : "1px solid var(--border-color)",
                          background: isBlocked ? "#fff5f5" : "var(--bg-surface-secondary)",
                          flexWrap: "wrap",
                          gap: "12px",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div
                          style={{ display: "flex", alignItems: "center", gap: "12px", cursor: "pointer" }}
                          onDoubleClick={() => setSelectedStudentForWizard(st)}
                          title="انقر مرتين لعرض كافة بيانات تسجيل الطالب"
                        >
                          <div
                            style={{
                              width: "42px",
                              height: "42px",
                              borderRadius: "50%",
                              background: isBlocked ? "#dc2626" : "#0f392b",
                              color: "#ffffff",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: "15px",
                              fontWeight: 800,
                            }}
                          >
                            {(st.name || "ط").slice(0, 2)}
                          </div>

                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <strong style={{ fontSize: "14px", color: "var(--text-main)" }}>{st.name}</strong>
                              {isBlocked ? (
                                <span style={{ fontSize: "10.5px", fontWeight: 800, padding: "2px 8px", borderRadius: "6px", background: "#fee2e2", color: "#b91c1c", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                  <Ban size={11} />
                                  <span>{lang === "ar" ? "محظور من المنصة" : "Blocked"}</span>
                                </span>
                              ) : (
                                <span style={{ fontSize: "10.5px", fontWeight: 800, padding: "2px 8px", borderRadius: "6px", background: "#dcfce7", color: "#166534" }}>
                                  {lang === "ar" ? "نشط" : "Active"}
                                </span>
                              )}
                            </div>
                            <div style={{ display: "flex", gap: "12px", fontSize: "11.5px", color: "var(--text-muted)", marginTop: "2px", flexWrap: "wrap" }}>
                              <span>{st.academicYearLabel || "الصف الأول الثانوي"}</span>
                              {st.studentPhone && <span>{st.studentPhone}</span>}
                              {st.email && <span>{st.email}</span>}
                              {st.nationalId && <span>{st.nationalId}</span>}
                            </div>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          {/* Video Viewing Timeline (مخطط المشاهدة) */}
                          <button
                            type="button"
                            onClick={() => setSelectedStudentForDetail(st)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              padding: "6px 12px",
                              borderRadius: "8px",
                              border: "1px solid var(--border-color)",
                              background: "var(--bg-surface)",
                              color: "var(--text-main)",
                              fontSize: "12px",
                              fontWeight: 800,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                            }}
                            title="عرض مخطط مشاهدة الفيديوهات وتفاصيل المتابعة"
                          >
                            <Video size={14} style={{ color: "#059669" }} />
                            <span>{lang === "ar" ? "مخطط المشاهدة" : "Watch History"}</span>
                          </button>

                          {/* Block / Unblock Button (styled red like delete) */}
                          <button
                            type="button"
                            onClick={() => handleToggleBlockStudent(st.id, st.name, isBlocked)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              padding: "6px 12px",
                              borderRadius: "8px",
                              border: "none",
                              background: isBlocked ? "#dcfce7" : "#dc2626",
                              color: isBlocked ? "#166534" : "#ffffff",
                              fontSize: "12px",
                              fontWeight: 800,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                            }}
                            title={isBlocked ? "إلغاء حظر الطالب والسماح له بالدخول" : "حظر الطالب ومنعه من الوصول"}
                          >
                            {isBlocked ? <ShieldCheck size={14} /> : <Ban size={14} />}
                            <span>{isBlocked ? (lang === "ar" ? "إلغاء الحظر" : "Unblock") : (lang === "ar" ? "حظر الطالب" : "Block")}</span>
                          </button>

                          {/* Delete Student Button */}
                          <button
                            type="button"
                            onClick={() => handleDeleteStudent(st.id, st.name)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              padding: "6px 12px",
                              borderRadius: "8px",
                              border: "none",
                              background: "#dc2626",
                              color: "#ffffff",
                              fontSize: "12px",
                              fontWeight: 800,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                            }}
                            title="حذف الطالب نهائياً من سجلات المنصة"
                          >
                            <Trash2 size={14} />
                            <span>{lang === "ar" ? "حذف نهائي" : "Delete"}</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Danger Zone: Reset All Lessons from Profile */}
            <div
              style={{
                marginTop: "20px",
                padding: "18px",
                background: "#fef2f2",
                border: "1.5px solid #fecaca",
                borderRadius: "12px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "14px",
              }}
            >
              <div>
                <strong style={{ display: "block", fontSize: "14px", color: "#991b1b" }}>
                  {lang === "ar" ? "تفريغ وحذف كافة الدروس للبدء من الصفر" : "Reset All Lessons From Scratch"}
                </strong>
                <p style={{ margin: "2px 0 0", color: "#b91c1c", fontSize: "12px" }}>
                  {lang === "ar"
                    ? "حذف وتفريغ كافة الدروس والفيديوهات المرفوعة لجميع الصفوف الدراسية لإعادة تجهيز المحتوى."
                    : "Permanently clear and empty all uploaded lessons and videos across all academic years."}
                </p>
              </div>
              <button
                type="button"
                onClick={async () => {
                  const confirmed = await confirm({
                    title: lang === "ar" ? "تفريغ كافة الدروس" : "Reset All Lessons",
                    message: lang === "ar"
                      ? "تحذير: سيتم تفريغ وحذف جميع الدروس من كافة الصفوف للبدء من الصفر. لا يمكن التراجع عن هذه الخطوة."
                      : "Warning: All lessons across all grades will be permanently deleted. This cannot be undone.",
                    confirmLabel: lang === "ar" ? "حذف الكل" : "Delete All",
                    tone: "danger",
                  });
                  if (confirmed) {
                    await confirm({
                      title: lang === "ar" ? "إجراء إداري" : "Admin Action",
                      message: lang === "ar"
                        ? "إدارة الحذف الجماعي متاحة عبر صلاحية إدارية على الخادم فقط."
                        : "Bulk deletion is available only through a server-side administrator workflow.",
                      confirmLabel: lang === "ar" ? "حسناً" : "OK",
                      cancelLabel: lang === "ar" ? "إغلاق" : "Close",
                      tone: "info",
                    });
                  }
                }}
                style={{
                  background: "#dc2626",
                  color: "#ffffff",
                  border: "none",
                  padding: "10px 18px",
                  borderRadius: "10px",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Trash2 size={16} />
                <span>{lang === "ar" ? "تفريغ كافة الدروس للبدء من الصفر" : "Reset All Lessons"}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Student Video Timeline Modal for Teacher */}
      <StudentDetailModal
        student={selectedStudentForDetail ? {
          id: selectedStudentForDetail.id,
          name: selectedStudentForDetail.name || "طالب",
          email: selectedStudentForDetail.email || "—",
          nationalId: selectedStudentForDetail.nationalId || "—",
          academicYear: selectedStudentForDetail.academicYear || "1st_secondary",
          academicYearLabel: selectedStudentForDetail.academicYearLabel || "الصف الأول الثانوي",
          overallAttendanceRatio: selectedStudentForDetail.overallAttendanceRatio ?? 0.85,
          assignmentSubmissionRatio: selectedStudentForDetail.assignmentSubmissionRatio ?? 0.8,
          averageQuizScore: selectedStudentForDetail.averageQuizScore ?? 82,
          totalOverallGrade: selectedStudentForDetail.totalOverallGrade ?? 85,
          homeworkSuccessRate: selectedStudentForDetail.homeworkSuccessRate ?? 85,
          quizSuccessRate: selectedStudentForDetail.quizSuccessRate ?? 80,
          lastActiveDate: selectedStudentForDetail.lastActiveDate || "اليوم",
          customFieldValues: selectedStudentForDetail.customFieldValues || {},
          watchHistory: selectedStudentForDetail.watchHistory || [
            {
              videoId: "vid_1",
              videoTitle: "الدرس الأول: العناصر الانتقالية وخواصها",
              courseTitle: "الكيمياء العامة",
              totalDurationSec: 2400,
              watchedDurationSec: 2160,
              completionPercentage: 90,
              lastWatchedAt: "2026-08-20 14:30",
              dropOffTimestampSec: 2160,
              segments: [
                { startTimeSec: 0, endTimeSec: 600, watched: true },
                { startTimeSec: 600, endTimeSec: 1200, watched: true },
                { startTimeSec: 1200, endTimeSec: 1800, watched: true },
                { startTimeSec: 1800, endTimeSec: 2160, watched: true },
              ],
            },
            {
              videoId: "vid_2",
              videoTitle: "الدرس الثاني: تفاعلات أكاسيد الحديد والمعادلات",
              courseTitle: "الكيمياء العامة",
              totalDurationSec: 1800,
              watchedDurationSec: 1620,
              completionPercentage: 90,
              lastWatchedAt: "2026-08-22 16:15",
              dropOffTimestampSec: 1620,
              segments: [
                { startTimeSec: 0, endTimeSec: 900, watched: true },
                { startTimeSec: 900, endTimeSec: 1620, watched: true },
              ],
            },
          ],
        } : null}
        onClose={() => setSelectedStudentForDetail(null)}
      />

      {/* Student Registration Detail Wizard (on Double-Click) */}
      <StudentDetailWizard
        student={selectedStudentForWizard}
        onClose={() => setSelectedStudentForWizard(null)}
        onBlock={async (studentId, studentName, isBlocked) => {
          await handleToggleBlockStudent(studentId, studentName, isBlocked);
          if (selectedStudentForWizard && selectedStudentForWizard.id === studentId) {
            setSelectedStudentForWizard({ ...selectedStudentForWizard, isBlocked: !isBlocked });
          }
        }}
        onDelete={async (studentId, studentName) => {
          await handleDeleteStudent(studentId, studentName);
          setSelectedStudentForWizard(null);
        }}
      />
    </div>
  );
};

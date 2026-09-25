import React, { useState } from "react";
import {
  GraduationCap,
  Upload,
  Users,
  X,
} from "lucide-react";
import { CurrentUser, StudentProfile, TeacherProfile, UserRole } from "../types/lms";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: CurrentUser) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [authTab, setAuthTab] = useState<"signin" | "register">("signin");
  const [selectedRole, setSelectedRole] = useState<UserRole>("student");

  // Sign In Form State
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");

  // Student Register Form State
  const [stdName, setStdName] = useState("");
  const [stdEmail, setStdEmail] = useState("");
  const [stdPassword, setStdPassword] = useState("");
  const [stdNationalId, setStdNationalId] = useState("");
  const [stdIdFile, setStdIdFile] = useState<string | null>(null);
  const [stdPhone, setStdPhone] = useState("");
  const [guardianPhone, setGuardianPhone] = useState("");
  const [stdAge, setStdAge] = useState(16);
  const [stdYear, setStdYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">("1st_secondary");
  const [stdSubjects] = useState<string[]>(["الكيمياء"]);

  // Teacher Register Form State
  const [tchName, setTchName] = useState("");
  const [tchEmail, setTchEmail] = useState("");
  const [tchPassword, setTchPassword] = useState("");
  const [tchNationalId, setTchNationalId] = useState("");
  const [tchIdFile, setTchIdFile] = useState<string | null>(null);
  const [tchPhone, setTchPhone] = useState("");
  const [tchYear, setTchYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary" | "all">("1st_secondary");
  const [tchSubject, setTchSubject] = useState("الكيمياء");
  const [contractAgreed, setContractAgreed] = useState(false);

  if (!isOpen) return null;

  function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    if (selectedRole === "student") {
      const studentUser: StudentProfile = {
        id: `std_${Date.now()}`,
        name: "عمر زيدان عبد الرحمن",
        email: signInEmail || "omar.zidan@student.lms.edu.eg",
        role: "student",
        nationalId: "30608150104892",
        studentPhone: "01092837461",
        guardianPhone: "01183746291",
        age: 16,
        academicYear: "1st_secondary",
        academicYearLabel: "الصف الأول الثانوي",
        interestedSubjects: ["الكيمياء"],
        joinedDate: "2026-08-23",
      };
      onLoginSuccess(studentUser);
    } else {
      const teacherUser: TeacherProfile = {
        id: `tch_${Date.now()}`,
        name: "حسن شعبان",
        email: signInEmail || "hassan.shaaban@teacher.lms.edu.eg",
        role: "teacher",
        nationalId: "28403120105938",
        phone: "01284729104",
        teachingYear: "all",
        teachingYearLabel: "جميع الصفوف الثانوية",
        subject: "الكيمياء",
        contractAgreed: true,
        contractAgreedAt: "2026-08-23",
        uploadedVideosCount: 24,
        enrolledStudentsCount: 148,
        joinedDate: "2026-08-23",
      };
      onLoginSuccess(teacherUser);
    }
    onClose();
  }

  function handleRegisterStudent(e: React.FormEvent) {
    e.preventDefault();
    const yearLabels = {
      "1st_secondary": "الصف الأول الثانوي",
      "2nd_secondary": "الصف الثاني الثانوي",
      "3rd_secondary": "الصف الثالث الثانوي",
    };

    const newStudent: StudentProfile = {
      id: `std_${Date.now()}`,
      name: stdName || "طالب جديد",
      email: stdEmail || "student@lms.edu.eg",
      role: "student",
      nationalId: stdNationalId || "30601010109999",
      nationalIdPhotoUrl: stdIdFile || undefined,
      studentPhone: stdPhone || "01000000000",
      guardianPhone: guardianPhone || "01100000000",
      age: stdAge,
      academicYear: stdYear,
      academicYearLabel: yearLabels[stdYear],
      interestedSubjects: stdSubjects,
      joinedDate: new Date().toISOString().split("T")[0],
    };
    onLoginSuccess(newStudent);
    onClose();
  }

  function handleRegisterTeacher(e: React.FormEvent) {
    e.preventDefault();
    if (!contractAgreed) {
      return;
    }

    const yearLabels = {
      "1st_secondary": "الصف الأول الثانوي",
      "2nd_secondary": "الصف الثاني الثانوي",
      "3rd_secondary": "الصف الثالث الثانوي",
      all: "جميع الصفوف الثانوية",
    };

    const newTeacher: TeacherProfile = {
      id: `tch_${Date.now()}`,
      name: tchName || "أ. معلم جديد",
      email: tchEmail || "teacher@lms.edu.eg",
      role: "teacher",
      nationalId: tchNationalId || "28501010109999",
      nationalIdPhotoUrl: tchIdFile || undefined,
      phone: tchPhone || "01200000000",
      teachingYear: tchYear,
      teachingYearLabel: yearLabels[tchYear],
      subject: tchSubject,
      contractAgreed: true,
      contractAgreedAt: new Date().toISOString(),
      uploadedVideosCount: 0,
      enrolledStudentsCount: 0,
      joinedDate: new Date().toISOString().split("T")[0],
    };
    onLoginSuccess(newTeacher);
    onClose();
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: "600px", padding: "28px" }}>
        {/* Modal Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", borderBottom: "1px solid #e2e8f0", paddingBottom: "14px" }}>
          <div>
            <h2 style={{ margin: "0 0 4px", fontSize: "20px", color: "#0f172a" }}>بوابة الدخول والتسجيل</h2>
            <p style={{ margin: 0, fontSize: "13px", color: "#64748b" }}>
              اختر دورك وسجل دخولك لمتابعة دروسك أو إدارة فصولك
            </p>
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

        {/* Role Selector */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "20px" }}>
          <button
            onClick={() => setSelectedRole("student")}
            style={{
              padding: "12px",
              borderRadius: "10px",
              border: selectedRole === "student" ? "2px solid #0f392b" : "1px solid #e2e8f0",
              background: selectedRole === "student" ? "#ecfdf5" : "#ffffff",
              color: selectedRole === "student" ? "#0f392b" : "#475569",
              fontWeight: 800,
              fontSize: "13px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
            }}
          >
            <GraduationCap size={18} />
            <span>حساب طالب</span>
          </button>

          <button
            onClick={() => setSelectedRole("teacher")}
            style={{
              padding: "12px",
              borderRadius: "10px",
              border: selectedRole === "teacher" ? "2px solid #0f392b" : "1px solid #e2e8f0",
              background: selectedRole === "teacher" ? "#ecfdf5" : "#ffffff",
              color: selectedRole === "teacher" ? "#0f392b" : "#475569",
              fontWeight: 800,
              fontSize: "13px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
            }}
          >
            <Users size={18} />
            <span>حساب معلم</span>
          </button>
        </div>

        {/* Auth Tabs */}
        <div style={{ display: "flex", borderBottom: "1px solid #e2e8f0", marginBottom: "20px" }}>
          <button
            onClick={() => setAuthTab("signin")}
            style={{
              flex: 1,
              padding: "10px",
              background: "none",
              border: "none",
              borderBottom: authTab === "signin" ? "2.5px solid #0f392b" : "none",
              color: authTab === "signin" ? "#0f392b" : "#64748b",
              fontWeight: 800,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            تسجيل الدخول
          </button>
          <button
            onClick={() => setAuthTab("register")}
            style={{
              flex: 1,
              padding: "10px",
              background: "none",
              border: "none",
              borderBottom: authTab === "register" ? "2.5px solid #0f392b" : "none",
              color: authTab === "register" ? "#0f392b" : "#64748b",
              fontWeight: 800,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            إنشاء حساب جديد
          </button>
        </div>

        {/* Tab 1: Sign In */}
        {authTab === "signin" && (
          <form onSubmit={handleSignIn} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                البريد الإلكتروني:
              </label>
              <input
                type="email"
                required
                value={signInEmail}
                onChange={(e) => setSignInEmail(e.target.value)}
                placeholder="example@lms.edu.eg"
                style={{ width: "100%", padding: "10px 14px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "13px" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                كلمة المرور:
              </label>
              <input
                type="password"
                required
                value={signInPassword}
                onChange={(e) => setSignInPassword(e.target.value)}
                placeholder="••••••••"
                style={{ width: "100%", padding: "10px 14px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "13px" }}
              />
            </div>

            <button type="submit" className="btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px", marginTop: "10px" }}>
              دخول الحساب
            </button>
          </form>
        )}

        {/* Tab 2: Register Student */}
        {authTab === "register" && selectedRole === "student" && (
          <form onSubmit={handleRegisterStudent} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>اسم الطالب رباعي:</label>
                <input
                  type="text"
                  required
                  value={stdName}
                  onChange={(e) => setStdName(e.target.value.replace(/[^a-zA-Z\u0600-\u06FF\s]/g, ""))}
                  placeholder="عمر زيدان عبد الرحمن"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>الرقم القومي (14 رقم فقط):</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={14}
                  required
                  value={stdNationalId}
                  onChange={(e) => setStdNationalId(e.target.value.replace(/\D/g, "").slice(0, 14))}
                  placeholder="30608150104892"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
            </div>

            {/* ID Card Photo Upload */}
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>صورة البطاقة الشخصية للتحقق:</label>
              <div style={{ border: "1px dashed #cbd5e1", padding: "10px", borderRadius: "8px", textAlign: "center", background: "#f8fafc" }}>
                <Upload size={18} style={{ color: "#64748b", margin: "0 auto 4px" }} />
                <span style={{ fontSize: "11px", color: "#475569" }}>
                  {stdIdFile ? "تم اختيار الصورة بنجاح" : "اضغط لرفع صورة بطاقة الرقم القومي"}
                </span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={() => setStdIdFile("uploaded_id.png")}
                  style={{ display: "block", opacity: 0, height: "1px" }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>رقم موبايل الطالب:</label>
                <input
                  type="tel"
                  inputMode="numeric"
                  maxLength={11}
                  required
                  value={stdPhone}
                  onChange={(e) => setStdPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
                  placeholder="01092837461"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>رقم موبايل ولي الأمر:</label>
                <input
                  type="tel"
                  inputMode="numeric"
                  maxLength={11}
                  required
                  value={guardianPhone}
                  onChange={(e) => setGuardianPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
                  placeholder="01183746291"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>السن:</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={2}
                  value={stdAge}
                  onChange={(e) => setStdAge(parseInt(e.target.value.replace(/\D/g, "").slice(0, 2)) || 0)}
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>السنة الدراسية:</label>
                <select
                  value={stdYear}
                  onChange={(e) => setStdYear(e.target.value as "1st_secondary" | "2nd_secondary" | "3rd_secondary")}
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px", background: "white" }}
                >
                  <option value="1st_secondary">الصف الأول الثانوي</option>
                  <option value="2nd_secondary">الصف الثاني الثانوي</option>
                  <option value="3rd_secondary">الصف الثالث الثانوي</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>البريد الإلكتروني:</label>
                <input
                  type="email"
                  required
                  value={stdEmail}
                  onChange={(e) => setStdEmail(e.target.value)}
                  placeholder="omar@example.com"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>كلمة المرور:</label>
                <input
                  type="password"
                  required
                  value={stdPassword}
                  onChange={(e) => setStdPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
            </div>

            <button type="submit" className="btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px", marginTop: "10px" }}>
              إتمام تسجيل حساب الطالب
            </button>
          </form>
        )}

        {/* Tab 2: Register Teacher */}
        {authTab === "register" && selectedRole === "teacher" && (
          <form onSubmit={handleRegisterTeacher} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>اسم المعلم ثلاثي/رباعي:</label>
                <input
                  type="text"
                  required
                  value={tchName}
                  onChange={(e) => setTchName(e.target.value.replace(/[^a-zA-Z\u0600-\u06FF\s]/g, ""))}
                  placeholder="اسم المعلم"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>الرقم القومي للتحقق (14 رقم فقط):</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={14}
                  required
                  value={tchNationalId}
                  onChange={(e) => setTchNationalId(e.target.value.replace(/\D/g, "").slice(0, 14))}
                  placeholder="28403120105938"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
            </div>

            {/* Teacher ID Photo Upload */}
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>صورة بطاقة الرقم القومي - للتحقق والاعتماد:</label>
              <div style={{ border: "1px dashed #cbd5e1", padding: "10px", borderRadius: "8px", textAlign: "center", background: "#f8fafc" }}>
                <Upload size={18} style={{ color: "#64748b", margin: "0 auto 4px" }} />
                <span style={{ fontSize: "11px", color: "#475569" }}>
                  {tchIdFile ? "تم اختيار صورة بطاقة المعلم بنجاح" : "اضغط لرفع صورة البطاقة الشخصية"}
                </span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={() => setTchIdFile("teacher_id.png")}
                  style={{ display: "block", opacity: 0, height: "1px" }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>رقم الموبايل:</label>
                <input
                  type="tel"
                  inputMode="numeric"
                  maxLength={11}
                  required
                  value={tchPhone}
                  onChange={(e) => setTchPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
                  placeholder="01284729104"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>المادة العلمية:</label>
                <input
                  type="text"
                  required
                  value={tchSubject}
                  onChange={(e) => setTchSubject(e.target.value.replace(/[^a-zA-Z\u0600-\u06FF\s/]/g, ""))}
                  placeholder="اسم المادة الدراسية"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>السنة الدراسية التي تدرسها:</label>
              <select
                value={tchYear}
                onChange={(e) => setTchYear(e.target.value as "1st_secondary" | "2nd_secondary" | "3rd_secondary" | "all")}
                style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px", background: "white" }}
              >
                <option value="1st_secondary">الصف الأول الثانوي</option>
                <option value="2nd_secondary">الصف الثاني الثانوي</option>
                <option value="3rd_secondary">الصف الثالث الثانوي</option>
                <option value="all">جميع الصفوف الثانوية</option>
              </select>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>البريد الإلكتروني:</label>
                <input
                  type="email"
                  required
                  value={tchEmail}
                  onChange={(e) => setTchEmail(e.target.value)}
                  placeholder="teacher@lms.edu.eg"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>كلمة المرور:</label>
                <input
                  type="password"
                  required
                  value={tchPassword}
                  onChange={(e) => setTchPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                />
              </div>
            </div>

            {/* Official Teacher Contract Agreement Box (Requirement 13) */}
            <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "12px", maxHeight: "120px", overflowY: "auto", fontSize: "11px", lineHeight: "1.6", color: "#334155" }}>
              <strong style={{ display: "block", color: "#0f392b", marginBottom: "4px" }}>
                وثيقة اتفاقية وشروط التدريس المعتمدة عبر المنصة:
              </strong>
              1. يلتزم المعلم بتقديم محتوى علمي وتربوي مطابق لمناهج وزارة التربية والتعليم الرسمية.
              <br />
              2. يلتزم المعلم بالحفاظ على سرية بيانات الطلاب ودرجاتهم وعدم مشاركتها خارج النطاق التعليمي.
              <br />
              3. تخضع كافة الاختبارات والمواد المرفوعة لسياسات الأمانة الأكاديمية والملكية الفكرية للمنصة.
              <br />
              4. يحق للمعلم اعتماد وتعديل نتائج تصحيح الذكاء الاصطناعي بما يضمن العدالة التامة لكل طالب.
            </div>

            <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", fontWeight: 700, color: "#0f172a", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={contractAgreed}
                onChange={(e) => setContractAgreed(e.target.checked)}
                style={{ width: "16px", height: "16px", accentColor: "#0f392b" }}
              />
              <span>تم القراءة والموافقة على بنود عقد التدريس والسياسات التربوية</span>
            </label>

            <button
              type="submit"
              disabled={!contractAgreed}
              className="btn-primary"
              style={{ width: "100%", justifyContent: "center", padding: "12px", marginTop: "6px", opacity: contractAgreed ? 1 : 0.6 }}
            >
              إتمام تسجيل المعلم والاعتماد
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

import React from "react";
import {
  ShieldCheck,
  Users,
  Video,
  X,
} from "lucide-react";
import { CurrentUser, StudentProfile, TeacherProfile } from "../types/lms";
import { useConfirm } from "./ConfirmWizard";

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: CurrentUser;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({
  isOpen,
  onClose,
  user,
}) => {
  const confirm = useConfirm();
  if (!isOpen) return null;

  const isStudent = user.role === "student";
  const student = isStudent ? (user as StudentProfile) : null;
  const teacher = !isStudent ? (user as TeacherProfile) : null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: "620px", padding: "26px" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px", borderBottom: "1px solid #e2e8f0", paddingBottom: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div
              style={{
                width: "52px",
                height: "52px",
                borderRadius: "50%",
                background: isStudent ? "#d97706" : "#0f392b",
                color: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "20px",
                fontWeight: 900,
              }}
            >
              {user.name.slice(0, 2)}
            </div>
            <div>
              <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent)", padding: "2px 8px", borderRadius: "6px" }}>
                {isStudent ? "الملف التعريفي للطالب" : "الملف التعريفي للمعلم المعتمد"}
              </span>
              <h2 style={{ margin: "4px 0 2px", fontSize: "18px", color: "var(--text-main)" }}>{user.name}</h2>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{user.email}</span>
            </div>
          </div>

          <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
            <X size={20} />
          </button>
        </div>

        {/* Core Info Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "20px" }}>
          <div style={{ background: "var(--bg-surface-secondary)", padding: "10px 14px", borderRadius: "8px", border: "1px solid var(--border-color)", fontSize: "12px" }}>
            <span style={{ color: "var(--text-muted)", display: "block" }}>الرقم القومي:</span>
            <strong style={{ color: "var(--text-main)" }}>{user.nationalId}</strong>
          </div>
          <div style={{ background: "var(--bg-surface-secondary)", padding: "10px 14px", borderRadius: "8px", border: "1px solid var(--border-color)", fontSize: "12px" }}>
            <span style={{ color: "var(--text-muted)", display: "block" }}>تاريخ الانضمام:</span>
            <strong style={{ color: "var(--text-main)" }}>{user.joinedDate}</strong>
          </div>
        </div>

        {/* Student Specific Profile (Requirement 12) */}
        {isStudent && student && (
          <div>
            <h3 style={{ margin: "0 0 10px", fontSize: "14px", fontWeight: 800, color: "var(--text-main)" }}>
              بيانات الدراسة والتقدم
            </h3>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px", marginBottom: "16px" }}>
              <div style={{ background: "var(--bg-accent)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>السنة الدراسية</span>
                <strong style={{ fontSize: "13px", color: "var(--text-main)" }}>{student.academicYearLabel}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>موبايل الطالب</span>
                <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>{student.studentPhone}</strong>
              </div>
              <div style={{ background: "var(--bg-surface-secondary)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>موبايل ولي الأمر</span>
                <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>{student.guardianPhone}</strong>
              </div>
            </div>

            <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "14px", marginBottom: "16px" }}>
              <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main)", marginBottom: "6px" }}>
                سجل الفيديوهات والدروس المسجلة:
              </strong>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)", textAlign: "center", padding: "8px 0" }}>
                  يتم تحديث سجل المشاهدات والتفاعل تلقائياً عند فتح ومشاهدة الدروس.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Teacher Specific Profile (Requirement 12) */}
        {!isStudent && teacher && (
          <div>
            <h3 style={{ margin: "0 0 10px", fontSize: "14px", fontWeight: 800, color: "var(--text-main)" }}>
              إحصائيات التدريس والمحتوى
            </h3>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px", marginBottom: "16px" }}>
              <div style={{ background: "var(--bg-accent)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                <Video size={18} style={{ color: "#059669", margin: "0 auto 4px" }} />
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>الفيديوهات المرفوعة</span>
                <strong style={{ fontSize: "18px", color: "var(--text-main)" }}>{teacher.uploadedVideosCount} فيديو</strong>
              </div>
              <div style={{ background: "var(--bg-accent)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                <Users size={18} style={{ color: "#059669", margin: "0 auto 4px" }} />
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>الطلاب المسجلون</span>
                <strong style={{ fontSize: "18px", color: "var(--text-main)" }}>{teacher.enrolledStudentsCount} طالب</strong>
              </div>
              <div style={{ background: "var(--bg-accent)", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                <ShieldCheck size={18} style={{ color: "#059669", margin: "0 auto 4px" }} />
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>حالة العقد</span>
                <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>معتمد وموثق</strong>
              </div>
            </div>

            <div style={{ background: "var(--bg-surface-secondary)", padding: "12px 14px", borderRadius: "8px", border: "1px solid var(--border-color)", fontSize: "12px" }}>
              <strong style={{ display: "block", color: "var(--text-main)", marginBottom: "4px" }}>المادة وسنوات التدريس:</strong>
              <p style={{ margin: 0, color: "var(--text-muted)" }}>
                المادة: <strong>{teacher.subject}</strong> | الفصول: <strong>{teacher.teachingYearLabel}</strong>
              </p>
            </div>

            {/* Danger Zone: Reset All Lessons */}
            <div
              style={{
                marginTop: "16px",
                padding: "14px",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "10px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div>
                <strong style={{ display: "block", fontSize: "12.5px", color: "#991b1b" }}>
                  تفريغ كافة الدروس للبدء من الصفر
                </strong>
                <small style={{ color: "#b91c1c", fontSize: "11px" }}>
                  حذف كافة الفيديوهات والمذكرات المرفوعة من جميع الفصول والمراحل.
                </small>
              </div>
              <button
                type="button"
                onClick={async () => {
                  const confirmed = await confirm({
                    title: "حذف جماعي للدروس",
                    message: "تحذير أخير: سيتم حذف وتفريغ كافة الدروس من جميع الفصول للبدء من الصفر. لا يمكن التراجع.",
                    confirmLabel: "حذف الكل",
                    tone: "danger",
                  });
                  if (confirmed) {
                    await confirm({
                      title: "إجراء إداري",
                      message: "إدارة الحذف الجماعي متاحة عبر صلاحية إدارية على الخادم فقط.",
                      confirmLabel: "حسناً",
                      cancelLabel: "إغلاق",
                      tone: "info",
                    });
                  }
                }}
                style={{
                  background: "#dc2626",
                  color: "#ffffff",
                  border: "none",
                  padding: "6px 12px",
                  borderRadius: "8px",
                  fontSize: "11.5px",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                تفريغ كافة الدروس
              </button>
            </div>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
          <button className="btn-secondary" onClick={onClose}>
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
};

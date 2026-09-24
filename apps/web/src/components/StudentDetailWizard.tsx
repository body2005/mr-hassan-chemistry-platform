import React from "react";
import {
  Ban,
  BookOpen,
  Calendar,
  GraduationCap,
  Mail,
  MapPin,
  Phone,
  ShieldCheck,
  Trash2,
  User,
  X,
} from "lucide-react";
import { StudentRecord } from "../types/lms";
import { ManagedStudentItem } from "../views/ProfileView";

type StudentLike = StudentRecord | ManagedStudentItem | null;

interface StudentDetailWizardProps {
  student: StudentLike;
  onClose: () => void;
  onBlock: ((studentId: string, studentName: string, isBlocked: boolean) => void) | null;
  onDelete: ((studentId: string, studentName: string) => void) | null;
}

function getGenderLabel(g?: string): string {
  if (!g || g === "—") return "—";
  if (g === "MALE") return "ذكر";
  if (g === "FEMALE") return "أنثى";
  return g;
}

function getReligionLabel(r?: string): string {
  if (!r || r === "—") return "—";
  if (r === "MUSLIM") return "مسلم";
  if (r === "CHRISTIAN") return "مسيحي";
  return r;
}

function getAcademicYearLabel(year?: string): string {
  if (year === "2nd_secondary") return "الصف الثاني الثانوي";
  if (year === "3rd_secondary") return "الصف الثالث الثانوي";
  return "الصف الأول الثانوي";
}

const fieldCardStyle: React.CSSProperties = {
  background: "var(--bg-surface-secondary)",
  padding: "12px 14px",
  borderRadius: "10px",
  border: "1px solid var(--border-color)",
};

const fieldLabelStyle: React.CSSProperties = {
  fontSize: "11px",
  color: "var(--text-muted)",
  display: "flex",
  alignItems: "center",
  gap: "5px",
  marginBottom: "4px",
};

const fieldValueStyle: React.CSSProperties = {
  fontSize: "14px",
  fontWeight: 700,
  color: "var(--text-main)",
  wordBreak: "break-word",
};

export const StudentDetailWizard: React.FC<StudentDetailWizardProps> = ({
  student,
  onClose,
  onBlock,
  onDelete,
}) => {
  if (!student) return null;

  const s = student;
  const isBlocked = !!s.isBlocked;
  const yearLabel = ("academicYearLabel" in s && s.academicYearLabel) || getAcademicYearLabel(s.academicYear);

  return (
    <div className="modal-overlay">
      <div
        className="modal-content"
        style={{
          maxWidth: "620px",
          padding: "0",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-color)",
          borderRadius: "18px",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            background: "#0f392b",
            color: "#ffffff",
            padding: "20px 24px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  background: isBlocked ? "#dc2626" : "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "16px",
                  fontWeight: 800,
                }}
              >
                {(s.name || "ط").slice(0, 2)}
              </div>
              <div>
                <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800 }}>{s.name}</h2>
                <span style={{ fontSize: "12px", opacity: 0.8 }}>{s.email}</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", marginTop: "6px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 800,
                  padding: "2px 8px",
                  borderRadius: "6px",
                  background: isBlocked ? "#fee2e2" : "rgba(255,255,255,0.15)",
                  color: isBlocked ? "#b91c1c" : "#ffffff",
                }}
              >
                {isBlocked ? "محظور من المنصة" : "نشط"}
              </span>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: "6px",
                  background: "rgba(255,255,255,0.15)",
                  color: "#ffffff",
                }}
              >
                {yearLabel}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.15)",
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

        {/* Body — registration data */}
        <div style={{ padding: "20px 24px" }}>
          <h3
            style={{
              margin: "0 0 14px",
              fontSize: "14px",
              fontWeight: 800,
              color: "var(--text-main)",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <User size={16} style={{ color: "#059669" }} />
            <span>بيانات التسجيل الكاملة</span>
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
            {/* Name */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <User size={13} /> الاسم الكامل
              </div>
              <div style={fieldValueStyle}>{s.name}</div>
            </div>

            {/* Email */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <Mail size={13} /> البريد الإلكتروني
              </div>
              <div style={fieldValueStyle}>{s.email}</div>
            </div>

            {/* National ID */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <ShieldCheck size={13} /> الرقم القومي
              </div>
              <div style={fieldValueStyle}>{s.nationalId || "—"}</div>
            </div>

            {/* Student Phone */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <Phone size={13} /> هاتف الطالب
              </div>
              <div style={{ ...fieldValueStyle, fontFamily: "monospace", direction: "ltr", textAlign: "right" }}>
                {("studentPhone" in s ? s.studentPhone : (s as any).phone) || "—"}
              </div>
            </div>

            {/* Guardian Phone */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <Phone size={13} /> هاتف ولي الأمر
              </div>
              <div style={{ ...fieldValueStyle, fontFamily: "monospace", direction: "ltr", textAlign: "right" }}>
                {s.guardianPhone || "—"}
              </div>
            </div>

            {/* Academic Year */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <GraduationCap size={13} /> السنة الدراسية
              </div>
              <div style={fieldValueStyle}>{yearLabel}</div>
            </div>

            {/* Governorate */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <MapPin size={13} /> المحافظة
              </div>
              <div style={fieldValueStyle}>{("governorate" in s ? (s as any).governorate : undefined) || "—"}</div>
            </div>

            {/* School */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <BookOpen size={13} /> المدرسة
              </div>
              <div style={fieldValueStyle}>{("schoolName" in s ? (s as any).schoolName : undefined) || "—"}</div>
            </div>

            {/* Gender */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <User size={13} /> النوع
              </div>
              <div style={fieldValueStyle}>{getGenderLabel("gender" in s ? (s as any).gender : undefined)}</div>
            </div>

            {/* Religion */}
            <div style={fieldCardStyle}>
              <div style={fieldLabelStyle}>
                <BookOpen size={13} /> الديانة
              </div>
              <div style={fieldValueStyle}>{getReligionLabel("religion" in s ? (s as any).religion : undefined)}</div>
            </div>

            {/* Joined / Created At */}
            <div style={{ ...fieldCardStyle, gridColumn: "span 2" }}>
              <div style={fieldLabelStyle}>
                <Calendar size={13} /> تاريخ التسجيل
              </div>
              <div style={fieldValueStyle}>
                {("createdAt" in s ? (s as any).createdAt : undefined) || "—"}
              </div>
            </div>
          </div>
        </div>

        {/* Footer — action buttons */}
        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid var(--border-color)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "10px",
          }}
        >
          <div style={{ display: "flex", gap: "8px" }}>
            {onBlock && (
              <button
                type="button"
                onClick={() => onBlock(s.id, s.name, isBlocked)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "8px 14px",
                  borderRadius: "8px",
                  border: "none",
                  background: isBlocked ? "#dcfce7" : "#dc2626",
                  color: isBlocked ? "#166534" : "#ffffff",
                  fontSize: "12px",
                  fontWeight: 800,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {isBlocked ? <ShieldCheck size={14} /> : <Ban size={14} />}
                <span>{isBlocked ? "إلغاء الحظر" : "حظر الطالب"}</span>
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(s.id, s.name)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "8px 14px",
                  borderRadius: "8px",
                  border: "none",
                  background: "#dc2626",
                  color: "#ffffff",
                  fontSize: "12px",
                  fontWeight: 800,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <Trash2 size={14} />
                <span>حذف نهائي</span>
              </button>
            )}
          </div>

          <button
            className="btn-secondary"
            onClick={onClose}
            style={{ padding: "8px 18px", fontSize: "12px" }}
          >
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
};

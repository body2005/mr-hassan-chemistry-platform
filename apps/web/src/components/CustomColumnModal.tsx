import React, { useState } from "react";
import { Columns3, Plus, X } from "lucide-react";
import { CustomColumn } from "../types/lms";

interface CustomColumnModalProps {
  isOpen: boolean;
  onClose: () => void;
  tableContext: "submissions" | "students";
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  onAddColumn: (col: CustomColumn) => void;
}

export const CustomColumnModal: React.FC<CustomColumnModalProps> = ({
  isOpen,
  onClose,
  tableContext,
  academicYear,
  onAddColumn,
}) => {
  const [colName, setColName] = useState("");
  const [dataType, setDataType] = useState<"text" | "number" | "percentage" | "checkbox">("text");

  if (!isOpen) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!colName.trim()) return;

    const newCol: CustomColumn = {
      id: `col_${Date.now()}`,
      name: colName.trim(),
      dataType,
      tableContext,
      academicYear,
      createdAt: new Date().toISOString().split("T")[0],
    };

    onAddColumn(newCol);
    setColName("");
    onClose();
  }

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
          maxWidth: "500px",
          width: "92%",
          padding: "26px",
          borderRadius: "20px",
          background: "var(--bg-surface, #ffffff)",
          border: "1px solid var(--border-color, #e2e8f0)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.1)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "18px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
            paddingBottom: "14px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: "var(--bg-accent, #ecfdf5)",
                color: "#059669",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "1px solid var(--border-accent, #a7f3d0)",
              }}
            >
              <Columns3 size={18} />
            </div>
            <div>
              <h2 style={{ margin: "0 0 2px", fontSize: "17px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
                إضافة عمود مخصص جديد
              </h2>
              <span style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
                سيظهر في جدول {tableContext === "submissions" ? "تسليم الواجبات" : "متابعة الطلاب"} لطلاب هذا الفصل
              </span>
            </div>
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
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 800, marginBottom: "6px", color: "var(--text-main, #0f172a)" }}>
              اسم العمود المخصص (Custom Column Label):
            </label>
            <input
              type="text"
              required
              value={colName}
              onChange={(e) => setColName(e.target.value)}
              placeholder="مثال: ملاحظات السلوك، تاريخ التواصل..."
              style={{
                width: "100%",
                padding: "11px 14px",
                border: "1px solid var(--border-color-strong, #cbd5e1)",
                borderRadius: "10px",
                fontSize: "13px",
                background: "var(--bg-surface-secondary, #f8fafc)",
                color: "var(--text-main, #0f172a)",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 800, marginBottom: "8px", color: "var(--text-main, #0f172a)" }}>
              نوع البيانات المدخلة داخل العمود:
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              {[
                { id: "text", label: "نص - Text" },
                { id: "number", label: "رقم - Number" },
                { id: "percentage", label: "نسبة مئوية - Percentage" },
                { id: "checkbox", label: "خانة اختيار - Checkbox" },
              ].map((type) => (
                <button
                  type="button"
                  key={type.id}
                  onClick={() => setDataType(type.id as any)}
                  style={{
                    padding: "11px",
                    borderRadius: "10px",
                    border: dataType === type.id ? "2px solid #059669" : "1px solid var(--border-color, #e2e8f0)",
                    background: dataType === type.id ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface, #ffffff)",
                    color: dataType === type.id ? "#059669" : "var(--text-main, #475569)",
                    fontWeight: 800,
                    fontSize: "12px",
                    cursor: "pointer",
                    textAlign: "center",
                    transition: "all 0.15s ease",
                  }}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "8px", paddingTop: "14px", borderTop: "1px solid var(--border-color, #e2e8f0)" }}>
            <button type="button" className="btn-secondary" onClick={onClose} style={{ padding: "8px 18px", fontSize: "12px" }}>
              إلغاء
            </button>
            <button type="submit" className="btn-primary" style={{ padding: "8px 22px", fontSize: "13px", fontWeight: 800, gap: "6px" }}>
              <Plus size={16} /> حفظ وإضافة العمود
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

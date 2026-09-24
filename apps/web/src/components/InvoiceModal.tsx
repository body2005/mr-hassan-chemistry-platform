import React, { useEffect, useState } from "react";
import {
  X,
  FileText,
  User,
  CreditCard,
  Calendar,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  AlertCircle,
  Eye,
  Check,
  ShieldCheck,
  RefreshCw,
} from "lucide-react";
import { PaymentOrder, paymentService } from "../services/paymentService";
import { useToast } from "./ToastProvider";

interface InvoiceModalProps {
  orderId: string | null;
  initialOrder?: PaymentOrder | null;
  isOpen: boolean;
  onClose: () => void;
  onOrderUpdated?: (updatedOrder: PaymentOrder) => void;
}

export const InvoiceModal: React.FC<InvoiceModalProps> = ({
  orderId,
  initialOrder,
  isOpen,
  onClose,
  onOrderUpdated,
}) => {
  const toast = useToast();
  const [order, setOrder] = useState<PaymentOrder | null>(initialOrder || null);
  const [loading, setLoading] = useState(false);
  const [receiptUrl, setReceiptUrl] = useState<string | null>(null);
  const [loadingReceipt, setLoadingReceipt] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      if (receiptUrl) {
        URL.revokeObjectURL(receiptUrl);
        setReceiptUrl(null);
      }
      return;
    }

    if (initialOrder) {
      setOrder(initialOrder);
    }

    const targetId = orderId || initialOrder?.id;
    if (targetId) {
      setLoading(true);
      paymentService
        .getOrder(targetId)
        .then((fetched) => {
          setOrder(fetched);
          if (fetched.review_note) setReviewNote(fetched.review_note);
        })
        .catch((err) => {
          console.error("Failed to fetch order", err);
          if (!initialOrder) {
            toast({ message: "تعذر تحميل تفاصيل الفاتورة", tone: "danger" });
          }
        })
        .finally(() => setLoading(false));

      // Fetch receipt image preview if order has receipt
      setLoadingReceipt(true);
      paymentService
        .getReceiptBlobUrl(targetId)
        .then((url) => {
          setReceiptUrl(url);
        })
        .catch((err) => {
          console.warn("Could not load receipt image blob", err);
        })
        .finally(() => setLoadingReceipt(false));
    }

    return () => {
      if (receiptUrl) {
        URL.revokeObjectURL(receiptUrl);
      }
    };
  }, [isOpen, orderId, initialOrder]);

  if (!isOpen) return null;

  async function handleAction(approve: boolean) {
    if (!order) return;
    setIsSubmitting(true);
    try {
      const updated = approve
        ? await paymentService.approve(order.id, reviewNote)
        : await paymentService.reject(order.id, reviewNote);
      setOrder(updated);
      if (onOrderUpdated) onOrderUpdated(updated);
      toast({
        message: approve ? "تم قبول الدفع وتفعيل المحتوى للطالب بنجاح" : "تم رفض الطلب بنجاح",
        tone: approve ? "success" : "info",
      });
    } catch (err) {
      toast({
        message: err instanceof Error ? err.message : "تعذرت معالجة الطلب",
        tone: "danger",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  const getMethodLabel = (method: string) => {
    switch (method) {
      case "vodafone_cash":
        return "فودافون كاش (Vodafone Cash)";
      case "instapay":
        return "إنستاباي (InstaPay)";
      case "bank_transfer":
        return "تحويل بنكي / حساب مصرفي";
      default:
        return method;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "paid":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "4px 12px",
              borderRadius: "20px",
              fontSize: "12px",
              fontWeight: 800,
              background: "#dcfce7",
              color: "#166534",
              border: "1px solid #86efac",
            }}
          >
            <CheckCircle2 size={14} /> مدفوعة ومفعّلة
          </span>
        );
      case "under_review":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "4px 12px",
              borderRadius: "20px",
              fontSize: "12px",
              fontWeight: 800,
              background: "#fef3c7",
              color: "#92400e",
              border: "1px solid #fde68a",
            }}
          >
            <Clock size={14} /> قيد المراجعة
          </span>
        );
      case "rejected":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "4px 12px",
              borderRadius: "20px",
              fontSize: "12px",
              fontWeight: 800,
              background: "#fee2e2",
              color: "#991b1b",
              border: "1px solid #fca5a5",
            }}
          >
            <XCircle size={14} /> مرفوضة
          </span>
        );
      default:
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "4px 12px",
              borderRadius: "20px",
              fontSize: "12px",
              fontWeight: 800,
              background: "var(--bg-surface-secondary)",
              color: "var(--text-muted)",
              border: "1px solid var(--border-color)",
            }}
          >
            <AlertCircle size={14} /> {status}
          </span>
        );
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(0, 0, 0, 0.65)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
        overflowY: "auto",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          border: "1.5px solid var(--border-color, #e2e8f0)",
          borderRadius: "20px",
          width: "100%",
          maxWidth: "760px",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.35)",
        }}
        onClick={(e) => e.stopPropagation()}
        dir="rtl"
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "1px solid var(--border-color)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--bg-surface-secondary)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "10px",
                background: "#0f392b",
                color: "#10b981",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <FileText size={22} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: "17px", fontWeight: 800, color: "var(--text-main)" }}>
                فاتورة وتفاصيل طلب الدفع
              </h2>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                رقم الطلب: {order?.id ? order.id.slice(0, 13) + "..." : orderId || "—"}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {order && getStatusBadge(order.status)}
            <button
              onClick={onClose}
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "8px",
                border: "1px solid var(--border-color)",
                background: "var(--bg-surface)",
                color: "var(--text-muted)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
              title="إغلاق"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: "24px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: "20px" }}>
          {loading && !order ? (
            <div style={{ padding: "50px 0", textAlign: "center", color: "var(--text-muted)" }}>
              <RefreshCw className="animate-spin" size={30} style={{ margin: "0 auto 10px", color: "#059669" }} />
              <p>جارٍ تحميل بيانات الفاتورة...</p>
            </div>
          ) : !order ? (
            <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-muted)" }}>
              <AlertCircle size={36} style={{ color: "#ef4444", margin: "0 auto 10px" }} />
              <p>تعذر العثور على بيانات هذا الطلب.</p>
            </div>
          ) : (
            <>
              {/* Summary Cards Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: "14px",
                }}
              >
                {/* Student Info */}
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    padding: "14px 16px",
                    borderRadius: "14px",
                    border: "1px solid var(--border-color)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted)", fontSize: "12px", marginBottom: "6px" }}>
                    <User size={15} style={{ color: "#059669" }} />
                    <span>بيانات الطالب</span>
                  </div>
                  <strong style={{ fontSize: "14.5px", color: "var(--text-main)", display: "block" }}>
                    {order.student_name || "طالب مسجل"}
                  </strong>
                </div>

                {/* Amount */}
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    padding: "14px 16px",
                    borderRadius: "14px",
                    border: "1px solid var(--border-color)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted)", fontSize: "12px", marginBottom: "6px" }}>
                    <CreditCard size={15} style={{ color: "#059669" }} />
                    <span>المبلغ المطلوب</span>
                  </div>
                  <strong style={{ fontSize: "17px", color: "#059669", display: "block" }}>
                    {order.amount_egp.toLocaleString("ar-EG")} ج.م
                  </strong>
                </div>

                {/* Date */}
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    padding: "14px 16px",
                    borderRadius: "14px",
                    border: "1px solid var(--border-color)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted)", fontSize: "12px", marginBottom: "6px" }}>
                    <Calendar size={15} style={{ color: "#059669" }} />
                    <span>تاريخ العملية</span>
                  </div>
                  <strong style={{ fontSize: "13px", color: "var(--text-main)", display: "block" }}>
                    {new Date(order.created_at).toLocaleString("ar-EG", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </strong>
                </div>
              </div>

              {/* Product and Transfer Details Box */}
              <div
                style={{
                  background: "var(--bg-surface-secondary)",
                  padding: "18px",
                  borderRadius: "14px",
                  border: "1px solid var(--border-color)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                  <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>المحتوى المطلوب:</span>
                  <strong style={{ fontSize: "14px", color: "var(--text-main)" }}>{order.product_name}</strong>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                  <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>طريقة الدفع المختارة:</span>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-main)" }}>
                    {getMethodLabel(order.payment_method)}
                  </span>
                </div>

                {order.payer_reference && (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                    <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>رقم الحساب / كود العملية المحول منه:</span>
                    <code
                      style={{
                        padding: "3px 10px",
                        background: "var(--bg-surface)",
                        borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        fontSize: "13px",
                        fontWeight: 700,
                        color: "#059669",
                      }}
                    >
                      {order.payer_reference}
                    </code>
                  </div>
                )}

                {order.student_note && (
                  <div style={{ borderTop: "1px dashed var(--border-color)", paddingTop: "10px" }}>
                    <span style={{ fontSize: "12.5px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                      ملاحظة من الطالب:
                    </span>
                    <p style={{ margin: 0, fontSize: "13px", color: "var(--text-main)", background: "var(--bg-surface)", padding: "10px", borderRadius: "8px" }}>
                      {order.student_note}
                    </p>
                  </div>
                )}
              </div>

              {/* Uploaded Payment Proof Receipt Section */}
              <div
                style={{
                  border: "1.5px solid var(--border-color)",
                  borderRadius: "16px",
                  padding: "18px",
                  background: "var(--bg-surface)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px", flexWrap: "wrap", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <ShieldCheck size={18} style={{ color: "#059669" }} />
                    <h3 style={{ margin: 0, fontSize: "14.5px", fontWeight: 800, color: "var(--text-main)" }}>
                      صورة إيصال التحويل (دليل الدفع)
                    </h3>
                  </div>

                  {order.has_receipt && (
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        onClick={() => void paymentService.openReceipt(order.id)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "6px 12px",
                          borderRadius: "8px",
                          border: "1px solid var(--border-color)",
                          background: "var(--bg-surface-secondary)",
                          color: "var(--text-main)",
                          fontSize: "12px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        <ExternalLink size={13} />
                        <span>فتح بالحجم الكامل</span>
                      </button>
                    </div>
                  )}
                </div>

                {loadingReceipt ? (
                  <div style={{ padding: "35px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                    <RefreshCw className="animate-spin" size={24} style={{ margin: "0 auto 8px", color: "#059669" }} />
                    <p>جارٍ تحميل صورة الإيصال...</p>
                  </div>
                ) : receiptUrl ? (
                  <div
                    style={{
                      background: "#0b0f19",
                      borderRadius: "12px",
                      overflow: "hidden",
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      maxHeight: "360px",
                      border: "1px solid var(--border-color)",
                      cursor: "pointer",
                    }}
                    onClick={() => void paymentService.openReceipt(order.id)}
                    title="اضغط لفتح الصورة في نافذة جديدة"
                  >
                    <img
                      src={receiptUrl}
                      alt="دليل التحويل"
                      style={{
                        maxWidth: "100%",
                        maxHeight: "360px",
                        objectFit: "contain",
                        display: "block",
                      }}
                    />
                  </div>
                ) : order.has_receipt ? (
                  <div
                    style={{
                      padding: "24px",
                      textAlign: "center",
                      background: "var(--bg-surface-secondary)",
                      borderRadius: "10px",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => void paymentService.openReceipt(order.id)}
                      className="btn-primary"
                      style={{ padding: "8px 18px", fontSize: "13px", gap: "6px", display: "inline-flex", alignItems: "center" }}
                    >
                      <Eye size={16} />
                      <span>عرض إيصال التحويل</span>
                    </button>
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "30px",
                      textAlign: "center",
                      background: "var(--bg-surface-secondary)",
                      borderRadius: "12px",
                      color: "var(--text-muted)",
                      fontSize: "13px",
                    }}
                  >
                    <AlertCircle size={28} style={{ color: "#f59e0b", margin: "0 auto 8px" }} />
                    <p style={{ margin: 0, fontWeight: 700 }}>لم يقم الطالب برفع صورة الإيصال بعد</p>
                  </div>
                )}
              </div>

              {/* Review Note & Actions (For Teacher) */}
              <div
                style={{
                  background: "var(--bg-surface-secondary)",
                  padding: "16px",
                  borderRadius: "14px",
                  border: "1px solid var(--border-color)",
                }}
              >
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: 700, color: "var(--text-muted)", marginBottom: "6px" }}>
                  ملاحظة المراجعة (اختياري، تظهر للطالب):
                </label>
                <input
                  type="text"
                  value={reviewNote}
                  onChange={(e) => setReviewNote(e.target.value)}
                  placeholder="مثال: تم التأكد من وصول الحوالة بنجاح..."
                  disabled={order.status === "paid" || isSubmitting}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                />
              </div>
            </>
          )}
        </div>

        {/* Footer Actions */}
        {order && order.status !== "paid" && (
          <div
            style={{
              padding: "16px 24px",
              borderTop: "1px solid var(--border-color)",
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              background: "var(--bg-surface-secondary)",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            <div style={{ display: "flex", gap: "10px" }}>
              {order.status !== "rejected" && (
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => void handleAction(false)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "8px 18px",
                    borderRadius: "8px",
                    border: "1px solid #ef4444",
                    background: "transparent",
                    color: "#ef4444",
                    fontSize: "13px",
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  <X size={15} />
                  <span>رفض الطلب</span>
                </button>
              )}

              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => void handleAction(true)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 20px",
                  borderRadius: "8px",
                  border: "none",
                  background: "#059669",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 800,
                  cursor: "pointer",
                  boxShadow: "0 2px 8px rgba(5, 150, 105, 0.3)",
                }}
              >
                <Check size={16} />
                <span>تفعيل وقبول الدفع</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

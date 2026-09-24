import React, { useEffect, useState } from "react";
import {
  X,
  BookOpen,
  User,
  Calendar,
  CheckCircle2,
  XCircle,
  Clock,
  Check,
  ShieldCheck,
  Phone,
  MessageSquare,
} from "lucide-react";
import { LessonAccessRequest, lessonAccessService } from "../services/paymentService";
import { useToast } from "./ToastProvider";

interface LessonAccessModalProps {
  requestId: string | null;
  initialRequest?: LessonAccessRequest | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdated?: (updated: LessonAccessRequest) => void;
  isTeacher?: boolean;
}

export const LessonAccessModal: React.FC<LessonAccessModalProps> = ({
  requestId,
  initialRequest,
  isOpen,
  onClose,
  onUpdated,
  isTeacher = true,
}) => {
  const toast = useToast();
  const [request, setRequest] = useState<LessonAccessRequest | null>(initialRequest || null);
  const [loading, setLoading] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    if (initialRequest) {
      setRequest(initialRequest);
      if (initialRequest.reviewer_note) setReviewNote(initialRequest.reviewer_note);
    }

    const targetId = requestId || initialRequest?.id;
    if (targetId) {
      setLoading(true);
      lessonAccessService
        .getRequest(targetId)
        .then((fetched) => {
          setRequest(fetched);
          if (fetched.reviewer_note) setReviewNote(fetched.reviewer_note);
        })
        .catch((err) => {
          console.error("Failed to fetch lesson access request", err);
          if (!initialRequest) {
            toast({ message: "تعذر تحميل تفاصيل طلب الإتاحة", tone: "danger" });
          }
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, requestId, initialRequest]);

  if (!isOpen) return null;

  async function handleAction(approve: boolean) {
    if (!request) return;
    setIsSubmitting(true);
    try {
      const updated = approve
        ? await lessonAccessService.approve(request.id, reviewNote)
        : await lessonAccessService.reject(request.id, reviewNote);
      setRequest(updated);
      if (onUpdated) onUpdated(updated);
      toast({
        message: approve ? "تمت الموافقة وإتاحة الدرس للطالب بنجاح" : "تم رفض الطلب بنجاح",
        tone: approve ? "success" : "info",
      });
    } catch (err) {
      toast({
        message: err instanceof Error ? err.message : "تعذرت معالجة طلب الإتاحة",
        tone: "danger",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "approved":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 12px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: 800,
              background: "#064e3b",
              color: "#34d399",
              border: "1px solid #059669",
            }}
          >
            <CheckCircle2 size={14} /> تمت الموافقة وإتاحة الدرس
          </span>
        );
      case "rejected":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 12px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: 800,
              background: "#450a0a",
              color: "#f87171",
              border: "1px solid #dc2626",
            }}
          >
            <XCircle size={14} /> طلب مرفوض
          </span>
        );
      case "pending":
      default:
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 12px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: 800,
              background: "#451a03",
              color: "#fbbf24",
              border: "1px solid #d97706",
            }}
          >
            <Clock size={14} /> قيد المراجعة والموافقة
          </span>
        );
    }
  };

  const formatDate = (isoStr?: string | null) => {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("ar-EG", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
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
          maxWidth: "640px",
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
                background: "#0284c718",
                color: "#0284c7",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <BookOpen size={22} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: "17px", fontWeight: 800, color: "var(--text-main)" }}>
                طلب إتاحة درس تعليمي
              </h2>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                رقم الطلب: {request?.id ? request.id.slice(0, 13) + "..." : requestId || "—"}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {request && renderStatusBadge(request.status)}
            <button
              type="button"
              onClick={onClose}
              className="modal-close-btn"
              style={{
                background: "var(--modal-close-bg)",
                border: "none",
                color: "#ffffff",
                cursor: "pointer",
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: "24px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "20px" }}>
          {loading && !request ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  border: "3px solid var(--border-color)",
                  borderTopColor: "var(--primary-color, #0284c7)",
                  borderRadius: "50%",
                  animation: "spin 0.8s linear infinite",
                  margin: "0 auto 12px",
                }}
              />
              جاري تحميل تفاصيل الطلب...
            </div>
          ) : request ? (
            <>
              {/* Information Cards Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                  gap: "14px",
                }}
              >
                {/* Student Info */}
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "14px",
                    padding: "14px 16px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      color: "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "6px",
                    }}
                  >
                    <User size={14} /> بيانات الطالب
                  </div>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-main)" }}>
                    {request.student_name || "طالب"}
                  </div>
                  {request.student_phone && (
                    <div
                      style={{
                        fontSize: "13px",
                        color: "var(--text-muted)",
                        marginTop: "4px",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        direction: "ltr",
                        justifyContent: "flex-end",
                      }}
                    >
                      <span>{request.student_phone}</span>
                      <Phone size={13} />
                    </div>
                  )}
                </div>

                {/* Course & Lesson Info */}
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "14px",
                    padding: "14px 16px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      color: "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "6px",
                    }}
                  >
                    <BookOpen size={14} /> المحتوى المطلوب
                  </div>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-main)" }}>
                    {request.lesson_title}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                    الكورس: {request.course_title}
                  </div>
                </div>

                {/* Request Timing */}
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "14px",
                    padding: "14px 16px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      color: "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "6px",
                    }}
                  >
                    <Calendar size={14} /> وقت الإرسال
                  </div>
                  <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)" }}>
                    {formatDate(request.created_at)}
                  </div>
                </div>

                {/* Review Time if processed */}
                {request.reviewed_at && (
                  <div
                    style={{
                      background: "var(--bg-surface-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "14px",
                      padding: "14px 16px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "12px",
                        color: "var(--text-muted)",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        marginBottom: "6px",
                      }}
                    >
                      <Clock size={14} /> وقت المراجعة
                    </div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)" }}>
                      {formatDate(request.reviewed_at)}
                    </div>
                  </div>
                )}
              </div>

              {/* Student Note */}
              {request.student_note && (
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    border: "1px dashed var(--border-color)",
                    borderRadius: "14px",
                    padding: "14px 16px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      color: "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "6px",
                    }}
                  >
                    <MessageSquare size={14} /> رسالة / ملاحظة الطالب:
                  </div>
                  <div
                    style={{
                      fontSize: "14px",
                      color: "var(--text-main)",
                      whiteSpace: "pre-wrap",
                      lineHeight: "1.6",
                    }}
                  >
                    {request.student_note}
                  </div>
                </div>
              )}

              {/* Review Section (For Teacher) */}
              {isTeacher && (
                <div
                  style={{
                    background: "var(--bg-surface-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "16px",
                    padding: "18px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <ShieldCheck size={18} color="var(--primary-color, #0284c7)" />
                    <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-main)" }}>
                      قرار المعلم والمراجعة
                    </span>
                  </div>

                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "var(--text-muted)",
                        marginBottom: "6px",
                      }}
                    >
                      ملاحظة للمعلم أو للطالب (اختياري):
                    </label>
                    <textarea
                      value={reviewNote}
                      onChange={(e) => setReviewNote(e.target.value)}
                      placeholder="أدخل أي ملاحظة تود توجيهها للطالب..."
                      rows={3}
                      disabled={isSubmitting}
                      style={{
                        width: "100%",
                        padding: "10px 14px",
                        borderRadius: "10px",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-surface, #ffffff)",
                        color: "var(--text-main)",
                        fontSize: "13px",
                        outline: "none",
                        resize: "vertical",
                      }}
                    />
                  </div>

                  {request.status === "pending" && (
                    <div style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
                      <button
                        type="button"
                        onClick={() => handleAction(true)}
                        disabled={isSubmitting}
                        style={{
                          flex: 2,
                          padding: "12px 18px",
                          borderRadius: "12px",
                          border: "none",
                          background: "#059669",
                          color: "#ffffff",
                          fontSize: "14px",
                          fontWeight: 700,
                          cursor: isSubmitting ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: "8px",
                          opacity: isSubmitting ? 0.7 : 1,
                          boxShadow: "0 4px 12px rgba(5, 150, 105, 0.25)",
                        }}
                      >
                        <Check size={18} />
                        الموافقة وإتاحة الدرس للطالب
                      </button>

                      <button
                        type="button"
                        onClick={() => handleAction(false)}
                        disabled={isSubmitting}
                        style={{
                          flex: 1,
                          padding: "12px 18px",
                          borderRadius: "12px",
                          border: "none",
                          background: "var(--danger-action-bg)",
                          color: "#ffffff",
                          fontSize: "14px",
                          fontWeight: 700,
                          cursor: isSubmitting ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: "8px",
                          opacity: isSubmitting ? 0.7 : 1,
                        }}
                      >
                        <X size={18} />
                        رفض الطلب
                      </button>
                    </div>
                  )}

                  {request.status !== "pending" && request.reviewer_note && (
                    <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                      <strong>ملاحظة المراجعة السابقة:</strong> {request.reviewer_note}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
};

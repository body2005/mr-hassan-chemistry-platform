import { useEffect, useState, useCallback, useRef } from "react";
import { CreditCard, Clock3, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { paymentService, type PaymentOrder, type PaymentConfig } from "../services/paymentService";
const statusLabels: Record<PaymentOrder["status"], string> = {
  pending: "بانتظار رفع الإيصال",
  under_review: "قيد المراجعة",
  paid: "تم التفعيل",
  rejected: "مرفوض",
  cancelled: "ملغي",
};

const statusIcons = {
  pending: Clock3,
  under_review: RefreshCw,
  paid: CheckCircle2,
  rejected: XCircle,
  cancelled: XCircle,
};

const card = { background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "18px" };
const sectionHead = { display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px" };
export function PaymentOrderHistory() {
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [loadingPayments, setLoadingPayments] = useState(false);
  const [paymentReadError, setPaymentReadError] = useState<string | null>(null);
  const [hasLoadedPayments, setHasLoadedPayments] = useState(false);
  const generation = useRef(0);
  const load = useCallback(async () => {
    const request = ++generation.current;
    setLoadingPayments(true);
    try {
      const [nextOrders, nextConfig] = await Promise.all([paymentService.getMyOrders(true), paymentService.getConfig()]);
      if (request !== generation.current) return;
      setOrders(nextOrders); setConfig(nextConfig); setPaymentReadError(null); setHasLoadedPayments(true);
    } catch (error) {
      if (request === generation.current) setPaymentReadError(error instanceof Error ? error.message : "تعذر تحديث الطلبات");
    } finally { if (request === generation.current) setLoadingPayments(false); }
  }, []);
  const cancelReads = useCallback(() => { generation.current++; }, []);
  useEffect(() => {
    void load();
    const refresh = () => { void load(); };
    window.addEventListener('lms_payment_updated', refresh);
    window.addEventListener('lms_lesson_unlocked', refresh);
    return () => { cancelReads(); window.removeEventListener('lms_payment_updated', refresh); window.removeEventListener('lms_lesson_unlocked', refresh); };
  }, [load, cancelReads]);
  return (<div className="payment-order-history" style={{ minWidth: 0, marginTop: 20 }}>
          <section style={{ ...card, padding: "20px" }}>
            <div style={{ ...sectionHead, justifyContent: "space-between" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "14.5px", fontWeight: 900, color: "var(--text-main)" }}>طلباتك السابقة</h2>
                <p style={{ margin: "3px 0 0", fontSize: "11px", color: "var(--text-muted)" }}>تابع حالة مراجعة الإيصالات من هنا.</p>
              </div>
              <button type="button" disabled={loadingPayments} onClick={() => void load().catch(() => undefined)} aria-label="تحديث" title="تحديث حالة الطلبات" style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "8px", cursor: "pointer", color: "var(--text-main)", display: "flex" }}>
                <RefreshCw size={15} />
              </button>
            </div>
            {paymentReadError && (
              <p role="alert" style={{ color: "var(--text-main)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "12px", fontSize: "12px", lineHeight: 1.7 }}>
                تعذر تحديث حالة الدفع: {paymentReadError}. {hasLoadedPayments ? "المعروض آخر حالة تم تحميلها؛ قد تكون تغيّرت." : "لم تُحمّل الطلبات بعد."} اضغط زر التحديث لإعادة المحاولة.
              </p>
            )}
            {loadingPayments && <p role="status" style={{ color: "var(--text-muted)", fontSize: "12px" }}>جارٍ تحديث حالة الدفع…</p>}
            {orders.length === 0 && hasLoadedPayments && !paymentReadError ? (
              <div style={{ textAlign: "center", padding: "24px 10px", color: "var(--text-muted)" }}>
                <CreditCard size={28} style={{ margin: "0 auto 8px", color: "#059669" }} />
                <p style={{ margin: 0, fontSize: "12px", fontWeight: 700 }}>لا توجد طلبات دفع حتى الآن.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "380px", overflowY: "auto" }}>
                {orders.map((order) => {
                  const StatusIcon = statusIcons[order.status];
                  return (
                    <article key={order.id} style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "12px", padding: "14px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px", flexWrap: "wrap" }}>
                        <div>
                          <strong style={{ fontSize: "12.5px", color: "var(--text-main)" }}>{order.product_name}</strong>
                          <small style={{ display: "block", fontSize: "10.5px", color: "var(--text-muted)", marginTop: "2px" }}>{new Date(order.created_at).toLocaleString("ar-EG")}</small>
                        </div>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: "4px",
                          padding: "3px 9px", borderRadius: "999px", fontSize: "10.5px", fontWeight: 800,
                          background: order.status === "paid" ? "var(--bg-accent)" : order.status === "rejected" ? "#fee2e2" : "var(--bg-surface)",
                          color: order.status === "paid" ? "#059669" : order.status === "rejected" ? "#b91c1c" : "var(--text-muted)",
                          border: "1px solid var(--border-color)",
                        }}>
                          <StatusIcon size={12} />{statusLabels[order.status]}
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: "12px", marginTop: "8px", fontSize: "11.5px", color: "var(--text-muted)", fontWeight: 700 }}>
                        <span>{order.amount_egp.toLocaleString("ar-EG")} ج.م</span>
                        <span>{config?.methods.find((item) => item.id === order.payment_method)?.label || order.payment_method}</span>
                      </div>
                      {order.review_note && <p style={{ margin: "8px 0 0", fontSize: "11px", color: "var(--text-muted)", background: "var(--bg-surface)", borderRadius: "8px", padding: "6px 8px" }}>ملاحظة المراجعة: {order.review_note}</p>}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
</div>);
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock3, CreditCard, FileUp, RefreshCw, XCircle } from "lucide-react";
import { Course } from "../types/lms";
import {
  PaymentConfig,
  PaymentMethod,
  PaymentOrder,
  PaymentProductType,
  PaymentTarget,
  paymentService,
} from "../services/paymentService";
import { useToast } from "../components/ToastProvider";

interface PaymentViewProps {
  courses: Course[];
  initialTarget?: PaymentTarget | null;
  onEntitlementsChanged?: () => void;
}

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

export function PaymentView({ courses, initialTarget, onEntitlementsChanged }: PaymentViewProps) {
  const toast = useToast();
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  // Student checkout is intentionally limited to a single lesson or the
  // optional AI subscription.  A whole-course target from an old link is
  // normalised to lesson checkout instead of exposing the removed product.
  const [productType, setProductType] = useState<PaymentProductType>(
    initialTarget?.productType === "ai_subscription" ? "ai_subscription" : "lesson",
  );
  const [productId, setProductId] = useState(
    initialTarget?.productType === "lesson" ? initialTarget.productId || "" : "",
  );
  const [method, setMethod] = useState<PaymentMethod | "">("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);

  const load = useCallback(async () => {
    const [nextConfig, nextOrders] = await Promise.all([
      paymentService.getConfig(),
      paymentService.getMyOrders(),
    ]);
    setConfig(nextConfig);
    setOrders(nextOrders);
    const firstMethod = nextConfig.methods.find((item) => item.enabled)?.id || "";
    setMethod((current) => current || firstMethod);
  }, []);

  useEffect(() => {
    void load().catch((error) => toast({ message: error instanceof Error ? error.message : "تعذر تحميل بيانات الدفع", tone: "danger" }));
  }, [load, toast]);

  useEffect(() => {
    if (!initialTarget) return;
    setProductType(initialTarget.productType === "ai_subscription" ? "ai_subscription" : "lesson");
    setProductId(initialTarget.productType === "lesson" ? initialTarget.productId || "" : "");
  }, [initialTarget]);

  const lessons = useMemo(() => courses.flatMap((course) => course.lessons.map((lesson) => ({ ...lesson, courseTitle: course.title }))), [courses]);
  const selectedLesson = lessons.find((lesson) => lesson.id === productId);
  const amount = productType === "ai_subscription"
    ? Number(config?.ai_monthly_price_egp || 0)
    : Number(selectedLesson?.price || 0);
  const selectedMethod = config?.methods.find((item) => item.id === method);

  async function submitPayment() {
    if (!method) {
      toast({ message: "اختر طريقة دفع مفعلة", tone: "warning" });
      return;
    }
    if (productType !== "ai_subscription" && !productId) {
      toast({ message: "اختر درسًا للدفع", tone: "warning" });
      return;
    }
    if (!receipt) {
      toast({ message: "ارفع صورة أو ملف إيصال التحويل", tone: "warning" });
      return;
    }
    setBusy(true);
    setProgress(0);
    try {
      const order = await paymentService.createOrder({
        product_type: productType,
        product_id: productType === "ai_subscription" ? undefined : productId,
        payment_method: method,
        payer_reference: reference || undefined,
        student_note: note || undefined,
      });
      await paymentService.uploadReceipt(order.id, receipt, reference, setProgress);
      await load();
      onEntitlementsChanged?.();
      setReceipt(null);
      setReference("");
      setNote("");
      toast({ message: "تم إرسال الإيصال للمراجعة. ستظهر حالة التفعيل هنا.", tone: "success" });
    } catch (error) {
      toast({ message: error instanceof Error ? error.message : "تعذر إرسال طلب الدفع", tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-container payment-page">
      <header className="section-heading payment-heading">
        <div>
          <span className="eyebrow">المدفوعات والاشتراكات</span>
          <h1>تفعيل المحتوى التعليمي</h1>
          <p>اختر ما تريد تفعيله، حوّل المبلغ إلى الحساب الظاهر، ثم أرسل الإيصال للمراجعة.</p>
        </div>
        <div className="payment-total" aria-label="المبلغ المطلوب">
          <span>المبلغ المطلوب</span>
          <strong>{amount.toLocaleString("ar-EG")} ج.م</strong>
        </div>
      </header>

      <div className="payment-layout">
        <section className="panel payment-form-panel">
          <h2>طلب تفعيل جديد</h2>
          <div className="segmented-control" role="tablist" aria-label="نوع المنتج">
            {([
              ["lesson", "درس منفرد"],
            ] as Array<[PaymentProductType, string]>).map(([value, label]) => (
              <button key={value} className={productType === value ? "active" : ""} onClick={() => { setProductType(value); setProductId(""); }}>
                {label}
              </button>
            ))}
          </div>

          {productType === "lesson" && (
            <label className="field-label">الدرس
              <select value={productId} onChange={(event) => setProductId(event.target.value)}>
                <option value="">اختر درسًا</option>
                {lessons.filter((lesson) => Number(lesson.price || 0) > 0).map((lesson) => (
                  <option key={lesson.id} value={lesson.id}>{lesson.courseTitle} / {lesson.title} — {Number(lesson.price || 0).toLocaleString("ar-EG")} ج.م</option>
                ))}
              </select>
            </label>
          )}
          {productType === "ai_subscription" && null}

          <fieldset className="payment-methods">
            <legend>طريقة التحويل</legend>
            {config?.methods.map((item) => (
              <label key={item.id} className={`method-row ${method === item.id ? "selected" : ""} ${!item.enabled ? "disabled" : ""}`}>
                <input type="radio" name="method" value={item.id} checked={method === item.id} disabled={!item.enabled} onChange={() => setMethod(item.id)} />
                <span><strong>{item.label}</strong><small>{item.enabled ? item.destination : "غير مفعلة حاليًا"}</small></span>
              </label>
            ))}
          </fieldset>

          {selectedMethod?.destination && <div className="destination-box"><CreditCard size={18} /><span>حوّل إلى: <b dir="ltr">{selectedMethod.destination}</b></span></div>}

          <div className="form-grid">
            <label className="field-label">مرجع التحويل (اختياري)<input value={reference} onChange={(event) => setReference(event.target.value)} maxLength={160} placeholder="رقم العملية أو رقم الهاتف" /></label>
            <label className="field-label">ملاحظة (اختياري)<input value={note} onChange={(event) => setNote(event.target.value)} maxLength={4000} placeholder="أي تفاصيل تساعد في المراجعة" /></label>
          </div>
          <label className="receipt-drop">
            <FileUp size={22} />
            <span>{receipt ? receipt.name : "اختر صورة أو PDF لإيصال التحويل"}</span>
            <small>JPG أو PNG أو WEBP أو PDF</small>
            <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(event) => setReceipt(event.target.files?.[0] || null)} />
          </label>
          {busy && <div className="upload-progress"><span style={{ width: `${progress}%` }} /></div>}
          <button className="primary-action" disabled={busy || amount <= 0} onClick={submitPayment}>{busy ? `جارٍ الإرسال ${progress}%` : "إرسال طلب التفعيل"}</button>
        </section>

        <section className="panel order-history">
          <div className="panel-title-row"><div><h2>طلباتك</h2><p>آخر تحديث للحالة من المدرس.</p></div><button className="icon-action" onClick={() => void load()} aria-label="تحديث"><RefreshCw size={17} /></button></div>
          {orders.length === 0 ? <div className="empty-state"><CreditCard size={30} /><p>لا توجد طلبات دفع حتى الآن.</p></div> : (
            <div className="order-list">{orders.map((order) => {
              const StatusIcon = statusIcons[order.status];
              return <article className="order-card" key={order.id}>
                <div className="order-card-head"><div><strong>{order.product_name}</strong><small>{new Date(order.created_at).toLocaleString("ar-EG")}</small></div><span className={`status-chip status-${order.status}`}><StatusIcon size={14} />{statusLabels[order.status]}</span></div>
                <div className="order-meta"><span>{order.amount_egp.toLocaleString("ar-EG")} ج.م</span><span>{config?.methods.find((item) => item.id === order.payment_method)?.label || order.payment_method}</span></div>
                {order.review_note && <p className="review-note">ملاحظة المراجعة: {order.review_note}</p>}
              </article>;
            })}</div>
          )}
        </section>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, Eye, FileText, RefreshCw, Save, WalletCards, X } from "lucide-react";
import { Course } from "../types/lms";
import { PaymentOrder, PaymentStatus, paymentService } from "../services/paymentService";
import { useToast } from "../components/ToastProvider";
import { useConfirm } from "../components/ConfirmWizard";
import { InvoiceModal } from "../components/InvoiceModal";

interface PaymentManagementViewProps {
  courses: Course[];
  onCoursesChanged: (courses: Course[]) => void;
}

const filterOptions: Array<[PaymentStatus | "all", string]> = [
  ["all", "الكل"], ["under_review", "قيد المراجعة"], ["pending", "بدون إيصال"],
  ["paid", "مفعّلة"], ["rejected", "مرفوضة"],
];

export function PaymentManagementView({ courses, onCoursesChanged }: PaymentManagementViewProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const [filter, setFilter] = useState<PaymentStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [selectedInvoiceOrder, setSelectedInvoiceOrder] = useState<PaymentOrder | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [hasLoadedOrders, setHasLoadedOrders] = useState(false);
  const readGeneration = useRef(0);
  const cancelReads = useCallback(() => { readGeneration.current++; }, []);

  useEffect(() => {
    const next: Record<string, string> = {};
    courses.forEach((course) => {
      next[`course:${course.id}`] = String(Number(course.price || 0));
      course.lessons.forEach((lesson) => { next[`lesson:${lesson.id}`] = String(Number(lesson.price || 0)); });
    });
    setPrices(next);
  }, [courses]);

  const load = useCallback(async (fresh = false) => {
    const generation = ++readGeneration.current;
    setLoading(true);
    try {
      const next = await paymentService.listOrders(filter === "all" ? undefined : filter, fresh);
      if (generation !== readGeneration.current) return;
      setOrders(next); setHasLoadedOrders(true); setReadError(null);
    } catch (error) {
      if (generation === readGeneration.current) setReadError(error instanceof Error ? error.message : "تعذر تحميل الطلبات");
      throw error;
    } finally {
      if (generation === readGeneration.current) setLoading(false);
    }
  }, [filter]);
  useEffect(() => {
    setOrders([]); setHasLoadedOrders(false); setReadError(null);
    void load(true).catch(() => undefined);
    return cancelReads;
  }, [load, cancelReads]);
  useEffect(() => {
    const reconcile = () => { void load(true).catch(() => undefined); };
    window.addEventListener('lms_payment_updated', reconcile);
    return () => window.removeEventListener('lms_payment_updated', reconcile);
  }, [load]);

  const underReviewCount = useMemo(() => orders.filter((order) => order.status === "under_review").length, [orders]);

  async function review(order: PaymentOrder, approve: boolean) {
    const accepted = await confirm({
      title: approve ? "تأكيد استلام المبلغ" : "رفض طلب الدفع",
      message: approve
        ? `سيتم تفعيل «${order.product_name}» للطالب ${order.student_name || ""}. تأكد من وصول ${order.amount_egp} ج.م أولًا.`
        : "لن يتم منح الطالب صلاحية الوصول. يمكنك إعادة المراجعة إذا أرسل طلبًا جديدًا.",
      confirmLabel: approve ? "تفعيل الآن" : "رفض الطلب",
      tone: approve ? "info" : "danger",
    });
    if (!accepted) return;
    setWorkingId(order.id);
    try {
      await (approve ? paymentService.approve(order.id) : paymentService.reject(order.id));
      await load(true);
      toast({ message: approve ? "تم تفعيل الاستحقاق للطالب" : "تم رفض الطلب", tone: "success" });
    } catch (error) {
      toast({ message: error instanceof Error ? error.message : "تعذرت مراجعة الطلب", tone: "danger" });
    } finally {
      setWorkingId(null);
    }
  }

  async function savePrice(kind: "course" | "lesson", id: string) {
    const key = `${kind}:${id}`;
    const price = Number(prices[key]);
    if (!Number.isFinite(price) || price < 0) {
      toast({ message: "أدخل سعرًا صحيحًا لا يقل عن صفر", tone: "warning" });
      return;
    }
    setWorkingId(key);
    try {
      if (kind === "course") await paymentService.updateCoursePrice(id, price);
      else await paymentService.updateLessonPrice(id, price);
      const next = courses.map((course) => kind === "course" && course.id === id
        ? { ...course, price }
        : { ...course, lessons: course.lessons.map((lesson) => kind === "lesson" && lesson.id === id ? { ...lesson, price } : lesson) });
      onCoursesChanged(next);
      toast({ message: "تم حفظ السعر", tone: "success" });
    } catch (error) {
      toast({ message: error instanceof Error ? error.message : "تعذر حفظ السعر", tone: "danger" });
    } finally {
      setWorkingId(null);
    }
  }

  return <div className="page-container payment-admin-page">
    <header className="section-heading payment-heading">
      <div><span className="eyebrow">للمدرس فقط</span><h1>المدفوعات والتسعير</h1><p>راجع التحويلات يدويًا وحدد سعر كل درس على حدة.</p></div>
      <div className="payment-total"><span>بانتظار المراجعة في القائمة المعروضة</span><strong>{hasLoadedOrders ? underReviewCount.toLocaleString("ar-EG") : "—"}</strong></div>
    </header>

    <section className="panel review-panel">
      <div className="panel-title-row"><div><h2>طلبات الطلاب</h2><p>الفترة الحالية — الأحدث أولًا</p></div><button className="icon-action" disabled={loading} onClick={() => void load(true).catch(() => undefined)} aria-label="تحديث"><RefreshCw size={17} /></button></div>
      <div className="segmented-control compact">{filterOptions.map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>)}</div>
      {readError && <p role="alert" style={{ color: "var(--text-main)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "12px", lineHeight: 1.7 }}>تعذر تحديث الطلبات: {readError}. {hasLoadedOrders ? "المعروض آخر حالة تم تحميلها؛ قد تكون تغيّرت." : "لم تُحمّل الطلبات بعد."} أعد التحديث يدويًا قبل المراجعة.</p>}
      {loading && <div role="status" className="empty-state"><RefreshCw className="spin" size={24} /><p>جارٍ تحميل الطلبات…</p></div>}
      {!loading && orders.length === 0 && hasLoadedOrders && !readError ? <div className="empty-state"><WalletCards size={30} /><p>لا توجد طلبات في هذه الحالة.</p></div> :
        <div className="review-list">{orders.map((order) => <article className="review-row" key={order.id}>
          <div className="review-main"><strong>{order.student_name || "طالب"}</strong><span>{order.product_name}</span><small>{new Date(order.created_at).toLocaleString("ar-EG")}</small></div>
          <div className="review-amount"><strong>{order.amount_egp.toLocaleString("ar-EG")} ج.م</strong><span>{order.status === "under_review" ? "قيد المراجعة" : order.status}</span></div>
          <div className="review-actions">
            <button className="secondary-action" onClick={() => setSelectedInvoiceOrder(order)}><FileText size={16} />معاينة الفاتورة</button>
            {order.has_receipt && <button className="secondary-action" onClick={() => void paymentService.openReceipt(order.id).catch((error) => toast({ message: error.message, tone: "danger" }))}><Eye size={16} />الإيصال</button>}
            {order.status !== "paid" && order.status !== "rejected" && <>
              <button disabled={loading || Boolean(readError) || workingId === order.id} className="approve-action" onClick={() => void review(order, true)}><Check size={16} />تفعيل</button>
              <button disabled={loading || Boolean(readError) || workingId === order.id} className="reject-action" onClick={() => void review(order, false)}><X size={16} />رفض</button>
            </>}
          </div>
        </article>)}</div>}
    </section>

    <section className="panel pricing-panel">
      <div className="panel-title-row"><div><h2>أسعار الدروس</h2><p>السعر صفر يعني أن الدرس مجاني. كل درس له سعر وصلاحية مستقلة.</p></div></div>
      <div className="pricing-list">{courses.map((course) => <div className="pricing-course" key={course.id}>
        <div className="pricing-course-heading"><strong>{course.title}</strong></div>
        {course.lessons.map((lesson) => <div className="pricing-row" key={lesson.id}><div><span>{lesson.title}</span><small>درس منفرد</small></div><div className="price-editor"><input type="number" min="0" step="1" value={prices[`lesson:${lesson.id}`] ?? "0"} onChange={(event) => setPrices((current) => ({ ...current, [`lesson:${lesson.id}`]: event.target.value }))} /><span>ج.م</span><button onClick={() => void savePrice("lesson", lesson.id)} disabled={workingId === `lesson:${lesson.id}`} aria-label="حفظ سعر الدرس"><Save size={15} /></button></div></div>)}
      </div>)}</div>
    </section>

    <InvoiceModal
      orderId={selectedInvoiceOrder?.id || null}
      initialOrder={selectedInvoiceOrder}
      isOpen={Boolean(selectedInvoiceOrder)}
      onClose={() => setSelectedInvoiceOrder(null)}
      onOrderUpdated={() => void load(true).catch(() => undefined)}
    />
  </div>;
}

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  Copy,
  CreditCard,
  FileUp,
  GraduationCap,
  HandCoins,
  Infinity as InfinityIcon,
  Landmark,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  UserRound,
  XCircle,
  Zap,
} from "lucide-react";
import { Course, CurrentUser } from "../types/lms";
import {
  PaymentConfig,
  PaymentMethod,
  PaymentMethodConfig,
  PaymentOrder,
  PaymentProductType,
  PaymentTarget,
  paymentService,
} from "../services/paymentService";
import { useToast } from "../components/ToastProvider";

interface PaymentViewProps {
  courses: Course[];
  currentUser?: CurrentUser | null;
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

const methodIcons: Record<PaymentMethod, typeof Landmark> = {
  instapay: Smartphone,
  vodafone_cash: HandCoins,
  bank_transfer: Landmark,
};

const card: React.CSSProperties = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border-color)",
  borderRadius: "18px",
  boxShadow: "0 2px 12px rgba(0,0,0,0.03)",
};

const sectionHead: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "12px",
  marginBottom: "20px",
  paddingBottom: "14px",
  borderBottom: "1px solid var(--border-color)",
};

const iconTile: React.CSSProperties = {
  width: "40px",
  height: "40px",
  borderRadius: "12px",
  background: "var(--bg-accent)",
  color: "#059669",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  height: "44px",
  padding: "0 14px",
  borderRadius: "12px",
  background: "var(--bg-surface-secondary)",
  border: "1px solid var(--border-color)",
  color: "var(--text-main)",
  fontSize: "13.5px",
  fontFamily: "inherit",
  outline: "none",
  boxSizing: "border-box",
};

export function PaymentView({ courses, currentUser, initialTarget, onEntitlementsChanged }: PaymentViewProps) {
  const toast = useToast();
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const productType: PaymentProductType = "lesson";
  const [productId, setProductId] = useState(
    initialTarget?.productType === "lesson" ? initialTarget.productId || "" : "",
  );
  const [method, setMethod] = useState<PaymentMethod | "">("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);

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
    setProductId(initialTarget.productType === "lesson" ? initialTarget.productId || "" : "");
  }, [initialTarget]);

  const lessons = useMemo(() => courses.flatMap((course) => course.lessons.map((lesson) => ({ ...lesson, courseTitle: course.title }))), [courses]);
  const selectedLesson = lessons.find((lesson) => lesson.id === productId);
  const amount = Number(selectedLesson?.price || 0);

  const enabledMethods = useMemo(() => (config?.methods || []).filter((m) => m.enabled), [config]);
  const selectedMethod: PaymentMethodConfig | undefined = config?.methods.find((item) => item.id === method);

  const student = currentUser && "studentPhone" in currentUser ? currentUser : null;

  async function copyDestination(m: PaymentMethodConfig) {
    if (!m.destination) return;
    try {
      await navigator.clipboard.writeText(m.destination);
      setCopiedId(m.id);
      setTimeout(() => setCopiedId(null), 1800);
      toast({ message: "تم نسخ بيانات التحويل", tone: "success" });
    } catch {
      toast({ message: "انسخ البيانات يدوياً", tone: "warning" });
    }
  }

  async function submitPayment() {
    if (!method) {
      toast({ message: "اختر طريقة دفع مفعلة", tone: "warning" });
      return;
    }
    if (!productId) {
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
        product_id: productId,
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
    <div style={{ padding: "24px 20px 60px", maxWidth: "1200px", margin: "0 auto" }}>
      {/* ── Breadcrumb ── */}
      <nav style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-muted)", marginBottom: "18px", flexWrap: "wrap" }}>
        <span>الرئيسية</span>
        <span>/</span>
        <span>متجر المقررات والكتب والمراجعات</span>
        <span>/</span>
        <span style={{ color: "var(--text-main)", fontWeight: 800 }}>تأكيد الاشتراك والسداد</span>
      </nav>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 7fr) minmax(0, 5fr)", gap: "24px", alignItems: "start" }}>
        {/* ═══════════ RIGHT COLUMN: student data + payment ═══════════ */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Student data */}
          <section style={{ ...card, padding: "24px" }}>
            <div style={sectionHead}>
              <div style={iconTile}><BadgeCheck size={21} /></div>
              <div>
                <h2 style={{ margin: 0, fontSize: "15px", fontWeight: 900, color: "var(--text-main)" }}>بيانات الطالب الأكاديمية</h2>
                <p style={{ margin: "3px 0 0", fontSize: "11.5px", color: "var(--text-muted)" }}>سيتم ربط المذكرات وبنك الأسئلة والتقييمات بهذه البيانات</p>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={labelStyle}>اسم الطالب <span style={{ color: "#e11d48" }}>*</span></label>
                <div style={{ position: "relative" }}>
                  <input style={{ ...inputStyle, paddingInlineStart: "40px" }} value={student?.name || ""} readOnly />
                  <UserRound size={17} style={{ position: "absolute", insetInlineEnd: "13px", top: "13px", color: "var(--text-muted)" }} />
                </div>
              </div>
              <div>
                <label style={labelStyle}>البريد الإلكتروني</label>
                <input style={{ ...inputStyle, direction: "ltr", textAlign: "right" }} value={student?.email || ""} readOnly dir="ltr" />
              </div>
              <div>
                <label style={labelStyle}>رقم الواتساب للتفعيل</label>
                <input style={{ ...inputStyle, direction: "ltr", textAlign: "right" }} value={student?.studentPhone || ""} readOnly dir="ltr" placeholder="—" />
              </div>
            </div>
            <div style={{ marginTop: "16px", padding: "12px 14px", borderRadius: "12px", background: "var(--bg-accent)", border: "1px solid var(--border-accent)", display: "flex", alignItems: "flex-start", gap: "10px", fontSize: "11.5px", color: "var(--text-main)" }}>
              <ShieldCheck size={16} style={{ color: "#059669", flexShrink: 0, marginTop: "1px" }} />
              <p style={{ margin: 0, lineHeight: 1.7 }}>
                بمجرد تأكيد المعلم للدفع يتم فوراً فتح درس الكيمياء وكويزاته التفاعلية ومذكراته بصيغة PDF داخل حسابك.
              </p>
            </div>
          </section>

          {/* Payment method */}
          <section style={{ ...card, padding: "24px" }}>
            <div style={{ ...sectionHead, justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div style={iconTile}><CreditCard size={21} /></div>
                <div>
                  <h2 style={{ margin: 0, fontSize: "15px", fontWeight: 900, color: "var(--text-main)" }}>طريقة الدفع الآمن</h2>
                  <p style={{ margin: "3px 0 0", fontSize: "11.5px", color: "var(--text-muted)" }}>حوّل المبلغ ثم ارفع إيصال التحويل للمراجعة والتفعيل</p>
                </div>
              </div>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", padding: "4px 10px", borderRadius: "999px", background: "var(--bg-accent)", color: "#059669", border: "1px solid var(--border-accent)", fontSize: "10.5px", fontWeight: 800 }}>
                <LockKeyhole size={12} /> بوابة مشفرة
              </span>
            </div>

            {/* Method cards grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", marginBottom: "18px" }}>
              {enabledMethods.length === 0 && (
                <p style={{ margin: 0, fontSize: "12.5px", color: "var(--text-muted)" }}>لا توجد وسائل دفع مفعلة حالياً — تواصل مع المعلم.</p>
              )}
              {enabledMethods.map((m) => {
                const Icon = methodIcons[m.id] || Landmark;
                const active = method === m.id;
                return (
                  <label
                    key={m.id}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px",
                      padding: "14px", borderRadius: "14px", cursor: "pointer",
                      border: active ? "2px solid #059669" : "1px solid var(--border-color)",
                      background: active ? "var(--bg-accent)" : "var(--bg-surface-secondary)",
                      boxShadow: active ? "0 0 0 4px rgba(5,150,105,0.10)" : "none",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <input type="radio" name="method" checked={active} onChange={() => setMethod(m.id)} style={{ accentColor: "#059669", width: "16px", height: "16px" }} />
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <span style={{ fontSize: "12.5px", fontWeight: 900, color: "var(--text-main)" }}>{m.label}</span>
                        <span style={{ fontSize: "10.5px", color: "var(--text-muted)" }}>تحويل فوري</span>
                      </div>
                    </div>
                    <Icon size={20} style={{ color: active ? "#059669" : "var(--text-muted)" }} />
                  </label>
                );
              })}
            </div>

            {/* Destination panel */}
            {selectedMethod?.destination && (
              <div style={{ padding: "16px", borderRadius: "14px", background: "var(--bg-surface-secondary)", border: "1px dashed var(--border-color)", display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
                  <span style={{ fontSize: "12px", fontWeight: 900, color: "var(--text-main)", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    {(() => { const MIcon = methodIcons[selectedMethod.id] || Landmark; return <MIcon size={14} />; })()}
                    بيانات التحويل — {selectedMethod.label}
                  </span>
                  <button
                    type="button"
                    onClick={() => void copyDestination(selectedMethod)}
                    style={{
                      display: "inline-flex", alignItems: "center", gap: "5px",
                      background: copiedId === selectedMethod.id ? "var(--bg-accent)" : "var(--bg-surface)",
                      border: "1px solid var(--border-color)", borderRadius: "9px",
                      padding: "6px 12px", fontSize: "11.5px", fontWeight: 800,
                      color: copiedId === selectedMethod.id ? "#059669" : "var(--text-main)", cursor: "pointer",
                    }}
                  >
                    {copiedId === selectedMethod.id ? <CheckCircle2 size={13} /> : <Copy size={13} />}
                    {copiedId === selectedMethod.id ? "تم النسخ" : "نسخ"}
                  </button>
                </div>
                <div style={{ fontFamily: "monospace", fontSize: "15px", fontWeight: 800, color: "#059669", direction: "ltr", textAlign: "center", letterSpacing: "0.5px", padding: "10px", background: "var(--bg-surface)", borderRadius: "10px", border: "1px solid var(--border-color)" }} dir="ltr">
                  {selectedMethod.destination}
                </div>
                <p style={{ margin: 0, fontSize: "11px", color: "var(--text-muted)" }}>
                  بعد التحويل، ارفع إيصال العملية أدناه — يراجعه المعلم ويُفعّل الدرس في حسابك فوراً.
                </p>
              </div>
            )}

            {/* Reference + note */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px", marginTop: "16px" }}>
              <label style={labelStyle}>
                مرجع التحويل (اختياري)
                <input style={inputStyle} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={160} placeholder="رقم العملية أو رقم الهاتف" />
              </label>
              <label style={labelStyle}>
                ملاحظة للمعلم (اختياري)
                <input style={inputStyle} value={note} onChange={(e) => setNote(e.target.value)} maxLength={4000} placeholder="أي تفاصيل تساعد في المراجعة" />
              </label>
            </div>

            {/* Receipt dropzone */}
            <label
              style={{
                marginTop: "16px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                gap: "7px", padding: "26px 18px", borderRadius: "14px", cursor: "pointer", textAlign: "center",
                border: receipt ? "2px solid #059669" : "2px dashed var(--border-color)",
                background: receipt ? "var(--bg-accent)" : "var(--bg-surface-secondary)",
                transition: "all 0.15s ease",
              }}
            >
              {receipt ? <CheckCircle2 size={26} style={{ color: "#059669" }} /> : <FileUp size={26} style={{ color: "#059669" }} />}
              <span style={{ fontSize: "13px", fontWeight: 900, color: "var(--text-main)" }}>
                {receipt ? receipt.name : "اختر صورة أو PDF لإيصال التحويل"}
              </span>
              <small style={{ fontSize: "11px", color: "var(--text-muted)" }}>JPG أو PNG أو WEBP أو PDF — بحد أقصى 20 ميجا</small>
              <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" style={{ display: "none" }} onChange={(event) => setReceipt(event.target.files?.[0] || null)} />
            </label>
            {busy && (
              <div style={{ marginTop: "12px", height: "7px", borderRadius: "4px", background: "var(--bg-surface-secondary)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${progress}%`, background: "linear-gradient(90deg, #059669, #10b981)", transition: "width 0.3s ease" }} />
              </div>
            )}

            {/* CTA */}
            <div style={{ marginTop: "22px", paddingTop: "18px", borderTop: "1px solid var(--border-color)" }}>
              <button
                type="button"
                onClick={submitPayment}
                disabled={busy || amount <= 0 || !method || !receipt}
                style={{
                  width: "100%", height: "52px", borderRadius: "14px",
                  background: "linear-gradient(135deg, #059669, #047857)",
                  color: "#ffffff", fontWeight: 900, fontSize: "14.5px",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: "10px",
                  border: "none", cursor: busy || amount <= 0 || !receipt ? "not-allowed" : "pointer",
                  opacity: busy || amount <= 0 || !receipt ? 0.55 : 1,
                  boxShadow: "0 8px 20px -6px rgba(5, 150, 105, 0.45)",
                }}
              >
                <LockKeyhole size={18} />
                <span>{busy ? `جارٍ الإرسال ${progress}%` : `إرسال الإيصال وتأكيد الدفع — ${amount.toLocaleString("ar-EG")} ج.م`}</span>
                <ArrowLeft size={17} />
              </button>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", marginTop: "10px", color: "var(--text-muted)", fontSize: "11px" }}>
                <ShieldCheck size={14} style={{ color: "#059669" }} />
                <span>بياناتك محمية — لا يتم عرض أو تخزين أي بيانات بنكية داخل المنصة</span>
              </div>
            </div>
          </section>
        </div>

        {/* ═══════════ LEFT COLUMN: order summary + guarantee + previous orders ═══════════ */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Course summary */}
          <section style={{ ...card, padding: "22px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", padding: "4px 10px", borderRadius: "8px", background: "#0f392b", color: "#ffffff", fontSize: "10.5px", fontWeight: 800 }}>
                <GraduationCap size={12} /> تفاصيل الطلب
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "4px 10px", borderRadius: "8px", background: "var(--bg-accent)", color: "#059669", border: "1px solid var(--border-accent)", fontSize: "10.5px", fontWeight: 800 }}>
                {student?.academicYearLabel || "المرحلة الثانوية"}
              </span>
            </div>

            {selectedLesson ? (
              <div style={{ borderRadius: "14px", overflow: "hidden", border: "1px solid var(--border-color)", background: "#021f18", color: "#ffffff", padding: "16px", marginBottom: "16px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "11px", fontFamily: "monospace", color: "#6ee7b7", paddingBottom: "10px", borderBottom: "1px solid rgba(110, 231, 183, 0.25)", marginBottom: "12px" }}>
                  <span style={{ fontSize: "13.5px", fontWeight: 900, color: "#6ee7b7" }}>{selectedLesson.courseTitle || "مقرر الكيمياء"}</span>
                  <span style={{ padding: "2px 8px", borderRadius: "6px", background: "rgba(6, 78, 59, 0.9)", color: "#a7f3d0", fontSize: "10.5px", fontWeight: 800, fontFamily: "inherit" }}>{student?.academicYearLabel || "منهج 2025"}</span>
                </div>
                <div style={{ paddingTop: "4px" }}>
                  <div style={{ fontSize: "11px", color: "#6ee7b7", fontWeight: 700, marginBottom: "4px" }}>درس مدفوع — تفعيل فردي</div>
                  <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 900, color: "#ffffff", lineHeight: 1.5 }}>{selectedLesson.title}</h3>
                  <div style={{ fontSize: "11px", color: "#d1fae5", fontWeight: 600, marginTop: "4px" }}>
                    {selectedLesson.durationFormatted || "درس فيديو + مذكرات + كويزات"}
                  </div>
                </div>
                <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid rgba(110, 231, 183, 0.25)", display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "11px", color: "#d1fae5" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
                    <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "#047857", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "10px", fontWeight: 900 }}>ح</div>
                    <span style={{ fontWeight: 800, color: "#ffffff" }}>مستر حسن شعبان</span>
                  </div>
                  <span style={{ fontSize: "10.5px", background: "rgba(2, 44, 34, 0.9)", padding: "2px 8px", borderRadius: "6px", color: "#6ee7b7", fontWeight: 700 }}>محاضرة مسجلة</span>
                </div>
              </div>
            ) : (
              <div style={{ borderRadius: "14px", border: "2px dashed var(--border-color)", padding: "26px 16px", textAlign: "center", marginBottom: "16px", color: "var(--text-muted)" }}>
                <GraduationCap size={30} style={{ margin: "0 auto 8px", color: "#059669" }} />
                <p style={{ margin: 0, fontSize: "12.5px", fontWeight: 700 }}>اختر الدرس من القائمة أعلاه لظهور تفاصيل الطلب</p>
              </div>
            )}

            {/* Lesson picker */}
            <label style={{ ...labelStyle, marginBottom: "12px", display: "block" }}>
              الدرس المطلوب تفعيله
              <select value={productId} onChange={(event) => setProductId(event.target.value)} style={{ ...inputStyle, marginTop: "5px" }}>
                <option value="">اختر درسًا</option>
                {lessons.filter((lesson) => Number(lesson.price || 0) > 0).map((lesson) => (
                  <option key={lesson.id} value={lesson.id}>{lesson.courseTitle} / {lesson.title} — {Number(lesson.price || 0).toLocaleString("ar-EG")} ج.م</option>
                ))}
              </select>
            </label>

            {/* What student gets */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "18px", paddingBottom: "18px", borderBottom: "1px solid var(--border-color)", fontSize: "11.5px", color: "var(--text-main)" }}>
              {[
                "شرح كامل لدرس الكيمياء بالفيديو عالي الجودة",
                "تحميل فوري لمذكرات الشرح والواجب بصيغة PDF",
                "كويزات تفاعلية تُصحح فورياً مع محاولات تدريب",
                "واجبات تُسلَّم وتُراجع من المعلم مباشرة",
              ].map((item) => (
                <div key={item} style={{ display: "flex", alignItems: "flex-start", gap: "9px" }}>
                  <CheckCircle2 size={16} style={{ color: "#059669", flexShrink: 0, marginTop: "1px" }} />
                  <span style={{ lineHeight: 1.6 }}>{item}</span>
                </div>
              ))}
            </div>

            {/* Financial breakdown */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "16px", borderRadius: "14px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", fontSize: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-muted)" }}>
                <span>سعر الدرس</span>
                <span>{amount ? `${amount.toLocaleString("ar-EG")} ج.م` : "—"}</span>
              </div>
              <div style={{ height: "1px", background: "var(--border-color)", margin: "2px 0" }} />
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                <span style={{ fontSize: "13px", fontWeight: 900, color: "var(--text-main)" }}>الإجمالي المطلوب</span>
                <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
                  <span style={{ fontSize: "24px", fontWeight: 900, color: "#059669" }}>{amount.toLocaleString("ar-EG")}</span>
                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#059669" }}>ج.م</span>
                </div>
              </div>
            </div>
          </section>

          {/* Guarantee */}
          <div style={{ ...card, padding: "18px", display: "flex", alignItems: "flex-start", gap: "13px" }}>
            <div style={{ width: "40px", height: "40px", borderRadius: "12px", background: "var(--bg-accent)", color: "#059669", border: "1px solid var(--border-accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <ShieldCheck size={20} />
            </div>
            <div>
              <h4 style={{ margin: "0 0 3px", fontSize: "12.5px", fontWeight: 900, color: "var(--text-main)" }}>ضمان المراجعة العادلة</h4>
              <p style={{ margin: 0, fontSize: "11px", color: "var(--text-muted)", lineHeight: 1.7 }}>
                كل إيصال يُراجع يدوياً من المعلم. لو حصل أي تأخير أو مشكلة في التفعيل بعد التحويل، تواصل معنا وسيتم حلها فوراً.
              </p>
            </div>
          </div>

          {/* Order history (moved to left column as requested) */}
          <section style={{ ...card, padding: "20px" }}>
            <div style={{ ...sectionHead, justifyContent: "space-between" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "14.5px", fontWeight: 900, color: "var(--text-main)" }}>طلباتك السابقة</h2>
                <p style={{ margin: "3px 0 0", fontSize: "11px", color: "var(--text-muted)" }}>تابع حالة مراجعة الإيصالات من هنا.</p>
              </div>
              <button type="button" onClick={() => void load()} aria-label="تحديث" title="تحديث حالة الطلبات" style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "8px", cursor: "pointer", color: "var(--text-main)", display: "flex" }}>
                <RefreshCw size={15} />
              </button>
            </div>
            {orders.length === 0 ? (
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
        </div>
      </div>

      {/* Trust badges - Centered */}
      <div
        style={{
          ...card,
          padding: "16px 24px",
          marginTop: "24px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "center",
          gap: "36px",
          fontSize: "12.5px",
          fontWeight: 700,
          color: "var(--text-main)",
          textAlign: "center",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
          <Zap size={18} style={{ color: "#059669" }} /> تفعيل فوري بعد تأكيد المعلم
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
          <ShieldCheck size={18} style={{ color: "#059669" }} /> مراجعة بشرية لكل إيصال
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
          <InfinityIcon size={18} style={{ color: "#059669" }} /> وصول مستمر طوال فترة المقرر
        </span>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "11.5px",
  fontWeight: 800,
  color: "var(--text-main)",
  marginBottom: "5px",
};

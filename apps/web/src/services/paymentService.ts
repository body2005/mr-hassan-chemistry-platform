import { apiRequest, fetchApiBlob, uploadWithProgress } from "./apiClient";

export type PaymentProductType = "course" | "lesson" | "ai_subscription";
export type PaymentMethod = "instapay" | "vodafone_cash" | "bank_transfer";
export type PaymentStatus = "pending" | "under_review" | "paid" | "rejected" | "cancelled";

export interface PaymentMethodConfig {
  id: PaymentMethod;
  label: string;
  destination: string | null;
  enabled: boolean;
}

export interface PaymentConfig {
  currency: "EGP";
  ai_monthly_price_egp: number;
  ai_subscription_days: number;
  ai_access_mode: "open" | "subscription_only" | "included_with_content" | "paid_content_or_subscription";
  methods: PaymentMethodConfig[];
}

export interface PaymentOrder {
  id: string;
  student_id: string;
  student_name?: string;
  product_type: PaymentProductType;
  product_id: string | null;
  product_name: string;
  amount_egp: number;
  payment_method: PaymentMethod;
  status: PaymentStatus;
  payer_reference?: string | null;
  has_receipt: boolean;
  student_note?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  created_at: string;
}

export interface StudentEntitlement {
  id: string;
  entitlement_type: "course" | "lesson" | "ai_global";
  resource_id: string | null;
  starts_at: string;
  expires_at: string | null;
  active: boolean;
}

export interface PaymentTarget {
  productType: PaymentProductType;
  productId?: string;
}

export const paymentService = {
  getConfig: () => apiRequest<PaymentConfig>("/payments/config", { cacheTtlMs: 300_000 }),
  getMyOrders: () => apiRequest<PaymentOrder[]>("/payments/me/orders", { cacheTtlMs: 15_000 }),
  getMyEntitlements: () => apiRequest<StudentEntitlement[]>("/payments/me/entitlements", { cacheTtlMs: 60_000 }),
  getAIAccess: (lessonId?: string) => apiRequest<{ allowed: boolean; global_subscription: boolean; mode: string }>(
    `/payments/me/ai-access${lessonId ? `?lesson_id=${encodeURIComponent(lessonId)}` : ""}`,
    { cacheTtlMs: 60_000 },
  ),
  createOrder: (payload: {
    product_type: PaymentProductType;
    product_id?: string;
    payment_method: PaymentMethod;
    payer_reference?: string;
    student_note?: string;
  }) => apiRequest<PaymentOrder>("/payments/orders", { method: "POST", body: JSON.stringify(payload) }),
  uploadReceipt: (
    orderId: string,
    receipt: File,
    payerReference?: string,
    onProgress?: (percent: number) => void,
  ) => {
    const form = new FormData();
    form.append("receipt", receipt);
    if (payerReference) form.append("payer_reference", payerReference);
    return uploadWithProgress<PaymentOrder>(`/payments/orders/${orderId}/receipt`, form, onProgress, 60_000);
  },
  getOrder: (orderId: string) => apiRequest<PaymentOrder>(`/payments/orders/${orderId}`, { cacheTtlMs: 30_000 }),
  listOrders: (status?: PaymentStatus) => apiRequest<PaymentOrder[]>(
    `/payments/orders${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    { cacheTtlMs: 15_000 },
  ),
  approve: (orderId: string, note?: string) => apiRequest<PaymentOrder>(`/payments/orders/${orderId}/approve`, {
    method: "POST",
    body: JSON.stringify({ note: note || undefined }),
  }),
  reject: (orderId: string, note?: string) => apiRequest<PaymentOrder>(`/payments/orders/${orderId}/reject`, {
    method: "POST",
    body: JSON.stringify({ note: note || undefined }),
  }),
  updateCoursePrice: (courseId: string, price: number) => apiRequest<{ id: string; price_egp: number }>(
    `/payments/pricing/courses/${courseId}`,
    { method: "PATCH", body: JSON.stringify({ price_egp: price }) },
  ),
  updateLessonPrice: (lessonId: string, price: number) => apiRequest<{ id: string; price_egp: number }>(
    `/payments/pricing/lessons/${lessonId}`,
    { method: "PATCH", body: JSON.stringify({ price_egp: price }) },
  ),
  async openReceipt(orderId: string): Promise<void> {
    const blob = await fetchApiBlob(`/payments/orders/${orderId}/receipt`);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
  async getReceiptBlobUrl(orderId: string): Promise<string> {
    const blob = await fetchApiBlob(`/payments/orders/${orderId}/receipt`);
    return URL.createObjectURL(blob);
  },
};

export interface LessonAccessRequest {
  id: string;
  student_id: string;
  student_name: string;
  student_phone?: string | null;
  lesson_id: string;
  lesson_title: string;
  course_id: string;
  course_title: string;
  status: "pending" | "approved" | "rejected";
  student_note?: string | null;
  reviewer_note?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export const lessonAccessService = {
  requestAccess: (lessonId: string, studentNote?: string) =>
    apiRequest<LessonAccessRequest>(`/lessons/${lessonId}/access-requests`, {
      method: "POST",
      body: JSON.stringify({ student_note: studentNote || undefined }),
    }),
  getRequest: (requestId: string) =>
    apiRequest<LessonAccessRequest>(`/lessons/access-requests/${requestId}`),
  approve: (requestId: string, note?: string) =>
    apiRequest<LessonAccessRequest>(`/lessons/access-requests/${requestId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note: note || undefined }),
    }),
  reject: (requestId: string, note?: string) =>
    apiRequest<LessonAccessRequest>(`/lessons/access-requests/${requestId}/reject`, {
      method: "POST",
      body: JSON.stringify({ note: note || undefined }),
    }),
  getMyRequests: () =>
    apiRequest<LessonAccessRequest[]>("/lessons/me/access-requests", { cacheTtlMs: 15_000 }),
};


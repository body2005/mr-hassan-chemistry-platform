const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api/v1").replace(/\/$/, "");
let sessionInvalidationDispatched = false;

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (normalized.startsWith("/api/v1/")) {
    const marker = API_BASE_URL.indexOf("/api/v1");
    const apiOrigin = marker >= 0 ? API_BASE_URL.slice(0, marker) : "";
    return `${apiOrigin}${normalized}`;
  }
  return `${API_BASE_URL}${normalized}`;
}

type ApiErrorBody = {
  error?: { code?: string; message?: string };
  detail?: string | { code?: string; message?: string };
};

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
  }
}

export interface ApiRequestInit extends RequestInit {
  timeoutMs?: number;
}

export async function fetchApiBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  const token = authToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { headers, credentials: "include" });
  } catch (error) {
    throw new ApiClientError("NETWORK_ERROR", "Unable to reach the API", 0, { cause: error });
  }
  if (!response.ok) {
    if (response.status === 401) clearStaleSession(path);
    throw new ApiClientError(`HTTP_${response.status}`, `Request failed (${response.status})`, response.status);
  }
  return response.blob();
}

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const raw = document.cookie.split(";").map((v) => v.trim()).find((v) => v.startsWith("matgar_csrf="));
  return raw ? decodeURIComponent(raw.split("=")[1]) : undefined;
}

export function authToken(): string | undefined {
  if (typeof localStorage === "undefined") return undefined;
  return localStorage.getItem("lms_session_token") || undefined;
}

function clearStaleSession(path: string): void {
  const normalized = path.replace(/^\/api\/v1/, "");
  if (normalized === "/auth/login" || normalized === "/auth/register") return;
  const hadSession = typeof localStorage !== "undefined"
    && Boolean(localStorage.getItem("lms_session_token") || localStorage.getItem("lms_cached_user"));
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem("lms_session_token");
    localStorage.removeItem("lms_cached_user");
  }
  if (hadSession && !sessionInvalidationDispatched && typeof window !== "undefined") {
    sessionInvalidationDispatched = true;
    window.dispatchEvent(new Event("lms_user_updated"));
  }
}

export async function apiRequest<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { timeoutMs = 30_000, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);
  const isFormData = typeof FormData !== "undefined" && requestInit.body instanceof FormData;
  if (requestInit.body && !isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const method = (requestInit.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const token = authToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const controller = new AbortController();
  let timer: number | undefined;
  if (typeof timeoutMs === "number" && timeoutMs > 0) {
    timer = window.setTimeout(() => controller.abort(), timeoutMs);
  }
  if (requestInit.signal) {
    if (requestInit.signal.aborted) controller.abort();
    else requestInit.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...requestInit,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiClientError("REQUEST_TIMEOUT", "Request timed out", 0, { cause: error });
    }
    throw new ApiClientError("NETWORK_ERROR", "Unable to reach the API", 0, { cause: error });
  } finally {
    if (timer !== undefined) window.clearTimeout(timer);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code = `HTTP_${response.status}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.error?.message) {
        message = body.error.message;
        code = body.error.code ?? code;
      } else if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail?.message) {
        message = body.detail.message;
        code = body.detail.code ?? code;
      }
    } catch {
      // Keep status-derived error if the body is not JSON.
    }
    if (response.status === 401) clearStaleSession(path);
    throw new ApiClientError(code, message, response.status);
  }
  if (path === "/auth/login" || path === "/auth/register") {
    sessionInvalidationDispatched = false;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number, loaded?: number, total?: number) => void,
  timeoutMs: number = 0,
  onXhrCreated?: (xhr: XMLHttpRequest) => void
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    if (onXhrCreated) {
      try {
        onXhrCreated(xhr);
      } catch (err) {
        console.error("onXhrCreated callback error", err);
      }
    }
    xhr.open("POST", apiUrl(path));
    xhr.withCredentials = true;
    if (timeoutMs > 0) xhr.timeout = timeoutMs;
    const csrf = csrfToken();
    if (csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
    const token = authToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          const pct = Math.round((event.loaded / event.total) * 100);
          onProgress(pct, event.loaded, event.total);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        if (xhr.status === 204) {
          resolve(undefined as T);
          return;
        }
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          resolve(xhr.responseText as unknown as T);
        }
      } else {
        let msg = `Upload failed (${xhr.status})`;
        let code = `HTTP_${xhr.status}`;
        try {
          if (xhr.responseText && xhr.responseText.trim()) {
            const err = JSON.parse(xhr.responseText) as {
              detail?: string | Array<string | { msg?: string }> | { message?: string };
              error?: { message?: string; code?: string };
            };
            if (err.detail) {
              if (typeof err.detail === "string") {
                msg = err.detail;
              } else if (Array.isArray(err.detail)) {
                msg = err.detail.map((d) => (typeof d === "string" ? d : d.msg || JSON.stringify(d))).join(", ");
              } else if (typeof err.detail === "object" && err.detail.message) {
                msg = err.detail.message;
              }
            } else if (err.error?.message) {
              msg = err.error.message;
            }
            if (err.error?.code) code = err.error.code;
          } else {
            if (xhr.status === 400 || xhr.status === 0) {
              msg = "فشل رفع الملف: انقطع الاتصال أو انتهت مهلة رفع الملف لكبر حجمه. يرجى إعادة المحاولة أو تقسيم الملف.";
            } else if (xhr.status === 413) {
              msg = "حجم الملف كبير جداً ويتجاوز الحد المسموح به للرفع في المرة الواحدة.";
            } else if (xhr.status === 504 || xhr.status === 408) {
              msg = "استغرقت عملية الرفع وقتاً أطول من المسموح به. يرجى التحقق من سرعة الإنترنت.";
            }
          }
        } catch {
          if (xhr.status === 400) {
            msg = "فشل رفع الملف: انقطع الاتصال أو انتهت مهلة الخادم. يرجى التحقق من سرعة الإنترنت والمحاولة مرة أخرى.";
          }
        }
        if (xhr.status === 401) clearStaleSession(path);
        console.error(`[Upload Error] Status: ${xhr.status}, Response:`, xhr.responseText);
        reject(new ApiClientError(code, msg, xhr.status));
      }
    };

    xhr.onerror = () => reject(new ApiClientError("NETWORK_ERROR", "فشل الاتصال بالخادم أثناء رفع الملف", 0));
    xhr.ontimeout = () => reject(new ApiClientError("REQUEST_TIMEOUT", "استغرقت عملية الرفع وقتاً أطول من المتوقع", 0));
    xhr.onabort = () => reject(new ApiClientError("ABORTED", "تم إلغاء رفع الملف", 0));

    xhr.send(formData);
  });
}

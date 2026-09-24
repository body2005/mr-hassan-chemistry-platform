const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api/v1").replace(/\/$/, "");
let sessionInvalidationDispatched = false;
let sessionKnownInvalid = false;
let refreshInFlight: Promise<boolean> | null = null;
let browserSessionActive = false;

/**
 * True once a request proved the session is gone (401 that did not survive a
 * refresh). Callers that merely re-probe identity can skip redundant /auth/me
 * calls until a successful login resets the flag.
 */
export function isSessionKnownInvalid(): boolean {
  return sessionKnownInvalid;
}

export function markBrowserSessionActive(active: boolean): void {
  browserSessionActive = active;
}

export function hasBrowserSession(): boolean {
  return browserSessionActive;
}

export function authToken(): string | undefined {
  if (typeof localStorage === "undefined") return undefined;
  return localStorage.getItem("lms_session_token") || undefined;
}

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
  cacheTtlMs?: number;
  skipCache?: boolean;
  cacheKey?: string;
}

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
  authScope: string;
}

const apiCache = new Map<string, CacheEntry<unknown>>();
const inFlightRequests = new Map<string, Promise<unknown>>();
let currentAuthScope = "anonymous";

export function setApiAuthScope(scope: string): void {
  const normalized = scope || "anonymous";
  if (currentAuthScope !== normalized) {
    currentAuthScope = normalized;
    clearApiCache();
  }
}

export function getApiAuthScope(): string {
  return currentAuthScope;
}

export function clearApiCache(): void {
  apiCache.clear();
}

export function getCachedData<T>(key: string): T | undefined {
  const entry = apiCache.get(key);
  if (!entry) return undefined;
  if (entry.expiresAt <= Date.now() || entry.authScope !== currentAuthScope) {
    apiCache.delete(key);
    return undefined;
  }
  return entry.data as T;
}

export function setCachedData<T>(key: string, data: T, ttlMs: number): void {
  apiCache.set(key, {
    data,
    expiresAt: Date.now() + Math.max(0, ttlMs),
    authScope: currentAuthScope,
  });
}

export function invalidateApiCache(patternOrPrefix?: string | RegExp): void {
  if (!patternOrPrefix) {
    apiCache.clear();
    return;
  }
  for (const key of Array.from(apiCache.keys())) {
    if (typeof patternOrPrefix === "string") {
      if (key.includes(patternOrPrefix)) {
        apiCache.delete(key);
      }
    } else if (patternOrPrefix.test(key)) {
      apiCache.delete(key);
    }
  }
}

function autoInvalidateOnMutation(path: string): void {
  const normalized = path.replace(/^\/api\/v1/, "");
  if (
    normalized.startsWith("/courses") ||
    normalized.startsWith("/quizzes") ||
    normalized.startsWith("/assignments") ||
    normalized.startsWith("/modules") ||
    normalized.startsWith("/questions")
  ) {
    invalidateApiCache("/courses");
  } else if (normalized.startsWith("/progress")) {
    invalidateApiCache("/progress");
    invalidateApiCache("/courses");
  } else if (normalized.startsWith("/submissions")) {
    invalidateApiCache("/submissions");
  } else if (normalized.startsWith("/users")) {
    invalidateApiCache("/users");
  } else if (normalized.startsWith("/notifications")) {
    invalidateApiCache("/notifications");
  } else if (normalized.startsWith("/calendar")) {
    invalidateApiCache("/calendar");
  } else if (normalized.startsWith("/payments")) {
    invalidateApiCache("/payments");
    invalidateApiCache("/courses");
  } else if (normalized.startsWith("/auth/logout") || normalized.startsWith("/auth/login") || normalized.startsWith("/auth/register")) {
    clearApiCache();
  }
}

export async function fetchApiBlob(path: string, retriedAfterRefresh = false): Promise<Blob> {
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
    if (response.status === 401 && !retriedAfterRefresh && !isAuthPath(path) && await refreshSession()) {
      return fetchApiBlob(path, true);
    }
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

function clearStaleSession(path: string): void {
  const normalized = path.replace(/^\/api\/v1/, "");
  if (["/auth/login", "/auth/register", "/auth/refresh"].includes(normalized)) return;
  sessionKnownInvalid = true;
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem("lms_session_token");
    localStorage.removeItem("lms_cached_user");
  }
  if (!sessionInvalidationDispatched && typeof window !== "undefined") {
    browserSessionActive = false;
    sessionInvalidationDispatched = true;
    window.dispatchEvent(new Event("lms_user_updated"));
  }
}

function isAuthPath(path: string): boolean {
  const normalized = path.replace(/^\/api\/v1/, "");
  return ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"].includes(normalized);
}

let lastFailedRefreshAt = 0;

async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  // A refresh that just failed means the session is genuinely gone; do not
  // hammer the endpoint once per subsequent 401 (storm guard).
  if (Date.now() - lastFailedRefreshAt < 10_000) return false;
  refreshInFlight = (async () => {
    const headers = new Headers();
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
    const token = authToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    try {
      const response = await fetch(apiUrl("/auth/refresh"), {
        method: "POST",
        headers,
        credentials: "include",
      });
      if (!response.ok) {
        lastFailedRefreshAt = Date.now();
        return false;
      }
      try {
        const body = await response.json();
        if (body?.token && typeof localStorage !== "undefined") {
          localStorage.setItem("lms_session_token", body.token);
        }
      } catch {}
      lastFailedRefreshAt = 0;
      browserSessionActive = true;
      sessionInvalidationDispatched = false;
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function executeRequest<T>(path: string, init: ApiRequestInit = {}, retriedAfterRefresh = false): Promise<T> {
  const { timeoutMs = 30_000, cacheTtlMs: _cacheTtlMs, skipCache: _skipCache, cacheKey: _cacheKey, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);
  const token = authToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const isFormData = typeof FormData !== "undefined" && requestInit.body instanceof FormData;
  if (requestInit.body && !isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const method = (requestInit.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
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
    if (requestInit.signal?.aborted) {
      // Caller-initiated cancellation (component unmount / page change).
      // Never label this as a timeout so callers cannot mistake it for a
      // failure and retry it.
      throw new ApiClientError("REQUEST_CANCELLED", "Request cancelled", 0, { cause: error });
    }
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
    if (response.status === 401 && !retriedAfterRefresh && !isAuthPath(path) && await refreshSession()) {
      return executeRequest<T>(path, init, true);
    }
    if (response.status === 401) clearStaleSession(path);
    throw new ApiClientError(code, message, response.status);
  }
  if (path === "/auth/login" || path === "/auth/register") {
    sessionInvalidationDispatched = false;
    sessionKnownInvalid = false;
    clearApiCache();
  }
  if (response.status === 204) return undefined as T;
  const json = (await response.json()) as T;
  if (json && typeof json === "object" && "token" in json && typeof (json as any).token === "string" && (json as any).token) {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("lms_session_token", (json as any).token);
    }
  }
  return json;
}

export async function apiRequest<T>(path: string, init: ApiRequestInit = {}, retriedAfterRefresh = false): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const isSafeMethod = method === "GET" || method === "HEAD";

  // Mutations bypass cache, are never deduplicated, and invalidate related cache entries on completion
  if (!isSafeMethod) {
    const result = await executeRequest<T>(path, init, retriedAfterRefresh);
    autoInvalidateOnMutation(path);
    return result;
  }

  const normalizedUrl = apiUrl(path);
  const cacheKey = init.cacheKey || `${method}:${normalizedUrl}`;
  const effectiveTtl = typeof init.cacheTtlMs === "number" ? init.cacheTtlMs : 15_000;

  // 1. Check client-side TTL cache
  if (!init.skipCache && effectiveTtl > 0) {
    const cached = apiCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now() && cached.authScope === currentAuthScope) {
      return cached.data as T;
    }
  }

  // 2. Check in-flight request deduplication
  if (!init.skipCache) {
    const inFlight = inFlightRequests.get(cacheKey);
    if (inFlight) {
      if (init.signal) {
        if (init.signal.aborted) {
          throw new ApiClientError("REQUEST_CANCELLED", "Request cancelled", 0);
        }
        return new Promise<T>((resolve, reject) => {
          const onAbort = () => reject(new ApiClientError("REQUEST_CANCELLED", "Request cancelled", 0));
          init.signal!.addEventListener("abort", onAbort, { once: true });
          inFlight
            .then((data) => {
              init.signal?.removeEventListener("abort", onAbort);
              resolve(data as T);
            })
            .catch((err) => {
              init.signal?.removeEventListener("abort", onAbort);
              reject(err);
            });
        });
      }
      return inFlight as Promise<T>;
    }
  }

  // 3. Initiate new request and share its promise while in-flight
  const requestPromise = executeRequest<T>(path, init, retriedAfterRefresh)
    .then((result) => {
      if (!init.skipCache && effectiveTtl > 0) {
        apiCache.set(cacheKey, {
          data: result,
          expiresAt: Date.now() + effectiveTtl,
          authScope: currentAuthScope,
        });
      }
      return result;
    })
    .finally(() => {
      inFlightRequests.delete(cacheKey);
    });

  if (!init.skipCache) {
    inFlightRequests.set(cacheKey, requestPromise);
  }

  return requestPromise;
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

import { reportRequestError } from './errorFeedback';

const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api/v1").replace(/\/$/, "");
let sessionInvalidationDispatched = false;
let sessionKnownInvalid = false;
type RefreshResult = 'renewed' | 'invalid' | 'transient' | 'cancelled';
let refreshInFlight: Promise<RefreshResult> | null = null;
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

function removeLegacySessionToken(): void {
  // Upgrade existing browsers without ever reading/using the old credential.
  try { localStorage.removeItem('lms_session_token'); } catch { /* storage can be unavailable */ }
}
removeLegacySessionToken();

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
  readonly retryAfterMs?: number;

  constructor(code: string, message: string, status: number, options?: { cause?: unknown; retryAfterMs?: number }) {
    super(message, options);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.retryAfterMs = options?.retryAfterMs;
  }
}

export interface ApiRequestInit extends RequestInit {
  /** Background telemetry failures must not interrupt the foreground task. */
  suppressErrorToast?: boolean;
  timeoutMs?: number;
  cacheTtlMs?: number;
  skipCache?: boolean;
  cacheKey?: string;
  /** Retained for callers; all browser requests now use HttpOnly cookies. */
  cookieOnly?: boolean;
}

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
  authScope: string;
}

const apiCache = new Map<string, CacheEntry<unknown>>();
const inFlightRequests = new Map<string, Promise<unknown>>();
let currentAuthScope = "anonymous";
let authScopeEpoch = 0;
let activeCourseReads = 0;
const queuedCourseReads: Array<() => void> = [];
let courseReadCooldown: { epoch: number; until: number; error: ApiClientError } | null = null;

function retryAfterMilliseconds(header: string | null): number | undefined {
  if (!header?.trim()) return undefined;
  const seconds = /^\d+$/.test(header.trim()) ? Number(header) : NaN;
  const delay = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(header) - Date.now();
  return Number.isFinite(delay) && delay > 0 ? delay : undefined;
}
const activeRequestControllers = new Set<AbortController>();

function drainCourseReads(): void {
  while (activeCourseReads < 4 && queuedCourseReads.length) queuedCourseReads.shift()!();
}

function boundedCourseRead<T>(run: () => Promise<T>, epoch: number, signal?: AbortSignal | null): Promise<T> {
  // Catalog hydration must leave capacity for video-token, auth and foreground
  // calls. This is not a retry policy and does not change server rate limits.
  return new Promise<T>((resolve, reject) => {
    queuedCourseReads.push(() => {
      if (epoch !== authScopeEpoch || signal?.aborted) {
        reject(new ApiClientError('REQUEST_CANCELLED', 'Request cancelled', 0));
        return;
      }
      if (courseReadCooldown?.epoch === epoch && courseReadCooldown.until > Date.now()) {
        // Cancel the queued batch, not the session. Never replay it on a timer
        // or let a fast 503/429 response drain hundreds of network requests.
        reject(courseReadCooldown.error);
        return;
      }
      activeCourseReads++;
      Promise.resolve().then(() => {
        if (epoch !== authScopeEpoch || signal?.aborted) {
          throw new ApiClientError('REQUEST_CANCELLED', 'Request cancelled', 0);
        }
        return run();
      }).then(resolve, error => {
        if (epoch === authScopeEpoch && error instanceof ApiClientError &&
            ([429, 502, 503, 504].includes(error.status) ||
             ['NETWORK_ERROR', 'REQUEST_TIMEOUT'].includes(error.code))) {
          courseReadCooldown = { epoch, until: Date.now() + (error.retryAfterMs ?? 2000), error };
        }
        reject(error);
      }).finally(() => { activeCourseReads--; drainCourseReads(); });
    });
    drainCourseReads();
  });
}

export function setApiAuthScope(scope: string, forceNewGeneration = false): void {
  const normalized = scope || "anonymous";
  if (currentAuthScope !== normalized || forceNewGeneration) {
    currentAuthScope = normalized;
    authScopeEpoch++;
    courseReadCooldown = null;
    lastFailedRefreshAt = 0;
    refreshInFlight = null;
    for (const controller of activeRequestControllers) controller.abort();
    clearApiCache();
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('lms_auth_scope_updated'));
  }
}

export function getApiAuthScope(): string {
  return currentAuthScope;
}

export function getApiAuthGeneration(): number {
  return authScopeEpoch;
}

/** Stop old-account work BEFORE sending logout. The logout request itself
 * still uses the captured credentials and must revoke the server session. */
export function beginBrowserLogout(): void {
  sessionKnownInvalid = true;
  browserSessionActive = false;
  setApiAuthScope('anonymous', true);
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
  if (normalized.startsWith('/quiz-attempts') || normalized.startsWith('/quizzes')) {
    invalidateApiCache('/quizzes');
    invalidateApiCache('/quiz-attempts');
    invalidateApiCache('/courses');
  }
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
  const requestEpoch = authScopeEpoch;
  const headers = new Headers();
  let response: Response;
  const controller = new AbortController();
  activeRequestControllers.add(controller);
  try {
    response = await fetch(apiUrl(path), { headers, credentials: "include", signal: controller.signal });
  } catch (error) {
    if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0, { cause: error });
    throw new ApiClientError("NETWORK_ERROR", "Unable to reach the API", 0, { cause: error });
  } finally {
    activeRequestControllers.delete(controller);
  }
  if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
  if (!response.ok) {
    if (response.status === 401 && !retriedAfterRefresh && !isAuthPath(path)) {
      const refreshed = await refreshSession();
      if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
      if (refreshed === 'renewed') return fetchApiBlob(path, true);
      checkRefreshFailure(refreshed);
    }
    if (response.status === 401) clearStaleSession(path);
    throw new ApiClientError(`HTTP_${response.status}`, `Request failed (${response.status})`, response.status);
  }
  const blob = await response.blob();
  if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
  return blob;
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
  setApiAuthScope('anonymous');
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

function checkRefreshFailure(result: RefreshResult): void {
  if (result === 'cancelled') throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
  if (result === 'transient') throw new ApiClientError('SESSION_REFRESH_UNAVAILABLE',
    'تعذر تجديد الجلسة مؤقتًا. بياناتك محفوظة؛ حاول مرة أخرى بعد قليل.', 503);
}

async function refreshSession(): Promise<RefreshResult> {
  if (sessionKnownInvalid) return 'invalid';
  if (refreshInFlight) return refreshInFlight;
  // A temporary outage is not evidence of logout. No automatic retry loop;
  // further requests in this tab return a recoverable error during cooldown.
  if (lastFailedRefreshAt && Date.now() - lastFailedRefreshAt < 10_000) return 'transient';
  const refreshEpoch = authScopeEpoch;
  const pending = (async (): Promise<RefreshResult> => {
    const headers = new Headers();
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
    const controller = new AbortController();
    activeRequestControllers.add(controller);
    const timer = window.setTimeout(() => controller.abort(), 15_000);
    try {
      const response = await fetch(apiUrl("/auth/refresh"), {
        method: "POST",
        headers,
        credentials: "include",
        signal: controller.signal,
      });
      if (refreshEpoch !== authScopeEpoch) return 'cancelled';
      if (!response.ok) {
        // 403 may be stale CSRF/proxy policy, not a revoked credential.
        if (response.status === 401) return 'invalid';
        lastFailedRefreshAt = Date.now();
        return 'transient';
      }
      removeLegacySessionToken();
      lastFailedRefreshAt = 0;
      browserSessionActive = true;
      sessionInvalidationDispatched = false;
      sessionKnownInvalid = false;
      return 'renewed';
    } catch {
      if (refreshEpoch !== authScopeEpoch) return 'cancelled';
      lastFailedRefreshAt = Date.now();
      return 'transient';
    } finally {
      window.clearTimeout(timer);
      activeRequestControllers.delete(controller);
    }
  })();
  refreshInFlight = pending;
  void pending.finally(() => { if (refreshInFlight === pending) refreshInFlight = null; });
  return pending;
}

async function executeRequest<T>(path: string, init: ApiRequestInit = {}, retriedAfterRefresh = false): Promise<T> {
  const requestEpoch = authScopeEpoch;
  const timeoutMs = init.timeoutMs ?? 30_000;
  const requestInit = { ...init };
  delete requestInit.timeoutMs;
  delete requestInit.suppressErrorToast;
  delete requestInit.cacheTtlMs;
  delete requestInit.skipCache;
  delete requestInit.cacheKey;
  delete requestInit.cookieOnly;
  const headers = new Headers(requestInit.headers);
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
  activeRequestControllers.add(controller);
  try {
    response = await fetch(apiUrl(path), {
      ...requestInit,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (error) {
    if (requestInit.signal?.aborted || requestEpoch !== authScopeEpoch) {
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
    activeRequestControllers.delete(controller);
    if (timer !== undefined) window.clearTimeout(timer);
  }

  if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
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
    if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
    if (response.status === 401 && !retriedAfterRefresh && !isAuthPath(path)) {
      const refreshed = await refreshSession();
      if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
      if (refreshed === 'renewed') return executeRequest<T>(path, init, true);
      checkRefreshFailure(refreshed);
    }
    if (response.status === 401) clearStaleSession(path);
    if (response.status === 401 && path.replace(/^\/api\/v1/, '') === '/auth/login') {
      message = 'البريد الإلكتروني أو كلمة المرور غير صحيحة. تأكد من بيانات الحساب.';
    }
    throw new ApiClientError(code, message, response.status, {
      retryAfterMs: retryAfterMilliseconds(response.headers.get('Retry-After')),
    });
  }
  if (path === "/auth/login" || path === "/auth/register") {
    sessionInvalidationDispatched = false;
    sessionKnownInvalid = false;
    lastFailedRefreshAt = 0;
    clearApiCache();
  }
  if (response.status === 204) return undefined as T;
  const json = (await response.json()) as T;
  if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
  removeLegacySessionToken();
  return json;
}

export async function apiRequest<T>(path: string, init: ApiRequestInit = {}, retriedAfterRefresh = false): Promise<T> {
  // A proven expired session cannot recover through repeated private probes.
  // Public browsing and an explicit login remain available; server protection
  // and rate limits are unchanged.
  if (sessionKnownInvalid && /^\/(?:auth\/me|progress\/me|video-uploads)(?:[/?]|$)/.test(path.replace(/^\/api\/v1/, ''))) {
    throw new ApiClientError('SESSION_EXPIRED', 'انتهت جلسة الدخول. سجّل الدخول مجددًا للمتابعة.', 401);
  }
  const method = (init.method || "GET").toUpperCase();
  const isSafeMethod = method === "GET" || method === "HEAD";
  // Legacy solve GET starts a persisted attempt; it is not a cacheable or
  // deduplicatable read. Enforce this centrally for every caller.
  if (method === 'GET' && /^\/quizzes\/[^/?]+\/solve(?:[?]|$)/.test(path.replace(/^\/api\/v1/, ''))) {
    init = { ...init, skipCache: true, cache: 'no-store' };
  }

  // Mutations bypass cache, are never deduplicated, and invalidate related cache entries on completion
  if (!isSafeMethod) {
    try {
      const result = await executeRequest<T>(path, init, retriedAfterRefresh);
      autoInvalidateOnMutation(path);
      return result;
    } catch (error) {
      if (!init.suppressErrorToast && !/^\/(?:api\/v1\/)?auth\/(?:logout|refresh)(?:[/?]|$)/.test(path)) reportRequestError(error);
      throw error;
    }
  }

  const normalizedUrl = apiUrl(path);
  const cacheKey = init.cacheKey || `${method}:${normalizedUrl}${init.cookieOnly ? ':cookie-only' : ''}`;
  const requestEpoch = authScopeEpoch;
  const requestScope = currentAuthScope;
  const inFlightKey = `${requestEpoch}:${cacheKey}`;
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
    const inFlight = inFlightRequests.get(inFlightKey);
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
  const execute = () => executeRequest<T>(path, init, retriedAfterRefresh);
  const isCourseHydration = method === 'GET' && /^\/courses\/[^/?]+(?:\/assessments)?(?:\?|$)/.test(path);
  const requestPromise = (isCourseHydration ? boundedCourseRead(execute, requestEpoch, init.signal) : execute())
    .then((result) => {
      if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
      if (!init.skipCache && effectiveTtl > 0) {
        apiCache.set(cacheKey, {
          data: result,
          expiresAt: Date.now() + effectiveTtl,
          authScope: requestScope,
        });
      }
      return result;
    })
    .finally(() => {
      if (inFlightRequests.get(inFlightKey) === requestPromise) inFlightRequests.delete(inFlightKey);
    });

  if (!init.skipCache) {
    inFlightRequests.set(inFlightKey, requestPromise);
  }

  return requestPromise;
}

export async function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number, loaded?: number, total?: number) => void,
  timeoutMs: number = 0,
  onXhrCreated?: (xhr: XMLHttpRequest) => void
): Promise<T> {
  const requestEpoch = authScopeEpoch;
  // Renew before sending potentially large/non-idempotent multipart bytes.
  // A temporary refresh outage is not logout, and must not start a transfer.
  await apiRequest('/auth/me', { skipCache: true, cacheTtlMs: 0 });
  if (requestEpoch !== authScopeEpoch) throw new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const controller = new AbortController();
    let settled = false;
    const changedAccount = () => requestEpoch !== authScopeEpoch;
    const cancelled = () => new ApiClientError('REQUEST_CANCELLED', 'Account changed', 0);
    const finish = (error?: unknown, value?: T) => {
      if (settled) return;
      settled = true;
      activeRequestControllers.delete(controller);
      controller.signal.removeEventListener('abort', abortUpload);
      if (error !== undefined) { reportRequestError(error); reject(error); }
      else resolve(value as T);
    };
    const abortUpload = () => {
      xhr.abort();
      finish(cancelled()); // DONE XHRs need not emit an abort event.
    };
    activeRequestControllers.add(controller);
    controller.signal.addEventListener('abort', abortUpload, { once: true });
    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (event) => {
        if (!settled && !changedAccount() && event.lengthComputable && event.total > 0) {
          const pct = Math.round((event.loaded / event.total) * 100);
          onProgress(pct, event.loaded, event.total);
        }
      };
    }

    xhr.onload = async () => {
      if (settled) return;
      if (changedAccount()) { finish(cancelled()); return; }
      if (xhr.status >= 200 && xhr.status < 300) {
        if (xhr.status === 204) {
          finish();
          return;
        }
        try {
          finish(undefined, JSON.parse(xhr.responseText) as T);
        } catch {
          finish(undefined, xhr.responseText as unknown as T);
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
        try {
          if (xhr.status === 401) {
            const refreshed = await refreshSession();
            if (settled) return;
            if (changedAccount()) { finish(cancelled()); return; }
            if (refreshed === 'renewed') {
              // Do not blindly replay bytes: some upload endpoints do not
              // provide a replay/idempotency contract. Let the user retry.
              finish(new ApiClientError('UPLOAD_RETRY_REQUIRED',
                'تم تجديد الجلسة. لم يكتمل الرفع؛ تحقق من حالة الملف ثم أعد المحاولة.', 401));
              return;
            }
            checkRefreshFailure(refreshed);
            // Do not abort this completed XHR while invalidating its scope.
            activeRequestControllers.delete(controller);
            clearStaleSession(path);
          }
          finish(new ApiClientError(code, msg, xhr.status));
        } catch (error) { finish(error); }
      }
    };

    xhr.onerror = () => finish(changedAccount() ? cancelled() : new ApiClientError("NETWORK_ERROR", "فشل الاتصال بالخادم أثناء رفع الملف", 0));
    xhr.ontimeout = () => finish(changedAccount() ? cancelled() : new ApiClientError("REQUEST_TIMEOUT", "استغرقت عملية الرفع وقتاً أطول من المتوقع", 0));
    xhr.onabort = () => finish(changedAccount() ? cancelled() : new ApiClientError("ABORTED", "تم إلغاء رفع الملف", 0));

    try {
      xhr.open("POST", apiUrl(path));
      xhr.withCredentials = true;
      if (timeoutMs > 0) xhr.timeout = timeoutMs;
      const csrf = csrfToken();
      if (csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
      onXhrCreated?.(xhr);
      if (changedAccount()) { finish(cancelled()); return; }
      // abort() before send() need not emit an event in real browsers.
      if (xhr.readyState === XMLHttpRequest.UNSENT) {
        finish(new ApiClientError('ABORTED', 'تم إلغاء رفع الملف', 0));
        return;
      }
      if (!settled) xhr.send(formData);
    } catch (error) { finish(error); }
  });
}

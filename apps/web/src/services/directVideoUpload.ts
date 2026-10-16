import { apiRequest } from "./apiClient";

export interface VideoUploadSession {
  id: string;
  status: string;
  part_bytes: number;
  size_bytes: number;
  fingerprint: string;
  uploaded_parts: { number: number; size_bytes: number }[];
  error_code?: string;
  retryable?: boolean;
  processing_percent?: number | null;
  processing_stage?: string | null;
}

/** Small bounded file identity for re-selection, NOT a full-file checksum. */
export async function videoFingerprint(file: File): Promise<string> {
  const edge = 1024 * 1024;
  const first = await file.slice(0, edge).arrayBuffer();
  const last = await file.slice(Math.max(edge, file.size - edge)).arrayBuffer();
  const identity = new TextEncoder().encode(`${file.size}:${file.name}:`);
  const bytes = new Uint8Array(identity.length + first.byteLength + last.byteLength);
  bytes.set(identity);
  bytes.set(new Uint8Array(first), identity.length);
  bytes.set(new Uint8Array(last), identity.length + first.byteLength);
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(v => v.toString(16).padStart(2, "0")).join("");
}

export function putVideoPart(url: string, part: Blob, progress: (bytes: number) => void, onXhr: (xhr: XMLHttpRequest) => void | boolean): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let settled = false;
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      xhr.upload.onprogress = null;
      xhr.onload = xhr.onerror = xhr.ontimeout = xhr.onabort = null;
      if (error) reject(error); else resolve();
    };
    xhr.open("PUT", url);
    xhr.withCredentials = false; // Never leak app cookies/Bearer to the store.
    xhr.timeout = 180_000;
    xhr.upload.onprogress = e => progress(e.loaded);
    xhr.onload = () => finish(xhr.status >= 200 && xhr.status < 300 ? undefined : new Error(`تعذر رفع الجزء (${xhr.status}). أعد المحاولة لاستئناف الرفع.`));
    xhr.onerror = () => finish(new Error("انقطع الاتصال؛ الأجزاء المكتملة محفوظة. أعد المحاولة."));
    xhr.ontimeout = () => finish(new Error("انتهت مهلة رفع الجزء؛ يمكنك الاستئناف."));
    xhr.onabort = () => finish(new Error("تم إيقاف نقل الجزء."));
    try {
      if (onXhr(xhr) === false) {
        finish(new Error("تم إيقاف نقل الجزء."));
        xhr.abort();
      }
      if (!settled) xhr.send(part);
    } catch (error) {
      finish(error instanceof Error ? error : new Error("تعذر بدء رفع الجزء."));
    }
  });
}

/** Three signed PUTs per file (at most six across the manager's two tasks).
 * Completed server parts are skipped; only in-flight slices are retained.
 * Drain cancelled siblings before allowing the caller to retry or complete. */
export async function uploadVideoParts(session: VideoUploadSession, file: File, options: {
  active: () => boolean;
  signal: AbortSignal;
  progress: (bytes: number) => void;
  partComplete: () => void;
}): Promise<void> {
  const completed = new Set(session.uploaded_parts.map(part => part.number));
  const totalParts = Math.ceil(session.size_bytes / session.part_bytes);
  let completedBytes = session.uploaded_parts.reduce((sum, part) => sum + part.size_bytes, 0);
  let reportedBytes = completedBytes;
  let nextNumber = 1;
  let failed = false;
  let failure: unknown;
  const pendingBytes = new Map<number, number>();
  const transfers = new Set<XMLHttpRequest>();
  const stopped = () => failed || options.signal.aborted || !options.active();
  const stop = (error: unknown) => {
    if (failed) return;
    failed = true; failure = error;
    for (const xhr of transfers) xhr.abort();
  };
  const cancel = () => stop(new Error("تم إيقاف نقل أجزاء الفيديو؛ يمكنك استئناف الأجزاء المحفوظة."));
  const report = () => {
    if (stopped()) { cancel(); return; }
    const bytes = completedBytes + [...pendingBytes.values()].reduce((sum, loaded) => sum + loaded, 0);
    reportedBytes = Math.max(reportedBytes, Math.min(session.size_bytes, bytes));
    options.progress(reportedBytes);
  };
  const worker = async () => {
    try {
      while (!stopped()) {
        while (completed.has(nextNumber)) nextNumber++;
        if (nextNumber > totalParts) return;
        const number = nextNumber++;
        const signed = await apiRequest<{ url: string; size_bytes: number }>(`/video-uploads/${session.id}/parts/${number}`, { method: "POST" });
        if (stopped()) { cancel(); return; }
        const start = (number - 1) * session.part_bytes;
        const size = Math.min(session.part_bytes, session.size_bytes - start);
        if (signed.size_bytes !== size) throw new Error("تعذر التحقق من حجم جزء الفيديو. أعد المحاولة.");
        const part = file.slice(start, start + size);
        let transfer: XMLHttpRequest | undefined;
        pendingBytes.set(number, 0);
        try {
          await putVideoPart(signed.url, part, bytes => {
            pendingBytes.set(number, Math.max(pendingBytes.get(number) ?? 0, Math.min(size, bytes)));
            report();
          }, xhr => {
            transfer = xhr;
            transfers.add(xhr);
            return !stopped();
          });
        } finally {
          if (transfer) transfers.delete(transfer);
          pendingBytes.delete(number);
        }
        if (stopped()) { cancel(); return; }
        completedBytes += size;
        report();
        options.partComplete();
      }
      cancel();
    } catch (error) { stop(error); }
  };
  options.signal.addEventListener("abort", cancel);
  try {
    if (stopped()) cancel();
    report();
    await Promise.all(Array.from({ length: Math.min(3, totalParts - completed.size) }, worker));
    if (stopped()) { cancel(); throw failure; }
  } finally {
    options.signal.removeEventListener("abort", cancel);
  }
}

export async function waitForVideo(id: string, active: () => boolean, update: (session: VideoUploadSession) => void): Promise<void> {
  const deadline = Date.now() + 48 * 3600_000;
  while (active() && Date.now() < deadline) {
    const session = await apiRequest<VideoUploadSession>(`/video-uploads/${id}`, { cacheTtlMs: 0 });
    update(session);
    if (session.status === "ready") return;
    if (["failed", "cancelled", "expired", "superseded", "aborted", "rejected"].includes(session.status)) throw new Error(videoUploadFailure(session.error_code));
    // Deliberately NO retry on 401, 429 or 503; the caller offers an explicit
    // resume button. Polling is bounded, even if a worker never recovers.
    await new Promise(resolve => window.setTimeout(resolve, 5000));
  }
  throw new Error("توقفت متابعة رفع الفيديو. أعد المحاولة للتحقق من حالته؛ الأجزاء المحفوظة لن تُرفع مرة أخرى.");
}

export const VIDEO_UPLOAD_LABEL = 'جاري رفع الفيديو…';

/** Weighted completed work, NOT elapsed time or an ETA. Transfer owns 0–10;
 * worker source transfer 10–15, encoded timeline 15–75, durable outputs 75–99.
 * Leave meaningful room for the slower server stages, without a timer or ETA.
 * Only the authoritative ready acknowledgement is allowed to set 100. */
export function videoOverallProgress(uploadPercent: number, processingPercent?: number | null): number {
  const bounded = (value: number) => Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
  if (processingPercent == null) return Math.floor(bounded(uploadPercent) * 0.1);
  const processing = bounded(processingPercent);
  return Math.min(99, Math.floor(processing <= 5 ? 10 + processing
    : processing <= 85 ? 15 + (processing - 5) * 0.75
    : 75 + (processing - 85) * 24 / 14));
}

export function videoUploadFailure(code?: string | null): string {
  if (code === 'VIDEO_WORKER_MEMORY_TOO_LOW' || code === 'VIDEO_OUTPUT_LIMIT_EXCEEDED') {
    return 'تعذر إكمال رفع الفيديو بسبب عدم كفاية موارد جهاز الرفع. وفّر مساحة وذاكرة ثم أعد المحاولة.';
  }
  if (code === 'VIDEO_DECODE_FAILED' || code === 'VIDEO_INVALID_METADATA' || code === 'VIDEO_LIMIT_EXCEEDED') {
    return 'تعذر إكمال رفع الفيديو. تحقق من سلامة الملف وصيغته ثم أعد المحاولة.';
  }
  return 'لم يكتمل رفع الفيديو. أعد المحاولة؛ سيُستكمل من الأجزاء المحفوظة متى كانت متاحة.';
}

import { apiRequest } from "./apiClient";

export interface VideoUploadSession {
  id: string;
  status: string;
  part_bytes: number;
  size_bytes: number;
  fingerprint: string;
  uploaded_parts: { number: number; size_bytes: number }[];
  error_code?: string;
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

export function putVideoPart(url: string, part: Blob, progress: (bytes: number) => void, onXhr: (xhr: XMLHttpRequest) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.withCredentials = false; // Never leak app cookies/Bearer to the store.
    xhr.timeout = 180_000;
    xhr.upload.onprogress = e => progress(e.loaded);
    xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`تعذر رفع الجزء (${xhr.status}). أعد المحاولة لاستئناف الرفع.`));
    xhr.onerror = () => reject(new Error("انقطع الاتصال؛ الأجزاء المكتملة محفوظة. أعد المحاولة."));
    xhr.ontimeout = () => reject(new Error("انتهت مهلة رفع الجزء؛ يمكنك الاستئناف."));
    xhr.onabort = () => reject(new Error("تم إيقاف نقل الجزء."));
    onXhr(xhr);
    xhr.send(part);
  });
}

export async function waitForVideo(id: string, active: () => boolean, update: (session: VideoUploadSession) => void): Promise<void> {
  const deadline = Date.now() + 2 * 3600_000;
  while (active() && Date.now() < deadline) {
    const session = await apiRequest<VideoUploadSession>(`/video-uploads/${id}`, { cacheTtlMs: 0 });
    update(session);
    if (session.status === "ready") return;
    if (["failed", "cancelled", "expired", "superseded"].includes(session.status)) throw new Error(`تعذر تجهيز الفيديو: ${session.error_code || session.status}`);
    // Deliberately NO retry on 401, 429 or 503; the caller offers an explicit
    // resume button. Polling is bounded, even if a worker never recovers.
    await new Promise(resolve => window.setTimeout(resolve, 5000));
  }
  throw new Error("توقفت متابعة المعالجة؛ يمكنك التحقق مجددًا دون إعادة رفع الملف.");
}

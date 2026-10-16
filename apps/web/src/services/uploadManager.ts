/**
 * Global Background Upload Manager (LMS Cloud Ingestion Engine)
 *
 * Enables non-blocking background uploads for large lesson videos and lesson
 * materials (PDF/Word notes). Uploads persist across internal page navigation,
 * view changes, modal dismissals, and browser reloads.
 *
 * Materials are stored standalone on the backend (lesson_assets); there is no
 * AI indexing, RAG, or knowledge-center polling in this pipeline anymore.
 */

import { courseService } from "./lmsService";
import { ApiClientError, apiRequest, uploadWithProgress, getApiAuthScope, getApiAuthGeneration,
  invalidateApiCache, isSessionKnownInvalid } from "./apiClient";
import { validateLessonUpload } from "./uploadLimits";
import { uploadVideoParts, videoFingerprint, waitForVideo, videoOverallProgress, videoUploadFailure, VIDEO_UPLOAD_LABEL, type VideoUploadSession } from "./directVideoUpload";

export type UploadType = "lesson_video" | "lesson_material";
export type UploadStatus = "queued" | "uploading" | "processing" | "completed" | "error" | "cancelled";

export interface UploadTask {
  id: string;
  title: string;
  fileName: string;
  fileSizeBytes: number;
  loadedBytes?: number;
  formattedSize: string;
  progress: number; // Video: monotonic end-to-end progress; 100 only after ready.
  videoProgressVersion?: 1;
  uploadPercent: number;
  status: UploadStatus;
  statusDetail?: string;
  error?: string;
  type: UploadType;
  lessonId?: string;
  courseId?: string;
  gradeLevel?: string;
  createdAt: number;
  completedAt?: number;
  file?: File;
  files?: File[];
  xhr?: XMLHttpRequest;
  onSuccess?: () => void;
  videoUploadId?: string;
  videoRequestKey?: string;
  videoFingerprint?: string;
  ownerScope?: string;
}

interface ServerMaterial {
  id: string;
  lesson_id: string;
  filename: string;
  size_bytes?: number;
}

const STORAGE_KEY = "lms_global_upload_tasks_v3";

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export class UploadManager {
  private tasks: UploadTask[] = [];
  private listeners: Set<(tasks: UploadTask[]) => void> = new Set();
  private maxConcurrent = 2;
  private isProcessingQueue = false;
  private running = new Set<string>();
  private videoTransfers = new Map<string, AbortController>();

  public async prepareVideo(lessonId: string, title: string, courseId: string): Promise<void> {
    const ownerScope = getApiAuthScope();
    const generation = getApiAuthGeneration();
    const session = await apiRequest<VideoUploadSession>(`/lessons/${lessonId}/prepare-video`, { method: 'POST' });
    if (generation !== getApiAuthGeneration() || ownerScope !== getApiAuthScope()) return;
    if (this.tasks.some(task => task.videoUploadId === session.id)) return;
    this.tasks.unshift({ id: crypto.randomUUID(), title, fileName: title, fileSizeBytes: session.size_bytes,
      formattedSize: formatFileSize(session.size_bytes), progress: videoOverallProgress(100, session.processing_percent ?? 0), uploadPercent: 100,
      videoProgressVersion: 1, status: 'processing', statusDetail: VIDEO_UPLOAD_LABEL,
      type: 'lesson_video', lessonId, courseId, createdAt: Date.now(), videoUploadId: session.id, ownerScope });
    this.persistTasks(); this.notify();
    void this.reconcileVideos();
  }

  private owns(task: UploadTask): boolean {
    return !!task.ownerScope && task.ownerScope === getApiAuthScope() && task.ownerScope !== 'anonymous';
  }

  public pauseOtherAccounts(): void {
    for (const task of this.tasks) {
      if (this.owns(task) || !['uploading', 'queued', 'processing'].includes(task.status)) continue;
      this.videoTransfers.get(task.id)?.abort();
      task.xhr?.abort();
      task.status = 'error';
      task.error = 'توقفت المتابعة لتغيير جلسة الدخول؛ الملف المحفوظ على السيرفر لا يُحذف.';
    }
    this.notify(); this.persistTasks();
  }

  /** Reconcile stored jobs only after login. Legacy jobs bind only after the
   * server's owner check succeeds; no byte upload or terminal retry is automatic. */
  public async reconcileVideos(): Promise<void> {
    const scope = getApiAuthScope();
    const generation = getApiAuthGeneration();
    if (scope === 'anonymous' || isSessionKnownInvalid()) return;
    for (const task of this.tasks) {
      if (!task.videoUploadId || task.status === 'completed' || task.status === 'cancelled' || this.running.has(task.id)
        || (task.ownerScope && task.ownerScope !== scope)) continue;
      if (generation !== getApiAuthGeneration() || isSessionKnownInvalid()) return;
      this.running.add(task.id);
      let handedOff = false;
      try {
        const session = await apiRequest<VideoUploadSession>(`/video-uploads/${task.videoUploadId}`, { cacheTtlMs: 0 });
        if (generation !== getApiAuthGeneration() || !this.tasks.includes(task)) continue;
        task.ownerScope = scope;
        if (session.status === 'ready') this.completeVideo(task);
        else if (['queued', 'processing', 'completing'].includes(session.status)) {
          this.running.delete(task.id);
          handedOff = true;
          void this.startVideoUpload(task);
        } else {
          task.status = 'error';
          task.error = ['creating', 'uploading'].includes(session.status)
            ? 'انقطع رفع الفيديو قبل اكتماله. أعد المحاولة لاستئناف الأجزاء المحفوظة.'
            : videoUploadFailure(session.error_code);
          this.notify(); this.persistTasks();
        }
      } catch (error) {
        if (generation !== getApiAuthGeneration() || isSessionKnownInvalid()) return;
        if (this.owns(task)) {
          task.status = 'error'; task.error = this.videoError(error);
          this.notify(); this.persistTasks();
        }
        // An inaccessible legacy job is neither displayed nor reassigned.
      } finally {
        // startVideoUpload owns its own running marker after taking over.
        if (!handedOff) this.running.delete(task.id);
      }
    }
    this.processQueue();
  }

  private completeVideo(task: UploadTask): void {
    task.status = 'completed'; task.progress = 100; task.uploadPercent = 100;
    task.statusDetail = 'تم رفع الفيديو بنجاح';
    task.completedAt = Date.now(); task.error = undefined;
    invalidateApiCache('/courses');
    this.notify(); this.persistTasks();
    task.onSuccess?.();
    window.dispatchEvent(new CustomEvent('lms_courses_updated'));
  }

  constructor() {
    this.tasks = this.loadTasksFromStorage();
    this.initBeforeUnloadHandler();
  }

  private initBeforeUnloadHandler() {
    if (typeof window !== "undefined") {
      window.addEventListener("beforeunload", (e) => {
        // ONLY warn if an active byte transfer is in-flight across the wire
        // (uploading / queued). Once status === 'processing' the bytes are
        // already safely stored server-side.
        const hasInFlightTransfer = this.tasks.some(
          (t) => this.owns(t) && (t.status === "uploading" || t.status === "queued")
        );
        if (hasInFlightTransfer) {
          const warningMessage = "هناك ملفات جارٍ رفعها. إغلاق الصفحة الآن قد يوقف الرفع قبل اكتماله.";
          e.preventDefault();
          e.returnValue = warningMessage;
          return warningMessage;
        }
      });
    }
  }

  private loadTasksFromStorage(): UploadTask[] {
    if (typeof window === "undefined" || !window.localStorage) return [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed: UploadTask[] = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];

      const now = Date.now();
      // Retain tasks from the last 48 hours
      return parsed
        .filter((t) => now - (t.createdAt || 0) < 48 * 3600 * 1000)
        .map((t) => {
          const normalizedTask = {
            ...t,
            uploadPercent: t.uploadPercent ?? (t.status === "processing" || t.status === "completed" ? 100 : t.progress || 0),
          };
          if (t.type === 'lesson_video') {
            normalizedTask.progress = t.status === 'completed' ? 100 : t.videoProgressVersion === 1
              ? Math.min(99, t.progress || 0)
              : videoOverallProgress(normalizedTask.uploadPercent, t.status === 'processing' ? t.progress : undefined);
            normalizedTask.videoProgressVersion = 1;
            normalizedTask.statusDetail = VIDEO_UPLOAD_LABEL;
            if (t.status === 'error') normalizedTask.error = videoUploadFailure();
          }
          // If task was mid-upload over network when browser was closed, it was interrupted
          if (t.status === "uploading" || t.status === "queued" || t.status === "processing") {
            return {
              ...normalizedTask,
              status: "error",
              error: "توقف الرفع عند إغلاق المتصفح. أعد المحاولة لاستكماله.",
            } as UploadTask;
          }
          return normalizedTask;
        });
    } catch {
      return [];
    }
  }

  private persistTasks() {
    if (typeof window === "undefined" || !window.localStorage) return;
    try {
      // Omit non-serializable objects (file, files, xhr, onSuccess)
      const serializable = this.tasks.slice(0, 15).map((t) => {
        const copy: Partial<UploadTask> = { ...t };
        delete copy.file;
        delete copy.files;
        delete copy.xhr;
        delete copy.onSuccess;
        return copy;
      });
      localStorage.setItem(STORAGE_KEY, JSON.stringify(serializable));
    } catch (err) {
      console.warn("Failed to persist upload tasks to storage", err);
    }
  }

  public subscribe(listener: (tasks: UploadTask[]) => void): () => void {
    this.listeners.add(listener);
    listener(this.tasks);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    // React subscribers need a new array identity when a task mutates; without
    // this the progress/error UI remains stuck and the resume action is hidden.
    this.listeners.forEach((listener) => listener([...this.tasks]));
  }

  private notifyFailure(task: UploadTask) {
    if (typeof window === 'undefined') return;
    window.dispatchEvent(new CustomEvent('lms_toast_notification', { detail: {
      message: `فشل رفع ${task.title}: ${task.error}`, tone: 'danger',
    } }));
  }

  private videoError(error: unknown): string {
    if (error instanceof ApiClientError && error.status === 404) {
      return 'لم تعد عملية الرفع متاحة. أعد المحاولة لبدء رفع الفيديو من جديد.';
    }
    if (error instanceof ApiClientError && error.status === 401) {
      return 'انتهت جلسة الدخول. سجّل الدخول مجددًا ثم أعد المحاولة.';
    }
    return error instanceof Error ? error.message : videoUploadFailure();
  }

  private updateVideoProgress(task: UploadTask, processingPercent?: number | null): void {
    task.progress = Math.max(task.progress, videoOverallProgress(task.uploadPercent, processingPercent));
    task.progress = Math.min(99, task.progress);
    task.videoProgressVersion = 1;
    task.statusDetail = VIDEO_UPLOAD_LABEL;
  }

  public getTasks(): UploadTask[] {
    return this.tasks;
  }

  /**
   * Enqueue a batch upload of lesson materials (PDFs, docs) in the background.
   * Files are stored standalone against the lesson — no AI indexing involved.
   */
  public enqueueKnowledgeBatchUpload(params: {
    files: File[];
    courseId?: string;
    gradeLevel?: string;
    lessonId?: string;
    lessonTitle?: string;
    onSuccess?: () => void;
  }): string {
    params.files.forEach((file) => validateLessonUpload(file, "material"));
    const taskId = `mat_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const totalBytes = params.files.reduce((sum, f) => sum + f.size, 0);
    const count = params.files.length;
    const taskTitle = params.lessonTitle
      ? `مذكرات درس: ${params.lessonTitle} (${count} ${count === 1 ? "ملف" : "ملفات"})`
      : `رفع دفعة مستندات (${count} ${count === 1 ? "ملف" : "ملفات"})`;
    const task: UploadTask = {
      id: taskId,
      ownerScope: getApiAuthScope(),
      title: taskTitle,
      fileName: params.files[0]?.name + (count > 1 ? ` (+${count - 1} ملفات أخرى)` : ""),
      fileSizeBytes: totalBytes,
      formattedSize: formatFileSize(totalBytes),
      progress: 0,
      uploadPercent: 0,
      status: "queued",
      type: "lesson_material",
      courseId: params.courseId,
      gradeLevel: params.gradeLevel,
      lessonId: params.lessonId,
      createdAt: Date.now(),
      files: params.files,
      onSuccess: params.onSuccess,
    };

    this.tasks.unshift(task);
    this.notify();
    this.persistTasks();
    this.processQueue();
    return taskId;
  }

  /**
   * Enqueue a large lesson video upload in the background.
   */
  public enqueueVideoUpload(params: {
    lessonId: string;
    lessonTitle: string;
    file: File;
    courseId?: string;
    onSuccess?: () => void;
  }): string {
    validateLessonUpload(params.file, "video");
    const taskId = `vid_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const task: UploadTask = {
      id: taskId,
      ownerScope: getApiAuthScope(),
      title: `فيديو درس: ${params.lessonTitle}`,
      fileName: params.file.name,
      fileSizeBytes: params.file.size,
      formattedSize: formatFileSize(params.file.size),
      progress: 0,
      videoProgressVersion: 1,
      uploadPercent: 0,
      status: "queued",
      type: "lesson_video",
      lessonId: params.lessonId,
      courseId: params.courseId,
      createdAt: Date.now(),
      file: params.file,
      onSuccess: params.onSuccess,
    };

    this.tasks.unshift(task);
    this.notify();
    this.persistTasks();
    this.processQueue();
    return taskId;
  }

  private processQueue() {
    if (this.isProcessingQueue) return;
    this.isProcessingQueue = true;

    try {
      const activeCount = this.tasks.filter((t) => this.owns(t) && (t.status === "uploading" || t.status === "processing")).length;
      if (activeCount >= this.maxConcurrent) return;

      const nextTask = this.tasks.find((t) => this.owns(t) && t.status === "queued" && !this.running.has(t.id));
      if (!nextTask) return;

      if (nextTask.type === "lesson_video" && (nextTask.file || nextTask.videoUploadId) && nextTask.lessonId) {
        this.startVideoUpload(nextTask);
      } else if (nextTask.type === "lesson_material" && nextTask.files && nextTask.files.length > 0) {
        this.startMaterialBatchUpload(nextTask);
      }
    } finally {
      this.isProcessingQueue = false;
    }
  }

  private async startVideoUpload(task: UploadTask) {
    if (!this.owns(task) || this.running.has(task.id)) return;
    this.running.add(task.id);
    const generation = getApiAuthGeneration();
    const active = () => this.owns(task) && generation === getApiAuthGeneration() && this.tasks.includes(task) && task.status !== 'cancelled';
    task.status = "uploading";
    this.updateVideoProgress(task);
    this.notify();
    this.persistTasks();

    try {
      await apiRequest("/auth/me", { cacheTtlMs: 0 });
      if (!active()) return;
      const capabilities = await apiRequest<{ direct_upload: boolean; processing_enabled?: boolean }>("/video-upload-capabilities", { cacheTtlMs: 0 });
      if (!active()) return;
      if (capabilities.processing_enabled === false && !task.videoUploadId) {
        throw new Error('خدمة رفع الفيديو غير متاحة حاليًا. أعد المحاولة بعد تفعيلها.');
      }
      if (capabilities.direct_upload || task.videoUploadId) {
        await this.startDirectVideoUpload(task, active);
      } else {
        const uploaded = await courseService.uploadLessonVideo(
        task.lessonId!,
        task.file!,
        (percent) => {
          task.uploadPercent = Math.max(task.uploadPercent, Math.min(100, percent));
          this.updateVideoProgress(task);
          if (percent >= 100) {
            task.status = "processing";
          }
          this.notify();
          this.persistTasks();
        },
        (xhr) => {
          task.xhr = xhr;
        }
        );
        if (uploaded.video_upload_id && active()) {
          task.videoUploadId = uploaded.video_upload_id;
          task.status = 'processing';
          task.uploadPercent = 100;
          this.updateVideoProgress(task, 0);
          this.notify(); this.persistTasks();
          await waitForVideo(uploaded.video_upload_id, active, session => {
            if (!active()) return;
            this.updateVideoProgress(task, session.processing_percent ?? 0);
            this.notify(); this.persistTasks();
          });
        } else {
          throw new Error('لم يؤكد الخادم اكتمال رفع الفيديو. أعد المحاولة للتحقق من حالته.');
        }
      }
      if (!active()) return;
      this.completeVideo(task);
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("lms_toast_notification", {
            detail: {
              message: 'تم رفع الفيديو بنجاح',
              tone: "success",
            },
          })
        );
      }
    } catch (err: unknown) {
      if (active()) {
        task.status = "error";
        task.error = this.videoError(err);
        this.notify();
        this.persistTasks();
        if (typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("lms_toast_notification", {
              detail: {
                message: `❌ فشل رفع ${task.title}: ${task.error}`,
                tone: "danger",
              },
            })
          );
        }
      }
    } finally {
      this.running.delete(task.id);
      if (generation !== getApiAuthGeneration() && !['completed', 'cancelled'].includes(task.status)) {
        task.status = 'error';
        task.error = 'توقفت المتابعة لتغيير جلسة الدخول؛ الملف المحفوظ على السيرفر لا يُحذف.';
        this.notify(); this.persistTasks();
        if (this.owns(task) && !isSessionKnownInvalid()) void this.reconcileVideos();
      }
      this.processQueue();
    }
  }

  private async startDirectVideoUpload(task: UploadTask, active: () => boolean): Promise<void> {
    let session: VideoUploadSession;
    if (task.videoUploadId) {
      session = await apiRequest<VideoUploadSession>(`/video-uploads/${task.videoUploadId}`, { cacheTtlMs: 0 });
      if (!active()) return;
      if (session.status === 'failed' && session.retryable) {
        session = await apiRequest<VideoUploadSession>(`/video-uploads/${session.id}/retry`, { method: 'POST' });
        if (!active()) return;
      }
      if (["failed", "expired", "cancelled"].includes(session.status) && task.file) {
        // An explicit retry starts a new intent only for a terminal session.
        // Incomplete/processing sessions ALWAYS resume the existing intent.
        task.videoUploadId = undefined;
        task.videoRequestKey = undefined;
        task.uploadPercent = 0;
        task.loadedBytes = 0;
        return this.startDirectVideoUpload(task, active);
      }
    } else {
      if (!task.file) throw new Error('تعذر الوصول إلى ملف الفيديو. أعد المحاولة لاستكمال الرفع.');
      task.videoFingerprint = await videoFingerprint(task.file);
      if (!active()) return;
      task.videoRequestKey ??= crypto.randomUUID();
      this.persistTasks();
      session = await apiRequest<VideoUploadSession>(`/lessons/${task.lessonId}/video-uploads`, { method: "POST", body: JSON.stringify({
        filename: task.file.name, size_bytes: task.file.size,
        content_type: task.file.type || ({ mp4: "video/mp4", m4v: "video/mp4", mov: "video/quicktime", webm: "video/webm" } as Record<string, string>)[task.file.name.split(".").pop()!.toLowerCase()],
        fingerprint: task.videoFingerprint, request_key: task.videoRequestKey,
      }) });
      task.videoUploadId = session.id;
      this.persistTasks();
    }
    if (!active()) return;
    if (["creating", "uploading"].includes(session.status)) {
      if (!task.file) throw new Error('توقف رفع الفيديو قبل اكتماله. أعد المحاولة لاستكمال الرفع.');
      if (session.fingerprint !== await videoFingerprint(task.file)) throw new Error("الملف المختار مختلف عن الفيديو الأصلي.");
      const controller = new AbortController();
      this.videoTransfers.set(task.id, controller);
      try {
        await uploadVideoParts(session, task.file, {
          active, signal: controller.signal,
          progress: bytes => {
            if (!active()) return;
            task.loadedBytes = bytes;
            task.uploadPercent = Math.min(100, bytes / session.size_bytes * 100);
            this.updateVideoProgress(task);
            this.notify();
          },
          partComplete: () => this.persistTasks(),
        });
      } finally {
        if (this.videoTransfers.get(task.id) === controller) this.videoTransfers.delete(task.id);
      }
      if (!active()) return;
      session = await apiRequest<VideoUploadSession>(`/video-uploads/${session.id}/complete`, { method: "POST" });
    } else if (session.status === "completing") {
      session = await apiRequest<VideoUploadSession>(`/video-uploads/${session.id}/complete`, { method: "POST" });
    }
    task.status = "processing";
    task.uploadPercent = 100;
    this.updateVideoProgress(task, session.processing_percent ?? 0);
    this.notify();
    this.persistTasks();
    await waitForVideo(session.id, active, current => {
      if (!active()) return;
      this.updateVideoProgress(task, current.processing_percent ?? 0);
      this.notify(); this.persistTasks();
    });
  }

  private async startMaterialBatchUpload(task: UploadTask) {
    const generation = getApiAuthGeneration();
    const active = () => this.owns(task) && generation === getApiAuthGeneration() && this.tasks.includes(task) && task.status !== 'cancelled';
    if (!active()) return;
    if (!task.lessonId) {
      task.status = "error";
      task.error = "لا يمكن رفع المذكرات بدون تحديد الدرس.";
      this.notifyFailure(task);
      this.notify();
      this.persistTasks();
      return;
    }

    task.status = "uploading";
    task.progress = 1;
    this.notify();
    this.persistTasks();

    const files = task.files!;
    let uploadedCount = 0;

    for (const file of files) {
      try {
        // The shared multipart helper renews before bytes and never blindly
        // replays a non-idempotent upload after a 401.
        if (!active()) return;
        task.statusDetail = `جاري رفع: ${file.name}`;
        task.progress = Math.max(1, Math.round((uploadedCount / files.length) * 100));
        this.notify();

        const formData = new FormData();
        formData.append("file", file);

        await uploadWithProgress<ServerMaterial>(
          `/lessons/${task.lessonId}/materials`,
          formData,
          (percent, loaded) => {
            if (!active()) return;
            const perFileShare = 100 / files.length;
            const overall = uploadedCount * perFileShare + (percent / 100) * perFileShare;
            task.progress = Math.max(1, Math.min(99, Math.round(overall)));
            task.uploadPercent = Math.max(task.uploadPercent, Math.min(100, percent));
            if (typeof loaded === "number") {
              task.loadedBytes = loaded;
            }
            this.notify();
          },
          0,
          (xhr) => {
            if (!active()) { xhr.abort(); return; }
            task.xhr = xhr;
          }
        );

        uploadedCount += 1;
        if (!active()) return;
      } catch (err: unknown) {
        if (!active()) return;
        task.status = "error";
        const detail = err instanceof ApiClientError ? err.message : (err as Error)?.message;
        task.error = detail || "تعذر رفع الملفات. تأكد من سرعة الاتصال وحجم الملفات.";
        this.notifyFailure(task);
        this.notify();
        this.persistTasks();
        this.processQueue();
        return;
      }
    }

    task.status = "completed";
    task.progress = 100;
    task.uploadPercent = 100;
    task.completedAt = Date.now();
    task.files = undefined;
    invalidateApiCache('/courses');
    this.notify();
    this.persistTasks();

    task.onSuccess?.();
    if (typeof window !== "undefined") {
      if (task.courseId) {
        window.dispatchEvent(new CustomEvent("lms_courses_updated"));
      }
      window.dispatchEvent(
        new CustomEvent("lms_toast_notification", {
          detail: {
            message: `✅ تم حفظ مذكرات "${task.title}" على السحابة بنجاح.`,
            tone: "success",
          },
        })
      );
    }
    this.processQueue();
  }

  public cancelUpload(taskId: string) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task || !this.owns(task)) return;
    task.status = "cancelled";
    this.videoTransfers.get(task.id)?.abort();
    if (task.videoUploadId) {
      void apiRequest(`/video-uploads/${task.videoUploadId}`, { method: "DELETE" }).catch(() => {
        window.dispatchEvent(new CustomEvent("lms_toast_notification", { detail: {
          message: "أوقفت المتابعة المحلية؛ قد تكون المعالجة بدأت بالفعل. تحقّق من حالة الفيديو.", tone: "warning",
        } }));
      });
    }

    if (task.xhr) {
      try {
        task.xhr.abort();
      } catch (err) {
        console.warn("Could not abort xhr", err);
      }
    }

    this.tasks = this.tasks.filter((t) => t.id !== taskId);
    this.notify();
    this.persistTasks();
    this.processQueue();

    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("lms_toast_notification", {
          detail: {
            message: "تم إلغاء عملية الرفع.",
            tone: "info",
          },
        })
      );
    }
  }

  public async retryUpload(taskId: string): Promise<'needs_file' | void> {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task || !this.owns(task) || this.running.has(task.id)) return;
    if (task.type === 'lesson_video') {
      const generation = getApiAuthGeneration();
      this.running.add(task.id);
      try {
        if (task.videoUploadId) {
          let session: VideoUploadSession;
          try {
            session = await apiRequest<VideoUploadSession>(`/video-uploads/${task.videoUploadId}`, { cacheTtlMs: 0 });
          } catch (error) {
            if (!(error instanceof ApiClientError) || error.status !== 404) throw error;
            if (generation !== getApiAuthGeneration() || !this.owns(task) || !this.tasks.includes(task)) return;
            // Explicit retry only: an absent intent cannot be resumed. Preserve
            // the key on all other errors so a lost response never duplicates it.
            task.videoUploadId = undefined;
            task.videoRequestKey = undefined;
            task.uploadPercent = 0;
            task.loadedBytes = 0;
            this.persistTasks();
            if (!task.file) return 'needs_file';
            session = { id: '', status: 'missing', part_bytes: 0, size_bytes: 0, fingerprint: '', uploaded_parts: [] };
          }
          if (generation !== getApiAuthGeneration() || !this.owns(task) || !this.tasks.includes(task)) return;
          if (session.status === 'ready') { this.completeVideo(task); return; }
          if (session.status === 'failed' && session.retryable) {
            session = await apiRequest<VideoUploadSession>(`/video-uploads/${session.id}/retry`, { method: 'POST' });
            if (generation !== getApiAuthGeneration() || !this.owns(task) || !this.tasks.includes(task)) return;
          }
          if (!['queued', 'processing', 'completing'].includes(session.status) && !task.file) return 'needs_file';
        } else if (!task.file) return 'needs_file';
      } catch (error) {
        if (generation === getApiAuthGeneration() && this.owns(task) && this.tasks.includes(task)) {
          task.status = 'error'; task.error = this.videoError(error);
          this.notify(); this.persistTasks(); this.notifyFailure(task);
        }
        return;
      } finally { this.running.delete(task.id); }
      if (generation !== getApiAuthGeneration() || !this.owns(task) || !this.tasks.includes(task)) return;
      task.status = 'queued'; task.error = undefined;
      this.updateVideoProgress(task);
      this.notify(); this.persistTasks(); this.processQueue();
      return;
    }
    if (!task.file && !task.files?.length && !task.videoUploadId) {
      task.error = "اختر الملف مجددًا قبل إعادة المحاولة.";
      this.notifyFailure(task);
      this.notify();
      return;
    }

    task.status = "queued";
    task.progress = 0;
    task.uploadPercent = 0;
    task.error = undefined;
    this.notify();
    this.persistTasks();
    this.processQueue();
  }

  public resumeVideo(taskId: string, file: File) {
    const task = this.tasks.find(t => t.id === taskId && t.type === "lesson_video");
    if (!task || !this.owns(task)) return;
    try { validateLessonUpload(file, "video"); }
    catch (error) { task.error = this.videoError(error); this.notify(); this.notifyFailure(task); return; }
    task.file = file;
    void this.retryUpload(taskId);
  }

  public clearTask(taskId: string) {
    const task = this.tasks.find(t => t.id === taskId && this.owns(t));
    if (task) this.videoTransfers.get(taskId)?.abort();
    this.tasks = this.tasks.filter((t) => t.id !== taskId || !this.owns(t));
    this.notify();
    this.persistTasks();
  }

  public clearCompleted() {
    this.tasks = this.tasks.filter((t) => !this.owns(t) || t.status === "uploading" || t.status === "queued" || t.status === "processing");
    this.notify();
    this.persistTasks();
  }
}

export const uploadManager = new UploadManager();

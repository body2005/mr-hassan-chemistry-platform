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
import { ApiClientError, apiRequest, uploadWithProgress } from "./apiClient";
import { validateLessonUpload } from "./uploadLimits";
import { putVideoPart, videoFingerprint, waitForVideo, type VideoUploadSession } from "./directVideoUpload";

export type UploadType = "lesson_video" | "lesson_material";
export type UploadStatus = "queued" | "uploading" | "processing" | "completed" | "error" | "cancelled";

export interface UploadTask {
  id: string;
  title: string;
  fileName: string;
  fileSizeBytes: number;
  loadedBytes?: number;
  formattedSize: string;
  progress: number; // 0-100 overall progress for the active phase
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

class UploadManager {
  private tasks: UploadTask[] = [];
  private listeners: Set<(tasks: UploadTask[]) => void> = new Set();
  private maxConcurrent = 2;
  private isProcessingQueue = false;

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
          (t) => t.status === "uploading" || t.status === "queued"
        );
        if (hasInFlightTransfer) {
          const warningMessage = "⚠️ تنبيه: هناك ملفات قيد نقل البيانات عبر الشبكة للمنصة. إذا أغلقت الصفحة الآن قبل اكتمال شريط النقل 100% قد ينقطع نقل الملف.";
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
          // If task was mid-upload over network when browser was closed, it was interrupted
          if (t.status === "uploading" || t.status === "queued" || t.status === "processing") {
            return {
              ...normalizedTask,
              status: "error",
              error: t.videoUploadId ? "اختر نفس الفيديو للاستئناف، أو أعد المحاولة للتحقق من المعالجة." : "انقطع نقل الملف لإغلاق المتصفح أثناء الإرسال. اختر الملف مجددًا.",
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
      title: `فيديو درس: ${params.lessonTitle}`,
      fileName: params.file.name,
      fileSizeBytes: params.file.size,
      formattedSize: formatFileSize(params.file.size),
      progress: 0,
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
      const activeCount = this.tasks.filter((t) => t.status === "uploading" || t.status === "processing").length;
      if (activeCount >= this.maxConcurrent) return;

      const nextTask = this.tasks.find((t) => t.status === "queued");
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
    task.status = "uploading";
    task.progress = 1;
    this.notify();
    this.persistTasks();

    try {
      await apiRequest("/auth/me", { cacheTtlMs: 0 });
      if (!this.tasks.includes(task)) return;
      const capabilities = await apiRequest<{ direct_upload: boolean }>("/video-upload-capabilities", { cacheTtlMs: 0 });
      if (!this.tasks.includes(task)) return;
      if (capabilities.direct_upload || task.videoUploadId) {
        await this.startDirectVideoUpload(task);
      } else {
        await courseService.uploadLessonVideo(
        task.lessonId!,
        task.file!,
        (percent) => {
          task.progress = Math.max(1, Math.min(99, percent));
          task.uploadPercent = Math.max(task.uploadPercent, Math.min(100, percent));
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
      }
      if (!this.tasks.includes(task)) return;

      task.status = "completed";
      task.progress = 100;
      task.uploadPercent = 100;
      task.completedAt = Date.now();
      task.error = undefined;
      this.notify();
      this.persistTasks();

      task.onSuccess?.();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("lms_courses_updated"));
        window.dispatchEvent(
          new CustomEvent("lms_toast_notification", {
            detail: {
              message: `✅ اكتمل رفع فيديو "${task.title}" بنجاح على السحابة!`,
              tone: "success",
            },
          })
        );
      }
    } catch (err: unknown) {
      if ((task.status as string) !== "cancelled") {
        task.status = "error";
        task.error = (err as Error)?.message || "تعذر إكمال رفع الفيديو. تأكد من سرعة الاتصال بالإنترنت.";
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
      this.processQueue();
    }
  }

  private async startDirectVideoUpload(task: UploadTask): Promise<void> {
    const active = () => this.tasks.includes(task) && task.status !== "cancelled";
    let session: VideoUploadSession;
    if (task.videoUploadId) {
      session = await apiRequest<VideoUploadSession>(`/video-uploads/${task.videoUploadId}`, { cacheTtlMs: 0 });
      if (["failed", "expired", "cancelled"].includes(session.status) && task.file) {
        // An explicit retry starts a new intent only for a terminal session.
        // Incomplete/processing sessions ALWAYS resume the existing intent.
        task.videoUploadId = undefined;
        task.videoRequestKey = undefined;
        return this.startDirectVideoUpload(task);
      }
    } else {
      if (!task.file) throw new Error("اختر ملف الفيديو مرة أخرى.");
      task.videoFingerprint = await videoFingerprint(task.file);
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
      if (!task.file) throw new Error("اختر نفس ملف الفيديو لاستكمال الأجزاء الناقصة.");
      if (session.fingerprint !== await videoFingerprint(task.file)) throw new Error("الملف المختار مختلف عن الفيديو الأصلي.");
      let loaded = session.uploaded_parts.reduce((sum, part) => sum + part.size_bytes, 0);
      const completed = new Set(session.uploaded_parts.map(part => part.number));
      for (let number = 1; number <= Math.ceil(session.size_bytes / session.part_bytes); number++) {
        if (!active()) return;
        if (completed.has(number)) continue;
        const signed = await apiRequest<{ url: string; size_bytes: number }>(`/video-uploads/${session.id}/parts/${number}`, { method: "POST" });
        if (!active()) return;
        const part = task.file.slice((number - 1) * session.part_bytes, (number - 1) * session.part_bytes + signed.size_bytes);
        await putVideoPart(signed.url, part, bytes => {
          task.loadedBytes = loaded + bytes;
          task.uploadPercent = Math.round(task.loadedBytes / session.size_bytes * 100);
          task.progress = Math.min(99, task.uploadPercent);
          this.notify();
        }, xhr => { task.xhr = xhr; });
        loaded += part.size;
        this.persistTasks();
      }
      if (!active()) return;
      session = await apiRequest<VideoUploadSession>(`/video-uploads/${session.id}/complete`, { method: "POST" });
    } else if (session.status === "completing") {
      session = await apiRequest<VideoUploadSession>(`/video-uploads/${session.id}/complete`, { method: "POST" });
    }
    task.status = "processing";
    task.uploadPercent = 100;
    task.statusDetail = "تم حفظ الفيديو؛ جارٍ التحقق وتجهيز جودات البث.";
    this.notify();
    this.persistTasks();
    await waitForVideo(session.id, active, current => {
      task.statusDetail = current.status === "ready" ? "الفيديو جاهز للمشاهدة." : "جارٍ تجهيز الفيديو في معالج منفصل.";
      this.notify();
    });
  }

  private async startMaterialBatchUpload(task: UploadTask) {
    if (!task.lessonId) {
      task.status = "error";
      task.error = "لا يمكن رفع المذكرات بدون تحديد الدرس.";
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
        // Renew once BEFORE transferring bytes. Never blindly replay a large
        // multipart upload after a 401 or re-upload completed files forever.
        await apiRequest("/auth/me", { cacheTtlMs: 0 });
        if (!this.tasks.includes(task)) return;
        task.statusDetail = `جاري رفع: ${file.name}`;
        task.progress = Math.max(1, Math.round((uploadedCount / files.length) * 100));
        this.notify();

        const formData = new FormData();
        formData.append("file", file);

        await uploadWithProgress<ServerMaterial>(
          `/lessons/${task.lessonId}/materials`,
          formData,
          (percent, loaded) => {
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
            task.xhr = xhr;
          }
        );

        uploadedCount += 1;
        if ((task.status as string) === "cancelled") return;
      } catch (err: unknown) {
        if ((task.status as string) === "cancelled") return;
        task.status = "error";
        const detail = err instanceof ApiClientError ? err.message : (err as Error)?.message;
        task.error = detail || "تعذر رفع الملفات. تأكد من سرعة الاتصال وحجم الملفات.";
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
    if (!task) return;
    task.status = "cancelled";
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

  public retryUpload(taskId: string) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task) return;
    if (!task.file && !task.files?.length && !task.videoUploadId) {
      task.error = "اختر الملف مجددًا قبل إعادة المحاولة.";
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
    if (!task) return;
    validateLessonUpload(file, "video");
    task.file = file;
    this.retryUpload(taskId);
  }

  public clearTask(taskId: string) {
    this.tasks = this.tasks.filter((t) => t.id !== taskId);
    this.notify();
    this.persistTasks();
  }

  public clearCompleted() {
    this.tasks = this.tasks.filter((t) => t.status === "uploading" || t.status === "queued" || t.status === "processing");
    this.notify();
    this.persistTasks();
  }
}

export const uploadManager = new UploadManager();

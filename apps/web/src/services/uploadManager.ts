/**
 * Global Background Upload Manager (LMS Cloud Ingestion Engine)
 * 
 * Enables non-blocking background uploads for large lesson videos and batch knowledge sources.
 * Uploads persist across internal page navigation, view changes, modal dismissals, and browser reloads.
 * Protects active network transfers while allowing safe closure during server-side indexing.
 */

import { courseService } from "./lmsService";
import { uploadWithProgress, apiRequest } from "./apiClient";

export type UploadType = "lesson_video" | "lesson_material" | "knowledge_source";
export type UploadStatus = "queued" | "uploading" | "processing" | "completed" | "error" | "cancelled";

export interface UploadTask {
  id: string;
  title: string;
  fileName: string;
  fileSizeBytes: number;
  loadedBytes?: number;
  formattedSize: string;
  progress: number; // Legacy display progress for the active phase
  uploadPercent: number;
  indexingPercent: number;
  processingGeneration?: number;
  processingAttemptId?: string;
  status: UploadStatus;
  error?: string;
  type: UploadType;
  lessonId?: string;
  courseId?: string;
  gradeLevel?: string;
  sourceIds?: string[];
  createdAt: number;
  completedAt?: number;
  file?: File;
  files?: File[];
  xhr?: XMLHttpRequest;
  onSuccess?: () => void;
}

interface ServerKnowledgeSource {
  id: string;
  filename: string;
  size_bytes?: number;
  progress_percent?: number;
  upload_percent?: number;
  indexing_percent?: number;
  processing_generation?: number;
  processing_attempt_id?: string;
  status: "QUEUED" | "PROCESSING" | "INDEXED" | "FAILED" | string;
  error_message?: string | null;
  course_id?: string;
  created_at?: string;
}

const STORAGE_KEY = "lms_global_upload_tasks_v2";

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
  private syncTimer: ReturnType<typeof setTimeout> | null = null;
  private activeAbortController: AbortController | null = null;
  private consecutivePollFailures = 0;

  constructor() {
    this.tasks = this.loadTasksFromStorage();
    this.initBeforeUnloadHandler();
    this.initLifecycleListeners();
    if (this.hasProcessingTasks()) {
      this.ensurePollingActive();
    }
  }

  private hasAuthenticatedSession(): boolean {
    if (typeof window === "undefined" || !window.localStorage) return false;
    return Boolean(localStorage.getItem("lms_session_token"));
  }

  public hasProcessingTasks(): boolean {
    return this.tasks.some((t) => t.status === "processing");
  }

  private initLifecycleListeners() {
    if (typeof window !== "undefined") {
      window.addEventListener("lms_user_updated", () => {
        if (!this.hasAuthenticatedSession()) {
          this.stopPolling();
        } else if (this.hasProcessingTasks()) {
          this.ensurePollingActive();
        }
      });
      if (typeof document !== "undefined") {
        document.addEventListener("visibilitychange", () => {
          if (!document.hidden && this.hasProcessingTasks() && this.hasAuthenticatedSession()) {
            this.ensurePollingActive();
            void this.syncWithServer();
          }
        });
      }
    }
  }

  public ensurePollingActive() {
    if (!this.hasAuthenticatedSession() || !this.hasProcessingTasks()) return;
    if (this.syncTimer) return;
    this.scheduleNextPoll();
  }

  public stopPolling() {
    if (this.syncTimer) {
      clearTimeout(this.syncTimer);
      this.syncTimer = null;
    }
    if (this.activeAbortController) {
      this.activeAbortController.abort();
      this.activeAbortController = null;
    }
    this.consecutivePollFailures = 0;
  }

  private scheduleNextPoll() {
    if (this.syncTimer) clearTimeout(this.syncTimer);
    if (!this.hasAuthenticatedSession() || !this.hasProcessingTasks()) {
      this.syncTimer = null;
      return;
    }

    const isHidden = typeof document !== "undefined" && document.hidden;
    const activeDelay = Math.min(60_000, 3_500 * 2 ** this.consecutivePollFailures);
    const delay = isHidden ? Math.max(30_000, activeDelay) : activeDelay;
    this.syncTimer = setTimeout(async () => {
      await this.syncWithServer();
      if (this.hasProcessingTasks() && this.hasAuthenticatedSession()) {
        this.scheduleNextPoll();
      } else {
        this.syncTimer = null;
      }
    }, delay);
  }

  private initBeforeUnloadHandler() {
    if (typeof window !== "undefined") {
      window.addEventListener("beforeunload", (e) => {
        // ONLY warn if active byte transfer is in-flight across the wire (uploading / queued).
        // If status === 'processing', the file is already safely stored on the server,
        // and backend indexing continues completely uninterrupted!
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
            indexingPercent: t.indexingPercent ?? (t.status === "processing" || t.status === "completed" ? t.progress || 0 : 0),
          };
          // If task was mid-upload over network when browser was closed, it was interrupted
          if (t.status === "uploading" || t.status === "queued") {
            return {
              ...normalizedTask,
              status: "error",
              error: "انقطع نقل الملف لإغلاق المتصفح أثناء الإرسال. يمكنك إعادة المحاولة.",
            } as UploadTask;
          }
          // If task was processing on the server, keep it as processing so server sync checks its status!
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

  public async syncWithServer(): Promise<void> {
    if (typeof window === "undefined" || !this.hasAuthenticatedSession() || !this.hasProcessingTasks()) return;

    if (this.activeAbortController) {
      this.activeAbortController.abort();
    }
    this.activeAbortController = new AbortController();
    const signal = this.activeAbortController.signal;

    try {
      let hasChanges = false;
      let sourceLookupFailed = false;

      // 1. Check specific source IDs for active tasks
      const activeTasks = this.tasks.filter(
        (t) => (t.type === "knowledge_source" || t.type === "lesson_material") && (t.status === "processing" || t.status === "uploading")
      );

      for (const task of activeTasks) {
        if (task.sourceIds && task.sourceIds.length > 0) {
          const matched: ServerKnowledgeSource[] = [];
          for (const sId of task.sourceIds) {
            try {
              const item = await apiRequest<ServerKnowledgeSource>(`/knowledge-center/sources/${sId}`, { signal });
              if (item && item.id) matched.push(item);
            } catch {
              // A transient API outage is handled by bounded exponential
              // backoff below; never mark a durable server-side job failed.
              sourceLookupFailed = true;
            }
          }

          if (matched.length > 0) {
            const allIndexed = matched.every((s) => s.status === "INDEXED");
            const anyFailed = matched.find((s) => s.status === "FAILED");
            const avgProgress = Math.round(
              matched.reduce((acc, s) => acc + (s.indexing_percent ?? s.progress_percent ?? 0), 0) / matched.length
            );
            const newestGeneration = Math.max(...matched.map((s) => s.processing_generation ?? 1));
            const attemptKey = matched.map((s) => s.processing_attempt_id || "legacy").sort().join(":");
            task.uploadPercent = Math.max(task.uploadPercent || 0, ...matched.map((s) => s.upload_percent ?? 100));
            if (task.processingGeneration !== newestGeneration || task.processingAttemptId !== attemptKey) {
              task.processingGeneration = newestGeneration;
              task.processingAttemptId = attemptKey;
              task.indexingPercent = avgProgress;
            } else {
              task.indexingPercent = Math.max(task.indexingPercent || 0, avgProgress);
            }

            if (allIndexed) {
              task.status = "completed";
              task.progress = 100;
              task.indexingPercent = 100;
              task.completedAt = Date.now();
              task.error = undefined;
              hasChanges = true;
              task.onSuccess?.();
              window.dispatchEvent(new CustomEvent("lms_knowledge_updated"));
              if (task.lessonId) window.dispatchEvent(new CustomEvent("lms_courses_updated"));
              window.dispatchEvent(
                new CustomEvent("lms_toast_notification", {
                  detail: {
                    message: `✅ اكتملت فهرسة ملفات "${task.title}" بنجاح في السحابة!`,
                    tone: "success",
                  },
                })
              );
            } else if (anyFailed) {
              task.status = "error";
              task.error = anyFailed.error_message || "فشلت عملية الفهرسة بالسيرفر";
              hasChanges = true;
            } else {
              if (task.progress !== task.indexingPercent) {
                task.progress = task.indexingPercent;
                hasChanges = true;
              }
            }
          }
        }
      }

      if (hasChanges) {
        this.notify();
        this.persistTasks();
      }
      this.consecutivePollFailures = sourceLookupFailed
        ? Math.min(this.consecutivePollFailures + 1, 5)
        : 0;
    } catch {
      // Backend might be momentarily offline or rate-limited. Keep the task
      // and progressively back off, capped at one minute.
      this.consecutivePollFailures = Math.min(this.consecutivePollFailures + 1, 5);
    }
  }

  public getTasks(): UploadTask[] {
    return [...this.tasks];
  }

  public hasActiveUploads(): boolean {
    return this.tasks.some(
      (t) => t.status === "queued" || t.status === "uploading" || t.status === "processing"
    );
  }

  public subscribe(listener: (tasks: UploadTask[]) => void): () => void {
    this.listeners.add(listener);
    listener(this.getTasks());
    return () => this.listeners.delete(listener);
  }

  private notify() {
    const current = this.getTasks();
    this.listeners.forEach((listener) => {
      try {
        listener(current);
      } catch (err) {
        console.error("Error notifying upload listener", err);
      }
    });
  }

  /**
   * Enqueue a lesson video upload in the background.
   */
  public enqueueVideoUpload(params: {
    lessonId: string;
    lessonTitle: string;
    file: File;
    courseId?: string;
    onSuccess?: () => void;
  }): string {
    const taskId = `vid_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const task: UploadTask = {
      id: taskId,
      title: `فيديو: ${params.lessonTitle}`,
      fileName: params.file.name,
      fileSizeBytes: params.file.size,
      formattedSize: formatFileSize(params.file.size),
      progress: 0,
      uploadPercent: 0,
      indexingPercent: 0,
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

  /**
   * Enqueue a batch upload of knowledge documents (PDFs, docs) in the background.
   */
  public enqueueKnowledgeBatchUpload(params: {
    files: File[];
    courseId?: string;
    gradeLevel?: string;
    lessonId?: string;
    lessonTitle?: string;
    onSuccess?: () => void;
  }): string {
    const taskId = `knw_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const totalBytes = params.files.reduce((sum, f) => sum + f.size, 0);
    const count = params.files.length;
    const gradeLabel = params.gradeLevel === "SECONDARY_1"
      ? "الصف الأول الثانوي"
      : params.gradeLevel === "SECONDARY_2"
      ? "الصف الثاني الثانوي"
      : params.gradeLevel === "SECONDARY_3"
      ? "الصف الثالث الثانوي"
      : "";
    const taskTitle = params.lessonTitle
      ? `مذكرات درس: ${params.lessonTitle} (${count} ${count === 1 ? "ملف" : "ملفات"})`
      : gradeLabel
      ? `مصادر ${gradeLabel} (${count} ${count === 1 ? "ملف" : "ملفات"})`
      : `رفع دفعة مستندات (${count} ${count === 1 ? "ملف" : "ملفات"})`;
    const isMaterial = Boolean(params.lessonId);
    const task: UploadTask = {
      id: taskId,
      title: taskTitle,
      fileName: params.files[0]?.name + (count > 1 ? ` (+${count - 1} ملفات أخرى)` : ""),
      fileSizeBytes: totalBytes,
      formattedSize: formatFileSize(totalBytes),
      progress: 0,
      uploadPercent: 0,
      indexingPercent: 0,
      status: "queued",
      type: isMaterial ? "lesson_material" : "knowledge_source",
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

  private async processQueue() {
    if (this.isProcessingQueue) return;
    this.isProcessingQueue = true;

    try {
      const activeCount = this.tasks.filter((t) => t.status === "uploading" || t.status === "processing").length;
      if (activeCount >= this.maxConcurrent) return;

      const nextTask = this.tasks.find((t) => t.status === "queued");
      if (!nextTask) return;

      if (nextTask.type === "lesson_video" && nextTask.file && nextTask.lessonId) {
        this.startVideoUpload(nextTask);
      } else if ((nextTask.type === "knowledge_source" || nextTask.type === "lesson_material") && nextTask.files && nextTask.files.length > 0) {
        this.startKnowledgeBatchUpload(nextTask);
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

  private async startKnowledgeBatchUpload(task: UploadTask) {
    task.status = "uploading";
    task.progress = 1;
    this.notify();
    this.persistTasks();

    try {
      const formData = new FormData();
      task.files!.forEach((file) => {
        formData.append("files", file);
      });
      if (task.gradeLevel) {
        formData.append("grade_level", task.gradeLevel);
      }
      if (task.courseId) {
        formData.append("course_id", task.courseId);
      }
      if (task.lessonId) {
        formData.append("lesson_id", task.lessonId);
      }
      const role = task.type === "lesson_material" || Boolean(task.lessonId)
        ? "LESSON_MATERIAL"
        : "COURSE_KNOWLEDGE";
      formData.append("source_role", role);

      const createdSources = await uploadWithProgress<ServerKnowledgeSource[]>(
        "/knowledge-center/sources/upload-batch",
        formData,
        (percent, loaded) => {
          task.progress = Math.max(1, Math.min(99, percent));
          task.uploadPercent = Math.max(task.uploadPercent, Math.min(100, percent));
          if (typeof loaded === "number") {
            task.loadedBytes = loaded;
          }
          if (percent >= 100) {
            task.status = "processing";
            this.ensurePollingActive();
          }
          this.notify();
          this.persistTasks();
        },
        0,
        (xhr) => {
          task.xhr = xhr;
        }
      );

      task.status = "processing";
      task.uploadPercent = 100;
      task.indexingPercent = 0;
      task.progress = 0;
      if (Array.isArray(createdSources)) {
        task.sourceIds = createdSources.map((s) => s.id);
        task.indexingPercent = Math.round(
          createdSources.reduce((sum, source) => sum + (source.indexing_percent ?? 0), 0)
          / Math.max(createdSources.length, 1)
        );
        task.progress = task.indexingPercent;
        task.processingGeneration = Math.max(...createdSources.map((source) => source.processing_generation ?? 1));
        task.processingAttemptId = createdSources.map((source) => source.processing_attempt_id || "legacy").sort().join(":");
      }
      this.ensurePollingActive();
      this.notify();
      this.persistTasks();

      if (task.onSuccess) {
        task.onSuccess();
      }

      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("lms_knowledge_updated"));
        if (task.courseId && task.lessonId) {
          window.dispatchEvent(new CustomEvent("lms_courses_updated"));
        }
        window.dispatchEvent(
          new CustomEvent("lms_toast_notification", {
            detail: {
              message: `📥 تم حفظ الملفات بالسيرفر بنجاح! بدأت الفهرسة.`,
              tone: "success",
            },
          })
        );
      }

      // Trigger immediate sync
      void this.syncWithServer();
    } catch (err: unknown) {
      if ((task.status as string) !== "cancelled") {
        task.status = "error";
        task.error = (err as Error)?.message || "تعذر رفع الملفات. تأكد من سرعة الاتصال وحجم الملفات.";
        this.notify();
        this.persistTasks();
      }
    } finally {
      this.processQueue();
    }
  }

  public cancelUpload(taskId: string) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task) return;

    if (task.xhr) {
      try {
        task.xhr.abort();
      } catch (err) {
        console.warn("Could not abort xhr", err);
      }
    }

    // If source exists on server, stop indexing without deleting the file!
    const sourceIds = [...(task.sourceIds || [])];
    if (taskId.startsWith("srv_")) {
      const parsedId = taskId.replace("srv_", "");
      if (!sourceIds.includes(parsedId)) {
        sourceIds.push(parsedId);
      }
    }

    if (sourceIds.length > 0) {
      sourceIds.forEach((sId) => {
        apiRequest(`/knowledge-center/sources/${sId}/stop-indexing`, { method: "POST" }).catch(() => {});
      });
    }

    this.tasks = this.tasks.filter((t) => t.id !== taskId);
    this.notify();
    this.persistTasks();
    this.processQueue();

    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("lms_knowledge_updated"));
      window.dispatchEvent(
        new CustomEvent("lms_toast_notification", {
          detail: {
            message: "تم إيقاف الفهرسة، والملف محفوظ بالسيرفر.",
            tone: "info",
          },
        })
      );
    }
  }

  public retryUpload(taskId: string) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (!task) return;

    task.status = "queued";
    task.progress = 0;
    task.uploadPercent = 0;
    task.indexingPercent = 0;
    task.processingGeneration = undefined;
    task.processingAttemptId = undefined;
    task.error = undefined;
    this.notify();
    this.persistTasks();
    this.processQueue();
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

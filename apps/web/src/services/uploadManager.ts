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
  progress: number; // 0 to 100
  status: UploadStatus;
  error?: string;
  type: UploadType;
  lessonId?: string;
  courseId?: string;
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

  constructor() {
    this.tasks = this.loadTasksFromStorage();
    this.initBeforeUnloadHandler();
    this.startServerSyncLoop();
  }

  private hasAuthenticatedSession(): boolean {
    if (typeof window === "undefined" || !window.localStorage) return false;
    return Boolean(localStorage.getItem("lms_session_token"));
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
          // If task was mid-upload over network when browser was closed, it was interrupted
          if (t.status === "uploading" || t.status === "queued") {
            return {
              ...t,
              status: "error",
              error: "انقطع نقل الملف لإغلاق المتصفح أثناء الإرسال. يمكنك إعادة المحاولة.",
            };
          }
          // If task was processing on the server, keep it as processing so server sync checks its status!
          return t;
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

  private startServerSyncLoop() {
    if (typeof window === "undefined") return;

    // Trigger initial sync shortly after initialization
    setTimeout(() => {
      if (this.hasAuthenticatedSession()) void this.syncWithServer();
    }, 1200);

    const scheduleNext = () => {
      if (this.syncTimer) clearTimeout(this.syncTimer);
      const hasProcessing = this.tasks.some((t) => t.status === "processing");
      const delay = hasProcessing ? 3500 : 15000;
      this.syncTimer = setTimeout(async () => {
        if (this.hasAuthenticatedSession()) await this.syncWithServer();
        scheduleNext();
      }, delay);
    };

    scheduleNext();
  }

  public async syncWithServer(): Promise<void> {
    if (typeof window === "undefined" || !this.hasAuthenticatedSession()) return;
    try {
      const sources = await apiRequest<ServerKnowledgeSource[]>("/knowledge-center/sources");
      if (!Array.isArray(sources)) return;

      let hasChanges = false;
      const serverSourcesMap = new Map<string, ServerKnowledgeSource>();
      sources.forEach((s) => {
        serverSourcesMap.set(s.id, s);
      });

      // 1. Update existing tasks with server status
      for (const task of this.tasks) {
        if (task.type === "knowledge_source" && (task.status === "processing" || task.status === "uploading")) {
          // If task has specific sourceIds
          if (task.sourceIds && task.sourceIds.length > 0) {
            const matched: ServerKnowledgeSource[] = [];
            for (const id of task.sourceIds) {
              const item = serverSourcesMap.get(id);
              if (item) matched.push(item);
            }
            if (matched.length > 0) {
              const allIndexed = matched.every((s) => s.status === "INDEXED");
              const anyFailed = matched.find((s) => s.status === "FAILED");
              const avgProgress = Math.round(
                matched.reduce((acc, s) => acc + (s.progress_percent || 0), 0) / matched.length
              );

              if (allIndexed) {
                task.status = "completed";
                task.progress = 100;
                task.completedAt = Date.now();
                task.error = undefined;
                hasChanges = true;
                task.onSuccess?.();
                window.dispatchEvent(new CustomEvent("lms_knowledge_updated"));
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
                if (avgProgress > task.progress) {
                  task.progress = avgProgress;
                  hasChanges = true;
                }
              }
            }
          }
        }
      }

      // 2. Discover any server-side PROCESSING sources not yet tracked in UI
      // (e.g. user closed browser and reopened, or indexing was started from another window)
      for (const s of sources) {
        if (s.status === "PROCESSING" || s.status === "QUEUED") {
          const alreadyTracked = this.tasks.some(
            (t) => t.sourceIds?.includes(s.id) || t.id === `srv_${s.id}`
          );
          if (!alreadyTracked) {
            const newTask: UploadTask = {
              id: `srv_${s.id}`,
              title: `فهرسة: ${s.filename}`,
              fileName: s.filename,
              fileSizeBytes: s.size_bytes || 0,
              formattedSize: formatFileSize(s.size_bytes || 0),
              progress: Math.max(10, s.progress_percent || 10),
              status: "processing",
              type: "knowledge_source",
              courseId: s.course_id,
              sourceIds: [s.id],
              createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            };
            this.tasks.unshift(newTask);
            hasChanges = true;
          }
        }
      }

      if (hasChanges) {
        this.notify();
        this.persistTasks();
      }
    } catch {
      // Backend might be momentarily offline or rate-limited; skip silently
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
    lessonId?: string;
    lessonTitle?: string;
    onSuccess?: () => void;
  }): string {
    const taskId = `knw_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
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
      status: "queued",
      type: "knowledge_source",
      courseId: params.courseId,
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
      } else if (nextTask.type === "knowledge_source" && nextTask.files && nextTask.files.length > 0) {
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
      if (task.courseId) {
        formData.append("course_id", task.courseId);
      }
      if (task.lessonId) {
        formData.append("lesson_id", task.lessonId);
      }
      formData.append("source_role", "KNOWLEDGE");

      const createdSources = await uploadWithProgress<{ id: string; status: string }[]>(
        "/knowledge-center/sources/upload-batch",
        formData,
        (percent, loaded) => {
          task.progress = Math.max(1, Math.min(99, percent));
          if (typeof loaded === "number") {
            task.loadedBytes = loaded;
          }
          if (percent >= 100) {
            task.status = "processing";
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
      task.progress = 100;
      if (Array.isArray(createdSources)) {
        task.sourceIds = createdSources.map((s) => s.id);
      }
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

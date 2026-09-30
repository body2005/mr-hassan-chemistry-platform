import { GeneratedQuestion } from "../types/quiz";

export interface PublishedQuizRecord {
  id: string;
  title: string;
  assessmentType: "quiz" | "assignment";
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  creationMode: "extract" | "manual" | "extracted";
  /** Legacy value from records saved before AI generation was removed. */
  quizMode?: "mix" | "extract" | "generate";
  publishedAt: string;
  publishStartDate: string;
  publishStartTime: string;
  closeDeadlineDate: string;
  closeDeadlineTime: string;
  closeDeadline: string;
  quizDurationMinutes?: number;
  showOnStudentCalendar: boolean;
  totalPoints: number;
  questionsCount: number;
  questions: GeneratedQuestion[];
  courseId?: string;
  selectedLessonIds?: string[];
  status: "active" | "closed" | "scheduled";
}

const STORAGE_KEY = "lms_teacher_quiz_history_v1";

const INITIAL_SAMPLE_HISTORY: PublishedQuizRecord[] = [];

class QuizHistoryService {
  private memoryCache: PublishedQuizRecord[] | null = null;
  private listeners: Set<(records: PublishedQuizRecord[]) => void> = new Set();

  private computeStatus(record: PublishedQuizRecord): "active" | "closed" | "scheduled" {
    try {
      const now = new Date();
      if (record.closeDeadlineDate) {
        const closeStr = `${record.closeDeadlineDate}T23:59:59`;
        const closeDate = new Date(closeStr);
        if (!isNaN(closeDate.getTime()) && now > closeDate) {
          return "closed";
        }
      }
      if (record.publishStartDate) {
        const startStr = `${record.publishStartDate}T00:00:00`;
        const startDate = new Date(startStr);
        if (!isNaN(startDate.getTime()) && now < startDate) {
          return "scheduled";
        }
      }
      return "active";
    } catch {
      return record.status || "active";
    }
  }

  public getHistory(): PublishedQuizRecord[] {
    if (this.memoryCache !== null) {
      return this.memoryCache;
    }

    try {
      const raw = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          this.memoryCache = parsed.map((item) => ({
            ...item,
            status: this.computeStatus(item),
          }));
          return this.memoryCache;
        }
      }
    } catch (e) {
      console.warn("Error reading quiz history from localStorage:", e);
    }

    // Seed default items
    this.memoryCache = INITIAL_SAMPLE_HISTORY.map((item) => ({
      ...item,
      status: this.computeStatus(item),
    }));
    this.persist(this.memoryCache);
    return this.memoryCache;
  }

  private persist(records: PublishedQuizRecord[]) {
    try {
      if (typeof localStorage !== "undefined") {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
      }
    } catch (e) {
      console.error("Failed to persist quiz history:", e);
    }
  }

  private notify() {
    const data = this.getHistory();
    this.listeners.forEach((fn) => fn(data));
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("lms_quiz_history_updated", { detail: data }));
    }
  }

  public saveQuiz(
    payload: Omit<PublishedQuizRecord, "id" | "publishedAt" | "status"> & { id?: string }
  ): PublishedQuizRecord {
    const list = [...this.getHistory()];
    const now = new Date();
    const formattedDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
      now.getDate()
    ).padStart(2, "0")} ${now.toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" })}`;

    const id = payload.id || `quiz_hist_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const newRecord: PublishedQuizRecord = {
      ...payload,
      id,
      publishedAt: formattedDate,
      status: "active",
    };
    newRecord.status = this.computeStatus(newRecord);

    const existingIndex = list.findIndex((q) => q.id === id);
    if (existingIndex >= 0) {
      list[existingIndex] = newRecord;
    } else {
      list.unshift(newRecord);
    }

    this.memoryCache = list;
    this.persist(list);
    this.notify();
    return newRecord;
  }

  public deleteQuiz(id: string): PublishedQuizRecord[] {
    const list = this.getHistory().filter((q) => q.id !== id);
    this.memoryCache = list;
    this.persist(list);
    this.notify();
    return list;
  }

  public getQuizById(id: string): PublishedQuizRecord | null {
    const list = this.getHistory();
    return list.find((q) => q.id === id) || null;
  }

  public subscribe(callback: (records: PublishedQuizRecord[]) => void): () => void {
    this.listeners.add(callback);
    callback(this.getHistory());
    return () => {
      this.listeners.delete(callback);
    };
  }
}

export const quizHistoryService = new QuizHistoryService();

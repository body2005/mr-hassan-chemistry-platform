import { GeneratedQuestion } from "../types/quiz";
import { getApiAuthScope } from './apiClient';
import { assessmentTimestamp } from './assessmentSchedule';

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
  selectedModuleIds?: string[];
  status: "active" | "closed" | "scheduled";
}

const STORAGE_KEY = "lms_teacher_quiz_history_v2";

const INITIAL_SAMPLE_HISTORY: PublishedQuizRecord[] = [];

class QuizHistoryService {
  private scope = '';
  private memoryCache: PublishedQuizRecord[] | null = null;
  private listeners: Set<(records: PublishedQuizRecord[]) => void> = new Set();

  constructor() {
    if (typeof window !== 'undefined') window.addEventListener('lms_auth_scope_updated', () => {
      this.memoryCache = null;
      this.notify();
    });
  }

  private computeStatus(record: PublishedQuizRecord): "active" | "closed" | "scheduled" {
    try {
      const now = new Date();
      if (record.closeDeadlineDate) {
        const closeStr = assessmentTimestamp(`${record.closeDeadlineDate}T${record.closeDeadlineTime || '23:59:59'}`, 'الإغلاق');
        const closeDate = new Date(closeStr!);
        if (!isNaN(closeDate.getTime()) && now >= closeDate) {
          return "closed";
        }
      }
      if (record.publishStartDate) {
        const startStr = assessmentTimestamp(`${record.publishStartDate}T${record.publishStartTime || '00:00'}`, 'الإتاحة');
        const startDate = new Date(startStr!);
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
    const scope = getApiAuthScope();
    if (scope !== this.scope) {
      this.scope = scope;
      this.memoryCache = null;
    }
    if (!scope || scope === 'anonymous') return [];
    if (this.memoryCache !== null) {
      return this.memoryCache;
    }

    try {
      // Never attribute the old unscoped v1 blob to the next signed-in user.
      // It is left intact for an explicit owner-reviewed migration later.
      const raw = typeof localStorage !== "undefined" ? localStorage.getItem(`${STORAGE_KEY}:${scope}`) : null;
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
        if (this.scope && this.scope !== 'anonymous')
          localStorage.setItem(`${STORAGE_KEY}:${this.scope}`, JSON.stringify(records));
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
    if (!this.scope || this.scope === 'anonymous') throw new Error('يلزم تسجيل الدخول لحفظ سجل التقييم.');
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

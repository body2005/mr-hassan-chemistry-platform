import { GeneratedQuestion } from "../types/ai";

export interface PublishedQuizRecord {
  id: string;
  title: string;
  assessmentType: "quiz" | "assignment";
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  creationMode: "ai" | "manual" | "extracted";
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

const INITIAL_SAMPLE_HISTORY: PublishedQuizRecord[] = [
  {
    id: "quiz_hist_001",
    title: "اختبار تقييمي: الكيمياء مركز العلوم وأدوات القياس",
    assessmentType: "quiz",
    academicYear: "1st_secondary",
    academicYearLabel: "الصف الأول الثانوي",
    creationMode: "ai",
    quizMode: "mix",
    publishedAt: "2026-09-08 10:30 ص",
    publishStartDate: "2026-09-08",
    publishStartTime: "10:30 ص",
    closeDeadlineDate: "2026-09-15",
    closeDeadlineTime: "11:59 م",
    closeDeadline: "2026-09-15 11:59 م",
    quizDurationMinutes: 30,
    showOnStudentCalendar: true,
    totalPoints: 20,
    questionsCount: 4,
    status: "active",
    questions: [
      {
        id: 1,
        question_type: "multiple_choice",
        difficulty: "easy",
        topic: "أدوات القياس في معمل الكيمياء",
        points: 5,
        question_text: "أي من الأدوات الآتية تُستخدم بدقة عالية في تعيين حجوم السوائل أثناء تجارب المعايرة؟",
        options: [
          { key: "أ", text: "السحاحة (Burette)", is_correct: true, distractor_explanation: "السحاحة هي الأداة المخصصة للقياس بالغ الدقة في تجارب المعايرة." },
          { key: "ب", text: "المخبار المدرج", is_correct: false },
          { key: "ج", text: "الكأس الزجاجي", is_correct: false },
          { key: "د", text: "الدورق المستدير", is_correct: false },
        ],
        correct_answer: "السحاحة (Burette)",
        explanation: "السحاحة أنبوبة زجاجية مدرجة من أعلى لأسفل تستخدم في إضافة حجوم دقيقة أثناء المعايرة.",
      },
      {
        id: 2,
        question_type: "true_false",
        difficulty: "medium",
        topic: "كيمياء النانو",
        points: 5,
        question_text: "تزداد النسبة بين مساحة السطح إلى الحجم زيادة كبيرة جداً عند تقسيم المادة إلى أبعاد نانوية.",
        options: [
          { key: "أ", text: "صواب", is_correct: true },
          { key: "ب", text: "خطأ", is_correct: false },
        ],
        correct_answer: "صواب",
        explanation: "كلما صغر حجم الحبيبات زادت مساحة السطح الكلية المعرضة للتفاعل بالنسبة للحجم الثابت مما يمنحها خواصاً نانوية فريدة.",
      },
      {
        id: 3,
        question_type: "fill_in_blank",
        difficulty: "medium",
        topic: "الكيمياء والبيولوجيا",
        points: 5,
        question_text: "العلم الذي ينتج من تكامل علم الكيمياء مع علم الأحياء (البيولوجي) هو علم ______.",
        correct_answer: "الكيمياء الحيوية (Biochemistry)",
        explanation: "علم الكيمياء الحيوية يدرس التركيب الكيميائي لأجزاء الخلية والتفاعلات الكيميائية الحيوية داخل الكائنات الحية.",
      },
      {
        id: 4,
        question_type: "essay",
        difficulty: "hard",
        topic: "المعايرة الكيميائية",
        points: 5,
        question_text: "علل: تثبت السحاحة على حامل ذو قاعدة معدنية في وضع رأسي أثناء إجراء تجربة المعايرة.",
        correct_answer: "للحفاظ على وضعها العمودي السليم وضمان القراءة الدقيقة لمستوى السائل وتجنب أخطاء الرؤية.",
        explanation: "يضمن الوضع العمودي عدم حدوث خطأ اختلاف زاوية النظر وتدفق المحلول بانتظام.",
      },
    ],
  },
  {
    id: "quiz_hist_002",
    title: "واجب منزلي: حساب كمية الحرارة وقانون هس",
    assessmentType: "assignment",
    academicYear: "1st_secondary",
    academicYearLabel: "الصف الأول الثانوي",
    creationMode: "manual",
    publishedAt: "2026-09-09 02:15 م",
    publishStartDate: "2026-09-09",
    publishStartTime: "02:15 م",
    closeDeadlineDate: "2026-09-14",
    closeDeadlineTime: "10:00 م",
    closeDeadline: "2026-09-14 10:00 م",
    quizDurationMinutes: 45,
    showOnStudentCalendar: true,
    totalPoints: 15,
    questionsCount: 3,
    status: "active",
    questions: [
      {
        id: 1,
        question_type: "multiple_choice",
        difficulty: "medium",
        topic: "الديناميكا الحرارية",
        points: 5,
        question_text: "إذا كانت كمية الحرارة الممتصة بواسطة 50g من الماء النقي هي 4180 J، فإن مقدار التغير في درجة الحرارة ΔT يساوي:",
        options: [
          { key: "أ", text: "20 °C", is_correct: true, distractor_explanation: "ΔT = q / (m × c) = 4180 / (50 × 4.18) = 20 °C" },
          { key: "ب", text: "10 °C", is_correct: false },
          { key: "ج", text: "40 °C", is_correct: false },
          { key: "د", text: "5 °C", is_correct: false },
        ],
        correct_answer: "20 °C",
        explanation: "بالتطبيق في قانون q = m × c × ΔT، نجد أن ΔT = 4180 / (50 × 4.18) = 20 درجة مئوية.",
      },
      {
        id: 2,
        question_type: "true_false",
        difficulty: "easy",
        topic: "الحرارة النوعية",
        points: 5,
        question_text: "الحرارة النوعية للماء السائل تعتبر أكبر حرارة نوعية بين المواد المعروفة.",
        options: [
          { key: "أ", text: "صواب", is_correct: true },
          { key: "ب", text: "خطأ", is_correct: false },
        ],
        correct_answer: "صواب",
        explanation: "الحرارة النوعية للماء تبلغ 4.18 J/g.°C وهي من أعلى القيم، لذلك يلزم اكتساب أو فقد كمية حرارة كبيرة لتغير درجة حرارته.",
      },
      {
        id: 3,
        question_type: "essay",
        difficulty: "hard",
        topic: "قانون هس",
        points: 5,
        question_text: "وضح نص قانون هس (مجموع الحرارة الثابت) واذكر أهميته في قياس حرارة التفاعلات التي يصعب قياسها عملياً.",
        correct_answer: "حرارة التفاعل مقدار ثابت في الظروف القياسية سواء تم التفاعل في خطوة واحدة أو عدة خطوات. وتكمن أهميته في حساب حرارة التفاعلات البطيئة أو الخطيرة أو المعقدة.",
        explanation: "قانون هس يسمح بمعاملة المعادلات الكيميائية كمعادلات جبرية لحساب التغير في المحتوى الحراري غير المباشر.",
      },
    ],
  },
  {
    id: "quiz_hist_003",
    title: "اختبار شامل: الباب الثاني — الجدول الدوري وتدرج الخواص",
    assessmentType: "quiz",
    academicYear: "2nd_secondary",
    academicYearLabel: "الصف الثاني الثانوي",
    creationMode: "ai",
    quizMode: "extract",
    publishedAt: "2026-08-30 09:00 ص",
    publishStartDate: "2026-08-30",
    publishStartTime: "09:00 ص",
    closeDeadlineDate: "2026-09-05",
    closeDeadlineTime: "11:59 م",
    closeDeadline: "2026-09-05 11:59 م",
    quizDurationMinutes: 40,
    showOnStudentCalendar: true,
    totalPoints: 20,
    questionsCount: 4,
    status: "closed",
    questions: [
      {
        id: 1,
        question_type: "multiple_choice",
        difficulty: "medium",
        topic: "نصف القطر الذري",
        points: 5,
        question_text: "في الدورة الواحدة، كلما اتجهنا من اليسار إلى اليمين بزيادة العدد الذري فإن نصف القطر الذري:",
        options: [
          { key: "أ", text: "يقل تدريجياً لزيادة شحنة النواة الفعالة", is_correct: true },
          { key: "ب", text: "يزداد تدريجياً لزيادة عدد الإلكترونات", is_correct: false },
          { key: "ج", text: "يظل ثابتاً لثبات عدد مستويات الطاقة", is_correct: false },
          { key: "د", text: "يتضاعف بسبب قوى التنافر", is_correct: false },
        ],
        correct_answer: "يقل تدريجياً لزيادة شحنة النواة الفعالة",
        explanation: "زيادة شحنة النواة الفعالة تزيد من جذب النواة لإلكترونات التكافؤ مما يؤدي لتقلص الحجم الذري.",
      },
      {
        id: 2,
        question_type: "multiple_choice",
        difficulty: "hard",
        topic: "جهد التأين",
        points: 5,
        question_text: "أي العناصر الآتية يمتلك أعلى قيمة لجهد التأين الأول في الجدول الدوري؟",
        options: [
          { key: "أ", text: "الهيليوم (He)", is_correct: true },
          { key: "ب", text: "النيون (Ne)", is_correct: false },
          { key: "ج", text: "الفلور (F)", is_correct: false },
          { key: "د", text: "الفرانسيوم (Fr)", is_correct: false },
        ],
        correct_answer: "الهيليوم (He)",
        explanation: "الهيليوم له أصغر نصف قطر ومستواه الرئيسي مكتمل ومستقر جداً مما يجعله أعلى جهد تأين أول.",
      },
      {
        id: 3,
        question_type: "true_false",
        difficulty: "easy",
        topic: "السالبية الكهربية",
        points: 5,
        question_text: "عنصر الفلور (F) هو الأعلى سالبية كهربية في جميع عناصر الجدول الدوري وتساوي قيمته تقريباً 4.0.",
        options: [
          { key: "أ", text: "صواب", is_correct: true },
          { key: "ب", text: "خطأ", is_correct: false },
        ],
        correct_answer: "صواب",
        explanation: "الفلور أصغر اللافلزات حجماً وأكبرها قدرة على جذب إلكترونات الرابطة التساهمية.",
      },
      {
        id: 4,
        question_type: "essay",
        difficulty: "medium",
        topic: "أعداد التأكسد",
        points: 5,
        question_text: "احسب عدد تأكسد المنجنيز في مركب برمنجانات البوتاسيوم KMnO₄.",
        correct_answer: "+7",
        explanation: "1(K) + Mn + 4(-2) = 0  =>  1 + Mn - 8 = 0  =>  Mn = +7.",
      },
    ],
  },
];

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

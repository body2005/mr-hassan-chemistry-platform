import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Calendar,
  CheckCircle2,
  CheckSquare,
  Clock,
  Edit3,
  FileQuestion,
  Loader2,
  Lock,
  PenTool,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { CalendarScheduleEvent, Course, NotificationItem, QuestionTypeConfig } from "../types/lms";
import { aiClient } from "../services/aiClient";
import { calendarService, notificationService } from "../services/lmsService";
import { GeneratedQuestion, QuizDraftResponse } from "../types/ai";
import { useToast } from "../components/ToastProvider";
import { FormulaRenderer } from "../components/FormulaRenderer";
import { RichFormulaEditor } from "../components/RichFormulaEditor";
import { formatChemicalFormula } from "../utils/formulaUtils";
import { quizHistoryService, PublishedQuizRecord } from "../services/quizHistoryService";
import { QuizHistorySection } from "../components/QuizHistorySection";

const QUIZ_DRAFT_STORAGE_KEY = "lms_quiz_maker_unuploaded_draft_v1";

function getInitialQuizDraft() {
  try {
    const raw = localStorage.getItem(QUIZ_DRAFT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    console.error("Error reading saved quiz draft:", e);
    return null;
  }
}

const DEFAULT_TYPE_CONFIGS: QuestionTypeConfig[] = [
  { id: "multiple_choice", label: "اختيار من متعدد (MCQ)", count: 2 },
  { id: "essay", label: "سؤال مقالي (Essay)", count: 1 },
  { id: "true_false", label: "صح أو خطأ (True/False)", count: 1, withCorrection: true },
  { id: "fill_in_blank", label: "أكمل الفراغات (Fill in the blank)", count: 1 },
  { id: "short_answer", label: "إجابة قصيرة (Short Answer)", count: 0 },
  { id: "numerical", label: "سؤال رقمي من المصدر (Numerical)", count: 0 },
  { id: "image_question", label: "سؤال مرتبط بصورة (Image)", count: 0 },
];

// Start a manual assessment empty; the teacher adds the first real question.
// This keeps sample/example content out of production screens.
const DEFAULT_MANUAL_QUESTIONS: GeneratedQuestion[] = [];

function formatLocalDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

interface QuizGeneratorViewProps {
  courses: Course[];
}

export const QuizGeneratorView: React.FC<QuizGeneratorViewProps> = ({ courses }) => {
  const toast = useToast();
  const initialDraftRef = useRef(getInitialQuizDraft());
  const initialDraft = initialDraftRef.current;

  const [hasRestoredDraft, setHasRestoredDraft] = useState<boolean>(() => !!initialDraft);

  const [extractingFile, setExtractingFile] = useState(false);
  const [extractedFileName, setExtractedFileName] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Mode: AI generation vs Manual Creation (Zero AI Requirement)
  const [creationMode, setCreationMode] = useState<"ai" | "manual">(() => initialDraft?.creationMode || "ai");
  // AI Quiz Mode: mix (extract first then generate), extract (verbatim from doc), generate (novel synthesis)
  const [quizMode, setQuizMode] = useState<"mix" | "extract" | "generate">(() => initialDraft?.quizMode || "mix");

  // Sub-tab: Creator vs History
  const [activeSubTab, setActiveSubTab] = useState<"create" | "history">("create");
  const [historyCount, setHistoryCount] = useState<number>(() => quizHistoryService.getHistory().length);

  useEffect(() => {
    const unsub = quizHistoryService.subscribe((list) => {
      setHistoryCount(list.length);
    });
    return () => unsub();
  }, []);

  // Confirmation Modal before upload / publish
  const [showPublishConfirmModal, setShowPublishConfirmModal] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  const [selectedAcademicYear, setSelectedAcademicYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">(
    () => initialDraft?.selectedAcademicYear || "1st_secondary"
  );
  const currentCourse = courses.find((c) => c.academicYear === selectedAcademicYear);
  const courseLessons = useMemo(() => currentCourse?.lessons || [], [currentCourse]);

  // Selected Lesson IDs
  const [selectedLessonIds, setSelectedLessonIds] = useState<string[]>(() => {
    if (Array.isArray(initialDraft?.selectedLessonIds) && initialDraft.selectedLessonIds.length > 0) {
      return initialDraft.selectedLessonIds;
    }
    const defaultCourse = courses.find((c) => c.academicYear === (initialDraft?.selectedAcademicYear || "1st_secondary"));
    return defaultCourse?.lessons?.[0] ? [defaultCourse.lessons[0].id] : [];
  });

  const isFirstMountRef = useRef(true);
  useEffect(() => {
    if (isFirstMountRef.current) {
      isFirstMountRef.current = false;
      if (initialDraft?.selectedLessonIds && initialDraft.selectedLessonIds.length > 0) {
        return;
      }
    }
    if (courseLessons.length > 0) {
      setSelectedLessonIds([courseLessons[0].id]);
    } else {
      setSelectedLessonIds([]);
    }
  }, [courseLessons, initialDraft?.selectedLessonIds]);

  // Activity Type: Quiz vs Assignment
  const [assessmentType, setAssessmentType] = useState<"quiz" | "assignment">(() => initialDraft?.assessmentType || "quiz");

  // Prompts start 100% EMPTY by default for teacher customization
  const [teacherPrompt, setTeacherPrompt] = useState(() => initialDraft?.teacherPrompt ?? "");
  const [gradingPrompt, setGradingPrompt] = useState(() => initialDraft?.gradingPrompt ?? "");

  // Quiz / Assignment Timing & Schedule Configuration
  const [quizDurationMinutes, setQuizDurationMinutes] = useState<number>(() => initialDraft?.quizDurationMinutes ?? 45);
  const [publishStartDate, setPublishStartDate] = useState<string>(() => initialDraft?.publishStartDate || formatLocalDate(new Date()));
  const [publishStartTime, setPublishStartTime] = useState<string>(() => initialDraft?.publishStartTime || "06:00 م");
  const [closeDeadlineDate, setCloseDeadlineDate] = useState<string>(() => {
    if (initialDraft?.closeDeadlineDate) return initialDraft.closeDeadlineDate;
    const future = new Date();
    future.setDate(future.getDate() + 3);
    return formatLocalDate(future);
  });
  const [closeDeadlineTime, setCloseDeadlineTime] = useState<string>(() => initialDraft?.closeDeadlineTime || "11:59 م");
  const [showOnStudentCalendar, setShowOnStudentCalendar] = useState<boolean>(() => initialDraft?.showOnStudentCalendar ?? true);
  const [sendScheduledNotification, setSendScheduledNotification] = useState<boolean>(() => initialDraft?.sendScheduledNotification ?? true);

  // Total questions count (AI mode)
  const [totalQuestions, setTotalQuestions] = useState(() => initialDraft?.totalQuestions ?? 5);

  // Question Types Config with Order & Counters (AI Mode)
  const [typeConfigs, setTypeConfigs] = useState<QuestionTypeConfig[]>(() => {
    if (Array.isArray(initialDraft?.typeConfigs) && initialDraft.typeConfigs.length > 0) {
      return initialDraft.typeConfigs;
    }
    return DEFAULT_TYPE_CONFIGS;
  });

  function normalizeQuestionType(t?: string): "multiple_choice" | "true_false" | "essay" | "fill_in_blank" {
    if (!t) return "multiple_choice";
    const upper = t.toUpperCase();
    if (upper === "MCQ" || upper === "MULTIPLE_CHOICE") return "multiple_choice";
    if (upper === "TRUE_FALSE" || upper === "TRUEFALSE") return "true_false";
    if (upper === "ESSAY") return "essay";
    if (upper === "FILL_BLANK" || upper === "FILL_IN_BLANK") return "fill_in_blank";
    return "multiple_choice";
  }

  function getQuestionTypeLabel(t?: string): { code: string; label: string; bg: string; color: string } {
    const norm = normalizeQuestionType(t);
    switch (norm) {
      case "multiple_choice":
        return { code: "MCQ", label: "اختيار من متعدد (MCQ)", bg: "rgba(16, 185, 129, 0.12)", color: "#065f46" };
      case "true_false":
        return { code: "TRUE_FALSE", label: "صح أو خطأ (True/False)", bg: "rgba(59, 130, 246, 0.12)", color: "#1e40af" };
      case "essay":
        return { code: "ESSAY", label: "سؤال مقالي (Essay)", bg: "rgba(245, 158, 11, 0.12)", color: "#92400e" };
      case "fill_in_blank":
        return { code: "FILL_BLANK", label: "أكمل الفراغات (Fill in the blank)", bg: "rgba(139, 92, 246, 0.12)", color: "#5b21b6" };
    }
  }

  function renderFillInBlankStem(text: string) {
    if (!text) return null;
    const regex = /(\[\.{2,}\]|\[فراغ\]|\[\s*\]|_+|\(\.{2,}\))/g;
    const parts = text.split(regex);

    if (parts.length <= 1) {
      return (
        <div style={{ display: "inline-flex", alignItems: "center", flexWrap: "wrap", gap: "8px", lineHeight: "2" }}>
          <FormulaRenderer inline text={text} />
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "4px 14px",
              minWidth: "140px",
              height: "30px",
              borderRadius: "6px",
              border: "2px dashed #059669",
              background: "var(--bg-surface-secondary)",
              color: "#059669",
              fontSize: "12px",
              fontWeight: 800,
            }}
          >
            [ خانة كتابة الإجابة ]
          </span>
        </div>
      );
    }

    return (
      <div style={{ display: "inline-flex", alignItems: "center", flexWrap: "wrap", gap: "6px", lineHeight: "2" }}>
        {parts.map((part, idx) => {
          if (/^(\[\.{2,}\]|\[فراغ\]|\[\s*\]|_+|\(\.{2,}\))$/.test(part)) {
            return (
              <span
                key={idx}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "3px 12px",
                  minWidth: "130px",
                  height: "28px",
                  borderRadius: "6px",
                  border: "2px solid #059669",
                  background: "var(--bg-surface-secondary)",
                  color: "#059669",
                  fontSize: "12px",
                  textAlign: "center",
                  fontWeight: 800,
                  boxShadow: "inset 0 1px 3px rgba(0,0,0,0.06)",
                }}
              >
                [ خانة إجابة الطالب ]
              </span>
            );
          }
          return <FormulaRenderer key={idx} inline text={part} />;
        })}
      </div>
    );
  }

  // Manual Mode State (Zero AI)
  const [manualTitle, setManualTitle] = useState(() => initialDraft?.manualTitle ?? "");
  const [manualDescription, setManualDescription] = useState(() => initialDraft?.manualDescription ?? "");
  const [manualQuestions, setManualQuestions] = useState<GeneratedQuestion[]>(() => {
    if (Array.isArray(initialDraft?.manualQuestions) && initialDraft.manualQuestions.length > 0) {
      return initialDraft.manualQuestions;
    }
    return DEFAULT_MANUAL_QUESTIONS;
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<QuizDraftResponse | null>(() => initialDraft?.draft || null);
  const [approved, setApproved] = useState(false);

  // Notify teacher on mount if an un-uploaded draft was restored
  useEffect(() => {
    if (initialDraft) {
      toast({
        message: "تم استعادة مسودة الاختبار غير المرفوعة تلقائياً!",
        tone: "info",
      });
    }
  }, [initialDraft, toast]);

  // ================= AUTO-SAVE PERSISTENCE FOR UN-UPLOADED QUIZ =================
  useEffect(() => {
    // If the quiz is approved/published, remove the un-uploaded draft
    if (approved) {
      localStorage.removeItem(QUIZ_DRAFT_STORAGE_KEY);
      setHasRestoredDraft(false);
      return;
    }

    const hasManual = creationMode === "manual" && (manualQuestions.length > 0 || manualTitle.trim().length > 0);
    const hasAi = creationMode === "ai" && draft && draft.questions && draft.questions.length > 0;

    if (!hasManual && !hasAi) {
      return;
    }

    const payload = {
      creationMode,
      quizMode,
      selectedAcademicYear,
      selectedLessonIds,
      assessmentType,
      quizDurationMinutes,
      publishStartDate,
      publishStartTime,
      closeDeadlineDate,
      closeDeadlineTime,
      showOnStudentCalendar,
      sendScheduledNotification,
      teacherPrompt,
      gradingPrompt,
      totalQuestions,
      typeConfigs,
      manualTitle,
      manualDescription,
      manualQuestions,
      draft,
      savedAt: new Date().toISOString(),
    };

    try {
      localStorage.setItem(QUIZ_DRAFT_STORAGE_KEY, JSON.stringify(payload));
      setHasRestoredDraft(true);
    } catch (e) {
      console.error("Failed to auto-save un-uploaded quiz draft:", e);
    }
  }, [
    approved,
    creationMode,
    quizMode,
    selectedAcademicYear,
    selectedLessonIds,
    assessmentType,
    quizDurationMinutes,
    publishStartDate,
    publishStartTime,
    closeDeadlineDate,
    closeDeadlineTime,
    showOnStudentCalendar,
    sendScheduledNotification,
    teacherPrompt,
    gradingPrompt,
    totalQuestions,
    typeConfigs,
    manualTitle,
    manualDescription,
    manualQuestions,
    draft,
  ]);

  function handleResetNewQuiz() {
    if (window.confirm("هل أنت متأكد من رغبتك في مسح مسودة هذا الاختبار الحالية والبدء باختبار جديد من البداية؟")) {
      localStorage.removeItem(QUIZ_DRAFT_STORAGE_KEY);
      setDraft(null);
      setManualTitle("");
      setManualDescription("");
      setTeacherPrompt("");
      setManualQuestions(DEFAULT_MANUAL_QUESTIONS);
      setApproved(false);
      setHasRestoredDraft(false);
      toast({
        message: "تم مسح المسودة والبدء باختبار جديد بنجاح.",
        tone: "info",
      });
    }
  }

  // Editing state for teacher modification (Part 11)
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);

  // Calculate sum of question type counters
  const totalAllocated = typeConfigs.reduce((sum, t) => sum + t.count, 0);



  function updateTypeCount(id: string, delta: number) {
    setTypeConfigs((prev) => {
      const updated = prev.map((t) => {
        if (t.id === id) {
          const newCount = Math.max(0, t.count + delta);
          return { ...t, count: newCount };
        }
        return t;
      });
      const newTotal = updated.reduce((s, t) => s + t.count, 0);
      setTotalQuestions(newTotal > 0 ? newTotal : 1);
      return updated;
    });
  }

  function toggleWithCorrection(id: string) {
    setTypeConfigs((prev) =>
      prev.map((t) => (t.id === id ? { ...t, withCorrection: !t.withCorrection } : t))
    );
  }

  function moveTypeOrder(index: number, direction: "up" | "down") {
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    if (targetIdx < 0 || targetIdx >= typeConfigs.length) return;

    const newConfigs = [...typeConfigs];
    const [moved] = newConfigs.splice(index, 1);
    newConfigs.splice(targetIdx, 0, moved);
    setTypeConfigs(newConfigs);
  }

  // ================= AI GENERATION HANDLER =================
  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setApproved(false);

    try {
      const selectedLessons = courseLessons.filter((l) =>
        selectedLessonIds.includes(l.id)
      );
      const targetLessons = selectedLessons.length > 0 ? selectedLessons : courseLessons;
      const lessonPassages = targetLessons.map(
        (l) => `${l.title}\n${l.description}\n${(l.flaggedHardConcepts || []).join("، ")}`.trim()
      );

      const allowedTypesList = typeConfigs
        .filter((t) => t.count > 0)
        .map((t) => t.id);

      const typeContext = assessmentType === "quiz" ? "اختبار تقييمي إلكتروني" : "واجب منزلي وتدريبات وتكليفات تطبيقية";
      const promptContext = teacherPrompt.trim()
        ? `نوع النشاط المطلوب: ${typeContext}\nتوجيهات المعلم: ${teacherPrompt.trim()}\n`
        : `نوع النشاط المطلوب: ${typeContext}\n`;

      const selectedCourseId = currentCourse?.id;
      if (!selectedCourseId) {
        setError("يرجى اختيار مادة دراسية صالحة أولاً لتوليد الاختبار منها.");
        return;
      }

      const resp = await aiClient.generateQuiz(
        {
          course_id: selectedCourseId,
          lesson_ids: targetLessons.map((l) => l.id),
          lesson_contents: lessonPassages.length > 0 ? lessonPassages : [promptContext],
          question_count: totalQuestions,
          allowed_types: allowedTypesList.length > 0 ? allowedTypesList : ["multiple_choice", "essay"],
          type_allocations: typeConfigs,
          topics: targetLessons.length > 0 ? targetLessons.map((l) => l.title) : [currentCourse?.title || "محتوى الدرس"],
          quiz_mode: quizMode,
          title: manualTitle.trim() || `${assessmentType === "quiz" ? "اختبار" : "واجب"}: ${currentCourse.title}`,
        },
        false
      );

      setDraft(resp);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "عذراً، حدث خطأ أثناء توليد مسودة الاختبار. تأكد من تشغيل خادم الذكاء الاصطناعي ورفع محتوى الدرس.");
    } finally {
      setLoading(false);
    }
  }

  // ================= EXTRACT QUIZ DIRECTLY FROM UPLOADED FILE =================
  async function handleExtractFromFile(file: File) {
    if (!file) return;
    setExtractingFile(true);
    setError(null);
    try {
      const resp = await aiClient.extractQuizFromFile(
        file,
        currentCourse?.id,
        selectedLessonIds.length > 0 ? selectedLessonIds[0] : undefined
      );

      if (!resp.questions || resp.questions.length === 0) {
        throw new Error("لم يتم العثور على أسئلة واضحة في الملف. يرجى التأكد من احتواء الملف على أسئلة أو ورقة امتحان.");
      }

      setDraft(resp);
      setExtractedFileName(file.name);
      setCreationMode("ai");
      setApproved(false);

      toast({
        message: `تم استخراج ${resp.questions.length} سؤال بنجاح من ملف "${file.name}"!`,
        tone: "success",
      });
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "فشل استخراج الأسئلة من الملف. يرجى التأكد من صحة الملف وصيغته.";
      setError(errMsg);
      toast({
        message: errMsg,
        tone: "danger",
      });
    } finally {
      setExtractingFile(false);
    }
  }

  // ================= GENERATE MORE FROM CONTEXT =================
  async function handleGenerateMore() {
    if (!draft || draft.questions.length === 0) return;
    setLoading(true);
    setError(null);

    try {
      const selectedLessons = courseLessons.filter((l) =>
        selectedLessonIds.includes(l.id)
      );
      const targetLessons = selectedLessons.length > 0 ? selectedLessons : courseLessons;
      const lessonPassages = targetLessons.map(
        (l) => `${l.title}\n${l.description}\n${(l.flaggedHardConcepts || []).join("، ")}`.trim()
      );

      const allowedTypesList = typeConfigs
        .filter((t) => t.count > 0)
        .map((t) => t.id);

      const existingStems = draft.questions.map((q) => q.question_text);

      const selectedCourseId = currentCourse?.id;
      if (!selectedCourseId) {
        setError("يرجى اختيار مادة دراسية صالحة أولاً.");
        return;
      }

      const resp = await aiClient.generateQuiz(
        {
          course_id: selectedCourseId,
          lesson_ids: targetLessons.map((l) => l.id),
          lesson_contents: lessonPassages.length > 0 ? lessonPassages : [""],
          question_count: totalQuestions,
          allowed_types: allowedTypesList.length > 0 ? allowedTypesList : ["multiple_choice", "essay"],
          type_allocations: typeConfigs,
          topics: targetLessons.length > 0 ? targetLessons.map((l) => l.title) : [currentCourse?.title || "محتوى الدرس"],
          quiz_mode: quizMode,
          exclude_stems: existingStems,
          title: manualTitle.trim() || `${assessmentType === "quiz" ? "اختبار" : "واجب"}: ${currentCourse.title}`,
        },
        true
      );

      const newQuestions = (resp.questions || []).filter(
        (nq) => !existingStems.some((stem) => stem.trim().toLowerCase() === nq.question_text.trim().toLowerCase())
      );

      if (newQuestions.length === 0) {
        setError("لم يتم العثور على أسئلة إضافية جديدة لم تُذكر من قبل في هذا الدرس.");
        return;
      }

      const startId = draft.questions.length + 1;
      const renumbered = newQuestions.map((q, idx) => ({ ...q, id: startId + idx }));
      const combined = [...draft.questions, ...renumbered];
      const newTotal = combined.reduce((sum, q) => sum + (q.points || 0), 0);

      setDraft({
        ...draft,
        questions: combined,
        total_points: newTotal,
        is_complete: resp.is_complete !== false,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "حدث خطأ أثناء توليد المزيد من الأسئلة.");
    } finally {
      setLoading(false);
    }
  }

  // ================= QUESTIONS EDITING & REORDERING =================
  function activeQuestionsList(): GeneratedQuestion[] {
    return creationMode === "manual" ? manualQuestions : draft?.questions || [];
  }

  function setActiveQuestionsList(updater: (prev: GeneratedQuestion[]) => GeneratedQuestion[]) {
    if (creationMode === "manual") {
      setManualQuestions((prev) => updater(prev));
    } else if (draft) {
      const updated = updater(draft.questions);
      const newTotal = updated.reduce((s, q) => s + (q.points || 0), 0);
      setDraft({ ...draft, questions: updated, total_points: newTotal });
    }
  }

  function updateQuestionText(qId: number, newText: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, question_text: newText } : q))
    );
  }

  function updateQuestionPoints(qId: number, newPoints: number) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, points: Math.max(1, newPoints) } : q))
    );
  }

  function updateQuestionCorrectAnswer(qId: number, newAnswer: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, correct_answer: newAnswer } : q))
    );
  }

  function insertBlankMarker(qId: number) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => {
        if (q.id !== qId) return q;
        const currentText = q.question_text || "";
        const updated = currentText.includes("[.....]") || currentText.includes("[....]")
          ? `${currentText.trim()} [.....] `
          : (currentText ? `${currentText.trim()} [.....] ` : "اكتب السؤال هنا ثم ضع الفراغ: [.....] ");
        return { ...q, question_text: updated };
      })
    );
  }

  function updateQuestionType(qId: number, newType: "multiple_choice" | "essay" | "true_false" | "fill_in_blank") {
    setActiveQuestionsList((prev) =>
      prev.map((q) => {
        if (q.id !== qId) return q;
        let newOptions = q.options;
        if (newType === "multiple_choice" && (!newOptions || newOptions.length < 2)) {
          newOptions = [
            { key: "أ", text: "الخيار أ", is_correct: true },
            { key: "ب", text: "الخيار ب", is_correct: false },
            { key: "ج", text: "الخيار ج", is_correct: false },
            { key: "د", text: "الخيار د", is_correct: false },
          ];
        } else if (newType === "true_false") {
          newOptions = [
            { key: "أ", text: "صح", is_correct: true },
            { key: "ب", text: "خطأ", is_correct: false },
          ];
        } else if (newType === "essay" || newType === "fill_in_blank") {
          newOptions = undefined;
        }
        return {
          ...q,
          question_type: newType,
          options: newOptions,
        };
      })
    );
  }

  function updateOptionText(qId: number, optKey: string, newText: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => {
        if (q.id === qId && q.options) {
          return {
            ...q,
            options: q.options.map((opt) => (opt.key === optKey ? { ...opt, text: newText } : opt)),
          };
        }
        return q;
      })
    );
  }

  function setCorrectOption(qId: number, optKey: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => {
        if (q.id === qId && q.options) {
          return {
            ...q,
            options: q.options.map((opt) => ({
              ...opt,
              is_correct: opt.key === optKey,
            })),
            correct_answer: q.options.find((o) => o.key === optKey)?.text || optKey,
          };
        }
        return q;
      })
    );
  }

  function addOptionToQuestion(qId: number) {
    const keys = ["أ", "ب", "ج", "د", "هـ", "و"];
    setActiveQuestionsList((prev) =>
      prev.map((q) => {
        if (q.id === qId && q.options) {
          const nextKey = keys[q.options.length] || `خيار ${q.options.length + 1}`;
          return {
            ...q,
            options: [...q.options, { key: nextKey, text: `خيار جديد (${nextKey})`, is_correct: false }],
          };
        }
        return q;
      })
    );
  }

  function removeOptionFromQuestion(qId: number, optKey: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => {
        if (q.id === qId && q.options && q.options.length > 2) {
          const filtered = q.options.filter((o) => o.key !== optKey);
          if (!filtered.some((o) => o.is_correct) && filtered.length > 0) {
            filtered[0].is_correct = true;
          }
          return { ...q, options: filtered };
        }
        return q;
      })
    );
  }

  function moveQuestionOrder(qIdx: number, direction: "up" | "down") {
    setActiveQuestionsList((prev) => {
      const targetIdx = direction === "up" ? qIdx - 1 : qIdx + 1;
      if (targetIdx < 0 || targetIdx >= prev.length) return prev;
      const copy = [...prev];
      const [moved] = copy.splice(qIdx, 1);
      copy.splice(targetIdx, 0, moved);
      return copy;
    });
  }

  function deleteQuestion(qId: number) {
    setActiveQuestionsList((prev) => prev.filter((q) => q.id !== qId));
  }

  function addNewManualQuestion() {
    const newId = Date.now();
    const newQ: GeneratedQuestion = {
      id: newId,
      question_type: "multiple_choice",
      difficulty: "medium",
      topic: currentCourse?.title || "الكيمياء",
      question_text: "اكتب نص السؤال الجديد هنا...",
      points: 5,
      correct_answer: "الخيار أ",
      explanation: "شرح الإجابة الصحيحة ومعيار التصحيح...",
      options: [
        { key: "أ", text: "الخيار أ (الصحيح)", is_correct: true },
        { key: "ب", text: "الخيار ب", is_correct: false },
        { key: "ج", text: "الخيار ج", is_correct: false },
        { key: "د", text: "الخيار د", is_correct: false },
      ],
    };

    setActiveQuestionsList((prev) => [...prev, newQ]);
    setEditingQuestionId(newId);
  }

  // ================= PUBLISH & SCHEDULE HANDLER (AI & MANUAL) =================
  function handleInitiatePublish() {
    const currentQuestions = activeQuestionsList();
    const isQuiz = assessmentType === "quiz";

    // Show error if there are no questions in the quiz
    if (currentQuestions.length === 0) {
      const emptyMsg = `لا يمكن حفظ أو رفع ${isQuiz ? "الاختبار" : "الواجب"} وهو فارغ. يرجى إضافة سؤال واحد على الأقل أولاً.`;
      setError(emptyMsg);
      toast({
        message: emptyMsg,
        tone: "warning",
      });
      return;
    }

    setError(null);
    setShowPublishConfirmModal(true);
  }

  async function handleConfirmPublish() {
    const currentQuestions = activeQuestionsList();
    const isQuiz = assessmentType === "quiz";

    if (currentQuestions.length === 0) {
      setError(`لا يمكن حفظ أو رفع ${isQuiz ? "الاختبار" : "الواجب"} وهو فارغ. يرجى إضافة سؤال واحد على الأقل أولاً.`);
      setShowPublishConfirmModal(false);
      return;
    }

    setIsPublishing(true);
    try {
      const yearLabel =
        selectedAcademicYear === "1st_secondary"
          ? "الصف الأول الثانوي"
          : selectedAcademicYear === "2nd_secondary"
          ? "الصف الثاني الثانوي"
          : "الصف الثالث الثانوي";

      // The teacher's title is authoritative for both manual and AI/extracted
      // assessments. If left blank, keep the generated/extracted title.
      const titleToPublish = manualTitle.trim()
        || (creationMode === "ai" ? draft?.title : "")
        || `${isQuiz ? "اختبار" : "واجب"}: ${yearLabel}`;

      // 1. Mark in Calendar Schedule for Teacher & Students
      const newCalendarEvent: CalendarScheduleEvent = {
        id: `evt_${assessmentType}_${Date.now()}`,
        academicYear: selectedAcademicYear,
        date: publishStartDate,
        dayName: `${isQuiz ? "اختبار" : "واجب"}: ${titleToPublish}`,
        time: publishStartTime,
        contentType: assessmentType,
        isPublishedToStudents: showOnStudentCalendar,
        quizDurationMinutes: isQuiz ? quizDurationMinutes : undefined,
        publishStartDate,
        publishStartTime,
        closeDeadline: `${closeDeadlineDate} ${closeDeadlineTime}`,
      };

      await calendarService.saveCalendarEvent(newCalendarEvent);

      // 2. Send Scheduled / Instant Notification to Students
      if (sendScheduledNotification) {
        const newNotif: NotificationItem = {
          id: `notif_${assessmentType}_${Date.now()}`,
          title: `${isQuiz ? "اختبار جديد" : "واجب منزلي جديد"}: ${titleToPublish}`,
          message: isQuiz
            ? `تم نشر اختبار (${titleToPublish}) لطلاب ${yearLabel}. مدة الحل: ${quizDurationMinutes} دقيقة. يبدأ: ${publishStartDate} الساعة ${publishStartTime}، ومتاح الدخول والحل حتى: ${closeDeadlineDate} الساعة ${closeDeadlineTime}.`
            : `تم نشر واجب منزلي (${titleToPublish}) لطلاب ${yearLabel}. يبدأ من: ${publishStartDate} الساعة ${publishStartTime}، وآخر موعد لتسليم الحل هو: ${closeDeadlineDate} الساعة ${closeDeadlineTime}.`,
          type: assessmentType,
          targetYear: selectedAcademicYear,
          dueDate: `${closeDeadlineDate} ${closeDeadlineTime}`,
          createdAt: "الآن",
          read: false,
          actionTab: "MyCourses",
          quizDurationMinutes: isQuiz ? quizDurationMinutes : undefined,
          quizCloseDeadline: `${closeDeadlineDate} ${closeDeadlineTime}`,
        };

        await notificationService.saveNotification(newNotif);
      }

      // 3. Save to Teacher Quiz History Archive
      quizHistoryService.saveQuiz({
        title: titleToPublish,
        assessmentType,
        academicYear: selectedAcademicYear,
        academicYearLabel: yearLabel,
        creationMode,
        quizMode: creationMode === "ai" ? quizMode : undefined,
        publishStartDate,
        publishStartTime,
        closeDeadlineDate,
        closeDeadlineTime,
        closeDeadline: `${closeDeadlineDate} ${closeDeadlineTime}`,
        quizDurationMinutes: isQuiz ? quizDurationMinutes : undefined,
        showOnStudentCalendar,
        totalPoints: totalPointsCount,
        questionsCount: currentQuestions.length,
        questions: currentQuestions,
        courseId: currentCourse?.id,
        selectedLessonIds,
      });

      setApproved(true);
      setShowPublishConfirmModal(false);
      localStorage.removeItem(QUIZ_DRAFT_STORAGE_KEY);
      setHasRestoredDraft(false);
      toast({
        message: `تم اعتماد ونشر ${isQuiz ? "الاختبار" : "الواجب"} وإدراجه في سجل الاختبارات المرفوعة وجدول الطلاب بنجاح!`,
        tone: "success",
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "حدث خطأ أثناء حفظ ونشر الاختبار.");
    } finally {
      setIsPublishing(false);
    }
  }

  function handleLoadQuizIntoEditor(quizRecord: PublishedQuizRecord) {
    setAssessmentType(quizRecord.assessmentType);
    setSelectedAcademicYear(quizRecord.academicYear);
    if (quizRecord.creationMode === "ai" && quizRecord.quizMode) {
      setQuizMode(quizRecord.quizMode);
    }
    setCreationMode("manual");
    setManualTitle(quizRecord.title);
    setManualQuestions(quizRecord.questions);
    if (quizRecord.publishStartDate) setPublishStartDate(quizRecord.publishStartDate);
    if (quizRecord.publishStartTime) setPublishStartTime(quizRecord.publishStartTime);
    if (quizRecord.closeDeadlineDate) setCloseDeadlineDate(quizRecord.closeDeadlineDate);
    if (quizRecord.closeDeadlineTime) setCloseDeadlineTime(quizRecord.closeDeadlineTime);
    if (quizRecord.quizDurationMinutes) setQuizDurationMinutes(quizRecord.quizDurationMinutes);
    setShowOnStudentCalendar(quizRecord.showOnStudentCalendar);
    setApproved(false);
    setActiveSubTab("create");
    toast({
      message: `تم فتح اختبار (${quizRecord.title}) في الصانع للتعديل.`,
      tone: "success",
    });
  }

  const displayedQuestions = activeQuestionsList();
  const totalPointsCount = displayedQuestions.reduce((sum, q) => sum + (q.points || 0), 0);

  return (
    <div className="page-container">
      {/* Top View Selector: Create New vs Quiz History Archive */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          marginBottom: "24px",
          paddingBottom: "16px",
          borderBottom: "1.5px solid var(--border-color, #e2e8f0)",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "8px",
            background: "var(--bg-surface-secondary, #f1f5f9)",
            padding: "5px",
            borderRadius: "14px",
            border: "1px solid var(--border-color, #cbd5e1)",
            flexWrap: "wrap",
            width: "100%",
            maxWidth: "480px",
          }}
        >
          <button
            type="button"
            onClick={() => setActiveSubTab("create")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              padding: "9px 14px",
              borderRadius: "10px",
              border: "none",
              background: activeSubTab === "create" ? "#0f392b" : "transparent",
              color: activeSubTab === "create" ? "#ffffff" : "var(--text-main, #0f172a)",
              fontWeight: 800,
              fontSize: "12.5px",
              cursor: "pointer",
              transition: "all 0.2s ease",
              flex: 1,
              minWidth: "140px",
            }}
          >
            <Sparkles size={15} />
            <span>صانع وتوليد الاختبارات</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab("history")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              padding: "9px 14px",
              borderRadius: "10px",
              border: "none",
              background: activeSubTab === "history" ? "#0f392b" : "transparent",
              color: activeSubTab === "history" ? "#ffffff" : "var(--text-main, #0f172a)",
              fontWeight: 800,
              fontSize: "12.5px",
              cursor: "pointer",
              transition: "all 0.2s ease",
              flex: 1,
              minWidth: "160px",
            }}
          >
            <FileQuestion size={15} />
            <span>سجل الاختبارات المرفوعة</span>
            {historyCount > 0 && (
              <span
                style={{
                  background: activeSubTab === "history" ? "#34d399" : "#0f392b",
                  color: activeSubTab === "history" ? "#064e3b" : "#ffffff",
                  fontSize: "11px",
                  fontWeight: 800,
                  padding: "2px 8px",
                  borderRadius: "12px",
                }}
              >
                {historyCount}
              </span>
            )}
          </button>
        </div>

      </div>

      {activeSubTab === "history" ? (
        <QuizHistorySection
          onSwitchToCreator={() => setActiveSubTab("create")}
          onLoadQuizIntoEditor={handleLoadQuizIntoEditor}
        />
      ) : (
        <>
          {/* Header & Mode Switcher */}
          <div style={{ marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "14px" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 800, color: assessmentType === "quiz" ? "#0f766e" : "#0f392b", background: assessmentType === "quiz" ? "#ccfbf1" : "#ecfdf5", padding: "3px 8px", borderRadius: "6px" }}>
            استوديو المعلم • {creationMode === "ai" ? "AI AUTOMATED AUTHORING" : "MANUAL CUSTOM AUTHORING"}
          </span>
          <h1 style={{ margin: "6px 0 2px", fontSize: "24px", color: "var(--text-main, #0f172a)" }}>
            {assessmentType === "quiz" ? "صانع الاختبارات والتقييمات" : "صانع الواجبات والتكليفات المنزلية"}
          </h1>
          <p style={{ margin: 0, color: "var(--text-muted, #64748b)", fontSize: "13px" }}>
            {creationMode === "ai"
              ? "استعن بالذكاء الاصطناعي لصياغة أسئلة تقييمية مستنبطة من محتوى الدرس والمذكرات المرفوعة بدقة."
              : "اكتب وصمم أسئلتك وخيارات الإجابة والدرجات يدوياً بالكامل دون الحاجة للذكاء الاصطناعي."}
          </p>
        </div>

        {/* Mode Tabs: AI vs Manual */}
        <div style={{ display: "flex", background: "var(--bg-surface-secondary, #f1f5f9)", padding: "4px", borderRadius: "12px", border: "1px solid var(--border-color, #e2e8f0)", flexWrap: "wrap", gap: "4px", width: "100%", maxWidth: "420px" }}>
          <button
            type="button"
            onClick={() => { setCreationMode("ai"); setApproved(false); }}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "8px 12px",
              borderRadius: "8px",
              border: "none",
              background: creationMode === "ai" ? "#0f392b" : "transparent",
              color: creationMode === "ai" ? "#ffffff" : "var(--text-main)",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
              transition: "all 0.2s ease",
              flex: 1,
              minWidth: "130px",
            }}
          >
            <Sparkles size={14} />
            <span>توليد بالذكاء الاصطناعي</span>
          </button>

          <button
            type="button"
            onClick={() => { setCreationMode("manual"); setApproved(false); }}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "8px 12px",
              borderRadius: "8px",
              border: "none",
              background: creationMode === "manual" ? "#0f392b" : "transparent",
              color: creationMode === "manual" ? "#ffffff" : "var(--text-main)",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
              transition: "all 0.2s ease",
              flex: 1,
              minWidth: "150px",
            }}
          >
            <PenTool size={14} />
            <span>إنشاء يدوي مباشر (بدون AI)</span>
          </button>
        </div>
      </div>

      <div className="responsive-split-grid">
        {/* Left Column: Configuration Form */}
        <div style={{ background: "var(--bg-surface, #ffffff)", border: "1px solid var(--border-color, #e2e8f0)", borderRadius: "16px", padding: "20px" }}>
          {/* Assessment Mode Selector (Quiz vs Assignment) */}
          <div style={{ marginBottom: "18px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 800, marginBottom: "6px", color: "var(--text-main)" }}>
              نوع النشاط التعليمي:
            </label>
            <div className="responsive-2col" style={{ gap: "8px" }}>
              <button
                type="button"
                onClick={() => setAssessmentType("quiz")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                  padding: "10px 6px",
                  borderRadius: "10px",
                  border: assessmentType === "quiz" ? "2px solid #0f766e" : "1px solid var(--border-color)",
                  background: assessmentType === "quiz" ? "#0f766e" : "var(--bg-surface-secondary)",
                  color: assessmentType === "quiz" ? "#ffffff" : "var(--text-main)",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                <span>اختبار إلكتروني (Quiz)</span>
              </button>

              <button
                type="button"
                onClick={() => setAssessmentType("assignment")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                  padding: "10px 6px",
                  borderRadius: "10px",
                  border: assessmentType === "assignment" ? "2px solid #0f392b" : "1px solid var(--border-color)",
                  background: assessmentType === "assignment" ? "#0f392b" : "var(--bg-surface-secondary)",
                  color: assessmentType === "assignment" ? "#ffffff" : "var(--text-main)",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                <span>واجب منزلي (Assignment)</span>
              </button>
            </div>
          </div>

          {/* Academic Year Selection */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "6px", color: "var(--text-main)" }}>
              الصف الدراسي:
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "6px", marginBottom: "12px" }}>
              {[
                { id: "1st_secondary" as const, label: "الأول الثانوي" },
                { id: "2nd_secondary" as const, label: "الثاني الثانوي" },
                { id: "3rd_secondary" as const, label: "الثالث الثانوي" },
              ].map((y) => (
                <button
                  key={y.id}
                  type="button"
                  onClick={() => setSelectedAcademicYear(y.id)}
                  style={{
                    padding: "8px 2px",
                    borderRadius: "8px",
                    border: selectedAcademicYear === y.id ? "2px solid #059669" : "1px solid var(--border-color)",
                    background: selectedAcademicYear === y.id ? "#0f392b" : "var(--bg-surface-secondary)",
                    color: selectedAcademicYear === y.id ? "#ffffff" : "var(--text-main)",
                    fontSize: "11.5px",
                    fontWeight: 800,
                    cursor: "pointer",
                    textAlign: "center",
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {y.label}
                </button>
              ))}
            </div>


          </div>

          {/* Assessment title is editable for manual, generated, and extracted work. */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
              اسم {assessmentType === "quiz" ? "الاختبار" : "الواجب"}:
            </label>
            <input
              type="text"
              value={manualTitle}
              onChange={(e) => setManualTitle(e.target.value)}
              placeholder={draft?.title || `مثال: ${assessmentType === "quiz" ? "اختبار الكيمياء — الروابط والمعادلات الكيميائية" : "واجب تدريبات الحساب الكيميائي والمول"}`}
              style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", fontSize: "13px", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box", marginBottom: creationMode === "manual" ? "10px" : 0 }}
            />

            {creationMode === "manual" && <>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                الوصف والتعليمات للطلاب:
              </label>
              <textarea
                rows={2}
                value={manualDescription}
                onChange={(e) => setManualDescription(e.target.value)}
                placeholder="اكتب تعليمات الحل أو ملاحظات هامة للطلاب قبل البدء..."
                style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", fontSize: "12px", lineHeight: "1.4", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box" }}
              />
            </>}
          </div>

          {/* AI MODE: Custom Empty Teacher Prompt */}
          {creationMode === "ai" && (
            <>
              {/* Quiz Generation Mode (Mix vs Extract vs Generate) */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "6px", color: "var(--text-main)" }}>
                  طريقة اشتقاق الأسئلة (Quiz Mode):
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px" }}>
                  {[
                    { id: "mix" as const, label: "مزيج متكامل", desc: "استخراج ثم توليد" },
                    { id: "extract" as const, label: "استخراج فقط", desc: "أسئلة المذكرات" },
                    { id: "generate" as const, label: "توليد فقط", desc: "ابتكار مفاهيمي" },
                  ].map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setQuizMode(m.id)}
                      style={{
                        padding: "8px 4px",
                        borderRadius: "8px",
                        border: quizMode === m.id ? "2px solid #0f766e" : "1px solid var(--border-color)",
                        background: quizMode === m.id ? "#0f766e" : "var(--bg-surface-secondary)",
                        color: quizMode === m.id ? "#ffffff" : "var(--text-main)",
                        cursor: "pointer",
                        textAlign: "center",
                        display: "flex",
                        flexDirection: "column",
                        gap: "2px",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ fontSize: "12px", fontWeight: 800 }}>{m.label}</span>
                      <span style={{ fontSize: "10px", opacity: 0.85 }}>{m.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Dedicated File Upload for Question Extraction */}
              {(quizMode === "extract" || quizMode === "mix") && (
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    if (e.dataTransfer.files?.[0]) handleExtractFromFile(e.dataTransfer.files[0]);
                  }}
                  style={{
                    marginBottom: "16px",
                    padding: "14px",
                    background: dragOver ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface-secondary, #f8fafc)",
                    border: dragOver ? "2px dashed #0f766e" : "1.5px dashed var(--border-accent, #0f766e)",
                    borderRadius: "10px",
                    textAlign: "center",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 800, color: "#0f766e", display: "flex", alignItems: "center", gap: "5px" }}>
                      <UploadCloud size={15} /> رفع ملف أسئلة للاستخراج الفوري
                    </span>
                    <span style={{ fontSize: "10px", background: "#ccfbf1", color: "#0f766e", padding: "2px 6px", borderRadius: "4px", fontWeight: 700 }}>
                      PDF / DOCX / TXT / صور
                    </span>
                  </div>

                  <input
                    type="file"
                    ref={fileInputRef}
                    accept=".pdf,.docx,.doc,.txt,.json,.png,.jpg,.jpeg"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleExtractFromFile(f);
                      e.target.value = "";
                    }}
                  />

                  {extractingFile ? (
                    <div style={{ padding: "12px 0", color: "#0f766e" }}>
                      <Loader2 size={24} className="animate-spin" style={{ margin: "0 auto 6px" }} />
                      <div style={{ fontSize: "12px", fontWeight: 700 }}>جاري استخراج الأسئلة من الملف...</div>
                      <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>تحليل الأسئلة والخيارات والرسومات التوضيحية</div>
                    </div>
                  ) : extractedFileName ? (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", background: "#ecfdf5", border: "1px solid #a7f3d0", padding: "8px 10px", borderRadius: "6px", marginBottom: "8px" }}>
                        <CheckCircle2 size={16} color="#059669" />
                        <span style={{ fontSize: "11.5px", color: "#065f46", fontWeight: 700, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {extractedFileName}
                        </span>
                        <button
                          type="button"
                          onClick={() => setExtractedFileName(null)}
                          style={{ background: "none", border: "none", cursor: "pointer", padding: "2px", color: "#991b1b" }}
                          title="إلغاء الملف"
                        >
                          <X size={14} />
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="btn-secondary"
                        style={{ width: "100%", padding: "7px", fontSize: "12px", fontWeight: 700, justifyContent: "center", gap: "6px" }}
                      >
                        <UploadCloud size={14} /> استخراج من ملف آخر
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p style={{ margin: "0 0 10px", fontSize: "11.5px", color: "var(--text-muted)", lineHeight: 1.4 }}>
                        ارفع ورقة امتحان أو بنك أسئلة لاستخراج الأسئلة وتعبئتها فوراً في المسودة
                      </p>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          borderRadius: "6px",
                          border: "1px solid #0f766e",
                          background: "#0f766e",
                          color: "#ffffff",
                          fontSize: "12px",
                          fontWeight: 700,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: "6px",
                        }}
                      >
                        <UploadCloud size={15} /> اختر ملف الامتحان لاستخراجه
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                  توجيهات إضافية للذكاء الاصطناعي (Prompt اختياري):
                </label>
                <textarea
                  rows={2}
                  value={teacherPrompt}
                  onChange={(e) => setTeacherPrompt(e.target.value)}
                  placeholder="اكتب أي موضوعات أو نقاط تركيز خاصة تود أن يركز عليها الذكاء الاصطناعي..."
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", fontSize: "12px", lineHeight: "1.4", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box" }}
                />
              </div>

              {/* Total Question Count in AI Mode */}
              <div style={{ marginBottom: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-main)" }}>
                    إجمالي عدد الأسئلة المطلوبة:
                  </label>
                  <strong style={{ fontSize: "14px", color: "#059669" }}>{totalQuestions} أسئلة</strong>
                </div>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={totalQuestions}
                  onChange={(e) => setTotalQuestions(Math.max(1, parseInt(e.target.value) || 1))}
                  style={{
                    width: "100%",
                    padding: "8px 14px",
                    border: "2px solid var(--border-accent, #059669)",
                    borderRadius: "8px",
                    fontSize: "15px",
                    fontWeight: 800,
                    color: "var(--text-main)",
                    background: "var(--bg-surface-secondary, #f8fafc)",
                    textAlign: "center",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              {/* Question Types Config in AI Mode */}
              <div style={{ marginBottom: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-main)" }}>
                    توزيع أنواع الأسئلة:
                  </label>
                  <span style={{ fontSize: "11px", fontWeight: 800, color: totalAllocated === totalQuestions ? "#059669" : "#d97706" }}>
                    المجموع: {totalAllocated} / {totalQuestions}
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {typeConfigs.map((type, idx) => (
                    <div
                      key={type.id}
                      style={{
                        background: "var(--bg-surface-secondary, #f8fafc)",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        borderRadius: "8px",
                        padding: "8px 10px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <div style={{ display: "flex", flexDirection: "column" }}>
                            <button
                              type="button"
                              onClick={() => moveTypeOrder(idx, "up")}
                              disabled={idx === 0}
                              style={{ background: "none", border: "none", padding: 0, cursor: idx === 0 ? "not-allowed" : "pointer", opacity: idx === 0 ? 0.3 : 1 }}
                            >
                              <ArrowUp size={12} />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveTypeOrder(idx, "down")}
                              disabled={idx === typeConfigs.length - 1}
                              style={{ background: "none", border: "none", padding: 0, cursor: idx === typeConfigs.length - 1 ? "not-allowed" : "pointer", opacity: idx === typeConfigs.length - 1 ? 0.3 : 1 }}
                            >
                              <ArrowDown size={12} />
                            </button>
                          </div>
                          <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>
                            {idx + 1}. {type.label}
                          </strong>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <button
                            type="button"
                            onClick={() => updateTypeCount(type.id, -1)}
                            style={{ width: "24px", height: "24px", borderRadius: "6px", border: "1px solid var(--border-color-strong)", background: "var(--bg-surface)", cursor: "pointer", fontWeight: 800 }}
                          >
                            -
                          </button>
                          <strong style={{ width: "18px", textAlign: "center", fontSize: "12px", color: "#0f392b" }}>
                            {type.count}
                          </strong>
                          <button
                            type="button"
                            onClick={() => updateTypeCount(type.id, 1)}
                            style={{ width: "24px", height: "24px", borderRadius: "6px", border: "1px solid var(--border-color-strong)", background: "var(--bg-surface)", cursor: "pointer", fontWeight: 800 }}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {type.id === "true_false" && type.count > 0 && (
                        <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--text-muted)", marginTop: "2px", cursor: "pointer" }}>
                          <input
                            type="checkbox"
                            checked={type.withCorrection}
                            onChange={() => toggleWithCorrection(type.id)}
                            style={{ accentColor: "#0f392b" }}
                          />
                          <span>تفعيل مع التصحيح (مطالبة الطالب بذكر تصحيح الخطأ)</span>
                        </label>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* AI Grading Prompt (Empty by default) */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                  معايير التصحيح الذاتي (AI Grading Prompt - اختياري):
                </label>
                <textarea
                  rows={2}
                  value={gradingPrompt}
                  onChange={(e) => setGradingPrompt(e.target.value)}
                  placeholder="اكتب معايير وتوجيهات التصحيح التي تريد أن يتبعها المصحح الذكي..."
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--border-color-strong)", borderRadius: "8px", fontSize: "12px", lineHeight: "1.4", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box" }}
                />
              </div>
            </>
          )}

          {/* Schedule & Timing Configuration */}
          <div style={{ marginBottom: "18px", background: "var(--bg-surface-secondary, #f8fafc)", border: "1.5px solid var(--border-color, #e2e8f0)", borderRadius: "10px", padding: "14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
              <Clock size={16} style={{ color: "#059669" }} />
              <strong style={{ fontSize: "13px", color: "var(--text-main)" }}>
                مواعيد الإتاحة ومدة الحل:
              </strong>
            </div>

            {/* Exam Timer */}
            {assessmentType === "quiz" && (
              <div style={{ marginBottom: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label style={{ fontSize: "11.5px", fontWeight: 700, color: "var(--text-main)" }}>
                    مدة حل الاختبار للطالب:
                  </label>
                  <strong style={{ fontSize: "13px", color: "#059669" }}>{quizDurationMinutes} دقيقة</strong>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    step={5}
                    value={quizDurationMinutes}
                    onChange={(e) => setQuizDurationMinutes(Math.max(5, parseInt(e.target.value) || 45))}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "6px",
                      fontSize: "13px",
                      fontWeight: 800,
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                    }}
                  />
                  <span style={{ fontSize: "12px", color: "var(--text-muted)", flexShrink: 0 }}>دقيقة</span>
                </div>
              </div>
            )}

            {/* Start Date & Time */}
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "11.5px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                {assessmentType === "quiz" ? "موعد النشر وبدء الإتاحة:" : "موعد نشر الواجب:"}
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "6px" }}>
                <input
                  type="date"
                  value={publishStartDate}
                  onChange={(e) => setPublishStartDate(e.target.value)}
                  style={{ width: "100%", boxSizing: "border-box", minWidth: 0, padding: "7px 10px", border: "1px solid var(--border-color-strong)", borderRadius: "6px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)" }}
                />
                <input
                  type="text"
                  value={publishStartTime}
                  onChange={(e) => setPublishStartTime(e.target.value)}
                  placeholder="06:00 م"
                  style={{ width: "100%", boxSizing: "border-box", minWidth: 0, padding: "7px 10px", border: "1px solid var(--border-color-strong)", borderRadius: "6px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)", textAlign: "center" }}
                />
              </div>
            </div>

            {/* Close Date & Time */}
            <div style={{ marginBottom: "12px" }}>
              <label style={{ display: "block", fontSize: "11.5px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                {assessmentType === "quiz" ? "موعد انتهاء الإتاحة وإغلاق الاختبار:" : "آخر موعد لتسليم الواجب (Deadline):"}
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "6px" }}>
                <input
                  type="date"
                  value={closeDeadlineDate}
                  onChange={(e) => setCloseDeadlineDate(e.target.value)}
                  style={{ width: "100%", boxSizing: "border-box", minWidth: 0, padding: "7px 10px", border: "1px solid var(--border-color-strong)", borderRadius: "6px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)" }}
                />
                <input
                  type="text"
                  value={closeDeadlineTime}
                  onChange={(e) => setCloseDeadlineTime(e.target.value)}
                  placeholder="11:59 م"
                  style={{ width: "100%", boxSizing: "border-box", minWidth: 0, padding: "7px 10px", border: "1px solid var(--border-color-strong)", borderRadius: "6px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)", textAlign: "center" }}
                />
              </div>
            </div>

            {/* Checkbox: Show on Student Calendar */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 10px",
                background: showOnStudentCalendar ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface)",
                border: showOnStudentCalendar ? "1.5px solid #059669" : "1px solid var(--border-color)",
                borderRadius: "6px",
                cursor: "pointer",
                marginBottom: "8px",
              }}
            >
              <input
                type="checkbox"
                checked={showOnStudentCalendar}
                onChange={(e) => setShowOnStudentCalendar(e.target.checked)}
                style={{ width: "16px", height: "16px", accentColor: "#059669", cursor: "pointer" }}
              />
              <div style={{ fontSize: "11.5px" }}>
                <strong style={{ color: "var(--text-main)", display: "block" }}>
                  إظهار في تقويم وجدول الطلاب
                </strong>
              </div>
            </label>

            {/* Checkbox: Send Notification */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 10px",
                background: sendScheduledNotification ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface)",
                border: sendScheduledNotification ? "1.5px solid #059669" : "1px solid var(--border-color)",
                borderRadius: "6px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={sendScheduledNotification}
                onChange={(e) => setSendScheduledNotification(e.target.checked)}
                style={{ width: "16px", height: "16px", accentColor: "#059669", cursor: "pointer" }}
              />
              <div style={{ fontSize: "11.5px" }}>
                <strong style={{ color: "var(--text-main)", display: "block" }}>
                  إرسال إشعار فوري وتنبيه للطلاب
                </strong>
              </div>
            </label>
          </div>

          {/* Action Trigger Button */}
          {creationMode === "ai" ? (
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="btn-primary"
              style={{ width: "100%", justifyContent: "center", padding: "12px", fontSize: "14px", fontWeight: 800, background: assessmentType === "quiz" ? "#0f766e" : "#0f392b" }}
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
              {loading ? "جاري صياغة الأسئلة بدقة..." : (assessmentType === "quiz" ? "اصنع الاختبار بالذكاء الاصطناعي الآن" : "اصنع الواجب بالذكاء الاصطناعي الآن")}
            </button>
          ) : (
            <button
              onClick={addNewManualQuestion}
              type="button"
              className="btn-secondary"
              style={{ width: "100%", justifyContent: "center", padding: "11px", fontSize: "13px", fontWeight: 800, gap: "6px" }}
            >
              <Plus size={16} />
              <span>إضافة سؤال جديد للاختبار</span>
            </button>
          )}
        </div>

        {/* Right Column: Questions Canvas (AI Review or Manual Builder) */}
        <div style={{ background: "var(--bg-surface, #ffffff)", border: "1px solid var(--border-color, #e2e8f0)", borderRadius: "16px", padding: "24px" }}>
          {error && (
            <div style={{ padding: "14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", color: "#991b1b", fontSize: "13px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <AlertCircle size={18} /> {error}
            </div>
          )}



          {/* AI Waiting State */}
          {creationMode === "ai" && !draft && !loading && !extractingFile && (
            <div style={{ textAlign: "center", padding: "60px 20px", color: "#94a3b8" }}>
              <FileQuestion size={48} style={{ color: "#cbd5e1", margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "17px", color: "var(--text-main, #0f172a)" }}>
                جاهز لإنشاء {assessmentType === "quiz" ? "الاختبار الإلكتروني" : "الواجب المنزلي"}
              </h3>
              <p style={{ margin: "0 0 18px", fontSize: "13px", maxWidth: "420px", marginInline: "auto" }}>
                {quizMode === "extract"
                  ? "قم برفع ملف الامتحان أو بنك الأسئلة أدناه لاستخراج جميع الأسئلة والخيارات والرسومات وتعديلها فوراً."
                  : `حدد إعدادات الأسئلة ومواعيد الإتاحة واضغط "اصنع ${assessmentType === "quiz" ? "الاختبار" : "الواجب"} بالذكاء الاصطناعي" أو ارفع ملف أسئلة للاستخراج الفوري.`}
              </p>

              {(quizMode === "extract" || quizMode === "mix") && (
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    if (e.dataTransfer.files?.[0]) handleExtractFromFile(e.dataTransfer.files[0]);
                  }}
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    maxWidth: "460px",
                    margin: "0 auto",
                    padding: "24px 18px",
                    border: dragOver ? "2px dashed #0f766e" : "2px dashed #cbd5e1",
                    borderRadius: "12px",
                    background: dragOver ? "#f0fdfa" : "#f8fafc",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <UploadCloud size={36} style={{ color: "#0f766e", margin: "0 auto 10px" }} />
                  <strong style={{ display: "block", fontSize: "14px", color: "#0f172a", marginBottom: "4px" }}>
                    اضغط لاختيار ملف أسئلة أو اسحبه هنا
                  </strong>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>
                    يدعم ملفات PDF، Word (.docx)، نصوص TXT، وصور الامتحانات
                  </span>
                </div>
              )}
            </div>
          )}

          {creationMode === "ai" && (loading || extractingFile) && (
            <div style={{ textAlign: "center", padding: "90px 20px", color: "#0f766e" }}>
              <Loader2 size={44} className="animate-spin" style={{ margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "18px" }}>
                {extractingFile
                  ? "جاري تحليل الملف واستخراج الأسئلة والخيارات..."
                  : `جاري تحليل محتوى الدرس وصياغة أسئلة ${assessmentType === "quiz" ? "الاختبار" : "الواجب"}...`}
              </h3>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
                {extractingFile
                  ? "استخراج الأسئلة المقالية والاختيار من متعدد والرسومات البيانية وتوليد نموذج الإجابة بدقة."
                  : "مطابقة المفاهيم التعليمية المقررة وصياغة خيارات الإجابة والأسئلة المقالية وإرشادات الحل."}
              </p>
            </div>
          )}

          {/* Questions Canvas (Available in Manual Mode OR after AI Draft) */}
          {(creationMode === "manual" || (creationMode === "ai" && draft && !loading)) && (
            <div>
              {/* Canvas Action Bar */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px", paddingBottom: "16px", borderBottom: "1px solid var(--border-color)", flexWrap: "wrap", gap: "12px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "11px", fontWeight: 800, color: "#166534", background: "#dcfce7", padding: "3px 8px", borderRadius: "6px" }}>
                      {displayedQuestions.length} أسئلة • {totalPointsCount} درجات
                    </span>
                    {assessmentType === "quiz" && (
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "#0369a1", background: "#e0f2fe", padding: "3px 8px", borderRadius: "6px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <Clock size={12} /> مدة الحل: {quizDurationMinutes} دقيقة
                      </span>
                    )}
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "#92400e", background: "#fef3c7", padding: "3px 8px", borderRadius: "6px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <Calendar size={12} /> النشر: {publishStartDate} ({publishStartTime})
                    </span>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "#991b1b", background: "#fee2e2", padding: "3px 8px", borderRadius: "6px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <Lock size={12} /> {assessmentType === "quiz" ? "الإغلاق" : "آخر موعد للتسليم"}: {closeDeadlineDate} ({closeDeadlineTime})
                    </span>
                    {hasRestoredDraft && !approved && (
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#1d4ed8",
                          background: "#eff6ff",
                          border: "1px solid #bfdbfe",
                          padding: "3px 8px",
                          borderRadius: "6px",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                        title="تم حفظ بيانات وأسئلة الاختبار تلقائياً في المتصفح ولن تضيع عند الانتقال أو التحديث"
                      >
                        <Save size={11} /> مسودة محفوظة تلقائياً
                      </span>
                    )}
                  </div>
                  <h2 style={{ margin: "2px 0 0", fontSize: "18px", color: "var(--text-main)" }}>
                    {creationMode === "manual" ? (manualTitle || `${assessmentType === "quiz" ? "اختبار" : "واجب"} جديد (إنشاء يدوي)`) : draft?.title}
                  </h2>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {creationMode === "ai" && draft && (
                    <button
                      type="button"
                      onClick={handleGenerateMore}
                      disabled={loading}
                      className="btn-secondary"
                      style={{ fontSize: "12px", gap: "6px", color: "#0f766e", borderColor: "#0f766e" }}
                    >
                      {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      <span>توليد المزيد من هذا الدرس</span>
                    </button>
                  )}

                  {hasRestoredDraft && !approved && (
                    <button
                      type="button"
                      onClick={handleResetNewQuiz}
                      className="btn-secondary"
                      style={{
                        fontSize: "12px",
                        gap: "5px",
                        color: "#ffffff",
                        background: "#dc2626",
                        borderColor: "#dc2626",
                      }}
                      title="مسح المسودة الحالية والبدء باختبار جديد من الصفر"
                    >
                      <RotateCcw size={13} />
                      <span>بدء اختبار جديد</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={addNewManualQuestion}
                    className="btn-secondary"
                    style={{ fontSize: "12px", gap: "4px" }}
                  >
                    <Plus size={14} /> إضافة سؤال
                  </button>

                  <button
                    onClick={handleInitiatePublish}
                    className="btn-primary"
                    style={{ background: approved ? "#15803d" : (assessmentType === "quiz" ? "#0f766e" : "#0f392b"), fontSize: "12px", gap: "6px" }}
                  >
                    <CheckSquare size={16} />
                    {approved
                      ? `تم حفظ ونشر ${assessmentType === "quiz" ? "الاختبار" : "الواجب"} بالجدول`
                      : `حفظ ونشر ${assessmentType === "quiz" ? "الاختبار" : "الواجب"} للطلاب`}
                  </button>
                </div>
              </div>

              {creationMode === "ai" && draft && draft.is_complete === false && (
                <div style={{ padding: "12px 16px", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: "10px", color: "#92400e", fontSize: "12.5px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                  <AlertCircle size={18} style={{ flexShrink: 0 }} />
                  <span>تنبيه تربوي: محتوى الدرس والمذكرات المتاحة لم يكفِ لتوليد كامل العدد المطلوب من الأسئلة الجديدة، وتم إخراج كافة الأسئلة الموثوقة المتاحة بدقة.</span>
                </div>
              )}

              {approved && (
                <div style={{ padding: "12px 16px", background: "#dcfce7", color: "#166534", borderRadius: "10px", fontSize: "13px", fontWeight: 700, marginBottom: "16px", border: "1px solid #86efac", display: "flex", alignItems: "center", gap: "8px" }}>
                  <CheckSquare size={18} />
                  <span>
                    تم حفظ ونشر {assessmentType === "quiz" ? "الاختبار" : "الواجب المنزلي"} بنجاح وتثبيت موعده في التقويم ({showOnStudentCalendar ? "معروض في جدول الطلاب" : "في جدول المعلم فقط"}) {sendScheduledNotification && "وإرسال إشعار فوري لطلاب هذا الصف!"}
                  </span>
                </div>
              )}

              {/* Questions List */}
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {displayedQuestions.map((q, qIdx) => {
                  const isEditing = editingQuestionId === q.id;

                  return (
                    <div
                      key={q.id}
                      style={{
                        border: isEditing ? "2px solid #059669" : "1px solid var(--border-color)",
                        borderRadius: "14px",
                        padding: "18px",
                        background: "var(--bg-surface, #ffffff)",
                        boxShadow: isEditing ? "0 4px 12px rgba(5, 150, 105, 0.12)" : "0 1px 3px rgba(0,0,0,0.03)",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {/* Question Top Header */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", paddingBottom: "8px", borderBottom: "1px solid var(--border-color)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          {/* Reorder Arrows */}
                          <div style={{ display: "flex", gap: "2px" }}>
                            <button
                              type="button"
                              onClick={() => moveQuestionOrder(qIdx, "up")}
                              disabled={qIdx === 0}
                              style={{ background: "none", border: "none", padding: "2px", cursor: qIdx === 0 ? "not-allowed" : "pointer", opacity: qIdx === 0 ? 0.25 : 0.8 }}
                              title="تحريك السؤال لأعلى"
                            >
                              <ArrowUp size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveQuestionOrder(qIdx, "down")}
                              disabled={qIdx === displayedQuestions.length - 1}
                              style={{ background: "none", border: "none", padding: "2px", cursor: qIdx === displayedQuestions.length - 1 ? "not-allowed" : "pointer", opacity: qIdx === displayedQuestions.length - 1 ? 0.25 : 0.8 }}
                              title="تحريك السؤال لأسفل"
                            >
                              <ArrowDown size={14} />
                            </button>
                          </div>

                          <strong style={{ fontSize: "13px", color: "#0f392b" }}>
                            السؤال {qIdx + 1}
                          </strong>

                          {/* Editable Question Type Selector with distinct badge (Requirement 9) */}
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <select
                              value={normalizeQuestionType(q.question_type)}
                              onChange={(e) => updateQuestionType(q.id, e.target.value as "multiple_choice" | "essay" | "true_false" | "fill_in_blank")}
                              style={{
                                padding: "3px 8px",
                                borderRadius: "6px",
                                border: "1px solid var(--border-color-strong)",
                                fontSize: "11.5px",
                                fontWeight: 700,
                                background: "var(--bg-surface-secondary)",
                                color: "var(--text-main)",
                              }}
                            >
                              <option value="multiple_choice">اختيار من متعدد (MCQ)</option>
                              <option value="true_false">صح أو خطأ (True/False)</option>
                              <option value="essay">سؤال مقالي (Essay)</option>
                              <option value="fill_in_blank">أكمل الفراغات (Fill in the blank)</option>
                            </select>

                            <span
                              style={{
                                fontSize: "10.5px",
                                padding: "2px 7px",
                                borderRadius: "12px",
                                fontWeight: 800,
                                letterSpacing: "0.5px",
                                background: getQuestionTypeLabel(q.question_type).bg,
                                color: getQuestionTypeLabel(q.question_type).color,
                              }}
                            >
                              {getQuestionTypeLabel(q.question_type).code}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          {/* Points */}
                          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <label style={{ fontSize: "11px", color: "var(--text-muted)" }}>الدرجة:</label>
                            <input
                              type="number"
                              min={1}
                              max={50}
                              value={q.points}
                              onChange={(e) => updateQuestionPoints(q.id, parseInt(e.target.value) || 1)}
                              style={{
                                width: "48px",
                                padding: "3px 6px",
                                border: "1px solid var(--border-color-strong)",
                                borderRadius: "6px",
                                fontSize: "12px",
                                fontWeight: 800,
                                textAlign: "center",
                                background: "var(--bg-surface-secondary)",
                                color: "#0f392b",
                              }}
                            />
                          </div>

                          {/* Toggle Edit */}
                          <button
                            type="button"
                            onClick={() => setEditingQuestionId(isEditing ? null : q.id)}
                            style={{
                              background: isEditing ? "#ecfdf5" : "none",
                              border: isEditing ? "1px solid #059669" : "none",
                              color: isEditing ? "#059669" : "var(--text-muted)",
                              cursor: "pointer",
                              padding: "4px 8px",
                              borderRadius: "6px",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                              fontSize: "11px",
                              fontWeight: 700,
                            }}
                          >
                            {isEditing ? <Save size={13} /> : <Edit3 size={13} />}
                            <span>{isEditing ? "حفظ التعديل" : "تعديل"}</span>
                          </button>

                          {/* Delete */}
                          <button
                            type="button"
                            onClick={() => deleteQuestion(q.id)}
                            style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", padding: "2px" }}
                            title="حذف هذا السؤال"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>

                      {/* Question Text */}
                      {isEditing ? (
                        <div style={{ marginBottom: "12px" }}>
                          {normalizeQuestionType(q.question_type) === "fill_in_blank" && (
                            <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                              <button
                                type="button"
                                onClick={() => insertBlankMarker(q.id)}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "6px",
                                  padding: "6px 14px",
                                  borderRadius: "8px",
                                  border: "1.5px solid #059669",
                                  background: "#ecfdf5",
                                  color: "#065f46",
                                  fontSize: "12px",
                                  fontWeight: 800,
                                  cursor: "pointer",
                                  boxShadow: "0 1px 3px rgba(5, 150, 105, 0.15)",
                                }}
                              >
                                <span>➕ إدراج فراغ [.....] في نص السؤال</span>
                              </button>
                              <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                                (اضغط لإدراج الفراغ في أي موضع تريده في السؤال ليتحول تلقائياً إلى Text Box يجاوب فيه الطالب)
                              </span>
                            </div>
                          )}
                          <RichFormulaEditor
                            value={q.question_text}
                            onChange={(newVal) => updateQuestionText(q.id, newVal)}
                            label="نص السؤال والمعادلات:"
                            minRows={2}
                          />
                        </div>
                      ) : (
                        <div style={{ margin: "0 0 12px", fontSize: "14px", fontWeight: 700, color: "var(--text-main)", lineHeight: "1.8" }}>
                          {normalizeQuestionType(q.question_type) === "fill_in_blank"
                            ? renderFillInBlankStem(q.question_text)
                            : <FormulaRenderer text={q.question_text} />
                          }
                        </div>
                      )}

                      {/* Attached Image Assets */}
                      {q.image_asset_ids && q.image_asset_ids.length > 0 && (
                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "14px" }}>
                          {q.image_asset_ids.map((assetId) => (
                            <div
                              key={assetId}
                              style={{
                                borderRadius: "8px",
                                overflow: "hidden",
                                border: "1.5px solid var(--border-color, #e2e8f0)",
                                background: "var(--bg-surface-secondary, #f8fafc)",
                                maxWidth: "260px",
                                padding: "4px",
                              }}
                            >
                              <img
                                src={`/api/v1/knowledge-center/assets/${assetId}/view`}
                                alt="رسم توضيحي للسؤال"
                                style={{ width: "100%", maxHeight: "180px", objectFit: "contain", display: "block", borderRadius: "6px" }}
                                onError={(e) => {
                                  (e.target as HTMLElement).parentElement!.style.display = "none";
                                }}
                              />
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Options List (for MCQ and True/False) */}
                      {q.options && q.options.length > 0 && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "12px" }}>
                          {q.options.map((opt) => (
                            <div
                              key={opt.key}
                              style={{
                                padding: "8px 12px",
                                borderRadius: "8px",
                                border: opt.is_correct ? "1.5px solid #059669" : "1px solid var(--border-color)",
                                background: opt.is_correct ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface-secondary, #ffffff)",
                                fontSize: "13px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                gap: "10px",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1 }}>
                                {/* Correct Option Radio */}
                                <button
                                  type="button"
                                  onClick={() => setCorrectOption(q.id, opt.key)}
                                  style={{
                                    width: "22px",
                                    height: "22px",
                                    borderRadius: "50%",
                                    border: opt.is_correct ? "2px solid #059669" : "2px solid var(--border-color-strong)",
                                    background: opt.is_correct ? "#059669" : "transparent",
                                    color: "white",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    cursor: "pointer",
                                    flexShrink: 0,
                                    fontSize: "11px",
                                    fontWeight: 900,
                                  }}
                                  title="اضغط لتعيين هذا الخيار كإجابة صحيحة"
                                >
                                  {opt.is_correct ? "✓" : ""}
                                </button>

                                <span style={{ fontWeight: 800, color: "#0f392b", minWidth: "22px" }}>({opt.key})</span>

                                {isEditing ? (
                                  <div style={{ flex: 1, display: "flex", gap: "6px", alignItems: "center" }}>
                                    <input
                                      type="text"
                                      value={opt.text}
                                      onChange={(e) => updateOptionText(q.id, opt.key, e.target.value)}
                                      onPaste={(e) => {
                                        e.preventDefault();
                                        const text = e.clipboardData.getData("text/plain");
                                        if (!text) return;
                                        const formatted = formatChemicalFormula(text);
                                        const input = e.currentTarget;
                                        const start = input.selectionStart || 0;
                                        const end = input.selectionEnd || 0;
                                        const current = opt.text || "";
                                        const updated = current.slice(0, start) + formatted + current.slice(end);
                                        updateOptionText(q.id, opt.key, updated);
                                      }}
                                      placeholder="نص الخيار..."
                                      onBlur={(e) => {
                                        const val = e.target.value;
                                        const formatted = formatChemicalFormula(val);
                                        if (formatted !== val) {
                                          updateOptionText(q.id, opt.key, formatted);
                                        }
                                      }}
                                      style={{
                                        flex: 1,
                                        padding: "4px 8px",
                                        border: "1px solid var(--border-color-strong)",
                                        borderRadius: "6px",
                                        fontSize: "13px",
                                        background: "var(--bg-surface)",
                                        color: "var(--text-main)",
                                        outline: "none",
                                      }}
                                    />
                                  </div>
                                ) : (
                                  <span style={{ color: "var(--text-main)", fontWeight: opt.is_correct ? 700 : 500 }}>
                                    <FormulaRenderer inline text={opt.text} />
                                  </span>
                                )}
                              </div>

                              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                {opt.is_correct && (
                                  <span style={{ color: "#059669", fontWeight: 800, fontSize: "11px" }}>
                                    الإجابة الصحيحة
                                  </span>
                                )}
                                {isEditing && normalizeQuestionType(q.question_type) === "multiple_choice" && (q.options?.length ?? 0) > 2 && (
                                  <button
                                    type="button"
                                    onClick={() => removeOptionFromQuestion(q.id, opt.key)}
                                    style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", padding: "2px" }}
                                    title="حذف هذا الخيار"
                                  >
                                    <Trash2 size={12} />
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}

                          {isEditing && normalizeQuestionType(q.question_type) === "multiple_choice" && (q.options?.length ?? 0) < 6 && (
                            <button
                              type="button"
                              onClick={() => addOptionToQuestion(q.id)}
                              style={{
                                alignSelf: "flex-start",
                                padding: "4px 10px",
                                borderRadius: "6px",
                                border: "1px dashed #059669",
                                background: "#ecfdf5",
                                color: "#059669",
                                fontSize: "11px",
                                fontWeight: 700,
                                cursor: "pointer",
                              }}
                            >
                              + إضافة خيار جديد
                            </button>
                          )}
                        </div>
                      )}

                      {/* Fill in the Blank Student Answer Box & Definition */}
                      {normalizeQuestionType(q.question_type) === "fill_in_blank" && (
                        <div style={{ marginTop: "12px", padding: "12px 14px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                            <span style={{ fontSize: "12px", fontWeight: 800, color: "#0f392b" }}>
                              ✏️ سؤال إكمال الفراغ (Fill in the blank):
                            </span>
                            {!isEditing && q.correct_answer && (
                              <span style={{ fontSize: "12px", color: "#059669", fontWeight: 700 }}>
                                الإجابة المقررة للفراغ: <strong>{q.correct_answer}</strong>
                              </span>
                            )}
                          </div>

                          {isEditing ? (
                            <div style={{ marginTop: "8px" }}>
                              <label style={{ display: "block", fontSize: "11.5px", fontWeight: 700, color: "#059669", marginBottom: "4px" }}>
                                الكلمة / المصطلح الصحيح لإكمال الفراغ (للتصحيح الذاتي):
                              </label>
                              <input
                                type="text"
                                value={q.correct_answer || ""}
                                onChange={(e) => updateQuestionCorrectAnswer(q.id, e.target.value)}
                                placeholder="اكتب الكلمة أو المصطلح الصحيح الذي يملأ الفراغ..."
                                style={{
                                  width: "100%",
                                  padding: "8px 12px",
                                  borderRadius: "6px",
                                  border: "1px solid var(--border-color-strong)",
                                  background: "var(--bg-surface)",
                                  color: "var(--text-main)",
                                  fontSize: "12.5px",
                                  boxSizing: "border-box",
                                }}
                              />
                            </div>
                          ) : (
                            <div style={{ marginTop: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
                              <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>خانة إجابة الطالب:</span>
                              <input
                                type="text"
                                disabled
                                placeholder="يكتب الطالب إجابته في الفراغ هنا..."
                                style={{
                                  padding: "6px 12px",
                                  borderRadius: "6px",
                                  border: "1.5px dashed var(--border-color)",
                                  background: "var(--bg-surface)",
                                  color: "var(--text-muted)",
                                  fontSize: "12.5px",
                                  width: "220px",
                                  cursor: "default",
                                }}
                              />
                            </div>
                          )}
                        </div>
                      )}

                      {/* Essay Question Student Answer Textarea */}
                      {normalizeQuestionType(q.question_type) === "essay" && (
                        <div style={{ marginTop: "12px", padding: "14px", background: "var(--bg-surface-secondary)", border: "1.5px dashed var(--border-color)", borderRadius: "10px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px", flexWrap: "wrap", gap: "6px" }}>
                            <label style={{ fontSize: "12.5px", fontWeight: 800, color: "#0f392b", display: "flex", alignItems: "center", gap: "6px" }}>
                              <span>📝 مساحة إجابة الطالب (سؤال مقالي):</span>
                            </label>
                            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                              (مربع كتابة مخصص يكتب فيه الطالب الشرح والخطوات بالتفصيل)
                            </span>
                          </div>

                          <textarea
                            rows={3}
                            readOnly
                            placeholder="مساحة مخصصة يكتب فيها الطالب إجابته المقالية والشرح والمعادلات عند حل الاختبار..."
                            style={{
                              width: "100%",
                              padding: "10px 12px",
                              borderRadius: "8px",
                              border: "1px solid var(--border-color)",
                              background: "var(--bg-surface)",
                              color: "var(--text-muted)",
                              fontSize: "13px",
                              resize: "none",
                              boxSizing: "border-box",
                              cursor: "default",
                            }}
                          />

                          {isEditing && (
                            <div style={{ marginTop: "10px", borderTop: "1px solid var(--border-color)", paddingTop: "8px" }}>
                              <label style={{ display: "block", fontSize: "11.5px", fontWeight: 700, color: "#059669", marginBottom: "4px" }}>
                                الإجابة النموذجية أو عناصر الإجابة المقالية (للمعلم وتصحيح الذكاء الاصطناعي):
                              </label>
                              <textarea
                                rows={2}
                                value={q.correct_answer || ""}
                                onChange={(e) => updateQuestionCorrectAnswer(q.id, e.target.value)}
                                placeholder="اكتب الإجابة النموذجية أو النقاط المفتاحية التي يجب توافرها في إجابة الطالب..."
                                style={{
                                  width: "100%",
                                  padding: "8px 12px",
                                  borderRadius: "6px",
                                  border: "1px solid var(--border-color-strong)",
                                  background: "var(--bg-surface)",
                                  color: "var(--text-main)",
                                  fontSize: "12.5px",
                                  lineHeight: "1.4",
                                  boxSizing: "border-box",
                                }}
                              />
                            </div>
                          )}

                          {!isEditing && q.correct_answer && (
                            <div style={{ marginTop: "8px", fontSize: "11.5px", color: "var(--text-muted)" }}>
                              <strong style={{ color: "#059669" }}>معيار الإجابة النموذجية: </strong>
                              <span>{q.correct_answer}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Bottom Canvas Actions */}
              {displayedQuestions.length > 0 && (
                <div
                  style={{
                    marginTop: "20px",
                    paddingTop: "16px",
                    borderTop: "1px solid var(--border-color, #e2e8f0)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "10px",
                  }}
                >
                  <button
                    type="button"
                    onClick={addNewManualQuestion}
                    className="btn-secondary"
                    style={{ fontSize: "12.5px", gap: "6px" }}
                  >
                    <Plus size={14} /> إضافة سؤال آخر
                  </button>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        onClick={handleInitiatePublish}
                        className="btn-primary"
                        style={{
                          background: approved ? "#15803d" : (assessmentType === "quiz" ? "#0f766e" : "#0f392b"),
                          fontSize: "13px",
                          gap: "8px",
                          padding: "10px 22px",
                        }}
                      >
                        <CheckSquare size={16} />
                        {approved
                          ? `تم حفظ ونشر ${assessmentType === "quiz" ? "الاختبار" : "الواجب"} بالسجل والجدول`
                          : `حفظ ونشر ${assessmentType === "quiz" ? "الاختبار" : "الواجب"} للطلاب`}
                      </button>

                      {approved && (
                        <button
                          type="button"
                          onClick={() => setActiveSubTab("history")}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            padding: "10px 18px",
                            borderRadius: "8px",
                            border: "1px solid #0f766e",
                            background: "#0f766e",
                            color: "#ffffff",
                            fontSize: "13px",
                            fontWeight: 800,
                            cursor: "pointer",
                          }}
                        >
                          <FileQuestion size={16} />
                          <span>عرض في سجل الاختبارات المرفوعة ({historyCount})</span>
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </>
      )}

      {/* Confirmation Modal Before Upload / Publish */}
      {showPublishConfirmModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              borderRadius: "16px",
              width: "100%",
              maxWidth: "520px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.3)",
              border: "1px solid var(--border-color, #e2e8f0)",
              overflow: "hidden",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "16px 20px",
                background: assessmentType === "quiz" ? "#0f766e" : "#0f392b",
                color: "#ffffff",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <UploadCloud size={20} color="#34d399" />
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800 }}>
                  تأكيد رفع واعتماد {assessmentType === "quiz" ? "الاختبار" : "الواجب"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => !isPublishing && setShowPublishConfirmModal(false)}
                disabled={isPublishing}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#ffffff",
                  cursor: isPublishing ? "not-allowed" : "pointer",
                  padding: "4px",
                  borderRadius: "6px",
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: "20px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", marginBottom: "16px" }}>
                <AlertCircle size={22} color="#059669" style={{ flexShrink: 0, marginTop: "2px" }} />
                <div>
                  <p style={{ margin: 0, fontSize: "14px", fontWeight: 800, color: "var(--text-main, #0f172a)", lineHeight: "1.5" }}>
                    هل أنت متأكد من رغبتك في رفع واعتماد هذا {assessmentType === "quiz" ? "الاختبار" : "الواجب"} للطلاب؟
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: "12.5px", color: "var(--text-muted, #64748b)" }}>
                    سيتم تثبيت الموعد في جدول التقويم {sendScheduledNotification ? "وإرسال إشعار فوري لجميع طلاب الصف." : "وفقاً للإعدادات المحددة."}
                  </p>
                </div>
              </div>

              {/* Summary Card */}
              <div
                style={{
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  borderRadius: "12px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  padding: "14px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  fontSize: "13px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color, #e2e8f0)", paddingBottom: "8px" }}>
                  <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>العنوان:</span>
                  <span style={{ color: "var(--text-main, #0f172a)", fontWeight: 800 }}>
                    {creationMode === "manual"
                      ? (manualTitle.trim() || `${assessmentType === "quiz" ? "اختبار" : "واجب"} جديد`)
                      : (draft?.title || `${assessmentType === "quiz" ? "اختبار" : "واجب"}`)}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>الصف الدراسي:</span>
                  <span style={{ color: "#0f766e", fontWeight: 800 }}>
                    {selectedAcademicYear === "1st_secondary" ? "الصف الأول الثانوي" : selectedAcademicYear === "2nd_secondary" ? "الصف الثاني الثانوي" : "الصف الثالث الثانوي"}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>عدد الأسئلة والدرجات:</span>
                  <span style={{ color: "var(--text-main, #0f172a)", fontWeight: 700 }}>
                    {activeQuestionsList().length} سؤال ({activeQuestionsList().reduce((sum, q) => sum + (q.points || 0), 0)} درجة)
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>موعد البدء والنشر:</span>
                  <span style={{ color: "var(--text-main, #0f172a)", fontWeight: 600 }}>
                    {publishStartDate} ({publishStartTime})
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>{assessmentType === "quiz" ? "موعد الإغلاق" : "آخر موعد للتسليم"}:</span>
                  <span style={{ color: "#dc2626", fontWeight: 700 }}>
                    {closeDeadlineDate} ({closeDeadlineTime})
                  </span>
                </div>

                {assessmentType === "quiz" && (
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>مدة حل الاختبار:</span>
                    <span style={{ color: "#0369a1", fontWeight: 700 }}>
                      {quizDurationMinutes} دقيقة
                    </span>
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border-color, #e2e8f0)", paddingTop: "8px" }}>
                  <span style={{ color: "var(--text-muted, #64748b)", fontWeight: 600 }}>إشعار الطلاب:</span>
                  <span style={{ color: sendScheduledNotification ? "#059669" : "#64748b", fontWeight: 700 }}>
                    {sendScheduledNotification ? "✓ سيتم إرسال إشعار فوري" : "بدون إشعار"}
                  </span>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                alignItems: "center",
                gap: "10px",
                padding: "14px 20px",
                background: "var(--bg-surface-secondary, #f8fafc)",
                borderTop: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <button
                type="button"
                onClick={() => setShowPublishConfirmModal(false)}
                disabled={isPublishing}
                style={{
                  padding: "8px 18px",
                  borderRadius: "8px",
                  border: "1px solid var(--border-color-strong, #cbd5e1)",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-main, #334155)",
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: isPublishing ? "not-allowed" : "pointer",
                }}
              >
                إلغاء
              </button>

              <button
                type="button"
                onClick={handleConfirmPublish}
                disabled={isPublishing}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "8px 22px",
                  borderRadius: "8px",
                  border: "none",
                  background: assessmentType === "quiz" ? "#0f766e" : "#0f392b",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 800,
                  cursor: isPublishing ? "wait" : "pointer",
                  boxShadow: "0 2px 6px rgba(15, 118, 110, 0.25)",
                }}
              >
                {isPublishing ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>جاري الرفع والنشر...</span>
                  </>
                ) : (
                  <>
                    <CheckSquare size={16} />
                    <span>تأكيد الرفع والنشر الآن</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

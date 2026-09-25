import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Calendar,
  CheckCircle2,
  CheckSquare,
  Clock,
  Copy,
  Edit3,
  FileQuestion,
  Loader2,
  Lock,
  Plus,
  RotateCcw,
  Save,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { CalendarScheduleEvent, Course, CurrentUser, NotificationItem } from "../types/lms";
import { quizExtractionService } from "../services/quizExtractionService";
import { calendarService, notificationService, courseService } from "../services/lmsService";
import { GeneratedQuestion, QuizDraftResponse } from "../types/quiz";
import { useToast } from "../components/ToastProvider";
import { FormulaRenderer } from "../components/FormulaRenderer";
import { RichFormulaEditor } from "../components/RichFormulaEditor";
import { formatChemicalFormula } from "../utils/formulaUtils";
import { quizHistoryService, PublishedQuizRecord } from "../services/quizHistoryService";
import { QuizHistorySection } from "../components/QuizHistorySection";

const QUIZ_DRAFT_STORAGE_KEY_PREFIX = "lms_quiz_maker_unuploaded_draft_v2";

function getQuizDraftStorageKey(userId: string): string {
  return `${QUIZ_DRAFT_STORAGE_KEY_PREFIX}:${userId}`;
}

function getInitialQuizDraft(userId: string) {
  try {
    const raw = localStorage.getItem(getQuizDraftStorageKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const hasQuestions = Array.isArray(parsed?.questions) && parsed.questions.length > 0;
    const hasTitle = typeof parsed?.title === "string" && parsed.title.trim().length > 0;
    if (!hasQuestions && !hasTitle) {
      return null;
    }
    return parsed;
  } catch (e) {
    console.error("Error reading saved quiz draft:", e);
    return null;
  }
}

async function computeFileFingerprint(file: File): Promise<string> {
  try {
    const buf = await file.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buf);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return "";
  }
}

// Start a manual assessment empty; the teacher adds the first real question.
// This keeps sample/example content out of production screens.
const DEFAULT_MANUAL_QUESTIONS: GeneratedQuestion[] = [];

interface QuizGeneratorViewProps {
  courses: Course[];
  currentUser: CurrentUser;
}

export const QuizGeneratorView: React.FC<QuizGeneratorViewProps> = ({ courses, currentUser }) => {
  const toast = useToast();
  const quizDraftStorageKey = getQuizDraftStorageKey(currentUser.id);
  const initialDraftRef = useRef(getInitialQuizDraft(currentUser.id));
  const initialDraft = initialDraftRef.current;

  const [hasRestoredDraft, setHasRestoredDraft] = useState<boolean>(() => !!initialDraft);

  const [extractingFile, setExtractingFile] = useState(false);
  const [extractedFileName, setExtractedFileName] = useState<string | null>(null);
  // The draft is bound to the exact file it came from: name + SHA-256 + time.
  // A new extraction replaces all three, so a restored draft can never be
  // mistaken for the result of a different file.
  const [extractedFileFingerprint, setExtractedFileFingerprint] = useState<string | null>(null);
  const [extractedAt, setExtractedAt] = useState<string | null>(null);
  const extractionRequestRef = useRef(0);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  // Selected Lesson IDs - Required, empty by default
  const [selectedLessonIds, setSelectedLessonIds] = useState<string[]>(() => {
    if (Array.isArray(initialDraft?.selectedLessonIds) && initialDraft.selectedLessonIds.length > 0) {
      return initialDraft.selectedLessonIds;
    }
    return [];
  });

  const isFirstMountRef = useRef(true);
  useEffect(() => {
    if (isFirstMountRef.current) {
      isFirstMountRef.current = false;
      return;
    }
    if (selectedLessonIds.length > 0 && !courseLessons.some((l) => selectedLessonIds.includes(l.id))) {
      setSelectedLessonIds([]);
    }
  }, [courseLessons, selectedLessonIds]);

  // Activity Type: Quiz vs Assignment
  const [assessmentType, setAssessmentType] = useState<"quiz" | "assignment">(() => initialDraft?.assessmentType || "quiz");

  // Quiz / Assignment Timing & Schedule Configuration - Required, empty by default
  const [quizDurationMinutes, setQuizDurationMinutes] = useState<number | "">(() => initialDraft?.quizDurationMinutes ?? "");
  const [publishStartDate, setPublishStartDate] = useState<string>(() => initialDraft?.publishStartDate || "");
  const [publishStartTime, setPublishStartTime] = useState<string>(() => initialDraft?.publishStartTime || "");
  const [closeDeadlineDate, setCloseDeadlineDate] = useState<string>(() => initialDraft?.closeDeadlineDate || "");
  const [closeDeadlineTime, setCloseDeadlineTime] = useState<string>(() => initialDraft?.closeDeadlineTime || "");
  const [showOnStudentCalendar, setShowOnStudentCalendar] = useState<boolean>(() => initialDraft?.showOnStudentCalendar ?? true);
  const [sendScheduledNotification, setSendScheduledNotification] = useState<boolean>(() => initialDraft?.sendScheduledNotification ?? true);


  function normalizeQuestionType(t?: string): "multiple_choice" | "true_false" | "essay" | "fill_in_blank" | "unknown" {
    if (!t) return "multiple_choice";
    const upper = t.toUpperCase();
    if (upper === "MCQ" || upper === "MULTIPLE_CHOICE") return "multiple_choice";
    if (upper === "TRUE_FALSE" || upper === "TRUEFALSE") return "true_false";
    if (upper === "ESSAY") return "essay";
    if (upper === "FILL_BLANK" || upper === "FILL_IN_BLANK") return "fill_in_blank";
    if (upper === "UNKNOWN") return "unknown";
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
        return { code: "FILL_BLANK", label: "أكمل الفراغ (Fill in blank)", bg: "rgba(139, 92, 246, 0.12)", color: "#5b21b6" };
      case "unknown":
        return { code: "UNKNOWN", label: "بحاجة لمراجعة التصنيف (Unknown)", bg: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" };
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

  // Unified Quiz / Assignment State (Extraction + Manual)
  const [quizTitle, setQuizTitle] = useState(() => initialDraft?.manualTitle || initialDraft?.title || "");
  const [questions, setQuestions] = useState<GeneratedQuestion[]>(() => {
    if (Array.isArray(initialDraft?.questions) && initialDraft.questions.length > 0) {
      return initialDraft.questions;
    }
    if (Array.isArray(initialDraft?.draft?.questions) && initialDraft.draft.questions.length > 0) {
      return initialDraft.draft.questions;
    }
    if (Array.isArray(initialDraft?.manualQuestions) && initialDraft.manualQuestions.length > 0) {
      return initialDraft.manualQuestions;
    }
    return DEFAULT_MANUAL_QUESTIONS;
  });

  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<QuizDraftResponse | null>(() => initialDraft?.draft || null);
  const [approved, setApproved] = useState(false);
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);
  const [touchedFields, setTouchedFields] = useState<Record<string, boolean>>({});

  const markTouched = (field: string) => {
    setTouchedFields((prev) => ({ ...prev, [field]: true }));
  };

  const quizTitleHasError = (attemptedSubmit || touchedFields.quizTitle) && !quizTitle.trim();
  const lessonHasError = (attemptedSubmit || touchedFields.lesson) && !selectedLessonIds[0];
  const durationHasError = assessmentType === "quiz" && (attemptedSubmit || touchedFields.duration) && (!quizDurationMinutes || Number(quizDurationMinutes) <= 0);
  const publishStartHasError = (attemptedSubmit || touchedFields.publishStart) && (!publishStartDate || !publishStartTime.trim());
  const closeDeadlineHasError = (attemptedSubmit || touchedFields.closeDeadline) && (!closeDeadlineDate || !closeDeadlineTime.trim());

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
    // If the quiz is approved/published or actively extracting, do not auto-save
    if (approved) {
      localStorage.removeItem(quizDraftStorageKey);
      setHasRestoredDraft(false);
      return;
    }

    if (extractingFile) {
      return;
    }

    if (questions.length === 0 && quizTitle.trim().length === 0) {
      localStorage.removeItem(quizDraftStorageKey);
      setHasRestoredDraft(false);
      return;
    }

    const payload = {
      title: quizTitle,
      questions,
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
      extractedFileName,
      extractedFileFingerprint,
      extractedAt,
      draft,
      savedAt: new Date().toISOString(),
    };

    try {
      localStorage.setItem(quizDraftStorageKey, JSON.stringify(payload));
      setHasRestoredDraft(true);
    } catch (e) {
      console.error("Failed to auto-save un-uploaded quiz draft:", e);
    }
  }, [
    approved,
    extractingFile,
    quizTitle,
    questions,
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
    extractedFileName,
    extractedFileFingerprint,
    extractedAt,
    draft,
    quizDraftStorageKey,
  ]);

  function handleResetNewQuiz() {
    if (window.confirm("هل أنت متأكد من رغبتك في مسح مسودة هذا الاختبار الحالية والبدء باختبار جديد من البداية؟")) {
      localStorage.removeItem(quizDraftStorageKey);
      setDraft(null);
      setQuizTitle("");
      setSelectedLessonIds([]);
      setQuizDurationMinutes("");
      setPublishStartDate("");
      setPublishStartTime("");
      setCloseDeadlineDate("");
      setCloseDeadlineTime("");
      setQuestions([]);
      setExtractedFileName(null);
      setExtractedFileFingerprint(null);
      setExtractedAt(null);
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

  // ================= EXTRACT QUIZ DIRECTLY FROM UPLOADED FILE =================
  async function handleExtractFromFile(file: File) {
    if (!file) return;
    const requestNumber = extractionRequestRef.current + 1;
    extractionRequestRef.current = requestNumber;
    setExtractingFile(true);
    setError(null);
    setDraft(null);
    // CRITICAL: Immediately clear stale questions from state and local storage
    setQuizTitle("");
    setQuestions([]);
    setExtractedFileName(null);
    setExtractedFileFingerprint(null);
    setExtractedAt(null);
    localStorage.removeItem(quizDraftStorageKey);
    setHasRestoredDraft(false);

    try {
      const resp = await quizExtractionService.extractQuizFromFile(
        file,
        currentCourse?.id,
        selectedLessonIds.length > 0 ? selectedLessonIds[0] : undefined,
        assessmentType === "assignment" ? "assignment" : "quiz",
      );

      if (extractionRequestRef.current !== requestNumber) return;

      if (!resp.questions || resp.questions.length === 0) {
        throw new Error("لم يتم العثور على أسئلة واضحة في الملف. يرجى التأكد من احتواء الملف على أسئلة أو ورقة امتحان.");
      }

      // Fail loudly on a checksum mismatch: the saved questions must belong
      // to the exact bytes the teacher selected, not a stale or cached copy.
      const fingerprint = await computeFileFingerprint(file);
      const serverChecksum = String(
        (resp.metadata as Record<string, unknown> | undefined)?.source_checksum ?? "",
      );
      if (fingerprint && serverChecksum && fingerprint !== serverChecksum) {
        throw new Error("فشل التحقق من بصمة الملف. النتيجة لا تطابق الملف المرفوع — أعد المحاولة.");
      }

      setDraft(resp);
      setQuestions(resp.questions || []);
      setExtractedFileName(file.name);
      setExtractedFileFingerprint(fingerprint || null);
      setExtractedAt(new Date().toISOString());
      setApproved(false);

      toast({
        message: `تم استخراج ${resp.questions.length} سؤال بنجاح من ملف "${file.name}"!`,
        tone: "success",
      });
    } catch (err: unknown) {
      if (extractionRequestRef.current !== requestNumber) return;
      // Keep state clean on error: never retain or fall back to old questions
      setQuestions([]);
      setDraft(null);
      const errMsg = err instanceof Error ? err.message : "فشل استخراج الأسئلة من الملف. يرجى التأكد من صحة الملف وصيغته.";
      setError(errMsg);
      toast({
        message: errMsg,
        tone: "danger",
      });
    } finally {
      if (extractionRequestRef.current === requestNumber) setExtractingFile(false);
    }
  }

  // ================= QUESTIONS EDITING & REORDERING =================
  function activeQuestionsList(): GeneratedQuestion[] {
    return questions;
  }

  function setActiveQuestionsList(updater: (prev: GeneratedQuestion[]) => GeneratedQuestion[]) {
    setQuestions((prev) => {
      const updated = updater(prev);
      if (draft) {
        const newTotal = updated.reduce((s, q) => s + (q.points || 0), 0);
        setDraft({ ...draft, questions: updated, total_points: newTotal });
      }
      return updated;
    });
  }

  function updateQuestionText(qId: number, newText: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, question_text: newText } : q))
    );
  }

  function updateQuestionPoints(qId: number, newPoints: number | null) {
    setActiveQuestionsList((prev) =>
      prev.map((q) =>
        q.id === qId
          ? {
              ...q,
              points: newPoints !== null && newPoints > 0 ? newPoints : null,
              needs_points_assignment: newPoints === null || newPoints <= 0,
            }
          : q
      )
    );
  }


  function handleCopyQuestionsOnly() {
    if (!questions || questions.length === 0) {
      toast({
        message: "لا توجد أسئلة لنسخها حالياً.",
        tone: "warning",
      });
      return;
    }

    const lines: string[] = [];
    questions.forEach((q, idx) => {
      const qNum = idx + 1;
      lines.push(`${qNum}. ${q.question_text}`);
      if (q.options && q.options.length > 0) {
        q.options.forEach((opt) => {
          lines.push(`(${opt.key}) ${opt.text}`);
        });
      }
      lines.push("");
    });

    const fullText = lines.join("\n").trim();
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(fullText)
        .then(() => {
          toast({
            message: `تم نسخ نص ${questions.length} سؤالاً بنجاح (نص الأسئلة والخيارات فقط بدون أي عناصر واجهة مستخدم)!`,
            tone: "success",
          });
        })
        .catch(() => {
          toast({
            message: "تعذر النسخ التلقائي للحافظة.",
            tone: "danger",
          });
        });
    }
  }

  function updateQuestionCorrectAnswer(qId: number, newAnswer: string) {
    setActiveQuestionsList((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, correct_answer: newAnswer, needs_answer_review: !newAnswer.trim() } : q))
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
        let needsAnswerReview = q.needs_answer_review;
        let newCorrectAnswer = q.correct_answer;

        if (newType === "multiple_choice") {
          if (!newOptions || newOptions.length < 2) {
            newOptions = [
              { key: "أ", text: "الخيار أ", is_correct: false },
              { key: "ب", text: "الخيار ب", is_correct: false },
              { key: "ج", text: "الخيار ج", is_correct: false },
              { key: "د", text: "الخيار د", is_correct: false },
            ];
            needsAnswerReview = true;
          }
        } else if (newType === "true_false") {
          const isCorrectTrue = q.correct_answer?.trim() === "صح" || q.correct_answer?.trim() === "صواب";
          const isCorrectFalse = q.correct_answer?.trim() === "خطأ";
          newOptions = [
            { key: "أ", text: "صح", is_correct: isCorrectTrue },
            { key: "ب", text: "خطأ", is_correct: isCorrectFalse },
          ];
          needsAnswerReview = !isCorrectTrue && !isCorrectFalse;
        } else if (newType === "essay" || newType === "fill_in_blank") {
          newOptions = undefined;
          needsAnswerReview = !newCorrectAnswer || !newCorrectAnswer.trim();
        }
        return {
          ...q,
          question_type: newType,
          options: newOptions,
          needs_answer_review: needsAnswerReview,
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
            needs_answer_review: false,
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
            options: [...q.options, { key: nextKey, text: `خيار ${nextKey}`, is_correct: false }],
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
    setAttemptedSubmit(true);
    const currentQuestions = activeQuestionsList();
    const isQuiz = assessmentType === "quiz";

    if (!quizTitle.trim()) {
      const msg = `يرجى إدخال اسم ${isQuiz ? "الاختبار" : "الواجب"} أولاً (يلزم ادخاله).`;
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

    if (!selectedLessonIds[0]) {
      const msg = `يرجى اختيار الدرس/الوحدة المرتبط ${isQuiz ? "بالاختبار" : "بالواجب"} (يلزم ادخاله).`;
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

    if (isQuiz && (!quizDurationMinutes || Number(quizDurationMinutes) <= 0)) {
      const msg = "يرجى تحديد مدة حل الاختبار للطالب بالدقائق (يلزم ادخاله).";
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

    if (!publishStartDate || !publishStartTime.trim()) {
      const msg = "يرجى تحديد موعد النشر وبدء الإتاحة (يلزم ادخاله).";
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

    if (!closeDeadlineDate || !closeDeadlineTime.trim()) {
      const msg = `يرجى تحديد موعد انتهاء الإتاحة وإغلاق ${isQuiz ? "الاختبار" : "الواجب"} (يلزم ادخاله).`;
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

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

    // Points Validation: all questions must have explicit positive points
    const unassignedPointsCount = currentQuestions.filter(
      (q) => q.points === null || q.points === undefined || q.points <= 0
    ).length;
    if (unassignedPointsCount > 0) {
      const msg = `لا يمكن نشر ${isQuiz ? "الاختبار" : "الواجب"} قبل تحديد درجات جميع الأسئلة. يوجد ${unassignedPointsCount} سؤال بدون درجات محددة.`;
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

    // Unknown Types Validation
    const unknownTypeCount = currentQuestions.filter(
      (q) => normalizeQuestionType(q.question_type) === "unknown"
    ).length;
    if (unknownTypeCount > 0) {
      const msg = `توجد أسئلة (${unknownTypeCount} سؤال) غير محددة النوع (Unknown). يرجى تحديد نوع كل سؤال قبل النشر.`;
      setError(msg);
      toast({ message: msg, tone: "warning" });
      return;
    }

    // Answer Review Validation for Quiz
    if (isQuiz) {
      const unreviewedMcqCount = currentQuestions.filter(
        (q) => normalizeQuestionType(q.question_type) === "multiple_choice" && (!q.options || !q.options.some((o) => o.is_correct))
      ).length;
      if (unreviewedMcqCount > 0) {
        const msg = `توجد أسئلة اختيار من متعدد (${unreviewedMcqCount} سؤال) بدون تحديد الإجابة الصحيحة. يرجى اختيار الإجابة الصحيحة قبل النشر.`;
        setError(msg);
        toast({ message: msg, tone: "warning" });
        return;
      }

      const unreviewedTfCount = currentQuestions.filter(
        (q) => normalizeQuestionType(q.question_type) === "true_false" && (!q.options || !q.options.some((o) => o.is_correct)) && !q.correct_answer
      ).length;
      if (unreviewedTfCount > 0) {
        const msg = `توجد أسئلة صح أو خطأ (${unreviewedTfCount} سؤال) بدون تحديد الإجابة الصحيحة. يرجى تحديد الإجابة الصحيحة قبل النشر.`;
        setError(msg);
        toast({ message: msg, tone: "warning" });
        return;
      }
    }

    setError(null);
    setShowPublishConfirmModal(true);
  }

  async function handleConfirmPublish() {
    const currentQuestions = activeQuestionsList();
    const isQuiz = assessmentType === "quiz";

    if (!quizTitle.trim()) {
      setError(`يرجى إدخال اسم ${isQuiz ? "الاختبار" : "الواجب"} (يلزم ادخاله).`);
      setShowPublishConfirmModal(false);
      return;
    }

    if (!selectedLessonIds[0]) {
      setError(`يلزم اختيار الدرس المرتبط ${isQuiz ? "بالاختبار" : "بالواجب"}.`);
      setShowPublishConfirmModal(false);
      return;
    }

    if (isQuiz && (!quizDurationMinutes || Number(quizDurationMinutes) <= 0)) {
      setError("يلزم تحديد مدة حل الاختبار بالدقائق.");
      setShowPublishConfirmModal(false);
      return;
    }

    if (!publishStartDate || !publishStartTime.trim() || !closeDeadlineDate || !closeDeadlineTime.trim()) {
      setError("يلزم تحديد جميع مواعيد البدء والانتهاء (التاريخ والوقت).");
      setShowPublishConfirmModal(false);
      return;
    }

    if (currentQuestions.length === 0) {
      setError(`لا يمكن حفظ أو رفع ${isQuiz ? "الاختبار" : "الواجب"} وهو فارغ. يرجى إضافة سؤال واحد على الأقل أولاً.`);
      setShowPublishConfirmModal(false);
      return;
    }

    const unassignedPointsCount = currentQuestions.filter(
      (q) => q.points === null || q.points === undefined || q.points <= 0
    ).length;
    if (unassignedPointsCount > 0) {
      setError(`لا يمكن نشر ${isQuiz ? "الاختبار" : "الواجب"} قبل تحديد درجات جميع الأسئلة. يوجد ${unassignedPointsCount} سؤال بدون درجات محددة.`);
      setShowPublishConfirmModal(false);
      return;
    }

    const unknownTypeCount = currentQuestions.filter(
      (q) => normalizeQuestionType(q.question_type) === "unknown"
    ).length;
    if (unknownTypeCount > 0) {
      setError(`توجد أسئلة (${unknownTypeCount} سؤال) غير محددة النوع (Unknown). يرجى تحديد نوع كل سؤال.`);
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

      const isQuiz = assessmentType === "quiz";
      const durationNum = isQuiz && typeof quizDurationMinutes === "number" ? quizDurationMinutes : undefined;

      // The teacher's title is authoritative for both manual and extracted
      // assessments. If left blank, keep the extracted title.
      const titleToPublish = quizTitle.trim()
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
        quizDurationMinutes: durationNum,
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
          message: "",
          type: assessmentType,
          targetYear: selectedAcademicYear,
          createdAt: "الآن",
          read: false,
          actionTab: "MyCourses",
          quizDurationMinutes: durationNum,
          quizCloseDeadline: `${closeDeadlineDate} ${closeDeadlineTime}`,
        };

        await notificationService.saveNotification(newNotif);
      }

      // 3. Publish to the SERVER (real, student-visible) — questions, quiz/assignment,
      // then publish. Requires a selected course and a lesson to attach to.
      if (!currentCourse) {
        throw new Error("اختر المقرر الدراسي أولاً قبل النشر ليستلمه الطلاب.");
      }
      const scopeLessonId = selectedLessonIds[0];
      if (!scopeLessonId) {
        throw new Error("يلزم اختيار الدرس الذي يتبعه " + (isQuiz ? "الاختبار" : "الواجب") + " — لن يراه الطلاب بدون ربطه بدرس مفعّل.");
      }
      const startIso = publishStartDate && publishStartTime ? `${publishStartDate}T${publishStartTime}:00` : null;
      const endIso = closeDeadlineDate && closeDeadlineTime ? `${closeDeadlineDate}T${closeDeadlineTime}:00` : null;
      if (isQuiz) {
        await courseService.publishQuizToServer({
          course_id: currentCourse.id,
          lesson_id: scopeLessonId,
          title: titleToPublish,
          duration_minutes: Number(quizDurationMinutes) || 45,
          starts_at: startIso,
          ends_at: endIso,
          questions: currentQuestions.map((q) => ({
            question_text: q.question_text,
            question_type: q.question_type,
            options: q.options,
            correct_answer: q.correct_answer ?? null,
            points: q.points ?? undefined,
          })),
        });
      } else {
        await courseService.publishAssignmentToServer({
          course_id: currentCourse.id,
          lesson_id: scopeLessonId,
          title: titleToPublish,
          prompt: currentQuestions.map((q) => q.question_text).join("\n\n"),
          due_at: endIso,
        });
      }

      // 4. Save to Teacher Quiz History Archive (local mirror for the teacher)
      quizHistoryService.saveQuiz({
        title: titleToPublish,
        assessmentType,
        academicYear: selectedAcademicYear,
        academicYearLabel: yearLabel,
        creationMode: extractedFileName ? "extract" : "manual",
        publishStartDate,
        publishStartTime,
        closeDeadlineDate,
        closeDeadlineTime,
        closeDeadline: `${closeDeadlineDate} ${closeDeadlineTime}`,
        quizDurationMinutes: durationNum,
        showOnStudentCalendar,
        totalPoints: totalPointsCount,
        questionsCount: currentQuestions.length,
        questions: currentQuestions,
        courseId: currentCourse?.id,
        selectedLessonIds,
      });

      setApproved(true);
      setShowPublishConfirmModal(false);
      localStorage.removeItem(quizDraftStorageKey);
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
    setQuizTitle(quizRecord.title);
    setQuestions(quizRecord.questions);
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
  const questionsNeedingPoints = displayedQuestions.filter(
    (q) => q.points === null || q.points === undefined || q.points <= 0 || q.needs_points_assignment
  );

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
            <FileQuestion size={15} />
            <span>صانع الاختبارات</span>
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
          {/* Header */}
          <div style={{ marginBottom: "20px" }}>
            <span style={{ fontSize: "11px", fontWeight: 800, color: assessmentType === "quiz" ? "#0f766e" : "#0f392b", background: assessmentType === "quiz" ? "#ccfbf1" : "#ecfdf5", padding: "3px 8px", borderRadius: "6px" }}>
              استوديو المعلم • {assessmentType === "quiz" ? "صانع الاختبارات والتقييمات" : "صانع الواجبات المنزلية"}
            </span>
            <h1 style={{ margin: "6px 0 2px", fontSize: "24px", color: "var(--text-main, #0f172a)" }}>
              {assessmentType === "quiz" ? "صانع الاختبارات والتقييمات" : "صانع الواجبات والتكليفات المنزلية"}
            </h1>
            <p style={{ margin: 0, color: "var(--text-muted, #64748b)", fontSize: "13px" }}>
              ارفع ورقة امتحان أو بنك أسئلة لاستخراجها وتعديلها فوراً، أو ابدأ بصياغة الأسئلة والخيارات يدوياً بالكامل.
            </p>
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
                <span>اختبار إلكتروني</span>
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
                <span>واجب منزلي</span>
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

          {/* Assessment title is editable */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
              اسم {assessmentType === "quiz" ? "الاختبار" : "الواجب"}:
            </label>
            <input
              type="text"
              required
              value={quizTitle}
              onChange={(e) => setQuizTitle(e.target.value)}
              onBlur={() => markTouched("quizTitle")}
              placeholder={`أدخل اسم ${assessmentType === "quiz" ? "الاختبار" : "الواجب"} هنا...`}
              style={{
                width: "100%",
                padding: "8px 12px",
                border: quizTitleHasError ? "1.5px solid #ef4444" : "1px solid var(--border-color-strong)",
                boxShadow: quizTitleHasError ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                borderRadius: "8px",
                fontSize: "13px",
                background: "var(--bg-surface)",
                color: "var(--text-main)",
                boxSizing: "border-box",
                marginBottom: quizTitleHasError ? "4px" : "16px",
              }}
            />
            {quizTitleHasError && (
              <div style={{ display: "flex", alignItems: "center", gap: "5px", marginBottom: "14px", color: "#ef4444", fontSize: "11.5px", fontWeight: 700 }}>
                <AlertCircle size={13} style={{ flexShrink: 0 }} />
                <span>يلزم ادخاله</span>
              </div>
            )}
          </div>

          {/* Dedicated file upload for question extraction */}
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
                    onClick={() => {
                      setExtractedFileName(null);
                      setExtractedFileFingerprint(null);
                      setExtractedAt(null);
                    }}
                    style={{ background: "none", border: "none", cursor: "pointer", padding: "2px", color: "#991b1b" }}
                    title="إلغاء الملف"
                  >
                    <X size={14} />
                  </button>
                </div>
                {extractedFileFingerprint && (
                  <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "8px", lineHeight: 1.6 }}>
                    <div>
                      بصمة الملف: <span style={{ fontFamily: "monospace", direction: "ltr", unicodeBidi: "embed" }}>{extractedFileFingerprint.slice(0, 16)}…</span>
                    </div>
                    {extractedAt && <div>استُخرجت في: {new Date(extractedAt).toLocaleString("ar-EG")}</div>}
                  </div>
                )}
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

          {/* Lesson scope (REQUIRED): the quiz/assignment attaches to one lesson
              so students find it inside that lesson and payment gates it. */}
          <div style={{ marginBottom: "14px", background: "var(--bg-surface-secondary, #f8fafc)", border: lessonHasError ? "1.5px solid #ef4444" : "1.5px solid var(--border-color, #e2e8f0)", borderRadius: "10px", padding: "14px" }}>
            <label style={{ display: "block", fontSize: "11.5px", fontWeight: 700, marginBottom: "6px", color: "var(--text-main)" }}>
              الدرس/الوحدة المرتبط {assessmentType === "quiz" ? "بالاختبار" : "بالواجب"}:
            </label>
            {courseLessons.length === 0 ? (
              <div style={{ fontSize: "12px", color: "#b45309", fontWeight: 700 }}>
                لا توجد دروس في هذا المقرر — أضف درساً أولاً ليُربط {assessmentType === "quiz" ? "الاختبار" : "الواجب"} به.
              </div>
            ) : (
              <>
                <select
                  required
                  value={selectedLessonIds[0] || ""}
                  onChange={(e) => setSelectedLessonIds(e.target.value ? [e.target.value] : [])}
                  onBlur={() => markTouched("lesson")}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    border: lessonHasError ? "1.5px solid #ef4444" : selectedLessonIds[0] ? "1px solid var(--border-color-strong)" : "1px solid var(--border-color)",
                    boxShadow: lessonHasError ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                    borderRadius: "8px",
                    fontSize: "13px",
                    fontWeight: 700,
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                  }}
                >
                  <option value="">-- اضغط لاختيار الدرس/الوحدة المرتبط --</option>
                  {courseLessons.map((lesson) => (
                    <option key={lesson.id} value={lesson.id}>{lesson.title}</option>
                  ))}
                </select>
                {lessonHasError && (
                  <div style={{ display: "flex", alignItems: "center", gap: "5px", marginTop: "6px", color: "#ef4444", fontSize: "11.5px", fontWeight: 700 }}>
                    <AlertCircle size={13} style={{ flexShrink: 0 }} />
                    <span>يلزم ادخاله</span>
                  </div>
                )}
              </>
            )}
          </div>

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
                  {quizDurationMinutes ? (
                    <strong style={{ fontSize: "13px", color: "#059669" }}>{quizDurationMinutes} دقيقة</strong>
                  ) : null}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    type="number"
                    required
                    min={5}
                    max={300}
                    step={5}
                    value={quizDurationMinutes}
                    placeholder="أدخل مدة الحل بالدقائق (مثال: 45)"
                    onChange={(e) => {
                      const val = e.target.value;
                      setQuizDurationMinutes(val === "" ? "" : Math.max(1, parseInt(val) || 0));
                    }}
                    onBlur={() => markTouched("duration")}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      border: durationHasError ? "1.5px solid #ef4444" : "1px solid var(--border-color-strong)",
                      boxShadow: durationHasError ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                      borderRadius: "6px",
                      fontSize: "13px",
                      fontWeight: 800,
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                    }}
                  />
                  <span style={{ fontSize: "12px", color: "var(--text-muted)", flexShrink: 0 }}>دقيقة</span>
                </div>
                {durationHasError && (
                  <div style={{ display: "flex", alignItems: "center", gap: "5px", marginTop: "5px", color: "#ef4444", fontSize: "11.5px", fontWeight: 700 }}>
                    <AlertCircle size={13} style={{ flexShrink: 0 }} />
                    <span>يلزم ادخاله</span>
                  </div>
                )}
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
                  required
                  value={publishStartDate}
                  onChange={(e) => setPublishStartDate(e.target.value)}
                  onBlur={() => markTouched("publishStart")}
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    minWidth: 0,
                    padding: "7px 10px",
                    border: publishStartHasError && !publishStartDate ? "1.5px solid #ef4444" : "1px solid var(--border-color-strong)",
                    boxShadow: publishStartHasError && !publishStartDate ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                    borderRadius: "6px",
                    fontSize: "12px",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                  }}
                />
                <input
                  type="text"
                  required
                  value={publishStartTime}
                  onChange={(e) => setPublishStartTime(e.target.value)}
                  onBlur={() => markTouched("publishStart")}
                  placeholder="مثال: 06:00 م"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    minWidth: 0,
                    padding: "7px 10px",
                    border: publishStartHasError && !publishStartTime.trim() ? "1.5px solid #ef4444" : "1px solid var(--border-color-strong)",
                    boxShadow: publishStartHasError && !publishStartTime.trim() ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                    borderRadius: "6px",
                    fontSize: "12px",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    textAlign: "center",
                  }}
                />
              </div>
              {publishStartHasError && (
                <div style={{ display: "flex", alignItems: "center", gap: "5px", marginTop: "5px", color: "#ef4444", fontSize: "11.5px", fontWeight: 700 }}>
                  <AlertCircle size={13} style={{ flexShrink: 0 }} />
                  <span>يلزم ادخاله</span>
                </div>
              )}
            </div>

            {/* Close Date & Time */}
            <div style={{ marginBottom: "12px" }}>
              <label style={{ display: "block", fontSize: "11.5px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                {assessmentType === "quiz" ? "موعد انتهاء الإتاحة وإغلاق الاختبار:" : "آخر موعد لتسليم الواجب:"}
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "6px" }}>
                <input
                  type="date"
                  required
                  value={closeDeadlineDate}
                  onChange={(e) => setCloseDeadlineDate(e.target.value)}
                  onBlur={() => markTouched("closeDeadline")}
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    minWidth: 0,
                    padding: "7px 10px",
                    border: closeDeadlineHasError && !closeDeadlineDate ? "1.5px solid #ef4444" : "1px solid var(--border-color-strong)",
                    boxShadow: closeDeadlineHasError && !closeDeadlineDate ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                    borderRadius: "6px",
                    fontSize: "12px",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                  }}
                />
                <input
                  type="text"
                  required
                  value={closeDeadlineTime}
                  onChange={(e) => setCloseDeadlineTime(e.target.value)}
                  onBlur={() => markTouched("closeDeadline")}
                  placeholder="مثال: 11:59 م"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    minWidth: 0,
                    padding: "7px 10px",
                    border: closeDeadlineHasError && !closeDeadlineTime.trim() ? "1.5px solid #ef4444" : "1px solid var(--border-color-strong)",
                    boxShadow: closeDeadlineHasError && !closeDeadlineTime.trim() ? "0 0 0 3px rgba(239, 68, 68, 0.15)" : undefined,
                    borderRadius: "6px",
                    fontSize: "12px",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    textAlign: "center",
                  }}
                />
              </div>
              {closeDeadlineHasError && (
                <div style={{ display: "flex", alignItems: "center", gap: "5px", marginTop: "5px", color: "#ef4444", fontSize: "11.5px", fontWeight: 700 }}>
                  <AlertCircle size={13} style={{ flexShrink: 0 }} />
                  <span>يلزم ادخاله</span>
                </div>
              )}
            </div>

            {/* Unified Schedule Checkbox (Calendar + Instant Notification - Image 1 combined) */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 12px",
                background: (showOnStudentCalendar && sendScheduledNotification) ? "rgba(5, 150, 105, 0.12)" : "var(--bg-surface)",
                border: (showOnStudentCalendar && sendScheduledNotification) ? "1.5px solid #059669" : "1px solid var(--border-color)",
                borderRadius: "8px",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ fontSize: "12px" }}>
                <strong style={{ color: "var(--text-main)", display: "block", marginBottom: "2px" }}>
                  إظهار في تقويم وجدول الطلاب وإرسال إشعار فوري
                </strong>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  تثبيت الموعد في جدول الطلاب مع إرسال تنبيه مباشر لهم
                </span>
              </div>
              <input
                type="checkbox"
                checked={showOnStudentCalendar && sendScheduledNotification}
                onChange={(e) => {
                  const val = e.target.checked;
                  setShowOnStudentCalendar(val);
                  setSendScheduledNotification(val);
                }}
                style={{ width: "18px", height: "18px", accentColor: "#059669", cursor: "pointer", flexShrink: 0 }}
              />
            </label>
          </div>
        </div>

        {/* Right Column: Questions Canvas (Extraction Review or Manual Builder) */}
        <div style={{ background: "var(--bg-surface, #ffffff)", border: "1px solid var(--border-color, #e2e8f0)", borderRadius: "16px", padding: "24px" }}>
          {error && (
            <div style={{ padding: "14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", color: "#991b1b", fontSize: "13px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <AlertCircle size={18} /> {error}
            </div>
          )}

          {/* Extraction waiting state */}
          {displayedQuestions.length === 0 && !extractingFile && (
            <div style={{ textAlign: "center", padding: "50px 20px", color: "#94a3b8" }}>
              <FileQuestion size={48} style={{ color: "#cbd5e1", margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "17px", color: "var(--text-main, #0f172a)" }}>
                جاهز {assessmentType === "quiz" ? "لاستخراج أسئلة الاختبار الإلكتروني" : "لاستخراج أسئلة الواجب المنزلي"}
              </h3>
              <p style={{ margin: "0 0 18px", fontSize: "13px", maxWidth: "440px", marginInline: "auto" }}>
                قم برفع ملف الامتحان أو بنك الأسئلة أدناه لاستخراج جميع الأسئلة والخيارات والرسومات وتعديلها فوراً، أو ابدأ بإضافة الأسئلة يدوياً.
              </p>

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

              <div style={{ marginTop: "24px", display: "flex", alignItems: "center", justifyContent: "center", gap: "12px" }}>
                <div style={{ height: "1px", background: "var(--border-color, #e2e8f0)", flex: 1, maxWidth: "120px" }} />
                <span style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", fontWeight: 700 }}>أو بدون ملف</span>
                <div style={{ height: "1px", background: "var(--border-color, #e2e8f0)", flex: 1, maxWidth: "120px" }} />
              </div>

              <button
                type="button"
                onClick={addNewManualQuestion}
                className="btn-secondary"
                style={{ margin: "16px auto 0", display: "inline-flex", alignItems: "center", gap: "6px", padding: "10px 22px", fontSize: "13px", fontWeight: 700 }}
              >
                <Plus size={16} />
                <span>بدء إضافة أسئلة {assessmentType === "quiz" ? "الاختبار" : "الواجب"} يدوياً</span>
              </button>
            </div>
          )}

          {extractingFile && (
            <div style={{ textAlign: "center", padding: "90px 20px", color: "#0f766e" }}>
              <Loader2 size={44} className="animate-spin" style={{ margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "18px" }}>
                جاري تحليل الملف واستخراج الأسئلة والخيارات...
              </h3>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
                استخراج الأسئلة المقالية والاختيار من متعدد والرسومات البيانية وتوليد نموذج الإجابة بدقة.
              </p>
            </div>
          )}

          {/* Questions Canvas (Rendered when questions exist) */}
          {displayedQuestions.length > 0 && (
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
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "#ffffff", background: "rgb(15, 118, 110)", padding: "3px 8px", borderRadius: "6px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
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
                    {quizTitle.trim() || `${assessmentType === "quiz" ? "اختبار" : "واجب"} جديد`}
                  </h2>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {displayedQuestions.length > 0 && hasRestoredDraft && !approved && (
                    <button
                      type="button"
                      onClick={handleResetNewQuiz}
                      className="btn-secondary"
                      style={{
                        fontSize: "12px",
                        gap: "5px",
                        color: "#ffffff",
                        background: "rgb(118, 40, 40)",
                        borderColor: "rgb(118, 40, 40)",
                      }}
                      title="مسح المسودة الحالية والبدء باختبار جديد من الصفر"
                    >
                      <RotateCcw size={13} />
                      <span>بدء اختبار جديد</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={handleCopyQuestionsOnly}
                    className="btn-secondary"
                    style={{
                      fontSize: "12px",
                      gap: "5px",
                      color: "#ffffff",
                      background: "rgb(222, 138, 38)",
                      borderColor: "rgb(222, 138, 38)",
                      fontWeight: 700,
                    }}
                    title="نسخ نص الأسئلة والخيارات فقط إلى الحافظة بدون أي عناصر أو أزرار تحكم"
                  >
                    <Copy size={13} />
                    <span>نسخ نص الأسئلة فقط</span>
                  </button>

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

              {draft && draft.is_complete === false && (
                <div style={{ padding: "12px 16px", background: "rgb(15, 118, 110)", border: "1px solid rgb(15, 118, 110)", borderRadius: "10px", color: "#ffffff", fontSize: "12.5px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                  <AlertCircle size={18} style={{ flexShrink: 0, color: "#99f6e4" }} />
                  <span>تنبيه: تعذر استخراج كامل العدد المتوقع من الأسئلة من الملف، وتم إدراج كافة الأسئلة الموثوقة المتاحة بدقة.</span>
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

              {/* Points Assignment Alert Banner */}
              {questionsNeedingPoints.length > 0 && !approved && (
                <div
                  className="question-card-controls"
                  style={{
                    padding: "12px 18px",
                    background: "rgb(118, 40, 40)",
                    border: "1.5px solid rgb(118, 40, 40)",
                    borderRadius: "12px",
                    marginBottom: "16px",
                    boxShadow: "0 2px 6px rgba(118, 40, 40, 0.25)",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#ffffff",
                    fontWeight: 800,
                    fontSize: "13.5px",
                  }}
                >
                  <AlertCircle size={18} style={{ flexShrink: 0, color: "#fca5a5" }} />
                  <span>
                    تنبيه: توجد أسئلة مستخرجة بدون درجات محددة ({questionsNeedingPoints.length} من أصل {displayedQuestions.length} سؤال). يرجى تحديد درجات الأسئلة قبل النشر.
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
                      <div className="question-card-controls" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", paddingBottom: "8px", borderBottom: "1px solid var(--border-color)", userSelect: "none", WebkitUserSelect: "none" }}>
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
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
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
                              <option value="multiple_choice">اختيار من متعدد</option>
                              <option value="true_false">صح أو خطأ</option>
                              <option value="essay">سؤال مقالي</option>
                              <option value="fill_in_blank">أكمل الفراغات</option>
                              {normalizeQuestionType(q.question_type) === "unknown" && (
                                <option value="unknown">غير محدد (يحتاج مراجعة)</option>
                              )}
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

                            {(q.points === null || q.points === undefined || q.points <= 0 || q.needs_points_assignment) && (
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 700,
                                  color: "#ffffff",
                                  background: "rgb(15, 118, 110)",
                                  border: "1px solid rgb(15, 118, 110)",
                                  padding: "2px 7px",
                                  borderRadius: "6px",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "3px",
                                }}
                              >
                                <AlertCircle size={12} style={{ color: "#99f6e4" }} /> حدد الدرجة
                              </span>
                            )}
                            {q.needs_answer_review && (
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 700,
                                  color: "#c2410c",
                                  background: "#ffedd5",
                                  border: "1px solid #fed7aa",
                                  padding: "2px 7px",
                                  borderRadius: "6px",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "3px",
                                }}
                              >
                                <AlertCircle size={12} /> حدد الإجابة الصحيحة
                              </span>
                            )}
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
                              value={q.points ?? ""}
                              onChange={(e) => {
                                const val = e.target.value === "" ? null : parseInt(e.target.value);
                                updateQuestionPoints(q.id, val);
                              }}
                              placeholder="—"
                              style={{
                                width: "48px",
                                padding: "3px 6px",
                                border: (q.points === null || q.points === undefined || q.points <= 0) ? "1.5px solid rgb(15, 118, 110)" : "1px solid var(--border-color-strong)",
                                borderRadius: "6px",
                                fontSize: "12px",
                                fontWeight: 800,
                                textAlign: "center",
                                background: (q.points === null || q.points === undefined || q.points <= 0) ? "rgba(15, 118, 110, 0.12)" : "var(--bg-surface-secondary)",
                                color: (q.points === null || q.points === undefined || q.points <= 0) ? "rgb(15, 118, 110)" : "#0f392b",
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

                      {/* Unknown Type Quick Conversion Callout */}
                      {normalizeQuestionType(q.question_type) === "unknown" && (
                        <div
                          className="question-card-controls"
                          style={{
                            padding: "10px 14px",
                            background: "#fef2f2",
                            border: "1px solid #fecaca",
                            borderRadius: "8px",
                            marginBottom: "12px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexWrap: "wrap",
                            gap: "8px",
                            userSelect: "none",
                            WebkitUserSelect: "none",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#991b1b", fontSize: "12px", fontWeight: 700 }}>
                            <AlertCircle size={15} />
                            <span>نوع السؤال غير مصنف بدقة من الملف، حدد نوع السؤال:</span>
                          </div>
                          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                            <button
                              type="button"
                              onClick={() => updateQuestionType(q.id, "multiple_choice")}
                              style={{ padding: "4px 10px", borderRadius: "6px", border: "1px solid #059669", background: "#ecfdf5", color: "#065f46", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}
                            >
                              اختيار من متعدد
                            </button>
                            <button
                              type="button"
                              onClick={() => updateQuestionType(q.id, "true_false")}
                              style={{ padding: "4px 10px", borderRadius: "6px", border: "1px solid #2563eb", background: "#eff6ff", color: "#1e40af", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}
                            >
                              صح أو خطأ
                            </button>
                            <button
                              type="button"
                              onClick={() => updateQuestionType(q.id, "essay")}
                              style={{ padding: "4px 10px", borderRadius: "6px", border: "1px solid rgb(15, 118, 110)", background: "rgba(15, 118, 110, 0.12)", color: "rgb(15, 118, 110)", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}
                            >
                              سؤال مقالي
                            </button>
                            <button
                              type="button"
                              onClick={() => updateQuestionType(q.id, "fill_in_blank")}
                              style={{ padding: "4px 10px", borderRadius: "6px", border: "1px solid #7c3aed", background: "#f5f3ff", color: "#5b21b6", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}
                            >
                              أكمل الفراغ
                            </button>
                          </div>
                        </div>
                      )}

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
                                src={`/api/v1/lessons/assets/${assetId}/view`}
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

                      {/* True / False Question Options */}
                      {normalizeQuestionType(q.question_type) === "true_false" && (
                        <div style={{ display: "flex", gap: "12px", marginBottom: "14px", marginTop: "8px" }}>
                          {[
                            { key: "أ", text: "صح" },
                            { key: "ب", text: "خطأ" },
                          ].map((tfOpt) => {
                            const isSelected =
                              q.options?.find((o) => (o.key === tfOpt.key || o.text === tfOpt.text) && o.is_correct) !== undefined ||
                              q.correct_answer === tfOpt.text;
                            return (
                              <button
                                key={tfOpt.key}
                                type="button"
                                onClick={() => {
                                  const updatedOptions = [
                                    { key: "أ", text: "صح", is_correct: tfOpt.key === "أ" },
                                    { key: "ب", text: "خطأ", is_correct: tfOpt.key === "ب" },
                                  ];
                                  setActiveQuestionsList((prev) =>
                                    prev.map((item) =>
                                      item.id === q.id
                                        ? {
                                            ...item,
                                            options: updatedOptions,
                                            correct_answer: tfOpt.text,
                                            needs_answer_review: false,
                                          }
                                        : item
                                    )
                                  );
                                }}
                                style={{
                                  flex: 1,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  gap: "8px",
                                  padding: "10px 16px",
                                  borderRadius: "8px",
                                  border: isSelected ? "2px solid #059669" : "1.5px solid var(--border-color)",
                                  background: isSelected ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface-secondary)",
                                  color: isSelected ? "#065f46" : "var(--text-main)",
                                  fontWeight: 800,
                                  fontSize: "14px",
                                  cursor: "pointer",
                                  transition: "all 0.15s ease",
                                }}
                              >
                                <span
                                  style={{
                                    width: "20px",
                                    height: "20px",
                                    borderRadius: "50%",
                                    border: isSelected ? "2px solid #059669" : "2px solid var(--border-color-strong)",
                                    background: isSelected ? "#059669" : "transparent",
                                    color: "#fff",
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: "11px",
                                    fontWeight: 900,
                                  }}
                                >
                                  {isSelected ? "✓" : ""}
                                </span>
                                <span>{tfOpt.text}</span>
                                {isSelected && (
                                  <span style={{ fontSize: "11px", fontWeight: 700, color: "#059669", marginRight: "auto" }}>
                                    (الإجابة الصحيحة)
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}

                      {/* Options List (for MCQ) */}
                      {normalizeQuestionType(q.question_type) === "multiple_choice" && q.options && q.options.length > 0 && (
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
                                {isEditing && (q.options?.length ?? 0) > 2 && (
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

                          {isEditing && (q.options?.length ?? 0) < 6 && (
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

                      {/* Options Placeholder for MCQ when empty */}
                      {normalizeQuestionType(q.question_type) === "multiple_choice" && (!q.options || q.options.length === 0) && (
                        <div style={{ marginBottom: "12px" }}>
                          <button
                            type="button"
                            onClick={() => updateQuestionType(q.id, "multiple_choice")}
                            style={{
                              padding: "6px 12px",
                              borderRadius: "6px",
                              border: "1px dashed #059669",
                              background: "#ecfdf5",
                              color: "#059669",
                              fontSize: "12px",
                              fontWeight: 700,
                              cursor: "pointer",
                            }}
                          >
                            + إضافة خيارات السؤال (أ، ب، ج، د)
                          </button>
                        </div>
                      )}

                      {/* Fill in the Blank Student Answer Box & Definition */}
                      {normalizeQuestionType(q.question_type) === "fill_in_blank" && (
                        <div style={{ marginTop: "12px", padding: "12px 14px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                            <span style={{ fontSize: "12px", fontWeight: 800, color: "#0f392b" }}>
                              ✏️ سؤال إكمال الفراغ:
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
                                الإجابة النموذجية أو عناصر الإجابة المقالية (للمراجعة والتصحيح اليدوي):
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
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
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
                className="modal-close-btn"
                style={{
                  background: "var(--modal-close-bg)",
                  border: "none",
                  color: "#ffffff",
                  cursor: isPublishing ? "not-allowed" : "pointer",
                  width: "32px",
                  height: "32px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "8px",
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
                    {quizTitle.trim() || `${assessmentType === "quiz" ? "اختبار" : "واجب"} جديد`}
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

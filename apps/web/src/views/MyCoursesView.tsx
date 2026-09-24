import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  Award,
  Book,
  BookOpen,
  CheckCircle2,
  Clock,
  Download,
  FileCheck,
  FileText,
  Flag,
  Flame,
  HelpCircle,
  Lock,
  Play,
  ShoppingCart,
  Search,
  Sparkles,
  Timer,
  Upload,
  Video,
  XCircle,
  VideoOff,
  X,
  Zap,
  Plus,
  Eye,
  History,
  Menu,
  GraduationCap,
  Sun,
  Moon,
} from "lucide-react";
import { Course, CourseAssessmentRef, CurrentUser, NotificationItem, StudentProfile, VideoLesson } from "../types/lms";
import { Language, translations } from "../utils/i18n";
import { EducationalBookItem, RevisionPackageItem } from "./GeneralHomeView";
import { courseService } from "../services/lmsService";
import { apiRequest, fetchApiBlob, uploadWithProgress } from "../services/apiClient";
import { useToast } from "../components/ToastProvider";
import { FormulaRenderer } from "../components/FormulaRenderer";
import { PaymentTarget, lessonAccessService } from "../services/paymentService";
import { VideoLessonPage } from "../components/VideoLessonPage";

export interface DisplayBookItem extends EducationalBookItem {
  fileUrl?: string;
  fileSize?: string;
  lessonTitle?: string;
  lessonId?: string;
  isLessonMaterial?: boolean;
}

export type QuizResultPage = {
  quiz: { id: string; title: string };
  attempt: { id: string; attempt_number: number; is_practice: boolean; submitted_at: string | null; duration_seconds: number | null };
  attempts_history?: Array<{
    id: string;
    attempt_number: number;
    is_practice: boolean;
    score: number;
    total_points: number;
    submitted_at: string | null;
    duration_seconds?: number | null;
  }>;
  score: number;
  total_points: number;
  summary: { correct: number; wrong: number; skipped: number; total: number };
  questions: Array<{
    id: string;
    question_type: string;
    prompt: string;
    learning_objective: string | null;
    points: number;
    awarded: number;
    state: "correct" | "wrong" | "skipped";
    answered: boolean;
    student_answer: string;
    student_answer_letter: number | null;
    correct_answer: string;
    correct_answer_letter: number | null;
    options: string[];
  }>;
};

export interface CourseAssignment {
  id: string;
  courseId: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  title: string;
  description: string;
  lessonTitle: string;
  maxScore: number;
  availableFrom: string;
  dueDate: string;
  attachments?: { name: string; size: string; fileType: "pdf" | "doc" }[];
  instructions: string;
  questionsPrompt: string;
}

export interface CourseQuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctAnswerIndex: number;
  explanation: string;
}

export interface CourseQuiz {
  id: string;
  courseId: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  title: string;
  description: string;
  lessonTitle: string;
  durationMinutes: number;
  maxScore: number;
  availableFrom: string;
  dueDate: string;
  questions: CourseQuizQuestion[];
}

interface MyCoursesViewProps {
  enrolledCourses: Course[];
  onNavigateToCatalog: () => void;
  lang: Language;
  currentUser?: CurrentUser;
  purchasedLessonIds?: string[];
  onCheckout: (target: PaymentTarget) => void;
  onToggleMenu?: () => void;
  menuOpen?: boolean;
  notifications?: NotificationItem[];
  onMarkNotificationRead?: (id: string) => void;
  onSelectNotification?: (notif: NotificationItem) => void;
  onNavigateToNotifications?: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
  onToggleLang?: () => void;
  onNavigateHome?: () => void;
}

export const MyCoursesView: React.FC<MyCoursesViewProps> = ({
  enrolledCourses,
  onNavigateToCatalog,
  lang,
  currentUser,
  purchasedLessonIds = [],
  onCheckout,
  onToggleMenu,
  menuOpen = false,
  notifications = [],
  onMarkNotificationRead,
  onSelectNotification,
  onNavigateToNotifications,
  theme,
  onToggleTheme,
  onToggleLang,
  onNavigateHome,
}) => {
  const t = translations[lang];
  const toast = useToast();
  void notifications;
  void onMarkNotificationRead;
  void onSelectNotification;
  void onNavigateToNotifications;

  // Strictly filter by student's registered academic year
  const isStudent = currentUser?.role === "student";
  const studentYear = isStudent ? (currentUser as StudentProfile).academicYear : null;

  const validEnrolledCourses = enrolledCourses.filter((c) => {
    if (studentYear) {
      return c.academicYear === studentYear;
    }
    return true;
  });

  const selectedCourseId = validEnrolledCourses[0]?.id || "";

  const activeCourse =
    validEnrolledCourses.find((c) => c.id === selectedCourseId) || validEnrolledCourses[0];

  // Sub-tabs: Lessons, Revisions, Assignments, Quizzes, Books
  const [activeContentTab, setActiveContentTab] = useState<"lessons" | "revisions" | "assignments" | "quizzes" | "books">("lessons");

  // Search query within current course tabs
  const [courseSearchQuery, setCourseSearchQuery] = useState("");

  // Track purchased book IDs
  const [purchasedBookIds] = useState<string[]>([]);

  // Track purchased revision IDs
  const [purchasedRevisionIds] = useState<string[]>([]);

  const [localPurchasedIds, setLocalPurchasedIds] = useState<Set<string>>(
    () => new Set(purchasedLessonIds)
  );
  const [pendingRequestLessonIds, setPendingRequestLessonIds] = useState<Set<string>>(new Set());
  const [requestingLessonId, setRequestingLessonId] = useState<string | null>(null);

  useEffect(() => {
    setLocalPurchasedIds((prev) => {
      const next = new Set(prev);
      for (const id of purchasedLessonIds) {
        next.add(id);
      }
      return next;
    });
  }, [purchasedLessonIds]);

  // Load existing pending requests for this student and listen for live unlock
  useEffect(() => {
    if (!isStudent) return;
    void lessonAccessService
      .getMyRequests()
      .then((reqs) => {
        const pending = reqs.filter((r) => r.status === "pending").map((r) => r.lesson_id);
        setPendingRequestLessonIds(new Set(pending));
      })
      .catch(() => undefined);

    const handleUnlocked = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const unlockedId = detail?.lesson_id || detail?.resource_id;
      if (unlockedId) {
        setLocalPurchasedIds((prev) => new Set([...prev, unlockedId]));
        setPendingRequestLessonIds((prev) => {
          const next = new Set(prev);
          next.delete(unlockedId);
          return next;
        });
        toast({ message: "تمت إتاحة الدرس بنجاح من المعلم!", tone: "success" });
      }
    };

    window.addEventListener("lms_lesson_unlocked", handleUnlocked);
    return () => window.removeEventListener("lms_lesson_unlocked", handleUnlocked);
  }, [isStudent, toast]);

  async function handleRequestAccess(lesson: VideoLesson) {
    setRequestingLessonId(lesson.id);
    try {
      await lessonAccessService.requestAccess(lesson.id);
      setPendingRequestLessonIds((prev) => new Set([...prev, lesson.id]));
      toast({
        message: "تم إرسال طلب إتاحة الدرس للمعلم بنجاح. سيتم تفعيل الدرس تلقائياً فور موافقة المعلم.",
        tone: "success",
      });
    } catch (err) {
      toast({
        message: err instanceof Error ? err.message : "تعذر إرسال طلب الإتاحة",
        tone: "danger",
      });
    } finally {
      setRequestingLessonId(null);
    }
  }

  function handleBuyLesson(lesson: VideoLesson) {
    onCheckout({ productType: "lesson", productId: lesson.id });
  }

  const [activeBookModal, setActiveBookModal] = useState<DisplayBookItem | null>(null);

  // Track completed lesson IDs
  const [completedLessonIds, setCompletedLessonIds] = useState<string[]>([]);

  // Track submitted assignments
  const [submittedAssignmentIds, setSubmittedAssignmentIds] = useState<Record<string, { submittedAt: string; answer: string; score?: number }>>({});

  // Track completed quizzes
  const [completedQuizzes, setCompletedQuizzes] = useState<Record<string, { score: number; maxScore: number; completedAt: string }>>({});

  useEffect(() => {
    void courseService.getLessonProgress()
      .then((items) => setCompletedLessonIds(items.filter((item) => item.completion_percent >= 100).map((item) => item.lesson_id)))
      .catch(() => setCompletedLessonIds([]));
  }, [currentUser?.id]);

  // Interactive Modals State
  const [activeLessonModal, setActiveLessonModal] = useState<VideoLesson | null>(null);

  // Interactive Transcript & AI Grounded Q&A State



  async function downloadLessonMaterial(url: string, filename: string) {
    try {
      const blob = await fetchApiBlob(url);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      toast(`تم تنزيل ملف: ${filename}`, "success");
    } catch {
      toast("تعذر تنزيل المذكرة. تحقق من صلاحية الوصول ثم أعد المحاولة.", "danger");
    }
  }


  const [activeAssignmentModal, setActiveAssignmentModal] = useState<CourseAssignment | null>(null);
  const [activeQuizModal, setActiveQuizModal] = useState<CourseQuiz | null>(null);

  // ── Server-driven quiz solving (standalone page) ──
  // ServerQuizSolve = real published quiz from GET /quizzes/{id}/solve.
  // Legacy local quizzes (activeQuizModal.questions) keep the old local path.


  type ServerQuizSolve = {
    quizId: string;
    title: string;
    durationSeconds: number | null;
    totalPoints: number;
    questions: Array<{
      id: string;
      question_type: string;
      prompt: string;
      options: Array<{ key?: string; text: string; is_correct?: boolean }> | null;
      points: number;
    }>;
  };
  const [serverQuiz, setServerQuiz] = useState<ServerQuizSolve | null>(null);
  const [serverQuizLoading, setServerQuizLoading] = useState(false);
  const [serverQuizError, setServerQuizError] = useState<string | null>(null);
  const [serverQuizAnswers, setServerQuizAnswers] = useState<Record<string, string>>({});
  // Mock-style solving: one question at a time + a question-map sidebar.
  const [serverQuizQuestionIndex, setServerQuizQuestionIndex] = useState(0);
  const [serverQuizFlagged, setServerQuizFlagged] = useState<Record<string, boolean>>({});
  const [serverQuizSubmitting, setServerQuizSubmitting] = useState(false);
  const [serverQuizResult, setServerQuizResult] = useState<{ attemptId?: string; score: number; total: number; attemptNumber: number } | null>(null);
  const [showQuizSubmitConfirm, setShowQuizSubmitConfirm] = useState(false);
  // Full graded result (standalone result page)
  const [quizResultPage, setQuizResultPage] = useState<QuizResultPage | null>(null);
  const [quizResultLoading, setQuizResultLoading] = useState(false);
  const [quizResultError, setQuizResultError] = useState<string | null>(null);
  const [quizResultFilter, setQuizResultFilter] = useState<"all" | "correct" | "wrong">("all");
  // Quiz attempt history modal state (opened from course page quiz card)
  const [activeQuizHistoryModal, setActiveQuizHistoryModal] = useState<CourseAssessmentRef | null>(null);
  const [quizHistoryAttempts, setQuizHistoryAttempts] = useState<Array<{
    id: string;
    attempt_number: number;
    is_practice: boolean;
    score: number;
    total_points: number;
    submitted_at: string | null;
    duration_seconds?: number | null;
  }> | null>(null);
  const [quizHistoryLoading, setQuizHistoryLoading] = useState(false);
  // Server-authoritative attempt: the clock starts when the page opens.
  const [serverQuizAttempt, setServerQuizAttempt] = useState<{ id: string; attemptNumber: number; expiresAt: string | null; isPractice: boolean } | null>(null);
  const [serverQuizDeadline, setServerQuizDeadline] = useState<number | null>(null);
  const [serverQuizRemaining, setServerQuizRemaining] = useState<number | null>(null);
  const serverQuizAutoSubmitted = useRef(false);

  // ── Server-driven assignment solving (standalone page) ──
  type ServerAssignmentSolve = {
    id: string;
    title: string;
    prompt: string;
    dueAt: string | null;
    maxScore: number;
    latestSubmission: { version: number; status: string; submittedAt: string | null; hasFile: boolean } | null;
    sheetUrl: string;
  };
  const [serverAssignment, setServerAssignment] = useState<ServerAssignmentSolve | null>(null);
  const [serverAssignmentLoading, setServerAssignmentLoading] = useState(false);
  const [serverAssignmentError, setServerAssignmentError] = useState<string | null>(null);
  const [assignmentFile, setAssignmentFile] = useState<File | null>(null);
  const [assignmentUploading, setAssignmentUploading] = useState(false);
  const [assignmentUploadDone, setAssignmentUploadDone] = useState<{ version: number; submittedAt: string } | null>(null);

  // ── Browser Back Button & History Stack for Overlays / Modals ──
  const overlayHistoryStack = useRef<string[]>([]);

  const closeOverlay = useCallback((overlayKey: string, directClose: () => void) => {
    if (overlayHistoryStack.current.includes(overlayKey)) {
      window.history.back();
    } else {
      directClose();
    }
  }, []);

  const handleConfirmSubmitQuiz = () => {
    if (overlayHistoryStack.current[overlayHistoryStack.current.length - 1] === "quizSubmitConfirm") {
      window.history.back();
    } else {
      setShowQuizSubmitConfirm(false);
    }
    void submitServerQuiz();
  };

  const handleHeaderNavigateHome = () => {
    overlayHistoryStack.current = [];
    setShowQuizSubmitConfirm(false);
    setServerQuiz(null);
    setServerQuizError(null);
    setQuizResultPage(null);
    setQuizResultError(null);
    setServerAssignment(null);
    setServerAssignmentError(null);
    setActiveLessonModal(null);
    setActiveBookModal(null);
    setActiveQuizHistoryModal(null);
    setActiveQuizModal(null);
    setActiveAssignmentModal(null);
    onNavigateHome?.();
  };

  useEffect(() => {
    const handleCloseOverlays = () => {
      overlayHistoryStack.current = [];
      setShowQuizSubmitConfirm(false);
      setServerQuiz(null);
      setServerQuizError(null);
      setQuizResultPage(null);
      setQuizResultError(null);
      setServerAssignment(null);
      setServerAssignmentError(null);
      setActiveLessonModal(null);
      setActiveBookModal(null);
      setActiveQuizHistoryModal(null);
      setActiveQuizModal(null);
      setActiveAssignmentModal(null);
    };
    window.addEventListener("lms:close-overlays", handleCloseOverlays);
    return () => window.removeEventListener("lms:close-overlays", handleCloseOverlays);
  }, []);

  // Sync overlays with browser history for Google Chrome Back button support
  useEffect(() => {
    if (serverQuiz) {
      if (!overlayHistoryStack.current.includes("serverQuiz")) {
        overlayHistoryStack.current.push("serverQuiz");
        window.history.pushState({ lmsOverlay: "serverQuiz" }, "");
      }
    }
  }, [Boolean(serverQuiz)]);

  useEffect(() => {
    if (showQuizSubmitConfirm) {
      if (!overlayHistoryStack.current.includes("quizSubmitConfirm")) {
        overlayHistoryStack.current.push("quizSubmitConfirm");
        window.history.pushState({ lmsOverlay: "quizSubmitConfirm" }, "");
      }
    }
  }, [showQuizSubmitConfirm]);

  useEffect(() => {
    if (quizResultPage) {
      if (!overlayHistoryStack.current.includes("quizResultPage")) {
        overlayHistoryStack.current.push("quizResultPage");
        window.history.pushState({ lmsOverlay: "quizResultPage" }, "");
      }
    }
  }, [Boolean(quizResultPage)]);

  useEffect(() => {
    if (serverAssignment) {
      if (!overlayHistoryStack.current.includes("serverAssignment")) {
        overlayHistoryStack.current.push("serverAssignment");
        window.history.pushState({ lmsOverlay: "serverAssignment" }, "");
      }
    }
  }, [Boolean(serverAssignment)]);

  useEffect(() => {
    if (activeLessonModal) {
      if (!overlayHistoryStack.current.includes("activeLessonModal")) {
        overlayHistoryStack.current.push("activeLessonModal");
        window.history.pushState({ lmsOverlay: "activeLessonModal" }, "");
      }
    }
  }, [Boolean(activeLessonModal)]);

  useEffect(() => {
    if (activeBookModal) {
      if (!overlayHistoryStack.current.includes("activeBookModal")) {
        overlayHistoryStack.current.push("activeBookModal");
        window.history.pushState({ lmsOverlay: "activeBookModal" }, "");
      }
    }
  }, [Boolean(activeBookModal)]);

  useEffect(() => {
    if (activeQuizHistoryModal) {
      if (!overlayHistoryStack.current.includes("activeQuizHistoryModal")) {
        overlayHistoryStack.current.push("activeQuizHistoryModal");
        window.history.pushState({ lmsOverlay: "activeQuizHistoryModal" }, "");
      }
    }
  }, [Boolean(activeQuizHistoryModal)]);

  useEffect(() => {
    if (activeQuizModal) {
      if (!overlayHistoryStack.current.includes("activeQuizModal")) {
        overlayHistoryStack.current.push("activeQuizModal");
        window.history.pushState({ lmsOverlay: "activeQuizModal" }, "");
      }
    }
  }, [Boolean(activeQuizModal)]);

  useEffect(() => {
    if (activeAssignmentModal) {
      if (!overlayHistoryStack.current.includes("activeAssignmentModal")) {
        overlayHistoryStack.current.push("activeAssignmentModal");
        window.history.pushState({ lmsOverlay: "activeAssignmentModal" }, "");
      }
    }
  }, [Boolean(activeAssignmentModal)]);

  useEffect(() => {
    const handlePopState = () => {
      const top = overlayHistoryStack.current.pop();
      if (!top) return;

      if (top === "quizSubmitConfirm") {
        setShowQuizSubmitConfirm(false);
      } else if (top === "serverQuiz") {
        setShowQuizSubmitConfirm(false);
        setServerQuiz(null);
        setServerQuizError(null);
        setServerQuizAttempt(null);
        setServerQuizRemaining(null);
        setServerQuizResult(null);
      } else if (top === "quizResultPage") {
        setQuizResultPage(null);
        setQuizResultError(null);
      } else if (top === "serverAssignment") {
        setServerAssignment(null);
        setServerAssignmentError(null);
        setAssignmentFile(null);
      } else if (top === "activeLessonModal") {
        setActiveLessonModal(null);
      } else if (top === "activeBookModal") {
        setActiveBookModal(null);
      } else if (top === "activeQuizHistoryModal") {
        setActiveQuizHistoryModal(null);
      } else if (top === "activeQuizModal") {
        setActiveQuizModal(null);
      } else if (top === "activeAssignmentModal") {
        setActiveAssignmentModal(null);
      }
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  /** Open the standalone graded-result page for the given attempt (or latest attempt if omitted). */
  async function openQuizResultPage(quizId: string, attemptId?: string) {
    setQuizResultPage(null);
    setQuizResultError(null);
    setQuizResultFilter("all");
    setQuizResultLoading(true);
    try {
      const url = attemptId ? `/quizzes/${quizId}/result?attempt_id=${attemptId}` : `/quizzes/${quizId}/result`;
      const data = await apiRequest<QuizResultPage>(url);
      setQuizResultPage(data);
    } catch (err) {
      setQuizResultError(err instanceof Error ? err.message : "لا توجد نتيجة متاحة بعد");
    } finally {
      setQuizResultLoading(false);
    }
  }

  /** Fetch and open the attempt history modal for a quiz. */
  async function openQuizHistoryModal(qz: CourseAssessmentRef) {
    setActiveQuizHistoryModal(qz);
    setQuizHistoryAttempts(null);
    setQuizHistoryLoading(true);
    try {
      const list = await apiRequest<Array<{
        id: string;
        attempt_number: number;
        is_practice: boolean;
        score: number;
        total_points: number;
        submitted_at: string | null;
        duration_seconds?: number | null;
      }>>(`/quizzes/${qz.id}/attempts-history`);
      setQuizHistoryAttempts(list);
    } catch {
      setQuizHistoryAttempts([]);
    } finally {
      setQuizHistoryLoading(false);
    }
  }

  async function openServerQuiz(assessment: CourseAssessmentRef) {
    setServerQuiz(null);
    setServerQuizError(null);
    setServerQuizAnswers({});
    setServerQuizResult(null);
    setServerQuizAttempt(null);
    setServerQuizDeadline(null);
    setServerQuizRemaining(null);
    serverQuizAutoSubmitted.current = false;
    setServerQuizQuestionIndex(0);
    setServerQuizFlagged({});
    setServerQuizLoading(true);
    try {
      const data = await apiRequest<{
        quiz: { id: string; title: string; duration_seconds: number | null; total_points: number };
        attempt: { id: string; attempt_number: number; started_at: string | null; expires_at: string | null } | null;
        questions: ServerQuizSolve["questions"];
      }>(`/quizzes/${assessment.id}/solve`);
      setServerQuiz({
        quizId: data.quiz.id,
        title: data.quiz.title,
        durationSeconds: data.quiz.duration_seconds,
        totalPoints: data.quiz.total_points,
        questions: data.questions,
      });
      if (data.attempt) {
        setServerQuizAttempt({
          id: data.attempt.id,
          attemptNumber: data.attempt.attempt_number,
          expiresAt: data.attempt.expires_at,
          isPractice: Boolean((data.attempt as { is_practice?: boolean }).is_practice),
        });
        setServerQuizDeadline(data.attempt.expires_at ? new Date(data.attempt.expires_at).getTime() : null);
      }
    } catch (err) {
      setServerQuizError(err instanceof Error ? err.message : "تعذر فتح الاختبار");
    } finally {
      setServerQuizLoading(false);
    }
  }

  // ── Countdown tick: recompute remaining seconds from the server deadline ──
  useEffect(() => {
    if (serverQuizDeadline === null || !serverQuiz || serverQuizResult) {
      setServerQuizRemaining(null);
      return;
    }
    const compute = () => setServerQuizRemaining(Math.max(0, Math.floor((serverQuizDeadline - Date.now()) / 1000)));
    compute();
    const interval = setInterval(compute, 1000);
    return () => clearInterval(interval);
  }, [serverQuizDeadline, serverQuiz, serverQuizResult]);

  // Auto-submit exactly once when the timer hits zero (server also enforces).
  useEffect(() => {
    if (serverQuizRemaining !== null && serverQuizRemaining <= 0 && serverQuiz && !serverQuizResult && !serverQuizSubmitting && !serverQuizAutoSubmitted.current) {
      serverQuizAutoSubmitted.current = true;
      toast({ message: "انتهى وقت الاختبار — جاري التسليم التلقائي", tone: "warning" });
      void submitServerQuiz(true);
    }
  }, [serverQuizRemaining, serverQuiz, serverQuizResult, serverQuizSubmitting]);

  /** Submit the solved server quiz: real attempt + server-side grading. */
  async function submitServerQuiz(force = false) {
    if (!serverQuiz) return;
    if (!force && serverQuizRemaining !== null && serverQuizRemaining <= 0) return; // manual submit after expiry
    setServerQuizSubmitting(true);
    try {
      // The attempt was already started when the page opened (server-side
      // clock). Reuse it — creating a new one here would restart the timer.
      let attemptId = serverQuizAttempt?.id;
      if (!attemptId) {
        const created = await apiRequest<{ id: string }>(`/quizzes/${serverQuiz.quizId}/attempts`, { method: "POST" });
        attemptId = created.id;
      }
      await apiRequest<{ score: number | null; total_points: number | null; attempt_number: number }>(`/quiz-attempts/${attemptId}/submit`, {
        method: "POST",
        body: JSON.stringify({
          submission_key: `web-${attemptId}`.slice(0, 60),
          answers: serverQuiz.questions.map((q) => ({
            question_id: q.id,
            answer: serverQuizAnswers[q.id] ?? null,
          })),
        }),
      }).then((submitted) => {
        setServerQuizResult({
          attemptId: (submitted as { id?: string }).id || attemptId,
          score: submitted.score ?? 0,
          total: submitted.total_points ?? serverQuiz.totalPoints,
          attemptNumber: submitted.attempt_number,
        });
        setShowQuizSubmitConfirm(false);
      });
    } catch (err) {
      const expired = serverQuizRemaining !== null && serverQuizRemaining <= 0;
      toast({
        message: expired ? "انتهى وقت الاختبار وأُغلق التسليم" : err instanceof Error ? err.message : "تعذر تسليم الاختبار",
        tone: expired ? "warning" : "danger",
      });
    } finally {
      setServerQuizSubmitting(false);
    }
  }

  /** Open the standalone assignment page: PDF download → solve → upload. */
  async function openServerAssignment(assessment: CourseAssessmentRef) {
    setServerAssignment(null);
    setServerAssignmentError(null);
    setAssignmentFile(null);
    setAssignmentUploadDone(null);
    setServerAssignmentLoading(true);
    try {
      const data = await apiRequest<{
        id: string;
        title: string;
        prompt: string;
        due_at: string | null;
        max_score: number;
        my_latest_submission: { version: number; status: string; submitted_at: string | null; has_file: boolean } | null;
      }>(`/assignments/${assessment.id}/solve`);
      setServerAssignment({
        id: data.id,
        title: data.title,
        prompt: data.prompt,
        dueAt: data.due_at,
        maxScore: data.max_score,
        sheetUrl: `/api/v1/assignments/${data.id}/sheet.pdf`,
        latestSubmission: data.my_latest_submission
          ? {
              version: data.my_latest_submission.version,
              status: data.my_latest_submission.status,
              submittedAt: data.my_latest_submission.submitted_at,
              hasFile: data.my_latest_submission.has_file,
            }
          : null,
      });
    } catch (err) {
      setServerAssignmentError(err instanceof Error ? err.message : "تعذر فتح الواجب");
    } finally {
      setServerAssignmentLoading(false);
    }
  }

  /** Download the printable assignment sheet (server-rendered Arabic PDF). */
  async function downloadAssignmentSheet() {
    if (!serverAssignment) return;
    try {
      const blob = await fetchApiBlob(serverAssignment.sheetUrl);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `${serverAssignment.title || "assignment"}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      toast({ message: "تم تحميل ورقة الواجب", tone: "success" });
    } catch {
      toast({ message: "تعذر تحميل ورقة الواجب", tone: "danger" });
    }
  }

  /** Upload the photographed/typed solution file (PDF or image). */
  async function submitAssignmentFile() {
    if (!serverAssignment || !assignmentFile) return;
    setAssignmentUploading(true);
    try {
      const form = new FormData();
      form.append("file", assignmentFile);
      const result = await uploadWithProgress<{ version: number; submitted_at: string }>(
        `/assignments/${serverAssignment.id}/submissions/file`,
        form,
      );
      setAssignmentUploadDone({ version: result.version, submittedAt: result.submitted_at });
      setAssignmentFile(null);
      toast({ message: "تم تسليم حل الواجب بنجاح", tone: "success" });
    } catch (err) {
      toast({ message: err instanceof Error ? err.message : "تعذر رفع ملف الحل", tone: "danger" });
    } finally {
      setAssignmentUploading(false);
    }
  }

  // Quiz Player State
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState<boolean>(false);
  const [quizScoreResult, setQuizScoreResult] = useState<{ score: number; maxScore: number } | null>(null);

  // Assignment Solve Form State
  const [assignmentAnswerText, setAssignmentAnswerText] = useState("");
  const [assignmentSuccessMsg, setAssignmentSuccessMsg] = useState(false);

  const isTeacher = currentUser?.role === "teacher";

  // Manual creation forms for teacher
  const [showManualQuizForm, setShowManualQuizForm] = useState(false);
  const [showManualAssignmentForm, setShowManualAssignmentForm] = useState(false);
  const [manualQuizTitle, setManualQuizTitle] = useState("");
  const [manualQuizQuestion, setManualQuizQuestion] = useState("");
  const [manualAssignmentTitle, setManualAssignmentTitle] = useState("");
  const [manualAssignmentPrompt, setManualAssignmentPrompt] = useState("");
  const [manualCreationLoading, setManualCreationLoading] = useState(false);

  const currentCourse = activeCourse;

  const allRevisions: RevisionPackageItem[] = [];
  const allBooks: EducationalBookItem[] = [];

  // Lesson materials / PDFs automatically exposed as books/booklets
  // "و خلي الكتاب او المذكره حتي لو اترفعوا مع فديو يبانوا في كتبي و مذكراتي المشتراه"
  const seenMaterialIds = new Set<string>();
  const lessonBooks: DisplayBookItem[] = validEnrolledCourses.flatMap((course) =>
    (course.lessons || []).flatMap((lesson) =>
      (lesson.materials || []).reduce<DisplayBookItem[]>((acc, mat) => {
        const matId = mat.id || `mat_${lesson.id}_${mat.title}`;
        if (seenMaterialIds.has(matId)) return acc;
        seenMaterialIds.add(matId);

        const isPdf = mat.fileType === "pdf" || mat.title.toLowerCase().endsWith(".pdf");
        const cleanTitle = mat.title.replace(/\.[^/.]+$/, "");
        acc.push({
          id: matId,
          title: cleanTitle || mat.title,
          academicYear: course.academicYear || "1st_secondary",
          author: course.teacherName || "مستر حسن شعبان",
          authorTitle: course.teacherTitle || "معلم خبير الكيمياء",
          pagesCount: mat.fileSize ? Math.max(1, Math.round(parseInt(mat.fileSize) / 35)) : 20,
          fileSize: mat.fileSize || "",
          fileUrl: mat.fileUrl,
          price: "0",
          description: `مذكرة وكتاب تعليمي مرفق مع شرح: ${lesson.title}`,
          gradient: "linear-gradient(135deg, #065f46 0%, #047857 100%)",
          sampleTopics: [lesson.title, isPdf ? "ملف PDF" : "مستند تعليمي", course.title].filter(Boolean),
          lessonTitle: lesson.title,
          lessonId: lesson.id,
          isLessonMaterial: true,
        });
        return acc;
      }, [])
    )
  );

  const allPurchasedBooks: DisplayBookItem[] = [
    ...allBooks.filter((b) => purchasedBookIds.includes(b.id)).map((b) => ({ ...b, isLessonMaterial: false })),
    ...lessonBooks,
  ];

  // Revision Video Lessons uploaded by teacher with isRevision flag or "مراجعة" in title/unit
  const revisionVideoLessons = React.useMemo(() => {
    const list: Array<{ lesson: VideoLesson; course: Course }> = [];
    validEnrolledCourses.forEach((course) => {
      (course.lessons || []).forEach((l) => {
        if (l.isRevision || l.title.includes("مراجعة") || l.unitTitle?.includes("مراجعة")) {
          list.push({ lesson: l, course });
        }
      });
    });
    return list;
  }, [validEnrolledCourses]);

  const filteredRevisionVideoLessons = React.useMemo(() => {
    if (!courseSearchQuery.trim()) return revisionVideoLessons;
    const q = courseSearchQuery.trim().toLowerCase();
    return revisionVideoLessons.filter(
      (item) =>
        item.lesson.title.toLowerCase().includes(q) ||
        (item.lesson.description && item.lesson.description.toLowerCase().includes(q)) ||
        (item.lesson.unitTitle && item.lesson.unitTitle.toLowerCase().includes(q)) ||
        item.course.title.toLowerCase().includes(q)
    );
  }, [revisionVideoLessons, courseSearchQuery]);

  // Assignments Data for Current Course (derived dynamically from course or platform store)
  const courseContent = currentCourse as (Course & {
    assignments?: CourseAssignment[];
    quizzes?: CourseQuiz[];
  }) | undefined;
  const courseAssignments: CourseAssignment[] = courseContent?.assignments || [];

  // Quizzes Data for Current Course (derived dynamically from course or platform store)
  const courseQuizzes: CourseQuiz[] = courseContent?.quizzes || [];

  // Server-published assessments (real, scoped to lessons/units, payment-gated).
  // These come from GET /courses/{id}/assessments via courseService.getCourses.
  const serverAssessments: CourseAssessmentRef[] = currentCourse?.assessments || [];
  const serverQuizzes = serverAssessments.filter((a) => a.kind === "quiz");
  const serverAssignments = serverAssessments.filter((a) => a.kind === "assignment");
  const lessonTitleById = new Map((currentCourse?.lessons || []).map((l) => [l.id, l.title]));

  // Helper to determine time availability & deadline status
  function getTimeStatus(availableFromStr: string, dueDateStr: string, isSubmitted: boolean) {
    if (isSubmitted) {
      return {
        status: "submitted" as const,
        label: "تم التسليم والتقييم",
        bg: "#dcfce7",
        color: "#166534",
        border: "#86efac",
        canOpen: true,
      };
    }

    const now = new Date(2026, 7, 25, 12, 0); // Reference local system context: Aug 25, 2026 12:00 PM

    // Helper to parse date strings
    function parseCustom(str: string) {
      try {
        const isEve = str.includes("م");
        const clean = str.replace(" ص", "").replace(" م", "").trim();
        const [dPart, tPart] = clean.split(" ");
        if (dPart && tPart) {
          const [y, m, d] = dPart.split("-").map(Number);
          let h = Number(tPart.split(":")[0]);
          const min = Number(tPart.split(":")[1]);
          if (isEve && h < 12) h += 12;
          if (!isEve && h === 12) h = 0;
          return new Date(y, m - 1, d, h, min);
        }
      } catch (e) {
        console.error(e);
      }
      return new Date(2026, 7, 26);
    }

    const start = parseCustom(availableFromStr);
    const end = parseCustom(dueDateStr);

    if (now < start) {
      return {
        status: "locked" as const,
        label: `يفتح في: ${availableFromStr}`,
        bg: "#fef3c7",
        color: "#92400e",
        border: "#fde68a",
        canOpen: false,
      };
    }

    if (now > end) {
      return {
        status: "expired" as const,
        label: `انتهى موعد التسليم - ${dueDateStr}`,
        bg: "#fee2e2",
        color: "#991b1b",
        border: "#fca5a5",
        canOpen: false,
      };
    }

    return {
      status: "open" as const,
      label: `متاح الآن للحل - الموعد النهائي: ${dueDateStr}`,
      bg: "var(--bg-accent, #ecfdf5)",
      color: "#059669",
      border: "var(--border-accent, #a7f3d0)",
      canOpen: true,
    };
  }

  function toggleCompleteLesson(lessonId: string) {
    if (completedLessonIds.includes(lessonId)) return;
    void courseService.completeLesson(lessonId)
      .then(() => setCompletedLessonIds((previous) => [...new Set([...previous, lessonId])]))
      .catch((error) => toast({ message: error instanceof Error ? error.message : "تعذر حفظ تقدم الدرس", tone: "danger" }));
  }

  // Handle Quiz Submission
  function handleSubmitQuiz() {
    if (!activeQuizModal) return;
    let correctCount = 0;
    activeQuizModal.questions.forEach((q) => {
      if (quizAnswers[q.id] === q.correctAnswerIndex) {
        correctCount += 1;
      }
    });

    const score = Math.round((correctCount / activeQuizModal.questions.length) * activeQuizModal.maxScore);
    const result = { score, maxScore: activeQuizModal.maxScore, completedAt: new Date().toISOString().split("T")[0] };

    setQuizScoreResult({ score, maxScore: activeQuizModal.maxScore });
    setQuizSubmitted(true);

    const updated = { ...completedQuizzes, [activeQuizModal.id]: result };
    setCompletedQuizzes(updated);
  }

  // Handle Assignment Submission
  function handleSubmitAssignment() {
    if (!activeAssignmentModal || !assignmentAnswerText.trim()) return;

    const submissionData = {
      submittedAt: "2026-08-25 08:30 م",
      answer: assignmentAnswerText,
      score: 19,
    };

    const updated = { ...submittedAssignmentIds, [activeAssignmentModal.id]: submissionData };
    setSubmittedAssignmentIds(updated);

    setAssignmentSuccessMsg(true);
    setTimeout(() => {
      setAssignmentSuccessMsg(false);
      setActiveAssignmentModal(null);
      setAssignmentAnswerText("");
    }, 2000);
  }

  // Empty catalog state
  if (validEnrolledCourses.length === 0) {
    return (
      <div className="page-container">
        <div style={{ textAlign: "center", padding: "80px 20px", background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px" }}>
          <BookOpen size={48} style={{ color: "var(--text-light)", margin: "0 auto 16px" }} />
          <h2 style={{ margin: "0 0 8px", fontSize: "20px", color: "var(--text-main)" }}>فارغ</h2>
          <p style={{ margin: "0 0 20px", color: "var(--text-muted)", fontSize: "14px" }}>
            {t.noCoursesEnrolledDesc}
          </p>
          <button className="btn-primary" onClick={onNavigateToCatalog}>
            {t.browseCatalogBtn}
          </button>
        </div>
      </div>
    );
  }

  if (activeLessonModal && currentCourse) {
    return (
      <VideoLessonPage
        lesson={activeLessonModal}
        course={currentCourse}
        currentUser={currentUser}
        completedLessonIds={completedLessonIds}
        onToggleCompleteLesson={toggleCompleteLesson}
        onSelectLesson={(ls) => setActiveLessonModal(ls)}
        onClose={() => closeOverlay("activeLessonModal", () => setActiveLessonModal(null))}
        onDownloadMaterial={downloadLessonMaterial}
      />
    );
  }

  const courseLessons = currentCourse?.lessons || [];
  const completedLessonsCount = courseLessons.filter((l) => completedLessonIds.includes(l.id)).length;

  // Search query filter for current tab items
  const searchQueryNormalized = courseSearchQuery.trim().toLowerCase();

  const filteredLessons = courseLessons.filter((l) => {
    if (!searchQueryNormalized) return true;
    return (
      l.title.toLowerCase().includes(searchQueryNormalized) ||
      (l.description && l.description.toLowerCase().includes(searchQueryNormalized))
    );
  });

  const filteredRevisions = allRevisions.filter((r) => {
    if (!searchQueryNormalized) return true;
    return (
      r.title.toLowerCase().includes(searchQueryNormalized) ||
      (r.description && r.description.toLowerCase().includes(searchQueryNormalized))
    );
  });

  const filteredAssignments = courseAssignments.filter((a) => {
    if (!searchQueryNormalized) return true;
    return (
      a.title.toLowerCase().includes(searchQueryNormalized) ||
      (a.description && a.description.toLowerCase().includes(searchQueryNormalized))
    );
  });

  const filteredServerAssignments = serverAssignments.filter((a) => {
    if (!searchQueryNormalized) return true;
    return a.title.toLowerCase().includes(searchQueryNormalized);
  });

  const filteredQuizzes = courseQuizzes.filter((item) => {
    if (!searchQueryNormalized) return true;
    return item.title.toLowerCase().includes(searchQueryNormalized);
  });

  const filteredServerQuizzes = serverQuizzes.filter((item) => {
    if (!searchQueryNormalized) return true;
    return item.title.toLowerCase().includes(searchQueryNormalized);
  });

  const filteredBooks = allPurchasedBooks.filter((b) => {
    if (!searchQueryNormalized) return true;
    return (
      b.title.toLowerCase().includes(searchQueryNormalized) ||
      (b.description && b.description.toLowerCase().includes(searchQueryNormalized)) ||
      (b.author && b.author.toLowerCase().includes(searchQueryNormalized)) ||
      (b.lessonTitle && b.lessonTitle.toLowerCase().includes(searchQueryNormalized))
    );
  });

  return (
    <div className="page-container">
      {/* Top Urgent Counter */}
      <div className="urgency-banner" style={{ marginBottom: "20px" }}>
        <div className="urgency-counter">
          <div className="urgency-badge">
            <Flame size={24} />
            <span>متبقي {Math.max(0, courseLessons.length - completedLessonsCount)} دروس</span>
          </div>
          <div>
            <strong style={{ display: "block", fontSize: "16px", color: "var(--urgency-text)" }}>
              مقرر {currentCourse.title}
            </strong>
          </div>
        </div>
      </div>



      {/* Main Course Header Card */}
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "18px", padding: "24px", marginBottom: "24px", boxShadow: "var(--card-shadow)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "4px 10px", borderRadius: "6px", border: "1px solid var(--border-accent)" }}>
              {currentCourse.subject || "الكيمياء"}
            </span>
            <h1 style={{ margin: "8px 0 4px", fontSize: "24px", color: "var(--text-main)" }}>
              {currentCourse.title}
            </h1>
            <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "680px", lineHeight: "1.5" }}>
              {currentCourse.description}
            </p>
          </div>
        </div>

        {/* Content Tabs & Dedicated Search Bar (Matching Image 2 layout) */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "16px",
            marginTop: "24px",
            borderTop: "1px solid var(--border-color)",
            paddingTop: "18px",
            flexWrap: "wrap",
          }}
        >
          {/* Sub-Tabs (Right side in RTL) */}
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              onClick={() => setActiveContentTab("lessons")}
              style={{
                padding: "10px 20px",
                borderRadius: "10px",
                border: activeContentTab === "lessons" ? "2px solid #059669" : "1px solid var(--border-color)",
                background: activeContentTab === "lessons" ? "#0f392b" : "var(--bg-surface-secondary)",
                color: activeContentTab === "lessons" ? "#ffffff" : "var(--text-muted)",
                fontSize: "13.5px",
                fontWeight: 800,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.15s ease",
              }}
            >
              <Video size={16} />
              <span>الدروس وشروحات الفيديو</span>
            </button>

            <button
              onClick={() => setActiveContentTab("revisions")}
              style={{
                padding: "10px 20px",
                borderRadius: "10px",
                border: activeContentTab === "revisions" ? "2px solid #059669" : "1px solid var(--border-color)",
                background: activeContentTab === "revisions" ? "#0f392b" : "var(--bg-surface-secondary)",
                color: activeContentTab === "revisions" ? "#ffffff" : "var(--text-muted)",
                fontSize: "13.5px",
                fontWeight: 800,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.15s ease",
              }}
            >
              <Zap size={16} />
              <span>المراجعات والورش المفعلة</span>
            </button>

            <button
              onClick={() => setActiveContentTab("assignments")}
              style={{
                padding: "10px 20px",
                borderRadius: "10px",
                border: activeContentTab === "assignments" ? "2px solid #059669" : "1px solid var(--border-color)",
                background: activeContentTab === "assignments" ? "#0f392b" : "var(--bg-surface-secondary)",
                color: activeContentTab === "assignments" ? "#ffffff" : "var(--text-muted)",
                fontSize: "13.5px",
                fontWeight: 800,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.15s ease",
              }}
            >
              <FileText size={16} />
              <span>الواجبات والتكليفات</span>
            </button>

            <button
              onClick={() => setActiveContentTab("quizzes")}
              style={{
                padding: "10px 20px",
                borderRadius: "10px",
                border: activeContentTab === "quizzes" ? "2px solid #059669" : "1px solid var(--border-color)",
                background: activeContentTab === "quizzes" ? "#0f392b" : "var(--bg-surface-secondary)",
                color: activeContentTab === "quizzes" ? "#ffffff" : "var(--text-muted)",
                fontSize: "13.5px",
                fontWeight: 800,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.15s ease",
              }}
            >
              <Zap size={16} />
              <span>الاختبارات والكويزات</span>
            </button>

            <button
              onClick={() => setActiveContentTab("books")}
              style={{
                padding: "10px 20px",
                borderRadius: "10px",
                border: activeContentTab === "books" ? "2px solid #059669" : "1px solid var(--border-color)",
                background: activeContentTab === "books" ? "#0f392b" : "var(--bg-surface-secondary)",
                color: activeContentTab === "books" ? "#ffffff" : "var(--text-muted)",
                fontSize: "13.5px",
                fontWeight: 800,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.15s ease",
              }}
            >
              <Book size={16} />
              <span>كتبي والمذكرات المشتراة</span>
            </button>
          </div>

          {/* Dedicated Search Box (Left side in RTL - Exact place circled in Image 2) */}
          <div style={{ display: "flex", alignItems: "center", minWidth: "260px", maxWidth: "380px", flex: "1 1 260px" }}>
            <div style={{ position: "relative", width: "100%", display: "flex", alignItems: "center" }}>
              <Search
                size={16}
                style={{
                  position: "absolute",
                  insetInlineStart: "12px",
                  color: "var(--text-muted)",
                  pointerEvents: "none",
                }}
              />
              <input
                type="text"
                value={courseSearchQuery}
                onChange={(e) => setCourseSearchQuery(e.target.value)}
                placeholder={
                  activeContentTab === "lessons" ? "بحث في شروحات ودروس المقرر…" :
                  activeContentTab === "revisions" ? "بحث في ورش ومراجعات المقرر…" :
                  activeContentTab === "assignments" ? "بحث في الواجبات والتكليفات…" :
                  activeContentTab === "quizzes" ? "بحث في الاختبارات والكويزات…" :
                  "بحث في الكتب والمذكرات المشتراة…"
                }
                style={{
                  width: "100%",
                  padding: "9px 36px 9px 36px",
                  borderRadius: "10px",
                  border: "1.5px solid var(--border-color)",
                  background: "var(--bg-surface-secondary)",
                  color: "var(--text-main)",
                  fontSize: "13px",
                  fontWeight: 600,
                  outline: "none",
                  transition: "all 0.15s ease",
                  boxSizing: "border-box",
                }}
              />
              {courseSearchQuery && (
                <button
                  type="button"
                  onClick={() => setCourseSearchQuery("")}
                  style={{
                    position: "absolute",
                    insetInlineEnd: "10px",
                    background: "transparent",
                    border: "none",
                    color: "var(--text-muted)",
                    cursor: "pointer",
                    padding: "2px",
                    display: "flex",
                    alignItems: "center",
                  }}
                  title="مسح البحث"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          SECTION 1: LESSONS GRID (في شكل بطاقات زي المقررات)
         ========================================================================= */}
      {activeContentTab === "lessons" && (
        <div>
          {courseLessons.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
              <VideoOff size={40} style={{ color: "var(--text-muted)", margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>غير متوفر الآن</h3>
              <p style={{ margin: "0 0 16px", color: "var(--text-muted)", fontSize: "13.5px" }}>
                لا توجد فيديوهات أو دروس مرفوعة في هذا المقرر حالياً.
              </p>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  padding: "10px 24px",
                  borderRadius: "10px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-muted)",
                  fontWeight: 800,
                  fontSize: "13.5px",
                }}
              >
                غير متوفر الآن
              </div>
            </div>
          ) : filteredLessons.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "50px 20px", textAlign: "center" }}>
              <Search size={36} style={{ color: "var(--text-muted)", margin: "0 auto 10px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد شروحات أو دروس تطابق «{courseSearchQuery}»
              </h3>
              <button
                type="button"
                onClick={() => setCourseSearchQuery("")}
                className="btn-secondary"
                style={{ marginTop: "10px", padding: "8px 16px", borderRadius: "8px", fontSize: "12.5px", fontWeight: 700 }}
              >
                مسح البحث
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))", gap: "20px" }}>
              {filteredLessons.map((lesson, idx) => {
                const isCompleted = completedLessonIds.includes(lesson.id);
                const price = Number(lesson.price || 0);
                const isPurchased =
                  !isStudent ||
                  Number(activeCourse?.price || 0) > 0 ||
                  price === 0 ||
                  purchasedLessonIds.includes(lesson.id) ||
                  localPurchasedIds.has(lesson.id);
                const isPending = pendingRequestLessonIds.has(lesson.id);
                const isRequesting = requestingLessonId === lesson.id;

                return (
                  <div
                    key={lesson.id}
                    style={{
                      background: "var(--bg-surface)",
                      border: isPurchased ? "1px solid var(--border-color)" : "1.5px dashed #059669",
                      borderRadius: "12px",
                      overflow: "hidden",
                      boxShadow: "none",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      transition: "transform 0.15s ease, box-shadow 0.15s ease",
                    }}
                  >
                    {/* Lesson Card Media Header */}
                    <div
                      onClick={() =>
                        isPurchased
                          ? setActiveLessonModal(lesson)
                          : isPending
                          ? toast({ message: "طلب إتاحة هذا الدرس قيد المراجعة لدى المعلم", tone: "info" })
                          : handleRequestAccess(lesson)
                      }
                      style={{
                        height: "150px",
                        background: isPurchased ? "#0f392b" : "#1e293b",
                        padding: "16px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        cursor: "pointer",
                        position: "relative",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: "11px", fontWeight: 800, background: "rgba(255,255,255,0.2)", color: "#ffffff", padding: "3px 8px", borderRadius: "6px", backdropFilter: "blur(4px)" }}>
                          الدرس {idx + 1}
                        </span>
                        <span style={{ fontSize: "11px", fontWeight: 800, background: "rgba(0,0,0,0.4)", color: "#ffffff", padding: "3px 8px", borderRadius: "6px" }}>
                          {lesson.durationFormatted}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <div style={{ width: "48px", height: "48px", borderRadius: "50%", background: "rgba(255,255,255,0.9)", color: "#0f392b", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {isPurchased ? (
                            <Play size={22} fill="#0f392b" style={{ marginInlineStart: "2px" }} />
                          ) : (
                            <Lock size={20} style={{ color: "#0f392b" }} />
                          )}
                        </div>
                      </div>

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: "11px", color: isPurchased ? "#a7f3d0" : "#fbbf24", fontWeight: 700 }}>
                          {isPurchased ? "فيديو شرح تفاعلي" : `درس مدفوع: ${price} ج.م`}
                        </span>
                        {isCompleted && (
                          <span style={{ fontSize: "11px", fontWeight: 800, color: "#10b981", background: "rgba(0,0,0,0.5)", padding: "2px 8px", borderRadius: "4px" }}>
                            تم الإنجاز
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Lesson Card Body */}
                    <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px", marginBottom: "6px" }}>
                          <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "var(--text-main)", lineHeight: "1.4" }}>
                            {lesson.title}
                          </h3>
                          {price > 0 && (
                            <span style={{ fontSize: "12px", fontWeight: 800, color: isPurchased ? "#059669" : "#d97706", background: isPurchased ? "var(--bg-accent)" : "rgba(217,119,6,0.1)", padding: "2px 8px", borderRadius: "6px", whiteSpace: "nowrap" }}>
                              {isPurchased ? "مشترك" : `${price} ج.م`}
                            </span>
                          )}
                        </div>
                        <p style={{ margin: "0 0 12px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: "1.5" }}>
                          {lesson.description || "شرح مبسط وتطبيقات عملية على مخرجات التعلم مع مذكرات وتلخيصات PDF."}
                        </p>
                      </div>

                      {/* Footer Actions */}
                      <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "12px", marginTop: "12px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                          ملفات ومذكرات: {lesson.materials?.length || 1}
                        </span>

                        {isPurchased ? (
                          <button
                            type="button"
                            onClick={() => setActiveLessonModal(lesson)}
                            className="btn-primary"
                            style={{ fontSize: "12px", padding: "7px 14px", gap: "6px" }}
                          >
                            <Play size={13} fill="currentColor" />
                            <span>مشاهدة الدرس</span>
                          </button>
                        ) : isPending ? (
                          <div
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "6px",
                              padding: "6px 12px",
                              borderRadius: "8px",
                              background: "rgba(217, 119, 6, 0.12)",
                              color: "#d97706",
                              fontSize: "12px",
                              fontWeight: 700,
                              border: "1px solid rgba(217, 119, 6, 0.3)",
                            }}
                          >
                            <Clock size={14} />
                            <span>قيد مراجعة المعلم</span>
                          </div>
                        ) : (
                          <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
                            <button
                              type="button"
                              onClick={() => handleRequestAccess(lesson)}
                              disabled={isRequesting}
                              style={{
                                fontSize: "12px",
                                padding: "7px 12px",
                                gap: "6px",
                                background: "#0284c7",
                                color: "#ffffff",
                                border: "none",
                                borderRadius: "8px",
                                cursor: isRequesting ? "not-allowed" : "pointer",
                                fontWeight: 700,
                                display: "inline-flex",
                                alignItems: "center",
                              }}
                            >
                              <BookOpen size={13} />
                              <span>{isRequesting ? "جاري الطلب..." : "طلب إتاحة الدرس"}</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => handleBuyLesson(lesson)}
                              className="btn-primary"
                              style={{ fontSize: "12px", padding: "7px 12px", gap: "6px", background: "#059669" }}
                            >
                              <ShoppingCart size={13} />
                              <span>شراء — {price} ج.م</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          SECTION 1.5: REVISIONS & WORKSHOPS GRID (المراجعات والورش المفعلة)
         ========================================================================= */}
      {activeContentTab === "revisions" && (
        <div>
          {filteredRevisionVideoLessons.length === 0 && purchasedRevisionIds.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
              <Zap size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد فيديوهات مراجعة أو معسكرات مفعلة حالياً
              </h3>
              <p style={{ margin: "0 0 18px", color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "480px", marginInline: "auto" }}>
                يمكنك متابعة شروحات المراجعات الدورية المنشورة من قبل المعلم أو تصفح ورش المراجعة ومعسكرات نصف العام والامتحانات من متجر المنصة.
              </p>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  padding: "10px 24px",
                  borderRadius: "10px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-muted)",
                  fontWeight: 800,
                  fontSize: "13.5px",
                }}
              >
                غير متوفر الآن
              </div>
            </div>
          ) : (
            <div>
              {/* Revision Video Lessons uploaded by Teacher */}
              {filteredRevisionVideoLessons.length > 0 && (
                <div style={{ marginBottom: purchasedRevisionIds.length > 0 ? "32px" : "0" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                    <Video size={20} style={{ color: "#059669" }} />
                    <h3 style={{ margin: 0, fontSize: "16.5px", fontWeight: 800, color: "var(--text-main)" }}>
                      فيديوهات المراجعة الشاملة ({filteredRevisionVideoLessons.length})
                    </h3>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 330px), 1fr))", gap: "20px" }}>
                    {filteredRevisionVideoLessons.map(({ lesson, course }) => (
                      <div
                        key={`rev_vid_${lesson.id}`}
                        className="course-card"
                        style={{
                          background: "var(--bg-surface)",
                          border: "2px solid #059669",
                          borderRadius: "18px",
                          overflow: "hidden",
                          display: "flex",
                          flexDirection: "column",
                          boxShadow: "var(--card-shadow)",
                        }}
                      >
                        {/* Header */}
                        <div style={{ background: "#0f392b", padding: "18px 20px", color: "white" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                            <span style={{ background: "#059669", padding: "3px 10px", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                              {lesson.unitTitle || "الوحدة الدراسية"}
                            </span>
                            <span style={{ fontSize: "11px", background: "rgba(255,255,255,0.18)", padding: "3px 8px", borderRadius: "6px", fontWeight: 700 }}>
                              فيديو مراجعة
                            </span>
                          </div>
                          <h3 style={{ margin: "4px 0 2px", fontSize: "15.5px", fontWeight: 800, lineHeight: 1.35 }}>
                            {lesson.title}
                          </h3>
                          <span style={{ fontSize: "11.5px", opacity: 0.85 }}>{course.title}</span>
                        </div>

                        {/* Content */}
                        <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                          <div>
                            {lesson.description && (
                              <p style={{ fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 14px" }}>
                                {lesson.description}
                              </p>
                            )}

                            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px", fontSize: "12px", color: "var(--text-muted)" }}>
                              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                <Clock size={14} style={{ color: "#059669" }} /> {lesson.durationFormatted || `${lesson.durationMinutes} دقيقة`}
                              </span>
                              {lesson.materials && lesson.materials.length > 0 && (
                                <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                  <BookOpen size={14} style={{ color: "#059669" }} /> {lesson.materials.length} مذكرات مرفقة
                                </span>
                              )}
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => setActiveLessonModal(lesson)}
                            className="btn-primary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              padding: "10px",
                              borderRadius: "10px",
                              fontWeight: 800,
                              fontSize: "13px",
                              gap: "6px",
                              background: "#059669",
                            }}
                          >
                            <Play size={15} fill="white" />
                            <span>مشاهدة فيديو المراجعة الآن</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 330px), 1fr))", gap: "20px" }}>
              {filteredRevisions
                .filter((r) => purchasedRevisionIds.includes(r.id))
                .map((rev) => (
                  <div
                    key={rev.id}
                    className="course-card"
                    style={{
                      background: "var(--bg-surface)",
                      border: "2px solid #059669",
                      borderRadius: "18px",
                      overflow: "hidden",
                      display: "flex",
                      flexDirection: "column",
                      boxShadow: "var(--card-shadow)",
                    }}
                  >
                    {/* Header */}
                    <div style={{ background: "#0f392b", padding: "20px", color: "white" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ background: "#059669", padding: "3px 10px", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                          ورشة مراجعة مفعلة
                        </span>
                        <span style={{ fontSize: "12px", opacity: 0.9 }}>{rev.workshopsCount} ورش عمل</span>
                      </div>
                      <h3 style={{ margin: "6px 0 2px", fontSize: "16px", fontWeight: 800, lineHeight: 1.35 }}>
                        {rev.title}
                      </h3>
                      <span style={{ fontSize: "11.5px", opacity: 0.85 }}>إشراف: {rev.teacherName}</span>
                    </div>

                    {/* Content */}
                    <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <p style={{ fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 14px" }}>
                          {rev.description}
                        </p>

                        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "14px", fontSize: "12px", color: "var(--text-muted)" }}>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Clock size={14} style={{ color: "#059669" }} /> {rev.durationFormatted}
                          </span>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Award size={14} style={{ color: "#059669" }} /> {rev.workshopsCount} ورش عمل
                          </span>
                        </div>

                        <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "16px" }}>
                          {rev.features?.map((feat: string, idx: number) => (
                            <div key={idx} style={{ fontSize: "11.5px", color: "var(--text-main)", display: "flex", alignItems: "center", gap: "6px" }}>
                              <CheckCircle2 size={13} style={{ color: "#059669" }} />
                              <span>{feat}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <button
                        onClick={() => toast({ message: `جاري فتح ورش ومحاضرات "${rev.title}"!`, tone: "info" })}
                        className="btn-primary"
                        style={{
                          width: "100%",
                          justifyContent: "center",
                          padding: "10px",
                          borderRadius: "10px",
                          fontWeight: 800,
                          fontSize: "13px",
                          gap: "6px",
                          background: "#047857",
                        }}
                      >
                        <Zap size={15} />
                        <span>فتح ورش المراجعة والبدء الآن</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          SECTION 2: ASSIGNMENTS GRID (في شكل بطاقات زي المقررات مع الـ Deadline)
         ========================================================================= */}
      {activeContentTab === "assignments" && filteredServerAssignments.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: "20px", marginBottom: "24px" }}>
          {filteredServerAssignments.map((asg) => (
            <div key={asg.id} style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", padding: "20px", boxShadow: "var(--card-shadow)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#92400e", background: "#fef3c7", padding: "3px 8px", borderRadius: "6px" }}>واجب منشور</span>
                {asg.maxScore != null && (
                  <span style={{ fontSize: "12px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>{asg.maxScore} درجة</span>
                )}
              </div>
              <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>{asg.title}</h3>
              <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "var(--text-muted)" }}>
                تابع للدرس: {asg.lessonId ? lessonTitleById.get(asg.lessonId) || "—" : "مقرر كامل"}
                {asg.dueLabel ? ` • آخر موعد: ${new Date(asg.dueLabel).toLocaleDateString("ar-EG")}` : ""}
              </p>
              {asg.accessible ? (
                <button
                  className="btn-primary"
                  style={{ width: "100%", justifyContent: "center", gap: 6 }}
                  onClick={() => void openServerAssignment(asg)}
                >
                  <FileCheck size={14} /> فتح الواجب وتسليم الحل
                </button>
              ) : (
                <button className="btn-primary" style={{ width: "100%", justifyContent: "center", gap: 6 }} onClick={() => { const lesson = (currentCourse?.lessons || []).find((l) => l.id === asg.lessonId); if (lesson) handleBuyLesson(lesson); }}>
                  <Lock size={14} /> اشترِ الدرس لحل الواجب
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {activeContentTab === "assignments" && (
        courseAssignments.length === 0 && serverAssignments.length === 0 ? (
          <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
            <FileText size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
            <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
              لا توجد واجبات أو تكليفات مطلوبة حالياً
            </h3>
            <p style={{ margin: "0 0 18px", color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "480px", marginInline: "auto" }}>
              سيتم إدراج الواجبات والتكليفات المنزلية هنا فور تعيينها ونشرها من قبل المعلم.
            </p>
            {isTeacher && (
              <>
                <button className="btn-primary" onClick={() => setShowManualAssignmentForm(true)}>
                  <Plus size={16} />
                  <span>إنشاء واجب يدوياً</span>
                </button>
                {showManualAssignmentForm && (
                  <div style={{ marginTop: 18, background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: 16, padding: 18, textAlign: "right", maxWidth: 520, marginInline: "auto" }}>
                    <h4 style={{ margin: "0 0 10px", fontSize: 15, fontWeight: 800 }}>إنشاء واجب جديد</h4>
                    <input placeholder="عنوان الواجب" value={manualAssignmentTitle} onChange={(e) => setManualAssignmentTitle(e.target.value)} style={{ width: "100%", marginBottom: 8, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border-color)", background: "var(--bg-surface)" }} />
                    <textarea placeholder="تعليمات الواجب والمواد المطلوبة" value={manualAssignmentPrompt} onChange={(e) => setManualAssignmentPrompt(e.target.value)} rows={4} style={{ width: "100%", marginBottom: 10, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border-color)", background: "var(--bg-surface)" }} />
                    <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                      <button className="btn-secondary" onClick={() => setShowManualAssignmentForm(false)}>إلغاء</button>
                      <button className="btn-primary" disabled={manualCreationLoading || !manualAssignmentTitle.trim() || !manualAssignmentPrompt.trim()} onClick={async () => {
                        setManualCreationLoading(true);
                        try {
                          const data = await apiRequest<{ message?: string }>("/manual/assignments", { method: "POST", body: JSON.stringify({ course_id: currentCourse.id, title: manualAssignmentTitle, prompt: manualAssignmentPrompt, max_score: 100 }) });
                          toast({ message: data.message || "تم إنشاء الواجب", tone: "success" });
                          setShowManualAssignmentForm(false);
                          setManualAssignmentTitle("");
                          setManualAssignmentPrompt("");
                        } catch { toast({ message: "تعذر إنشاء الواجب", tone: "danger" }); }
                        setManualCreationLoading(false);
                      }}>حفظ</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: "20px" }}>
            {filteredAssignments.map((asg) => {
              const isSubmitted = !!submittedAssignmentIds[asg.id];
              const timeInfo = getTimeStatus(asg.availableFrom, asg.dueDate, isSubmitted);

              return (
                <div
                  key={asg.id}
                  style={{
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "16px",
                    padding: "20px",
                    boxShadow: "var(--card-shadow)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    transition: "transform 0.15s ease",
                  }}
                >
                  <div>
                    {/* Top Badge & Points */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 800, color: "#1e3a8a", background: "#dbeafe", padding: "3px 8px", borderRadius: "6px" }}>
                        واجب وتكليف منزلي
                      </span>
                      <span style={{ fontSize: "12px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px", border: "1px solid var(--border-accent)" }}>
                        {asg.maxScore} درجة
                      </span>
                    </div>

                    <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)", lineHeight: "1.4" }}>
                      {asg.title}
                    </h3>

                    <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: "1.5" }}>
                      {asg.description}
                    </p>

                    {/* Timing & Deadline Badge */}
                    <div
                      style={{
                        padding: "8px 12px",
                        background: timeInfo.bg,
                        color: timeInfo.color,
                        border: `1px solid ${timeInfo.border}`,
                        borderRadius: "8px",
                        fontSize: "11.5px",
                        fontWeight: 800,
                        marginBottom: "14px",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Clock size={14} />
                      <span>{timeInfo.label}</span>
                    </div>
                  </div>

                  {/* Footer Action */}
                  <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                      {asg.attachments?.length ? `مرفق: ${asg.attachments[0].name}` : "نموذج إلكتروني"}
                    </span>

                    <button
                      type="button"
                      onClick={() => {
                        if (!timeInfo.canOpen) {
                          toast({ message: `تنبيه: هذا الواجب ${timeInfo.status === "locked" ? `لم يفتح بعد، موعد البدء هو: ${asg.availableFrom}` : `انتهى موعد تسليمه النهائي في: ${asg.dueDate}`}`, tone: "warning" });
                          return;
                        }
                        setActiveAssignmentModal(asg);
                      }}
                      style={{
                        padding: "8px 16px",
                        borderRadius: "8px",
                        border: "none",
                        background: isSubmitted ? "#166534" : (timeInfo.status === "open" ? "#0f392b" : "#94a3b8"),
                        color: "#ffffff",
                        fontSize: "12.5px",
                        fontWeight: 800,
                        cursor: timeInfo.canOpen ? "pointer" : "not-allowed",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      {isSubmitted ? (
                        <>
                          <CheckCircle2 size={14} />
                          <span>عرض الإجابة والدرجة</span>
                        </>
                      ) : timeInfo.status === "open" ? (
                        <>
                          <FileCheck size={14} />
                          <span>حل وتسليم الواجب</span>
                        </>
                      ) : (
                        <>
                          <Lock size={14} />
                          <span>مغلق</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}

      {/* =========================================================================
          SECTION 3: QUIZZES GRID (في شكل بطاقات زي المقررات مع الـ Deadline)
         ========================================================================= */}
      {activeContentTab === "quizzes" && filteredServerQuizzes.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: "20px", marginBottom: "24px" }}>
          {filteredServerQuizzes.map((qz) => (
            <div key={qz.id} style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", padding: "20px", boxShadow: "var(--card-shadow)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#831843", background: "#fce7f3", padding: "3px 8px", borderRadius: "6px" }}>كويز تقييمي تفاعلي</span>
                  {qz.durationMinutes != null && (
                    <span style={{ fontSize: "12px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>{qz.durationMinutes} دقيقة</span>
                  )}
                </div>
                <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)", lineHeight: 1.4 }}>{qz.title}</h3>
                <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5 }}>
                  تابع للدرس: {qz.lessonId ? lessonTitleById.get(qz.lessonId) || "—" : "مقرر كامل"}
                  {qz.dueLabel ? ` • متاح حتى ${new Date(qz.dueLabel).toLocaleDateString("ar-EG")}` : ""}
                </p>
              </div>
              {qz.accessible && (qz.attemptsAllowed == null || (qz.attemptsUsed ?? 0) < qz.attemptsAllowed) ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", position: "relative" }}>
                  {(qz.attemptsUsed ?? 0) > 0 && (
                    <span
                      title="تم حل هذا الاختبار"
                      style={{
                        position: "absolute", top: "-10px", insetInlineEnd: "-8px", zIndex: 2,
                        width: "22px", height: "22px", borderRadius: "50%",
                        background: "#059669", color: "#ffffff",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        border: "2px solid var(--bg-surface, #fff)", boxShadow: "0 2px 6px rgba(5,150,105,0.4)",
                      }}
                    >
                      <CheckCircle2 size={14} />
                    </span>
                  )}
                  <button
                    className="btn-primary"
                    style={{ width: "100%", justifyContent: "center", gap: 6 }}
                    onClick={() => void openServerQuiz(qz)}
                  >
                    <Play size={14} /> بدء حل الاختبار
                  </button>
                  {(qz.attemptsUsed ?? 0) > 0 && (
                    (qz.attemptsUsed ?? 0) > 1 ? (
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ flex: 1, justifyContent: "center", gap: 6, borderColor: "#059669", color: "#059669" }}
                          onClick={() => void openQuizResultPage(qz.id)}
                          title="عرض تصحيح أحدث محاولة"
                        >
                          <Award size={14} /> عرض النتيجة والتصحيح
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ padding: "0 11px", justifyContent: "center", gap: 5, borderColor: "#059669", color: "#059669", fontWeight: 800, fontSize: "12px", flexShrink: 0 }}
                          onClick={() => void openQuizHistoryModal(qz)}
                          title="سجل كل المرات التي امتحنت فيها لاختيار أي محاولة ورؤية غلطاتك فيها"
                        >
                          <History size={14} />
                          <span>السجل ({qz.attemptsUsed})</span>
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ width: "100%", justifyContent: "center", gap: 6, borderColor: "#059669", color: "#059669" }}
                        onClick={() => void openQuizResultPage(qz.id)}
                      >
                        <Award size={14} /> عرض النتيجة والتصحيح
                      </button>
                    )
                  )}
                </div>
              ) : qz.accessible && qz.attemptsAllowed != null && (qz.attemptsUsed ?? 0) >= qz.attemptsAllowed ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", position: "relative" }}>
                  <span
                    title="تم حل هذا الاختبار"
                    style={{
                      position: "absolute", top: "-10px", insetInlineEnd: "-8px", zIndex: 2,
                      width: "22px", height: "22px", borderRadius: "50%",
                      background: "#059669", color: "#ffffff",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      border: "2px solid var(--bg-surface, #fff)", boxShadow: "0 2px 6px rgba(5,150,105,0.4)",
                    }}
                  >
                    <CheckCircle2 size={14} />
                  </span>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ width: "100%", justifyContent: "center", gap: 6, borderColor: "#059669", color: "#059669" }}
                    onClick={() => void openServerQuiz(qz)}
                    title="محاولات تدريبية إضافية تُصحح لك فوراً لكن لا تصل للمعلم ولا تُحسب في الدرجات"
                  >
                    <BookOpen size={14} /> امتحن نفسك (تدريب — لا يُرسل للمعلم)
                  </button>
                  {(qz.attemptsUsed ?? 0) > 1 ? (
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        className="btn-primary"
                        style={{ flex: 1, justifyContent: "center", gap: 6 }}
                        onClick={() => void openQuizResultPage(qz.id)}
                        title="عرض تصحيح أحدث محاولة"
                      >
                        <Award size={14} /> عرض النتيجة والتصحيح
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ padding: "0 11px", justifyContent: "center", gap: 5, borderColor: "#059669", color: "#059669", fontWeight: 800, fontSize: "12px", flexShrink: 0 }}
                        onClick={() => void openQuizHistoryModal(qz)}
                        title="سجل كل المرات التي امتحنت فيها لاختيار أي محاولة ورؤية غلطاتك فيها"
                      >
                        <History size={14} />
                        <span>السجل ({qz.attemptsUsed})</span>
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ width: "100%", justifyContent: "center", gap: 6 }}
                      onClick={() => void openQuizResultPage(qz.id)}
                    >
                      <Award size={14} /> عرض النتيجة والتصحيح
                    </button>
                  )}
                </div>
              ) : (
                <button className="btn-primary" style={{ width: "100%", justifyContent: "center", gap: 6 }} onClick={() => { const lesson = (currentCourse?.lessons || []).find((l) => l.id === qz.lessonId); if (lesson) handleBuyLesson(lesson); }}>
                  <Lock size={14} /> اشترِ الدرس لفتح الكويز
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {activeContentTab === "quizzes" && (
        courseQuizzes.length === 0 && serverQuizzes.length === 0 ? (
          <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
            <HelpCircle size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
            <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
              لا توجد اختبارات أو كويزات تقييمية حالياً
            </h3>
            <p style={{ margin: "0 0 18px", color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "480px", marginInline: "auto" }}>
              سيتم إتاحة الاختبارات التقييمية الإلكترونية هنا فور جدولتها ونشرها من قبل المعلم.
            </p>
            {isTeacher && (
              <>
                <button className="btn-primary" onClick={() => setShowManualQuizForm(true)}>
                  <Plus size={16} />
                  <span>إنشاء كويز يدوياً</span>
                </button>
                {showManualQuizForm && (
                  <div style={{ marginTop: 18, background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: 16, padding: 18, textAlign: "right", maxWidth: 520, marginInline: "auto" }}>
                    <h4 style={{ margin: "0 0 10px", fontSize: 15, fontWeight: 800 }}>إنشاء كويز جديد</h4>
                    <input placeholder="عنوان الكويز" value={manualQuizTitle} onChange={(e) => setManualQuizTitle(e.target.value)} style={{ width: "100%", marginBottom: 8, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border-color)", background: "var(--bg-surface)" }} />
                    <textarea placeholder="السؤال الرئيسي أو موضوع الكويز" value={manualQuizQuestion} onChange={(e) => setManualQuizQuestion(e.target.value)} rows={4} style={{ width: "100%", marginBottom: 10, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border-color)", background: "var(--bg-surface)" }} />
                    <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                      <button className="btn-secondary" onClick={() => setShowManualQuizForm(false)}>إلغاء</button>
                      <button className="btn-primary" disabled={manualCreationLoading || !manualQuizTitle.trim() || !manualQuizQuestion.trim()} onClick={async () => {
                        setManualCreationLoading(true);
                        try {
                          const data = await apiRequest<{ message?: string }>("/manual/quizzes", { method: "POST", body: JSON.stringify({ course_id: currentCourse.id, title: manualQuizTitle, question_text: manualQuizQuestion, max_score: 10 }) });
                          toast({ message: data.message || "تم إنشاء الكويز", tone: "success" });
                          setShowManualQuizForm(false);
                          setManualQuizTitle("");
                          setManualQuizQuestion("");
                        } catch { toast({ message: "تعذر إنشاء الكويز", tone: "danger" }); }
                        setManualCreationLoading(false);
                      }}>حفظ</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: "20px" }}>
            {filteredQuizzes.map((quiz) => {
              const isCompleted = !!completedQuizzes[quiz.id];
              const timeInfo = getTimeStatus(quiz.availableFrom, quiz.dueDate, isCompleted);
              const userScore = completedQuizzes[quiz.id]?.score;

              return (
                <div
                  key={quiz.id}
                  style={{
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "16px",
                    padding: "20px",
                    boxShadow: "var(--card-shadow)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    transition: "transform 0.15s ease",
                  }}
                >
                  <div>
                    {/* Top Badge & Duration */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 800, color: "#831843", background: "#fce7f3", padding: "3px 8px", borderRadius: "6px" }}>
                        كويز تقييمي تفاعلي
                      </span>
                      <span style={{ fontSize: "12px", fontWeight: 800, color: "#059669", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px", border: "1px solid var(--border-accent)" }}>
                        {quiz.maxScore} درجات • {quiz.durationMinutes} دقيقة
                      </span>
                    </div>

                    <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)", lineHeight: "1.4" }}>
                      {quiz.title}
                    </h3>

                    <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: "1.5" }}>
                      {quiz.description}
                    </p>

                    {/* Timing & Deadline Badge */}
                    <div
                      style={{
                        padding: "8px 12px",
                        background: timeInfo.bg,
                        color: timeInfo.color,
                        border: `1px solid ${timeInfo.border}`,
                        borderRadius: "8px",
                        fontSize: "11.5px",
                        fontWeight: 800,
                        marginBottom: "14px",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Timer size={14} />
                      <span>{timeInfo.label}</span>
                    </div>
                  </div>

                  {/* Footer Action */}
                  <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                      {quiz.questions.length} أسئلة اختيارية ومقالية
                    </span>

                    <button
                      type="button"
                      onClick={() => {
                        if (!timeInfo.canOpen) {
                          toast({ message: `تنبيه: هذا الكويز ${timeInfo.status === "locked" ? `لم يبدأ بعد، موعد البدء هو: ${quiz.availableFrom}` : `انتهى موعده في: ${quiz.dueDate}`}`, tone: "warning" });
                          return;
                        }
                        setActiveQuizModal(quiz);
                        setQuizAnswers({});
                        setQuizSubmitted(isCompleted);
                        setQuizScoreResult(isCompleted ? { score: userScore || quiz.maxScore, maxScore: quiz.maxScore } : null);
                      }}
                      style={{
                        padding: "8px 16px",
                        borderRadius: "8px",
                        border: "none",
                        background: isCompleted ? "#166534" : (timeInfo.status === "open" ? "#0f392b" : "#94a3b8"),
                        color: "#ffffff",
                        fontSize: "12.5px",
                        fontWeight: 800,
                        cursor: timeInfo.canOpen ? "pointer" : "not-allowed",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      {isCompleted ? (
                        <>
                          <CheckCircle2 size={14} />
                          <span>مراجعة النتيجة: {userScore}/{quiz.maxScore}</span>
                        </>
                      ) : timeInfo.status === "open" ? (
                        <>
                          <Zap size={14} />
                          <span>ابدأ الاختبار الآن</span>
                        </>
                      ) : (
                        <>
                          <Lock size={14} />
                          <span>مغلق</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}

      {/* =========================================================================
          SECTION 4: BOOKS & NOTES GRID (الكتب والمذكرات المشتراة)
         ========================================================================= */}
      {activeContentTab === "books" && (
        <div>
          {allPurchasedBooks.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
              <Book size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد كتب أو مذكرات مشتراة حتى الآن
              </h3>
              <p style={{ margin: "0 0 18px", color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "480px", marginInline: "auto" }}>
                يمكنك تصفح وشراء كتب الشرح المعتمدة، بنوك الأسئلة، ومذكرات ليلة الامتحان من متجر المنصة، كما تظهر هنا المذكرات والملفات المرفقة مع الفيديوهات المشتراة تلقائياً.
              </p>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  padding: "10px 24px",
                  borderRadius: "10px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-muted)",
                  fontWeight: 800,
                  fontSize: "13.5px",
                }}
              >
                غير متوفر الآن
              </div>
            </div>
          ) : filteredBooks.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "50px 20px", textAlign: "center" }}>
              <Search size={36} style={{ color: "var(--text-muted)", margin: "0 auto 10px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد كتب أو مذكرات تطابق «{courseSearchQuery}»
              </h3>
              <button
                type="button"
                onClick={() => setCourseSearchQuery("")}
                className="btn-secondary"
                style={{ marginTop: "10px", padding: "8px 16px", borderRadius: "8px", fontSize: "12.5px", fontWeight: 700 }}
              >
                مسح البحث
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))", gap: "20px" }}>
              {filteredBooks.map((book) => (
                <div
                  key={book.id}
                  className="course-card"
                  style={{
                    background: "var(--bg-surface)",
                    border: "2px solid #059669",
                    borderRadius: "18px",
                    overflow: "hidden",
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "var(--card-shadow)",
                  }}
                >
                  {/* Header */}
                  <div style={{ background: book.gradient, padding: "20px", color: "#ffffff" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span style={{ background: "rgba(255,255,255,0.2)", color: "#ffffff", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                        {book.isLessonMaterial ? "مذكرة درس مرفقة" : "نسخة مملوكة ومفعلة"}
                      </span>
                      <span style={{ fontSize: "12px", opacity: 0.95, color: "#ffffff" }}>
                        {book.fileSize ? book.fileSize : `${book.pagesCount} صفحة`}
                      </span>
                    </div>
                    <h3 style={{ margin: "4px 0", fontSize: "16px", fontWeight: 800, lineHeight: 1.3, color: "#ffffff" }}>
                      {book.title}
                    </h3>
                    <span style={{ fontSize: "11.5px", opacity: 0.9, color: "#ffffff" }}>إعداد: {book.author}</span>
                  </div>

                  {/* Content */}
                  <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                    <div>
                      <p style={{ fontSize: "13px", color: "var(--text-main, #0f172a)", fontWeight: 700, lineHeight: 1.6, margin: "0 0 14px" }}>
                        {book.description}
                      </p>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "16px" }}>
                        {book.sampleTopics?.map((top: string, idx: number) => (
                          <span key={idx} style={{ fontSize: "11px", background: "#047857", color: "#ffffff", padding: "3px 8px", borderRadius: "6px", fontWeight: 700 }}>
                            {top}
                          </span>
                        ))}
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        if (book.fileUrl) {
                          void downloadLessonMaterial(book.fileUrl, book.title);
                        } else {
                          setActiveBookModal(book);
                        }
                      }}
                      className="btn-primary"
                      style={{
                        width: "100%",
                        justifyContent: "center",
                        padding: "10px",
                        borderRadius: "10px",
                        fontWeight: 800,
                        fontSize: "13px",
                        gap: "6px",
                        background: "#047857",
                        color: "#ffffff",
                      }}
                    >
                      <Download size={15} />
                      <span>{book.fileUrl ? "تحميل المذكرة - PDF" : "فتح وتحميل الكتاب - PDF"}</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          STANDALONE PAGE A: SERVER QUIZ SOLVING — site topbar + one question
          at a time with a question-map sidebar, flagging and submit.
         ========================================================================= */}
      {(serverQuiz || serverQuizLoading || serverQuizError) && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "var(--bg-primary, #f8fafc)",
            zIndex: 100000,
            overflowY: "auto",
          }}
        >
          {/* Unified Quiz Header (Exact match to Image 3 with Sidebar, Logo, Theme, Lang, and Exit) */}
          <header
            style={{
              height: "68px",
              background: "var(--bg-surface, #ffffff)",
              borderBottom: "1px solid var(--border-color)",
              padding: "0 24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "14px",
              position: "sticky",
              top: 0,
              zIndex: 100,
              boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
              boxSizing: "border-box",
            }}
          >
            {/* Right side (RTL Start): Sidebar menu, Logo, Quiz Title, Points */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
              <button
                type="button"
                className="icon-btn"
                onClick={onToggleMenu}
                aria-label={menuOpen ? "Close Menu" : "Open Menu"}
                title={lang === "ar" ? "القائمة الجانبية" : "Sidebar Menu"}
              >
                {menuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>

              <div
                onClick={handleHeaderNavigateHome}
                role="button"
                tabIndex={0}
                title={lang === "ar" ? "العودة إلى الصفحة الأولى" : "Go to Home"}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  cursor: "pointer",
                  userSelect: "none",
                }}
              >
                <div
                  className="brand-mark"
                  style={{
                    width: "34px",
                    height: "34px",
                    borderRadius: "9px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <GraduationCap size={18} />
                </div>
              </div>

              <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 900, color: "var(--text-main)", whiteSpace: "nowrap" }}>
                {serverQuiz?.title || (serverQuizLoading ? "جاري التحميل…" : "اختبار")}
              </h2>

              {serverQuiz && !serverQuizResult && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontSize: "11.5px", fontWeight: 900, color: "#059669", background: "var(--bg-accent)", border: "1px solid var(--border-accent)", padding: "4px 11px", borderRadius: "999px", flexShrink: 0 }}>
                  <CheckCircle2 size={12} />
                  {Number(serverQuiz.totalPoints || 0)} درجة • {serverQuiz.questions.length} أسئلة
                </span>
              )}
            </div>

            {/* Left side (RTL End): Theme, Lang, Practice badge, Question count, Timer, Exit */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
              <button
                type="button"
                className="icon-btn"
                onClick={onToggleTheme}
                title={theme === "dark" ? "تفعيل الوضع النهاري" : "تفعيل الوضع الليلي"}
                aria-label="Toggle Theme"
              >
                {theme === "dark" ? <Sun size={18} style={{ color: "#f59e0b" }} /> : <Moon size={18} />}
              </button>

              <button
                type="button"
                className="icon-btn"
                onClick={onToggleLang}
                title="Switch Language / تغيير اللغة"
                style={{ width: "auto", minWidth: "42px", padding: "0 8px", fontSize: "11.5px", fontWeight: 800 }}
              >
                <span>{lang === "ar" ? "AR" : "EN"}</span>
              </button>

              {serverQuizAttempt?.isPractice && (
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#92400e", background: "#fef3c7", padding: "4px 10px", borderRadius: "8px" }}>
                  محاولة تدريبية — لن تصل للمعلم
                </span>
              )}

              {serverQuiz && !serverQuizResult && (
                <span style={{ fontSize: "13px", fontWeight: 800, color: "var(--text-main)", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <Timer size={15} style={{ color: "var(--text-main)" }} /> السؤال {Math.min(serverQuizQuestionIndex + 1, serverQuiz.questions.length)} من {serverQuiz.questions.length}
                </span>
              )}

              {serverQuizRemaining !== null && !serverQuizResult && (
                <div className="quiz-timer-pill">
                  <span style={{ width: "9px", height: "9px", borderRadius: "50%", background: "#ef4444", display: "inline-block", flexShrink: 0 }} />
                  <span style={{ fontWeight: 900, letterSpacing: "0.5px" }}>
                    {Math.floor(serverQuizRemaining / 60)}:{String(serverQuizRemaining % 60).padStart(2, "0")}
                  </span>
                </div>
              )}

              <button
                type="button"
                onClick={() => {
                  closeOverlay("serverQuiz", () => {
                    setServerQuiz(null);
                    setServerQuizError(null);
                  });
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "7px 14px",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  color: "var(--text-main)",
                  cursor: "pointer",
                  flexShrink: 0,
                  transition: "all 0.15s ease",
                }}
              >
                <X size={15} />
                <span>خروج</span>
              </button>
            </div>
          </header>

          {/* Body: question-map sidebar + one-question card */}
          <div
            style={{
              maxWidth: "1200px",
              margin: "0 auto",
              padding: "26px 20px 60px",
              display: "flex",
              gap: "24px",
              alignItems: "flex-start",
              flexDirection: "row-reverse",
            }}
          >
            {/* Sidebar: question map + submit */}
            <div style={{ width: "280px", flexShrink: 0, display: "flex", flexDirection: "column", gap: "16px", position: "sticky", top: "84px" }}>
              <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", padding: "20px 18px" }}>
                <h3 style={{ margin: "0 0 16px", fontSize: "15px", fontWeight: 900, color: "var(--text-main)", textAlign: "center" }}>خريطة أسئلة الاختبار</h3>
                <div style={{ display: "flex", justifyContent: "center", gap: "14px", flexWrap: "wrap", direction: "rtl", marginBottom: "16px" }}>
                  {serverQuiz?.questions.map((q, qIdx) => {
                    const answered = Boolean(serverQuizAnswers[q.id]);
                    const flagged = serverQuizFlagged[q.id];
                    const isCurrent = qIdx === serverQuizQuestionIndex;
                    return (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() => setServerQuizQuestionIndex(qIdx)}
                        title={answered ? "مُجاب" : flagged ? "مُعلّم للمراجعة" : "لم يُجاب بعد"}
                        style={{
                          width: "44px",
                          height: "44px",
                          borderRadius: "50%",
                          border: isCurrent
                            ? "2px solid #059669"
                            : answered
                            ? "1.5px solid #059669"
                            : "1px solid var(--border-color)",
                          background: answered
                            ? "#059669"
                            : "var(--bg-surface)",
                          color: answered ? "#ffffff" : isCurrent ? "#059669" : "var(--text-main)",
                          fontSize: "15px",
                          fontWeight: 800,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          position: "relative",
                          transition: "all 0.15s ease",
                        }}
                      >
                        {qIdx + 1}
                        {flagged && !answered && (
                          <span style={{ position: "absolute", top: "-2px", insetInlineStart: "-2px", width: "10px", height: "10px", borderRadius: "50%", background: "#f59e0b", border: "1.5px solid var(--bg-surface)" }} />
                        )}
                      </button>
                    );
                  })}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "8px", paddingTop: "14px", borderTop: "1px solid var(--border-color)", fontSize: "12px", color: "var(--text-main)", fontWeight: 700 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}><span style={{ width: "11px", height: "11px", borderRadius: "50%", background: "#059669", display: "inline-block" }} /> تم الإجابة</span>
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}><span style={{ width: "11px", height: "11px", borderRadius: "50%", border: "2px solid #059669", background: "transparent", display: "inline-block" }} /> الحالي</span>
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}><span style={{ width: "11px", height: "11px", borderRadius: "50%", border: "1px solid var(--border-color)", background: "transparent", display: "inline-block" }} /> لم يتم الإجابة</span>
                </div>
              </div>

              {!serverQuizResult && (
                <>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => setShowQuizSubmitConfirm(true)}
                    disabled={serverQuizSubmitting || serverQuizRemaining === 0}
                    style={{ width: "100%", justifyContent: "center", gap: "7px", padding: "13px" }}
                  >
                    <CheckCircle2 size={17} />
                    <span>{serverQuizRemaining === 0 ? "انتهى الوقت" : serverQuizSubmitting ? "جاري التصحيح…" : "تسليم الاختبار"}</span>
                  </button>
                  {serverQuiz && Object.keys(serverQuizAnswers).length < serverQuiz.questions.length && (
                    <p style={{ margin: 0, fontSize: "11.5px", color: "var(--text-muted)", textAlign: "center" }}>
                      متبقي {serverQuiz.questions.length - Object.keys(serverQuizAnswers).length} أسئلة دون إجابة (يمكنك التسليم أو الإكمال)
                    </p>
                  )}
                </>
              )}
            </div>

            {/* Main card: the current question only */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {serverQuizLoading && <div style={{ padding: "60px", textAlign: "center", color: "var(--text-muted)" }}>جاري تحميل أسئلة الاختبار…</div>}

              {serverQuizError && (
                <div style={{ padding: "16px", background: "#fee2e2", color: "#b91c1c", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px" }}>
                  {serverQuizError}
                </div>
              )}

              {serverQuizResult && (
                <div style={{ background: "var(--bg-surface, #fff)", border: "1.5px solid #86efac", borderRadius: "16px", padding: "26px", boxShadow: "var(--card-shadow)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "18px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <Sparkles size={28} style={{ color: "#059669" }} />
                      <div>
                        <strong style={{ fontSize: "16px", color: "var(--text-main)", display: "block" }}>تم تسليم الاختبار وتصحيحه فورياً</strong>
                        <span style={{ fontSize: "12.5px", color: "var(--text-muted)" }}>
                          {serverQuizAttempt?.isPractice
                            ? `المحاولة رقم ${serverQuizResult.attemptNumber} — تدريبية: ظهرت لك فقط ولن تصل للمعلم أو كشف الدرجات.`
                            : `المحاولة رقم ${serverQuizResult.attemptNumber} — النتيجة مسجلة في كشف الدرجات.`}
                        </span>
                      </div>
                    </div>
                    <div style={{ fontSize: "26px", fontWeight: 900, color: "#059669" }}>
                      {serverQuizResult.score} / {serverQuizResult.total} درجة
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginTop: "16px" }}>
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ flex: 1, minWidth: "220px", justifyContent: "center", gap: "8px", padding: "12px 20px", fontSize: "14px", fontWeight: 800 }}
                      onClick={() => {
                        const qId = serverQuiz?.quizId;
                        const attId = serverQuizResult.attemptId;
                        overlayHistoryStack.current = overlayHistoryStack.current.map((item) => (item === "serverQuiz" ? "quizResultPage" : item));
                        window.history.replaceState({ lmsOverlay: "quizResultPage" }, "");
                        setServerQuiz(null);
                        setServerQuizError(null);
                        if (qId) void openQuizResultPage(qId, attId);
                      }}
                    >
                      <Eye size={17} />
                      <span>عرض تصحيح هذه المحاولة والأخطاء</span>
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ flex: 1, minWidth: "160px", justifyContent: "center", gap: "6px", padding: "12px 18px", fontSize: "14px", fontWeight: 800 }}
                      onClick={() => {
                        closeOverlay("serverQuiz", () => {
                          setServerQuiz(null);
                          setServerQuizError(null);
                        });
                      }}
                    >
                      العودة إلى المقرر
                    </button>
                  </div>
                </div>
              )}

              {serverQuiz && !serverQuizResult && serverQuiz.questions[serverQuizQuestionIndex] && (() => {
                const q = serverQuiz.questions[serverQuizQuestionIndex];
                const opts = q.options || [];
                const isMcq = Array.isArray(opts) && opts.length > 0;
                const flagged = Boolean(serverQuizFlagged[q.id]);
                return (
                  <div style={{ background: "var(--bg-surface, #ffffff)", border: "1px solid var(--border-color)", borderRadius: "16px", padding: "26px", boxShadow: "var(--card-shadow)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                      <span style={{ fontSize: "12px", fontWeight: 900, color: "#059669", background: "var(--bg-accent)", padding: "4px 12px", borderRadius: "8px" }}>
                        السؤال {ORDINAL_AR[serverQuizQuestionIndex] || serverQuizQuestionIndex + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => setServerQuizFlagged({ ...serverQuizFlagged, [q.id]: !flagged })}
                        style={{
                          display: "inline-flex", alignItems: "center", gap: "5px",
                          background: flagged ? "#fef3c7" : "transparent",
                          border: "none", cursor: "pointer", fontSize: "12px", fontWeight: 800,
                          color: flagged ? "#92400e" : "var(--text-muted)", borderRadius: "8px", padding: "5px 10px",
                        }}
                        title="تعليم السؤال للمراجعة لاحقاً"
                      >
                        <Flag size={14} /> {flagged ? "مُعلّم للمراجعة" : "تعليم السؤال للمراجعة لاحقاً"}
                      </button>
                    </div>

                    <div style={{ fontSize: "15.5px", color: "var(--text-main)", lineHeight: "1.8", fontWeight: 700, marginBottom: "20px" }}>
                      <FormulaRenderer text={q.prompt} />
                      <span style={{ marginInlineStart: "10px", fontSize: "11.5px", fontWeight: 800, color: "var(--text-muted)" }}>({q.points} درجة)</span>
                    </div>

                    {isMcq ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {opts.map((opt, optIdx) => {
                          const chosen = serverQuizAnswers[q.id] === opt.text;
                          return (
                            <label
                              key={optIdx}
                              style={{
                                display: "flex", alignItems: "center", gap: "12px", padding: "14px 16px",
                                borderRadius: "12px",
                                border: chosen ? "1.5px solid #059669" : "1px solid var(--border-color)",
                                background: chosen ? "var(--bg-accent)" : "var(--bg-surface)",
                                cursor: "pointer", fontSize: "14px", color: "var(--text-main)",
                                transition: "all 0.15s ease",
                              }}
                            >
                              <input
                                type="radio"
                                className="quiz-radio-hidden"
                                name={q.id}
                                checked={chosen}
                                onChange={() => setServerQuizAnswers({ ...serverQuizAnswers, [q.id]: opt.text })}
                                style={{ visibility: "hidden", position: "absolute", width: 0, height: 0, opacity: 0, pointerEvents: "none" }}
                              />
                              <div style={{ flex: 1 }}>
                                <FormulaRenderer inline text={opt.text} />
                              </div>
                              <span style={{ fontSize: "12px", fontWeight: 900, color: chosen ? "#059669" : "var(--text-muted)", flexShrink: 0 }}>
                                {OPTION_LETTERS_AR[optIdx] || ""}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <textarea
                        rows={5}
                        value={serverQuizAnswers[q.id] || ""}
                        onChange={(e) => setServerQuizAnswers({ ...serverQuizAnswers, [q.id]: e.target.value })}
                        placeholder="اكتب إجابتك هنا…"
                        style={{ width: "100%", padding: "12px 14px", borderRadius: "10px", border: "1px solid var(--border-color)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: "14px", fontFamily: "inherit", boxSizing: "border-box" }}
                      />
                    )}

                    <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", marginTop: "24px", paddingTop: "18px", borderTop: "1px solid var(--border-color)" }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => setServerQuizQuestionIndex((i) => Math.max(0, i - 1))}
                        disabled={serverQuizQuestionIndex === 0}
                        style={{ gap: "6px" }}
                      >
                        <ArrowRight size={15} /> السؤال السابق
                      </button>
                      {serverQuizQuestionIndex < serverQuiz.questions.length - 1 ? (
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={() => setServerQuizQuestionIndex((i) => Math.min(serverQuiz!.questions.length - 1, i + 1))}
                          style={{ gap: "6px" }}
                        >
                          السؤال التالي <ArrowLeft size={15} />
                        </button>
                      ) : !serverQuizResult ? (
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={() => setShowQuizSubmitConfirm(true)}
                          disabled={serverQuizSubmitting || serverQuizRemaining === 0}
                          style={{ gap: "6px" }}
                        >
                          <Zap size={15} /> {serverQuizRemaining === 0 ? "انتهى الوقت" : "تسليم الاختبار"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          CONFIRMATION WIZARD: QUIZ SUBMISSION MODAL
         ========================================================================= */}
      {showQuizSubmitConfirm && serverQuiz && !serverQuizResult && (() => {
        const totalCount = serverQuiz.questions.length;
        const answeredCount = serverQuiz.questions.filter((q) => Boolean(serverQuizAnswers[q.id])).length;
        const unansweredCount = totalCount - answeredCount;
        const flaggedCount = serverQuiz.questions.filter((q) => Boolean(serverQuizFlagged[q.id])).length;

        return (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(15, 23, 42, 0.72)",
              backdropFilter: "blur(8px)",
              WebkitBackdropFilter: "blur(8px)",
              zIndex: 100000,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "20px",
            }}
            onClick={() => closeOverlay("quizSubmitConfirm", () => setShowQuizSubmitConfirm(false))}
          >
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "1.5px solid var(--border-color)",
                borderRadius: "20px",
                width: "100%",
                maxWidth: "520px",
                boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.45)",
                padding: "28px 24px",
                position: "relative",
                direction: "rtl",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div style={{ display: "flex", alignItems: "flex-start", gap: "14px", marginBottom: "20px" }}>
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "14px",
                    background: unansweredCount > 0 ? "rgba(239, 68, 68, 0.12)" : "rgba(5, 150, 105, 0.12)",
                    color: unansweredCount > 0 ? "#dc2626" : "#059669",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {unansweredCount > 0 ? <AlertTriangle size={26} /> : <CheckCircle2 size={26} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3 style={{ margin: "0 0 6px", fontSize: "19px", fontWeight: 900, color: "var(--text-main)" }}>
                    تأكيد تسليم الاختبار
                  </h3>
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5 }}>
                    هل أنت متأكد من رغبتك في إنهاء وتسليم الاختبار؟ سيتم تصحيح إجاباتك فورياً وحساب النتيجة.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => closeOverlay("quizSubmitConfirm", () => setShowQuizSubmitConfirm(false))}
                  style={{
                    background: "var(--bg-surface-secondary)",
                    border: "none",
                    borderRadius: "50%",
                    width: "32px",
                    height: "32px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    color: "var(--text-main)",
                    flexShrink: 0,
                  }}
                >
                  <X size={17} />
                </button>
              </div>

              {/* Statistics Grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: "10px",
                  background: "var(--bg-surface-secondary)",
                  padding: "14px",
                  borderRadius: "14px",
                  border: "1px solid var(--border-color)",
                  marginBottom: "18px",
                }}
              >
                <div style={{ textAlign: "center" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, display: "block" }}>
                    إجمالي الأسئلة
                  </span>
                  <strong style={{ fontSize: "20px", fontWeight: 900, color: "var(--text-main)" }}>
                    {totalCount}
                  </strong>
                </div>
                <div style={{ textAlign: "center" }}>
                  <span style={{ fontSize: "11px", color: "#059669", fontWeight: 700, display: "block" }}>
                    تمت الإجابة
                  </span>
                  <strong style={{ fontSize: "20px", fontWeight: 900, color: "#059669" }}>
                    {answeredCount}
                  </strong>
                </div>
                <div style={{ textAlign: "center" }}>
                  <span style={{ fontSize: "11px", color: unansweredCount > 0 ? "#dc2626" : "var(--text-muted)", fontWeight: 700, display: "block" }}>
                    متبقية دون إجابة
                  </span>
                  <strong style={{ fontSize: "20px", fontWeight: 900, color: unansweredCount > 0 ? "#dc2626" : "var(--text-muted)" }}>
                    {unansweredCount}
                  </strong>
                </div>
              </div>

              {/* Extra notice row (Flagged & Time) */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "12px",
                  padding: "0 4px",
                  marginBottom: "20px",
                  color: "var(--text-muted)",
                  fontWeight: 700,
                }}
              >
                {flaggedCount > 0 ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", color: "#d97706" }}>
                    <Flag size={14} /> لديك {flaggedCount} سؤال مُعلّم للمراجعة
                  </span>
                ) : (
                  <span />
                )}
                {serverQuizRemaining !== null && (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                    <Clock size={14} /> الوقت المتبقي: {Math.floor(serverQuizRemaining / 60)}:{String(serverQuizRemaining % 60).padStart(2, "0")} دقيقة
                  </span>
                )}
              </div>

              {/* Unanswered Warning Alert */}
              {unansweredCount > 0 ? (
                <div
                  style={{
                    background: "rgba(239, 68, 68, 0.1)",
                    border: "1px solid rgba(239, 68, 68, 0.25)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    fontSize: "12.5px",
                    color: "#b91c1c",
                    fontWeight: 700,
                    marginBottom: "22px",
                    display: "flex",
                    alignItems: "center",
                    gap: "9px",
                  }}
                >
                  <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                  <span>
                    تنبيه: لم تقم بالإجابة على <strong>{unansweredCount}</strong> سؤال! إذا سلّمت الآن فلن تتمكن من تعديلها وستُحسب درجاتها صفر.
                  </span>
                </div>
              ) : (
                <div
                  style={{
                    background: "rgba(5, 150, 105, 0.1)",
                    border: "1px solid rgba(5, 150, 105, 0.25)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    fontSize: "12.5px",
                    color: "#047857",
                    fontWeight: 700,
                    marginBottom: "22px",
                    display: "flex",
                    alignItems: "center",
                    gap: "9px",
                  }}
                >
                  <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
                  <span>
                    ممتاز! قمت بالإجابة على جميع الأسئلة ({totalCount} من {totalCount}). يمكنك تأكيد التسليم الآن.
                  </span>
                </div>
              )}

              {/* Actions */}
              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleConfirmSubmitQuiz}
                  disabled={serverQuizSubmitting}
                  style={{
                    flex: 1,
                    justifyContent: "center",
                    padding: "13px 18px",
                    fontSize: "14px",
                    fontWeight: 800,
                    borderRadius: "10px",
                    gap: "8px",
                    background: unansweredCount > 0 ? "#dc2626" : "#059669",
                  }}
                >
                  <Zap size={16} />
                  <span>{serverQuizSubmitting ? "جاري التسليم…" : "نعم، تأكيد وتسليم الآن"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => closeOverlay("quizSubmitConfirm", () => setShowQuizSubmitConfirm(false))}
                  disabled={serverQuizSubmitting}
                  style={{
                    flex: 1,
                    background: "var(--bg-surface-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "10px",
                    padding: "13px 18px",
                    fontSize: "14px",
                    fontWeight: 800,
                    color: "var(--text-main)",
                    cursor: "pointer",
                    textAlign: "center",
                  }}
                >
                  متابعة ومراجعة الأسئلة
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* =========================================================================
          STANDALONE PAGE A2: QUIZ GRADED RESULT — site topbar + hero score ring +
          summary stats + filterable corrected question list (per approved mock).
         ========================================================================= */}
      {(quizResultPage || quizResultLoading || quizResultError) && (() => {
        const percent = quizResultPage && quizResultPage.total_points > 0
          ? Math.round((quizResultPage.score / quizResultPage.total_points) * 1000) / 10
          : 0;
        const rankLabel = percent >= 90 ? "ممتاز — أنت نجم!" : percent >= 75 ? "جيد جداً — استمر!" : percent >= 50 ? "جيد — يمكنك التحسن" : "تحتاج مراجعة الدرس";
        const filtered = quizResultPage
          ? quizResultPage.questions.filter((q) => quizResultFilter === "all" || q.state === quizResultFilter)
          : [];
        const stateLabel: Record<string, string> = { correct: "إجابة صحيحة", wrong: "إجابة خاطئة", skipped: "لم تُجب" };
        const stateColor: Record<string, { bg: string; fg: string; border: string }> = {
          correct: { bg: "rgba(5, 150, 105, 0.15)", fg: "#10b981", border: "rgba(5, 150, 105, 0.35)" },
          wrong: { bg: "rgba(220, 38, 38, 0.15)", fg: "#f87171", border: "rgba(220, 38, 38, 0.35)" },
          skipped: { bg: "var(--bg-surface-secondary)", fg: "var(--text-muted)", border: "var(--border-color)" },
        };
        return (
          <div dir="rtl" style={{ position: "fixed", inset: 0, backgroundColor: "var(--bg-primary, #f8fafc)", zIndex: 100000, overflowY: "auto" }}>
            {/* Unified Quiz Result Header (Single bar matching Image 3 with Sidebar, Logo, Theme, Lang, and Exit) */}
            <header
              style={{
                height: "68px",
                background: "var(--bg-surface, #ffffff)",
                borderBottom: "1px solid var(--border-color)",
                padding: "0 24px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "14px",
                position: "sticky",
                top: 0,
                zIndex: 100,
                boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
                boxSizing: "border-box",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={onToggleMenu}
                  aria-label={menuOpen ? "Close Menu" : "Open Menu"}
                  title={lang === "ar" ? "القائمة الجانبية" : "Sidebar Menu"}
                >
                  {menuOpen ? <X size={18} /> : <Menu size={18} />}
                </button>

                <div
                  onClick={handleHeaderNavigateHome}
                  role="button"
                  tabIndex={0}
                  title={lang === "ar" ? "العودة إلى الصفحة الأولى" : "Go to Home"}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    cursor: "pointer",
                    userSelect: "none",
                  }}
                >
                  <div
                    className="brand-mark"
                    style={{
                      width: "34px",
                      height: "34px",
                      borderRadius: "9px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <GraduationCap size={18} />
                  </div>
                </div>

                <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 900, color: "var(--text-main)" }}>
                  نتيجة اختبار: {quizResultPage?.quiz.title || ""}
                </h2>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={onToggleTheme}
                  title={theme === "dark" ? "تفعيل الوضع النهاري" : "تفعيل الوضع الليلي"}
                  aria-label="Toggle Theme"
                >
                  {theme === "dark" ? <Sun size={18} style={{ color: "#f59e0b" }} /> : <Moon size={18} />}
                </button>

                <button
                  type="button"
                  className="icon-btn"
                  onClick={onToggleLang}
                  title="Switch Language / تغيير اللغة"
                  style={{ width: "auto", minWidth: "42px", padding: "0 8px", fontSize: "11.5px", fontWeight: 800 }}
                >
                  <span>{lang === "ar" ? "AR" : "EN"}</span>
                </button>

                <button
                  onClick={() => {
                    closeOverlay("quizResultPage", () => {
                      setQuizResultPage(null);
                      setQuizResultError(null);
                    });
                  }}
                  style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "7px 14px", fontSize: "12.5px", fontWeight: 800, color: "var(--text-main)", cursor: "pointer", flexShrink: 0 }}
                >
                  <X size={16} /> <span>خروج</span>
                </button>
              </div>
            </header>

            <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "24px 20px 70px" }}>
              {quizResultLoading && <div style={{ padding: "70px", textAlign: "center", color: "var(--text-muted)", fontSize: "14px" }}>جاري تحميل النتيجة…</div>}

              {quizResultError && (
                <div style={{ padding: "18px", background: "#fee2e2", color: "#b91c1c", borderRadius: "12px", fontWeight: 800, fontSize: "13.5px" }}>{quizResultError}</div>
              )}

              {quizResultPage && (() => {
                const dur = quizResultPage.attempt.duration_seconds;
                const durLabel = dur != null ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, "0")}` : "—";
                return (
                  <>
                    {/* ── Attempts History Bar: Switch attempts to review mistakes ── */}
                    {quizResultPage.attempts_history && quizResultPage.attempts_history.length > 0 && (
                      <div
                        style={{
                          ...assignmentPageCard,
                          padding: "16px 20px",
                          marginBottom: "20px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: "14px",
                          flexWrap: "wrap",
                          background: "var(--bg-surface)",
                          border: "1px solid var(--border-color)",
                          borderRadius: "14px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                          <span
                            style={{
                              width: "32px",
                              height: "32px",
                              borderRadius: "8px",
                              background: "var(--bg-accent, rgba(5,150,105,0.1))",
                              color: "#059669",
                              display: "inline-flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            <History size={17} />
                          </span>
                          <div>
                            <strong style={{ fontSize: "14px", color: "var(--text-main)", display: "block" }}>
                              سجل المحاولات ({quizResultPage.attempts_history.length} {quizResultPage.attempts_history.length === 1 ? "محاولة" : "محاولات"})
                            </strong>
                            <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                              اختر أي محاولة لرؤية درجاتك، أخطائك، والإجابات الصحيحة فيها
                            </span>
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                          {quizResultPage.attempts_history.map((att) => {
                            const isCurrent = att.id === quizResultPage.attempt.id;
                            return (
                              <button
                                key={att.id}
                                type="button"
                                onClick={() => void openQuizResultPage(quizResultPage.quiz.id, att.id)}
                                title={att.is_practice ? "محاولة تدريبية" : "محاولة رسمية"}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "7px",
                                  padding: "7px 14px",
                                  borderRadius: "10px",
                                  fontSize: "12.5px",
                                  fontWeight: 800,
                                  cursor: "pointer",
                                  background: isCurrent ? "#059669" : "var(--bg-surface-secondary)",
                                  color: isCurrent ? "#ffffff" : "var(--text-main)",
                                  border: isCurrent ? "1.5px solid #059669" : "1px solid var(--border-color)",
                                  boxShadow: isCurrent ? "0 2px 8px rgba(5,150,105,0.3)" : "none",
                                  transition: "all 0.15s ease",
                                }}
                              >
                                <span>المحاولة {att.attempt_number}</span>
                                {att.is_practice || att.attempt_number > 1 ? (
                                  <span style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "5px", background: isCurrent ? "rgba(255,255,255,0.25)" : "rgba(245,158,11,0.15)", color: isCurrent ? "#ffffff" : "#d97706" }}>
                                    تدريب
                                  </span>
                                ) : (
                                  <span style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "5px", background: isCurrent ? "rgba(255,255,255,0.25)" : "rgba(5,150,105,0.15)", color: isCurrent ? "#ffffff" : "#059669" }}>
                                    رسمية
                                  </span>
                                )}
                                <span style={{ fontWeight: 900, fontSize: "12px" }}>
                                  ({att.score}/{att.total_points})
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* ── Hero card: score ring + stats row ── */}
                    <div style={{ ...assignmentPageCard, padding: "26px", marginBottom: "20px", display: "flex", gap: "26px", flexWrap: "wrap", alignItems: "center" }}>
                      {/* Score ring */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", minWidth: "190px" }}>
                        <div style={{ position: "relative", width: "130px", height: "130px" }}>
                          <svg width="130" height="130" viewBox="0 0 130 130" style={{ transform: "rotate(-90deg)" }}>
                            <circle cx="65" cy="65" r="56" fill="none" stroke="var(--border-color)" strokeWidth="11" />
                            <circle
                              cx="65" cy="65" r="56" fill="none"
                              stroke={percent >= 75 ? "#10b981" : percent >= 50 ? "#f59e0b" : "#ef4444"}
                              strokeWidth="11" strokeLinecap="round"
                              strokeDasharray={`${(percent / 100) * 2 * Math.PI * 56} ${2 * Math.PI * 56}`}
                            />
                          </svg>
                          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                            <strong style={{ fontSize: "24px", fontWeight: 900, color: "var(--text-main)" }}>{percent}%</strong>
                            <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>
                              {quizResultPage.score.toLocaleString("ar-EG")} / {quizResultPage.total_points.toLocaleString("ar-EG")} درجة
                            </span>
                          </div>
                        </div>
                        <span style={{ fontSize: "12.5px", fontWeight: 900, color: "#059669", background: "var(--bg-accent)", border: "1px solid var(--border-accent)", padding: "5px 14px", borderRadius: "999px" }}>ممتاز — {rankLabel.split("—")[1]?.trim() || rankLabel}</span>
                        {quizResultPage.attempt.is_practice && (
                          <span style={{ fontSize: "11px", fontWeight: 800, color: "#92400e", background: "#fef3c7", padding: "3px 10px", borderRadius: "8px" }}>محاولة تدريبية — لن تصل للمعلم</span>
                        )}
                      </div>

                      {/* Stats row */}
                      <div style={{ flex: 1, minWidth: "280px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px" }}>
                        {[
                          { label: "الإجابات الصحيحة", value: `${quizResultPage.summary.correct} من ${quizResultPage.summary.total}`, color: "#059669", icon: <CheckCircle2 size={17} /> },
                          { label: "الإجابات الخاطئة", value: `${quizResultPage.summary.wrong} من ${quizResultPage.summary.total}`, color: "#dc2626", icon: <XCircle size={17} /> },
                          { label: "الوقت المستغرق", value: durLabel, color: "var(--text-main)", icon: <Clock size={17} /> },
                          { label: "الترتيب بالصف", value: "—", color: "var(--text-main)", icon: <Award size={17} /> },
                        ].map((s) => (
                          <div key={s.label} style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "14px 16px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11.5px", color: "var(--text-muted)", fontWeight: 800, marginBottom: "6px" }}>
                              <span style={{ color: s.color }}>{s.icon}</span>
                              {s.label}
                            </div>
                            <strong style={{ fontSize: "17px", fontWeight: 900, color: s.color }}>{s.value}</strong>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* ── Body: map sidebar + corrected questions ── */}
                    <div style={{ display: "flex", gap: "22px", alignItems: "flex-start", flexDirection: "row-reverse" }}>
                      {/* Correction map sidebar */}
                      <div style={{ width: "270px", flexShrink: 0, position: "sticky", top: "84px", display: "flex", flexDirection: "column", gap: "12px" }}>
                        <div style={{ ...assignmentPageCard, padding: "18px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                            <h3 style={{ margin: 0, fontSize: "13.5px", fontWeight: 900, color: "var(--text-main)" }}>خريطة تصحيح الأسئلة</h3>
                            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)" }}>{quizResultPage.summary.total} سؤال</span>
                          </div>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "7px", direction: "rtl" }}>
                            {quizResultPage.questions.map((q, qIdx) => {
                              const c = stateColor[q.state];
                              return (
                                <button
                                  key={q.id}
                                  type="button"
                                  title={stateLabel[q.state]}
                                  onClick={() => { const el = document.getElementById(`qr-q-${q.id}`); el?.scrollIntoView({ behavior: "smooth", block: "center" }); }}
                                  style={{
                                    width: "38px", height: "38px", borderRadius: "10px",
                                    background: c.bg, color: c.fg, border: `1.5px solid ${c.border}`,
                                    fontSize: "12.5px", fontWeight: 900, cursor: "pointer",
                                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1px",
                                  }}
                                >
                                  <span>{String(qIdx + 1).padStart(2, "0")}</span>
                                  <span style={{ fontSize: "9px", lineHeight: 1 }}>{q.state === "correct" ? "✓" : q.state === "wrong" ? "✕" : "—"}</span>
                                </button>
                              );
                            })}
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "14px", paddingTop: "12px", borderTop: "1px solid var(--border-color)", fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>
                            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: "11px", height: "11px", borderRadius: "3px", background: "#059669", border: "1.5px solid #059669" }} /> صحيح ({quizResultPage.summary.correct})</span>
                            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: "11px", height: "11px", borderRadius: "3px", background: "#dc2626", border: "1.5px solid #dc2626" }} /> خطأ ({quizResultPage.summary.wrong})</span>
                            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: "11px", height: "11px", borderRadius: "3px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)" }} /> متروك ({quizResultPage.summary.skipped})</span>
                          </div>
                        </div>
                      </div>

                      {/* Questions list */}
                      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "16px" }}>
                        {/* Filters */}
                        <div style={{ ...assignmentPageCard, padding: "12px 16px", display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                          {(["all", "correct", "wrong"] as const).map((f) => (
                            <button
                              key={f}
                              type="button"
                              onClick={() => setQuizResultFilter(f)}
                              style={{
                                padding: "7px 16px", borderRadius: "9px", cursor: "pointer",
                                fontSize: "12px", fontWeight: 900, border: quizResultFilter === f ? "1.5px solid #059669" : "1px solid var(--border-color)",
                                background: quizResultFilter === f ? "#059669" : "var(--bg-surface)",
                                color: quizResultFilter === f ? "#ffffff" : "var(--text-main)",
                              }}
                            >
                              {f === "all" ? `جميع الأسئلة (${quizResultPage.questions.length})` : f === "correct" ? `الأسئلة الصحيحة (${quizResultPage.summary.correct})` : `الأسئلة الخاطئة (${quizResultPage.summary.wrong})`}
                            </button>
                          ))}
                        </div>

                        {filtered.map((q) => {
                          const qIdx = quizResultPage.questions.findIndex((item) => item.id === q.id);
                          const c = stateColor[q.state];
                          return (
                            <div key={q.id} id={`qr-q-${q.id}`} style={{ ...assignmentPageCard, padding: "22px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px", marginBottom: "12px", flexWrap: "wrap" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                                  <span style={{ fontSize: "13.5px", fontWeight: 900, color: "var(--text-main)" }}>السؤال {ORDINAL_AR[qIdx] || qIdx + 1}</span>
                                  <span style={{ fontSize: "11.5px", fontWeight: 800, color: c.fg, background: c.bg, border: `1px solid ${c.border}`, padding: "3px 10px", borderRadius: "8px" }}>
                                    {q.state === "correct" ? "✓ " : q.state === "wrong" ? "✕ " : ""}{stateLabel[q.state]}
                                  </span>
                                </div>
                                <span style={{ fontSize: "11.5px", fontWeight: 800, color: "var(--text-muted)" }}>
                                  الدرجة: {q.awarded.toLocaleString("ar-EG")} / {q.points.toLocaleString("ar-EG")}
                                </span>
                              </div>

                              <div style={{ fontSize: "14.5px", color: "var(--text-main)", lineHeight: 1.8, fontWeight: 700, marginBottom: "14px" }}>
                                <FormulaRenderer text={q.prompt} />
                              </div>

                              {/* Options review */}
                              {q.options.length > 0 ? (
                                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: q.learning_objective ? "12px" : 0 }}>
                                  {q.options.map((opt, oIdx) => {
                                    const isStudentChoice = q.student_answer_letter === oIdx;
                                    const isCorrect = q.correct_answer_letter === oIdx;
                                    const revealWrong = isStudentChoice && q.state === "wrong";
                                    return (
                                      <div
                                        key={oIdx}
                                        style={{
                                          display: "flex", alignItems: "center", gap: "10px", padding: "11px 14px",
                                          borderRadius: "11px",
                                          border: isCorrect ? "1.5px solid #059669" : revealWrong ? "1.5px solid #dc2626" : "1px solid var(--border-color)",
                                          background: isCorrect ? "#059669" : revealWrong ? "#dc2626" : "var(--bg-surface-secondary)",
                                          color: isCorrect || revealWrong ? "#ffffff" : "var(--text-main)",
                                        }}
                                      >
                                        <span style={{
                                          width: "28px", height: "28px", borderRadius: "8px", flexShrink: 0,
                                          display: "flex", alignItems: "center", justifyContent: "center",
                                          background: isCorrect || revealWrong ? "rgba(255, 255, 255, 0.2)" : "var(--bg-surface)",
                                          color: isCorrect || revealWrong ? "#ffffff" : "var(--text-main)", fontSize: "12px", fontWeight: 900,
                                        }}>
                                          {OPTION_LETTERS_AR[oIdx] || oIdx + 1}
                                        </span>
                                        <div style={{ flex: 1, fontSize: "14px", color: isCorrect || revealWrong ? "#ffffff" : "var(--text-main)", fontWeight: isStudentChoice || isCorrect ? 800 : 600 }}>
                                          <FormulaRenderer inline text={opt} />
                                        </div>
                                        {isStudentChoice && q.state === "wrong" && <span style={{ fontSize: "11px", fontWeight: 800, background: "rgba(0,0,0,0.25)", color: "#ffffff", padding: "2px 8px", borderRadius: "6px", flexShrink: 0 }}>إجابتك (خاطئة)</span>}
                                        {isStudentChoice && q.state === "correct" && <span style={{ fontSize: "11px", fontWeight: 800, background: "rgba(255,255,255,0.25)", color: "#ffffff", padding: "2px 8px", borderRadius: "6px", flexShrink: 0 }}>إجابتك (صحيحة)</span>}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: q.learning_objective ? "12px" : 0 }}>
                                  <div style={{ padding: "12px 14px", borderRadius: "11px", background: q.state === "correct" ? "rgba(5, 150, 105, 0.12)" : "rgba(220, 38, 38, 0.12)", border: q.state === "correct" ? "1px solid rgba(5, 150, 105, 0.3)" : "1px solid rgba(220, 38, 38, 0.3)" }}>
                                    <small style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "4px" }}>إجابتك:</small>
                                    <span style={{ fontSize: "13.5px", color: "var(--text-main)", fontWeight: 700 }}>{q.student_answer || "— لم تُجب —"}</span>
                                  </div>
                                  <div style={{ padding: "12px 14px", borderRadius: "11px", background: "rgba(5, 150, 105, 0.12)", border: "1px solid rgba(5, 150, 105, 0.3)" }}>
                                    <small style={{ display: "block", fontSize: "11px", fontWeight: 800, color: "#059669", marginBottom: "4px" }}>الإجابة النموذجية:</small>
                                    <span style={{ fontSize: "13.5px", color: "var(--text-main)", fontWeight: 700 }}>{q.correct_answer || "—"}</span>
                                  </div>
                                </div>
                              )}

                              {q.learning_objective && (
                                <div style={{ padding: "11px 14px", borderRadius: "11px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-muted)", fontWeight: 700 }}>
                                  <HelpCircle size={14} style={{ color: "#059669", flexShrink: 0 }} />
                                  <span>الموضوع: {q.learning_objective}</span>
                                </div>
                              )}
                            </div>
                          );
                        })}

                        {filtered.length === 0 && (
                          <div style={{ ...assignmentPageCard, padding: "34px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                            لا توجد أسئلة في هذا التصنيف
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ textAlign: "center", marginTop: "28px" }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => {
                          closeOverlay("quizResultPage", () => {
                            setQuizResultPage(null);
                            setQuizResultError(null);
                          });
                        }}
                        style={{ padding: "11px 28px", fontSize: "14px", fontWeight: 800 }}
                      >
                        العودة إلى المقرر
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        );
      })()}

      {/* =========================================================================
          STANDALONE PAGE B: ASSIGNMENT SOLVE — site topbar + breadcrumb title +
          countdown to due date + PDF sheet card + upload card (per approved mock).
         ========================================================================= */}
      {(serverAssignment || serverAssignmentLoading || serverAssignmentError) && (
        <div
          dir="rtl"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "var(--bg-primary, #f8fafc)",
            zIndex: 100000,
            overflowY: "auto",
          }}
        >
          {/* Unified Assignment Header (Single bar matching Image 3 with Sidebar, Logo, Theme, Lang, and Exit) */}
          <header
            style={{
              height: "68px",
              background: "var(--bg-surface, #ffffff)",
              borderBottom: "1px solid var(--border-color)",
              padding: "0 24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "14px",
              position: "sticky",
              top: 0,
              zIndex: 100,
              boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
              boxSizing: "border-box",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
              <button
                type="button"
                className="icon-btn"
                onClick={onToggleMenu}
                aria-label={menuOpen ? "Close Menu" : "Open Menu"}
                title={lang === "ar" ? "القائمة الجانبية" : "Sidebar Menu"}
              >
                {menuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>

              <div
                onClick={handleHeaderNavigateHome}
                role="button"
                tabIndex={0}
                title={lang === "ar" ? "العودة إلى الصفحة الأولى" : "Go to Home"}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  cursor: "pointer",
                  userSelect: "none",
                }}
              >
                <div
                  className="brand-mark"
                  style={{
                    width: "34px",
                    height: "34px",
                    borderRadius: "9px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <GraduationCap size={18} />
                </div>
              </div>

              <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 900, color: "var(--text-main)" }}>
                {serverAssignment?.title || "واجب"}
              </h2>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
              <button
                type="button"
                className="icon-btn"
                onClick={onToggleTheme}
                title={theme === "dark" ? "تفعيل الوضع النهاري" : "تفعيل الوضع الليلي"}
                aria-label="Toggle Theme"
              >
                {theme === "dark" ? <Sun size={18} style={{ color: "#f59e0b" }} /> : <Moon size={18} />}
              </button>

              <button
                type="button"
                className="icon-btn"
                onClick={onToggleLang}
                title="Switch Language / تغيير اللغة"
                style={{ width: "auto", minWidth: "42px", padding: "0 8px", fontSize: "11.5px", fontWeight: 800 }}
              >
                <span>{lang === "ar" ? "AR" : "EN"}</span>
              </button>

              <button
                onClick={() => {
                  closeOverlay("serverAssignment", () => {
                    setServerAssignment(null);
                    setServerAssignmentError(null);
                  });
                }}
                style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "7px 14px", fontSize: "12.5px", fontWeight: 800, color: "var(--text-main)", cursor: "pointer", flexShrink: 0 }}
              >
                <X size={16} /> <span>خروج</span>
              </button>
            </div>
          </header>

          <div style={{ maxWidth: "760px", margin: "0 auto", padding: "26px 20px 70px" }}>
            {/* ── Breadcrumb lesson context + centered title + countdown chip ── */}
            <div style={{ textAlign: "center", marginBottom: "22px" }}>
              <div style={{ fontSize: "12px", fontWeight: 800, color: "#059669", marginBottom: "6px", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <FileText size={14} />
                {currentCourse?.title || "المقرر الدراسي"}
              </div>
              <h1 style={{ margin: "0 0 10px", fontSize: "25px", fontWeight: 900, color: "var(--text-main)" }}>
                {serverAssignment?.title || "واجب"}
              </h1>
              {serverAssignment?.dueAt && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 800, color: "var(--text-muted)", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", padding: "5px 14px", borderRadius: "999px" }}>
                  <Clock size={13} />
                  متبقٍ: {formatDueCountdown(serverAssignment.dueAt)}
                </span>
              )}
            </div>

            {/* ── Card 1: the printable assignment sheet (PDF) ── */}
            <div style={{ ...assignmentPageCard, marginBottom: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
                  <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: "#fee2e2", color: "#dc2626", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <FileText size={22} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <strong style={{ display: "block", fontSize: "13.5px", fontWeight: 900, color: "var(--text-main)" }}>
                      ملف أسئلة الواجب — ورقة الأسئلة
                    </strong>
                    <small style={{ display: "block", fontSize: "11.5px", color: "var(--text-muted)", marginTop: "2px" }}>
                      ملف PDF • حمّله وحلّه على الورق ثم صوّر إجابتك
                    </small>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
                  <button
                    type="button"
                    onClick={() => void downloadAssignmentSheet()}
                    style={{
                      display: "inline-flex", alignItems: "center", gap: "6px",
                      background: "#0f392b", color: "#ffffff", border: "none",
                      borderRadius: "9px", padding: "9px 16px", fontSize: "12.5px", fontWeight: 900,
                      cursor: "pointer",
                    }}
                  >
                    <Download size={15} />
                    <span>تحميل PDF</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => window.open(serverAssignment?.sheetUrl || "", "_blank", "noopener")}
                    style={{
                      display: "inline-flex", alignItems: "center", gap: "6px",
                      background: "var(--bg-surface)", color: "var(--text-main)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "9px", padding: "9px 14px", fontSize: "12.5px", fontWeight: 800,
                      cursor: "pointer",
                    }}
                  >
                    <BookOpen size={15} />
                    <span>معاينة</span>
                  </button>
                </div>
              </div>
            </div>

            {/* ── Card 2: upload the solved answer ── */}
            <div style={{ ...assignmentPageCard, padding: "24px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px", fontSize: "13.5px", fontWeight: 900, color: "var(--text-main)" }}>
                <FileCheck size={17} style={{ color: "#059669" }} />
                <span>رفع ملف إجابتك</span>
                <small style={{ fontSize: "11.5px", fontWeight: 600, color: "var(--text-muted)", marginInlineStart: "auto" }}>
                  PDF أو صور (PNG, JPG)
                </small>
              </div>

              {assignmentUploadDone ? (
                <div style={{ padding: "18px", background: "#dcfce7", border: "1.5px solid #86efac", borderRadius: "14px", display: "flex", alignItems: "center", gap: "12px" }}>
                  <CheckCircle2 size={24} style={{ color: "#059669", flexShrink: 0 }} />
                  <div>
                    <strong style={{ display: "block", fontSize: "14px", color: "#166534" }}>تم إرسال حل الواجب للمعلم بنجاح</strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      نسخة رقم {assignmentUploadDone.version} • {new Date(assignmentUploadDone.submittedAt).toLocaleString("ar-EG")}
                    </span>
                  </div>
                </div>
              ) : (
                <>
                  {serverAssignmentLoading && <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>جاري تحميل الواجب…</div>}

                  {serverAssignmentError && (
                    <div style={{ padding: "16px", background: "#fee2e2", color: "#b91c1c", borderRadius: "12px", fontWeight: 800, fontSize: "13.5px", marginBottom: "14px" }}>
                      {serverAssignmentError}
                    </div>
                  )}

                  {serverAssignment && (
                    <>
                      {serverAssignment.latestSubmission?.hasFile && (
                        <div style={{ padding: "12px 14px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: "10px", fontSize: "12.5px", color: "#065f46", fontWeight: 700, marginBottom: "14px" }}>
                          ✓ سبق أن سلّمت نسخة رقم {serverAssignment.latestSubmission.version} — يمكنك رفع نسخة أحدث إن لزم.
                        </div>
                      )}

                      {/* Dropzone */}
                      <label
                        style={{
                          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                          gap: "8px", padding: "34px 18px", borderRadius: "14px", cursor: "pointer", textAlign: "center",
                          border: assignmentFile ? "2px solid #059669" : "2px dashed var(--border-color)",
                          background: assignmentFile ? "var(--bg-accent)" : "transparent",
                          transition: "all 0.15s ease", marginBottom: "14px",
                        }}
                      >
                        {assignmentFile ? <CheckCircle2 size={28} style={{ color: "#059669" }} /> : <Upload size={28} style={{ color: "#059669" }} />}
                        <strong style={{ fontSize: "13.5px", fontWeight: 900, color: "var(--text-main)" }}>
                          {assignmentFile ? assignmentFile.name : "اضغط لاختيار ملف الحل أو اسحبه هنا"}
                        </strong>
                        <small style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                          يمكنك رفع صور شاشوئية أو ملف PDF مجمع (حتى 50 ميجابايت)
                        </small>
                        <input
                          type="file"
                          accept=".pdf,.png,.jpg,.jpeg"
                          style={{ display: "none" }}
                          onChange={(e) => setAssignmentFile(e.target.files?.[0] || null)}
                        />
                      </label>

                      {assignmentUploading && (
                        <div style={{ height: "7px", borderRadius: "4px", background: "var(--bg-surface-secondary)", overflow: "hidden", marginBottom: "14px" }}>
                          <div style={{ height: "100%", width: "100%", background: "linear-gradient(90deg, #059669, #10b981)", animation: "assignmentProgress 1.2s ease-in-out infinite" }} />
                        </div>
                      )}

                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => void submitAssignmentFile()}
                        disabled={!assignmentFile || assignmentUploading}
                        style={{
                          width: "100%", justifyContent: "center", gap: "8px", height: "48px",
                          fontSize: "14px", fontWeight: 900,
                          background: "#065f46", opacity: !assignmentFile || assignmentUploading ? 0.55 : 1,
                        }}
                      >
                        <FileCheck size={17} />
                        <span>{assignmentUploading ? "جاري الرفع…" : "إرسال الحل للمعلم"}</span>
                      </button>
                    </>
                  )}
                </>
              )}
            </div>

            {/* ── Return to course ── */}
            <div style={{ textAlign: "center", marginTop: "18px" }}>
              <button
                type="button"
                onClick={() => {
                  closeOverlay("serverAssignment", () => {
                    setServerAssignment(null);
                    setServerAssignmentError(null);
                  });
                }}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "6px",
                  background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)",
                  borderRadius: "9px", padding: "9px 18px", fontSize: "12.5px", fontWeight: 800,
                  color: "var(--text-main)", cursor: "pointer",
                }}
              >
                <ArrowRight size={15} />
                <span>رجوع للمقرر</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 0: BOOK READER MODAL
         ========================================================================= */}
      {activeBookModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            zIndex: 99999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "20px",
              width: "100%",
              maxWidth: "650px",
              maxHeight: "90vh",
              overflowY: "auto",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.35)",
              padding: "24px",
              position: "relative",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
              <div>
                <span style={{ fontSize: "11.5px", color: "#059669", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px", fontWeight: 800 }}>
                  قارئ الكتب والمذكرات الإلكتروني
                </span>
                <h2 style={{ margin: "6px 0 2px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                  {activeBookModal.title}
                </h2>
                <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  {activeBookModal.author} • {activeBookModal.pagesCount} صفحة
                </span>
              </div>
              <button
                onClick={() => closeOverlay("activeBookModal", () => setActiveBookModal(null))}
                style={{ background: "var(--bg-surface-secondary)", border: "none", borderRadius: "50%", width: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--text-main)" }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Book Simulation Preview */}
            <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "12px", padding: "30px 20px", textAlign: "center", marginBottom: "20px" }}>
              <BookOpen size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
              <strong style={{ display: "block", fontSize: "15px", color: "var(--text-main)", marginBottom: "6px" }}>
                نسخة إلكترونية تفاعلية عالية الجودة
              </strong>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
                تم فك تشفير النسخة الخاصة بحسابك ومتاحة للقراءة الفورية والتنزيل المباشر على جهازك.
              </p>
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={() => {
                  if (activeBookModal.fileUrl) {
                    void downloadLessonMaterial(activeBookModal.fileUrl, activeBookModal.title);
                  } else {
                    toast(`تم بدء تنزيل "${activeBookModal.title}" بنجاح!`, "success");
                  }
                  closeOverlay("activeBookModal", () => setActiveBookModal(null));
                }}
                className="btn-primary"
                style={{ flex: 1, justifyContent: "center", padding: "12px", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px", gap: "6px" }}
              >
                <Download size={16} />
                <span>تحميل النسخة الكاملة على الجهاز</span>
              </button>
            </div>
          </div>
        </div>
      )}


      {/* =========================================================================
          MODAL 2: ASSIGNMENT SOLVING & SUBMISSION MODAL
         ========================================================================= */}
      {activeAssignmentModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "var(--bg-primary, #f8fafc)",
            zIndex: 99999,
            overflowY: "auto",
            padding: "28px 20px 60px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color)",
              borderRadius: "20px",
              maxWidth: "880px",
              width: "100%",
              margin: "0 auto",
              padding: "26px",
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px", borderBottom: "1px solid var(--border-color)", paddingBottom: "14px" }}>
              <div>
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#1e3a8a", background: "#dbeafe", padding: "3px 8px", borderRadius: "6px" }}>
                  تسليم الواجب المنزلي • الدرجة: {activeAssignmentModal.maxScore}
                </span>
                <h2 style={{ margin: "6px 0 2px", fontSize: "18px", color: "var(--text-main)" }}>
                  {activeAssignmentModal.title}
                </h2>
                <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  الموعد النهائي للتسليم: <strong>{activeAssignmentModal.dueDate}</strong>
                </span>
              </div>
              <button
                onClick={() => closeOverlay("activeAssignmentModal", () => setActiveAssignmentModal(null))}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "7px 14px",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  color: "var(--text-main)",
                  cursor: "pointer",
                }}
              >
                <X size={16} />
                <span>رجوع للمقرر</span>
              </button>
            </div>

            {/* Success Message */}
            {assignmentSuccessMsg && (
              <div style={{ padding: "12px", background: "#dcfce7", color: "#166534", borderRadius: "8px", fontSize: "13px", fontWeight: 800, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                <CheckCircle2 size={18} />
                <span>تم إرسال وتسليم إجابة الواجب للمعلم بنجاح!</span>
              </div>
            )}

            {/* Assignment Prompt */}
            <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)", marginBottom: "18px" }}>
              <strong style={{ display: "block", fontSize: "13.5px", color: "var(--text-main)", marginBottom: "6px" }}>
                تعليمات ونص الأسئلة:
              </strong>
              <p style={{ margin: "0 0 10px", fontSize: "13px", color: "var(--text-muted)", lineHeight: "1.6", whiteSpace: "pre-line" }}>
                {activeAssignmentModal.questionsPrompt}
              </p>
              <small style={{ color: "#059669", fontWeight: 700 }}>
                تنبيه: تأكد من مراجعة إجابتك قبل الضغط على تسليم الواجب.
              </small>
            </div>

            {/* Answer Input */}
            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 800, color: "var(--text-main)", marginBottom: "6px" }}>
                اكتب إجابتك النموذجية هنا:
              </label>
              <textarea
                rows={5}
                value={submittedAssignmentIds[activeAssignmentModal.id]?.answer || assignmentAnswerText}
                onChange={(e) => setAssignmentAnswerText(e.target.value)}
                disabled={!!submittedAssignmentIds[activeAssignmentModal.id]}
                placeholder="اكتب خطوات الحل بالتفصيل هنا..."
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "10px",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-surface)",
                  color: "var(--text-main)",
                  fontSize: "13px",
                  fontFamily: "inherit",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>

            {/* Actions */}
            {!submittedAssignmentIds[activeAssignmentModal.id] && (
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid var(--border-color)", paddingTop: "16px" }}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleSubmitAssignment}
                  disabled={!assignmentAnswerText.trim()}
                  style={{ gap: "6px" }}
                >
                  <FileCheck size={16} />
                  <span>تسليم الواجب الآن</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 3: INTERACTIVE QUIZ SOLVING MODAL
         ========================================================================= */}
      {activeQuizModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "var(--bg-primary, #f8fafc)",
            zIndex: 99999,
            overflowY: "auto",
            padding: "28px 20px 60px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color)",
              borderRadius: "20px",
              maxWidth: "880px",
              width: "100%",
              margin: "0 auto",
              padding: "26px",
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)",
            }}
          >
            {/* Top Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "14px", marginBottom: "20px" }}>
              <div>
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#831843", background: "#fce7f3", padding: "3px 8px", borderRadius: "6px" }}>
                  اختبار تقييمي إلكتروني • {activeQuizModal.durationMinutes} دقيقة
                </span>
                <h2 style={{ margin: "6px 0 2px", fontSize: "18px", color: "var(--text-main)" }}>
                  {activeQuizModal.title}
                </h2>
              </div>
              <button
                onClick={() => closeOverlay("activeQuizModal", () => setActiveQuizModal(null))}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "7px 14px",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  color: "var(--text-main)",
                  cursor: "pointer",
                }}
              >
                <X size={16} />
                <span>خروج</span>
              </button>
            </div>

            {/* Quiz Result Banner */}
            {quizSubmitted && quizScoreResult && (
              <div
                style={{
                  padding: "16px",
                  background: quizScoreResult.score >= 7 ? "#dcfce7" : "#fef3c7",
                  border: quizScoreResult.score >= 7 ? "1.5px solid #86efac" : "1.5px solid #fde68a",
                  borderRadius: "12px",
                  marginBottom: "20px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <Sparkles size={24} style={{ color: "#059669" }} />
                  <div>
                    <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block" }}>
                      {quizScoreResult.score >= 7 ? "أحسنت! تم اجتياز الكويز بنجاح" : "تم تسليم الاختبار - مراجعة الأخطاء مطلوبة"}
                    </strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      تم تسجيل نتيجتك في كشف درجات الطالب بالمنصة.
                    </span>
                  </div>
                </div>
                <div style={{ fontSize: "20px", fontWeight: 900, color: "#059669" }}>
                  {quizScoreResult.score} / {quizScoreResult.maxScore} درجة
                </div>
              </div>
            )}

            {/* Questions List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "18px", marginBottom: "24px" }}>
              {activeQuizModal.questions.map((q, qIdx) => {
                const selectedOpt = quizAnswers[q.id];
                const isCorrect = selectedOpt === q.correctAnswerIndex;

                return (
                  <div
                    key={q.id}
                    style={{
                      background: "var(--bg-surface-secondary)",
                      border: quizSubmitted
                        ? (isCorrect ? "1.5px solid #10b981" : "1.5px solid #ef4444")
                        : "1px solid var(--border-color)",
                      borderRadius: "12px",
                      padding: "16px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "12px" }}>
                      <span style={{ width: "24px", height: "24px", borderRadius: "50%", background: "#0f392b", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px", fontWeight: 800, flexShrink: 0 }}>
                        {qIdx + 1}
                      </span>
                      <div style={{ fontSize: "14px", color: "var(--text-main)", lineHeight: "1.5", flex: 1 }}>
                        <FormulaRenderer text={q.question} />
                      </div>
                    </div>

                    {/* Options */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginInlineStart: "32px" }}>
                      {q.options.map((opt, optIdx) => {
                        const isChosen = selectedOpt === optIdx;
                        const isRightAnswer = optIdx === q.correctAnswerIndex;

                        return (
                          <label
                            key={optIdx}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              padding: "8px 12px",
                              borderRadius: "8px",
                              border: isChosen ? "1.5px solid #059669" : "1px solid var(--border-color)",
                              background: isChosen ? "var(--bg-accent)" : "var(--bg-surface)",
                              cursor: quizSubmitted ? "default" : "pointer",
                              fontSize: "13px",
                              color: "var(--text-main)",
                            }}
                          >
                            <input
                              type="radio"
                              className="quiz-radio-hidden"
                              name={q.id}
                              checked={isChosen}
                              disabled={quizSubmitted}
                              onChange={() => setQuizAnswers({ ...quizAnswers, [q.id]: optIdx })}
                              style={{ visibility: "hidden", position: "absolute", width: 0, height: 0, opacity: 0, pointerEvents: "none" }}
                            />
                            <div style={{ flex: 1 }}>
                              <FormulaRenderer inline text={opt} />
                            </div>
                            {quizSubmitted && isRightAnswer && (
                              <span style={{ fontSize: "11px", color: "#166534", fontWeight: 800, marginInlineStart: "auto" }}>
                                الإجابة الصحيحة
                              </span>
                            )}
                          </label>
                        );
                      })}
                    </div>

                    {/* AI Explanation after submit */}
                    {quizSubmitted && (
                      <div style={{ marginTop: "12px", padding: "10px", background: "var(--bg-surface)", border: "1px dashed var(--border-color)", borderRadius: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
                        <strong style={{ display: "block", marginBottom: "4px" }}>تفسير الذكاء الاصطناعي:</strong>
                        <FormulaRenderer text={q.explanation} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Bottom Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid var(--border-color)", paddingTop: "16px" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => closeOverlay("activeQuizModal", () => setActiveQuizModal(null))}
              >
                {quizSubmitted ? "تم والعودة للمقرر" : "إلغاء"}
              </button>

              {!quizSubmitted && (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleSubmitQuiz}
                  disabled={Object.keys(quizAnswers).length < activeQuizModal.questions.length}
                  style={{ gap: "6px" }}
                >
                  <Zap size={16} />
                  <span>إنهاء وتسليم الاختبار</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          QUIZ ATTEMPT HISTORY MODAL — select any past attempt to review mistakes
         ========================================================================= */}
      {activeQuizHistoryModal && (
        <div
          dir="rtl"
          className="modal-overlay"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.65)",
            zIndex: 100060,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          onClick={() => closeOverlay("activeQuizHistoryModal", () => setActiveQuizHistoryModal(null))}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              borderRadius: "18px",
              padding: "24px",
              maxWidth: "540px",
              width: "100%",
              maxHeight: "85vh",
              overflowY: "auto",
              boxShadow: "var(--card-shadow)",
              border: "1px solid var(--border-color)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", paddingBottom: "12px", borderBottom: "1px solid var(--border-color)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ width: "36px", height: "36px", borderRadius: "10px", background: "var(--bg-accent, rgba(5,150,105,0.1))", color: "#059669", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                  <History size={20} />
                </span>
                <div>
                  <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 900, color: "var(--text-main)" }}>
                    سجل محاولات الاختبار
                  </h3>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    {activeQuizHistoryModal.title}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => closeOverlay("activeQuizHistoryModal", () => setActiveQuizHistoryModal(null))}
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "var(--bg-surface-secondary)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-main)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <X size={16} />
              </button>
            </div>

            <p style={{ margin: "0 0 16px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.6 }}>
              اختر أي محاولة امتحنت فيها لعرض تصحيحها بالكامل ومعرفة إجاباتك، أخطائك، والإجابة النموذجية:
            </p>

            {quizHistoryLoading ? (
              <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)", fontSize: "13.5px" }}>
                جاري تحميل سجل المحاولات…
              </div>
            ) : !quizHistoryAttempts || quizHistoryAttempts.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                لا توجد محاولات مسجلة بعد لهذا الاختبار.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {quizHistoryAttempts.map((att) => (
                  <div
                    key={att.id}
                    style={{
                      background: "var(--bg-surface-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "12px",
                      padding: "14px 16px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "12px",
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <strong style={{ fontSize: "14px", fontWeight: 900, color: "var(--text-main)" }}>
                          المحاولة رقم {att.attempt_number}
                        </strong>
                        {att.is_practice || att.attempt_number > 1 ? (
                          <span style={{ fontSize: "10.5px", fontWeight: 800, color: "#92400e", background: "#fef3c7", padding: "2px 8px", borderRadius: "6px" }}>
                            تدريبية
                          </span>
                        ) : (
                          <span style={{ fontSize: "10.5px", fontWeight: 800, color: "#065f46", background: "#d1fae5", padding: "2px 8px", borderRadius: "6px" }}>
                            رسمية
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                        {att.submitted_at ? new Date(att.submitted_at).toLocaleString("ar-EG") : "—"}
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontSize: "15px", fontWeight: 900, color: "#059669" }}>
                        {att.score} / {att.total_points}
                      </span>
                      <button
                        type="button"
                        className="btn-primary"
                        style={{ padding: "8px 14px", fontSize: "12.5px", gap: "6px" }}
                        onClick={() => {
                          const quizId = activeQuizHistoryModal.id;
                          overlayHistoryStack.current = overlayHistoryStack.current.map((item) => (item === "activeQuizHistoryModal" ? "quizResultPage" : item));
                          window.history.replaceState({ lmsOverlay: "quizResultPage" }, "");
                          setActiveQuizHistoryModal(null);
                          void openQuizResultPage(quizId, att.id);
                        }}
                      >
                        <Eye size={14} />
                        <span>عرض الأخطاء والتصحيح</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

/* ── Assignment standalone page helpers ── */

const assignmentPageCard: React.CSSProperties = {
  background: "var(--bg-surface, #ffffff)",
  border: "1px solid var(--border-color, #e2e8f0)",
  borderRadius: "16px",
  padding: "20px 22px",
  boxShadow: "0 2px 12px rgba(0,0,0,0.04)",
};

/** Human Arabic countdown to the assignment due date. */
function formatDueCountdown(dueAt: string): string {
  const ms = new Date(dueAt).getTime() - Date.now();
  if (Number.isNaN(ms)) return "—";
  if (ms <= 0) return "انتهى الموعد النهائي";
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 60) return `${minutes.toLocaleString("ar-EG")} دقيقة`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours.toLocaleString("ar-EG")} يوم و ${((minutes % 60) / 60 >= 0.5 ? 1 : 0).toLocaleString("ar-EG")} ساعات`.replace(" و 1 ساعات", " و نصف");
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return remHours > 0
    ? `${days.toLocaleString("ar-EG")} يوم و ${remHours.toLocaleString("ar-EG")} ساعة`
    : `${days.toLocaleString("ar-EG")} يوم`;
}

/* ── Quiz page Arabic ordinals and MCQ letter prefixes (per approved mock) ── */

const ORDINAL_AR: Record<number, string> = {
  0: "الأول",
  1: "الثاني",
  2: "الثالث",
  3: "الرابع",
  4: "الخامس",
  5: "السادس",
  6: "السابع",
  7: "الثامن",
  8: "التاسع",
  9: "العاشر",
};

const OPTION_LETTERS_AR: Record<number, string> = {
  0: "أ",
  1: "ب",
  2: "ج",
  3: "د",
  4: "هـ",
};

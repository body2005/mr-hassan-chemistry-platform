import React, { useState, useEffect, useRef } from "react";
import {
  Award,
  Book,
  BookOpen,
  CheckCircle2,
  Clock,
  Download,
  FileCheck,
  FileText,
  Flame,
  HelpCircle,
  Lock,
  Play,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Timer,
  Upload,
  Video,
  VideoOff,
  X,
  Zap,
  Plus,
} from "lucide-react";
import { Course, CourseAssessmentRef, CurrentUser, StudentProfile, VideoLesson } from "../types/lms";
import { Language, translations } from "../utils/i18n";
import { EducationalBookItem, RevisionPackageItem } from "./GeneralHomeView";
import { courseService } from "../services/lmsService";
import { apiRequest, fetchApiBlob, uploadWithProgress } from "../services/apiClient";
import { useToast } from "../components/ToastProvider";
import { FormulaRenderer } from "../components/FormulaRenderer";
import { PaymentTarget } from "../services/paymentService";
import { VideoLessonPage } from "../components/VideoLessonPage";

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
}

export const MyCoursesView: React.FC<MyCoursesViewProps> = ({
  enrolledCourses,
  onNavigateToCatalog,
  lang,
  currentUser,
  purchasedLessonIds = [],
  onCheckout,
}) => {
  const t = translations[lang];
  const toast = useToast();

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

  // Track purchased book IDs
  const [purchasedBookIds] = useState<string[]>([]);

  // Track purchased revision IDs
  const [purchasedRevisionIds] = useState<string[]>([]);

  function handleBuyLesson(lesson: VideoLesson) {
    onCheckout({ productType: "lesson", productId: lesson.id });
  }

  const [activeBookModal, setActiveBookModal] = useState<EducationalBookItem | null>(null);

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
  const [serverQuizSubmitting, setServerQuizSubmitting] = useState(false);
  const [serverQuizResult, setServerQuizResult] = useState<{ score: number; total: number; attemptNumber: number } | null>(null);
  // Server-authoritative attempt: the clock starts when the page opens.
  const [serverQuizAttempt, setServerQuizAttempt] = useState<{ id: string; attemptNumber: number; expiresAt: string | null } | null>(null);
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
  };
  const [serverAssignment, setServerAssignment] = useState<ServerAssignmentSolve | null>(null);
  const [serverAssignmentLoading, setServerAssignmentLoading] = useState(false);
  const [serverAssignmentError, setServerAssignmentError] = useState<string | null>(null);
  const [assignmentFile, setAssignmentFile] = useState<File | null>(null);
  const [assignmentUploading, setAssignmentUploading] = useState(false);
  const [assignmentUploadDone, setAssignmentUploadDone] = useState<{ version: number; submittedAt: string } | null>(null);

  /** Open the standalone quiz-solving page with the real server quiz. */
  async function openServerQuiz(assessment: CourseAssessmentRef) {
    setServerQuiz(null);
    setServerQuizError(null);
    setServerQuizAnswers({});
    setServerQuizResult(null);
    setServerQuizAttempt(null);
    setServerQuizDeadline(null);
    setServerQuizRemaining(null);
    serverQuizAutoSubmitted.current = false;
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
          score: submitted.score ?? 0,
          total: submitted.total_points ?? serverQuiz.totalPoints,
          attemptNumber: submitted.attempt_number,
        });
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
        onClose={() => setActiveLessonModal(null)}
        onDownloadMaterial={downloadLessonMaterial}
      />
    );
  }

  const courseLessons = currentCourse?.lessons || [];
  const completedLessonsCount = courseLessons.filter((l) => completedLessonIds.includes(l.id)).length;
  const progressPercent = courseLessons.length > 0 ? Math.round((completedLessonsCount / courseLessons.length) * 100) : 0;

  return (
    <div className="page-container">
      {/* Top Urgent Counter & Progress Banner */}
      <div className="urgency-banner" style={{ marginBottom: "20px" }}>
        <div className="urgency-counter">
          <div className="urgency-badge">
            <Flame size={24} />
            <span>متبقي {Math.max(0, courseLessons.length - completedLessonsCount)} دروس</span>
          </div>
          <div>
            <strong style={{ display: "block", fontSize: "16px", color: "var(--urgency-text)" }}>
              مقرر {currentCourse.subject} - {currentCourse.academicYearLabel}
            </strong>
            <span style={{ fontSize: "13px", color: "var(--urgency-text)", opacity: 0.9 }}>
              تابع شروحات الفيديوهات، أنجز الواجبات المطلوبة، وتدرب على الكويزات التفاعلية قبل الموعد النهائي!
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ textAlign: "center", fontSize: "12px", color: "var(--urgency-text)", fontWeight: 700 }}>
            <span>نسبة إنجاز المقرر</span>
            <strong style={{ display: "block", fontSize: "20px" }}>{progressPercent}%</strong>
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

        {/* Content Tabs (الدروس • الواجبات • الكويزات) */}
        <div style={{ display: "flex", gap: "10px", marginTop: "24px", borderTop: "1px solid var(--border-color)", paddingTop: "18px", flexWrap: "wrap" }}>
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
      </div>

      {/* =========================================================================
          SECTION 1: LESSONS GRID (في شكل بطاقات زي المقررات)
         ========================================================================= */}
      {activeContentTab === "lessons" && (
        <div>
          {courseLessons.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
              <VideoOff size={40} style={{ color: "var(--text-muted)", margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>فارغ</h3>
              <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "13.5px" }}>
                لا توجد فيديوهات أو دروس مرفوعة في هذا المقرر حالياً.
              </p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))", gap: "20px" }}>
              {courseLessons.map((lesson, idx) => {
                const isCompleted = completedLessonIds.includes(lesson.id);
                const price = Number(lesson.price || 0);
                const isPurchased = !isStudent || Number(activeCourse?.price || 0) > 0 || price === 0 || purchasedLessonIds.includes(lesson.id);

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
                      onClick={() => (isPurchased ? setActiveLessonModal(lesson) : handleBuyLesson(lesson))}
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
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleBuyLesson(lesson)}
                            className="btn-primary"
                            style={{ fontSize: "12px", padding: "7px 14px", gap: "6px", background: "#059669" }}
                          >
                            <ShoppingCart size={13} />
                            <span>شراء الدرس — {price} ج.م</span>
                          </button>
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
          {purchasedRevisionIds.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
              <Zap size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد معسكرات مراجعة أو ورش عمل مفعلة حالياً
              </h3>
              <p style={{ margin: "0 0 18px", color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "480px", marginInline: "auto" }}>
                يمكنك الاشتراك في معسكرات مراجعة نصف العام، ورش حل المسائل والمعادلات الكيميائية، ومراجعات ليلة الامتحان من متجر المنصة.
              </p>
              <button
                className="btn-primary"
                onClick={onNavigateToCatalog}
                style={{ padding: "10px 20px", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px", display: "inline-flex", alignItems: "center", gap: "8px" }}
              >
                <ShoppingBag size={16} />
                <span>تصفح المراجعات والورش في المتجر</span>
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 330px), 1fr))", gap: "20px" }}>
              {allRevisions
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
          )}
        </div>
      )}

      {/* =========================================================================
          SECTION 2: ASSIGNMENTS GRID (في شكل بطاقات زي المقررات مع الـ Deadline)
         ========================================================================= */}
      {activeContentTab === "assignments" && serverAssignments.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: "20px", marginBottom: "24px" }}>
          {serverAssignments.map((asg) => (
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
            {courseAssignments.map((asg) => {
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
      {activeContentTab === "quizzes" && serverQuizzes.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))", gap: "20px", marginBottom: "24px" }}>
          {serverQuizzes.map((qz) => (
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
                <button
                  className="btn-primary"
                  style={{ width: "100%", justifyContent: "center", gap: 6 }}
                  onClick={() => void openServerQuiz(qz)}
                >
                  <Play size={14} /> بدء حل الاختبار
                </button>
              ) : qz.accessible ? (
                <div
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                    padding: "10px 12px",
                    borderRadius: "10px",
                    background: "var(--bg-surface-secondary)",
                    border: "1px dashed var(--border-color)",
                    fontSize: "12.5px",
                    fontWeight: 800,
                    color: "var(--text-muted)",
                  }}
                >
                  <CheckCircle2 size={14} /> انتهت المحاولات المسموحة ({qz.attemptsUsed ?? 0} من {qz.attemptsAllowed})
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
            {courseQuizzes.map((quiz) => {
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
          {purchasedBookIds.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1.5px dashed var(--border-color)", borderRadius: "18px", padding: "60px 20px", textAlign: "center" }}>
              <Book size={48} style={{ color: "#059669", margin: "0 auto 12px" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد كتب أو مذكرات مشتراة حتى الآن
              </h3>
              <p style={{ margin: "0 0 18px", color: "var(--text-muted)", fontSize: "13.5px", maxWidth: "480px", marginInline: "auto" }}>
                يمكنك تصفح وشراء كتب الشرح المعتمدة، بنوك الأسئلة، ومذكرات ليلة الامتحان من متجر المنصة وتفعيلها مباشرة هنا.
              </p>
              <button
                className="btn-primary"
                onClick={onNavigateToCatalog}
                style={{ padding: "10px 20px", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px", display: "inline-flex", alignItems: "center", gap: "8px" }}
              >
                <ShoppingBag size={16} />
                <span>تصفح وشراء الكتب من المتجر</span>
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))", gap: "20px" }}>
              {allBooks
                .filter((b) => purchasedBookIds.includes(b.id))
                .map((book) => (
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
                    <div style={{ background: book.gradient, padding: "20px", color: "white" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ background: "rgba(255,255,255,0.2)", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                          نسخة مملوكة ومفعلة
                        </span>
                        <span style={{ fontSize: "12px", opacity: 0.9 }}>{book.pagesCount} صفحة</span>
                      </div>
                      <h3 style={{ margin: "4px 0", fontSize: "16px", fontWeight: 800, lineHeight: 1.3 }}>
                        {book.title}
                      </h3>
                      <span style={{ fontSize: "11.5px", opacity: 0.85 }}>إعداد: {book.author}</span>
                    </div>

                    {/* Content */}
                    <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <p style={{ fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 14px" }}>
                          {book.description}
                        </p>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "16px" }}>
                          {book.sampleTopics?.map((top: string, idx: number) => (
                            <span key={idx} style={{ fontSize: "10.5px", background: "var(--bg-accent)", color: "#065f46", padding: "2px 7px", borderRadius: "4px", fontWeight: 700 }}>
                              {top}
                            </span>
                          ))}
                        </div>
                      </div>

                      <button
                        onClick={() => setActiveBookModal(book)}
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
                        <Download size={15} />
                        <span>فتح وتحميل الكتاب - PDF</span>
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          STANDALONE PAGE A: SERVER QUIZ SOLVING (full page, not a dialog)
         ========================================================================= */}
      {(serverQuiz || serverQuizLoading || serverQuizError) && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "var(--bg-app, #f8fafc)",
            zIndex: 100000,
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "14px", marginBottom: "18px", gap: "10px" }}>
              <div>
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#831843", background: "#fce7f3", padding: "3px 8px", borderRadius: "6px" }}>
                  اختبار إلكتروني{serverQuiz?.durationSeconds ? ` • ${Math.ceil(serverQuiz.durationSeconds / 60)} دقيقة` : ""}
                </span>
                <h2 style={{ margin: "6px 0 0", fontSize: "19px", color: "var(--text-main)" }}>{serverQuiz?.title || "جاري التحميل…"}</h2>
              </div>
              {serverQuizRemaining !== null && !serverQuizResult && (
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "7px",
                    padding: "8px 16px",
                    borderRadius: "10px",
                    fontWeight: 900,
                    fontSize: "16px",
                    fontVariantNumeric: "tabular-nums",
                    direction: "ltr",
                    flexShrink: 0,
                    background: serverQuizRemaining <= 60 ? "#fef2f2" : "var(--bg-surface-secondary)",
                    color: serverQuizRemaining <= 60 ? "#b91c1c" : "var(--text-main)",
                    border: serverQuizRemaining <= 60 ? "1.5px solid #fca5a5" : "1px solid var(--border-color)",
                  }}
                >
                  <Timer size={18} style={{ color: serverQuizRemaining <= 60 ? "#b91c1c" : "#059669" }} />
                  <span>
                    {Math.floor(serverQuizRemaining / 60)}:{String(serverQuizRemaining % 60).padStart(2, "0")}
                  </span>
                </div>
              )}
              <button
                onClick={() => { setServerQuiz(null); setServerQuizError(null); }}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "6px",
                  background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)",
                  borderRadius: "8px", padding: "7px 14px", fontSize: "12.5px", fontWeight: 800,
                  color: "var(--text-main)", cursor: "pointer", flexShrink: 0,
                }}
              >
                <X size={16} />
                <span>خروج</span>
              </button>
            </div>

            {serverQuizLoading && <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>جاري تحميل أسئلة الاختبار…</div>}

            {serverQuizError && (
              <div style={{ padding: "16px", background: "#fee2e2", color: "#b91c1c", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px" }}>
                {serverQuizError}
              </div>
            )}

            {serverQuizResult && (
              <div style={{ padding: "18px", background: "#dcfce7", border: "1.5px solid #86efac", borderRadius: "12px", marginBottom: "18px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <Sparkles size={24} style={{ color: "#059669" }} />
                  <div>
                    <strong style={{ fontSize: "15px", color: "var(--text-main)", display: "block" }}>تم تسليم الاختبار وتصحيحه فورياً</strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>المحاولة رقم {serverQuizResult.attemptNumber} — النتيجة مسجلة في كشف الدرجات.</span>
                  </div>
                </div>
                <div style={{ fontSize: "22px", fontWeight: 900, color: "#059669" }}>
                  {serverQuizResult.score} / {serverQuizResult.total} درجة
                </div>
              </div>
            )}

            {serverQuiz && !serverQuizResult && (
              <>
                <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginBottom: "22px" }}>
                  {serverQuiz.questions.map((q, qIdx) => {
                    const opts = q.options || [];
                    const isMcq = Array.isArray(opts) && opts.length > 0;
                    return (
                      <div key={q.id} style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "12px", padding: "16px" }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "10px" }}>
                          <span style={{ width: "24px", height: "24px", borderRadius: "50%", background: "#0f392b", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px", fontWeight: 800, flexShrink: 0 }}>
                            {qIdx + 1}
                          </span>
                          <div style={{ fontSize: "14px", color: "var(--text-main)", lineHeight: "1.6", flex: 1 }}>
                            <FormulaRenderer text={q.prompt} />
                          </div>
                          <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 800, flexShrink: 0 }}>{q.points} درجة</span>
                        </div>

                        {isMcq ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginInlineStart: "32px" }}>
                            {opts.map((opt, optIdx) => {
                              const chosen = serverQuizAnswers[q.id] === opt.text;
                              return (
                                <label
                                  key={optIdx}
                                  style={{
                                    display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px",
                                    borderRadius: "8px",
                                    border: chosen ? "1.5px solid #059669" : "1px solid var(--border-color)",
                                    background: chosen ? "var(--bg-accent)" : "var(--bg-surface)",
                                    cursor: "pointer", fontSize: "13px", color: "var(--text-main)",
                                  }}
                                >
                                  <input
                                    type="radio"
                                    name={q.id}
                                    checked={chosen}
                                    onChange={() => setServerQuizAnswers({ ...serverQuizAnswers, [q.id]: opt.text })}
                                  />
                                  <div style={{ flex: 1 }}>
                                    <FormulaRenderer inline text={opt.text} />
                                  </div>
                                </label>
                              );
                            })}
                          </div>
                        ) : (
                          <textarea
                            rows={4}
                            value={serverQuizAnswers[q.id] || ""}
                            onChange={(e) => setServerQuizAnswers({ ...serverQuizAnswers, [q.id]: e.target.value })}
                            placeholder="اكتب إجابتك هنا…"
                            style={{ width: "100%", padding: "10px 12px", borderRadius: "8px", border: "1px solid var(--border-color)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: "13px", fontFamily: "inherit", boxSizing: "border-box" }}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid var(--border-color)", paddingTop: "16px" }}>
                  <button type="button" className="btn-secondary" onClick={() => setServerQuiz(null)} disabled={serverQuizSubmitting}>
                    خروج دون تسليم
                  </button>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => void submitServerQuiz()}
                    disabled={serverQuizSubmitting || serverQuizRemaining === 0 || Object.keys(serverQuizAnswers).length < serverQuiz.questions.length}
                    style={{ gap: "6px" }}
                  >
                    <Zap size={16} />
                    <span>{serverQuizRemaining === 0 ? "انتهى الوقت" : serverQuizSubmitting ? "جاري التصحيح…" : "إنهاء وتسليم الاختبار"}</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          STANDALONE PAGE B: ASSIGNMENT SOLVE (download PDF → solve → upload)
         ========================================================================= */}
      {(serverAssignment || serverAssignmentLoading || serverAssignmentError) && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "var(--bg-app, #f8fafc)",
            zIndex: 100000,
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--border-color)", paddingBottom: "14px", marginBottom: "18px", gap: "10px" }}>
              <div>
                <span style={{ fontSize: "11px", fontWeight: 800, color: "#1e3a8a", background: "#dbeafe", padding: "3px 8px", borderRadius: "6px" }}>
                  واجب منزلي • الدرجة: {serverAssignment?.maxScore ?? "—"}
                </span>
                <h2 style={{ margin: "6px 0 2px", fontSize: "19px", color: "var(--text-main)" }}>{serverAssignment?.title || "جاري التحميل…"}</h2>
                {serverAssignment?.dueAt && (
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    آخر موعد للتسليم: <strong>{new Date(serverAssignment.dueAt).toLocaleDateString("ar-EG")}</strong>
                  </span>
                )}
              </div>
              <button
                onClick={() => { setServerAssignment(null); setServerAssignmentError(null); }}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "6px",
                  background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)",
                  borderRadius: "8px", padding: "7px 14px", fontSize: "12.5px", fontWeight: 800,
                  color: "var(--text-main)", cursor: "pointer", flexShrink: 0,
                }}
              >
                <X size={16} />
                <span>رجوع للمقرر</span>
              </button>
            </div>

            {serverAssignmentLoading && <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>جاري تحميل الواجب…</div>}

            {serverAssignmentError && (
              <div style={{ padding: "16px", background: "#fee2e2", color: "#b91c1c", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px" }}>
                {serverAssignmentError}
              </div>
            )}

            {serverAssignment && (
              <>
                <div style={{ background: "var(--bg-surface-secondary)", padding: "16px", borderRadius: "12px", border: "1px solid var(--border-color)", marginBottom: "18px" }}>
                  <strong style={{ display: "block", fontSize: "13.5px", color: "var(--text-main)", marginBottom: "6px" }}>تعليمات الواجب:</strong>
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)", lineHeight: "1.7", whiteSpace: "pre-line" }}>
                    <FormulaRenderer text={serverAssignment.prompt} />
                  </p>
                </div>

                {assignmentUploadDone ? (
                  <div style={{ padding: "16px", background: "#dcfce7", border: "1.5px solid #86efac", borderRadius: "12px", display: "flex", alignItems: "center", gap: "10px", marginBottom: "18px" }}>
                    <CheckCircle2 size={22} style={{ color: "#059669" }} />
                    <div>
                      <strong style={{ display: "block", fontSize: "14px", color: "#166534" }}>تم إرسال حل الواجب للمعلم بنجاح</strong>
                      <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                        نسخة رقم {assignmentUploadDone.version} • {new Date(assignmentUploadDone.submittedAt).toLocaleString("ar-EG")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Step 1: download the assignment PDF (lesson materials) */}
                    {serverAssignment.latestSubmission?.hasFile && (
                      <div style={{ padding: "12px 14px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: "10px", fontSize: "12.5px", color: "#065f46", fontWeight: 700, marginBottom: "14px" }}>
                        ✓ سبق أن سلّمت نسخة رقم {serverAssignment.latestSubmission.version} — يمكنك رفع نسخة أحدث إن لزم.
                      </div>
                    )}

                    {/* Step 2: solve on paper then upload a photographed PDF/images */}
                    <div style={{ border: "1.5px dashed var(--border-color)", borderRadius: "14px", padding: "22px", textAlign: "center", marginBottom: "16px" }}>
                      <Upload size={30} style={{ color: "#059669", margin: "0 auto 10px" }} />
                      <strong style={{ display: "block", fontSize: "14px", color: "var(--text-main)", marginBottom: "4px" }}>
                        ارفع ملف حل الواجب
                      </strong>
                      <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.6 }}>
                        حمّل ورقة الواجب، حلها بالكتابة، صوّر أوراقك أو امسحها ضوئياً، وارفعها ملف PDF أو صور واضحة (حتى 50 ميجا).
                      </p>
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={(e) => setAssignmentFile(e.target.files?.[0] || null)}
                        style={{ maxWidth: "320px", margin: "0 auto 12px", display: "block", fontSize: "12.5px" }}
                      />
                      {assignmentFile && (
                        <div style={{ fontSize: "12.5px", color: "var(--text-main)", fontWeight: 800, marginBottom: "12px" }}>
                          الملف المختار: {assignmentFile.name} ({Math.round(assignmentFile.size / 1024)} كيلوبايت)
                        </div>
                      )}
                      <div>
                        <button
                          type="button"
                          className="btn-primary"
                          onClick={() => void submitAssignmentFile()}
                          disabled={!assignmentFile || assignmentUploading}
                          style={{ gap: "6px" }}
                        >
                          <FileCheck size={16} />
                          <span>{assignmentUploading ? "جاري الرفع…" : "تسليم الواجب الآن"}</span>
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
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
                onClick={() => setActiveBookModal(null)}
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
                  toast(`تم بدء تنزيل "${activeBookModal.title}" بنجاح!`, "success");
                  setActiveBookModal(null);
                }}
                className="btn-primary"
                style={{ flex: 1, justifyContent: "center", padding: "12px", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px", gap: "6px" }}
              >
                <Download size={16} />
                <span>تحميل النسخة الكاملة على الجهاز</span>
              </button>
              <button
                onClick={() => setActiveBookModal(null)}
                className="btn-outline"
                style={{ padding: "12px 20px", borderRadius: "10px", fontWeight: 800, fontSize: "13.5px" }}
              >
                إغلاق
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
            backgroundColor: "var(--bg-app, #f8fafc)",
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
                onClick={() => setActiveAssignmentModal(null)}
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
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid var(--border-color)", paddingTop: "16px" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setActiveAssignmentModal(null)}
              >
                إغلاق
              </button>

              {!submittedAssignmentIds[activeAssignmentModal.id] && (
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
              )}
            </div>
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
            backgroundColor: "var(--bg-app, #f8fafc)",
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
                onClick={() => setActiveQuizModal(null)}
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
                              name={q.id}
                              checked={isChosen}
                              disabled={quizSubmitted}
                              onChange={() => setQuizAnswers({ ...quizAnswers, [q.id]: optIdx })}
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
                onClick={() => setActiveQuizModal(null)}
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
    </div>
  );
};

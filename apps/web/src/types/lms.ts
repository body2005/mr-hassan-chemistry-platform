export type UserRole = "student" | "teacher" | "institution_admin" | "platform_admin";

export interface StudentProfile {
  id: string;
  name: string;
  email: string;
  role: "student";
  nationalId: string;
  nationalIdPhotoUrl?: string;
  studentPhone: string;
  guardianPhone: string;
  age: number;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  interestedSubjects: string[];
  avatarUrl?: string;
  isBlocked?: boolean;
  joinedDate: string;
}

export interface TeacherProfile {
  id: string;
  name: string;
  email: string;
  role: "teacher" | "institution_admin" | "platform_admin";
  nationalId: string;
  nationalIdPhotoUrl?: string;
  phone: string;
  teachingYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary" | "all";
  teachingYearLabel: string;
  subject: string;
  contractAgreed: boolean;
  contractAgreedAt?: string;
  uploadedVideosCount: number;
  enrolledStudentsCount: number;
  avatarUrl?: string;
  joinedDate: string;
}

export type CurrentUser = StudentProfile | TeacherProfile;

export interface UploadedMaterial {
  id: string;
  title: string;
  fileType: "pdf" | "video" | "doc";
  fileUrl: string;
  fileSize: string;
  uploadedAt: string;
}

export interface VideoWatchSegment {
  startTimeSec: number;
  endTimeSec: number;
  watched: boolean;
}

export interface LessonAISignals {
  viewsCount: number;
  completionRate: number; // percentage (e.g. 88%)
  mostRewatchedSegment?: {
    timeRange: string; // e.g. "14:20 - 18:45"
    replayCount: number; // e.g. 84
    conceptLabel: string; // e.g. "استنتاج إشارة العجلة والسرعة اللحظية"
  };
  commentsSentiment?: {
    totalComments: number;
    confusionQuestionsCount: number;
    sampleQuestion: string; // e.g. "ليه العجلة سالبة والجسم بيتحرك للأمام؟"
  };
  assignmentPerformance?: {
    assignmentTitle: string;
    averageScore: number; // percentage, e.g. 71%
    hardestQuestion: string; // e.g. "المسألة 3: حساب الإزاحة من منحنى (v-t)"
  };
  quizPerformance?: {
    quizTitle: string;
    averageScore: number; // percentage, e.g. 68%
    commonMistake: string; // e.g. "الخلط بين السرعة المتوسطة والمتجهة"
  };
}

export interface VideoLesson {
  id: string;
  moduleId?: string;
  courseId: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  title: string;
  description: string;
  durationMinutes: number;
  durationFormatted: string;
  videoUrl: string;
  /** Native videos are resolved only after the viewer obtains a scoped token. */
  requiresProtectedPlayback?: boolean;
  thumbnailUrl?: string;
  price?: number; // Per-lesson price decided by teacher (0 = free)
  materials: UploadedMaterial[];
  uploadedByTeacherName: string;
  uploadedAt: string;
  order: number;
  // Transcript materialization status (real processing state, no AI)
  materialization_status?: string;
}

export interface Course {
  id: string;
  title: string;
  subject: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  teacherName: string;
  teacherTitle: string;
  description: string;
  thumbnailColor: string;
  coverImage?: string;
  lessonsCount: number;
  totalDurationFormatted: string;
  lessons: VideoLesson[];
  enrolledStudentsCount: number;
  price?: number;
}

export interface NotificationSchedule {
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  days: string[];
  time: string;
  active: boolean;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: "assignment" | "quiz" | "system" | "warning";
  dueDate?: string;
  targetYear?: "all" | "1st_secondary" | "2nd_secondary" | "3rd_secondary" | string;
  createdAt: string;
  read: boolean;
  actionUrl?: string;
  actionTab?: "GeneralHome" | "MyCourses" | "MySubmissions" | "LessonManagement" | "QuizGen" | "Submissions" | "StudentAnalytics" | "Notifications" | string;
  targetCourseId?: string;
  targetLessonId?: string;
  quizDurationMinutes?: number;
  quizCloseDeadline?: string;
}

export interface StudentVideoWatchLog {
  videoId: string;
  videoTitle: string;
  courseTitle: string;
  totalDurationSec: number;
  watchedDurationSec: number;
  completionPercentage: number;
  lastWatchedAt: string;
  dropOffTimestampSec: number;
  segments: VideoWatchSegment[];
}

export interface StudentRecord {
  id: string;
  name: string;
  nationalId: string;
  email: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  overallAttendanceRatio: number; // 0 - 1.0 (e.g. 0.85 = 85%)
  assignmentSubmissionRatio: number; // 0 - 1.0 (e.g. 0.92 = 92%)
  averageQuizScore: number; // 0 - 100
  totalOverallGrade: number; // 0 - 100
  quizSuccessRate: number; // 0 - 100%
  homeworkSuccessRate: number; // 0 - 100%
  lastActiveDate: string;
  isBlocked?: boolean;
  watchHistory: StudentVideoWatchLog[];
  customFieldValues: Record<string, unknown>;
}

export interface AssignmentSubmission {
  id: string;
  assignmentId?: string;
  studentId: string;
  studentName: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  academicYearLabel: string;
  assignmentTitle: string;
  lessonTitle: string;
  questionPrompt: string;
  studentAnswer: string;
  submittedAt: string;
  maxScore: number;
  aiScore: number;
  finalScore: number;
  teacherFeedback?: string;
  aiFeedbackSummary: string;
  criteriaScores: Array<{
    criterion: string;
    score: number;
    max: number;
    notes: string;
  }>;
  status: "graded" | "needs_review" | "approved";
}

export interface CustomColumn {
  id: string;
  name: string;
  dataType: "text" | "number" | "percentage" | "checkbox";
  tableContext: "submissions" | "students";
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary" | "all";
  createdAt: string;
}

export interface AIChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: Array<{
    lesson_id: string;
    lesson_title?: string;
    snippet: string;
  }>;
}

export interface AIChatSession {
  id: string;
  title: string;
  courseId: string;
  createdAt: string;
  messages: AIChatMessage[];
}

export interface QuestionTypeConfig {
  id: "multiple_choice" | "essay" | "true_false" | "fill_in_blank" | "short_answer" | "numerical" | "image_question";
  label: string;
  count: number;
  withCorrection?: boolean; // For true/false
}

export interface CalendarScheduleEvent {
  id: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary" | "all";
  date: string; // YYYY-MM-DD
  dayName: string; // Title / Name of the day
  time: string; // e.g. "06:00 م"
  contentType: "lesson" | "assignment" | "quiz" | "general";
  isRecurringWeekly?: boolean;
  isCancelled?: boolean;
  isPublishedToStudents?: boolean; // Checkbox: visible to students on calendar
  quizDurationMinutes?: number; // Duration in minutes to complete the quiz
  publishStartDate?: string;
  publishStartTime?: string;
  closeDeadline?: string; // Deadline after which quiz is locked
}

import { apiRequest, uploadWithProgress, ApiClientError, markBrowserSessionActive } from "./apiClient";
/**
 * ============================================================================
 * MATGAR LMS - UNIFIED DATA ACCESS LAYER (DAL)
 * ============================================================================
 * Architecture: Clean Service Layer Abstraction (Repository Pattern)
 * Purpose: Decouples UI Views from Direct Storage Implementations.
 * Migration Path: Swapping from LocalStorage to FastAPI / REST Backend
 * requires editing only this service file without touching UI components.
 * ============================================================================
 */

import {
  AssignmentSubmission,
  CalendarScheduleEvent,
  Course,
  CurrentUser,
  NotificationItem,
  NotificationSchedule,
  StudentVideoWatchLog,
} from "../types/lms";

export const STORAGE_KEYS = {
  USER: "lms_user",
  REGISTERED_USERS: "lms_registered_users",
  COURSES: "lms_courses",
  ENROLLED_COURSES: "lms_enrolled_courses",
  NOTIFICATIONS: "lms_notifications",
  CALENDAR_EVENTS: "lms_calendar_schedule_events",
  NOTIFICATION_SCHEDULES: "lms_notification_schedules",
  VIDEO_LOGS: "lms_student_video_logs",
  SUBMISSIONS: "lms_submissions",
  THEME: "lms_theme",
  LANG: "lms_lang",
  ACTIVE_TAB: "lms_active_tab",
} as const;

type ApiUser = {
  id: string;
  institution_id: string;
  username: string;
  email: string;
  display_name: string;
  role: "student" | "teacher" | "institution_admin" | "platform_admin";
  grade_level: "SECONDARY_1" | "SECONDARY_2" | "SECONDARY_3" | null;
  governorate: string | null;
  school_name: string | null;
  gender: "MALE" | "FEMALE" | null;
  student_phone?: string | null;
  guardian_phone?: string | null;
  national_id?: string | null;
  religion?: "MUSLIM" | "CHRISTIAN" | "OTHER" | "PREFER_NOT_TO_SAY" | null;
  is_active: boolean;
  created_at: string;
};

type ApiCourse = {
  id: string;
  institution_id: string;
  teacher_id: string;
  code: string;
  title: string;
  description: string | null;
  status: "draft" | "published" | "archived";
  published_at: string | null;
  created_at: string;
  updated_at: string;
  price_egp: number;
  modules: Array<{
    id: string;
    title: string;
    position: number;
    lessons: Array<{
      id: string;
      title: string;
      kind: "video" | "article" | "live";
      position: number;
      content: string | null;
      video_asset_key: string | null;
      video_duration_seconds: number | null;
      indexing_status?: "not_indexed" | "in_progress" | "indexed" | "failed";
      indexing_error?: string | null;
      indexed_chunks_count?: number;
      price_egp?: number;
      materials?: Array<{
        id: string;
        filename: string;
        file_format: string;
        size_bytes: number;
        source_role: string;
        download_url: string;
        created_at: string;
      }>;
    }>;
  }>;
};

type ApiEnrollment = { course_id: string };

type ApiNotification = {
  id: string;
  kind: string;
  title: string;
  message: string;
  action_url: string | null;
  read_at: string | null;
  scheduled_for: string | null;
  delivered_at: string | null;
  delivery_status: "pending" | "delivered" | "failed";
  created_at: string;
};

type ApiCalendarEvent = {
  id: string;
  course_id: string | null;
  title: string;
  description: string | null;
  event_type: string;
  starts_at: string;
  ends_at: string | null;
  is_published: boolean;
  cancelled_at: string | null;
  created_at: string;
};

type ApiSubmission = {
  id: string;
  assignment_id: string;
  student_id: string;
  version: number;
  answer_text: string;
  object_key: string | null;
  status: "submitted" | "needs_review" | "graded" | "approved";
  ai_score: number | null;
  final_score: number | null;
  ai_feedback: string | null;
  teacher_feedback: string | null;
  submitted_at: string;
  graded_at: string | null;
  approved_at: string | null;
  assignment_title: string | null;
  assignment_prompt: string | null;
  max_score: number | null;
  course_title: string | null;
  student_name: string | null;
};

type ApiLessonProgress = {
  lesson_id: string;
  last_position_seconds: number;
  watched_duration_seconds: number;
  completion_percent: number;
  last_event_at: string | null;
  completed_at: string | null;
};

export { apiRequest, ApiClientError };

function mapApiUser(user: ApiUser): CurrentUser {
  const gradeMap = {
    SECONDARY_1: { value: "1st_secondary", label: "الصف الأول الثانوي" },
    SECONDARY_2: { value: "2nd_secondary", label: "الصف الثاني الثانوي" },
    SECONDARY_3: { value: "3rd_secondary", label: "الصف الثالث الثانوي" },
  } as const;
  const base = {
    id: user.id,
    name: user.display_name,
    email: user.email,
    nationalId: user.national_id || "",
    joinedDate: user.created_at.slice(0, 10),
  };
  if (user.role === "student") {
    const grade = user.grade_level ? gradeMap[user.grade_level] : undefined;
    if (!grade) throw new ApiClientError("INVALID_STUDENT_GRADE", "Student grade is missing", 422);
    return {
      ...base,
      role: "student",
      studentPhone: user.student_phone || "",
      guardianPhone: user.guardian_phone || "",
      age: 0,
      academicYear: grade.value,
      academicYearLabel: grade.label,
      interestedSubjects: [],
    };
  }
  return {
    ...base,
    role: user.role,
    phone: "",
    teachingYear: "all",
    teachingYearLabel: "جميع الصفوف الثانوية",
    subject: "",
    contractAgreed: false,
    uploadedVideosCount: 0,
    enrolledStudentsCount: 0,
  };
}

function mapApiCourse(course: ApiCourse): Course {
  const lessons = course.modules
    .slice()
    .sort((a, b) => a.position - b.position)
    .flatMap((module) =>
      module.lessons
        .slice()
        .sort((a, b) => a.position - b.position)
        .map((lesson) => ({
          id: lesson.id,
          moduleId: module.id,
          courseId: course.id,
          academicYear: "1st_secondary" as const,
          title: lesson.title,
          description: lesson.content || "",
          durationMinutes: Math.ceil((lesson.video_duration_seconds || 0) / 60),
          durationFormatted: lesson.video_duration_seconds
            ? `${Math.ceil(lesson.video_duration_seconds / 60)} دقيقة`
            : "",
          // A native upload never becomes a browser URL here. The player asks
          // the API for a short-lived, lesson-scoped stream token when opened.
          // This explicit flag avoids inventing a pseudo URL, which browsers
          // cannot safely resolve.
          videoUrl: lesson.video_asset_key && /^https?:\/\//i.test(lesson.video_asset_key)
            ? lesson.video_asset_key
            : "",
          requiresProtectedPlayback: Boolean(
            lesson.video_asset_key && !/^https?:\/\//i.test(lesson.video_asset_key),
          ),
          price: Number(lesson.price_egp || 0),
          materials: (lesson.materials || []).map((m) => ({
            id: m.id,
            title: m.filename,
            fileType: (m.file_format === "pdf" ? "pdf" : "doc") as "pdf" | "video" | "doc",
            fileUrl: m.download_url,
            fileSize: `${Math.round(m.size_bytes / 1024)} KB`,
            uploadedAt: m.created_at,
          })),
          uploadedByTeacherName: "",
          uploadedAt: lesson.video_duration_seconds ? course.updated_at : course.created_at,
          order: lesson.position,
          predictedDifficultyScore: 0,
          expectedStruggleRate: 0,
          predictedMisconceptionRate: 0,
          flaggedHardConcepts: [],
          indexing_status: lesson.indexing_status || "not_indexed",
          indexing_error: lesson.indexing_error || undefined,
          indexed_chunks_count: lesson.indexed_chunks_count || 0,
        })),
    );
  return {
    id: course.id,
    title: course.title,
    subject: course.code,
    academicYear: "1st_secondary",
    academicYearLabel: "الصف الأول الثانوي",
    teacherName: "",
    teacherTitle: "",
    description: course.description || "",
    thumbnailColor: "#164f40",
    lessonsCount: lessons.length,
    totalDurationFormatted: `${lessons.reduce((sum, lesson) => sum + lesson.durationMinutes, 0)} دقيقة`,
    lessons,
    enrolledStudentsCount: 0,
    price: Number(course.price_egp || 0),
  };
}

function mapApiNotification(item: ApiNotification): NotificationItem {
  const type: NotificationItem["type"] = ["assignment", "quiz", "warning"].includes(item.kind)
    ? (item.kind as NotificationItem["type"])
    : "system";
  return {
    id: item.id,
    title: item.title,
    message: item.message,
    type,
    createdAt: item.created_at,
    read: Boolean(item.read_at),
    dueDate: item.scheduled_for || undefined,
    actionUrl: item.action_url || undefined,
    actionTab: item.action_url?.replace(/^#/, "") as NotificationItem["actionTab"],
  };
}

function mapApiCalendarEvent(item: ApiCalendarEvent): CalendarScheduleEvent {
  const starts = new Date(item.starts_at);
  const time = starts.toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" });
  const contentType = ["lesson", "assignment", "quiz", "general"].includes(item.event_type)
    ? (item.event_type as CalendarScheduleEvent["contentType"])
    : "general";

  let academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary" | "all" = "1st_secondary";
  let isRecurringWeekly: boolean | undefined = undefined;
  let quizDurationMinutes: number | undefined = undefined;
  let publishStartDate: string | undefined = undefined;
  let publishStartTime: string | undefined = undefined;

  if (item.description) {
    try {
      const parsed = JSON.parse(item.description);
      if (parsed && typeof parsed === "object") {
        if (["1st_secondary", "2nd_secondary", "3rd_secondary", "all"].includes(parsed.academicYear)) {
          academicYear = parsed.academicYear;
        }
        if (parsed.isRecurringWeekly !== undefined) isRecurringWeekly = parsed.isRecurringWeekly;
        if (parsed.quizDurationMinutes !== undefined) quizDurationMinutes = parsed.quizDurationMinutes;
        if (parsed.publishStartDate) publishStartDate = parsed.publishStartDate;
        if (parsed.publishStartTime) publishStartTime = parsed.publishStartTime;
      }
    } catch {
      if (item.description.includes("2nd_secondary") || item.description.includes("الثاني الثانوي")) {
        academicYear = "2nd_secondary";
      } else if (item.description.includes("3rd_secondary") || item.description.includes("الثالث الثانوي")) {
        academicYear = "3rd_secondary";
      } else if (item.description.includes("1st_secondary") || item.description.includes("الأول الثانوي")) {
        academicYear = "1st_secondary";
      }
    }
  }

  return {
    id: item.id,
    academicYear,
    date: item.starts_at.slice(0, 10),
    dayName: item.title,
    time,
    contentType,
    isCancelled: Boolean(item.cancelled_at),
    isPublishedToStudents: item.is_published,
    isRecurringWeekly,
    quizDurationMinutes,
    publishStartDate,
    publishStartTime,
  };
}

function mapApiSubmission(item: ApiSubmission): AssignmentSubmission {
  return {
    id: item.id,
    assignmentId: item.assignment_id,
    studentId: item.student_id,
    studentName: item.student_name || "—",
    academicYear: "1st_secondary",
    academicYearLabel: "الصف الأول الثانوي",
    assignmentTitle: item.assignment_title || "واجب",
    lessonTitle: item.course_title || "—",
    questionPrompt: item.assignment_prompt || "—",
    studentAnswer: item.answer_text,
    submittedAt: item.submitted_at,
    maxScore: item.max_score || 100,
    aiScore: item.ai_score || 0,
    finalScore: item.final_score || 0,
    teacherFeedback: item.teacher_feedback || undefined,
    aiFeedbackSummary: item.ai_feedback || "",
    criteriaScores: [],
    status: item.status === "approved" ? "approved" : item.status === "graded" ? "graded" : "needs_review",
  };
}

// ============================================================================
// DEDUPLICATION & SANITIZATION UTILITIES
// ============================================================================

/**
 * Robust notification deduplicator using full-content composite signature.
 * Prevents false positives caused by truncated prefixes while guaranteeing 
 * strictly unique entries.
 */
export function deduplicateNotifications(list: NotificationItem[]): NotificationItem[] {
  if (!Array.isArray(list)) return [];
  const seenIds = new Set<string>();
  const seenSignatures = new Set<string>();

  return list.filter((n) => {
    if (!n || !n.id) return false;
    
    // Composite deterministic signature
    const signature = [
      n.id,
      n.targetYear || "all",
      n.type || "system",
      (n.title || "").trim(),
      n.dueDate || "",
      n.createdAt || "",
      (n.message || "").trim(),
    ].join("::");

    if (seenIds.has(n.id) || seenSignatures.has(signature)) {
      return false;
    }

    seenIds.add(n.id);
    seenSignatures.add(signature);
    return true;
  });
}

// sanitizeUser was removed: identity and credentials never round-trip through
// the browser. The server session is the only source of authentication state.

// ============================================================================
// 1. AUTH & USER SERVICE (Server session is the ONLY source of identity)
// ============================================================================
export const authService = {
  async getRegisteredUsers(): Promise<never[]> {
    return [];
  },

  async getCurrentUser(): Promise<CurrentUser | null> {
    try {
      const apiUser = await apiRequest<ApiUser>("/auth/me");
      markBrowserSessionActive(true);
      return mapApiUser(apiUser);
    } catch (err: unknown) {
      // ONLY genuine 401 Unauthenticated means the session is expired or invalid
      if (err instanceof ApiClientError && err.status === 401) {
        markBrowserSessionActive(false);
        return null;
      }
      // 403 Forbidden is an authorization error, NOT an unauthenticated session!
      // 502/503/Network failures are temporary outages; preserve session data and rethrow
      throw err;
    }
  },

  async login(email: string, pass: string, institutionSlug = "demo"): Promise<{ success: boolean; user?: CurrentUser; error?: string }> {
    const cleanEmail = (email || "").trim().toLowerCase();
    const cleanPass = (pass || "").trim();

    try {
      const result = await apiRequest<{ user: ApiUser; expires_at: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: cleanEmail, password: cleanPass, institution_slug: institutionSlug }),
      });
      const user = mapApiUser(result.user);
      markBrowserSessionActive(true);
      if (typeof localStorage !== "undefined") {
        const targetTab = user.role === "student" ? "GeneralHome" : "LessonManagement";
        localStorage.setItem("lms_active_tab", targetTab);
      }
      window.dispatchEvent(new Event("lms_user_updated"));
      return { success: true, user };
    } catch (error: unknown) {
      const message = error instanceof ApiClientError
        ? error.message
        : "تعذر تسجيل الدخول. تحقق من الاتصال وبيانات الحساب ثم حاول مرة أخرى.";
      return { success: false, error: message };
    }
  },

  async register(userData: {
    name: string;
    email: string;
    password: string;
    institutionSlug?: string;
    academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
    studentPhone?: string;
    guardianPhone?: string;
    nationalId?: string;
    governorate: string;
    schoolName: string;
    gender: "MALE" | "FEMALE";
    religion: "MUSLIM" | "CHRISTIAN" | "OTHER" | "PREFER_NOT_TO_SAY";
  }): Promise<{ success: boolean; user?: CurrentUser; error?: string }> {
    const cleanEmail = (userData.email || "").trim().toLowerCase();

    // 1. Try FastAPI backend API
    try {
      const result = await apiRequest<{ user: ApiUser; expires_at: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          display_name: userData.name,
          email: cleanEmail,
          password: userData.password,
          institution_slug: userData.institutionSlug || "demo",
          grade_level: {
            "1st_secondary": "SECONDARY_1",
            "2nd_secondary": "SECONDARY_2",
            "3rd_secondary": "SECONDARY_3",
          }[userData.academicYear],
          student_phone: userData.studentPhone || null,
          guardian_phone: userData.guardianPhone || null,
          national_id: userData.nationalId || null,
          governorate: userData.governorate,
          school_name: userData.schoolName,
          gender: userData.gender,
          religion: userData.religion,
        }),
      });
      const user = mapApiUser(result.user);
      markBrowserSessionActive(true);
      if (typeof localStorage !== "undefined") {
        const targetTab = user.role === "student" ? "GeneralHome" : "LessonManagement";
        localStorage.setItem("lms_active_tab", targetTab);
      }
      window.dispatchEvent(new Event("lms_user_updated"));
      return { success: true, user };
    } catch (error: unknown) {
      const message = error instanceof ApiClientError
        ? error.message
        : "تعذر إنشاء الحساب. تحقق من الاتصال والبيانات ثم حاول مرة أخرى.";
      return { success: false, error: message };
    }
  },

  async logout(): Promise<void> {
    try {
      await apiRequest<void>("/auth/logout", { method: "POST" });
    } catch {
      // Logout is local-first so an unavailable server cannot trap the user in the UI.
    }
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("lms_active_tab", "Landing");
    }
    if (typeof window !== "undefined") {
      markBrowserSessionActive(false);
      window.location.hash = "";
      window.dispatchEvent(new Event("lms_user_updated"));
    }
  },
};

// ============================================================================
// 2. NOTIFICATIONS SERVICE
// ============================================================================
export const notificationService = {
  async getNotifications(): Promise<NotificationItem[]> {
    const result = await apiRequest<ApiNotification[]>("/notifications");
    return Array.isArray(result) ? deduplicateNotifications(result.map(mapApiNotification)) : [];
  },

  async saveNotification(item: NotificationItem): Promise<NotificationItem[]> {
    await apiRequest<ApiNotification[]>("/notifications/broadcast", {
      method: "POST",
      body: JSON.stringify({
        kind: item.type,
        title: item.title,
        message: item.message,
        action_url: item.actionTab ? `#${item.actionTab}` : item.actionUrl,
        dedup_key: item.id,
        scheduled_for: item.createdAt.includes("T") ? item.createdAt : undefined,
      }),
    });
    return this.getNotifications();
  },

  async saveNotifications(list: NotificationItem[]): Promise<void> {
    for (const item of deduplicateNotifications(list)) await this.saveNotification(item);
  },

  async markAsRead(id: string): Promise<NotificationItem[]> {
    await apiRequest(`/notifications/${id}/read`, { method: "POST" });
    return this.getNotifications();
  },
};

// ============================================================================
// 3. CALENDAR & SCHEDULE SERVICE
// ============================================================================
export const calendarService = {
  async getCalendarEvents(): Promise<CalendarScheduleEvent[]> {
    const result = await apiRequest<ApiCalendarEvent[]>("/calendar");
    return result.map(mapApiCalendarEvent);
  },

  async saveCalendarEvent(event: CalendarScheduleEvent): Promise<CalendarScheduleEvent[]> {
    const startsAt = new Date(`${event.date}T${parseScheduleClock(event.time)}:00`).toISOString();
    const metaPayload = {
      academicYear: event.academicYear || "1st_secondary",
      isRecurringWeekly: event.isRecurringWeekly,
      quizDurationMinutes: event.quizDurationMinutes,
      publishStartDate: event.publishStartDate,
      publishStartTime: event.publishStartTime,
    };
    const payload = {
      title: event.dayName,
      description: JSON.stringify(metaPayload),
      event_type: event.contentType,
      starts_at: startsAt,
      ends_at: null,
      is_published: event.isPublishedToStudents !== false,
    };
    const isServerId = !event.id.startsWith("evt_");
    await apiRequest<ApiCalendarEvent>(isServerId ? `/calendar/${event.id}` : "/calendar", {
      method: isServerId ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    return this.getCalendarEvents();
  },

  async cancelCalendarEvent(dateStr: string, academicYear: string): Promise<CalendarScheduleEvent[]> {
    const current = await this.getCalendarEvents();
    const normDate = (dateStr || "").split("T")[0];
    await Promise.all(
      current
        .filter((event) => event.date === normDate && (event.academicYear === academicYear || event.academicYear === "all"))
        .filter((event) => !event.isCancelled)
        .map((event) => apiRequest(`/calendar/${event.id}/cancel`, { method: "POST" })),
    );
    return this.getCalendarEvents();
  },

  async getNotificationSchedules(): Promise<NotificationSchedule[]> {
    try {
      const stored = localStorage.getItem("lms_notification_schedules_v1");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // Ignore corrupt browser-only schedule data and return an empty collection.
    }
    return [];
  },

  async saveNotificationSchedules(schedules: NotificationSchedule[]): Promise<void> {
    try {
      localStorage.setItem("lms_notification_schedules_v1", JSON.stringify(schedules));
      window.dispatchEvent(new Event("lms_schedule_updated"));
    } catch {
      // Browser storage can be unavailable in private or restricted contexts.
    }
  },
};

function parseScheduleClock(value: string): string {
  const match = value.match(/(\d{1,2})(?::(\d{2}))?/);
  if (!match) return "18:00";
  let hour = Number(match[1]);
  const minute = match[2] || "00";
  if (value.includes("م") && hour < 12) hour += 12;
  if (value.includes("ص") && hour === 12) hour = 0;
  return `${String(Math.min(hour, 23)).padStart(2, "0")}:${minute}`;
}

// ============================================================================
// 4. COURSES & ENROLLMENT SERVICE
// ============================================================================
export const courseService = {
  async getCourses(): Promise<Course[]> {
    const result = await apiRequest<{ items: ApiCourse[] }>("/courses?page=1&page_size=100");
    return Array.isArray(result.items) ? result.items.map(mapApiCourse) : [];
  },

  async saveCourses(courses: Course[]): Promise<void> {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("lms_courses_v2", JSON.stringify(courses));
      window.dispatchEvent(new Event("lms_courses_updated"));
    }
  },

  async getEnrolledCourseIds(): Promise<string[]> {
    const result = await apiRequest<ApiEnrollment[]>("/courses/me/enrollments");
    return Array.isArray(result) ? result.map((enrollment) => enrollment.course_id) : [];
  },

  async enrollCourse(courseId: string): Promise<string[]> {
    await apiRequest(`/courses/${courseId}/enroll`, { method: "POST" });
    return this.getEnrolledCourseIds();
  },

  async getLessonProgress(): Promise<ApiLessonProgress[]> {
    return apiRequest<ApiLessonProgress[]>("/progress/me");
  },

  async completeLesson(lessonId: string): Promise<ApiLessonProgress> {
    return apiRequest<ApiLessonProgress>(`/progress/lessons/${lessonId}/complete`, { method: "POST" });
  },

  async createCourse(payload: { code: string; title: string; description?: string; price_egp?: number }): Promise<ApiCourse> {
    return apiRequest<ApiCourse>("/courses", { method: "POST", body: JSON.stringify(payload) });
  },

  async getCourseContent(courseId: string): Promise<ApiCourse> {
    return apiRequest<ApiCourse>(`/courses/${courseId}`);
  },

  async addModule(courseId: string, payload: { title: string; position: number }): Promise<ApiCourse["modules"][number]> {
    return apiRequest<ApiCourse["modules"][number]>(`/courses/${courseId}/modules`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async addLesson(moduleId: string, payload: {
    title: string;
    kind: "video" | "article" | "live";
    position: number;
    content?: string;
    video_asset_key?: string;
    video_duration_seconds?: number;
    price_egp?: number;
  }): Promise<{ id: string }> {
    return apiRequest<{ id: string }>(`/modules/${moduleId}/lessons`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async reindexLesson(lessonId: string): Promise<{ status: string; lesson_id: string }> {
    return apiRequest<{ status: string; lesson_id: string }>(`/lessons/${lessonId}/reindex`, {
      method: "POST",
    });
  },

  async getLessonIndexingStatus(lessonId: string): Promise<{ status: "not_indexed" | "in_progress" | "indexed" | "failed"; indexed_chunks_count: number; error?: string }> {
    return apiRequest<{ status: "not_indexed" | "in_progress" | "indexed" | "failed"; indexed_chunks_count: number; error?: string }>(`/lessons/${lessonId}/indexing-status`);
  },

  async getLessonTranscript(lessonId: string): Promise<{
    lesson_id: string;
    transcript_id?: string;
    status: string;
    language: string;
    duration_seconds: number;
    full_text: string;
    provider?: string;
    completed_at?: string;
  }> {
    return apiRequest(`/lessons/${lessonId}/transcript`);
  },

  async getLessonSegments(lessonId: string, q?: string): Promise<{
    lesson_id: string;
    count: number;
    segments: Array<{
      id: string;
      sequence: number;
      start_time: number;
      end_time: number;
      time_formatted: string;
      text: string;
    }>;
  }> {
    const queryStr = q ? `?q=${encodeURIComponent(q)}` : "";
    return apiRequest(`/lessons/${lessonId}/transcript/segments${queryStr}`);
  },

  async askAIAboutLesson(lessonId: string, question: string): Promise<{
    answer: string;
    is_grounded: boolean;
    citations: Array<{
      chunk_id: string;
      start_time: number;
      end_time: number;
      time_formatted: string;
      text_snippet: string;
    }>;
  }> {
    return apiRequest(`/lessons/${lessonId}/ai/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
  },

  async getLessonAISummary(lessonId: string): Promise<{
    title: string;
    full_overview: string;
    total_duration_sec: number;
    language: string;
    sections: Array<{
      time_range: string;
      start_time: number;
      end_time: number;
      summary_snippet: string;
    }>;
  }> {
    return apiRequest(`/lessons/${lessonId}/ai/summary`);
  },

  async reindexAllCourseLessons(courseId: string): Promise<{ queued_lessons: number; skipped: Array<{ lesson_id: string; reason: string }> }> {
    return apiRequest<{ queued_lessons: number; skipped: Array<{ lesson_id: string; reason: string }> }>(`/courses/${courseId}/reindex-all`, {
      method: "POST",
    });
  },

  async uploadLessonVideo(
    lessonId: string,
    file: File,
    onProgress?: (percent: number) => void,
    onXhrCreated?: (xhr: XMLHttpRequest) => void
  ): Promise<{ id: string; video_url: string; filename: string }> {
    const formData = new FormData();
    formData.append("file", file);
    return uploadWithProgress<{ id: string; video_url: string; filename: string }>(
      `/lessons/${lessonId}/video`,
      formData,
      onProgress,
      0,
      onXhrCreated
    );
  },

  async deleteLesson(moduleId: string, lessonId: string): Promise<void> {
    await apiRequest<void>(`/modules/${moduleId}/lessons/${lessonId}`, { method: "DELETE" });
  },
};

// ============================================================================
// 5. VIDEO TELEMETRY & ANALYTICS SERVICE
// ============================================================================
export const analyticsService = {
  async getVideoLogs(): Promise<StudentVideoWatchLog[]> {
    return [];
  },

  async logVideoWatch(log: StudentVideoWatchLog): Promise<void> {
    void log;
  },
};

// ============================================================================
// 6. SUBMISSIONS & EXAM SERVICE
// ============================================================================
export const submissionService = {
  async getStudentSubmissions(): Promise<AssignmentSubmission[]> {
    const result = await apiRequest<ApiSubmission[]>("/submissions/me");
    return Array.isArray(result) ? result.map(mapApiSubmission) : [];
  },

  async getTeacherSubmissions(): Promise<AssignmentSubmission[]> {
    const result = await apiRequest<ApiSubmission[]>("/submissions");
    return Array.isArray(result) ? result.map(mapApiSubmission) : [];
  },

  async saveSubmission(sub: AssignmentSubmission): Promise<AssignmentSubmission[]> {
    throw new ApiClientError("UNSUPPORTED_OPERATION", `Submission ${sub.id} must be created through its assignment endpoint`, 501);
  },

  async gradeSubmission(id: string, finalScore: number, teacherFeedback: string, approve = true): Promise<AssignmentSubmission> {
    const result = await apiRequest<ApiSubmission>(`/submissions/${id}/grade`, {
      method: "POST",
      body: JSON.stringify({ final_score: finalScore, teacher_feedback: teacherFeedback, approve }),
    });
    return mapApiSubmission(result);
  },
};

type ApiManagedUser = Pick<ApiUser, "id" | "email" | "display_name" | "role" | "is_active" | "created_at">;

export const userService = {
  async getStudents(): Promise<ApiManagedUser[]> {
    const res = await apiRequest<ApiManagedUser[]>("/users?role=student");
    return Array.isArray(res) ? res : [];
  },

  async toggleBlock(studentId: string): Promise<ApiManagedUser> {
    return apiRequest<ApiManagedUser>(`/users/${studentId}/block`, { method: "POST" });
  },

  async deleteStudent(studentId: string): Promise<void> {
    await apiRequest<void>(`/users/${studentId}`, { method: "DELETE" });
  },
};

export const systemService = {
  async getASRConfig(): Promise<{ kaggle_asr_url: string; mode: string; provider: string }> {
    return apiRequest<{ kaggle_asr_url: string; mode: string; provider: string }>("/system/asr-config");
  },

  async updateASRConfig(kaggleAsrUrl: string): Promise<{ kaggle_asr_url: string; mode: string; provider: string }> {
    return await apiRequest<{ kaggle_asr_url: string; mode: string; provider: string }>("/system/asr-config", {
      method: "POST",
      body: JSON.stringify({ kaggle_asr_url: kaggleAsrUrl }),
    });
  },
};

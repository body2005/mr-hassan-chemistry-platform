import {
  apiRequest,
  apiUrl,
  uploadWithProgress,
  ApiClientError,
  markBrowserSessionActive,
  isSessionKnownInvalid,
  setApiAuthScope,
  clearApiCache,
  invalidateApiCache,
  getCachedData,
  setCachedData,
} from "./apiClient";
import type { StudentEntitlement } from "./paymentService";
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
      /** The private storage key is never serialized by the API. */
      has_video?: boolean;
      video_url?: string | null;
      video_duration_seconds: number | null;
      price_egp?: number;
      materialization_status?: string;
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

export { apiRequest, ApiClientError, clearApiCache, invalidateApiCache };

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
      governorate: user.governorate || "",
      schoolName: user.school_name || "",
      gender: user.gender || undefined,
      religion: user.religion || undefined,
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
        .map((lesson) => {
          const isRevision = Boolean(
            (lesson.content && lesson.content.includes("<!--is_revision:true-->")) ||
            lesson.title.includes("مراجعة") ||
            module.title.includes("مراجعة")
          );
          return {
            id: lesson.id,
            moduleId: module.id,
            unitTitle: module.title,
            isRevision,
            courseId: course.id,
            academicYear: "1st_secondary" as const,
            title: lesson.title,
            description: (lesson.content || "").replace("<!--is_revision:true-->", "").trim(),
            durationMinutes: Math.ceil((lesson.video_duration_seconds || 0) / 60),
            durationFormatted: lesson.video_duration_seconds
              ? `${Math.ceil(lesson.video_duration_seconds / 60)} دقيقة`
              : "",
            // Playback entry points only: the API never exposes the private
            // storage key. External URLs entered by the teacher stay as-is;
            // native uploads resolve through the short-lived token endpoint.
            videoUrl: lesson.video_url || "",
            requiresProtectedPlayback: Boolean(
              lesson.has_video && lesson.video_url && lesson.video_url.startsWith("/api/v1/lessons/"),
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
            materialization_status: lesson.materialization_status || "NOT_INDEXED",
          };
        }),
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
    assessments: [],
  };
}

function mapApiNotification(item: ApiNotification): NotificationItem {
  const isPayment = item.kind === "payment" || (item.action_url && item.action_url.includes("/payments/orders/"));
  const type: NotificationItem["type"] = isPayment
    ? "payment"
    : ["assignment", "quiz", "warning"].includes(item.kind)
    ? (item.kind as NotificationItem["type"])
    : "system";

  let paymentOrderId: string | undefined = undefined;
  if (isPayment && item.action_url) {
    const match = item.action_url.match(/\/payments\/orders\/([0-9a-fA-F-]+)/);
    if (match) paymentOrderId = match[1];
  }

  // Detect target academic year from content/action_url so teachers & students can filter properly
  let targetYear: NotificationItem["targetYear"] = "all";
  const combinedText = `${item.title || ""} ${item.message || ""} ${item.action_url || ""}`;
  if (combinedText.includes("1st_secondary") || combinedText.includes("الأول الثانوي")) {
    targetYear = "1st_secondary";
  } else if (combinedText.includes("2nd_secondary") || combinedText.includes("الثاني الثانوي")) {
    targetYear = "2nd_secondary";
  } else if (combinedText.includes("3rd_secondary") || combinedText.includes("الثالث الثانوي")) {
    targetYear = "3rd_secondary";
  }

  return {
    id: item.id,
    title: item.title,
    message: item.message,
    type,
    targetYear,
    createdAt: item.created_at,
    read: Boolean(item.read_at),
    dueDate: item.scheduled_for || undefined,
    actionUrl: item.action_url || undefined,
    actionTab: isPayment ? "PaymentManagement" : (item.action_url?.replace(/^#/, "") as NotificationItem["actionTab"]),
    paymentOrderId,
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
  let customMessage: string | undefined = undefined;

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
        if (parsed.customMessage) customMessage = parsed.customMessage;
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
    customMessage,
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
    hasFile: !!item.object_key,
    fileUrl: item.object_key ? apiUrl(`/submissions/${item.id}/file`) : undefined,
    version: item.version,
    submittedAt: item.submitted_at,
    maxScore: item.max_score || 100,
    finalScore: item.final_score || 0,
    teacherFeedback: item.teacher_feedback || undefined,
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
// 0. BOOTSTRAP SERVICE (Unified 1-roundtrip initial startup)
// ============================================================================
export interface BootstrapData {
  authenticated: boolean;
  user: CurrentUser | null;
  unread_notifications_count: number;
  notifications: NotificationItem[];
  courses: Course[];
  enrolledCourseIds: string[];
  entitlements: StudentEntitlement[];
  settings: Record<string, any>;
}

export const bootstrapService = {
  async getBootstrap(): Promise<BootstrapData> {
    // Pages with no session footprint (e.g. the login screen on a fresh
    // browser) must stay silent: no bootstrap request, no 401 churn. The
    // HttpOnly session cookie cannot be introspected from JS, so the persisted
    // session token (written on every successful login) is the "maybe logged
    // in" signal. When it is absent AND the client already knows the session
    // is invalid, resolve as anonymous without touching the network.
    if (
      typeof localStorage !== "undefined" &&
      !localStorage.getItem("lms_session_token") &&
      isSessionKnownInvalid()
    ) {
      markBrowserSessionActive(false);
      setApiAuthScope("anonymous");
      return {
        authenticated: false,
        user: null,
        unread_notifications_count: 0,
        notifications: [],
        courses: [],
        enrolledCourseIds: [],
        entitlements: [],
        settings: {},
      };
    }
    try {
      const res = await apiRequest<{
        authenticated: boolean;
        user: ApiUser | null;
        unread_notifications_count: number;
        notifications: ApiNotification[];
        courses: ApiCourse[];
        enrolled_course_ids: string[];
        entitlements: any[];
        settings: Record<string, any>;
      }>("/bootstrap", { cacheTtlMs: 15_000 });

      if (!res.authenticated || !res.user) {
        markBrowserSessionActive(false);
        setApiAuthScope("anonymous");
        return {
          authenticated: false,
          user: null,
          unread_notifications_count: 0,
          notifications: [],
          courses: [],
          enrolledCourseIds: [],
          entitlements: [],
          settings: res.settings || {},
        };
      }

      markBrowserSessionActive(true);
      const user = mapApiUser(res.user);
      setApiAuthScope(user.id);

      if (typeof localStorage !== "undefined") {
        localStorage.setItem("lms_cached_user", JSON.stringify(user));
      }

      // Prepopulate cache for /auth/me so any subsequent call hits cache in 0ms.
      // Keys must match the apiRequest cache format "METHOD:url" exactly.
      setCachedData(`GET:${apiUrl("/auth/me")}`, res.user, 30_000);

      // Map notifications
      const notifs = Array.isArray(res.notifications)
        ? deduplicateNotifications(res.notifications.map(mapApiNotification))
        : [];
      setCachedData(`GET:${apiUrl("/notifications")}`, res.notifications || [], 10_000);

      // Map courses — key must match getCourses' real request URL (/courses?page=1&page_size=100)
      const mappedCourses = Array.isArray(res.courses) ? res.courses.map(mapApiCourse) : [];
      setCachedData(
        `GET:${apiUrl("/courses?page=1&page_size=100")}`,
        { items: res.courses || [], pagination: { total: mappedCourses.length, page: 1, page_size: 100, pages: 1 } },
        30_000
      );
      if (typeof localStorage !== "undefined" && mappedCourses.length > 0) {
        localStorage.setItem("lms_courses_v2", JSON.stringify(mappedCourses));
      }

      // Enrolled courses
      const enrolled = Array.isArray(res.enrolled_course_ids) ? res.enrolled_course_ids : [];
      setCachedData(
        `GET:${apiUrl("/courses/me/enrollments")}`,
        (res.enrolled_course_ids || []).map((cid) => ({ course_id: cid, status: "active" })),
        60_000
      );

      // Entitlements
      const entitlements = Array.isArray(res.entitlements) ? res.entitlements : [];
      setCachedData(`GET:${apiUrl("/payments/me/entitlements")}`, entitlements, 60_000);

      return {
        authenticated: true,
        user,
        unread_notifications_count: res.unread_notifications_count || 0,
        notifications: notifs,
        courses: mappedCourses,
        enrolledCourseIds: enrolled,
        entitlements,
        settings: res.settings || {},
      };
    } catch (err) {
      console.warn("Bootstrap request failed, falling back to local cached identity", err);
      const cached = authService.getCachedUser();
      return {
        authenticated: Boolean(cached),
        user: cached,
        unread_notifications_count: 0,
        notifications: [],
        courses: courseService.getCachedCourses(),
        enrolledCourseIds: [],
        entitlements: [],
        settings: {},
      };
    }
  },
};

// ============================================================================
// 1. AUTH & USER SERVICE (Server session is the ONLY source of identity)
// ============================================================================
let meInFlight: Promise<CurrentUser | null> | null = null;

export const authService = {
  async getRegisteredUsers(): Promise<never[]> {
    return [];
  },

  getCachedUser(): CurrentUser | null {
    if (typeof localStorage === "undefined") return null;
    try {
      const raw = localStorage.getItem("lms_cached_user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  async getCurrentUser(): Promise<CurrentUser | null> {
    // Skip the probe entirely when a previous request already proved the
    // session is gone. Re-probing only generates duplicate 401/refresh churn.
    if (isSessionKnownInvalid()) {
      markBrowserSessionActive(false);
      setApiAuthScope("anonymous");
      return null;
    }
    // Concurrent callers (mount + sync events) share one in-flight /me call
    // instead of firing several identical requests in parallel.
    if (meInFlight) return meInFlight;
    meInFlight = this.getCurrentUserUncached().finally(() => {
      meInFlight = null;
    });
    return meInFlight;
  },

  async getCurrentUserUncached(): Promise<CurrentUser | null> {
    try {
      const apiUser = await apiRequest<ApiUser>("/auth/me", { cacheTtlMs: 30_000 });
      markBrowserSessionActive(true);
      setApiAuthScope(apiUser.id);
      const user = mapApiUser(apiUser);
      if (typeof localStorage !== "undefined") {
        localStorage.setItem("lms_cached_user", JSON.stringify(user));
      }
      return user;
    } catch (err: unknown) {
      // ONLY genuine 401 Unauthenticated means the session is expired or invalid
      if (err instanceof ApiClientError && err.status === 401) {
        markBrowserSessionActive(false);
        setApiAuthScope("anonymous");
        if (typeof localStorage !== "undefined") {
          localStorage.removeItem("lms_session_token");
          localStorage.removeItem("lms_cached_user");
        }
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
      const result = await apiRequest<{ user: ApiUser; expires_at: string; token?: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: cleanEmail, password: cleanPass, institution_slug: institutionSlug }),
      });
      const user = mapApiUser(result.user);
      markBrowserSessionActive(true);
      setApiAuthScope(user.id);
      clearApiCache();
      if (typeof localStorage !== "undefined") {
        if (result.token) {
          localStorage.setItem("lms_session_token", result.token);
        }
        localStorage.setItem("lms_cached_user", JSON.stringify(user));
        const targetTab = user.role === "student" ? "MyCourses" : "LessonManagement";
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
    religion?: "MUSLIM" | "CHRISTIAN" | "OTHER" | "PREFER_NOT_TO_SAY" | null;
  }): Promise<{ success: boolean; user?: CurrentUser; error?: string }> {
    const cleanEmail = (userData.email || "").trim().toLowerCase();

    // 1. Try FastAPI backend API
    try {
      const result = await apiRequest<{ user: ApiUser; expires_at: string; token?: string }>("/auth/register", {
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
          religion: userData.religion || null,
        }),
      });
      const user = mapApiUser(result.user);
      markBrowserSessionActive(true);
      setApiAuthScope(user.id);
      clearApiCache();
      if (typeof localStorage !== "undefined") {
        if (result.token) {
          localStorage.setItem("lms_session_token", result.token);
        }
        localStorage.setItem("lms_cached_user", JSON.stringify(user));
        const targetTab = user.role === "student" ? "MyCourses" : "LessonManagement";
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
    setApiAuthScope("anonymous");
    clearApiCache();
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem("lms_session_token");
      localStorage.removeItem("lms_cached_user");
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
    const result = await apiRequest<ApiNotification[]>("/notifications", { cacheTtlMs: 10_000 });
    return Array.isArray(result) ? deduplicateNotifications(result.map(mapApiNotification)) : [];
  },

  async saveNotification(item: NotificationItem): Promise<NotificationItem[]> {
    const actionUrl = item.actionUrl || (item.actionTab ? `#${item.actionTab}` : undefined);
    const result = await apiRequest<ApiNotification[]>("/notifications/broadcast", {
      method: "POST",
      body: JSON.stringify({
        kind: item.type,
        title: item.title,
        message: item.message,
        action_url: item.targetYear ? `${actionUrl || "#Notifications"}?grade=${item.targetYear}` : actionUrl,
        dedup_key: item.id,
        scheduled_for: item.createdAt.includes("T") ? item.createdAt : undefined,
      }),
    });
    invalidateApiCache("/notifications");
    const mappedNew = Array.isArray(result) ? result.map(mapApiNotification) : [];
    const all = await this.getNotifications();
    const merged = deduplicateNotifications([...mappedNew, ...all]);
    window.dispatchEvent(new Event("lms_notifications_updated"));
    return merged;
  },

  async saveNotifications(list: NotificationItem[]): Promise<void> {
    for (const item of deduplicateNotifications(list)) await this.saveNotification(item);
  },

  async markAsRead(id: string): Promise<NotificationItem[]> {
    await apiRequest(`/notifications/${id}/read`, { method: "POST" });
    invalidateApiCache("/notifications");
    return this.getNotifications();
  },
};

// ============================================================================
// 3. CALENDAR & SCHEDULE SERVICE
// ============================================================================
export const calendarService = {
  async getCalendarEvents(): Promise<CalendarScheduleEvent[]> {
    const result = await apiRequest<ApiCalendarEvent[]>("/calendar", { cacheTtlMs: 30_000 });
    const mapped = result.map(mapApiCalendarEvent);
    try {
      localStorage.setItem("lms_calendar_events_cache", JSON.stringify(mapped));
    } catch {}
    return mapped;
  },

  async saveCalendarEvent(event: CalendarScheduleEvent): Promise<CalendarScheduleEvent[]> {
    const startsAt = new Date(`${event.date}T${parseScheduleClock(event.time)}:00`).toISOString();
    const metaPayload = {
      academicYear: event.academicYear || "1st_secondary",
      isRecurringWeekly: event.isRecurringWeekly,
      quizDurationMinutes: event.quizDurationMinutes,
      publishStartDate: event.publishStartDate,
      publishStartTime: event.publishStartTime,
      customMessage: event.customMessage,
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
    invalidateApiCache("/calendar");
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
    invalidateApiCache("/calendar");
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
let composedCoursesInFlight: Promise<Course[]> | null = null;

export const courseService = {
  async getCourses(options?: { skipCache?: boolean }): Promise<Course[]> {
    const composedKey = "composed:/courses";
    if (!options?.skipCache) {
      const cached = getCachedData<Course[]>(composedKey);
      if (cached) return cached;
      if (composedCoursesInFlight) return composedCoursesInFlight;
    }

    const fetchPromise = (async () => {
      const result = await apiRequest<{ items: ApiCourse[] }>("/courses?page=1&page_size=100", {
        cacheTtlMs: 60_000,
        skipCache: options?.skipCache,
      });
      const courses = Array.isArray(result.items) ? result.items.map(mapApiCourse) : [];
      setCachedData(composedKey, courses, 60_000);

      // Asynchronously enrich courses with assessments in the background without blocking the course list
      void Promise.all(
        courses.map(async (course) => {
          try {
            const data = await courseService.getCourseAssessments(course.id);
            course.assessments = [
              ...data.quizzes.map((q) => ({
                id: q.id,
                kind: "quiz" as const,
                title: q.title,
                lessonId: q.lesson_id,
                moduleId: q.module_id,
                durationMinutes: q.duration_seconds ? Math.ceil(q.duration_seconds / 60) : undefined,
                dueLabel: q.ends_at,
                attemptsUsed: q.attempts_used,
                attemptsAllowed: q.attempts_allowed,
                accessible: q.accessible,
              })),
              ...data.assignments.map((a) => ({
                id: a.id,
                kind: "assignment" as const,
                title: a.title,
                lessonId: a.lesson_id,
                moduleId: a.module_id,
                maxScore: a.max_score,
                dueLabel: a.due_at,
                accessible: a.accessible,
              })),
            ];
          } catch {
            course.assessments = [];
          }
        }),
      ).then(() => {
        setCachedData(composedKey, courses, 60_000);
      });

      return courses;
    })();

    composedCoursesInFlight = fetchPromise.finally(() => {
      composedCoursesInFlight = null;
    });

    return composedCoursesInFlight;
  },

  getCachedCourses(): Course[] {
    const cached = getCachedData<Course[]>("composed:/courses");
    if (cached && Array.isArray(cached) && cached.length > 0) return cached;
    return [];
  },

  async saveCourses(courses: Course[]): Promise<void> {
    invalidateApiCache("/courses");
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("lms_courses_v2", JSON.stringify(courses));
      window.dispatchEvent(new Event("lms_courses_updated"));
    }
  },

  async getEnrolledCourseIds(): Promise<string[]> {
    const result = await apiRequest<ApiEnrollment[]>("/courses/me/enrollments", { cacheTtlMs: 60_000 });
    return Array.isArray(result) ? result.map((enrollment) => enrollment.course_id) : [];
  },

  async enrollCourse(courseId: string): Promise<string[]> {
    await apiRequest(`/courses/${courseId}/enroll`, { method: "POST" });
    invalidateApiCache("/courses");
    return this.getEnrolledCourseIds();
  },

  async getLessonProgress(): Promise<ApiLessonProgress[]> {
    return apiRequest<ApiLessonProgress[]>("/progress/me", { cacheTtlMs: 15_000 });
  },

  async completeLesson(lessonId: string): Promise<ApiLessonProgress> {
    const res = await apiRequest<ApiLessonProgress>(`/progress/lessons/${lessonId}/complete`, { method: "POST" });
    invalidateApiCache("/progress");
    invalidateApiCache("/courses");
    return res;
  },

  async createCourse(payload: { code: string; title: string; description?: string; price_egp?: number }): Promise<ApiCourse> {
    const res = await apiRequest<ApiCourse>("/courses", { method: "POST", body: JSON.stringify(payload) });
    invalidateApiCache("/courses");
    return res;
  },

  async getCourseContent(courseId: string): Promise<ApiCourse> {
    return apiRequest<ApiCourse>(`/courses/${courseId}`, { cacheTtlMs: 60_000 });
  },

  /** Server-side shape of a published assessment the student can attempt. */
  async getCourseAssessments(courseId: string): Promise<{
    course_id: string;
    lessons: Array<{ id: string; title: string; accessible: boolean }>;
    quizzes: Array<{
      id: string;
      kind: "quiz";
      title: string;
      module_id: string | null;
      lesson_id: string | null;
      duration_seconds: number | null;
      starts_at: string | null;
      ends_at: string | null;
      attempts_allowed: number;
      attempts_used: number;
      accessible: boolean;
    }>;
    assignments: Array<{
      id: string;
      kind: "assignment";
      title: string;
      module_id: string | null;
      lesson_id: string | null;
      due_at: string | null;
      max_score: number;
      accessible: boolean;
    }>;
  }> {
    return apiRequest(`/courses/${courseId}/assessments`, { cacheTtlMs: 60_000 });
  },

  /** Publish a real quiz to the server: questions -> quiz -> publish. */
  async publishQuizToServer(payload: {
    course_id: string;
    module_id?: string;
    lesson_id?: string;
    title: string;
    duration_minutes?: number;
    starts_at?: string | null;
    ends_at?: string | null;
    questions: Array<{
      question_text: string;
      question_type: string;
      options?: Array<{ key: string; text: string; is_correct: boolean }>;
      correct_answer?: string | null;
      points?: number;
    }>;
  }): Promise<{ quiz_id: string }> {
    const questionIds: string[] = [];
    for (const q of payload.questions) {
      const created = await apiRequest<{ id: string }>("/questions", {
        method: "POST",
        body: JSON.stringify({
          course_id: payload.course_id,
          question_type: q.question_type,
          prompt: q.question_text,
          options: q.options ?? null,
          correct_answer: q.correct_answer ?? null,
          points: q.points ?? 1,
        }),
      });
      questionIds.push(created.id);
    }
    const quiz = await apiRequest<{ id: string }>("/quizzes", {
      method: "POST",
      body: JSON.stringify({
        course_id: payload.course_id,
        quiz_title: payload.title,
        module_id: payload.module_id || null,
        lesson_id: payload.lesson_id || null,
        duration_seconds: payload.duration_minutes ? payload.duration_minutes * 60 : null,
        starts_at: payload.starts_at || null,
        ends_at: payload.ends_at || null,
        question_ids: questionIds,
      }),
    });
    await apiRequest(`/quizzes/${quiz.id}/publish`, {
      method: "POST",
    });
    invalidateApiCache("/courses");
    return { quiz_id: quiz.id };
  },

  /** Publish a real assignment to the server. */
  async publishAssignmentToServer(payload: {
    course_id: string;
    module_id?: string;
    lesson_id?: string;
    title: string;
    prompt: string;
    due_at?: string | null;
    max_score?: number;
  }): Promise<{ assignment_id: string }> {
    const created = await apiRequest<{ id: string }>("/assignments", {
      method: "POST",
      body: JSON.stringify({
        course_id: payload.course_id,
        assignment_title: payload.title,
        prompt: payload.prompt || payload.title,
        due_at: payload.due_at || null,
        max_score: payload.max_score ?? 100,
        module_id: payload.module_id || null,
        lesson_id: payload.lesson_id || null,
      }),
    });
    await apiRequest(`/assignments/${created.id}/publish`, {
      method: "POST",
    });
    invalidateApiCache("/courses");
    return { assignment_id: created.id };
  },

  async addModule(courseId: string, payload: { title: string; position: number }): Promise<ApiCourse["modules"][number]> {
    const res = await apiRequest<ApiCourse["modules"][number]>(`/courses/${courseId}/modules`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    invalidateApiCache("/courses");
    return res;
  },

  async addLesson(moduleId: string, payload: {
    title: string;
    kind: "video" | "article" | "live";
    position: number;
    content?: string;
    external_video_url?: string;
    video_duration_seconds?: number;
    price_egp?: number;
  }): Promise<{ id: string }> {
    const res = await apiRequest<{ id: string }>(`/modules/${moduleId}/lessons`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    invalidateApiCache("/courses");
    return res;
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
    invalidateApiCache("/courses");
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
    const result = await apiRequest<ApiSubmission[]>("/submissions/me", { cacheTtlMs: 30_000 });
    return Array.isArray(result) ? result.map(mapApiSubmission) : [];
  },

  async getTeacherSubmissions(): Promise<AssignmentSubmission[]> {
    const result = await apiRequest<ApiSubmission[]>("/submissions", { cacheTtlMs: 30_000 });
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
    invalidateApiCache("/submissions");
    return mapApiSubmission(result);
  },
};

import { lessonAccessService } from "./paymentService";

type ApiManagedUser = Pick<
  ApiUser,
  | "id"
  | "email"
  | "display_name"
  | "role"
  | "grade_level"
  | "student_phone"
  | "guardian_phone"
  | "national_id"
  | "governorate"
  | "school_name"
  | "gender"
  | "religion"
  | "is_active"
  | "created_at"
>;

export const userService = {
  async getStudents(): Promise<ApiManagedUser[]> {
    const res = await apiRequest<ApiManagedUser[]>("/users?role=student", { cacheTtlMs: 60_000 });
    return Array.isArray(res) ? res : [];
  },

  async toggleBlock(studentId: string): Promise<ApiManagedUser> {
    const res = await apiRequest<ApiManagedUser>(`/users/${studentId}/block`, { method: "POST" });
    invalidateApiCache("/users");
    return res;
  },

  async deleteStudent(studentId: string): Promise<void> {
    await apiRequest<void>(`/users/${studentId}`, { method: "DELETE" });
    invalidateApiCache("/users");
  },
};

export const accessService = lessonAccessService;


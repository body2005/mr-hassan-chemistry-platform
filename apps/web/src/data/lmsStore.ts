import {
  AIChatSession,
  AssignmentSubmission,
  Course,
  CustomColumn,
  NotificationItem,
  StudentRecord,
  StudentProfile,
} from "../types/lms";

export const INITIAL_REGISTERED_STUDENTS: any[] = [];

export const INITIAL_STUDENT_PROFILE: StudentProfile = {
  id: "std_default",
  name: "طالب جديد",
  email: "student@lms.edu.eg",
  role: "student",
  nationalId: "",
  studentPhone: "",
  guardianPhone: "",
  age: 16,
  academicYear: "1st_secondary",
  academicYearLabel: "الصف الأول الثانوي",
  interestedSubjects: [],
  joinedDate: "2026-08-01",
};

// INITIAL_TEACHER_PROFILE was removed: no hardcoded demo teacher identity may
// exist in production code. Teacher profiles come exclusively from the API.

export const INITIAL_COURSES: Course[] = [];

export const INITIAL_NOTIFICATIONS: NotificationItem[] = [];

export const INITIAL_STUDENTS: StudentRecord[] = [];

export const INITIAL_SUBMISSIONS: AssignmentSubmission[] = [];

export const INITIAL_CUSTOM_COLUMNS: CustomColumn[] = [];

export const INITIAL_CHAT_SESSIONS: AIChatSession[] = [];

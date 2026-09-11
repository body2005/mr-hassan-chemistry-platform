import {
  AIChatSession,
  AssignmentSubmission,
  Course,
  CustomColumn,
  NotificationItem,
  StudentRecord,
  StudentProfile,
  TeacherProfile,
} from "../types/lms";

export const DEFAULT_TEACHER_USER: TeacherProfile = {
  id: "usr_teacher_hassan",
  name: "مستر حسن شعبان",
  email: "teacher@demo.com",
  role: "teacher",
  nationalId: "28501011234567",
  phone: "01001234567",
  teachingYear: "all",
  teachingYearLabel: "جميع الصفوف الثانوية",
  subject: "الكيمياء",
  contractAgreed: true,
  uploadedVideosCount: 0,
  enrolledStudentsCount: 0,
  joinedDate: "2026-01-01",
};

export const DEFAULT_STUDENT_USER: StudentProfile = {
  id: "usr_student_demo",
  name: "طالب",
  email: "student@demo.com",
  role: "student",
  nationalId: "",
  studentPhone: "",
  guardianPhone: "",
  age: 17,
  academicYear: "3rd_secondary",
  academicYearLabel: "الصف الثالث الثانوي",
  interestedSubjects: ["الكيمياء"],
  joinedDate: "2026-01-01",
};

export const INITIAL_STUDENT_PROFILE: StudentProfile = DEFAULT_STUDENT_USER;

export const INITIAL_COURSES: Course[] = [];

export const INITIAL_STUDENTS: StudentRecord[] = [];

export const INITIAL_NOTIFICATIONS: NotificationItem[] = [];

export const INITIAL_SUBMISSIONS: AssignmentSubmission[] = [];

export const INITIAL_CUSTOM_COLUMNS: CustomColumn[] = [];
export const INITIAL_CHAT_SESSIONS: AIChatSession[] = [];
export const INITIAL_REGISTERED_STUDENTS: any[] = [];

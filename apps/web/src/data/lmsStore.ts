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
  name: "أحمد محمد",
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

export const INITIAL_COURSES: Course[] = [
  {
    id: "f33b77ad-45d0-54c0-80e8-1373a52ec477",
    title: "الكيمياء - الصف الثالث الثانوي",
    subject: "الكيمياء",
    academicYear: "3rd_secondary",
    academicYearLabel: "الصف الثالث الثانوي",
    teacherName: "مستر حسن شعبان",
    teacherTitle: "معلم أول الكيمياء للثانوية العامة",
    description: "منهج الكيمياء للثانوية العامة — شرح وافٍ وتدريبات وتأهيل للامتحان النهائي.",
    thumbnailColor: "#0f392b",
    lessonsCount: 0,
    totalDurationFormatted: "0 دقيقة",
    lessons: [],
    enrolledStudentsCount: 0,
  },
  {
    id: "1d8881ce-c07d-5e2e-bd9e-a756989ad3b6",
    title: "الكيمياء - الصف الثاني الثانوي",
    subject: "الكيمياء",
    academicYear: "2nd_secondary",
    academicYearLabel: "الصف الثاني الثانوي",
    teacherName: "مستر حسن شعبان",
    teacherTitle: "معلم أول الكيمياء للثانوية العامة",
    description: "منهج الكيمياء للصف الثاني الثانوي — شرح وتدريبات واختبارات تفاعلية.",
    thumbnailColor: "#164e63",
    lessonsCount: 0,
    totalDurationFormatted: "0 دقيقة",
    lessons: [],
    enrolledStudentsCount: 0,
  },
  {
    id: "0326dbfd-5df8-5af1-8efe-4458d53977f0",
    title: "الكيمياء - الصف الأول الثانوي",
    subject: "الكيمياء",
    academicYear: "1st_secondary",
    academicYearLabel: "الصف الأول الثانوي",
    teacherName: "مستر حسن شعبان",
    teacherTitle: "معلم أول الكيمياء للثانوية العامة",
    description: "منهج الكيمياء للصف الأول الثانوي — شرح وتدريبات واختبارات تفاعلية.",
    thumbnailColor: "#065f46",
    lessonsCount: 0,
    totalDurationFormatted: "0 دقيقة",
    lessons: [],
    enrolledStudentsCount: 0,
  },
];

export const INITIAL_STUDENTS: StudentRecord[] = [
  {
    id: "a3312f94726d4098931642bb05ec609b",
    name: "أحمد محمد",
    email: "student@demo.com",
    nationalId: "",
    academicYear: "3rd_secondary",
    academicYearLabel: "الصف الثالث الثانوي",
    overallAttendanceRatio: 1.0,
    assignmentSubmissionRatio: 0,
    averageQuizScore: 0,
    homeworkSuccessRate: 0,
    quizSuccessRate: 0,
    totalOverallGrade: 0,
    lastActiveDate: "2026-09-11",
    isBlocked: false,
    customFieldValues: {},
    watchHistory: [],
  },
];

export const INITIAL_NOTIFICATIONS: NotificationItem[] = [];

export const INITIAL_SUBMISSIONS: AssignmentSubmission[] = [];

export const INITIAL_CUSTOM_COLUMNS: CustomColumn[] = [];
export const INITIAL_CHAT_SESSIONS: AIChatSession[] = [];
export const INITIAL_REGISTERED_STUDENTS: any[] = [];

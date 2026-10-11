export interface Lesson {
  id: string;
  title: string;
  duration: string;
  content: string;
  summary: string;
}

export interface Course {
  id: string;
  title: string;
  subject: string;
  description: string;
  progress: number;
  currentLesson: string;
  meta: string;
  tone: "coral" | "blue" | "green" | "purple";
  mark: string;
  lessons: Lesson[];
}

export const COURSES: Course[] = [
  {
    id: "chem-1st",
    title: "الكيمياء — الصف الأول الثانوي",
    subject: "الكيمياء",
    description: "المقرر الشامل لمادة الكيمياء للصف الأول الثانوي مع مستر حسن شعبان.",
    progress: 68,
    currentLesson: "القياس في الكيمياء وأدوات المعمل",
    meta: "الدرس 1 من 12",
    tone: "coral",
    mark: "CHEM",
    lessons: [
      {
        id: "chem_lesson_1",
        title: "القياس في الكيمياء وأدوات المعمل",
        duration: "18 دقيقة",
        summary: "أهمية القياس وأدوات المعمل واستخداماتها في التجارب الكيميائية.",
        content: `الكيمياء هي مركز العلوم. القياس في الكيمياء عملية مقارنة كمية مجهولة بكمية أخرى معلومة من نفس النوع لمعرفة عدد مرات احتواء الأولى على الثانية. ومن الأدوات المعملية: الميزان الحساس لقياس الكتلة، والمخبار المدرج لقياس حجوم السوائل، والماصة والسحاحة في عمليات المعايرة.`
      },
      {
        id: "chem_lesson_2",
        title: "الجدول الدوري والتوزيع الإلكتروني",
        duration: "22 دقيقة",
        summary: "مستويات الطاقة، أعداد الكم، وتدرج الخواص في الجدول الدوري.",
        content: `يترتب الجدول الدوري الحديث للعناصر تصاعدياً وفقاً لأعدادها الذرية وطريقة ملء مستويات الطاقة الفرعية بالإلكترونات طبقاً لمبدأ البناء التصاعدي وقاعدة هوند.`
      }
    ]
  },
  {
    id: "chem-2nd",
    title: "الكيمياء — الصف الثاني الثانوي",
    subject: "الكيمياء",
    description: "المقرر الشامل لمادة الكيمياء للصف الثاني الثانوي مع مستر حسن شعبان.",
    progress: 42,
    currentLesson: "الروابط الكيميائية ونظريات الترابط",
    meta: "الدرس 1 من 14",
    tone: "blue",
    mark: "CHEM",
    lessons: [
      {
        id: "chem_lesson_3",
        title: "الروابط الكيميائية ونظريات الترابط",
        duration: "25 دقيقة",
        summary: "الروابط الأيونية والتساهمية ونظرية تنافر أزواج الإلكترونات.",
        content: `تنشأ الرابطة الأيونية بين فلز ولا فلز نتيجة التجاذب الكهربي الاستاتيكي، بينما تنشأ الرابطة التساهمية نتيجة المشاركة الإلكترونية بين ذرات اللافلزات. وتحدد نظرية تنافر أزواج الإلكترونات الأشكال الفراغية للجزيئات.`
      }
    ]
  },
  {
    id: "chem-3rd",
    title: "الكيمياء — الصف الثالث الثانوي",
    subject: "الكيمياء",
    description: "المقرر الشامل لمادة الكيمياء للثانوية العامة مع مستر حسن شعبان.",
    progress: 81,
    currentLesson: "العناصر الانتقالية والاتزان الكيميائي",
    meta: "الدرس 1 من 12",
    tone: "green",
    mark: "CHEM",
    lessons: [
      {
        id: "chem_lesson_4",
        title: "العناصر الانتقالية والاتزان الكيميائي",
        duration: "20 دقيقة",
        summary: "خواص السلسلة الانتقالية الأولى وقاعدة لوشاتيليه في الاتزان.",
        content: `تتميز عناصر السلسلة الانتقالية الأولى بتعدد حالات التأكسد والخواص البارامغناطيسية والنشاط الحفزي، كما يوضح مبدأ لوشاتيليه استجابة النظام المتزن للتغير في التركيز أو الضغط أو درجة الحرارة.`
      }
    ]
  }
];

export const SAMPLE_STUDENTS_COHORT = [
  {
    student_id: "std_101",
    cohort_id: "fall_cohort_a",
    course_id: "chem-1st",
    name: "Tariq Mansoor",
    login_frequency_weekly: 0.8,
    assignments_submitted_ratio: 0.35,
    average_quiz_score: 48.5,
    late_submissions_count: 4,
    forum_posts_count: 0,
    time_spent_hours_weekly: 1.2,
    video_watch_completion_ratio: 0.15,
    days_since_last_activity: 9,
  },
  {
    student_id: "std_102",
    cohort_id: "fall_cohort_a",
    course_id: "chem-1st",
    name: "Layla Al-Khatib",
    login_frequency_weekly: 6.5,
    assignments_submitted_ratio: 0.95,
    average_quiz_score: 88.0,
    late_submissions_count: 0,
    forum_posts_count: 6,
    time_spent_hours_weekly: 8.0,
    video_watch_completion_ratio: 0.92,
    days_since_last_activity: 1,
  },
  {
    student_id: "std_103",
    cohort_id: "fall_cohort_b",
    course_id: "chem-1st",
    name: "Ziad El-Shamy",
    login_frequency_weekly: 2.1,
    assignments_submitted_ratio: 0.60,
    average_quiz_score: 62.0,
    late_submissions_count: 2,
    forum_posts_count: 1,
    time_spent_hours_weekly: 3.5,
    video_watch_completion_ratio: 0.45,
    days_since_last_activity: 5,
  },
  {
    student_id: "std_104",
    cohort_id: "fall_cohort_b",
    course_id: "chem-2nd",
    name: "Nouran Ezzat",
    login_frequency_weekly: 8.2,
    assignments_submitted_ratio: 1.0,
    average_quiz_score: 96.0,
    late_submissions_count: 0,
    forum_posts_count: 9,
    time_spent_hours_weekly: 11.0,
    video_watch_completion_ratio: 1.0,
    days_since_last_activity: 0,
  },
  {
    student_id: "std_105",
    cohort_id: "fall_cohort_b",
    course_id: "chem-2nd",
    name: "Kareem Hamdi",
    login_frequency_weekly: 1.4,
    assignments_submitted_ratio: 0.40,
    average_quiz_score: 51.0,
    late_submissions_count: 3,
    forum_posts_count: 0,
    time_spent_hours_weekly: 1.8,
    video_watch_completion_ratio: 0.20,
    days_since_last_activity: 8,
  }
];

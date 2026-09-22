export * from "./i18nContext";
export type Language = "ar" | "en";

export interface Translations {
  // Brand
  brandTitle: string;
  brandSubtitle: string;
  
  // Roles
  studentRole: string;
  teacherRole: string;
  studentMenu: string;
  teacherMenu: string;

  // Nav Items (Strict 1:1 Meaning)
  navHome: string;
  navHomeSub: string;
  navMyCourses: string;
  navMyCoursesSub: string;
  navMySubmissions: string;
  navMySubmissionsSub: string;
  navLessonManagement: string;
  navLessonManagementSub: string;
  navQuizGen: string;
  navQuizGenSub: string;
  navSubmissions: string;
  navSubmissionsSub: string;
  navStudentAnalytics: string;
  navStudentAnalyticsSub: string;
  navProfile: string;
  navProfileSub: string;

  // Header & Global
  searchPlaceholder: string;
  notificationsTitle: string;
  newBadge: string;
  authButton: string;
  exportReport: string;
  exportWord: string;
  exportExcel: string;
  exportPdf: string;
  addCustomColumn: string;
  
  // Academic Years
  academicYear: string;
  allYears: string;
  firstSecondary: string;
  secondSecondary: string;
  thirdSecondary: string;

  // Landing Page Dual-Bar Header (Part 6 & User Image)
  landingTopPhone: string;
  landingTopEmail: string;
  landingNavHome: string;
  landingNavYears: string;
  landingNavCourses: string;
  landingNavTeacher: string;
  landingNavLibrary: string;
  landingHeroBadge: string;
  landingHeroTitle: string;
  landingHeroSubtitle: string;
  landingStartLearningBtn: string;
  landingExploreCoursesBtn: string;
  landingStatStudents: string;
  landingStatLessons: string;
  landingStatYears: string;
  landingStatSuccess: string;
  landingAboutTeacherBadge: string;
  landingAboutTeacherTitle: string;
  landingAboutTeacherBio: string;
  landingTeacherExp1: string;
  landingTeacherExp2: string;
  landingTeacherExp3: string;
  landingFeaturedCoursesTitle: string;
  landingFeaturedCoursesSubtitle: string;
  landingLibraryTitle: string;
  landingLibrarySubtitle: string;
  landingFooterRights: string;
  landingNavAbout: string;
  landingNavContact: string;

  // General Home View
  catalogBadge: string;
  catalogTitle: string;
  catalogSubtitle: string;
  goToMyCoursesBtn: string;
  searchFilterPlaceholder: string;
  enrolledStudentsCount: string;
  instructorLabel: string;
  addCourseBtn: string;
  allCoursesEnrolledTitle: string;
  allCoursesEnrolledDesc: string;

  // My Courses View
  remainingLessonsUrgency: string;
  keepGoingMotivation: string;
  courseProgress: string;
  teacherInCharge: string;
  teacherLessonsList: string;
  lessonWord: string;
  completedBadge: string;
  markCompleted: string;
  markCompletedDone: string;
  teacherMaterialsTitle: string;
  downloadMaterial: string;
  noMaterialsFound: string;
  noCoursesEnrolledTitle: string;
  noCoursesEnrolledDesc: string;
  browseCatalogBtn: string;

  // AI Assistant (FAB & Window)
  aiAssistant: string;
  aiAssistantSubtitle: string;
  aiThinking: string;
  chatPlaceholder: string;
  newChat: string;
  chatHistory: string;
  quickExplain: string;
  quickExample: string;
  quickSummary: string;
  citationsLabel: string;

  // Buttons & Modals
  close: string;
  cancel: string;
  save: string;
  logoutBtn: string;
  toggleThemeLight: string;
  toggleThemeDark: string;

  // Student Analytics & Submissions
  studentAttendanceRatio: string;
  homeworkSuccessRatio: string;
  quizSuccessRatio: string;
  studentTableDetails: string;
  timelineVisualizerTitle: string;
  groupPassingRate: string;
  overallEngagementRate: string;
  hardestLessonStruggle: string;
  misconceptionRate: string;
  minThresholdLabel: string;
  totalGradeCol: string;
  studentNameCol: string;
  nationalIdCol: string;
  statusCol: string;
  actionsCol: string;
  lastActiveCol: string;
  belowThresholdAlert: string;
  stableStatus: string;
  viewAiGradingBtn: string;
  notSubmittedYet: string;

  // Lesson Management
  uploadLessonBadge: string;
  uploadLessonTitle: string;
  uploadLessonSubtitle: string;
  metricEngagement: string;
  metricStruggle: string;
  metricMisconception: string;
  newLessonUploadCard: string;
  lessonTitleLabel: string;
  lessonDescLabel: string;
  lessonDurationLabel: string;
  videoFileLabel: string;
  uploadSubmitBtn: string;
  currentUploadedLessons: string;
  flaggedConceptsTitle: string;

  // Auth (Split Screen)
  splitWelcomeBack: string;
  splitWelcomeDesc: string;
  splitJoinUs: string;
  splitJoinDesc: string;
  splitSignInTab: string;
  splitRegisterTab: string;
  splitHaveAccount: string;
  splitDontHaveAccount: string;
  forgotPasswordLink: string;
  demoTeacherHint: string;
  demoStudentHint: string;

  profileTitle: string;
  profileSubtitle: string;
  emailLabel: string;
  passwordLabel: string;
  fullNameLabel: string;
  studentPhoneLabel: string;
  guardianPhoneLabel: string;
  ageLabel: string;
  nationalIdLabel: string;
  idPhotoUploadLabel: string;
  subjectLabel: string;
  signInSubmit: string;
  registerStudentSubmit: string;
}

export const translations: Record<Language, Translations> = {
  ar: {
    brandTitle: "منصة الكيمياء التعليمية — مستر حسن شعبان",
    brandSubtitle: "المنصة المتخصصة في تدريس مادة الكيمياء للمرحلة الثانوية مع مستر حسن شعبان",
    studentRole: "حساب طالب",
    teacherRole: "المعلم المسؤول",
    studentMenu: "قائمة الطالب",
    teacherMenu: "لوحة المعلم",

    navHome: "الصفحة الرئيسية (مقررات الكيمياء)",
    navHomeSub: "استعراض مقررات الكيمياء المتاحة",
    navMyCourses: "مقرراتي ودروسي",
    navMyCoursesSub: "مقررات الكيمياء المسجلة لي",
    navMySubmissions: "واجباتي واختباراتي",
    navMySubmissionsSub: "كشف درجاتي وتصحيحي",
    navLessonManagement: "إدارة ورفع الدروس",
    navLessonManagementSub: "المحتوى وتوقعات الصعوبة",
    navQuizGen: "صانع الاختبارات والواجبات",
    navQuizGenSub: "توليد ونشر الاختبارات والواجبات الذكية",
    navSubmissions: "تسليمات الواجبات والتصحيح",
    navSubmissionsSub: "تصحيح المقالات والدرجات",
    navStudentAnalytics: "متابعة الطلاب",
    navStudentAnalyticsSub: "سنوات الدراسة ومخطط المشاهدة",
    navProfile: "الملف الشخصي",
    navProfileSub: "بيانات الحساب وإحصائياتي",

    searchPlaceholder: "ابحث في دروس الكيمياء، المذكرات، أو الواجبات...",
    notificationsTitle: "الإشعارات والمواعيد",
    newBadge: "جديد",
    authButton: "تسجيل الدخول / إنشاء حساب",
    exportReport: "تصدير التقرير",
    exportWord: "تصدير Word (.docx حقيقي)",
    exportExcel: "تصدير Excel / CSV",
    exportPdf: "تصدير / طباعة PDF",
    addCustomColumn: "إضافة عمود مخصص",

    academicYear: "السنة الدراسية:",
    allYears: "جميع الصفوف",
    firstSecondary: "الصف الأول الثانوي",
    secondSecondary: "الصف الثاني الثانوي",
    thirdSecondary: "الصف الثالث الثانوي",

    // Landing Page Dual-Bar Header
    landingTopPhone: "01092837461",
    landingTopEmail: "contact@chemistry-platform.edu.eg",
    landingNavHome: "الصفحة الرئيسية",
    landingNavYears: "السنوات الدراسية",
    landingNavCourses: "مقررات الكيمياء",
    landingNavTeacher: "عن المعلم",
    landingNavLibrary: "المكتبة والملخصات",
    landingHeroBadge: "المنصة التعليمية لمادة الكيمياء — مستر حسن شعبان",
    landingHeroTitle: "طريقك للدرجة النهائية والتفوق في مادة الكيمياء للثانوية العامة",
    landingHeroSubtitle: "شروحات تفصيلية لمنهج الكيمياء، بنوك أسئلة تفاعلية، ومتابعة دقيقة لكل درس وواجب مع مستر حسن شعبان بنظام الذكاء الاصطناعي.",
    landingStartLearningBtn: "ابدأ التعلم الآن مجاناً",
    landingExploreCoursesBtn: "استعرض شروحات الكيمياء",
    landingStatStudents: "طالب مسجل ومتفوق",
    landingStatLessons: "محاضرة وفيديو شرح",
    landingStatYears: "صفوف ثانوية معتمدة",
    landingStatSuccess: "نسبة اجتياز وتفوق",
    landingAboutTeacherBadge: "عن معلم الكيمياء",
    landingAboutTeacherTitle: "مستر حسن شعبان — معلم مادة الكيمياء للثانوية العامة",
    landingAboutTeacherBio: "خبرة واسعة في تدريس وتبسيط منهج الكيمياء للثانوية العامة والربط العملي والتطبيقي وحل نماذج الامتحانات وتأهيل الطلاب للدرجات النهائية.",
    landingTeacherExp1: "خبرة رائدة في إعداد وتأهيل أوائل الثانوية العامة في مادة الكيمياء",
    landingTeacherExp2: "إعداد مذكرات الكيمياء وبنوك الأسئلة الشاملة",
    landingTeacherExp3: "متابعة وتصحيح ذكي لواجبات وتدريبات الكيمياء وتحديد نقاط القوة والضعف",
    landingFeaturedCoursesTitle: "مقررات الكيمياء المعتمدة",
    landingFeaturedCoursesSubtitle: "اختر صفك الدراسي واستمتع بتجربة تعلم حديثة مع متابعة مستمرة وتصحيح ذكي للواجبات مع مستر حسن شعبان.",
    landingLibraryTitle: "المكتبة الرقمية ومذكرات الكيمياء المعتمدة",
    landingLibrarySubtitle: "حمل مذكرات الشرح ونماذج الامتحانات المحدثة في مادة الكيمياء لمراجعة الدروس.",
    landingFooterRights: "جميع الحقوق محفوظة © 2026 — منصة الكيمياء التعليمية (مستر حسن شعبان)",
    landingNavAbout: "عن المعلم",
    landingNavContact: "تواصل معنا",

    catalogBadge: "مقررات الكيمياء المعتمدة",
    catalogTitle: "استكشف مقررات الكيمياء المتاحة",
    catalogSubtitle: "اختر صفك الدراسي وسجل في مقرر الكيمياء للوصول إلى فيديوهات الشرح المعتمدة مع مستر حسن شعبان.",
    goToMyCoursesBtn: "الانتقال إلى مقرراتي المسجلة",
    searchFilterPlaceholder: "بحث في دروس ومذكرات الكيمياء...",
    enrolledStudentsCount: "طالب مسجل",
    instructorLabel: "معلم الكيمياء المسؤول:",
    addCourseBtn: "إضافة للمقررات",
    allCoursesEnrolledTitle: "جميع مقررات الكيمياء متاحة ومسجلة في حسابك بالفعل!",
    allCoursesEnrolledDesc: "أضفت كل المقررات المتاحة، يمكنك الانتقال إلى صفحة مقرراتي ودروسي لمتابعة شروحات الكيمياء.",

    remainingLessonsUrgency: "أنت على بُعد {count} دروس فقط من إتمام مقرر الكيمياء!",
    keepGoingMotivation: "شاهد الدرس المتبقي اليوم وحل الواجب للحفاظ على ترتيبك في لوحة شرف المتفوقين",
    courseProgress: "نسبة إنجاز مقرر الكيمياء",
    teacherInCharge: "معلم الكيمياء المسؤول:",
    teacherLessonsList: "قائمة شروحات مستر حسن شعبان المعتمدة",
    lessonWord: "الدرس",
    completedBadge: "مكتمل",
    markCompleted: "تعليم الدرس كمكتمل",
    markCompletedDone: "تم إنهاء الدرس",
    teacherMaterialsTitle: "الملفات والمذكرات المرفوعة من المعلم:",
    downloadMaterial: "تنزيل الملف",
    noMaterialsFound: "لا توجد ملفات إضافية مرفقة مع هذا الدرس.",
    noCoursesEnrolledTitle: "لم تقم بالاشتراك في أي مقرر كيمياء بعد",
    noCoursesEnrolledDesc: "تصفح مقررات الكيمياء المتاحة في الصفحة الرئيسية واختر صفك الدراسي لتظهر الدروس هنا مباشرة.",
    browseCatalogBtn: "تصفح مقررات الكيمياء",

    aiAssistant: "مساعد الكيمياء الذكي - AI",
    aiAssistantSubtitle: "المساعد التعليمي الذكي لشرح وتلخيص الكيمياء",
    aiThinking: "مساعد الكيمياء يفكر ويراجع محتوى الدرس...",
    chatPlaceholder: "اكتب سؤالك هنا في منهج الكيمياء...",
    newChat: "محادثة جديدة",
    chatHistory: "المحادثات السابقة",
    quickExplain: "اشرحلي الدرس ببساطة",
    quickExample: "مثال عملي وسهل",
    quickSummary: "ملخص القوانين والمعادلات",
    citationsLabel: "مقتطفات واستشهادات من نص الدرس",

    close: "إغلاق",
    cancel: "إلغاء",
    save: "حفظ",
    logoutBtn: "تسجيل الخروج من الحساب",
    toggleThemeLight: "الوضع النهاري",
    toggleThemeDark: "الوضع الليلي",

    studentAttendanceRatio: "نسبة المتابعة الشخصية %",
    homeworkSuccessRatio: "نسبة نجاح الواجبات %",
    quizSuccessRatio: "نسبة نجاح الاختبارات %",
    studentTableDetails: "مخطط المشاهدة والتفاصيل",
    timelineVisualizerTitle: "تفاصيل مشاهدة الفيديوهات ومخطط المتابعة الزمني",
    groupPassingRate: "نسبة نجاح المجموعة كاملة:",
    overallEngagementRate: "نسبة المتابعة والحضور العامة:",
    hardestLessonStruggle: "توقع الدرس الأصعب ونسبة التعثر:",
    misconceptionRate: "نسبة عدم الفهم المتوقعة:",
    minThresholdLabel: "المعدل الأدنى للتسليم:",
    totalGradeCol: "الدرجة الكلية",
    studentNameCol: "اسم الطالب",
    nationalIdCol: "الرقم القومي",
    statusCol: "حالة المتابعة",
    actionsCol: "إجراءات وتصحيح الواجب",
    lastActiveCol: "آخر ظهور",
    belowThresholdAlert: "تحت المعدل الأدنى",
    stableStatus: "منتظم ومستقر",
    viewAiGradingBtn: "عرض إجابة وتصحيح الـ AI",
    notSubmittedYet: "لم يسلم بعد",

    uploadLessonBadge: "إدارة المحتوى وتوقعات الصعوبة",
    uploadLessonTitle: "إدارة ورفع دروس الكيمياء وتوقعات صعوبة المنهج",
    uploadLessonSubtitle: "ارفع فيديوهات شروحات الكيمياء والمذكرات، وتعرف على توقعات الذكاء الاصطناعي لأصعب أجزاء المنهج ونسب تعثر الطلاب.",
    metricEngagement: "١. نسبة متابعة الطلاب:",
    metricStruggle: "٢. توقع الدرس الأصعب ونسبة التعثر:",
    metricMisconception: "٣. نسبة عدم الفهم المتوقعة:",
    newLessonUploadCard: "رفع درس ومحتوى جديد",
    lessonTitleLabel: "عنوان الدرس:",
    lessonDescLabel: "وصف وملخص الدرس:",
    lessonDurationLabel: "مدة الفيديو - بالدقائق:",
    videoFileLabel: "ملف الفيديو - MP4 / WebM:",
    uploadSubmitBtn: "رفع وحفظ الدرس في المنصة",
    currentUploadedLessons: "الدروس المرفوعة الحالية",
    flaggedConceptsTitle: "مفاهيم مرصودة تحتاج تركيز إضافي من المعلم:",

    // Split Screen Auth
    splitWelcomeBack: "أهلاً بك مجدداً في منصة الكيمياء",
    splitWelcomeDesc: "سجل دخولك لمتابعة شروحات الكيمياء وحل الواجبات والاختبارات التفاعلية مع مستر حسن شعبان.",
    splitJoinUs: "ابدأ رحلة التفوق في الكيمياء مع مستر حسن شعبان",
    splitJoinDesc: "أنشئ حسابك كطالب لتتمكن من الوصول الفوري لمحاضرات الكيمياء ومتابعة مستواك أولاً بأول.",
    splitSignInTab: "تسجيل الدخول",
    splitRegisterTab: "تسجيل جديد",
    splitHaveAccount: "لديك حساب بالفعل؟ سجل دخولك الآن",
    splitDontHaveAccount: "طالب جديد؟ أنشئ حسابك وابدأ التعلم الآن",
    forgotPasswordLink: "هل نسيت كلمة المرور؟",
    demoTeacherHint: "دخول كمعلم: teacher@demo.com",
    demoStudentHint: "دخول كطالب: student01@demo.com",

    profileTitle: "الملف التعريفي للحساب",
    profileSubtitle: "استعرض إحصائياتك الأكاديمية وسجل نشاطك في المنصة",
    emailLabel: "البريد الإلكتروني:",
    passwordLabel: "كلمة المرور:",
    fullNameLabel: "الاسم رباعي (للطالب):",
    studentPhoneLabel: "رقم موبايل الطالب:",
    guardianPhoneLabel: "رقم موبايل ولي الأمر:",
    ageLabel: "السن:",
    nationalIdLabel: "الرقم القومي للطالب أو ولي الأمر (14 رقم):",
    idPhotoUploadLabel: "صورة بطاقة الرقم القومي للتحقق والاعتماد:",
    subjectLabel: "المادة العلمية:",
    signInSubmit: "دخول الحساب",
    registerStudentSubmit: "إتمام تسجيل حساب الطالب وبدء التعلم",
  },
  en: {
    brandTitle: "Chemistry Learning Platform — Mr. Hassan Shaaban",
    brandSubtitle: "Secondary School Chemistry Education Portal with Mr. Hassan Shaaban",
    studentRole: "Student Account",
    teacherRole: "Certified Instructor",
    studentMenu: "Student Menu",
    teacherMenu: "Instructor Panel",

    navHome: "Home (Chemistry Courses)",
    navHomeSub: "Explore Available Chemistry Courses",
    navMyCourses: "My Courses & Lessons",
    navMyCoursesSub: "Enrolled Chemistry Curriculum",
    navMySubmissions: "My Assignments & Quizzes",
    navMySubmissionsSub: "Evaluated Grades & Feedback",
    navLessonManagement: "Lesson Management & Upload",
    navLessonManagementSub: "Content & Difficulty Forecast",
    navQuizGen: "Quiz & Assignment Studio",
    navQuizGenSub: "Smart Assessment & Homework Authoring",
    navSubmissions: "Assignment Submissions & Grading",
    navSubmissionsSub: "Essay Grading & Scores",
    navStudentAnalytics: "Student Tracking & Cohorts",
    navStudentAnalyticsSub: "Academic Years & Timelines",
    navProfile: "User Profile",
    navProfileSub: "Account Info & Stats",

    searchPlaceholder: "Search chemistry lessons, notes, assignments...",
    notificationsTitle: "Notifications & Deadlines",
    newBadge: "New",
    authButton: "Sign In / Register",
    exportReport: "Export Report (Generate)",
    exportWord: "Export Word (.docx OOXML)",
    exportExcel: "Export Excel / CSV",
    exportPdf: "Export / Print PDF",
    addCustomColumn: "+ Add Custom Column",

    academicYear: "Academic Year:",
    allYears: "All Grades",
    firstSecondary: "1st Secondary Year",
    secondSecondary: "2nd Secondary Year",
    thirdSecondary: "3rd Secondary Year",

    // Landing Page Dual-Bar Header
    landingTopPhone: "+20 109 283 7461",
    landingTopEmail: "contact@chemistry-platform.edu.eg",
    landingNavHome: "Home",
    landingNavYears: "Academic Grades",
    landingNavCourses: "Chemistry Courses",
    landingNavTeacher: "Instructor",
    landingNavLibrary: "Library & Summaries",
    landingHeroBadge: "Official Chemistry Learning Platform — Mr. Hassan Shaaban",
    landingHeroTitle: "Your Path to Excellence and Full Marks in Chemistry",
    landingHeroSubtitle: "In-depth Chemistry lectures, interactive question banks, and dedicated AI-powered study assistance by Mr. Hassan Shaaban.",
    landingStartLearningBtn: "Start Learning Now",
    landingExploreCoursesBtn: "Explore Chemistry Lectures",
    landingStatStudents: "Enrolled High-Achieving Students",
    landingStatLessons: "Recorded Lectures & Video Lessons",
    landingStatYears: "Accredited Secondary Grades",
    landingStatSuccess: "Student Success & Pass Rate",
    landingAboutTeacherBadge: "About the Chemistry Instructor",
    landingAboutTeacherTitle: "Mr. Hassan Shaaban — Senior Chemistry Educator",
    landingAboutTeacherBio: "Extensive experience delivering secondary school Chemistry curricula, practical applications, and preparing students for top exam scores.",
    landingTeacherExp1: "Years of excellence mentoring top-ranked secondary graduates in Chemistry",
    landingTeacherExp2: "Author of structured Chemistry study guides and comprehensive question banks",
    landingTeacherExp3: "AI-assisted rubric grading and diagnostic support for Chemistry students",
    landingFeaturedCoursesTitle: "Accredited Chemistry Curricula",
    landingFeaturedCoursesSubtitle: "Select your secondary grade and study Chemistry with Mr. Hassan Shaaban.",
    landingLibraryTitle: "Digital Library & Chemistry Summaries",
    landingLibrarySubtitle: "Download official Chemistry study notes and model exams to review your lessons.",
    landingFooterRights: "All Rights Reserved © 2026 — Chemistry Learning Platform (Mr. Hassan Shaaban)",
    landingNavAbout: "About Instructor",
    landingNavContact: "Contact Us",

    catalogBadge: "ACCREDITED CHEMISTRY CURRICULUM",
    catalogTitle: "Explore Available Chemistry Courses",
    catalogSubtitle: "Choose your secondary grade to access certified Chemistry lectures by Mr. Hassan Shaaban.",
    goToMyCoursesBtn: "Go to My Enrolled Courses",
    searchFilterPlaceholder: "Search chemistry lessons or worksheets...",
    enrolledStudentsCount: "enrolled students",
    instructorLabel: "Chemistry Instructor in Charge:",
    addCourseBtn: "Enroll in Course (Add)",
    allCoursesEnrolledTitle: "All chemistry courses are already added to your account!",
    allCoursesEnrolledDesc: "You have enrolled in all available chemistry courses. Go to My Courses to view your video lessons.",

    remainingLessonsUrgency: "You are only {count} lessons away from completing this chemistry course!",
    keepGoingMotivation: "Watch today's lesson and submit your assignment to maintain your Honor Roll ranking",
    courseProgress: "Chemistry Course Progress",
    teacherInCharge: "Chemistry Instructor in Charge:",
    teacherLessonsList: "Official Chemistry Video Lessons by Mr. Hassan Shaaban",
    lessonWord: "Lesson",
    completedBadge: "Completed",
    markCompleted: "Mark as Completed",
    markCompletedDone: "Lesson Completed",
    teacherMaterialsTitle: "Teacher Uploaded Materials & Worksheets:",
    downloadMaterial: "Download File",
    noMaterialsFound: "No extra files attached with this lesson.",
    noCoursesEnrolledTitle: "You have not enrolled in any chemistry course yet",
    noCoursesEnrolledDesc: "Browse available chemistry courses in the Home page and select your grade.",
    browseCatalogBtn: "Browse Chemistry Courses",

    aiAssistant: "Chemistry AI Assistant",
    aiAssistantSubtitle: "Grounded AI Tutor for Chemistry explanations & study support",
    aiThinking: "Chemistry AI Tutor is analyzing the lesson content...",
    chatPlaceholder: "Ask anything about the Chemistry lesson...",
    newChat: "New Conversation",
    chatHistory: "Past Conversations",
    quickExplain: "Explain simply",
    quickExample: "Practical example",
    quickSummary: "Formula & Law Summary",
    citationsLabel: "Lesson Content Snippets & Citations",

    close: "Close",
    cancel: "Cancel",
    save: "Save",
    logoutBtn: "Log Out of Account",
    toggleThemeLight: "Light Mode",
    toggleThemeDark: "Dark Mode",

    studentAttendanceRatio: "Personal Attendance %",
    homeworkSuccessRatio: "Homework Success %",
    quizSuccessRatio: "Quiz Success %",
    studentTableDetails: "Viewing Timeline & Details",
    timelineVisualizerTitle: "Video Watching Timeline & Engagement Visualizer",
    groupPassingRate: "Group Passing Rate:",
    overallEngagementRate: "Overall Attendance Rate:",
    hardestLessonStruggle: "Hardest Lesson & Struggle Forecast:",
    misconceptionRate: "Predicted Misconception Rate:",
    minThresholdLabel: "Minimum Submission Threshold:",
    totalGradeCol: "Total Grade",
    studentNameCol: "Student Name",
    nationalIdCol: "National ID",
    statusCol: "Progress Status",
    actionsCol: "Actions & AI Grading",
    lastActiveCol: "Last Active",
    belowThresholdAlert: "Below Minimum Threshold",
    stableStatus: "Regular & Stable",
    viewAiGradingBtn: "View Student Answer & AI Rubric",
    notSubmittedYet: "Not submitted yet",

    uploadLessonBadge: "Content Management & Difficulty Forecasting",
    uploadLessonTitle: "Chemistry Lesson Management & Difficulty Forecasting",
    uploadLessonSubtitle: "Upload Chemistry explanation videos and worksheets, and review AI predictions on difficulty and struggle rates.",
    metricEngagement: "1. Student Engagement Rate:",
    metricStruggle: "2. Hardest Lesson & Expected Struggle:",
    metricMisconception: "3. Predicted Misconception Rate:",
    newLessonUploadCard: "Upload New Lesson & Content",
    lessonTitleLabel: "Lesson Title:",
    lessonDescLabel: "Lesson Summary & Description:",
    lessonDurationLabel: "Video Duration (in minutes):",
    videoFileLabel: "Video File (MP4 / WebM):",
    uploadSubmitBtn: "Upload and Publish Lesson",
    currentUploadedLessons: "Currently Published Lessons",
    flaggedConceptsTitle: "Flagged Concepts Requiring Extra Instructor Focus:",

    // Split Screen Auth
    splitWelcomeBack: "Welcome back to your Chemistry portal",
    splitWelcomeDesc: "Sign in to access your Chemistry video lectures, submit assignments, and track your progress with Mr. Hassan Shaaban.",
    splitJoinUs: "Start your journey to excellence in Chemistry with Mr. Hassan Shaaban",
    splitJoinDesc: "Create your student account to get instant access to lectures and AI-assisted homework grading.",
    splitSignInTab: "Sign In",
    splitRegisterTab: "Register",
    splitHaveAccount: "Already have an account? Sign in here",
    splitDontHaveAccount: "New student? Create an account and start learning",
    forgotPasswordLink: "Forgot your password?",
    demoTeacherHint: "Teacher Login: teacher@demo.com",
    demoStudentHint: "Student Login: student01@demo.com",

    profileTitle: "User Profile & Account",
    profileSubtitle: "Review your academic statistics and platform activity",
    emailLabel: "Email Address:",
    passwordLabel: "Password:",
    fullNameLabel: "Student Full Name:",
    studentPhoneLabel: "Student Mobile Number:",
    guardianPhoneLabel: "Guardian Mobile Number:",
    ageLabel: "Age:",
    nationalIdLabel: "National ID (Student or Guardian - 14 digits):",
    idPhotoUploadLabel: "National ID Card Photo (Verification):",
    subjectLabel: "Teaching Subject:",
    signInSubmit: "Sign In to Account",
    registerStudentSubmit: "Complete Student Registration & Start Learning",
  },
};

import { PageLoadingScreen } from "./components/PageLoadingScreen";
import { lazy, Suspense, useEffect, useState, useCallback } from "react";
import { Sidebar, NavTab } from "./components/Sidebar";
import { Header } from "./components/Header";
import { FloatingAITutor } from "./components/FloatingAITutor";
import { GlobalUploadWidget } from "./components/GlobalUploadWidget";
import {
  INITIAL_COURSES,
  INITIAL_STUDENT_PROFILE,
} from "./data/lmsStore";
import { Course, CurrentUser, NotificationItem } from "./types/lms";
import { Language } from "./utils/i18n";

import { authService, courseService, notificationService } from "./services/lmsService";
import { useConfirm } from "./components/ConfirmWizard";

// Views
import { LandingPageView } from "./views/LandingPageView";
// View chunk loaders for background prefetching & instant navigation
export const viewLoaders = {
  GeneralHome: () => import("./views/GeneralHomeView"),
  MyCourses: () => import("./views/MyCoursesView"),
  MySubmissions: () => import("./views/MySubmissionsView"),
  LessonManagement: () => import("./views/LessonManagementView"),
  AIKnowledgeCenter: () => import("./views/AIKnowledgeCenterView"),
  QuizGen: () => import("./views/QuizGeneratorView"),
  Submissions: () => import("./views/SubmissionsView"),
  StudentAnalytics: () => import("./views/StudentAnalyticsView"),
  Notifications: () => import("./views/NotificationsView"),
  Profile: () => import("./views/ProfileView"),
};

export function preloadView(tabName: keyof typeof viewLoaders) {
  try {
    const loader = viewLoaders[tabName];
    if (loader) {
      void loader();
    }
  } catch {
    // Ignore preload error
  }
}

const GeneralHomeView = lazy(() => viewLoaders.GeneralHome().then((m) => ({ default: m.GeneralHomeView })));
const MyCoursesView = lazy(() => viewLoaders.MyCourses().then((m) => ({ default: m.MyCoursesView })));
const MySubmissionsView = lazy(() => viewLoaders.MySubmissions().then((m) => ({ default: m.MySubmissionsView })));
const LessonManagementView = lazy(() => viewLoaders.LessonManagement().then((m) => ({ default: m.LessonManagementView })));
const AIKnowledgeCenterView = lazy(() => viewLoaders.AIKnowledgeCenter().then((m) => ({ default: m.AIKnowledgeCenterView })));
const QuizGeneratorView = lazy(() => viewLoaders.QuizGen().then((m) => ({ default: m.QuizGeneratorView })));
const SubmissionsView = lazy(() => viewLoaders.Submissions().then((m) => ({ default: m.SubmissionsView })));
const StudentAnalyticsView = lazy(() => viewLoaders.StudentAnalytics().then((m) => ({ default: m.StudentAnalyticsView })));
const NotificationsView = lazy(() => viewLoaders.Notifications().then((m) => ({ default: m.NotificationsView })));
const ProfileView = lazy(() => viewLoaders.Profile().then((m) => ({ default: m.ProfileView })));
import { AuthView } from "./views/AuthView";

const VALID_TABS = [
  "Landing",
  "Auth",
  "GeneralHome",
  "MyCourses",
  "MySubmissions",
  "LessonManagement",
  "AIKnowledgeCenter",
  "QuizGen",
  "Submissions",
  "StudentAnalytics",
  "Notifications",
  "Profile",
] as const;

type AllTabs = (typeof VALID_TABS)[number];

function getTabFromHash(): AllTabs | null {
  const raw = window.location.hash.replace("#", "").trim().toLowerCase();
  if (!raw) return null;
  const match = VALID_TABS.find((t) => t.toLowerCase() === raw);
  return match || null;
}

function App() {
  const confirm = useConfirm();
  // Restore cached user session immediately so user is instantly authenticated without having to sign in again
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(() => {
    try {
      const cached = typeof localStorage !== "undefined" ? localStorage.getItem("lms_cached_user") : null;
      return cached ? (JSON.parse(cached) as CurrentUser) : null;
    } catch {
      return null;
    }
  });
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isInitialRefresh, setIsInitialRefresh] = useState(true);
  const [authLoading, setAuthLoading] = useState(() => {
    return typeof localStorage !== "undefined" ? !localStorage.getItem("lms_cached_user") : true;
  });

  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("lms_theme");
    return (saved as "light" | "dark") || "light";
  });

    // Manage Refresh / Initial Page Load splash duration
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsInitialRefresh(false);
    }, 600);
    return () => clearTimeout(timer);
  }, []);

  const [lang, setLang] = useState<Language>(() => {
    const saved = localStorage.getItem("lms_lang");
    return (saved as Language) || "ar";
  });

  const [courses, setCourses] = useState<Course[]>(INITIAL_COURSES);
  const [enrolledCourseIds, setEnrolledCourseIds] = useState<string[]>([]);

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  // Real-time synchronization for courses, notifications, and auth sessions via DAL
  useEffect(() => {
    async function handleNotificationsSync() {
      try {
        const data = await notificationService.getNotifications();
        setNotifications(data);
      } catch {
        setNotifications([]);
      }
    }

    async function handleUserSync() {
      const user = await authService.getCurrentUser();
      setCurrentUser(user);
      if (user) await handleNotificationsSync();
      setAuthLoading(false);
    }

    async function handleCoursesSync() {
      try {
        const data = await courseService.getCourses();
        setCourses(data);
      } catch (err) {
        console.error("Courses sync error", err);
      }
    }

    // Local in-window custom event listeners
    window.addEventListener("lms_notifications_updated", handleNotificationsSync);
    window.addEventListener("lms_user_updated", handleUserSync);
    window.addEventListener("lms_courses_updated", handleCoursesSync);

    void handleUserSync();

    return () => {
      window.removeEventListener("lms_notifications_updated", handleNotificationsSync);
      window.removeEventListener("lms_user_updated", handleUserSync);
      window.removeEventListener("lms_courses_updated", handleCoursesSync);
    };
  }, []);

  // Track active navigation tab with Google Chrome native History & Hash support
  const [activeTab, setActiveTab] = useState<AllTabs>(() => {
    const fromHash = getTabFromHash();
    if (fromHash && fromHash !== "Landing" && fromHash !== "Auth") return fromHash;

    let user: CurrentUser | null = null;
    try {
      const cached = typeof localStorage !== "undefined" ? localStorage.getItem("lms_cached_user") : null;
      user = cached ? (JSON.parse(cached) as CurrentUser) : null;
    } catch {}

    const savedTab = typeof localStorage !== "undefined" ? localStorage.getItem("lms_active_tab") : null;
    if (user) {
      if (savedTab && VALID_TABS.includes(savedTab as AllTabs) && savedTab !== "Landing" && savedTab !== "Auth") {
        return savedTab as AllTabs;
      }
      return user.role === "student" ? "GeneralHome" : "LessonManagement";
    }

    if (savedTab && VALID_TABS.includes(savedTab as AllTabs)) {
      return savedTab as AllTabs;
    }

    return "Landing";
  });

  const [authInitialTab, setAuthInitialTab] = useState<"signin" | "register">("signin");
  const [menuOpen, setMenuOpen] = useState(false);

  // Navigate to Tab and push to Google Chrome history stack
  const navigateToTab = useCallback((targetTab: AllTabs) => {
    setActiveTab(targetTab);
    localStorage.setItem("lms_active_tab", targetTab);
    const targetHash = `#${targetTab.toLowerCase()}`;
    if (window.location.hash.toLowerCase() !== targetHash) {
      window.location.hash = targetHash;
    }
  }, []);

  useEffect(() => {
    if (currentUser && (activeTab === "Landing" || activeTab === "Auth")) {
      const target = currentUser.role === "student" ? "GeneralHome" : "LessonManagement";
      navigateToTab(target);
    }
  }, [currentUser, activeTab, navigateToTab]);

  // Intelligent Background Prefetch: Preload all other views while the user is on any page
  useEffect(() => {
    if (!currentUser) return;

    const isTeacher = currentUser.role === "teacher";
    const priorityList: Array<keyof typeof viewLoaders> = isTeacher
      ? ["LessonManagement", "QuizGen", "StudentAnalytics", "AIKnowledgeCenter", "Submissions", "Notifications", "Profile", "GeneralHome", "MyCourses", "MySubmissions"]
      : ["GeneralHome", "MyCourses", "MySubmissions", "Notifications", "Profile", "LessonManagement", "QuizGen", "StudentAnalytics", "AIKnowledgeCenter", "Submissions"];

    // Filter out current view since it is already rendered
    const viewsToPrefetch = priorityList.filter((tab) => tab !== activeTab);

    let currentIndex = 0;
    let isCancelled = false;

    const prefetchNext = () => {
      if (isCancelled || currentIndex >= viewsToPrefetch.length) return;

      const tab = viewsToPrefetch[currentIndex];
      currentIndex++;

      const loader = viewLoaders[tab];
      if (loader) {
        loader()
          .catch(() => undefined)
          .finally(() => {
            if (!isCancelled) {
              if (typeof window !== "undefined" && "requestIdleCallback" in window) {
                (window as any).requestIdleCallback(prefetchNext, { timeout: 1200 });
              } else {
                setTimeout(prefetchNext, 120);
              }
            }
          });
      }
    };

    // Start background prefetch shortly after page mount (700ms)
    const timer = setTimeout(() => {
      if (typeof window !== "undefined" && "requestIdleCallback" in window) {
        (window as any).requestIdleCallback(prefetchNext, { timeout: 1500 });
      } else {
        setTimeout(prefetchNext, 150);
      }
    }, 700);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [currentUser, activeTab]);

  // Listen to Google Chrome Native Back & Forward Buttons (hashchange + popstate)
  useEffect(() => {
    // Sync initial hash if absent
    const initialHash = getTabFromHash();
    if (!initialHash) {
      window.location.replace(`#${activeTab.toLowerCase()}`);
    }

    function handleChromeNavigation() {
      const match = getTabFromHash();
      if (match) {
        setActiveTab(match);
        localStorage.setItem("lms_active_tab", match);
      }
    }

    window.addEventListener("hashchange", handleChromeNavigation);
    window.addEventListener("popstate", handleChromeNavigation);

    return () => {
      window.removeEventListener("hashchange", handleChromeNavigation);
      window.removeEventListener("popstate", handleChromeNavigation);
    };
  }, [activeTab]);

  // Apply Theme & Direction to Document
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("lms_theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");
    document.documentElement.setAttribute("lang", lang);
    localStorage.setItem("lms_lang", lang);
  }, [lang]);

  // Load business data from the backend after the server session is known.
  useEffect(() => {
    if (!currentUser) {
      setCourses([]);
      setEnrolledCourseIds([]);
      return;
    }
    void courseService.getCourses().then(setCourses).catch(() => setCourses([]));
    if (currentUser.role === "student") {
      void courseService.getEnrolledCourseIds().then(setEnrolledCourseIds).catch(() => setEnrolledCourseIds([]));
    } else {
      setEnrolledCourseIds([]);
    }
  }, [currentUser]);

  function handleToggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  function handleToggleLang() {
    setLang((prev) => (prev === "ar" ? "en" : "ar"));
  }

  async function handleEnrollCourse(courseId: string) {
    try {
      const updated = await courseService.enrollCourse(courseId);
      setEnrolledCourseIds(updated);
    } catch (error) {
      await confirm({
        title: "تعذر التسجيل في المقرر",
        message: error instanceof Error ? error.message : "حدث خطأ غير متوقع. حاول مرة أخرى.",
        cancelLabel: "إغلاق",
        tone: "warning",
      });
    }
  }

  function handleMarkNotificationRead(id: string) {
    void notificationService.markAsRead(id).then(setNotifications).catch(() => undefined);
  }

  function handleAddNotification(notif: NotificationItem) {
    void notificationService.saveNotification(notif).then(setNotifications).catch(() => undefined);
  }

  function handleSelectNotification(notif: NotificationItem) {
    handleMarkNotificationRead(notif.id);
    if (notif.actionTab) {
      navigateToTab(notif.actionTab as NavTab);
    } else if (notif.type === "assignment") {
      navigateToTab(currentUser?.role === "teacher" ? "Submissions" : "MySubmissions");
    } else if (notif.type === "quiz") {
      navigateToTab(currentUser?.role === "teacher" ? "QuizGen" : "MyCourses");
    } else {
      navigateToTab(currentUser?.role === "teacher" ? "LessonManagement" : "MyCourses");
    }
  }

  async function handleLogout() {
    try {
      await authService.logout();
    } catch {
      // Clear the local UI even if the session endpoint is temporarily unavailable.
    } finally {
      setCurrentUser(null);
      setAuthLoading(false);
      localStorage.removeItem("lms_session_token");
      localStorage.removeItem("lms_cached_user");
      navigateToTab("Landing");
    }
  }

  function handleNavigateToAuth(tab: "signin" | "register" = "signin") {
    setAuthInitialTab(tab);
    navigateToTab("Auth");
  }

  const enrolledCoursesList = courses.filter((c) => {
    return enrolledCourseIds.includes(c.id);
  });

  if (isInitialRefresh || (authLoading && !currentUser) || isLoggingIn) {
    return <PageLoadingScreen brandTitle="منصة الكيمياء التعليمية — مستر حسن شعبان" />;
  }

  // If user is not logged in: show Landing Page or Auth Page
  if (!currentUser) {
    if (activeTab === "Auth") {
      return (
        <AuthView
          initialTab={authInitialTab}
          onLoginSuccess={(user) => {
            setIsLoggingIn(true);
            setCurrentUser(user);
            const targetTab = user.role === "student" ? "GeneralHome" : "LessonManagement";
            navigateToTab(targetTab);
            setTimeout(() => {
              setIsLoggingIn(false);
            }, 600);
          }}
          onBackToLanding={() => navigateToTab("Landing")}
          lang={lang}
          onToggleLang={handleToggleLang}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      );
    }

    return (
      <LandingPageView
        courses={courses}
        onNavigateToAuth={handleNavigateToAuth}
        lang={lang}
        onToggleLang={handleToggleLang}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />
    );
  }

  // Internal Authenticated Platform View
  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab as NavTab}
        onSelectTab={(tab) => navigateToTab(tab)}
        onHoverTab={(tab) => preloadView(tab as any)}
        menuOpen={menuOpen}
        onCloseMenu={() => setMenuOpen(false)}
        currentUser={currentUser || INITIAL_STUDENT_PROFILE}
        lang={lang}
      />

      {/* Main Content */}
      <main>
        {/* Top Header */}
        <Header
          onToggleMenu={() => setMenuOpen(!menuOpen)}
          menuOpen={menuOpen}
          notifications={notifications}
          onMarkNotificationRead={handleMarkNotificationRead}
          onSelectNotification={handleSelectNotification}
          onNavigateToNotifications={() => navigateToTab("Notifications")}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          lang={lang}
          onToggleLang={handleToggleLang}
          onNavigateHome={() => navigateToTab(currentUser?.role === "teacher" ? "LessonManagement" : "GeneralHome")}
        />

        <Suspense fallback={<div className="page-container" style={{ minHeight: "60vh" }} />}>
          {/* Dynamic Route Views */}
          {/* Student Views */}
          {activeTab === "GeneralHome" && (
          <GeneralHomeView
            courses={courses}
            enrolledCourseIds={enrolledCourseIds}
            onEnrollCourse={handleEnrollCourse}
            onNavigateToMyCourses={() => navigateToTab("MyCourses")}
            currentUser={currentUser || INITIAL_STUDENT_PROFILE}
            lang={lang}
          />
          )}

          {activeTab === "MyCourses" && (
          <MyCoursesView
            enrolledCourses={enrolledCoursesList}
            onNavigateToCatalog={() => navigateToTab("GeneralHome")}
            lang={lang}
            currentUser={currentUser || INITIAL_STUDENT_PROFILE}
          />
          )}

          {activeTab === "MySubmissions" && <MySubmissionsView />}

        {/* Shared Notifications View */}
          {activeTab === "Notifications" && (
          <NotificationsView
            notifications={notifications}
            onMarkNotificationRead={handleMarkNotificationRead}
            onNavigateToTab={(tab) => navigateToTab(tab)}
            onAddNotification={handleAddNotification}
            currentUser={currentUser || INITIAL_STUDENT_PROFILE}
            lang={lang}
          />
          )}

        {/* Teacher Views */}
          {activeTab === "LessonManagement" && (
          <LessonManagementView
            currentUser={currentUser || INITIAL_STUDENT_PROFILE}
            courses={courses}
            onCoursesChanged={setCourses}
          />
          )}

          {activeTab === "AIKnowledgeCenter" && (
            <AIKnowledgeCenterView lang={lang} />
          )}

          {activeTab === "QuizGen" && <QuizGeneratorView courses={courses} />}

          {activeTab === "Submissions" && <SubmissionsView />}

          {activeTab === "StudentAnalytics" && <StudentAnalyticsView />}

        {/* Full-Page Profile Route */}
          {activeTab === "Profile" && currentUser && (
          <ProfileView
            user={currentUser}
            onLogout={handleLogout}
            lang={lang}
          />
          )}
        </Suspense>
      </main>

      {/* Floating AI Assistant FAB at Bottom-Left in Emerald */}
      <FloatingAITutor
        currentCourseId={enrolledCoursesList[0]?.id || "chem-1st"}
        currentCourseTitle={enrolledCoursesList[0]?.title || (lang === "ar" ? "الكيمياء — الصف الأول الثانوي" : "1st Secondary Chemistry")}
        currentUser={currentUser || undefined}
        lang={lang}
      />

      {/* Global Background Upload Manager Widget - strictly for teachers only */}
      {currentUser?.role === "teacher" && <GlobalUploadWidget currentUser={currentUser} />}
    </div>
  );
}

export default App;

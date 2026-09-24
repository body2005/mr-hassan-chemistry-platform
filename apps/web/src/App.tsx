import { PageLoadingScreen } from "./components/PageLoadingScreen";
import { lazy, Suspense, useEffect, useState, useCallback, useMemo, useRef } from "react";
import { Sidebar, NavTab } from "./components/Sidebar";
import { Header } from "./components/Header";
import { GlobalUploadWidget } from "./components/GlobalUploadWidget";
import { Course, CurrentUser, NotificationItem } from "./types/lms";
import { useTranslation } from "./utils/i18n";

import { ApiClientError, authService, bootstrapService, courseService, notificationService } from "./services/lmsService";
import { useConfirm } from "./components/ConfirmWizard";
import { PaymentTarget, StudentEntitlement, paymentService } from "./services/paymentService";
import { realtimeService } from "./services/realtimeService";
import { LessonAccessModal } from "./components/LessonAccessModal";

// Views
import { LandingPageView } from "./views/LandingPageView";
// View chunk loaders stay lazy. A chunk is only preloaded after the user
// expresses intent on the corresponding navigation item.
const viewLoaders = {
  MyCourses: () => import("./views/MyCoursesView"),
  MySubmissions: () => import("./views/MySubmissionsView"),
  LessonManagement: () => import("./views/LessonManagementView"),
  QuizGen: () => import("./views/QuizGeneratorView"),
  Submissions: () => import("./views/SubmissionsView"),
  StudentAnalytics: () => import("./views/StudentAnalyticsView"),
  Notifications: () => import("./views/NotificationsView"),
  Profile: () => import("./views/ProfileView"),
  Payments: () => import("./views/PaymentView"),
  PaymentManagement: () => import("./views/PaymentManagementView"),
};

function preloadView(tabName: keyof typeof viewLoaders) {
  try {
    const loader = viewLoaders[tabName];
    if (loader) {
      void loader();
    }
  } catch {
    // Ignore preload error
  }
}

const MyCoursesView = lazy(() => viewLoaders.MyCourses().then((m) => ({ default: m.MyCoursesView })));
const MySubmissionsView = lazy(() => viewLoaders.MySubmissions().then((m) => ({ default: m.MySubmissionsView })));
const LessonManagementView = lazy(() => viewLoaders.LessonManagement().then((m) => ({ default: m.LessonManagementView })));
const QuizGeneratorView = lazy(() => viewLoaders.QuizGen().then((m) => ({ default: m.QuizGeneratorView })));
const SubmissionsView = lazy(() => viewLoaders.Submissions().then((m) => ({ default: m.SubmissionsView })));
const StudentAnalyticsView = lazy(() => viewLoaders.StudentAnalytics().then((m) => ({ default: m.StudentAnalyticsView })));
const NotificationsView = lazy(() => viewLoaders.Notifications().then((m) => ({ default: m.NotificationsView })));
const ProfileView = lazy(() => viewLoaders.Profile().then((m) => ({ default: m.ProfileView })));
const PaymentView = lazy(() => viewLoaders.Payments().then((m) => ({ default: m.PaymentView })));
const PaymentManagementView = lazy(() => viewLoaders.PaymentManagement().then((m) => ({ default: m.PaymentManagementView })));
import { AuthView } from "./views/AuthView";

const VALID_TABS = [
  "Landing",
  "Auth",
  "MyCourses",
  "MySubmissions",
  "LessonManagement",
  "QuizGen",
  "Submissions",
  "StudentAnalytics",
  "Notifications",
  "Profile",
  "Payments",
  "PaymentManagement",
] as const;

type AllTabs = (typeof VALID_TABS)[number];

const STUDENT_TABS = new Set<AllTabs>(["MyCourses", "MySubmissions", "Notifications", "Payments", "Profile"]);
const STAFF_TABS = new Set<AllTabs>(["LessonManagement", "QuizGen", "Submissions", "StudentAnalytics", "Notifications", "PaymentManagement", "Profile"]);

function homeTab(user: CurrentUser): AllTabs {
  return user.role === "student" ? "MyCourses" : "LessonManagement";
}

function tabAllowed(tab: AllTabs, user: CurrentUser): boolean {
  return (user.role === "student" ? STUDENT_TABS : STAFF_TABS).has(tab);
}

function getTabFromHash(): AllTabs | null {
  const raw = window.location.hash.replace("#", "").trim().toLowerCase();
  if (!raw) return null;
  const match = VALID_TABS.find((t) => t.toLowerCase() === raw);
  return match || null;
}

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "temporarily_unavailable";

function App() {
  const confirm = useConfirm();
  const cachedUser = useMemo(() => authService.getCachedUser(), []);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(() => cachedUser);
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() => (cachedUser ? "authenticated" : "loading"));
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [authLoading, setAuthLoading] = useState(() => !cachedUser);
  const authSyncId = useRef(0);

  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("lms_theme");
    return (saved as "light" | "dark") || "light";
  });

  const { lang, toggleLang: handleToggleLang } = useTranslation();

  const [courses, setCourses] = useState<Course[]>(() => courseService.getCachedCourses());
  const [enrolledCourseIds, setEnrolledCourseIds] = useState<string[]>([]);
  const [entitlements, setEntitlements] = useState<StudentEntitlement[]>([]);
  const [checkoutTarget, setCheckoutTarget] = useState<PaymentTarget | null>(null);

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [selectedAccessRequestId, setSelectedAccessRequestId] = useState<string | null>(null);
  const [isAccessModalOpen, setIsAccessModalOpen] = useState(false);

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

    async function handleBootstrapSync() {
      const requestId = ++authSyncId.current;
      try {
        const bootstrap = await bootstrapService.getBootstrap();
        if (requestId !== authSyncId.current) return;
        if (bootstrap.authenticated && bootstrap.user) {
          setCurrentUser(bootstrap.user);
          setAuthStatus("authenticated");
          setRetryAttempt(0);
          if (bootstrap.notifications.length > 0) {
            setNotifications(bootstrap.notifications);
          }
          if (bootstrap.courses.length > 0) {
            setCourses(bootstrap.courses);
          }
          if (bootstrap.user.role === "student") {
            setEnrolledCourseIds(bootstrap.enrolledCourseIds);
            setEntitlements(bootstrap.entitlements);
          }
        } else {
          setCurrentUser(null);
          setAuthStatus("unauthenticated");
          setRetryAttempt(0);
        }
      } catch (error) {
        if (requestId !== authSyncId.current) return;
        console.error("Bootstrap sync error", error);
        setAuthStatus("temporarily_unavailable");
      } finally {
        if (requestId === authSyncId.current) setAuthLoading(false);
      }
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
    window.addEventListener("lms_user_updated", handleBootstrapSync);
    window.addEventListener("lms_courses_updated", handleCoursesSync);

    void handleBootstrapSync();

    return () => {
      window.removeEventListener("lms_notifications_updated", handleNotificationsSync);
      window.removeEventListener("lms_user_updated", handleBootstrapSync);
      window.removeEventListener("lms_courses_updated", handleCoursesSync);
    };
  }, []);

  // Exponential backoff retry when auth server is temporarily unavailable
  useEffect(() => {
    if (authStatus !== "temporarily_unavailable") return;
    const delay = Math.min(2000 * Math.pow(1.5, retryAttempt), 30000);
    const timer = setTimeout(() => {
      setRetryAttempt((prev) => prev + 1);
      window.dispatchEvent(new Event("lms_user_updated"));
    }, delay);
    return () => clearTimeout(timer);
  }, [authStatus, retryAttempt]);

  // Track active navigation tab with Google Chrome native History & Hash support
  const [activeTab, setActiveTab] = useState<AllTabs>(() => {
    if (typeof window !== "undefined" && window.location.hash.toLowerCase() === "#generalhome") {
      window.location.hash = "#mycourses";
    }
    const fromHash = getTabFromHash();
    if (fromHash && fromHash !== "Landing" && fromHash !== "Auth") {
      return fromHash;
    }

    const savedTab = typeof localStorage !== "undefined" ? localStorage.getItem("lms_active_tab") : null;
    if (savedTab === "GeneralHome" && typeof localStorage !== "undefined") {
      localStorage.setItem("lms_active_tab", "MyCourses");
      return "MyCourses";
    }
    if (savedTab && VALID_TABS.includes(savedTab as AllTabs)) {
      return savedTab as AllTabs;
    }

    return "Landing";
  });

  const [authInitialTab, setAuthInitialTab] = useState<"signin" | "register">("signin");
  const [menuOpen, setMenuOpen] = useState(false);

  // Navigate to Tab and push to Google Chrome history stack
  const navigateToTab = useCallback((requestedTab: AllTabs | NavTab | string) => {
    const rawTab = (requestedTab === "GeneralHome" ? "MyCourses" : requestedTab) as AllTabs;
    const targetTab = currentUser && rawTab !== "Landing" && rawTab !== "Auth" && !tabAllowed(rawTab, currentUser)
      ? homeTab(currentUser)
      : rawTab;
    setActiveTab(targetTab);
    localStorage.setItem("lms_active_tab", targetTab);
    const targetHash = `#${targetTab.toLowerCase()}`;
    if (window.location.hash.toLowerCase() !== targetHash) {
      window.location.hash = targetHash;
    }
  }, [currentUser]);

  useEffect(() => {
    if (currentUser && (activeTab === "Landing" || activeTab === "Auth")) {
      navigateToTab(homeTab(currentUser));
    } else if (currentUser && !tabAllowed(activeTab, currentUser)) {
      navigateToTab(homeTab(currentUser));
    }
  }, [currentUser, activeTab, navigateToTab]);

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
        const safeTab = currentUser && match !== "Landing" && match !== "Auth" && !tabAllowed(match, currentUser)
          ? homeTab(currentUser)
          : match;
        setActiveTab(safeTab);
        localStorage.setItem("lms_active_tab", safeTab);
      }
    }

    window.addEventListener("hashchange", handleChromeNavigation);
    window.addEventListener("popstate", handleChromeNavigation);

    return () => {
      window.removeEventListener("hashchange", handleChromeNavigation);
      window.removeEventListener("popstate", handleChromeNavigation);
    };
  }, [activeTab, currentUser]);

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
      setEntitlements([]);
      return;
    }

    void courseService.getCourses().then(setCourses).catch(() => setCourses([]));
    if (currentUser.role === "student") {
      void Promise.all([courseService.getEnrolledCourseIds(), paymentService.getMyEntitlements()])
        .then(([enrollments, access]) => {
          setEnrolledCourseIds(enrollments);
          setEntitlements(access);
        })
        .catch(() => {
          setEnrolledCourseIds([]);
          setEntitlements([]);
        });
    } else {
      setEnrolledCourseIds([]);
      setEntitlements([]);
    }
  }, [currentUser?.id, currentUser?.role]);

  const refreshStudentAccess = useCallback(() => {
    if (currentUser?.role !== "student") return;
    void Promise.all([courseService.getEnrolledCourseIds(), paymentService.getMyEntitlements()])
      .then(([enrollments, access]) => {
        setEnrolledCourseIds(enrollments);
        setEntitlements(access);
      })
      .catch(() => undefined);
  }, [currentUser]);

  // Real-time EventSource connection lifecycle
  useEffect(() => {
    if (!currentUser) {
      realtimeService.disconnect();
      return;
    }

    realtimeService.connect();

    const handleLessonUnlocked = () => {
      refreshStudentAccess();
    };

    window.addEventListener("lms_lesson_unlocked", handleLessonUnlocked);
    window.addEventListener("lms_payment_updated", handleLessonUnlocked);

    return () => {
      window.removeEventListener("lms_lesson_unlocked", handleLessonUnlocked);
      window.removeEventListener("lms_payment_updated", handleLessonUnlocked);
      realtimeService.disconnect();
    };
  }, [currentUser, refreshStudentAccess]);

  function handleToggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  async function handleEnrollCourse(courseId: string) {
    try {
      const updated = await courseService.enrollCourse(courseId);
      setEnrolledCourseIds(updated);
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 402) {
        // Whole-course checkout is no longer offered to students.  Send them
        // to the lesson-only checkout picker instead.
        setCheckoutTarget({ productType: "lesson" });
        navigateToTab("Payments");
        return;
      }
      await confirm({
        title: "تعذر التسجيل في المقرر",
        message: error instanceof Error ? error.message : "حدث خطأ غير متوقع. حاول مرة أخرى.",
        cancelLabel: "إغلاق",
        tone: "warning",
      });
    }
  }
  void handleEnrollCourse;

  function handleMarkNotificationRead(id: string) {
    void notificationService.markAsRead(id).then(setNotifications).catch(() => undefined);
  }

  function handleAddNotification(notif: NotificationItem) {
    void notificationService.saveNotification(notif).then(setNotifications).catch(() => undefined);
  }

  function handleSelectNotification(notif: NotificationItem) {
    handleMarkNotificationRead(notif.id);
    if (
      notif.type === "lesson_access" ||
      (notif.actionUrl && (notif.actionUrl.includes("/access-requests/") || notif.actionUrl.includes("/lessons/access-requests/")))
    ) {
      const match = notif.actionUrl?.match(/\/access-requests\/([0-9a-fA-F-]+)/);
      if (match && match[1]) {
        setSelectedAccessRequestId(match[1]);
        setIsAccessModalOpen(true);
        return;
      }
    }
    if (notif.type === "payment" || notif.paymentOrderId || (notif.actionUrl && notif.actionUrl.includes("/payments/orders/"))) {
      navigateToTab("PaymentManagement");
      return;
    }
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
      realtimeService.disconnect();
      await authService.logout();
    } catch {
      // Clear the local UI even if the session endpoint is temporarily unavailable.
    } finally {
      authSyncId.current += 1;
      setCurrentUser(null);
      setAuthStatus("unauthenticated");
      setAuthLoading(false);
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

  const activeEntitlements = useMemo(() => entitlements.filter((item) => item.active), [entitlements]);

  if ((authLoading && !currentUser && authStatus === "loading") || isLoggingIn) {
    return <PageLoadingScreen brandTitle="منصة الكيمياء التعليمية — مستر حسن شعبان" />;
  }

  // If user is not logged in: show Landing Page or Auth Page
  if (!currentUser) {
    if (activeTab === "Auth") {
      return (
        <AuthView
          initialTab={authInitialTab}
          onLoginSuccess={(user) => {
            authSyncId.current += 1;
            setIsLoggingIn(true);
            setCurrentUser(user);
            setAuthStatus("authenticated");
            setRetryAttempt(0);
            const targetTab = user.role === "student" ? "MyCourses" : "LessonManagement";
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
      <div>
        {authStatus === "temporarily_unavailable" && (
          <div
            role="alert"
            style={{
              background: "#b45309",
              color: "#ffffff",
              padding: "10px 16px",
              textAlign: "center",
              fontSize: "13px",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "12px",
              position: "sticky",
              top: 0,
              zIndex: 99999,
              boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
            }}
          >
            <span>⚠️ الخدمة غير متاحة مؤقتًا، جاري محاولة إعادة الاتصال بالخادم...</span>
            <button
              type="button"
              onClick={() => {
                setRetryAttempt(0);
                window.dispatchEvent(new Event("lms_user_updated"));
              }}
              style={{
                padding: "4px 12px",
                background: "rgba(255,255,255,0.25)",
                border: "1px solid rgba(255,255,255,0.4)",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "12px",
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              إعادة المحاولة الآن
            </button>
          </div>
        )}
        <LandingPageView
          courses={courses}
          onNavigateToAuth={handleNavigateToAuth}
          lang={lang}
          onToggleLang={handleToggleLang}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />
      </div>
    );
  }

  // Internal Authenticated Platform View
  return (
    <div className="app-shell">
      {authStatus === "temporarily_unavailable" && (
        <div
          role="alert"
          style={{
            background: "#b45309",
            color: "#ffffff",
            padding: "10px 16px",
            textAlign: "center",
            fontSize: "13px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "12px",
            position: "sticky",
            top: 0,
            zIndex: 99999,
            boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
          }}
        >
          <span>⚠️ الخدمة غير متاحة مؤقتًا، جاري محاولة إعادة الاتصال بالخادم... (البيانات المعروضة من الذاكرة المؤقتة)</span>
          <button
            type="button"
            onClick={() => {
              setRetryAttempt(0);
              window.dispatchEvent(new Event("lms_user_updated"));
            }}
            style={{
              padding: "4px 12px",
              background: "rgba(255,255,255,0.25)",
              border: "1px solid rgba(255,255,255,0.4)",
              borderRadius: "4px",
              color: "#fff",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            إعادة المحاولة الآن
          </button>
        </div>
      )}
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab as NavTab}
        onSelectTab={(tab) => navigateToTab(tab)}
        onHoverTab={(tab) => {
          if (tab in viewLoaders) preloadView(tab as keyof typeof viewLoaders);
        }}
        menuOpen={menuOpen}
        onCloseMenu={() => setMenuOpen(false)}
        currentUser={currentUser}
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
          onNavigateHome={() => navigateToTab(currentUser?.role === "teacher" ? "LessonManagement" : "MyCourses")}
          currentUser={currentUser}
        />

        <Suspense fallback={<div className="page-container" style={{ minHeight: "60vh" }} />}>
          {/* Dynamic Route Views */}
          {/* Student Views */}
          {activeTab === "MyCourses" && currentUser.role === "student" && (
          <MyCoursesView
            enrolledCourses={enrolledCoursesList}
            onNavigateToCatalog={() => navigateToTab("Payments")}
            lang={lang}
            currentUser={currentUser}
            purchasedLessonIds={activeEntitlements.filter((item) => item.entitlement_type === "lesson").map((item) => item.resource_id || "")}
            onCheckout={(target) => { setCheckoutTarget(target); navigateToTab("Payments"); }}
            onToggleMenu={() => setMenuOpen(!menuOpen)}
            menuOpen={menuOpen}
            notifications={notifications}
            onMarkNotificationRead={handleMarkNotificationRead}
            onSelectNotification={handleSelectNotification}
            onNavigateToNotifications={() => navigateToTab("Notifications")}
            theme={theme}
            onToggleTheme={handleToggleTheme}
            onToggleLang={handleToggleLang}
            onNavigateHome={() => navigateToTab("MyCourses")}
          />
          )}

          {activeTab === "MySubmissions" && currentUser.role === "student" && (
            <MySubmissionsView currentUser={currentUser} />
          )}

        {/* Shared Notifications View */}
          {activeTab === "Notifications" && (
          <NotificationsView
            notifications={notifications}
            onMarkNotificationRead={handleMarkNotificationRead}
            onNavigateToTab={(tab) => navigateToTab(tab)}
            onAddNotification={handleAddNotification}
            currentUser={currentUser}
            lang={lang}
          />
          )}

        {/* Teacher Views */}
          {activeTab === "LessonManagement" && currentUser.role !== "student" && (
          <LessonManagementView
            currentUser={currentUser}
            courses={courses}
            onCoursesChanged={setCourses}
          />
          )}

          {activeTab === "QuizGen" && currentUser.role !== "student" && (
            <QuizGeneratorView courses={courses} currentUser={currentUser} />
          )}

          {activeTab === "Submissions" && currentUser.role !== "student" && <SubmissionsView />}

          {activeTab === "StudentAnalytics" && currentUser.role !== "student" && <StudentAnalyticsView />}

          {activeTab === "Payments" && currentUser.role === "student" && (
            <PaymentView
              courses={courses}
              currentUser={currentUser}
              initialTarget={checkoutTarget}
              onEntitlementsChanged={refreshStudentAccess}
            />
          )}

          {activeTab === "PaymentManagement" && currentUser.role !== "student" && (
            <PaymentManagementView courses={courses} onCoursesChanged={setCourses} />
          )}

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

      {/* Global Background Upload Manager Widget - strictly for teachers only */}
      {currentUser?.role !== "student" && (
        <GlobalUploadWidget currentUser={currentUser} menuOpen={menuOpen} />
      )}

      {/* Lesson Access Approval Modal for Teachers and Students */}
      <LessonAccessModal
        requestId={selectedAccessRequestId}
        isOpen={isAccessModalOpen}
        onClose={() => {
          setIsAccessModalOpen(false);
          setSelectedAccessRequestId(null);
        }}
        onUpdated={() => {
          refreshStudentAccess();
          void notificationService.getNotifications().then(setNotifications).catch(() => undefined);
        }}
        isTeacher={currentUser?.role !== "student"}
      />
    </div>
  );
}

export default App;

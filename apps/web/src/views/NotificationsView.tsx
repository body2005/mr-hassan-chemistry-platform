import React, { useState, useEffect } from "react";
import {
  Bell,
  Calendar,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Clock,
  ExternalLink,
  FileQuestion,
  FileText,
  Plus,
  Sparkles,
  Video,
  X,
  XCircle,
  CheckCircle2,
} from "lucide-react";
import { CurrentUser, NotificationItem, NotificationSchedule, StudentProfile } from "../types/lms";
import { NavTab } from "../components/Sidebar";
import { calendarService, notificationService } from "../services/lmsService";

interface NotificationsViewProps {
  notifications: NotificationItem[];
  onMarkNotificationRead: (id: string) => void;
  onNavigateToTab: (tab: NavTab) => void;
  onAddNotification?: (notif: NotificationItem) => void;
  currentUser: CurrentUser;
  lang?: string;
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
  isPublishedToStudents?: boolean;
  quizDurationMinutes?: number;
  publishStartDate?: string;
  publishStartTime?: string;
  closeDeadline?: string;
}

const DEFAULT_SCHEDULES: NotificationSchedule[] = [
  {
    academicYear: "1st_secondary",
    academicYearLabel: "الصف الأول الثانوي",
    days: [],
    time: "06:00 م",
    active: true,
  },
  {
    academicYear: "2nd_secondary",
    academicYearLabel: "الصف الثاني الثانوي",
    days: [],
    time: "07:00 م",
    active: true,
  },
  {
    academicYear: "3rd_secondary",
    academicYearLabel: "الصف الثالث الثانوي",
    days: [],
    time: "08:00 م",
    active: true,
  },
];

const DEFAULT_CALENDAR_EVENTS: CalendarScheduleEvent[] = [];

const WEEK_DAYS = ["السبت", "الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"];

const TIME_OPTIONS = [
  "01:00", "02:00", "03:00", "04:00", "05:00", "06:00",
  "07:00", "08:00", "09:00", "10:00", "11:00", "12:00",
  "01:30", "02:30", "03:30", "04:30", "05:30", "06:30",
  "07:30", "08:30", "09:30", "10:30", "11:30", "12:30",
];

const ARABIC_MONTHS = [
  "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
];

function parseScheduleTime(timeStr: string): { hour: string; period: "ص" | "م" } {
  const period = timeStr && timeStr.includes("ص") ? "ص" : "م";
  const match = timeStr ? timeStr.match(/(\d{1,2}(?::\d{2})?)/) : null;
  let hour = match ? match[1] : "06:00";
  if (!hour.includes(":")) {
    hour = hour.padStart(2, "0") + ":00";
  } else {
    const [h, m] = hour.split(":");
    hour = `${h.padStart(2, "0")}:${(m || "00").padStart(2, "0")}`;
  }
  if (!TIME_OPTIONS.includes(hour)) {
    hour = "06:00";
  }
  return { hour, period };
}

function formatIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getArabicDayName(d: Date): string {
  const map = ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
  return map[d.getDay()];
}

function getMonthYearTitle(d: Date): string {
  return `${ARABIC_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function getGradeLabel(g: "1st_secondary" | "2nd_secondary" | "3rd_secondary"): string {
  if (g === "2nd_secondary") return "الصف الثاني الثانوي";
  if (g === "3rd_secondary") return "الصف الثالث الثانوي";
  return "الصف الأول الثانوي";
}

function getContentTypeLabel(t: string): string {
  if (t === "assignment") return "واجب منزلي";
  if (t === "quiz") return "اختبار تقييمي";
  if (t === "general") return "تنبيه عام";
  return "رفع وشرح درس جديد";
}

function cleanLegacyMockSchedules(arr: NotificationSchedule[]): NotificationSchedule[] {
  return arr.length ? arr : DEFAULT_SCHEDULES;
}

function deduplicateNotifications(list: NotificationItem[]): NotificationItem[] {
  if (!Array.isArray(list)) return [];
  const seenIds = new Set<string>();
  const seenSignatures = new Set<string>();
  return list.filter((n) => {
    if (!n || !n.id) return false;
    const sig = `${n.targetYear || "all"}_${(n.title || "").trim()}_${(n.dueDate || "")}_${(n.message || "").slice(0, 50)}`;
    if (seenIds.has(n.id) || seenSignatures.has(sig)) return false;
    seenIds.add(n.id);
    seenSignatures.add(sig);
    return true;
  });
}

export const NotificationsView: React.FC<NotificationsViewProps> = ({
  notifications,
  onMarkNotificationRead,
  onNavigateToTab,
  onAddNotification,
  currentUser,
}) => {
  const isTeacher = currentUser.role === "teacher";
  const studentYear = ((currentUser as StudentProfile).academicYear as "1st_secondary" | "2nd_secondary" | "3rd_secondary") || "1st_secondary";
  const initialGrade = !isTeacher ? studentYear : "1st_secondary";

  const [selectedGrade, setSelectedGrade] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">(initialGrade);
  const [calendarCurrentDate, setCalendarCurrentDate] = useState<Date>(() => new Date());
  const [isMonthPickerOpen, setIsMonthPickerOpen] = useState(false);
  const [pickerYear, setPickerYear] = useState<number>(() => new Date().getFullYear());

  useEffect(() => {
    setPickerYear(calendarCurrentDate.getFullYear());
  }, [calendarCurrentDate]);

  const [schedules, setSchedules] = useState<NotificationSchedule[]>(DEFAULT_SCHEDULES);
  const [calendarEvents, setCalendarEvents] = useState<CalendarScheduleEvent[]>(DEFAULT_CALENDAR_EVENTS);

  const [activeNotifications, setActiveNotifications] = useState<NotificationItem[]>(() => deduplicateNotifications(notifications));

  useEffect(() => {
    setActiveNotifications(deduplicateNotifications(notifications));
  }, [notifications]);

  // Sync state between teacher and student in real time
  const reloadFromServer = async () => {
    try {
      const [remoteSchedules, remoteEvents, remoteNotifications] = await Promise.all([
        calendarService.getNotificationSchedules(),
        calendarService.getCalendarEvents(),
        notificationService.getNotifications(),
      ]);
      const normalizedSchedules = cleanLegacyMockSchedules(remoteSchedules).map((s) => {
        const { hour, period } = parseScheduleTime(s.time);
        return { ...s, time: `${hour} ${period}` };
      });
      setSchedules(normalizedSchedules);
      setCalendarEvents(remoteEvents);
      setActiveNotifications(deduplicateNotifications(remoteNotifications));
    } catch (e) {
      console.error(e);
    }
  };

  // Sync selectedGrade and reload whenever the current logged-in user changes (e.g. role switch)
  useEffect(() => {
    if (!isTeacher) {
      setSelectedGrade(studentYear);
    }
    void reloadFromServer();
  }, [currentUser, isTeacher, studentYear]);

  useEffect(() => {
    void reloadFromServer();

    const handleSync = () => void reloadFromServer();
    window.addEventListener("lms_schedule_updated", handleSync);
    window.addEventListener("lms_notifications_updated", handleSync);

    return () => {
      window.removeEventListener("lms_schedule_updated", handleSync);
      window.removeEventListener("lms_notifications_updated", handleSync);
    };
  }, []);

  // In-page Wizard State (معالج إضافة الموعد)
  const [wizardState, setWizardState] = useState<{
    isOpen: boolean;
    step: 1 | 2 | 3;
    editingEventId?: string;
    selectedDate: string;
    dayTitle: string;
    timeHour: string;
    timePeriod: "ص" | "م";
    contentType: "lesson" | "assignment" | "quiz" | "general";
    isRecurringWeekly: boolean;
    isPublishedToStudents: boolean;
    quizDurationMinutes: number;
    isScheduledNotif: boolean;
    scheduledNotifDate: string;
    scheduledNotifHour: string;
    scheduledNotifPeriod: "ص" | "م";
  }>({
    isOpen: false,
    step: 1,
    editingEventId: undefined,
    selectedDate: "2026-08-25",
    dayTitle: "",
    timeHour: "06:00",
    timePeriod: "م",
    contentType: "lesson",
    isRecurringWeekly: true,
    isPublishedToStudents: true,
    quizDurationMinutes: 45,
    isScheduledNotif: false,
    scheduledNotifDate: "",
    scheduledNotifHour: "06:00",
    scheduledNotifPeriod: "م",
  });

  const [activeFilter, setActiveFilter] = useState<"all" | "assignment" | "quiz" | "system">("all");
  const [scheduleSavedMsg, setScheduleSavedMsg] = useState(false);
  const [teacherTargetAudience, setTeacherTargetAudience] = useState<"all" | "1st_secondary" | "2nd_secondary" | "3rd_secondary">("all");
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [broadcastTargetGrade, setBroadcastTargetGrade] = useState<"all" | "1st_secondary" | "2nd_secondary" | "3rd_secondary">("all");
  const [broadcastTitle, setBroadcastTitle] = useState("");
  const [broadcastMessage, setBroadcastMessage] = useState("");
  const [broadcastType, setBroadcastType] = useState<"system" | "assignment" | "quiz" | "warning">("system");
  const [broadcastDueDate, setBroadcastDueDate] = useState("");
  const [broadcastActionTab, setBroadcastActionTab] = useState<string>("GeneralHome");

  async function handleSendBroadcast(e: React.FormEvent) {
    e.preventDefault();
    if (!broadcastTitle.trim() || !broadcastMessage.trim()) return;

    const newNotif: NotificationItem = {
      id: `notif_${Date.now()}`,
      title: broadcastTitle.trim(),
      message: broadcastMessage.trim(),
      type: broadcastType,
      targetYear: broadcastTargetGrade,
      dueDate: broadcastDueDate.trim() || undefined,
      createdAt: "الآن",
      read: false,
      actionTab: broadcastActionTab,
    };

    if (onAddNotification) onAddNotification(newNotif);
    else await notificationService.saveNotification(newNotif);

    setIsBroadcastModalOpen(false);
    setBroadcastTitle("");
    setBroadcastMessage("");
    setBroadcastDueDate("");
    setScheduleSavedMsg(true);
    setTimeout(() => setScheduleSavedMsg(false), 3000);
  }

  const gradeSchedule = schedules.find((s) => s.academicYear === selectedGrade);

  function toggleScheduleDay(academicYear: string, day: string) {
    if (!isTeacher) return;

    setSchedules((prev) => {
      const updated = prev.map((s) => {
        if (s.academicYear === academicYear) {
          const days = s.days.includes(day)
            ? s.days.filter((d) => d !== day)
            : [...s.days, day];
          return { ...s, days };
        }
        return s;
      });
      void calendarService.saveNotificationSchedules(updated);
      window.dispatchEvent(new Event("lms_schedule_updated"));
      return updated;
    });

    setScheduleSavedMsg(true);
    setTimeout(() => setScheduleSavedMsg(false), 2500);
  }
  void toggleScheduleDay;

  async function handleSaveWizardSchedule() {
    const fullTimeStr = `${wizardState.timeHour} ${wizardState.timePeriod}`;
    const newEvent: CalendarScheduleEvent = {
      id: wizardState.editingEventId || `evt_${Date.now()}`,
      academicYear: selectedGrade,
      date: wizardState.selectedDate,
      dayName: wizardState.dayTitle.trim() || `${getArabicDayName(new Date(wizardState.selectedDate))} - موعد إرسال`,
      time: fullTimeStr,
      contentType: wizardState.contentType,
      isRecurringWeekly: wizardState.isRecurringWeekly,
      isPublishedToStudents: wizardState.isPublishedToStudents,
      quizDurationMinutes: wizardState.contentType === "quiz" ? wizardState.quizDurationMinutes : undefined,
      isCancelled: false,
      publishStartDate: wizardState.isScheduledNotif ? wizardState.scheduledNotifDate : undefined,
      publishStartTime: wizardState.isScheduledNotif ? `${wizardState.scheduledNotifHour} ${wizardState.scheduledNotifPeriod}` : undefined,
    };

    // Delegate to calendarService
    const updatedEvents = await calendarService.saveCalendarEvent(newEvent);
    setCalendarEvents(updatedEvents);

    // Build the notification createdAt — either scheduled ISO date or "الآن"
    let notifCreatedAt = "الآن";
    if (wizardState.isScheduledNotif && wizardState.scheduledNotifDate) {
      const schedDate = wizardState.scheduledNotifDate;
      const schedHour = wizardState.scheduledNotifHour || "06:00";
      const schedPeriod = wizardState.scheduledNotifPeriod || "م";
      const [hh] = schedHour.split(":");
      let hour24 = parseInt(hh, 10) || 6;
      if (schedPeriod === "م" && hour24 < 12) hour24 += 12;
      if (schedPeriod === "ص" && hour24 === 12) hour24 = 0;
      notifCreatedAt = `${schedDate}T${String(hour24).padStart(2, "0")}:00:00`;
    }

    // If teacher set event to visible for students, delegate to notificationService
    if (wizardState.isPublishedToStudents) {
      const autoNotif: NotificationItem = {
        id: `notif_sched_${newEvent.id}`,
        title: `${wizardState.contentType === "quiz" ? "موعد اختبار بالجدول" : "موعد جديد بالجدول"}: ${newEvent.dayName}`,
        message: `تم تثبيت موعد (${newEvent.dayName}) في تقويم ${getGradeLabel(selectedGrade)} يوم ${getArabicDayName(new Date(wizardState.selectedDate))} الموافق ${wizardState.selectedDate} الساعة ${fullTimeStr}${wizardState.contentType === "quiz" ? ` (مدة الاختبار: ${wizardState.quizDurationMinutes} دقيقة)` : ""}.`,
        type: wizardState.contentType === "quiz" ? "quiz" : wizardState.contentType === "assignment" ? "assignment" : "system",
        targetYear: selectedGrade,
        createdAt: notifCreatedAt,
        read: false,
        actionTab: "Notifications",
        quizDurationMinutes: wizardState.contentType === "quiz" ? wizardState.quizDurationMinutes : undefined,
      };

      const updatedNotifs = await notificationService.saveNotification(autoNotif);
      setActiveNotifications(updatedNotifs);
      if (onAddNotification) {
        onAddNotification(autoNotif);
      }
    }

    // If weekly recurrence was checked, update schedules
    if (wizardState.isRecurringWeekly) {
      const dayName = getArabicDayName(new Date(wizardState.selectedDate));
      setSchedules((prev) => {
        const updated = prev.map((s) => {
          if (s.academicYear === selectedGrade) {
            const days = s.days.includes(dayName) ? s.days : [...s.days, dayName];
            return { ...s, days, time: fullTimeStr };
          }
          return s;
        });
        calendarService.saveNotificationSchedules(updated);
        return updated;
      });
    }

    setWizardState((prev) => ({ ...prev, isOpen: false }));
    setScheduleSavedMsg(true);
    setTimeout(() => setScheduleSavedMsg(false), 3500);
  }

  async function handleCancelSchedule(dateStr: string) {
    if (!isTeacher) return;

    const normTargetDate = (dateStr || "").split("T")[0];
    const targetEvent = calendarEvents.find(
      (e) => e.academicYear === selectedGrade && (e.date || "").split("T")[0] === normTargetDate
    );
    const dayName = getArabicDayName(new Date(dateStr));
    const eventTitle = targetEvent?.dayName || `${dayName} - موعد مجدول`;

    const updatedEvents = await calendarService.cancelCalendarEvent(dateStr, selectedGrade);
    setCalendarEvents(updatedEvents);

    // Send Cancellation Warning Notification to Students via notificationService
    const cancelNotif: NotificationItem = {
      id: `notif_cancel_${Date.now()}`,
      title: "تنبيه: تم إلغاء موعد مجدول",
      message: `تنبيه لطلاب ${getGradeLabel(selectedGrade)}: تم إلغاء موعد (${eventTitle}) المقرر ليوم ${dayName} الموافق ${dateStr} من قِبل المعلم.`,
      type: "warning",
      targetYear: selectedGrade,
      createdAt: "الآن",
      read: false,
      actionTab: "Notifications",
    };

    const updatedNotifs = await notificationService.saveNotification(cancelNotif);
    setActiveNotifications(updatedNotifs);
    if (onAddNotification) {
      onAddNotification(cancelNotif);
    }

    setWizardState((prev) => ({ ...prev, isOpen: false }));
    setScheduleSavedMsg(true);
    setTimeout(() => setScheduleSavedMsg(false), 3000);
  }

  function handleActionClick(n: NotificationItem) {
    onMarkNotificationRead(n.id);
    if (n.actionTab) {
      onNavigateToTab(n.actionTab as NavTab);
    } else if (n.type === "assignment") {
      onNavigateToTab(isTeacher ? "Submissions" : "MySubmissions");
    } else if (n.type === "quiz") {
      onNavigateToTab(isTeacher ? "QuizGen" : "MyCourses");
    } else {
      onNavigateToTab(isTeacher ? "LessonManagement" : "MyCourses");
    }
  }

  function renderMonthCalendarCells() {
    const year = calendarCurrentDate.getFullYear();
    const month = calendarCurrentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDayIndex = new Date(year, month, 1).getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
    // Saturday start week offset: Sat=0, Sun=1, Mon=2, Tue=3, Wed=4, Thu=5, Fri=6
    const startingOffset = (firstDayIndex + 1) % 7;

    const cells = [];
    // Empty padding cells
    for (let i = 0; i < startingOffset; i++) {
      cells.push(
        <div
          key={`empty-${i}`}
          style={{
            minHeight: "48px",
            background: "var(--bg-surface)",
            border: "1px dashed var(--border-color)",
            borderRadius: "8px",
            opacity: 0.3,
          }}
        />
      );
    }

    // Current month days
    for (let dayNum = 1; dayNum <= daysInMonth; dayNum++) {
      const cellDate = new Date(year, month, dayNum);
      const dateStr = formatIsoDate(cellDate);
      const dayName = getArabicDayName(cellDate);
      const isSelected = wizardState.isOpen && wizardState.selectedDate === dateStr;

      const dayEvents = calendarEvents.filter((e) => {
        const eventDateNorm = (e.date || "").split("T")[0].trim();
        const matchesGrade = e.academicYear === selectedGrade;
        const matchesDate = eventDateNorm === dateStr;
        // For students: show events that are published OR cancelled (so they see the cancellation badge)
        const isVisible = isTeacher || e.isPublishedToStudents === true || e.isCancelled === true;
        return matchesGrade && matchesDate && isVisible;
      });

      const isRecurringDay = gradeSchedule?.days.includes(dayName);

      const openWizard = (evt: CalendarScheduleEvent | undefined, targetDate: string) => {
        if (!isTeacher) return;
        const targetDayName = getArabicDayName(new Date(targetDate));
        setWizardState({
          isOpen: true,
          step: 1,
          editingEventId: evt ? evt.id : undefined,
          selectedDate: targetDate,
          dayTitle: evt ? evt.dayName : `${targetDayName} - موعد إرسال مجدول`,
          timeHour: evt ? parseScheduleTime(evt.time).hour : (gradeSchedule?.time ? parseScheduleTime(gradeSchedule.time).hour : "06:00"),
          timePeriod: evt ? parseScheduleTime(evt.time).period : (gradeSchedule?.time ? parseScheduleTime(gradeSchedule.time).period : "م"),
          contentType: evt ? evt.contentType : "lesson",
          isRecurringWeekly: evt?.isRecurringWeekly ?? isRecurringDay ?? true,
          isPublishedToStudents: evt?.isPublishedToStudents ?? true,
          quizDurationMinutes: evt?.quizDurationMinutes ?? 45,
          isScheduledNotif: !!(evt?.publishStartDate),
          scheduledNotifDate: evt?.publishStartDate || targetDate,
          scheduledNotifHour: evt?.publishStartTime ? parseScheduleTime(evt.publishStartTime).hour : "06:00",
          scheduledNotifPeriod: evt?.publishStartTime ? parseScheduleTime(evt.publishStartTime).period : "م",
        });
      };

      cells.push(
        <div
          key={dateStr}
          className="calendar-cell"
          onClick={() => {
            if (!isTeacher) return;
            openWizard(dayEvents.length === 1 ? dayEvents[0] : undefined, dateStr);
          }}
          style={{
            minHeight: "48px",
            background: isSelected
              ? "var(--bg-accent)"
              : "var(--bg-surface)",
            border: isSelected
              ? "2px solid #059669"
              : "1px solid var(--border-color)",
            borderRadius: "10px",
            padding: "8px 6px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: isTeacher ? "pointer" : "default",
            transition: "all 0.15s ease",
            boxShadow: isSelected ? "0 2px 8px rgba(5, 150, 105, 0.2)" : "none",
          }}
        >
          {/* Day Number Only - No markers or badges */}
          <span
            className="calendar-cell-day"
            style={{
              fontSize: "13.5px",
              fontWeight: 800,
              color: isSelected ? "#059669" : "var(--text-main)",
              background: isSelected ? "var(--bg-accent)" : "transparent",
              padding: isSelected ? "2px 8px" : "0",
              borderRadius: "4px",
            }}
          >
            {dayNum}
          </span>
        </div>
      );
    }

    return cells;
  }

  const filteredNotifications = activeNotifications.filter((n) => {
    // For Teacher: filter by audience selector
    if (isTeacher) {
      if (teacherTargetAudience !== "all" && n.targetYear && n.targetYear !== "all" && n.targetYear !== teacherTargetAudience) {
        return false;
      }
    } else {
      // For Student: show notifications for active selected grade tab or their own academic year or general ("all")
      const studentYear = (currentUser as StudentProfile).academicYear;
      const activeGrade = selectedGrade || studentYear;
      if (n.targetYear && n.targetYear !== activeGrade && n.targetYear !== studentYear && n.targetYear !== "all") {
        return false;
      }

      // Scheduled Time filter: Students ONLY see the notification once the scheduled time arrives
      if (n.createdAt && n.createdAt !== "الآن") {
        const notifDate = new Date(n.createdAt);
        if (!isNaN(notifDate.getTime()) && notifDate.getTime() > Date.now()) {
          return false;
        }
      }
    }

    if (activeFilter === "all") return true;
    return n.type === activeFilter;
  });

  return (
    <div className="page-container" style={{ maxWidth: "1280px", margin: "0 auto" }}>
      {/* 2-Column Responsive Grid matching the exact reference image */}
      <div className="notifications-layout-grid" style={{ width: "100%" }}>
        {/* =========================================================================
            COLUMN 1 (RIGHT in RTL): PAGE HEADER + NOTIFICATIONS FEED CARD
           ========================================================================= */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Header Title Section aligned directly above the Notifications Card */}
          <div>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 800,
                color: "#ffffff",
                background: "#0f392b",
                padding: "4px 10px",
                borderRadius: "6px",
                border: "1px solid #059669",
                display: "inline-block",
                marginBottom: "8px",
                boxShadow: "0 1px 4px rgba(15, 57, 43, 0.2)",
              }}
            >
              {isTeacher
                ? "إدارة مواعيد الإشعارات • BROADCAST & NOTIFICATION SCHEDULE"
                : "مركز الإشعارات والجدول • NOTIFICATIONS & TIMETABLE"}
            </span>
            <h1
              style={{
                margin: "0 0 6px",
                fontSize: "23px",
                fontWeight: 800,
                color: "var(--text-main, #0f172a)",
                letterSpacing: "-0.02em",
              }}
            >
              {isTeacher ? "جدول مواعيد الإشعارات والتنبيهات المجدولة" : "الإشعارات ومواعيد الدروس والواجبات"}
            </h1>
            <p style={{ margin: 0, color: "var(--text-muted, #64748b)", fontSize: "12.5px", lineHeight: "1.5" }}>
              {isTeacher
                ? "يتم إرسال الإشعارات للطلاب بدقة وفق الجدول المحدد لكل صف دراسي وبناءً على المحتوى المرفوع حصراً."
                : "تابع تنبيهات الدروس الجديدة ومواعيد تسليم الواجبات والاختبارات الدورية وفق جدول صفك الدراسي."}
            </p>
          </div>

          {/* Notifications Feed Card */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "18px",
              padding: "20px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
            }}
          >
            {/* Teacher Audience Selector Bar */}
            {isTeacher && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "16px",
                  padding: "10px 14px",
                  background: "var(--bg-surface-secondary)",
                  borderRadius: "12px",
                  border: "1px solid var(--border-color)",
                  flexWrap: "wrap",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <label htmlFor="audience-selector" style={{ fontSize: "12.5px", fontWeight: 800, color: "var(--text-main)" }}>
                    تحديد الصف الدراسي للإشعارات:
                  </label>
                  <select
                    id="audience-selector"
                    value={teacherTargetAudience}
                    onChange={(e) => setTeacherTargetAudience(e.target.value as "all" | "1st_secondary" | "2nd_secondary" | "3rd_secondary")}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "8px",
                      border: "1.5px solid #059669",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      fontSize: "12.5px",
                      fontWeight: 700,
                      cursor: "pointer",
                      outline: "none",
                    }}
                  >
                    <option value="all">الكل (جميع الصفوف الدراسية)</option>
                    <option value="1st_secondary">الصف الأول الثانوي فقط</option>
                    <option value="2nd_secondary">الصف الثاني الثانوي فقط</option>
                    <option value="3rd_secondary">الصف الثالث الثانوي فقط</option>
                  </select>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setBroadcastTargetGrade(teacherTargetAudience);
                    setIsBroadcastModalOpen(true);
                  }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "7px 14px",
                    borderRadius: "8px",
                    background: "#059669",
                    color: "#ffffff",
                    border: "none",
                    fontSize: "12px",
                    fontWeight: 800,
                    cursor: "pointer",
                    boxShadow: "0 2px 6px rgba(5, 150, 105, 0.2)",
                  }}
                >
                  <Plus size={14} />
                  <span>إرسال إشعار فوري للطلاب</span>
                </button>
              </div>
            )}

            {/* Card Header with Feed Title and Filter Pills */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Bell size={18} style={{ color: "#059669" }} />
                <h2 style={{ margin: 0, fontSize: "15px", fontWeight: 800, color: "var(--text-main)" }}>
                  سجل الإشعارات ({filteredNotifications.length})
                </h2>
              </div>

              {/* Filter Pills */}
              <div style={{ display: "flex", gap: "6px" }}>
                {([
                  { id: "all", label: "الكل" },
                  { id: "assignment", label: "الواجبات" },
                  { id: "quiz", label: "الاختبارات" },
                  { id: "system", label: "الدروس" },
                ] as const).map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setActiveFilter(f.id)}
                    style={{
                      padding: "4px 12px",
                      borderRadius: "8px",
                      border: activeFilter === f.id ? "1.5px solid #059669" : "1px solid var(--border-color, #e2e8f0)",
                      background: activeFilter === f.id ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface, #ffffff)",
                      color: activeFilter === f.id ? "#059669" : "var(--text-muted, #64748b)",
                      fontSize: "12px",
                      fontWeight: activeFilter === f.id ? 800 : 600,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Notification Items List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {filteredNotifications.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)", fontSize: "13px" }}>
                  لا توجد إشعارات تطابق هذا الفلتر.
                </div>
              ) : (
                filteredNotifications.map((n, idx) => (
                  <div
                    key={`${n.id}-${idx}`}
                    style={{
                      border: "1px solid var(--border-color, #e2e8f0)",
                      background: "var(--bg-surface, #ffffff)",
                      borderRadius: "14px",
                      padding: "16px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                      transition: "all 0.15s ease",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
                    }}
                  >
                    {/* Item Top Row */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", flex: 1 }}>
                        {/* Icon badge */}
                        <div
                          style={{
                            width: "36px",
                            height: "36px",
                            borderRadius: "8px",
                            background: n.type === "assignment" ? "#fef3c7" : n.type === "quiz" ? "#ccfbf1" : "#dcfce7",
                            color: n.type === "assignment" ? "#b45309" : n.type === "quiz" ? "#0f766e" : "#15803d",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                            marginTop: "2px",
                          }}
                        >
                          {n.type === "assignment" ? <FileText size={18} /> : n.type === "quiz" ? <FileQuestion size={18} /> : <Video size={18} />}
                        </div>

                        <div>
                          <strong style={{ display: "block", fontSize: "13.5px", color: "var(--text-main, #0f172a)", marginBottom: "3px" }}>
                            {n.title}
                          </strong>
                          <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted, #64748b)", lineHeight: "1.5" }}>
                            {n.message}
                          </p>
                        </div>
                      </div>

                      {/* Timestamps */}
                      <div style={{ textAlign: "left", flexShrink: 0 }}>
                        <span style={{ fontSize: "11px", color: "var(--text-muted, #94a3b8)", display: "block" }}>
                          {n.createdAt}
                        </span>
                        {n.dueDate && (
                          <span style={{ fontSize: "11px", fontWeight: 800, color: "#dc2626", display: "flex", alignItems: "center", gap: "3px", justifyContent: "flex-end", marginTop: "3px" }}>
                            <Clock size={11} />
                            <span>{n.dueDate}</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Action Button */}
                    <div style={{ display: "flex", justifyContent: "flex-end" }}>
                      <button
                        onClick={() => handleActionClick(n)}
                        style={{
                          background: "#0f392b",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "8px",
                          padding: "6px 14px",
                          fontSize: "12px",
                          fontWeight: 800,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          cursor: "pointer",
                          transition: "opacity 0.15s ease",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.9")}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                      >
                        <span>
                          {n.type === "assignment"
                            ? isTeacher ? "مراجعة تسليمات الواجب" : "حل وتسليم الواجب"
                            : n.type === "quiz"
                            ? isTeacher ? "عرض وتعديل الاختبار" : "دخول الاختبار"
                            : "دخول على الدرس مباشرة"}
                        </span>
                        <ExternalLink size={12} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* =========================================================================
            COLUMN 2 (LEFT in RTL): SCHEDULE MANAGER CARD WITH FULL MONTH CALENDAR & WIZARD
           ========================================================================= */}
        <div
          style={{
            background: "var(--bg-surface, #ffffff)",
            border: "1px solid var(--border-color, #e2e8f0)",
            borderRadius: "18px",
            padding: "20px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
            width: "100%",
            maxWidth: "100%",
            boxSizing: "border-box",
          }}
        >
          {/* Card Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Calendar size={22} style={{ color: "#059669" }} />
              <h2 style={{ margin: 0, fontSize: "17.5px", fontWeight: 800, color: "var(--text-main)" }}>
                {isTeacher ? "جدول مواعيد الإرسال والتقويم الشهري" : "تقويم ومواعيد إشعارات صفك الدراسي"}
              </h2>
            </div>
            {isTeacher && (
              <button
                onClick={() => {
                  const todayStr = formatIsoDate(calendarCurrentDate);
                  const dayName = getArabicDayName(calendarCurrentDate);
                  setWizardState({
                    isOpen: true,
                    step: 1,
                    selectedDate: todayStr,
                    dayTitle: `${dayName} - موعد إرسال جديد`,
                    timeHour: "06:00",
                    timePeriod: "م",
                    contentType: "lesson",
                    isRecurringWeekly: true,
                    isPublishedToStudents: true,
                    quizDurationMinutes: 45,
                    isScheduledNotif: false,
                    scheduledNotifDate: todayStr,
                    scheduledNotifHour: "06:00",
                    scheduledNotifPeriod: "م",
                  });
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "7px 14px",
                  borderRadius: "8px",
                  border: "none",
                  background: "#0f392b",
                  color: "#ffffff",
                  fontSize: "12.5px",
                  fontWeight: 800,
                  cursor: "pointer",
                  boxShadow: "0 2px 6px rgba(15, 57, 43, 0.2)",
                }}
              >
                <Plus size={15} />
                <span>إضافة موعد جديد</span>
              </button>
            )}
          </div>

          {/* Academic Year Selection (For Teacher only - Students only view their own year) */}
          {isTeacher && (
            <div className="responsive-3col" style={{ gap: "8px", marginBottom: "16px" }}>
              {[
                { id: "1st_secondary" as const, label: "الصف الأول الثانوي" },
                { id: "2nd_secondary" as const, label: "الصف الثاني الثانوي" },
                { id: "3rd_secondary" as const, label: "الصف الثالث الثانوي" },
              ].map((g) => {
                const isSelected = selectedGrade === g.id;
                return (
                  <button
                    key={g.id}
                    onClick={() => {
                      setSelectedGrade(g.id);
                      setTeacherTargetAudience(g.id);
                      setWizardState((prev) => ({ ...prev, isOpen: false }));
                    }}
                    style={{
                      padding: "10px 8px",
                      borderRadius: "10px",
                      border: isSelected ? "2px solid #059669" : "1px solid var(--border-color)",
                      background: isSelected ? "#0f392b" : "var(--bg-surface-secondary)",
                      color: isSelected ? "#ffffff" : "var(--text-muted)",
                      fontSize: "clamp(12px, 2.5vw, 13px)",
                      fontWeight: 800,
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                      boxShadow: isSelected ? "0 2px 8px rgba(15, 57, 43, 0.25)" : "none",
                      textAlign: "center",
                      whiteSpace: "nowrap",
                    }}
                    title={g.label}
                  >
                    {g.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Success Banner */}
          {scheduleSavedMsg && (
            <div
              style={{
                padding: "10px 14px",
                background: "#dcfce7",
                color: "#166534",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 700,
                marginBottom: "14px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <CheckCircle2 size={17} />
              <span>تم حفظ وتحديث الموعد في جدول الصف الدراسي بنجاح!</span>
            </div>
          )}

          {/* =========================================================================
              FULL MONTH INTERACTIVE CALENDAR GRID (التقويم الشهري الكامل)
             ========================================================================= */}
          <div
            style={{
              background: "var(--bg-surface-secondary)",
              border: "1px solid var(--border-color)",
              borderRadius: "14px",
              padding: "16px",
              marginBottom: "16px",
            }}
          >
            {/* Month Navigation Header (Month Name between the two arrows) */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "8px" }}>
              {/* Previous / Month Name / Next Group */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button
                  onClick={() => setCalendarCurrentDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  title="الشهر السابق"
                >
                  <ChevronRight size={18} />
                </button>

                {/* Clickable Month & Year Indicator with Popover */}
                <div style={{ position: "relative" }}>
                  <button
                    type="button"
                    onClick={() => setIsMonthPickerOpen((v) => !v)}
                    style={{
                      padding: "6px 16px",
                      borderRadius: "8px",
                      border: isMonthPickerOpen ? "1.5px solid #059669" : "1.5px solid var(--border-color)",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      fontSize: "14px",
                      fontWeight: 800,
                      minWidth: "145px",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                      cursor: "pointer",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                      transition: "all 0.15s ease",
                    }}
                    title="اضغط لاختيار الشهر والسنة مباشرة"
                  >
                    <span>{getMonthYearTitle(calendarCurrentDate)}</span>
                    <ChevronDown
                      size={15}
                      style={{
                        color: "#059669",
                        transform: isMonthPickerOpen ? "rotate(180deg)" : "none",
                        transition: "transform 0.2s ease",
                      }}
                    />
                  </button>

                  {/* Backdrop for closing popover on outside click */}
                  {isMonthPickerOpen && (
                    <div
                      onClick={() => setIsMonthPickerOpen(false)}
                      style={{
                        position: "fixed",
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        zIndex: 99,
                      }}
                    />
                  )}

                  {/* Month & Year Picker Dropdown Popover */}
                  {isMonthPickerOpen && (
                    <div
                      style={{
                        position: "absolute",
                        top: "calc(100% + 8px)",
                        right: 0,
                        zIndex: 100,
                        width: "270px",
                        background: "var(--bg-surface, #ffffff)",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        borderRadius: "14px",
                        padding: "14px",
                        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
                      }}
                    >
                      {/* Year Selection Bar */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "12px",
                          paddingBottom: "8px",
                          borderBottom: "1px solid var(--border-color)",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setPickerYear((y) => y - 1)}
                          style={{
                            width: "30px",
                            height: "30px",
                            borderRadius: "6px",
                            border: "1px solid var(--border-color)",
                            background: "var(--bg-surface-secondary)",
                            color: "var(--text-main)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: "pointer",
                          }}
                          title="السنة السابقة"
                        >
                          <ChevronRight size={16} />
                        </button>

                        <select
                          value={pickerYear}
                          onChange={(e) => setPickerYear(Number(e.target.value))}
                          style={{
                            padding: "4px 10px",
                            borderRadius: "6px",
                            border: "1px solid #059669",
                            background: "#0f392b",
                            color: "#ffffff",
                            fontWeight: 800,
                            fontSize: "14px",
                            cursor: "pointer",
                          }}
                        >
                          {[2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030].map((yr) => (
                            <option key={yr} value={yr} style={{ background: "#0f392b", color: "#ffffff" }}>
                              {yr}
                            </option>
                          ))}
                        </select>

                        <button
                          type="button"
                          onClick={() => setPickerYear((y) => y + 1)}
                          style={{
                            width: "30px",
                            height: "30px",
                            borderRadius: "6px",
                            border: "1px solid var(--border-color)",
                            background: "var(--bg-surface-secondary)",
                            color: "var(--text-main)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: "pointer",
                          }}
                          title="السنة التالية"
                        >
                          <ChevronLeft size={16} />
                        </button>
                      </div>

                      {/* 12 Months Grid */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(3, 1fr)",
                          gap: "6px",
                        }}
                      >
                        {ARABIC_MONTHS.map((monthName, idx) => {
                          const isCurrent =
                            calendarCurrentDate.getFullYear() === pickerYear &&
                            calendarCurrentDate.getMonth() === idx;
                          return (
                            <button
                              key={monthName}
                              type="button"
                              onClick={() => {
                                setCalendarCurrentDate(new Date(pickerYear, idx, 1));
                                setIsMonthPickerOpen(false);
                              }}
                              style={{
                                padding: "7px 4px",
                                borderRadius: "8px",
                                border: isCurrent ? "1.5px solid #059669" : "1px solid var(--border-color)",
                                background: isCurrent ? "#0f392b" : "var(--bg-surface-secondary)",
                                color: isCurrent ? "#ffffff" : "var(--text-main)",
                                fontSize: "12px",
                                fontWeight: isCurrent ? 800 : 600,
                                cursor: "pointer",
                                transition: "all 0.15s ease",
                              }}
                            >
                              {monthName}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => setCalendarCurrentDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  title="الشهر التالي"
                >
                  <ChevronLeft size={18} />
                </button>
              </div>

              {/* Grade Badge */}
              <span
                style={{
                  fontSize: "12.5px",
                  color: "#ffffff",
                  background: "#0f392b",
                  padding: "5px 14px",
                  borderRadius: "8px",
                  fontWeight: 800,
                  border: "1px solid #059669",
                  boxShadow: "0 1px 4px rgba(15, 57, 43, 0.2)",
                }}
              >
                {getGradeLabel(selectedGrade)}
              </span>
            </div>

            {/* Weekdays Grid Header */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px", marginBottom: "8px", textAlign: "center" }}>
              {WEEK_DAYS.map((d) => (
                <div key={d} style={{ fontSize: "12.5px", fontWeight: 800, color: "var(--text-muted)", padding: "4px 0" }}>
                  {d}
                </div>
              ))}
            </div>

            {/* Month Days Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px" }}>
              {renderMonthCalendarCells()}
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          WIZARD FLOW OVERLAY WITH BLUR BACKDROP (يظهر فوق الصفحة مع Blur للمعلم فقط)
         ========================================================================= */}
      {isTeacher && wizardState.isOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.65)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            zIndex: 99999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "16px",
          }}
          onClick={() => setWizardState((prev) => ({ ...prev, isOpen: false }))}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "2px solid #059669",
              borderRadius: "18px",
              maxWidth: "520px",
              width: "100%",
              padding: "24px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
              maxHeight: "90vh",
              overflowY: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Wizard Top Bar */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", borderBottom: "1px solid var(--border-color)", paddingBottom: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "#059669", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Sparkles size={18} />
                </div>
                <div>
                  <strong style={{ fontSize: "14px", color: "var(--text-main)", display: "block" }}>
                    معالج إضافة وتعديل موعد الإرسال المجدول
                  </strong>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                    {getGradeLabel(selectedGrade)} • {wizardState.selectedDate}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setWizardState((prev) => ({ ...prev, isOpen: false }))}
                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "4px" }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Wizard Steps Indicator */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px", marginBottom: "18px" }}>
              {[
                { step: 1, title: "1. اسم اليوم والموعد" },
                { step: 2, title: "2. التوقيت والفترة" },
                { step: 3, title: "3. المراجعة والتأكيد" },
              ].map((s) => (
                <div
                  key={s.step}
                  style={{
                    padding: "7px 8px",
                    borderRadius: "8px",
                    background: wizardState.step === s.step ? "#0f392b" : (wizardState.step > s.step ? "var(--bg-accent)" : "var(--bg-surface-secondary)"),
                    color: wizardState.step === s.step ? "#ffffff" : (wizardState.step > s.step ? "#059669" : "var(--text-muted)"),
                    fontSize: "11.5px",
                    fontWeight: 800,
                    textAlign: "center",
                    border: wizardState.step === s.step ? "1.5px solid #059669" : "1px solid var(--border-color)",
                  }}
                >
                  {s.title}
                </div>
              ))}
            </div>

            {/* WIZARD STEP 1: DAY TITLE & CONTENT TYPE */}
            {wizardState.step === 1 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "4px" }}>
                    التاريخ المختار في التقويم:
                  </label>
                  <div style={{ padding: "9px 12px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", fontSize: "12.5px", fontWeight: 800, color: "#059669" }}>
                    {wizardState.selectedDate} - {getArabicDayName(new Date(wizardState.selectedDate))}
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 800, color: "var(--text-main)", marginBottom: "4px" }}>
                    اسم اليوم / عنوان الموعد:
                  </label>
                  <input
                    type="text"
                    value={wizardState.dayTitle}
                    onChange={(e) => setWizardState((prev) => ({ ...prev, dayTitle: e.target.value }))}
                    placeholder="مثال: الثلاثاء - المحاضرة الأسبوعية"
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "8px",
                      fontSize: "13px",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                      outline: "none",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 800, color: "var(--text-main)", marginBottom: "4px" }}>
                    نوع المحتوى المرتبط بالإرسال:
                  </label>
                  <select
                    value={wizardState.contentType}
                    onChange={(e) => setWizardState((prev) => ({ ...prev, contentType: e.target.value as "lesson" | "assignment" | "quiz" | "general" }))}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      border: "1px solid var(--border-color-strong)",
                      borderRadius: "8px",
                      fontSize: "13px",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      fontWeight: 700,
                      boxSizing: "border-box",
                      outline: "none",
                      cursor: "pointer",
                    }}
                  >
                    <option value="lesson">رفع وشرح درس جديد</option>
                    <option value="assignment">موعد تسليم واجب منزلي</option>
                    <option value="quiz">اختبار تقييمي دوري</option>
                    <option value="general">تنبيه عام وتذكير للمجموعة</option>
                  </select>
                  {wizardState.contentType === "quiz" && (
                    <div style={{ marginTop: "12px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <label style={{ fontSize: "11.5px", fontWeight: 700, color: "var(--text-main)" }}>
                          مدة حل الاختبار للطالب (المؤقت):
                        </label>
                        <strong style={{ fontSize: "12.5px", color: "#059669" }}>{wizardState.quizDurationMinutes || 45} دقيقة</strong>
                      </div>
                      <input
                        type="number"
                        min={5}
                        max={300}
                        step={5}
                        value={wizardState.quizDurationMinutes || 45}
                        onChange={(e) => setWizardState((prev) => ({ ...prev, quizDurationMinutes: Math.max(5, parseInt(e.target.value) || 45) }))}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          border: "1px solid var(--border-color-strong)",
                          borderRadius: "8px",
                          fontSize: "13px",
                          fontWeight: 800,
                          background: "var(--bg-surface)",
                          color: "var(--text-main)",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  )}

                  {/* Student Calendar Visibility Checkbox */}
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      marginTop: "12px",
                      padding: "10px 12px",
                      background: wizardState.isPublishedToStudents ? "var(--bg-accent, #ecfdf5)" : "var(--bg-surface-secondary)",
                      border: wizardState.isPublishedToStudents ? "1.5px solid #059669" : "1px solid var(--border-color)",
                      borderRadius: "8px",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={wizardState.isPublishedToStudents}
                      onChange={(e) => setWizardState((prev) => ({ ...prev, isPublishedToStudents: e.target.checked }))}
                      style={{ width: "16px", height: "16px", accentColor: "#059669", cursor: "pointer" }}
                    />
                    <div>
                      <strong style={{ fontSize: "12px", color: "var(--text-main)", display: "block" }}>
                        إظهار هذا الموعد للطلاب في تقويم صفهم الدراسي
                      </strong>
                      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                        {wizardState.isPublishedToStudents ? "معروض في جدول وتقويم الطلاب" : "مخفي عن الطلاب ويظهر في جدولك كمعلم فقط"}
                      </span>
                    </div>
                  </label>

                  {/* Scheduled Notification Checkbox */}
                  {wizardState.isPublishedToStudents && (
                    <div style={{ marginTop: "6px" }}>
                      <label
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          padding: "10px 12px",
                          background: wizardState.isScheduledNotif ? "#fef3c7" : "var(--bg-surface-secondary)",
                          border: wizardState.isScheduledNotif ? "1.5px solid #f59e0b" : "1px solid var(--border-color)",
                          borderRadius: "8px",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={wizardState.isScheduledNotif}
                          onChange={(e) => setWizardState((prev) => ({
                            ...prev,
                            isScheduledNotif: e.target.checked,
                            scheduledNotifDate: e.target.checked ? prev.selectedDate : "",
                          }))}
                          style={{ width: "16px", height: "16px", accentColor: "#f59e0b", cursor: "pointer" }}
                        />
                        <div>
                          <strong style={{ fontSize: "12px", color: "var(--text-main)", display: "block" }}>
                            جدولة ظهور الإشعار للطلاب في وقت محدد
                          </strong>
                          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                            {wizardState.isScheduledNotif ? "الطلاب سيرون الإشعار في التاريخ والوقت المحدد أدناه" : "الإشعار يظهر للطلاب فوراً عند الحفظ"}
                          </span>
                        </div>
                      </label>

                      {wizardState.isScheduledNotif && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", marginTop: "8px", padding: "10px 12px", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: "8px" }}>
                          <div>
                            <small style={{ display: "block", color: "var(--text-muted)", fontSize: "10.5px", marginBottom: "3px", fontWeight: 700 }}>تاريخ ظهور الإشعار:</small>
                            <input
                              type="date"
                              value={wizardState.scheduledNotifDate}
                              onChange={(e) => setWizardState((prev) => ({ ...prev, scheduledNotifDate: e.target.value }))}
                              style={{
                                width: "100%",
                                padding: "7px 8px",
                                border: "1px solid var(--border-color-strong)",
                                borderRadius: "7px",
                                fontSize: "12px",
                                fontWeight: 700,
                                background: "var(--bg-surface)",
                                color: "var(--text-main)",
                                boxSizing: "border-box",
                              }}
                            />
                          </div>
                          <div>
                            <small style={{ display: "block", color: "var(--text-muted)", fontSize: "10.5px", marginBottom: "3px", fontWeight: 700 }}>الفترة:</small>
                            <select
                              value={wizardState.scheduledNotifPeriod}
                              onChange={(e) => setWizardState((prev) => ({ ...prev, scheduledNotifPeriod: e.target.value as "ص" | "م" }))}
                              style={{
                                width: "100%",
                                padding: "7px 8px",
                                border: "1px solid var(--border-color-strong)",
                                borderRadius: "7px",
                                fontSize: "12px",
                                fontWeight: 700,
                                background: "var(--bg-surface)",
                                color: "var(--text-main)",
                                boxSizing: "border-box",
                                cursor: "pointer",
                              }}
                            >
                              <option value="ص">صباحاً (ص)</option>
                              <option value="م">مساءً (م)</option>
                            </select>
                          </div>
                          <div>
                            <small style={{ display: "block", color: "var(--text-muted)", fontSize: "10.5px", marginBottom: "3px", fontWeight: 700 }}>الساعة:</small>
                            <select
                              value={wizardState.scheduledNotifHour}
                              onChange={(e) => setWizardState((prev) => ({ ...prev, scheduledNotifHour: e.target.value }))}
                              style={{
                                width: "100%",
                                padding: "7px 8px",
                                border: "1px solid var(--border-color-strong)",
                                borderRadius: "7px",
                                fontSize: "12px",
                                fontWeight: 700,
                                background: "var(--bg-surface)",
                                color: "var(--text-main)",
                                boxSizing: "border-box",
                                cursor: "pointer",
                              }}
                            >
                              {["12:00","01:00","02:00","03:00","04:00","05:00","06:00","07:00","08:00","09:00","10:00","11:00"].map((t) => (
                                <option key={t} value={t}>{t}</option>
                              ))}
                            </select>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px", flexWrap: "wrap", gap: "8px" }}>
                  {(() => {
                    const normWizDate = (wizardState.selectedDate || "").split("T")[0];
                    const existingEvt = calendarEvents.find((e) => (e.academicYear === selectedGrade || e.academicYear === "all") && (e.date || "").split("T")[0] === normWizDate);
                    if (existingEvt && !existingEvt.isCancelled) {
                      return (
                        <button
                          type="button"
                          onClick={() => handleCancelSchedule(wizardState.selectedDate)}
                          style={{
                            padding: "8px 14px",
                            borderRadius: "8px",
                            border: "1px solid #fca5a5",
                            background: "#fee2e2",
                            color: "#b91c1c",
                            fontSize: "12px",
                            fontWeight: 800,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <XCircle size={15} />
                          <span>إلغاء هذا الموعد وإشعار الطلاب</span>
                        </button>
                      );
                    }
                    return <div />;
                  })()}

                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <button
                      type="button"
                      onClick={() => setWizardState((prev) => ({ ...prev, step: 2 }))}
                      disabled={!wizardState.dayTitle.trim()}
                      style={{
                        padding: "9px 16px",
                        borderRadius: "8px",
                        border: "1px solid var(--border-color)",
                        background: "#0f392b",
                        color: "#ffffff",
                        fontSize: "12.5px",
                        fontWeight: 800,
                        cursor: "pointer",
                        opacity: !wizardState.dayTitle.trim() ? 0.6 : 1,
                      }}
                    >
                      التالي: تحديد التوقيت
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* WIZARD STEP 2: TIME SELECTORS & RECURRENCE */}
            {wizardState.step === 2 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 800, color: "var(--text-main)", marginBottom: "6px" }}>
                    وقت وتوقيت الإرسال:
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    {/* Period Selector (ص / م) */}
                    <div>
                      <small style={{ display: "block", color: "var(--text-muted)", fontSize: "11px", marginBottom: "3px" }}>الفترة:</small>
                      <select
                        value={wizardState.timePeriod}
                        onChange={(e) => setWizardState((prev) => ({ ...prev, timePeriod: e.target.value as "ص" | "م" }))}
                        style={{
                          width: "100%",
                          padding: "9px 12px",
                          border: "1.5px solid var(--border-color-strong)",
                          borderRadius: "8px",
                          fontSize: "13px",
                          fontWeight: 800,
                          background: "var(--bg-surface)",
                          color: "var(--text-main)",
                          outline: "none",
                          cursor: "pointer",
                        }}
                      >
                        <option value="م">م (مساءً)</option>
                        <option value="ص">ص (صباحاً)</option>
                      </select>
                    </div>

                    {/* Hour Selector */}
                    <div>
                      <small style={{ display: "block", color: "var(--text-muted)", fontSize: "11px", marginBottom: "3px" }}>الساعة:</small>
                      <select
                        value={wizardState.timeHour}
                        onChange={(e) => setWizardState((prev) => ({ ...prev, timeHour: e.target.value }))}
                        style={{
                          width: "100%",
                          padding: "9px 12px",
                          border: "1.5px solid var(--border-color-strong)",
                          borderRadius: "8px",
                          fontSize: "13px",
                          fontWeight: 800,
                          background: "var(--bg-surface)",
                          color: "var(--text-main)",
                          outline: "none",
                          direction: "ltr",
                          textAlign: "center",
                          cursor: "pointer",
                        }}
                      >
                        {TIME_OPTIONS.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Weekly Recurrence Toggle */}
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    background: "var(--bg-surface-secondary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "8px",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={wizardState.isRecurringWeekly}
                    onChange={(e) => setWizardState((prev) => ({ ...prev, isRecurringWeekly: e.target.checked }))}
                    style={{ width: "16px", height: "16px", accentColor: "#059669", cursor: "pointer" }}
                  />
                  <div>
                    <strong style={{ fontSize: "12px", color: "var(--text-main)", display: "block" }}>
                      تكرار أسبوعي (كل {getArabicDayName(new Date(wizardState.selectedDate))})
                    </strong>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      تثبيت هذا الموعد بشكل دائم لطلاب {getGradeLabel(selectedGrade)}
                    </span>
                  </div>
                </label>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: "6px" }}>
                  <button
                    onClick={() => setWizardState((prev) => ({ ...prev, step: 1 }))}
                    style={{ padding: "9px 16px", borderRadius: "8px", border: "1px solid var(--border-color)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: "12px", fontWeight: 700, cursor: "pointer" }}
                  >
                    السابق
                  </button>
                  <button
                    onClick={() => setWizardState((prev) => ({ ...prev, step: 3 }))}
                    style={{ padding: "9px 18px", borderRadius: "8px", border: "none", background: "#0f392b", color: "#ffffff", fontSize: "12px", fontWeight: 800, cursor: "pointer" }}
                  >
                    التالي: مراجعة وحفظ
                  </button>
                </div>
              </div>
            )}

            {/* WIZARD STEP 3: REVIEW & CONFIRMATION */}
            {wizardState.step === 3 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>الصف الدراسي:</span>
                    <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>{getGradeLabel(selectedGrade)}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>التاريخ واليوم:</span>
                    <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>{wizardState.selectedDate} ({getArabicDayName(new Date(wizardState.selectedDate))})</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>اسم الموعد:</span>
                    <strong style={{ fontSize: "12px", color: "#059669" }}>{wizardState.dayTitle}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>وقت الإرسال:</span>
                    <strong style={{ fontSize: "13px", color: "#b45309" }}>{wizardState.timeHour} {wizardState.timePeriod}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>نوع المحتوى والتكرار:</span>
                    <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>
                      {getContentTypeLabel(wizardState.contentType)} {wizardState.isRecurringWeekly ? "(تكرار أسبوعي)" : "(مرة واحدة)"}
                    </strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>الظهور في تقويم الطلاب:</span>
                    <strong style={{ fontSize: "12px", color: wizardState.isPublishedToStudents ? "#059669" : "#b45309" }}>
                      {wizardState.isPublishedToStudents ? "معروض في جدول الطلاب" : "مخفي عن الطلاب (خاص بالمعلم)"}
                    </strong>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px", flexWrap: "wrap", gap: "8px" }}>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <button
                      onClick={() => setWizardState((prev) => ({ ...prev, step: 2 }))}
                      style={{ padding: "9px 16px", borderRadius: "8px", border: "1px solid var(--border-color)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: "12px", fontWeight: 700, cursor: "pointer" }}
                    >
                      السابق
                    </button>
                    {calendarEvents.some((e) => e.academicYear === selectedGrade && e.date === wizardState.selectedDate && !e.isCancelled) && (
                      <button
                        type="button"
                        onClick={() => handleCancelSchedule(wizardState.selectedDate)}
                        style={{
                          padding: "9px 14px",
                          borderRadius: "8px",
                          border: "1px solid #fca5a5",
                          background: "#fee2e2",
                          color: "#b91c1c",
                          fontSize: "12px",
                          fontWeight: 800,
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <XCircle size={15} />
                        <span>إلغاء الموعد وإشعار الطلاب</span>
                      </button>
                    )}
                  </div>

                  <button
                    onClick={handleSaveWizardSchedule}
                    style={{
                      padding: "10px 22px",
                      borderRadius: "8px",
                      border: "none",
                      background: "#059669",
                      color: "#ffffff",
                      fontSize: "13px",
                      fontWeight: 800,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      boxShadow: "0 2px 8px rgba(5, 150, 105, 0.3)",
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>تأكيد وحفظ الموعد في الجدول</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Broadcast Modal for Teacher */}
      {isBroadcastModalOpen && (
        <div className="modal-overlay" style={{ zIndex: 1000 }}>
          <div
            className="modal-content"
            style={{
              maxWidth: "540px",
              padding: "24px",
              background: "var(--bg-surface)",
              borderRadius: "16px",
              border: "1px solid var(--border-color)",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px", borderBottom: "1px solid var(--border-color)", paddingBottom: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Bell size={20} style={{ color: "#059669" }} />
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                  إرسال إشعار فوري وتنبيه للطلاب
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsBroadcastModalOpen(false)}
                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSendBroadcast} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                  الصف الدراسي المستهدف:
                </label>
                <select
                  value={broadcastTargetGrade}
                  onChange={(e) => setBroadcastTargetGrade(e.target.value as "all" | "1st_secondary" | "2nd_secondary" | "3rd_secondary")}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color-strong, #cbd5e1)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                    fontWeight: 700,
                  }}
                >
                  <option value="all">الكل (جميع الطلاب في كافة الصفوف)</option>
                  <option value="1st_secondary">الصف الأول الثانوي</option>
                  <option value="2nd_secondary">الصف الثاني الثانوي</option>
                  <option value="3rd_secondary">الصف الثالث الثانوي</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                  نوع الإشعار:
                </label>
                <select
                  value={broadcastType}
                  onChange={(e) => setBroadcastType(e.target.value as "system" | "assignment" | "quiz" | "warning")}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color-strong, #cbd5e1)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                  }}
                >
                  <option value="system">تنبيه درس جديد / شرح</option>
                  <option value="assignment">تنبيه واجب منزلي</option>
                  <option value="quiz">تنبيه اختبار تقييمي</option>
                  <option value="warning">تنبيه عام / هام</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                  عنوان الإشعار:
                </label>
                <input
                  type="text"
                  required
                  value={broadcastTitle}
                  onChange={(e) => setBroadcastTitle(e.target.value)}
                  placeholder="مثال: تنبيه هام حول موعد حل الاختبار القادم"
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color-strong, #cbd5e1)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                  نص وتفاصيل الإشعار:
                </label>
                <textarea
                  required
                  rows={3}
                  value={broadcastMessage}
                  onChange={(e) => setBroadcastMessage(e.target.value)}
                  placeholder="اكتب التوجيهات أو التعليمات التي تريد وصولها للطلاب فوراً..."
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color-strong, #cbd5e1)",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                    تاريخ التسليم/الموعد (اختياري):
                  </label>
                  <input
                    type="text"
                    value={broadcastDueDate}
                    onChange={(e) => setBroadcastDueDate(e.target.value)}
                    placeholder="مثال: الجمعة القادمة 09:00 م"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-color-strong, #cbd5e1)",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      fontSize: "12px",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                    زر الانتقال المباشر:
                  </label>
                  <select
                    value={broadcastActionTab}
                    onChange={(e) => setBroadcastActionTab(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-color-strong, #cbd5e1)",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      fontSize: "12px",
                    }}
                  >
                    <option value="GeneralHome">الصفحة الرئيسية / المقررات</option>
                    <option value="MyCourses">مقرراتي / الدروس</option>
                    <option value="MySubmissions">واجباتي وتسليماتي</option>
                    <option value="Notifications">مركز الإشعارات</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setIsBroadcastModalOpen(false)}
                  style={{
                    padding: "9px 16px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-surface)",
                    color: "var(--text-muted)",
                    fontSize: "12.5px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  style={{
                    padding: "9px 20px",
                    borderRadius: "8px",
                    border: "none",
                    background: "#059669",
                    color: "#ffffff",
                    fontSize: "12.5px",
                    fontWeight: 800,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    boxShadow: "0 2px 6px rgba(5, 150, 105, 0.25)",
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>إرسال الإشعار الآن</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

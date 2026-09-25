import React, { useState, useRef, useEffect } from "react";
import {
  Film,
  Download,
  FileSpreadsheet,
  FileText,
  Paperclip,
  Play,
  Plus,
  Printer,
  Trash2,
  Upload,
  Video,
  X,
  Search,
  Globe,
} from "lucide-react";
import { Course, CurrentUser, VideoLesson } from "../types/lms";
import { VideoLessonPage } from "../components/VideoLessonPage";
import { exportToDocx, exportToExcel, exportToPrintPdf } from "../utils/exportEngine";
import { courseService } from "../services/lmsService";
import { uploadManager } from "../services/uploadManager";
import { fetchApiBlob } from "../services/apiClient";
import { useConfirm } from "../components/ConfirmWizard";
import { useTranslation } from "../utils/i18nContext";

/** Tracks the app-wide light/dark theme by watching the `data-theme`
 * attribute on <html>, so inline styles can pick theme-aware colors. */
function useDataTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
  );
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}

/** Lightweight in-app toast — replaces window.alert for transient notices. */
function useWizardToast() {
  const [toast, setToast] = useState<string | null>(null);
  const timer = React.useRef<number | null>(null);
  function notify(message: string) {
    setToast(message);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), 3200);
  }
  return { toast, notify };
}

interface SelectedMaterialFile {
  id: string;
  name: string;
  sizeFormatted: string;
  fileType: "pdf" | "video" | "doc";
  file?: File;
}

interface LessonManagementViewProps {
  currentUser: CurrentUser;
  courses: Course[];
  onCoursesChanged: (courses: Course[]) => void;
}


export const LessonManagementView: React.FC<LessonManagementViewProps> = ({
  currentUser,
  courses: availableCourses,
  onCoursesChanged,
}) => {
  const { lang } = useTranslation();
  const isDark = useDataTheme() === "dark";
  void lang;
  void isDark;

  const [courses, setCourses] = useState<Course[]>(availableCourses);
  React.useEffect(() => setCourses(availableCourses), [availableCourses]);
  const confirm = useConfirm();
  const { toast, notify } = useWizardToast();
  const [selectedYear, setSelectedYear] = useState<"1st_secondary" | "2nd_secondary" | "3rd_secondary">("1st_secondary");
  const selectedGradeLevel = selectedYear === "1st_secondary"
    ? "SECONDARY_1"
    : selectedYear === "2nd_secondary"
    ? "SECONDARY_2"
    : "SECONDARY_3";
  const [isDeleteMode, setIsDeleteMode] = useState(false);
  const [activeLessonModal, setActiveLessonModal] = useState<VideoLesson | null>(null);



  // Minimum Views Threshold Configured by Teacher (Requirement: AI predicts after X students watch)

  // New Lesson Form State
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonDescription, setLessonDescription] = useState("");
  const [lessonDuration, setLessonDuration] = useState(45);
  const [lessonPrice, setLessonPrice] = useState<number>(50);
  const [videoSourceType, setVideoSourceType] = useState<"file" | "url">("file");
  const [videoExternalUrl, setVideoExternalUrl] = useState("");
  const [selectedVideo, setSelectedVideo] = useState<{ name: string; size: string } | null>(null);
  const [selectedVideoFile, setSelectedVideoFile] = useState<File | null>(null);
  const [attachedFiles, setAttachedFiles] = useState<SelectedMaterialFile[]>([]);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [courseModules, setCourseModules] = useState<Array<{ id: string; title: string }>>([]);
  const [selectedModuleId, setSelectedModuleId] = useState<string>("auto");
  const [newModuleTitle, setNewModuleTitle] = useState("");
  const [isRevision, setIsRevision] = useState(false);

  // Auto-sync courses when background uploads finish
  useEffect(() => {
    async function handleAutoSyncCourses() {
      try {
        const refreshed = await courseService.getCourses();
        setCourses(refreshed);
        onCoursesChanged(refreshed);
      } catch (err) {
        console.error("Auto-sync courses failed", err);
      }
    }
    window.addEventListener("lms_courses_updated", handleAutoSyncCourses);
    return () => window.removeEventListener("lms_courses_updated", handleAutoSyncCourses);
  }, [onCoursesChanged]);

  const individualVideoInputRef = useRef<HTMLInputElement>(null);
  const targetLessonIdForVideoRef = useRef<string | null>(null);

  function triggerAttachVideoToLesson(lessonId: string) {
    targetLessonIdForVideoRef.current = lessonId;
    individualVideoInputRef.current?.click();
  }
  void triggerAttachVideoToLesson;

  async function handleIndividualVideoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    const lessonId = targetLessonIdForVideoRef.current;
    if (file && lessonId) {
      const lesson = activeLessons.find((l) => l.id === lessonId);
      const lessonTitle = lesson?.title || "الدرس";
      uploadManager.enqueueVideoUpload({
        lessonId,
        lessonTitle,
        file,
        courseId: activeCourse?.id,
      });
      notify(`جاري رفع وتحديث فيديو "${lessonTitle}" في الخلفية إلى السحابة... يمكنك الاستمرار بالعمل بحرية.`);
      e.target.value = "";
    }
  }

  const individualMaterialInputRef = useRef<HTMLInputElement>(null);
  const targetLessonIdForMaterialRef = useRef<string | null>(null);

  function triggerAttachMaterialToLesson(lessonId: string) {
    targetLessonIdForMaterialRef.current = lessonId;
    individualMaterialInputRef.current?.click();
  }

  async function handleIndividualMaterialChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    const lessonId = targetLessonIdForMaterialRef.current;
    if (files && files.length > 0 && lessonId && activeCourse) {
      const lesson = activeLessons.find((l) => l.id === lessonId);
      const lessonTitle = lesson?.title || "الدرس";
      uploadManager.enqueueKnowledgeBatchUpload({
        files: Array.from(files),
        courseId: activeCourse.id,
        gradeLevel: selectedGradeLevel,
        lessonId,
        lessonTitle,
        onSuccess: () => {
          courseService.getCourses().then((refreshed) => {
            setCourses(refreshed);
            onCoursesChanged(refreshed);
          });
        },
      });
      notify(`جاري رفع ${files.length} ملفات مذكرة للدرس "${lessonTitle}" في الخلفية إلى السحابة...`);
      e.target.value = "";
    }
  }

  // File Input Refs for Guaranteed Click Triggering
  const videoInputRef = useRef<HTMLInputElement>(null);
  const materialsInputRef = useRef<HTMLInputElement>(null);

  const activeCourse = courses.find((c) => c.academicYear === selectedYear);
  // Reverse order so the latest uploaded video/lesson is always displayed at the top
  const activeLessons: VideoLesson[] = React.useMemo(() => {
    if (!activeCourse?.lessons) return [];
    return [...activeCourse.lessons].reverse();
  }, [activeCourse]);

  // Load modules (units) for the active course
  useEffect(() => {
    if (!activeCourse?.id) {
      setCourseModules([]);
      return;
    }
    courseService
      .getCourseContent(activeCourse.id)
      .then((content) => {
        const mods = (content.modules || []).map((m) => ({ id: m.id, title: m.title }));
        setCourseModules(mods);
        if (mods.length > 0 && (selectedModuleId === "auto" || !selectedModuleId)) {
          setSelectedModuleId(mods[0].id);
        }
      })
      .catch(() => undefined);
  }, [activeCourse?.id, courses]);

  // Video & Lesson Search State
  const [videoSearchQuery, setVideoSearchQuery] = useState("");

  const filteredLessons: VideoLesson[] = React.useMemo(() => {
    let result = activeLessons;
    if (videoSearchQuery.trim()) {
      const q = videoSearchQuery.trim().toLowerCase();
      result = result.filter((l) => {
        const title = (l.title || "").toLowerCase();
        const desc = (l.description || "").toLowerCase();
        return title.includes(q) || desc.includes(q);
      });
    }
    return result;
  }, [activeLessons, videoSearchQuery]);

  const activeYearLabel =
    selectedYear === "1st_secondary"
      ? "الصف الأول الثانوي"
      : selectedYear === "2nd_secondary"
      ? "الصف الثاني الثانوي"
      : "الصف الثالث الثانوي";

  // Handle Video File Selection
  function handleVideoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedVideoFile(file);
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
    if (!lessonTitle.trim()) {
      setLessonTitle(cleanName);
    }
    setSelectedVideo({
      name: file.name,
      size: `${sizeMB} MB`,
    });
    setVideoPreviewUrl(URL.createObjectURL(file));

    const tempVid = document.createElement("video");
    tempVid.src = URL.createObjectURL(file);
    tempVid.onloadedmetadata = () => {
      const dur = Math.round(tempVid.duration / 60) || 45;
      setLessonDuration(dur);
    };
  }

  // Handle Lesson Materials / PDF Selection
  function handleMaterialsChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files && files.length > 0) {
      const newMaterials: SelectedMaterialFile[] = Array.from(files).map((f) => {
        const sizeMB = (f.size / (1024 * 1024)).toFixed(1);
        const ext = f.name.split(".").pop()?.toLowerCase();
        return {
          id: `mat_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
          name: f.name,
          sizeFormatted: `${sizeMB} MB`,
          fileType: ext === "pdf" ? "pdf" : "doc",
          file: f,
        };
      });
      setAttachedFiles((prev) => [...prev, ...newMaterials]);
    }
  }

  function removeAttachedFile(id: string) {
    setAttachedFiles((prev) => prev.filter((f) => f.id !== id));
  }

  async function downloadLessonMaterial(url: string, filename: string) {
    try {
      const blob = await fetchApiBlob(url);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      notify(`تم تنزيل المذكرة: ${filename}`);
    } catch {
      notify("تعذر تنزيل المذكرة. تحقق من الاتصال والصلاحيات ثم أعد المحاولة.");
    }
  }

  async function handleDeleteLesson(lessonId: string, lessonTitle: string) {
    const confirmed = await confirm({
      title: "حذف الدرس",
      message: `هل أنت متأكد من رغبتك في حذف درس "${lessonTitle}" نهائياً من هذا الصف الدراسي؟`,
      confirmLabel: "حذف",
      tone: "danger",
    });
    if (confirmed) {
      const lesson = activeCourse?.lessons.find((item) => item.id === lessonId);
      if (!activeCourse || !lesson?.moduleId) {
        await confirm({
          title: "خطأ",
          message: "تعذر تحديد وحدة الدرس على الخادم.",
          cancelLabel: "إغلاق",
          tone: "warning",
        });
        return;
      }
      try {
        await courseService.deleteLesson(lesson.moduleId, lessonId);
        const updated = await courseService.getCourses();
        setCourses(updated);
        onCoursesChanged(updated);
      } catch (error) {
        await confirm({
          title: "تعذر حذف الدرس",
          message: error instanceof Error ? error.message : "حدث خطأ غير متوقع أثناء الحذف.",
          cancelLabel: "إغلاق",
          tone: "danger",
        });
      }
    }
  }

  // Handle Form Submission: Create and Upload Lesson
  async function handleUploadLesson(e: React.FormEvent) {
    e.preventDefault();
    if (!lessonTitle.trim()) {
      notify("يرجى كتابة عنوان الدرس أولاً.");
      return;
    }

    const hasVideo = videoSourceType === "url" ? Boolean(videoExternalUrl.trim()) : Boolean(selectedVideo);
    if (!hasVideo && attachedFiles.length === 0) {
      notify("يجب اختيار ملف فيديو أو إدخال رابط فيديو سحابي أو مذكرة للدرس لإتمام عملية الرفع.");
      return;
    }

    // Show Confirmation Dialog on button click for file uploads
    if (videoSourceType === "file" && selectedVideoFile) {
      const sizeMB = (selectedVideoFile.size / (1024 * 1024)).toFixed(1);
      const confirmed = await confirm({
        title: "تأكيد رفع فيديو الدرس",
        message: `هل تريد بدء رفع الفيديو "${selectedVideoFile.name}" (${sizeMB} MB) بعنوان "${lessonTitle.trim()}"؟ سيتم الرفع في الخلفية فوراً ويمكنك مغادرة الصفحة أو العمل بحرية.`,
        confirmLabel: "نعم، ارفع في الخلفية",
        cancelLabel: "إلغاء",
        tone: "info",
      });
      if (!confirmed) {
        return;
      }
    }

    const yearLabel =
      selectedYear === "1st_secondary"
        ? "الصف الأول الثانوي"
        : selectedYear === "2nd_secondary"
        ? "الصف الثاني الثانوي"
        : "الصف الثالث الثانوي";

    setIsUploading(true);
    try {
      let course = activeCourse;
      if (!course) {
        const teacherSubject = currentUser.role === "student" ? "" : currentUser.subject;
        await courseService.createCourse({
          code: `${selectedYear}-${Date.now()}`.slice(0, 40),
          title: `مقرر ${teacherSubject || "المادة الدراسية"}: ${yearLabel}`,
          description: `المقرر الدراسي لمادة ${teacherSubject || "المادة"} لطلاب ${yearLabel}.`,
        });
        const refreshed = await courseService.getCourses();
        setCourses(refreshed);
        onCoursesChanged(refreshed);
        course = refreshed[refreshed.length - 1];
      }
      if (!course) throw new Error("تعذر إنشاء المقرر");
      const content = await courseService.getCourseContent(course.id);
      let module = content.modules[0];
      if (selectedModuleId === "new" && newModuleTitle.trim()) {
        module = await courseService.addModule(course.id, {
          title: newModuleTitle.trim(),
          position: (content.modules?.length || 0) + 1,
        });
      } else if (selectedModuleId && selectedModuleId !== "auto") {
        const found = content.modules.find((m) => m.id === selectedModuleId);
        if (found) module = found;
      }
      if (!module) {
        module = await courseService.addModule(course.id, { title: "الوحدة الأولى", position: 1 });
      }

      const savedTitle = lessonTitle.trim();
      const externalUrl = videoSourceType === "url" && videoExternalUrl.trim() ? videoExternalUrl.trim() : undefined;
      const lessonContentWithMeta = isRevision
        ? `${lessonDescription.trim()}\n<!--is_revision:true-->`
        : lessonDescription.trim();

      const addedLesson = await courseService.addLesson(module.id, {
        title: savedTitle,
        kind: "video",
        position: module.lessons.length + 1,
        content: lessonContentWithMeta || (isRevision ? "<!--is_revision:true-->" : undefined),
        external_video_url: externalUrl,
        video_duration_seconds: lessonDuration * 60,
      });

      if (videoSourceType === "file" && selectedVideoFile) {
        uploadManager.enqueueVideoUpload({
          lessonId: addedLesson.id,
          lessonTitle: savedTitle,
          file: selectedVideoFile,
          courseId: course.id,
        });
      }

      const noteFiles = attachedFiles.map((f) => f.file).filter((f): f is File => Boolean(f));
      if (noteFiles.length > 0) {
        uploadManager.enqueueKnowledgeBatchUpload({
          files: noteFiles,
          courseId: course.id,
          lessonId: addedLesson.id,
          gradeLevel: selectedGradeLevel,
          lessonTitle: savedTitle,
          onSuccess: () => {
            courseService.getCourses().then((refreshed) => {
              setCourses(refreshed);
              onCoursesChanged(refreshed);
            });
          },
        });
      }

      if (videoSourceType === "file" && selectedVideoFile && noteFiles.length > 0) {
        notify(`تم إنشاء درس "${savedTitle}" بنجاح! جاري رفع الفيديو والمذكرات الآن في الخلفية إلى السحابة... يمكنك التنقل ومتابعة عملك بحرية.`);
      } else if (videoSourceType === "file" && selectedVideoFile) {
        notify(`تم إنشاء درس "${savedTitle}" بنجاح! جاري رفع الفيديو الآن في الخلفية إلى السحابة... يمكنك التنقل ومتابعة عملك بحرية.`);
      } else if (noteFiles.length > 0) {
        notify(`تم إنشاء درس "${savedTitle}" بنجاح! جاري رفع المذكرات الآن في الخلفية إلى السحابة... يمكنك التنقل ومتابعة عملك بحرية.`);
      } else {
        notify(`تم حفظ درس "${savedTitle}" بنجاح!`);
      }

      const refreshed = await courseService.getCourses();
      setCourses(refreshed);
      onCoursesChanged(refreshed);
    } catch (error) {
      notify(error instanceof Error ? error.message : "تعذر حفظ الدرس على الخادم");
      setIsUploading(false);
      return;
    }

    setIsUploading(false);
    setLessonTitle("");
    setLessonDescription("");
    setSelectedVideo(null);
    setSelectedVideoFile(null);
    setVideoPreviewUrl(null);
    setVideoExternalUrl("");
    setAttachedFiles([]);
    setLessonPrice(0);
    setIsRevision(false);
    setNewModuleTitle("");
    setUploadSuccess(true);
    setTimeout(() => setUploadSuccess(false), 5000);
  }

  // Universal Export Handlers
  function getExportPayload() {
    const headers = [
      "عنوان الدرس",
      "المدة",
      "عدد الملفات المرفقة",
      "حالة تجهيز التفريغ",
    ];

    const rows = activeLessons.map((l) => [
      l.title,
      l.durationFormatted || "—",
      String((l.materials || []).length),
      l.materialization_status === "INDEXED" ? "جاهز" : "غير معالج",
    ]);

    return {
      title: `تقرير الدروس والمذكرات - ${activeYearLabel}`,
      subtitle: `عدد الدروس: ${activeLessons.length}`,
      headers,
      rows,
      summaryStats: [
        { label: "المادة الدراسية", value: activeCourse?.title || "المقرر الدراسي" },
        { label: "إجمالي الدروس", value: activeLessons.length },
      ],
    };
  }

  if (activeLessonModal && activeCourse) {
    return (
      <VideoLessonPage
        lesson={activeLessonModal}
        course={activeCourse}
        currentUser={currentUser}
        completedLessonIds={[]}
        onToggleCompleteLesson={() => {}}
        onSelectLesson={(ls) => setActiveLessonModal(ls)}
        onClose={() => setActiveLessonModal(null)}
        onDownloadMaterial={downloadLessonMaterial}
      />
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: "1280px", margin: "0 auto" }}>
      {/* Hidden File Input for Per-Lesson Video Upload */}
      <input
        type="file"
        ref={individualVideoInputRef}
        accept="video/*"
        onChange={handleIndividualVideoChange}
        style={{ display: "none" }}
      />
      <input
        type="file"
        ref={individualMaterialInputRef}
        multiple
        accept=".pdf,.doc,.docx,.ppt,.pptx"
        onChange={handleIndividualMaterialChange}
        style={{ display: "none" }}
      />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", color: "var(--text-main, #0f172a)" }}>
            إدارة الدروس
          </h1>
        </div>

        {/* Universal Export */}
        <div style={{ position: "relative" }}>
          <button
            className="btn-primary"
            onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
            style={{ fontSize: "12px", gap: "6px" }}
          >
            <Download size={15} /> تصدير التقرير
          </button>

          {exportDropdownOpen && (
            <div
              style={{
                position: "absolute",
                left: 0,
                top: "42px",
                background: "var(--bg-surface, #ffffff)",
                border: "1px solid var(--border-color, #e2e8f0)",
                borderRadius: "10px",
                boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
                zIndex: 50,
                width: "220px",
                overflow: "hidden",
              }}
            >
              <button
                onClick={() => {
                  exportToDocx(getExportPayload(), `difficulty_report_${selectedYear}.docx`);
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-main)" }}
              >
                <FileText size={16} style={{ color: "#2563eb" }} />
                <strong>تصدير Word (.docx من اليمين للشمال)</strong>
              </button>

              <button
                onClick={() => {
                  exportToExcel(getExportPayload(), `difficulty_report_${selectedYear}.xlsx`);
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-main)" }}
              >
                <FileSpreadsheet size={16} style={{ color: "#059669" }} />
                <strong>تصدير Excel (.xlsx من اليمين للشمال)</strong>
              </button>

              <button
                onClick={() => {
                  exportToPrintPdf(getExportPayload());
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-main)" }}
              >
                <Printer size={16} style={{ color: "#0f392b" }} />
                <strong>تصدير / طباعة PDF (من اليمين للشمال)</strong>
              </button>
            </div>
          )}
        </div>
      </div>


      {/* Grade Selector Tabs + AI Threshold Setting Banner */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "14px" }}>
        <div style={{ display: "flex", gap: "10px" }}>
          {[
            { id: "1st_secondary", label: "الصف الأول الثانوي" },
            { id: "2nd_secondary", label: "الصف الثاني الثانوي" },
            { id: "3rd_secondary", label: "الصف الثالث الثانوي" },
          ].map((y) => (
            <button
              key={y.id}
              onClick={() => setSelectedYear(y.id as "1st_secondary" | "2nd_secondary" | "3rd_secondary")}
              style={{
                padding: "8px 18px",
                borderRadius: "8px",
                border: selectedYear === y.id ? "1.5px solid #0f392b" : "1px solid var(--border-color, #cbd5e1)",
                background: selectedYear === y.id ? "#0f392b" : "var(--bg-surface, #ffffff)",
                color: selectedYear === y.id ? "#ffffff" : "var(--text-main)",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {y.label}
            </button>
          ))}
        </div>

      </div>

      {/* Main 2-Column Layout: Lesson Upload Form + Per-Lesson Detailed Archive */}
      <div className="responsive-split-grid">
        {/* Upload Form */}
        <div style={{ background: "var(--bg-surface, #ffffff)", border: "1px solid var(--border-color, #e2e8f0)", borderRadius: "16px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 14px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
            رفع درس ومحتوى جديد
          </h3>

          {uploadSuccess && (
            <div style={{ padding: "10px 12px", background: "#dcfce7", color: "#166534", borderRadius: "8px", fontSize: "12px", fontWeight: 700, marginBottom: "14px" }}>
              تم رفع وحفظ الدرس والمرفقات بنجاح!
            </div>
          )}

          <form onSubmit={handleUploadLesson} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {/* Unit / Module Selection */}
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                الوحدة الدراسية التابع لها الفيديو:
              </label>
              <select
                value={selectedModuleId}
                onChange={(e) => setSelectedModuleId(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  border: "1px solid var(--border-color-strong, #cbd5e1)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  background: "var(--bg-surface)",
                  color: "var(--text-main)",
                  boxSizing: "border-box",
                  outline: "none",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {courseModules.map((m, idx) => (
                  <option key={m.id} value={m.id}>
                    {m.title || `الوحدة ${idx + 1}`}
                  </option>
                ))}
                <option value="new">+ إضافة وحدة دراسية جديدة للمقرر...</option>
              </select>

              {selectedModuleId === "new" && (
                <div style={{ marginTop: "8px" }}>
                  <input
                    type="text"
                    required
                    value={newModuleTitle}
                    onChange={(e) => setNewModuleTitle(e.target.value)}
                    placeholder="اكتب اسم الوحدة الجديدة (مثال: الوحدة الثالثة: الكيمياء العضوية)..."
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      border: "1.5px solid #059669",
                      borderRadius: "8px",
                      fontSize: "12px",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              )}
            </div>

            {/* Revision Video Toggle */}
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                padding: "10px 14px",
                background: isRevision ? "rgba(16, 185, 129, 0.12)" : "var(--bg-surface-secondary)",
                borderRadius: "10px",
                border: isRevision ? "1.5px solid #059669" : "1px solid var(--border-color)",
                transition: "all 0.15s ease",
              }}
            >
              <input
                id="isRevisionCheckbox"
                type="checkbox"
                checked={isRevision}
                onChange={(e) => setIsRevision(e.target.checked)}
                style={{
                  width: "18px",
                  height: "18px",
                  marginTop: "2px",
                  cursor: "pointer",
                  accentColor: "#059669",
                }}
              />
              <label htmlFor="isRevisionCheckbox" style={{ cursor: "pointer", userSelect: "none" }}>
                <strong style={{ display: "block", fontSize: "13px", color: isRevision ? "#059669" : "var(--text-main)", marginBottom: "2px" }}>
                  فيديو مراجعة / ورشة عمل
                </strong>
                <span style={{ fontSize: "11.5px", color: "var(--text-muted)", lineHeight: 1.4 }}>
                  عند تفعيل هذا الخيار، سيتم تصنيف الفيديو كمراجعة ووضعه تلقائياً في تبويب «المراجعات» لدى الطلاب.
                </span>
              </label>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>عنوان الدرس:</label>
              <input
                type="text"
                required
                value={lessonTitle}
                onChange={(e) => setLessonTitle(e.target.value)}
                placeholder="مثال: الدرس 5: كمية التحرك وقانون نيوتن الثاني"
                style={{ width: "100%", padding: "9px 12px", border: "1px solid var(--border-color-strong, #cbd5e1)", borderRadius: "8px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>وصف وملخص الدرس:</label>
              <textarea
                rows={2}
                value={lessonDescription}
                onChange={(e) => setLessonDescription(e.target.value)}
                placeholder="اكتب نبذة عن القوانين والنقاط المشروحة في هذا الفيديو..."
                style={{ width: "100%", padding: "8px 12px", border: "1px solid var(--border-color-strong, #cbd5e1)", borderRadius: "8px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                سعر شراء هذا الدرس منفرداً (ج.م) — حدد السعر أو اكتب 0 إذا كان متاحاً مجاناً:
              </label>
              <input
                type="number"
                min={0}
                value={lessonPrice}
                onChange={(e) => setLessonPrice(Math.max(0, Number(e.target.value) || 0))}
                placeholder="50"
                style={{ width: "100%", padding: "9px 12px", border: "1px solid var(--border-color-strong, #cbd5e1)", borderRadius: "8px", fontSize: "12px", background: "var(--bg-surface)", color: "var(--text-main)", boxSizing: "border-box" }}
              />
            </div>

            {/* Video File Upload / Cloud Link Box */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-main)" }}>
                  فيديو الشرح للمقرر:
                </label>
                <div style={{ display: "flex", background: "var(--bg-surface-secondary, #f1f5f9)", padding: "2px", borderRadius: "8px", border: "1px solid var(--border-color, #e2e8f0)" }}>
                  <button
                    type="button"
                    onClick={() => setVideoSourceType("file")}
                    style={{
                      border: "none",
                      padding: "4px 8px",
                      borderRadius: "6px",
                      fontSize: "11px",
                      fontWeight: 700,
                      cursor: "pointer",
                      background: videoSourceType === "file" ? "#059669" : "transparent",
                      color: videoSourceType === "file" ? "#ffffff" : "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <Video size={12} />
                    <span>رفع ملف (في الخلفية)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setVideoSourceType("url")}
                    style={{
                      border: "none",
                      padding: "4px 8px",
                      borderRadius: "6px",
                      fontSize: "11px",
                      fontWeight: 700,
                      cursor: "pointer",
                      background: videoSourceType === "url" ? "#059669" : "transparent",
                      color: videoSourceType === "url" ? "#ffffff" : "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <Globe size={12} />
                    <span>رابط فيديو سحابي</span>
                  </button>
                </div>
              </div>

              {videoSourceType === "url" ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <input
                    type="url"
                    value={videoExternalUrl}
                    onChange={(e) => setVideoExternalUrl(e.target.value)}
                    placeholder="ضع رابط الفيديو هنا (يوتيوب أو جوجل درايف أو رابط مباشر)..."
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      border: "1px solid var(--border-color-strong, #cbd5e1)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      background: "var(--bg-surface)",
                      color: "var(--text-main)",
                      boxSizing: "border-box",
                    }}
                  />
                  <div style={{ padding: "6px 10px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "6px", color: "#166534", fontSize: "11px" }}>
                    ⚡ <strong>حفظ فوري:</strong> الروابط السحابية تحفظ الدرس فوراً دون استهلاك باقة الإنترنت لديك ودون أي وقت انتظار.
                  </div>
                </div>
              ) : (
                <>
                  <input
                    type="file"
                    ref={videoInputRef}
                    accept="video/*"
                    onChange={handleVideoChange}
                    style={{ display: "none" }}
                  />

                  {videoPreviewUrl ? (
                    <div style={{ border: "1.5px solid #059669", borderRadius: "12px", overflow: "hidden", background: "#000" }}>
                      <div style={{ padding: "8px 12px", background: "#0f392b", color: "#ffffff", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11.5px" }}>
                        <span style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: "6px" }}>
                          <Film size={14} style={{ color: "#34d399" }} />
                          معاينة وتشغيل الفيديو قبل الرفع — {selectedVideo?.name}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedVideo(null);
                            setSelectedVideoFile(null);
                            setVideoPreviewUrl(null);
                          }}
                          style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: "11px", fontWeight: 700 }}
                        >
                          إلغاء
                        </button>
                      </div>
                      <video
                        src={videoPreviewUrl}
                        controls
                        playsInline
                        style={{ width: "100%", maxHeight: "220px", display: "block", background: "#000" }}
                      />
                      <div style={{ padding: "8px 12px", background: "#ecfdf5", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "#065f46" }}>
                        <span>المدة المحسوبة: <strong>{lessonDuration} دقيقة</strong></span>
                        <button
                          type="button"
                          onClick={() => videoInputRef.current?.click()}
                          style={{ background: "none", border: "none", color: "#059669", fontWeight: 800, cursor: "pointer", fontSize: "11px" }}
                        >
                          تغيير الفيديو
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div
                      onClick={() => videoInputRef.current?.click()}
                      style={{
                        border: "1.5px dashed var(--border-color-strong, #cbd5e1)",
                        padding: "16px",
                        borderRadius: "10px",
                        textAlign: "center",
                        background: "var(--bg-surface-secondary, #f8fafc)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <Video size={24} style={{ color: "#64748b", margin: "0 auto 6px" }} />
                      <div>
                        <strong style={{ display: "block", fontSize: "12px", color: "var(--text-main)" }}>
                          اضغط هنا لاختيار ورفع ملف الفيديو
                        </strong>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                          يمكنك معاينة الفيديو وتشغيله فور اختياره • الرفع سيتم في الخلفية بالسحابة
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Lesson Materials / PDFs Upload Box */}
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px", color: "var(--text-main)" }}>
                المذكرات والملفات المرفقة:
              </label>

              <input
                type="file"
                ref={materialsInputRef}
                multiple
                accept=".pdf,.doc,.docx,.ppt,.pptx"
                onChange={handleMaterialsChange}
                style={{ display: "none" }}
              />

              <div
                onClick={() => materialsInputRef.current?.click()}
                style={{
                  border: "1.5px dashed var(--border-color-strong, #cbd5e1)",
                  padding: "12px",
                  borderRadius: "10px",
                  textAlign: "center",
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  cursor: "pointer",
                  marginBottom: attachedFiles.length > 0 ? "8px" : "0",
                }}
              >
                <Paperclip size={18} style={{ color: "#64748b", margin: "0 auto 4px" }} />
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block" }}>
                  اضغط لرفع ملخص الدرس، واجب PDF، أو أوراق العمل
                </span>
              </div>

              {/* List of Attached Files */}
              {attachedFiles.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {attachedFiles.map((af) => (
                    <div
                      key={af.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "6px 10px",
                        background: "var(--bg-surface-secondary)",
                        borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        fontSize: "11px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", overflow: "hidden" }}>
                        <FileText size={14} style={{ color: "#2563eb", flexShrink: 0 }} />
                        <span style={{ fontWeight: 700, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {af.name}
                        </span>
                        <small style={{ color: "var(--text-muted)" }}>({af.sizeFormatted})</small>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeAttachedFile(af.id)}
                        style={{ background: "none", border: "none", color: "rgb(118, 40, 40)", cursor: "pointer", padding: "2px" }}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={isUploading}
              className="btn-primary"
              style={{
                width: "100%",
                justifyContent: "center",
                padding: "12px",
                marginTop: "6px",
                fontWeight: 800,
                fontSize: "13px",
                gap: "8px",
                opacity: isUploading ? 0.7 : 1,
                cursor: isUploading ? "not-allowed" : "pointer",
              }}
            >
              <Upload size={16} />
              {isUploading ? "جاري رفع الدرس والفيديو..." : "رفع وحفظ الدرس في المنصة"}
            </button>
          </form>
        </div>

        {/* Uploaded Lessons List: EACH LESSON WITH ITS OWN AI PREDICTIONS & TELEMETRY */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <h3 style={{ margin: 0, fontSize: "17px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
              الدروس المرفوعة ({activeLessons.length} دروس)
            </h3>

            {activeLessons.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>

                <button
                  type="button"
                  onClick={() => setIsDeleteMode((prev) => !prev)}
                  className="btn-danger"
                  style={{
                    background: "rgb(118, 40, 40)",
                    color: "#ffffff",
                    border: "1px solid rgb(118, 40, 40)",
                    borderRadius: "8px",
                    padding: "6px 14px",
                    fontSize: "12px",
                    fontWeight: 800,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    transition: "all 0.15s ease",
                  }}
                >
                  {isDeleteMode ? (
                    <>
                      <X size={14} />
                      <span>إلغاء وضع الحذف</span>
                    </>
                  ) : (
                    <>
                      <Trash2 size={14} />
                      <span>تحديد للحذف</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Dedicated Search & Filter Bar for Teacher's Uploaded Videos & Lessons */}
          {activeLessons.length > 0 && (
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "1px solid var(--border-color, #e2e8f0)",
                borderRadius: "14px",
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
                boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                {/* Search Input Box */}
                <div style={{ position: "relative", flex: 1, minWidth: "220px" }}>
                  <Search
                    size={16}
                    style={{
                      position: "absolute",
                      right: "12px",
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "#059669",
                      pointerEvents: "none",
                    }}
                  />
                  <input
                    type="text"
                    value={videoSearchQuery}
                    onChange={(e) => setVideoSearchQuery(e.target.value)}
                    placeholder={`ابحث في فيديوهات وشروحات ${activeYearLabel}...`}
                    style={{
                      width: "100%",
                      padding: "9px 38px 9px 36px",
                      borderRadius: "10px",
                      border: "1.5px solid var(--border-color, #e2e8f0)",
                      background: "var(--bg-surface-secondary, #f8fafc)",
                      color: "var(--text-main, #0f172a)",
                      fontSize: "13px",
                      fontWeight: 600,
                      outline: "none",
                      boxSizing: "border-box",
                      transition: "border-color 0.15s ease, box-shadow 0.15s ease",
                    }}
                    onFocus={(e) => (e.target.style.borderColor = "#059669")}
                    onBlur={(e) => (e.target.style.borderColor = "var(--border-color, #e2e8f0)")}
                  />
                  {videoSearchQuery && (
                    <button
                      type="button"
                      onClick={() => setVideoSearchQuery("")}
                      style={{
                        position: "absolute",
                        left: "10px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        color: "rgb(118, 40, 40)",
                        cursor: "pointer",
                        padding: "2px",
                        display: "flex",
                        alignItems: "center",
                      }}
                      title="مسح البحث"
                    >
                      <X size={15} />
                    </button>
                  )}
                </div>

              </div>

              {/* Search Active Indicator / Summary */}
              {videoSearchQuery.trim() && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: "11.5px",
                    color: "var(--text-muted, #64748b)",
                    paddingTop: "4px",
                    borderTop: "1px dashed var(--border-color, #e2e8f0)",
                  }}
                >
                  <span>
                    تم العثور على <strong style={{ color: "#059669" }}>{filteredLessons.length}</strong> من أصل {activeLessons.length} درس
                    {videoSearchQuery.trim() ? ` لبحثك عن "${videoSearchQuery}"` : ""}
                  </span>
                  <button
                    type="button"
                    onClick={() => setVideoSearchQuery("")}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#dc2626",
                      cursor: "pointer",
                      fontSize: "11.5px",
                      fontWeight: 700,
                    }}
                  >
                    إعادة ضبط الفلترة
                  </button>
                </div>
              )}
            </div>
          )}

          {activeLessons.length === 0 ? (
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "2px dashed var(--border-color, #cbd5e1)",
                borderRadius: "18px",
                padding: "48px 24px",
                textAlign: "center",
              }}
            >
              <Video size={44} style={{ color: "#059669", opacity: 0.6, margin: "0 auto 12px" }} />
              <h4 style={{ margin: "0 0 6px", fontSize: "17px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد دروس مرفوعة بعد — {activeYearLabel}
              </h4>
              <p style={{ margin: "0 auto 16px", maxWidth: "420px", color: "var(--text-muted)", fontSize: "13px", lineHeight: "1.5" }}>
                تم تنظيف كافة الأمثلة السابقة بالكامل لتبدأ برفع فيديوهاتك ومذكراتك الحقيقية من الصفر!
              </p>
              <span style={{ fontSize: "12px", color: "#059669", fontWeight: 700, background: "var(--bg-accent, #ecfdf5)", padding: "6px 14px", borderRadius: "20px", border: "1px solid #a7f3d0", display: "inline-block" }}>
                املأ نموذج "رفع درس ومحتوى جديد" على اليمين للبدء
              </span>
            </div>
          ) : filteredLessons.length === 0 ? (
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "1.5px dashed var(--border-color, #cbd5e1)",
                borderRadius: "16px",
                padding: "36px 20px",
                textAlign: "center",
              }}
            >
              <Search size={36} style={{ color: "#059669", opacity: 0.5, margin: "0 auto 10px" }} />
              <h4 style={{ margin: "0 0 6px", fontSize: "15px", fontWeight: 800, color: "var(--text-main)" }}>
                لا توجد فيديوهات أو شروحات مطابقة لبحثك
              </h4>
              <p style={{ margin: "0 auto 12px", color: "var(--text-muted)", fontSize: "12.5px" }}>
                لم يتم العثور على أي درس يطابق "{videoSearchQuery}". جرب البحث بكلمات أخرى أو مسح الفلتر.
              </p>
              <button
                type="button"
                onClick={() => setVideoSearchQuery("")}
                style={{
                  background: "var(--bg-surface-secondary, #f1f5f9)",
                  color: "#059669",
                  border: "1px solid #059669",
                  borderRadius: "8px",
                  padding: "6px 14px",
                  fontSize: "12px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                عرض جميع الفيديوهات
              </button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 310px), 1fr))", gap: "20px" }}>
              {filteredLessons.map((lesson, idx) => {
                const hasLessonVideo = Boolean(lesson.videoUrl || lesson.requiresProtectedPlayback);

                return (
                  <div
                    key={lesson.id}
                    style={{
                      background: "var(--bg-surface, #ffffff)",
                      border: isDeleteMode ? "1.5px solid rgb(118, 40, 40)" : "1px solid var(--border-color, #e2e8f0)",
                      borderRadius: "14px",
                      overflow: "hidden",
                      boxShadow: isDeleteMode ? "0 2px 10px rgba(118, 40, 40, 0.25)" : "0 1px 4px rgba(0,0,0,0.04)",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      transition: "transform 0.15s ease, box-shadow 0.15s ease",
                    }}
                  >
                    {/* Lesson Card Media Header (Dark Emerald — Matches Image 1) */}
                    <div
                      onClick={() => setActiveLessonModal(lesson)}
                      style={{
                        height: "150px",
                        background: "#0f392b",
                        padding: "16px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        cursor: "pointer",
                        position: "relative",
                      }}
                      title="انقر لمشاهدة الفيديو والرد على استفسارات وتعليقات الطلاب"
                    >
                      {/* Top Badges */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 800,
                            background: "rgba(255,255,255,0.2)",
                            color: "#ffffff",
                            padding: "3px 8px",
                            borderRadius: "6px",
                            backdropFilter: "blur(4px)",
                          }}
                        >
                          الدرس {idx + 1}
                        </span>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 800,
                            background: "rgba(0,0,0,0.4)",
                            color: "#ffffff",
                            padding: "3px 8px",
                            borderRadius: "6px",
                          }}
                        >
                          {lesson.durationFormatted || "21 دقيقة"}
                        </span>
                      </div>

                      {/* Center Play Button Circle */}
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <div
                          style={{
                            width: "48px",
                            height: "48px",
                            borderRadius: "50%",
                            background: "rgba(255,255,255,0.9)",
                            color: "#0f392b",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
                          }}
                        >
                          <Play size={22} fill="#0f392b" style={{ marginInlineStart: "2px" }} />
                        </div>
                      </div>

                      {/* Bottom Status Row */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: "11px", color: "#a7f3d0", fontWeight: 700 }}>
                          فيديو شرح تفاعلي
                        </span>
                        {hasLessonVideo ? (
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 800,
                              color: "#10b981",
                              background: "rgba(0,0,0,0.5)",
                              padding: "2px 8px",
                              borderRadius: "4px",
                            }}
                          >
                            جاهز للتشغيل
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 700,
                              color: "#fbbf24",
                              background: "rgba(0,0,0,0.5)",
                              padding: "2px 8px",
                              borderRadius: "4px",
                            }}
                          >
                            مرفق ملفات
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Lesson Card Body (Matches Image 1) */}
                    <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)", lineHeight: "1.4" }}>
                          {lesson.title}
                        </h3>
                        <p style={{ margin: "0 0 12px", fontSize: "12.5px", color: "var(--text-muted)", lineHeight: "1.5" }}>
                          {lesson.description || "شرح مبسط وتطبيقات عملية على مخرجات التعلم مع مذكرات وتلخيصات PDF."}
                        </p>
                      </div>

                      <div>
                        {/* Footer Action Bar (Matches Image 1) */}
                        <div
                          style={{
                            borderTop: "1px solid var(--border-color, #e2e8f0)",
                            paddingTop: "12px",
                            marginTop: "12px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>
                            ملفات ومذكرات: {(lesson.materials || []).length || 1}
                          </span>

                          <button
                            type="button"
                            onClick={() => setActiveLessonModal(lesson)}
                            className="btn-primary"
                            style={{ fontSize: "12px", padding: "7px 14px", display: "inline-flex", alignItems: "center", gap: "6px" }}
                          >
                            <Play size={13} fill="currentColor" />
                            <span>مشاهدة الدرس</span>
                          </button>
                        </div>

                        {/* Teacher Management Toolbar */}
                        <div
                          style={{
                            marginTop: "10px",
                            paddingTop: "10px",
                            borderTop: "1px dashed var(--border-color, #e2e8f0)",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: "6px",
                          }}
                        >
                          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                            <button
                              type="button"
                              onClick={() => triggerAttachMaterialToLesson(lesson.id)}
                              style={{
                                background: "var(--bg-surface-secondary, #f1f5f9)",
                                color: "#059669",
                                border: "1px solid var(--border-color, #e2e8f0)",
                                borderRadius: "8px",
                                padding: "4px 9px",
                                fontSize: "11px",
                                fontWeight: 700,
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                              }}
                            >
                              <Plus size={12} />
                              <span> مذكرة</span>
                            </button>
                          </div>

                          {isDeleteMode && (
                            <button
                              type="button"
                              onClick={() => handleDeleteLesson(lesson.id, lesson.title)}
                              style={{
                                background: "var(--danger-action-bg)",
                                color: "#ffffff",
                                border: "none",
                                borderRadius: "8px",
                                padding: "4px 10px",
                                fontSize: "11px",
                                fontWeight: 800,
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                              }}
                            >
                              <Trash2 size={12} />
                              <span>حذف</span>
                            </button>
                          )}
                        </div>

                        {/* Attached Material Chips if any */}
                        {lesson.materials && lesson.materials.length > 0 && (
                          <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {lesson.materials.map((mat) => (
                              <div
                                key={mat.id}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "5px",
                                  padding: "3px 8px",
                                  background: "var(--bg-surface-secondary, #f8fafc)",
                                  borderRadius: "6px",
                                  fontSize: "10.5px",
                                  border: "1px solid var(--border-color, #e2e8f0)",
                                }}
                              >
                                <FileText size={11} style={{ color: "#2563eb" }} />
                                <span style={{ fontWeight: 600, maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {mat.title}
                                </span>
                                <button
                                  type="button"
                                  title="تنزيل المذكرة"
                                  onClick={() => void downloadLessonMaterial(mat.fileUrl, mat.title)}
                                  style={{ background: "none", border: "none", color: "#059669", cursor: "pointer", padding: "0 2px" }}
                                >
                                  <Download size={11} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>


      <input
        type="file"
        ref={individualVideoInputRef}
        accept="video/*"
        onChange={handleIndividualVideoChange}
        style={{ display: "none" }}
      />

      {toast && (
        <div className="wizard-toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
};

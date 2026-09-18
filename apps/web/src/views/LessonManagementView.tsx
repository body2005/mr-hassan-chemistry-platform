import React, { useState, useRef, useEffect } from "react";
import {
  Film,
  Bot,
  Brain,
  Clock,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  HelpCircle,
  MessageSquare,
  Paperclip,
  Plus,
  Printer,
  RotateCcw,
  Sparkles,
  Trash2,
  TrendingDown,
  Upload,
  Video,
  X,
  Search,
  Globe,
} from "lucide-react";
import { Course, CurrentUser, VideoLesson } from "../types/lms";
import { exportToCsv, exportToDocx, exportToPrintPdf } from "../utils/exportEngine";
import { courseService } from "../services/lmsService";
import { uploadManager } from "../services/uploadManager";
import { apiRequest, apiUrl, fetchApiBlob } from "../services/apiClient";
import { useConfirm } from "../components/ConfirmWizard";

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

/** A teacher receives the same short-lived, lesson-scoped playback URL as a
 * student. Native storage paths never reach a video element. */
const ManagedLessonVideo: React.FC<{ lesson: VideoLesson }> = ({ lesson }) => {
  const [streamUrl, setStreamUrl] = useState(lesson.videoUrl);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    setError(null);
    if (!lesson.requiresProtectedPlayback) {
      setStreamUrl(lesson.videoUrl);
      return () => { disposed = true; };
    }
    setStreamUrl("");
    void apiRequest<{ stream_url: string }>(`/lessons/${lesson.id}/video-token`, {
      method: "POST",
    })
      .then(({ stream_url }) => {
        if (!disposed) setStreamUrl(apiUrl(stream_url));
      })
      .catch(() => {
        if (!disposed) setError("تعذر تجهيز بث الفيديو. أعد المحاولة.");
      });
    return () => { disposed = true; };
  }, [lesson.id, lesson.requiresProtectedPlayback, lesson.videoUrl]);

  if (error) {
    return <div style={{ padding: "24px", color: "#b91c1c", textAlign: "center" }}>{error}</div>;
  }
  if (!streamUrl) {
    return <div style={{ padding: "24px", color: "#475569", textAlign: "center" }}>جاري تجهيز البث المحمي…</div>;
  }
  return (
    <video
      src={streamUrl}
      controls
      controlsList="nodownload noremoteplayback"
      disablePictureInPicture
      disableRemotePlayback
      onContextMenu={(event) => event.preventDefault()}
      playsInline
      preload="metadata"
      style={{ width: "100%", maxHeight: "360px", display: "block", background: "#000", userSelect: "none" }}
    />
  );
};

export const LessonManagementView: React.FC<LessonManagementViewProps> = ({
  currentUser,
  courses: availableCourses,
  onCoursesChanged,
}) => {

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



  // Minimum Views Threshold Configured by Teacher (Requirement: AI predicts after X students watch)
  const [minViewsThreshold, setMinViewsThreshold] = useState<number>(20);

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

  // Transcript & AI Summary Modals State
  const [transcriptModalLesson, setTranscriptModalLesson] = useState<VideoLesson | null>(null);
  const [transcriptModalSegments] = useState<Array<{ id: string; sequence: number; start_time: number; end_time: number; time_formatted: string; text: string }>>([]);
  const [transcriptModalSearch, setTranscriptModalSearch] = useState("");
  const [visibleTranscriptModalCount, setVisibleTranscriptModalCount] = useState(60);
  const [loadingTranscriptModal] = useState(false);

  const [summaryModalLesson, setSummaryModalLesson] = useState<VideoLesson | null>(null);
  const [summaryData] = useState<{ title: string; full_overview: string; total_duration_sec: number; language: string; sections: Array<{ time_range: string; start_time: number; end_time: number; summary_snippet: string }> } | null>(null);
  const [visibleSummaryCount, setVisibleSummaryCount] = useState(50);
  const [loadingSummary] = useState(false);

  const filteredTranscriptModalSegments = React.useMemo(() => {
    if (!transcriptModalSearch.trim()) return transcriptModalSegments;
    const q = transcriptModalSearch.toLowerCase().trim();
    return transcriptModalSegments.filter((s) => s.text.toLowerCase().includes(q));
  }, [transcriptModalSegments, transcriptModalSearch]);

  useEffect(() => {
    setVisibleTranscriptModalCount(60);
  }, [transcriptModalSearch]);

  // File Input Refs for Guaranteed Click Triggering
  const videoInputRef = useRef<HTMLInputElement>(null);
  const materialsInputRef = useRef<HTMLInputElement>(null);

  const activeCourse = courses.find((c) => c.academicYear === selectedYear);
  // Reverse order so the latest uploaded video/lesson is always displayed at the top
  const activeLessons: VideoLesson[] = React.useMemo(() => {
    if (!activeCourse?.lessons) return [];
    return [...activeCourse.lessons].reverse();
  }, [activeCourse]);

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

  function handleThresholdChange(val: number) {
    const num = Math.max(1, Math.min(val, 200));
    setMinViewsThreshold(num);
  }

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
      if (!module) {
        module = await courseService.addModule(course.id, { title: "الوحدة الأولى", position: 1 });
      }
      const savedTitle = lessonTitle.trim();
      const directCloudUrl = videoSourceType === "url" && videoExternalUrl.trim() ? videoExternalUrl.trim() : undefined;
      const addedLesson = await courseService.addLesson(module.id, {
        title: savedTitle,
        kind: "video",
        position: module.lessons.length + 1,
        content: lessonDescription.trim() || undefined,
        video_duration_seconds: lessonDuration * 60,
        video_asset_key: directCloudUrl,
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
      } else if (directCloudUrl) {
        notify(`تم حفظ درس "${savedTitle}" بنجاح مع رابط الفيديو السحابي المباشر!`);
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
    setUploadSuccess(true);
    setTimeout(() => setUploadSuccess(false), 5000);
  }

  // Universal Export Handlers
  function getExportPayload() {
    const headers = [
      "عنوان الدرس",
      "المدة",
      "المشاهدات",
      "نسبة المتابعة %",
      "توقع التعثر %",
      "نسبة عدم الفهم %",
      "المقطع الأكثر إعادة",
      "أبرز نقاط التردد والخلط",
    ];

    const rows = activeLessons.map((l) => [
      l.title,
      l.durationFormatted,
      `${l.aiSignals?.viewsCount || 0} طالب`,
      `${l.aiSignals?.completionRate || 0}%`,
      `${l.expectedStruggleRate}%`,
      `${l.predictedMisconceptionRate}%`,
      l.aiSignals?.mostRewatchedSegment ? `${l.aiSignals.mostRewatchedSegment.timeRange} (${l.aiSignals.mostRewatchedSegment.conceptLabel})` : "—",
      l.flaggedHardConcepts.join(" ، ") || "—",
    ]);

    return {
      title: `تقرير تحليل وتوقعات صعوبة الدروس بالذكاء الاصطناعي - ${activeYearLabel}`,
      subtitle: `عدد الدروس: ${activeLessons.length} • الحد الأدنى للمشاهدات: ${minViewsThreshold} طالب`,
      headers,
      rows,
      summaryStats: [
        { label: "المادة الدراسية", value: activeCourse?.title || "المقرر الدراسي" },
        { label: "إجمالي الدروس", value: activeLessons.length },
        { label: "معيار تفعيل الذكاء الاصطناعي", value: `${minViewsThreshold} مشاهدة` },
      ],
    };
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
            <Download size={15} /> تصدير التقرير (Generate Report)
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
                <strong>تصدير Word (.docx حقيقي)</strong>
              </button>

              <button
                onClick={() => {
                  exportToCsv(getExportPayload(), `difficulty_report_${selectedYear}.csv`);
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", borderBottom: "1px solid var(--border-color)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-main)" }}
              >
                <FileSpreadsheet size={16} style={{ color: "#059669" }} />
                <strong>تصدير Excel / CSV</strong>
              </button>

              <button
                onClick={() => {
                  exportToPrintPdf(getExportPayload());
                  setExportDropdownOpen(false);
                }}
                style={{ width: "100%", textAlign: "right", padding: "10px 14px", background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-main)" }}
              >
                <Printer size={16} style={{ color: "#0f392b" }} />
                <strong>تصدير / طباعة PDF</strong>
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

        {/* AI Threshold Configuration Pill (Teacher Control) */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            background: "var(--bg-surface, #ffffff)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "6px 14px",
            borderRadius: "10px",
          }}
        >
          <Bot size={18} style={{ color: "#059669" }} />
          <span style={{ fontSize: "12px", color: "var(--text-main)", fontWeight: 700 }}>
            الحد الأدنى لمشاهدات الطلاب لتفعيل تحليل الـ AI:
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <input
              type="number"
              min={1}
              max={200}
              value={minViewsThreshold}
              onChange={(e) => handleThresholdChange(parseInt(e.target.value) || 20)}
              style={{
                width: "54px",
                padding: "3px 6px",
                textAlign: "center",
                fontWeight: 800,
                fontSize: "13px",
                borderRadius: "6px",
                border: "1.5px solid #059669",
                background: "var(--bg-accent, #ecfdf5)",
                color: "var(--text-main)",
                outline: "none",
              }}
            />
            <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>طالب</span>
          </div>
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
                    placeholder="ضع رابط الفيديو هنا (YouTube / Google Drive / MP4 سحابي مباشر)..."
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
                          معاينة وتشغيل الفيديو قبل الرفع ({selectedVideo?.name})
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
                المذكرات والملفات المرفقة (PDF / Word):
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
                        style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", padding: "2px" }}
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
              الدروس المرفوعة وتوقعات صعوبة كل درس ({activeLessons.length} دروس)
            </h3>

            {activeLessons.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>

                <button
                  type="button"
                  onClick={() => setIsDeleteMode((prev) => !prev)}
                  style={{
                    background: isDeleteMode ? "#b91c1c" : "#fee2e2",
                    color: isDeleteMode ? "#ffffff" : "#b91c1c",
                    border: isDeleteMode ? "1.5px solid #991b1b" : "1px solid #fca5a5",
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
                      <span>تحديد للحذف (Select to Delete)</span>
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
                        color: "var(--text-muted, #94a3b8)",
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
                لا توجد دروس مرفوعة بعد ({activeYearLabel})
              </h4>
              <p style={{ margin: "0 auto 16px", maxWidth: "420px", color: "var(--text-muted)", fontSize: "13px", lineHeight: "1.5" }}>
                تم تفريغ كافة الأمثلة السابقة بالكامل لتبدأ برفع فيديوهاتك ومذكراتك الحقيقية وتجربة توقعات الذكاء الاصطناعي من الصفر!
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
            filteredLessons.map((lesson, idx) => {
            const viewsCount = lesson.aiSignals?.viewsCount || 0;
            const hasRealTelemetry = viewsCount > 0 && Boolean(lesson.aiSignals);
            const isAnalyzed = hasRealTelemetry && viewsCount >= minViewsThreshold;
            const completionRate = lesson.aiSignals?.completionRate || 0;

            return (
              <div
                key={lesson.id}
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  border: isDeleteMode
                    ? "1.5px solid #ef4444"
                    : (isAnalyzed ? "1px solid var(--border-color, #e2e8f0)" : "1.5px dashed #cbd5e1"),
                  borderRadius: "16px",
                  padding: "22px",
                  boxShadow: isDeleteMode ? "0 2px 10px rgba(239, 68, 68, 0.12)" : "0 1px 4px rgba(0,0,0,0.03)",
                  position: "relative",
                  transition: "all 0.2s ease",
                }}
              >
                {/* Strictly Per-Lesson Video Player Section */}
                {(() => {
                  const lessonVideoUrl = lesson.videoUrl;
                  const hasLessonVideo = Boolean(lessonVideoUrl || lesson.requiresProtectedPlayback);

                  return (
                    <div
                      style={{
                        background: "var(--bg-surface-secondary, #f8fafc)",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        borderRadius: "14px",
                        padding: "14px",
                        marginBottom: "16px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: hasLessonVideo ? "12px" : "0", flexWrap: "wrap", gap: "10px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <Film size={18} style={{ color: "#059669" }} />
                          <strong style={{ fontSize: "13px", color: "var(--text-main)" }}>
                            فيديو الشرح: {lesson.title}
                          </strong>
                          {hasLessonVideo ? (
                            <span style={{ fontSize: "11px", color: "#059669", fontWeight: 700, background: "#ecfdf5", padding: "2px 8px", borderRadius: "6px" }}>
                              جاهز للتشغيل
                            </span>
                          ) : (
                            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                              (مرفق مذكرات / ملفات)
                            </span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => triggerAttachVideoToLesson(lesson.id)}
                          style={{
                            background: "var(--bg-surface, #ffffff)",
                            color: "#059669",
                            border: "1px solid #059669",
                            borderRadius: "8px",
                            padding: "5px 12px",
                            fontSize: "11.5px",
                            fontWeight: 700,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                          }}
                        >
                          <Upload size={13} />
                          <span>{hasLessonVideo ? "تغيير فيديو هذا الدرس" : "رفع فيديو لهذا الدرس"}</span>
                        </button>
                      </div>

                      {/* Video Player — Appears ONLY when this specific lesson has a video */}
                      {hasLessonVideo && (
                        <div style={{ borderRadius: "10px", overflow: "hidden", border: "1.5px solid #0f392b", background: "#000" }}>
                          {(() => {
                            if (lesson.requiresProtectedPlayback) {
                              return <ManagedLessonVideo lesson={lesson} />;
                            }
                            const ytMatch = lessonVideoUrl.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([\w-]{11})/);
                            if (ytMatch && ytMatch[1]) {
                              return (
                                <iframe
                                  src={`https://www.youtube-nocookie.com/embed/${ytMatch[1]}`}
                                  title={lesson.title}
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                  style={{ width: "100%", height: "360px", border: "none", display: "block" }}
                                />
                              );
                            }
                            if (lessonVideoUrl.includes("drive.google.com")) {
                              const driveEmbed = lessonVideoUrl.replace(/\/view(\?.*)?$/, "/preview");
                              return (
                                <iframe
                                  src={driveEmbed}
                                  title={lesson.title}
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                  style={{ width: "100%", height: "360px", border: "none", display: "block" }}
                                />
                              );
                            }
                            return (
                              <video
                                key={lessonVideoUrl}
                                src={lessonVideoUrl}
                                controls
                                controlsList="nodownload nofullscreen noremoteplayback"
                                disablePictureInPicture
                                disableRemotePlayback
                                onContextMenu={(e) => e.preventDefault()}
                                playsInline
                                preload="metadata"
                                style={{ width: "100%", maxHeight: "360px", display: "block", background: "#000", userSelect: "none" }}
                              />
                            );
                          })()}
                          <div style={{ padding: "8px 12px", background: "#0f392b", color: "#ecfdf5", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px" }}>
                            <span>{lesson.title}</span>
                            <span style={{ color: "#34d399", fontWeight: 700 }}>تشغيل فائق الدقة وسلس للمشاهدة والشرح</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Lesson Top Header: Title, Duration, Views Badge */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent, #ecfdf5)", padding: "2px 8px", borderRadius: "6px" }}>
                        الدرس {idx + 1}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>
                        {lesson.durationFormatted}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>
                        • {viewsCount} مشاهدة طالب
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "0 0 4px", flexWrap: "wrap" }}>
                      <h4 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                        {lesson.title}
                      </h4>
                    </div>
                    <p style={{ margin: 0, fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.4" }}>
                      {lesson.description}
                    </p>
                  </div>

                  {/* Lesson actions */}
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    {isDeleteMode && (
                      <button
                        type="button"
                        onClick={() => handleDeleteLesson(lesson.id, lesson.title)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "6px 14px",
                          borderRadius: "8px",
                          background: "#dc2626",
                          color: "#ffffff",
                          border: "none",
                          fontSize: "12px",
                          fontWeight: 800,
                          cursor: "pointer",
                          boxShadow: "0 2px 6px rgba(220, 38, 38, 0.3)",
                        }}
                        title="حذف هذا الفيديو"
                      >
                        <Trash2 size={14} />
                        <span>حذف الفيديو</span>
                      </button>
                    )}

                    {isAnalyzed && (
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 800,
                        padding: "4px 10px",
                        borderRadius: "8px",
                        background: lesson.expectedStruggleRate > 40 ? "var(--bg-accent-warm)" : "var(--bg-accent)",
                        color: lesson.expectedStruggleRate > 40 ? "#ef4444" : "#059669",
                        border: lesson.expectedStruggleRate > 40 ? "1px solid #fca5a5" : "1px solid #a7f3d0",
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                      }}
                    >
                      <Sparkles size={13} />
                      <span>{lesson.expectedStruggleRate > 40 ? "درس عالي الصعوبة" : "صعوبة معتدلة"}</span>
                    </span>
                  )}
                  </div>
                </div>

                {/* Show analytics only after actual student telemetry is available. */}
                {isAnalyzed ? (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
                      <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "12px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#059669", marginBottom: "2px" }}>
                          <Eye size={15} />
                          <span style={{ fontSize: "11px", fontWeight: 800 }}>نسبة متابعة الدرس:</span>
                        </div>
                        <strong style={{ display: "block", fontSize: "20px", color: "var(--text-main)" }}>
                          {completionRate}%
                        </strong>
                        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>متوسط إتمام المشاهدة</span>
                      </div>

                      <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "12px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#d97706", marginBottom: "2px" }}>
                          <TrendingDown size={15} />
                          <span style={{ fontSize: "11px", fontWeight: 800 }}>توقع التعثر وصعوبة الدرس:</span>
                        </div>
                        <strong style={{ display: "block", fontSize: "20px", color: "var(--text-main)" }}>
                          {lesson.expectedStruggleRate}%
                        </strong>
                        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>نسبة الطلاب المتوقع تعثرهم</span>
                      </div>

                      <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "12px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#d97706", marginBottom: "2px" }}>
                          <Brain size={15} />
                          <span style={{ fontSize: "11px", fontWeight: 800 }}>نسبة عدم الفهم المرصودة:</span>
                        </div>
                        <strong style={{ display: "block", fontSize: "20px", color: "var(--text-main)" }}>
                          {lesson.predictedMisconceptionRate}%
                        </strong>
                        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>خلط المفاهيم</span>
                      </div>
                    </div>

                    {lesson.aiSignals && (
                      <div
                        style={{
                          background: "var(--bg-surface-secondary)",
                          border: "1px solid var(--border-color)",
                          borderRadius: "12px",
                          padding: "14px",
                          marginBottom: "14px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "10px" }}>
                          <Bot size={15} style={{ color: "#059669" }} />
                          <strong style={{ fontSize: "12px", color: "var(--text-main)" }}>
                            مصادر تحليل الذكاء الاصطناعي لهذا الدرس (AI Telemetry Signals):
                          </strong>
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
                          {lesson.aiSignals.mostRewatchedSegment && (
                            <div style={{ background: "var(--bg-surface)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#2563eb", marginBottom: "3px" }}>
                                <RotateCcw size={13} />
                                <strong style={{ fontSize: "11px" }}>١. أكثر مقطع تمت إعادته (Heatmap):</strong>
                              </div>
                              <span style={{ display: "block", fontSize: "11.5px", color: "var(--text-main)", fontWeight: 700 }}>
                                {lesson.aiSignals.mostRewatchedSegment.timeRange}
                                <small style={{ color: "#2563eb", marginInlineStart: "6px" }}>
                                  ({lesson.aiSignals.mostRewatchedSegment.replayCount} إعادة تكرار)
                                </small>
                              </span>
                              <small style={{ display: "block", fontSize: "10.5px", color: "var(--text-muted)", marginTop: "2px" }}>
                                {lesson.aiSignals.mostRewatchedSegment.conceptLabel}
                              </small>
                            </div>
                          )}

                          {lesson.aiSignals.commentsSentiment && (
                            <div style={{ background: "var(--bg-surface)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#d97706", marginBottom: "3px" }}>
                                <MessageSquare size={13} />
                                <strong style={{ fontSize: "11px" }}>٢. تحليل تعليقات وأسئلة الطلاب:</strong>
                              </div>
                              <span style={{ display: "block", fontSize: "11.5px", color: "var(--text-main)", fontWeight: 700 }}>
                                رصد {lesson.aiSignals.commentsSentiment.confusionQuestionsCount} سؤال عدم فهم
                              </span>
                              <small style={{ display: "block", fontSize: "10.5px", color: "#d97706", marginTop: "2px" }}>
                                {lesson.aiSignals.commentsSentiment.sampleQuestion}
                              </small>
                            </div>
                          )}

                          {lesson.aiSignals.assignmentPerformance && (
                            <div style={{ background: "var(--bg-surface)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#059669", marginBottom: "3px" }}>
                                <FileText size={13} />
                                <strong style={{ fontSize: "11px" }}>٣. متوسط درجات واجب الدرس:</strong>
                              </div>
                              <span style={{ display: "block", fontSize: "11.5px", color: "var(--text-main)", fontWeight: 700 }}>
                                {lesson.aiSignals.assignmentPerformance.averageScore}%
                              </span>
                            </div>
                          )}

                          {lesson.aiSignals.quizPerformance && (
                            <div style={{ background: "var(--bg-surface)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#059669", marginBottom: "3px" }}>
                                <HelpCircle size={13} />
                                <strong style={{ fontSize: "11px" }}>٤. نتائج ونسب خطأ الكويز:</strong>
                              </div>
                              <span style={{ display: "block", fontSize: "11.5px", color: "var(--text-main)", fontWeight: 700 }}>
                                {lesson.aiSignals.quizPerformance.averageScore}% نسبة الدقة
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                ) : null}

                {/* Attached Materials Section & Add Material Button */}
                <div style={{ background: "var(--bg-surface-secondary, #f8fafc)", padding: "10px 14px", borderRadius: "10px", border: "1px solid var(--border-color)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: (lesson.materials && lesson.materials.length > 0) ? "8px" : "0" }}>
                    <strong style={{ fontSize: "11.5px", color: "var(--text-main)" }}>
                      الملفات والمذكرات المرفقة ({(lesson.materials || []).length}):
                    </strong>
                    <button
                      type="button"
                      onClick={() => {
                        triggerAttachMaterialToLesson(lesson.id);
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#059669",
                        fontSize: "11.5px",
                        fontWeight: 800,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <Plus size={13} /> + رفع مذكرة إضافية للدرس
                    </button>
                  </div>

                  {lesson.materials && lesson.materials.length > 0 ? (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                      {lesson.materials.map((mat) => (
                        <div
                          key={mat.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            padding: "5px 10px",
                            background: "var(--bg-surface, #ffffff)",
                            borderRadius: "6px",
                            fontSize: "11px",
                            border: "1px solid var(--border-color)",
                          }}
                        >
                          <FileText size={13} style={{ color: "#2563eb" }} />
                          <span style={{ fontWeight: 700, color: "var(--text-main)" }}>{mat.title}</span>
                          <span style={{ color: "var(--text-muted)", fontSize: "10px" }}>({mat.fileSize})</span>
                          <button
                            type="button"
                            aria-label={`تنزيل ${mat.title}`}
                            title="تنزيل المذكرة"
                            onClick={() => void downloadLessonMaterial(mat.fileUrl, mat.title)}
                            style={{ background: "transparent", border: "none", color: "#059669", cursor: "pointer", display: "inline-flex", padding: "2px" }}
                          >
                            <Download size={13} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>لم يتم إرفاق مذكرات إضافية بعد</span>
                  )}
                </div>
              </div>
            );
          })
        )}
        </div>
      </div>

      {/* TEACHER TRANSCRIPT & SEGMENTS SEARCH MODAL */}
      {transcriptModalLesson && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            zIndex: 99999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color)",
              borderRadius: "20px",
              maxWidth: "760px",
              width: "100%",
              maxHeight: "88vh",
              overflowY: "auto",
              padding: "26px",
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <FileText size={20} style={{ color: "#059669" }} />
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                  تفريغ الشرح النصي والفهرس الزمني: {transcriptModalLesson.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setTranscriptModalLesson(null)}
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", display: "flex" }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ position: "relative", marginBottom: "16px" }}>
              <Search size={15} style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
              <input
                type="text"
                placeholder="ابحث في نص الشرح للوصول إلى أي كلمة أو مفهوم..."
                value={transcriptModalSearch}
                onChange={(e) => setTranscriptModalSearch(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 38px 10px 14px",
                  borderRadius: "10px",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-surface-secondary)",
                  color: "var(--text-main)",
                  fontSize: "13px",
                }}
              />
            </div>

            {loadingTranscriptModal ? (
              <div style={{ textAlign: "center", padding: "30px", color: "var(--text-muted)" }}>
                جاري تحميل تفريغ الشرح...
              </div>
            ) : filteredTranscriptModalSegments.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", background: "var(--bg-surface-secondary)", borderRadius: "10px", color: "var(--text-muted)", fontSize: "13px" }}>
                {transcriptModalSearch.trim()
                  ? `لا توجد نتائج مطابقة لبحثك: "${transcriptModalSearch}"`
                  : (transcriptModalLesson.description ? transcriptModalLesson.description : "لا يتوفر تفريغ مسجل لهذا الدرس حتى الآن.")}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "360px", overflowY: "auto", paddingInlineEnd: "4px" }}>
                {filteredTranscriptModalSegments
                  .slice(0, visibleTranscriptModalCount)
                  .map((seg) => (
                    <div
                      key={seg.id || seg.sequence}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "10px",
                        padding: "10px 14px",
                        borderRadius: "10px",
                        background: "var(--bg-surface-secondary)",
                        border: "1px solid var(--border-color)",
                      }}
                    >
                      <span
                        style={{
                          background: "#059669",
                          color: "#ffffff",
                          padding: "2px 8px",
                          borderRadius: "6px",
                          fontSize: "11px",
                          fontWeight: 800,
                          flexShrink: 0,
                          marginTop: "2px",
                        }}
                      >
                        {seg.time_formatted}
                      </span>
                      <span style={{ fontSize: "13px", color: "var(--text-main)", lineHeight: "1.5" }}>
                        {seg.text}
                      </span>
                    </div>
                  ))}

                {filteredTranscriptModalSegments.length > visibleTranscriptModalCount && (
                  <button
                    type="button"
                    onClick={() => setVisibleTranscriptModalCount((prev) => prev + 80)}
                    style={{
                      padding: "8px",
                      borderRadius: "8px",
                      border: "1px dashed #059669",
                      background: "var(--bg-accent, #ecfdf5)",
                      color: "#059669",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: "pointer",
                      marginTop: "4px",
                    }}
                  >
                    عرض المزيد من المقاطع ({visibleTranscriptModalCount} معروض من إجمالي {filteredTranscriptModalSegments.length})
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TEACHER AI SUMMARY MODAL */}
      {summaryModalLesson && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            zIndex: 99999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color)",
              borderRadius: "20px",
              maxWidth: "760px",
              width: "100%",
              maxHeight: "88vh",
              overflowY: "auto",
              padding: "26px",
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Bot size={20} style={{ color: "#0f766e" }} />
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>
                  ملخص الذكاء الاصطناعي للدرس: {summaryModalLesson.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSummaryModalLesson(null)}
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", display: "flex" }}
              >
                <X size={20} />
              </button>
            </div>

            {loadingSummary ? (
              <div style={{ textAlign: "center", padding: "30px", color: "var(--text-muted)" }}>
                جاري توليد ملخص الدرس والمفاهيم الجوهرية...
              </div>
            ) : !summaryData ? (
              <div style={{ padding: "20px", textAlign: "center", background: "var(--bg-surface-secondary)", borderRadius: "10px", color: "var(--text-muted)" }}>
                تعذر توليد الملخص لعدم توفر نص كافي مفهرس.
              </div>
            ) : (
              <div>
                <div style={{ background: "var(--bg-accent, #ecfdf5)", border: "1px solid #a7f3d0", borderRadius: "12px", padding: "16px", marginBottom: "18px" }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: "14px", fontWeight: 800, color: "#065f46" }}>
                    نظرة شاملة على الدرس ({summaryData.language === "ar" ? "اللغة العربية" : summaryData.language}):
                  </h4>
                  <p style={{ margin: 0, fontSize: "13px", color: "var(--text-main)", lineHeight: "1.6" }}>
                    {summaryData.full_overview}
                  </p>
                </div>

                {summaryData.sections && summaryData.sections.length > 0 && (
                  <div>
                    <h4 style={{ margin: "0 0 10px", fontSize: "13.5px", fontWeight: 800, color: "var(--text-main)" }}>
                      المحاور والمقاطع الزمنية المفهرسة:
                    </h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {summaryData.sections.slice(0, visibleSummaryCount).map((sec, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: "10px",
                            padding: "10px 14px",
                            borderRadius: "10px",
                            background: "var(--bg-surface-secondary)",
                            border: "1px solid var(--border-color)",
                          }}
                        >
                          <span
                            style={{
                              background: "#0f766e",
                              color: "#ffffff",
                              padding: "2px 8px",
                              borderRadius: "6px",
                              fontSize: "11px",
                              fontWeight: 800,
                              flexShrink: 0,
                              marginTop: "2px",
                            }}
                          >
                            {sec.time_range}
                          </span>
                          <span style={{ fontSize: "12.5px", color: "var(--text-main)", lineHeight: "1.5" }}>
                            {sec.summary_snippet}
                          </span>
                        </div>
                      ))}

                      {summaryData.sections.length > visibleSummaryCount && (
                        <button
                          type="button"
                          onClick={() => setVisibleSummaryCount((prev) => prev + 50)}
                          style={{
                            padding: "8px",
                            borderRadius: "8px",
                            border: "1px dashed #0f766e",
                            background: "var(--bg-accent, #ecfdf5)",
                            color: "#0f766e",
                            fontSize: "12px",
                            fontWeight: 700,
                            cursor: "pointer",
                            marginTop: "4px",
                          }}
                        >
                          عرض المزيد من المحاور المفهرسة ({visibleSummaryCount} معروض من إجمالي {summaryData.sections.length})
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

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

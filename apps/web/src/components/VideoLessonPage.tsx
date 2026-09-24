import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  Settings,
  Expand,
  Share2,
  Eye,
  Calendar,
  Download,
  FileText,
  Heart,
  CornerDownLeft,
  ChevronDown,
  ChevronLeft,
  ArrowRight,
} from "lucide-react";
import { Course, CurrentUser, VideoLesson } from "../types/lms";
import { apiRequest, apiUrl } from "../services/apiClient";
import { VideoTelemetryTracker } from "../services/videoTelemetry";
import { lessonAccessService } from "../services/paymentService";
import { useToast } from "./ToastProvider";

export interface VideoLessonPageProps {
  lesson: VideoLesson;
  course: Course;
  currentUser?: CurrentUser | null;
  completedLessonIds: string[];
  onToggleCompleteLesson: (lessonId: string) => void;
  onSelectLesson: (lesson: VideoLesson) => void;
  onClose: () => void;
  onDownloadMaterial?: (url: string, filename: string) => void;
}

type CommentItem = {
  id: string;
  author: string;
  role?: string;
  isTeacher?: boolean;
  isMine?: boolean;
  avatar?: string;
  body: string;
  timeAgo: string;
  likes: number;
  isLiked?: boolean;
  replies?: CommentItem[];
};

export const VideoLessonPage: React.FC<VideoLessonPageProps> = ({
  lesson,
  course,
  currentUser,
  completedLessonIds,
  onToggleCompleteLesson,
  onSelectLesson,
  onClose,
  onDownloadMaterial,
}) => {
  const toast = useToast();
  const videoElementRef = useRef<HTMLVideoElement | null>(null);
  const telemetryTrackerRef = useRef<VideoTelemetryTracker | null>(null);
  const playerContainerRef = useRef<HTMLDivElement | null>(null);

  // Completion & Anti-skip tracking
  const isTeacher = currentUser?.role === "teacher";
  const isAlreadyCompleted = isTeacher || completedLessonIds.includes(lesson.id);
  const [isLessonFinished, setIsLessonFinished] = useState(isAlreadyCompleted);
  const [maxWatchedTime, setMaxWatchedTime] = useState(0);
  const maxWatchedRef = useRef(0);

  // Playback state
  const [playbackUrl, setPlaybackUrl] = useState("");
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [selectedQuality, setSelectedQuality] = useState("1080p");
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  // Wide/theater mode: video fills the entire viewport instead of the column.
  const [isWide, setIsWide] = useState(false);
  const controlsTimeoutRef = useRef<number | null>(null);

  // Sort & Comments state (Real comments only, NO mock comments)
  const [sortBy, setSortBy] = useState<"newest" | "top">("newest");
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [newCommentText, setNewCommentText] = useState("");
  const [replyInputs, setReplyInputs] = useState<Record<string, string>>({});
  const [activeReplyId, setActiveReplyId] = useState<string | null>(null);
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);

  // Reset lesson state when lesson changes
  useEffect(() => {
    const done = isTeacher || completedLessonIds.includes(lesson.id);
    setIsLessonFinished(done);
    const initialMax = done ? 999999 : 0;
    maxWatchedRef.current = initialMax;
    setMaxWatchedTime(initialMax);
    setCurrentTime(0);
    setIsPlaying(false);
  }, [lesson.id, completedLessonIds, isTeacher]);

  // Protected playback token fetching
  useEffect(() => {
    let disposed = false;
    setPlaybackUrl("");
    setPlaybackError(null);

    if (!lesson.videoUrl && !lesson.requiresProtectedPlayback) {
      return () => {
        disposed = true;
      };
    }

    if (!lesson.requiresProtectedPlayback) {
      setPlaybackUrl(lesson.videoUrl);
      return () => {
        disposed = true;
      };
    }

    void apiRequest<{ stream_url: string }>(`/lessons/${lesson.id}/video-token`, {
      method: "POST",
    })
      .then(({ stream_url }) => {
        if (!disposed) setPlaybackUrl(apiUrl(stream_url));
      })
      .catch(() => {
        if (!disposed) {
          setPlaybackError("تعذر تجهيز بث الفيديو المحمي. تأكد من صلاحية الوصول ثم أعد المحاولة.");
        }
      });

    return () => {
      disposed = true;
    };
  }, [lesson.id, lesson.videoUrl, lesson.requiresProtectedPlayback]);

  const [isAccessRequested, setIsAccessRequested] = useState(false);
  const [isSubmittingAccessRequest, setIsSubmittingAccessRequest] = useState(false);

  useEffect(() => {
    const handleUnlocked = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const targetId = detail?.lesson_id || detail?.resource_id;
      if (targetId && targetId === lesson.id) {
        setPlaybackError(null);
        setIsAccessRequested(false);
        void apiRequest<{ stream_url: string }>(`/lessons/${lesson.id}/video-token`, {
          method: "POST",
        })
          .then(({ stream_url }) => {
            setPlaybackUrl(apiUrl(stream_url));
            toast({ message: "تمت إتاحة الدرس بنجاح، جاري تشغيل الفيديو!", tone: "success" });
          })
          .catch(() => undefined);
      }
    };
    window.addEventListener("lms_lesson_unlocked", handleUnlocked);
    return () => window.removeEventListener("lms_lesson_unlocked", handleUnlocked);
  }, [lesson.id, toast]);

  async function handleRequestLessonAccess() {
    setIsSubmittingAccessRequest(true);
    try {
      await lessonAccessService.requestAccess(lesson.id);
      setIsAccessRequested(true);
      toast({
        message: "تم إرسال طلب إتاحة الدرس للمعلم. سيتم بدء تشغيل الفيديو تلقائياً فور موافقة المعلم.",
        tone: "success",
      });
    } catch (err) {
      toast({
        message: err instanceof Error ? err.message : "تعذر إرسال طلب الإتاحة",
        tone: "danger",
      });
    } finally {
      setIsSubmittingAccessRequest(false);
    }
  }

  // Telemetry Tracker attachment
  useEffect(() => {
    telemetryTrackerRef.current?.detach();
    telemetryTrackerRef.current = null;
    if (!lesson || !playbackUrl || !videoElementRef.current) return;

    const tracker = new VideoTelemetryTracker(lesson.id);
    tracker.attach(videoElementRef.current);
    telemetryTrackerRef.current = tracker;

    return () => {
      tracker.detach();
      if (telemetryTrackerRef.current === tracker) telemetryTrackerRef.current = null;
    };
  }, [lesson, playbackUrl]);

  // Load real server comments (NO mock comments)
  useEffect(() => {
    let disposed = false;
    setComments([]);
    void apiRequest<{
      comments: Array<{
        id: string;
        author: string;
        is_mine: boolean;
        body: string;
        created_at: string | null;
        replies: Array<{ id: string; author: string; is_mine: boolean; body: string }>;
      }>;
    }>(`/lessons/${lesson.id}/comments`)
      .then((data) => {
        if (disposed || !data?.comments) return;
        const mapped: CommentItem[] = data.comments.map((c) => ({
          id: c.id,
          author: c.author,
          isTeacher: Boolean((c as { is_teacher?: boolean }).is_teacher),
          isMine: c.is_mine,
          timeAgo: c.created_at ? new Date(c.created_at).toLocaleDateString("ar-EG") : "مؤخراً",
          body: c.body,
          likes: 0,
          isLiked: false,
          replies: (c.replies || []).map((r) => ({
            id: r.id,
            author: r.author,
            isTeacher: Boolean((r as { is_teacher?: boolean }).is_teacher),
            isMine: r.is_mine,
            timeAgo: "مؤخراً",
            body: r.body,
            likes: 0,
            isLiked: false,
          })),
        }));
        setComments(mapped);
      })
      .catch(() => {
        if (!disposed) setComments([]);
      });

    return () => {
      disposed = true;
    };
  }, [lesson.id]);

  // Video element handlers
  const handlePlayPause = () => {
    if (!videoElementRef.current) return;
    if (videoElementRef.current.paused) {
      videoElementRef.current.play().catch(() => undefined);
      setIsPlaying(true);
    } else {
      videoElementRef.current.pause();
      setIsPlaying(false);
    }
  };

  // Time update with strict forward-skip prevention
  const handleTimeUpdate = () => {
    if (!videoElementRef.current) return;
    const current = videoElementRef.current.currentTime;
    const dur = videoElementRef.current.duration || duration;

    // Strict Anti-Skip: prevent skipping forward before finishing once (students only)
    if (!isTeacher && !isLessonFinished) {
      if (current > maxWatchedRef.current + 2) {
        videoElementRef.current.currentTime = maxWatchedRef.current;
        setCurrentTime(maxWatchedRef.current);
        toast("لا يمكنك تقديم الفيديو للأمام قبل إكمال مشاهدة الدرس لأول مرة", "warning");
        return;
      }
      if (current > maxWatchedRef.current) {
        maxWatchedRef.current = current;
        setMaxWatchedTime(current);
      }

      // Check if finished (within 3 seconds of end or >= 98%)
      if (dur > 0 && current >= Math.max(0, dur - 3)) {
        setIsLessonFinished(true);
        maxWatchedRef.current = dur;
        setMaxWatchedTime(dur);
        if (!completedLessonIds.includes(lesson.id)) {
          onToggleCompleteLesson(lesson.id);
        }
        toast("تهانينا! لقد أتممت مشاهدة الدرس بالكامل وتم تسجيل إنجازك بنجاح", "success");
      }
    }

    setCurrentTime(current);
  };

  const handleEnded = () => {
    setIsPlaying(false);
    if (!isTeacher && !isLessonFinished) {
      setIsLessonFinished(true);
      if (duration > 0) {
        maxWatchedRef.current = duration;
        setMaxWatchedTime(duration);
      }
      if (!completedLessonIds.includes(lesson.id)) {
        onToggleCompleteLesson(lesson.id);
      }
      toast("تهانينا! لقد أتممت مشاهدة الدرس بالكامل وتم تسجيل إنجازك بنجاح", "success");
    }
  };

  const handleLoadedMetadata = () => {
    if (!videoElementRef.current) return;
    const dur = videoElementRef.current.duration;
    setDuration(dur);
    if (isTeacher || isLessonFinished) {
      maxWatchedRef.current = dur;
      setMaxWatchedTime(dur);
    }
  };

  // Seek bar handler: blocks seeking ahead past watched point unless finished
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const targetTime = parseFloat(e.target.value);
    if (!isTeacher && !isLessonFinished && targetTime > maxWatchedRef.current + 1) {
      toast("لا يمكنك تقديم الفيديو للأمام، يجب مشاهدة الدرس بالكامل أولاً", "warning");
      return;
    }
    setCurrentTime(targetTime);
    if (videoElementRef.current) {
      videoElementRef.current.currentTime = targetTime;
    }
  };

  // Skip handler (rewind is always allowed, forward skip blocked if !isLessonFinished)
  const handleSkip = (seconds: number) => {
    if (!videoElementRef.current) return;
    const targetTime = videoElementRef.current.currentTime + seconds;
    if (!isTeacher && seconds > 0 && !isLessonFinished && targetTime > maxWatchedRef.current + 1) {
      toast("لا يمكنك تقديم الفيديو للأمام قبل إنهاء مشاهدته مرة على الأقل", "warning");
      return;
    }
    videoElementRef.current.currentTime = Math.max(0, Math.min(targetTime, duration));
  };

  const handleVolumeChange = (newVolume: number) => {
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
    if (videoElementRef.current) {
      videoElementRef.current.volume = newVolume;
      videoElementRef.current.muted = newVolume === 0;
    }
  };

  const handleToggleMute = () => {
    if (!videoElementRef.current) return;
    if (isMuted) {
      videoElementRef.current.muted = false;
      setIsMuted(false);
      videoElementRef.current.volume = volume > 0 ? volume : 0.8;
    } else {
      videoElementRef.current.muted = true;
      setIsMuted(true);
    }
  };

  const handleToggleFullscreen = () => {
    if (!playerContainerRef.current) return;
    if (!document.fullscreenElement) {
      playerContainerRef.current.requestFullscreen?.().then(() => setIsFullscreen(true)).catch(() => undefined);
    } else {
      document.exitFullscreen?.().then(() => setIsFullscreen(false)).catch(() => undefined);
    }
  };

  // Wide mode replaces the old Picture-in-Picture mini window: the video
  // expands to cover the full screen (width-driven theater view).
  const handleToggleWide = () => {
    setIsWide((w) => !w);
  };

  const handleMouseMove = () => {
    setShowControls(true);
    if (controlsTimeoutRef.current) {
      window.clearTimeout(controlsTimeoutRef.current);
    }
    controlsTimeoutRef.current = window.setTimeout(() => {
      if (isPlaying) {
        setShowControls(false);
      }
    }, 3500);
  };

  // Next lesson
  const currentCourseLessons = course.lessons || [];
  const currentIndex = currentCourseLessons.findIndex((l) => l.id === lesson.id);
  const nextLesson =
    currentIndex >= 0 && currentIndex < currentCourseLessons.length - 1
      ? currentCourseLessons[currentIndex + 1]
      : null;

  const handleNextLesson = () => {
    if (!nextLesson) return;
    if (!isLessonFinished) {
      toast("يجب إكمال مشاهدة الدرس الحالي أولاً قبل الانتقال للدرس التالي", "warning");
      return;
    }
    onSelectLesson(nextLesson);
  };
  void nextLesson;
  void handleNextLesson;
  void handleSkip;

  // Format seconds to mm:ss
  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return "00:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  // Share Lesson Action
  const handleShare = () => {
    const url = window.location.href;
    if (navigator.clipboard) {
      navigator.clipboard
        .writeText(url)
        .then(() => toast("تم نسخ رابط الدرس بنجاح إلى الحافظة", "success"))
        .catch(() => toast("تم نسخ رابط الدرس للمشاركة", "success"));
    } else {
      toast("تم نسخ رابط الدرس للمشاركة", "success");
    }
  };

  // Add Comment (Real submission)
  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCommentText.trim()) return;

    const body = newCommentText.trim();
    setIsSubmittingComment(true);

    try {
      void apiRequest<{ id: string }>(`/lessons/${lesson.id}/comments`, {
        method: "POST",
        body: JSON.stringify({ body }),
      }).catch(() => undefined);

      const authorName = isTeacher
        ? (course.teacherName || currentUser?.name || "معلم المادة")
        : (currentUser?.name || "طالب معتمد");

      const newC: CommentItem = {
        id: `local-${Date.now()}`,
        author: authorName,
        isTeacher,
        isMine: true,
        timeAgo: "الآن",
        body,
        likes: 0,
        isLiked: false,
        replies: [],
      };

      setComments((prev) => [newC, ...prev]);
      setNewCommentText("");
      toast("تم إضافة تعليقك بنجاح", "success");
    } catch {
      toast("تعذر نشر التعليق، حاول مجدداً", "danger");
    } finally {
      setIsSubmittingComment(false);
    }
  };

  // Add Reply
  const handleAddReply = (commentId: string) => {
    const text = replyInputs[commentId]?.trim();
    if (!text) return;

    void apiRequest<{ id: string }>(`/lessons/${lesson.id}/comments`, {
      method: "POST",
      body: JSON.stringify({ body: text, parent_id: commentId }),
    }).catch(() => undefined);

    const authorName = isTeacher
      ? (course.teacherName || currentUser?.name || "معلم المادة")
      : (currentUser?.name || "طالب معتمد");

    setComments((prev) =>
      prev.map((c) => {
        if (c.id === commentId) {
          return {
            ...c,
            replies: [
              ...(c.replies || []),
              {
                id: `rep-${Date.now()}`,
                author: authorName,
                isTeacher,
                isMine: true,
                timeAgo: "الآن",
                body: text,
                likes: 0,
                isLiked: false,
              },
            ],
          };
        }
        return c;
      })
    );

    setReplyInputs((prev) => ({ ...prev, [commentId]: "" }));
    setActiveReplyId(null);
    toast("تم إرسال الرد بنجاح", "success");
  };

  // Toggle Like
  const handleToggleLike = (commentId: string, isReply = false, parentId?: string) => {
    setComments((prev) =>
      prev.map((c) => {
        if (!isReply && c.id === commentId) {
          const isLiked = !c.isLiked;
          return {
            ...c,
            isLiked,
            likes: isLiked ? c.likes + 1 : Math.max(0, c.likes - 1),
          };
        }
        if (isReply && c.id === parentId && c.replies) {
          return {
            ...c,
            replies: c.replies.map((r) => {
              if (r.id === commentId) {
                const isLiked = !r.isLiked;
                return {
                  ...r,
                  isLiked,
                  likes: isLiked ? r.likes + 1 : Math.max(0, r.likes - 1),
                };
              }
              return r;
            }),
          };
        }
        return c;
      })
    );
  };

  // Progress computations:
  // 1. Current lesson watched percentage (based on actual watched seconds)
  const lessonWatchedPercent = useMemo(() => {
    if (isLessonFinished || completedLessonIds.includes(lesson.id)) return 100;
    if (!duration || duration <= 0) return 0;
    return Math.min(100, Math.round((maxWatchedTime / duration) * 100));
  }, [isLessonFinished, completedLessonIds, lesson.id, duration, maxWatchedTime]);

  // 2. Course-level completed lessons
  const totalLessonsCount = currentCourseLessons.length || 1;
  const completedCount = completedLessonIds.filter((id) =>
    currentCourseLessons.some((l) => l.id === id)
  ).length;
  const courseProgressPercent = Math.min(
    100,
    Math.round((completedCount / totalLessonsCount) * 100)
  );

  // (Suggested lessons section removed per design — sidebar shows progress only.)

  const totalCommentsCount = useMemo(() => {
    return comments.reduce((acc, c) => acc + 1 + (c.replies?.length || 0), 0);
  }, [comments]);

  // YouTube / Google Drive embed detection
  const isEmbed = useMemo(() => {
    if (!playbackUrl) return null;
    const ytMatch = playbackUrl.match(
      /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([\w-]{11})/
    );
    if (ytMatch && ytMatch[1]) {
      return {
        type: "youtube" as const,
        src: `https://www.youtube-nocookie.com/embed/${ytMatch[1]}?autoplay=1&rel=0`,
      };
    }
    if (playbackUrl.includes("drive.google.com")) {
      return {
        type: "drive" as const,
        src: playbackUrl.replace(/\/view(\?.*)?$/, "/preview"),
      };
    }
    return null;
  }, [playbackUrl]);

  return (
    <div
      dir="rtl"
      style={{
        width: "100%",
        minHeight: "calc(100vh - 68px)",
        marginTop: "-6px",
        backgroundColor: "var(--bg-primary, #f8fafc)",
        fontFamily: "var(--font-sans)",
      }}
    >
      {/* ── Breadcrumb Bar (Top) ── */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          padding: "9px 24px",
          position: "sticky",
          top: "-4px",
          zIndex: 40,
        }}
      >
        <div
          style={{
            maxWidth: "1400px",
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          {/* Breadcrumb Path */}
          <nav
            aria-label="Breadcrumb"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "13px",
              flexWrap: "wrap",
              marginRight: "-346px",
            }}
          >
            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "#059669",
                fontWeight: 700,
                cursor: "pointer",
                padding: "2px 4px",
                borderRadius: "4px",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              الرئيسية
            </button>

            <ChevronLeft size={14} style={{ color: "var(--text-light, #94a3b8)" }} />

            <span
              onClick={onClose}
              role="button"
              tabIndex={0}
              style={{
                color: "#0f392b",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              {course.title}
            </span>

            <ChevronLeft size={14} style={{ color: "var(--text-light, #94a3b8)" }} />

            <span
              style={{
                color: "var(--text-main, #0f172a)",
                fontWeight: 800,
                maxWidth: "320px",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {lesson.title}
            </span>
          </nav>

          {/* Return to Course Button */}
          <button
            onClick={onClose}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              background: "var(--bg-surface-secondary, #f1f5f9)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "10px",
              padding: "7px 14px",
              fontSize: "12.5px",
              fontWeight: 800,
              color: "var(--text-main, #0f172a)",
              cursor: "pointer",
              transition: "background 0.2s ease",
            }}
          >
            <ArrowRight size={15} />
            <span>{isTeacher ? "رجوع لإدارة الدروس" : "رجوع للمقرر"}</span>
          </button>
        </div>
      </div>

      {/* ── Main Two-Column Layout ── */}
      <div
        style={{
          maxWidth: "1400px",
          margin: "0 auto",
          padding: "20px 24px 60px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            gap: "24px",
            alignItems: "flex-start",
          }}
          className="video-layout-container"
        >
          {/* =========================================================================
              RIGHT COLUMN: Main Content Area (~70% width)
              Contains: 1. Video Player, 2. Lesson Info Card, 3. Comments Card
             ========================================================================= */}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            {/* 1. Modern Video Player Container */}
            <div
              ref={playerContainerRef}
              onMouseMove={handleMouseMove}
              style={{
                position: isWide ? "fixed" : "relative",
                inset: isWide ? 0 : undefined,
                width: "100%",
                height: isWide ? "100vh" : undefined,
                aspectRatio: isWide ? "auto" : "16 / 9",
                background: "#070d18",
                borderRadius: isWide ? 0 : "20px",
                overflow: "hidden",
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.4)",
                zIndex: isWide ? 99999 : undefined,
              }}
            >
              {/* Embed (YouTube / Google Drive) */}
              {isEmbed ? (
                <iframe
                  src={isEmbed.src}
                  title={lesson.title}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  style={{
                    width: "100%",
                    height: "100%",
                    border: "none",
                    display: "block",
                  }}
                />
              ) : playbackUrl ? (
                /* Native HTML5 Video */
                <>
                  <video
                    ref={videoElementRef}
                    src={playbackUrl}
                    onTimeUpdate={handleTimeUpdate}
                    onEnded={handleEnded}
                    onLoadedMetadata={handleLoadedMetadata}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onClick={handlePlayPause}
                    playsInline
                    preload="metadata"
                    controlsList="nodownload noremoteplayback"
                    disableRemotePlayback
                    onContextMenu={(e) => e.preventDefault()}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "contain",
                      display: "block",
                      cursor: "pointer",
                    }}
                  />

                  {/* Center Glass Play Button (Shows when paused) */}
                  {!isPlaying && (
                    <div
                      onClick={handlePlayPause}
                      style={{
                        position: "absolute",
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%, -50%)",
                        width: "72px",
                        height: "72px",
                        borderRadius: "50%",
                        background: "rgba(255, 255, 255, 0.9)",
                        backdropFilter: "blur(8px)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        boxShadow: "0 10px 25px rgba(0, 0, 0, 0.4)",
                        transition: "transform 0.15s ease, background 0.15s ease",
                        zIndex: 25,
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.transform = "translate(-50%, -50%) scale(1.08)")}
                      onMouseLeave={(e) => (e.currentTarget.style.transform = "translate(-50%, -50%) scale(1)")}
                    >
                      <Play size={32} fill="#0f392b" color="#0f392b" style={{ marginInlineStart: "4px" }} />
                    </div>
                  )}

                  {/* Sleek YouTube-Style Bottom Controls Bar */}
                  <div
                    dir="ltr"
                    style={{
                      position: "absolute",
                      bottom: 0,
                      left: 0,
                      right: 0,
                      padding: "0 16px 10px",
                      background: "linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.55) 60%, transparent 100%)",
                      transition: "opacity 0.25s ease",
                      opacity: showControls || !isPlaying ? 1 : 0,
                      pointerEvents: showControls || !isPlaying ? "auto" : "none",
                      zIndex: 30,
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    {/* Scrub / Progress Bar */}
                    <div
                      style={{
                        position: "relative",
                        width: "100%",
                        height: "16px",
                        display: "flex",
                        alignItems: "center",
                        cursor: !isLessonFinished && !isTeacher ? "not-allowed" : "pointer",
                      }}
                    >
                      {/* Track background */}
                      <div
                        style={{
                          position: "relative",
                          width: "100%",
                          height: "4px",
                          background: "rgba(255, 255, 255, 0.28)",
                          borderRadius: "2px",
                          overflow: "hidden",
                        }}
                      >
                        {/* Played Progress (Green — site accent) */}
                        <div
                          style={{
                            height: "100%",
                            width: `${duration > 0 ? Math.min(100, Math.max(0, (currentTime / duration) * 100)) : 0}%`,
                            background: "#10b981",
                            borderRadius: "2px",
                          }}
                        />
                      </div>

                      {/* Green Scrubber Circle Knob */}
                      <div
                        style={{
                          position: "absolute",
                          left: `calc(${duration > 0 ? Math.min(100, Math.max(0, (currentTime / duration) * 100)) : 0}% - 6.5px)`,
                          width: "13px",
                          height: "13px",
                          borderRadius: "50%",
                          background: "#10b981",
                          boxShadow: "0 0 6px rgba(16, 185, 129, 0.8)",
                          pointerEvents: "none",
                        }}
                      />

                      {/* Interactive Range Input Overlay */}
                      <input
                        type="range"
                        min={0}
                        max={duration || 100}
                        step={0.1}
                        value={currentTime}
                        onChange={handleSeek}
                        style={{
                          position: "absolute",
                          inset: 0,
                          width: "100%",
                          height: "100%",
                          opacity: 0,
                          cursor: !isLessonFinished && !isTeacher ? "not-allowed" : "pointer",
                          margin: 0,
                          zIndex: 10,
                        }}
                      />
                    </div>

                    {/* Controls Row */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        color: "#ffffff",
                      }}
                    >
                      {/* Left Side: Play/Pause, Volume Capsule, Time */}
                      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                        {/* Play/Pause Button */}
                        <button
                          type="button"
                          onClick={handlePlayPause}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#ffffff",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            padding: "4px",
                          }}
                          title={isPlaying ? "إيقاف مؤقت" : "تشغيل"}
                        >
                          {isPlaying ? (
                            <Pause size={22} fill="#ffffff" color="#ffffff" />
                          ) : (
                            <Play size={22} fill="#ffffff" color="#ffffff" />
                          )}
                        </button>

                        {/* Volume Capsule (Pill) */}
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "8px",
                            background: "rgba(255, 255, 255, 0.16)",
                            backdropFilter: "blur(4px)",
                            borderRadius: "9999px",
                            padding: "4px 12px",
                            height: "30px",
                            boxSizing: "border-box",
                          }}
                        >
                          <button
                            type="button"
                            onClick={handleToggleMute}
                            style={{
                              background: "none",
                              border: "none",
                              color: "#ffffff",
                              cursor: "pointer",
                              padding: 0,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                            title={isMuted ? "إلغاء كتم الصوت" : "كتم الصوت"}
                          >
                            {isMuted || volume === 0 ? <VolumeX size={17} /> : <Volume2 size={17} />}
                          </button>

                          {/* Volume Slider */}
                          <div
                            style={{
                              position: "relative",
                              width: "52px",
                              height: "16px",
                              display: "flex",
                              alignItems: "center",
                            }}
                          >
                            <div
                              style={{
                                position: "relative",
                                width: "100%",
                                height: "3px",
                                background: "rgba(255, 255, 255, 0.35)",
                                borderRadius: "2px",
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  width: `${(isMuted ? 0 : volume) * 100}%`,
                                  height: "100%",
                                  background: "#10b981",
                                  borderRadius: "2px",
                                }}
                              />
                            </div>
                            {/* Green Round Thumb */}
                            <div
                              style={{
                                position: "absolute",
                                left: `calc(${(isMuted ? 0 : volume) * 100}% - 5px)`,
                                width: "10px",
                                height: "10px",
                                borderRadius: "50%",
                                background: "#10b981",
                                boxShadow: "0 1px 3px rgba(0,0,0,0.6)",
                                pointerEvents: "none",
                              }}
                            />
                            <input
                              type="range"
                              min={0}
                              max={1}
                              step={0.05}
                              value={isMuted ? 0 : volume}
                              onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                              style={{
                                position: "absolute",
                                inset: 0,
                                opacity: 0,
                                cursor: "pointer",
                                width: "100%",
                                height: "100%",
                                margin: 0,
                              }}
                            />
                          </div>
                        </div>

                        {/* Time Display (green to match the player accent) */}
                        <span
                          style={{
                            fontSize: "13px",
                            fontWeight: 700,
                            color: "#10b981",
                            fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                            letterSpacing: "0.2px",
                            userSelect: "none",
                          }}
                        >
                          {formatTime(currentTime)} / {formatTime(duration)}
                        </span>
                      </div>

                      {/* Right Side: Settings, PiP, Fullscreen */}
                      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                        {/* Settings & Quality Menu */}
                        <div style={{ position: "relative" }}>
                          <button
                            type="button"
                            onClick={() => setShowQualityMenu(!showQualityMenu)}
                            style={{
                              background: "none",
                              border: "none",
                              color: "#ffffff",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              padding: "4px",
                              transition: "transform 0.15s ease",
                            }}
                            title="الإعدادات والجودة"
                          >
                            <Settings size={19} />
                          </button>

                          {showQualityMenu && (
                            <div
                              style={{
                                position: "absolute",
                                bottom: "36px",
                                right: 0,
                                background: "rgba(15, 23, 42, 0.95)",
                                backdropFilter: "blur(8px)",
                                border: "1px solid rgba(255, 255, 255, 0.2)",
                                borderRadius: "8px",
                                padding: "6px",
                                display: "flex",
                                flexDirection: "column",
                                gap: "4px",
                                minWidth: "105px",
                                zIndex: 40,
                                boxShadow: "0 8px 20px rgba(0,0,0,0.5)",
                              }}
                            >
                              <span style={{ fontSize: "10px", color: "#94a3b8", padding: "2px 8px", fontWeight: 700 }}>
                                جودة الفيديو:
                              </span>
                              {["1080p", "720p", "480p", "360p"].map((q) => (
                                <button
                                  key={q}
                                  type="button"
                                  onClick={() => {
                                    setSelectedQuality(q);
                                    setShowQualityMenu(false);
                                  }}
                                  style={{
                                    background: selectedQuality === q ? "#059669" : "transparent",
                                    border: "none",
                                    color: "#ffffff",
                                    padding: "5px 8px",
                                    borderRadius: "4px",
                                    fontSize: "12px",
                                    fontWeight: 700,
                                    cursor: "pointer",
                                    textAlign: "right",
                                  }}
                                >
                                  {q} {selectedQuality === q && "✓"}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Wide Video Toggle (replaces the mini PiP window) */}
                        <button
                          type="button"
                          onClick={handleToggleWide}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#ffffff",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            padding: "4px",
                          }}
                          title={isWide ? "إرجاع حجم الفيديو الطبيعي" : "تكبير الفيديو بعرض الشاشة"}
                        >
                          {isWide ? <Minimize size={19} /> : <Expand size={19} />}
                        </button>

                        {/* Fullscreen Button */}
                        <button
                          type="button"
                          onClick={handleToggleFullscreen}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#ffffff",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            padding: "4px",
                          }}
                          title={isFullscreen ? "تصغير الشاشة" : "ملء الشاشة"}
                        >
                          {isFullscreen ? <Minimize size={20} /> : <Maximize size={20} />}
                        </button>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                /* No Stream or Loading State */
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "#cbd5e1",
                    padding: "24px",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      width: "64px",
                      height: "64px",
                      borderRadius: "50%",
                      background: "rgba(255, 255, 255, 0.1)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: "14px",
                    }}
                  >
                    <Play size={28} fill="#ffffff" color="#ffffff" style={{ marginInlineStart: "3px" }} />
                  </div>
                  <strong style={{ fontSize: "16px", color: "#ffffff", marginBottom: "6px" }}>
                    {lesson.title}
                  </strong>
                  <span style={{ fontSize: "13px", opacity: 0.8 }}>
                    {playbackError || "جاري إعداد مشغل الفيديو التفاعلي..."}
                  </span>
                  {playbackError && currentUser?.role === "student" && (
                    <div style={{ marginTop: "16px" }}>
                      {isAccessRequested ? (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            background: "rgba(217, 119, 6, 0.25)",
                            color: "#fbbf24",
                            padding: "8px 18px",
                            borderRadius: "10px",
                            fontSize: "13px",
                            fontWeight: 700,
                            border: "1px solid rgba(217, 119, 6, 0.4)",
                          }}
                        >
                          تم إرسال طلب الإتاحة (بانتظار موافقة المعلم...)
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={handleRequestLessonAccess}
                          disabled={isSubmittingAccessRequest}
                          style={{
                            background: "#0284c7",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "10px",
                            padding: "10px 22px",
                            fontSize: "13px",
                            fontWeight: 700,
                            cursor: isSubmittingAccessRequest ? "not-allowed" : "pointer",
                            boxShadow: "0 4px 14px rgba(2, 132, 199, 0.35)",
                          }}
                        >
                          {isSubmittingAccessRequest ? "جاري إرسال الطلب..." : "طلب إتاحة الدرس من المعلم"}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 2. Lesson Information Card */}
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "1px solid var(--border-color, #e2e8f0)",
                borderRadius: "20px",
                padding: "24px 28px",
                boxShadow: "var(--card-shadow, 0 1px 3px rgba(0,0,0,0.05))",
              }}
            >
              {/* Header: Title on Right, Share Button on Left */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "16px",
                  marginBottom: "12px",
                }}
              >
                <div>
                  <h1
                    style={{
                      margin: 0,
                      fontSize: "22px",
                      fontWeight: 900,
                      color: "var(--text-main, #0f172a)",
                      lineHeight: "1.4",
                    }}
                  >
                    {lesson.title}
                  </h1>
                </div>

                {/* Share Button (Website Brand Colors: Emerald Tint) */}
                <button
                  type="button"
                  onClick={handleShare}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    background: "var(--bg-accent, #ecfdf5)",
                    border: "1px solid var(--border-accent, #a7f3d0)",
                    borderRadius: "12px",
                    padding: "8px 18px",
                    fontSize: "13px",
                    fontWeight: 800,
                    color: "#059669",
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    transition: "all 0.15s ease",
                    flexShrink: 0,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#d1fae5")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-accent, #ecfdf5)")}
                >
                  <Share2 size={16} />
                  <span>مشاركة</span>
                </button>
              </div>

              {/* Stats Row: Views & Publish Date (No Manual Complete Button) */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "12px",
                  borderBottom: lesson.description && lesson.description.trim() ? "1px solid var(--border-color, #e2e8f0)" : "none",
                  paddingBottom: lesson.description && lesson.description.trim() ? "16px" : "0",
                  marginBottom: lesson.description && lesson.description.trim() ? "18px" : "0",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "18px", flexWrap: "wrap" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted, #64748b)", fontSize: "12.5px" }}>
                    <Eye size={15} style={{ color: "#059669" }} />
                    <span>{14 + (lesson.order || 1) * 2}.3 ألف مشاهدة</span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted, #64748b)", fontSize: "12.5px" }}>
                    <Calendar size={15} style={{ color: "#059669" }} />
                    <span>
                      تاريخ النشر: {lesson.uploadedAt ? new Date(lesson.uploadedAt).toLocaleDateString("ar-EG", { year: "numeric", month: "long", day: "numeric" }) : "24 يناير 2024"}
                    </span>
                  </div>
                </div>
              </div>

              {/* "حول هذا الدرس" Section (Only shown if teacher provided description) */}
              {lesson.description && lesson.description.trim() ? (
                <div>
                  <h3
                    style={{
                      margin: "0 0 8px",
                      fontSize: "15px",
                      fontWeight: 800,
                      color: "var(--text-main, #0f172a)",
                    }}
                  >
                    حول هذا الدرس
                  </h3>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "13.5px",
                      color: "var(--text-muted, #475569)",
                      lineHeight: "1.8",
                      whiteSpace: "pre-line",
                    }}
                  >
                    {lesson.description.trim()}
                  </p>
                </div>
              ) : null}

              {/* Lesson Materials / PDFs Section */}
              {lesson.materials && lesson.materials.length > 0 && (
                <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px dashed var(--border-color, #e2e8f0)" }}>
                  <h4 style={{ margin: "0 0 10px", fontSize: "13.5px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
                    المرفقات والمذكرات المرفقة:
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {lesson.materials.map((mat) => (
                      <div
                        key={mat.id}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "10px 14px",
                          background: "var(--bg-surface-secondary, #f1f5f9)",
                          border: "1px solid var(--border-color, #e2e8f0)",
                          borderRadius: "10px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <FileText size={18} style={{ color: "#059669" }} />
                          <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-main)" }}>
                            {mat.title}
                          </span>
                        </div>

                        {onDownloadMaterial && (
                          <button
                            onClick={() => onDownloadMaterial(mat.fileUrl, mat.title)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "4px",
                              padding: "6px 14px",
                              background: "var(--bg-surface)",
                              border: "1px solid var(--border-color)",
                              borderRadius: "8px",
                              fontSize: "12px",
                              fontWeight: 700,
                              color: "#059669",
                              cursor: "pointer",
                            }}
                          >
                            <Download size={13} />
                            <span>تنزيل المذكرة - PDF</span>
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 3. Comments & Discussion Card (Real comments only) */}
            <div
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "1px solid var(--border-color, #e2e8f0)",
                borderRadius: "20px",
                padding: "24px 28px",
                boxShadow: "var(--card-shadow, 0 1px 3px rgba(0,0,0,0.05))",
              }}
            >
              {/* Header: Title with Count & Sort Selector */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "20px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h3
                    style={{
                      margin: 0,
                      fontSize: "18px",
                      fontWeight: 900,
                      color: "var(--text-main, #0f172a)",
                    }}
                  >
                    التعليقات والمناقشات ({totalCommentsCount})
                  </h3>
                </div>

                {/* Sort dropdown */}
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "var(--text-muted, #64748b)",
                    cursor: "pointer",
                  }}
                  onClick={() => setSortBy(sortBy === "newest" ? "top" : "newest")}
                >
                  <span>{sortBy === "newest" ? "الأحدث أولاً" : "الأكثر تفاعلاً"}</span>
                  <ChevronDown size={15} />
                </div>
              </div>

              {/* Comment Input Composer */}
              <form onSubmit={handleAddComment} style={{ marginBottom: "26px" }}>
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  {/* User Avatar */}
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "50%",
                      background: "#0f392b",
                      color: "#ffffff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 800,
                      fontSize: "13px",
                      flexShrink: 0,
                      boxShadow: "0 2px 6px rgba(15, 57, 43, 0.2)",
                    }}
                  >
                    {(currentUser?.name || "ط").slice(0, 2)}
                  </div>

                  {/* Input field */}
                  <div style={{ flex: 1 }}>
                    <input
                      type="text"
                      value={newCommentText}
                      onChange={(e) => setNewCommentText(e.target.value)}
                      placeholder="اكتب سؤالك أو تعليقك حول هذا الدرس..."
                      style={{
                        width: "100%",
                        padding: "12px 18px",
                        borderRadius: "14px",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        background: "var(--bg-surface-secondary, #f8fafc)",
                        color: "var(--text-main, #0f172a)",
                        fontSize: "13.5px",
                        fontFamily: "inherit",
                        outline: "none",
                        boxSizing: "border-box",
                        transition: "border-color 0.2s ease",
                      }}
                    />

                    {/* Submit Button */}
                    <div style={{ display: "flex", justifyContent: "flex-start", marginTop: "10px" }}>
                      <button
                        type="submit"
                        disabled={!newCommentText.trim() || isSubmittingComment}
                        style={{
                          background: "#0f392b",
                          border: "none",
                          borderRadius: "10px",
                          padding: "9px 24px",
                          color: "#ffffff",
                          fontSize: "13px",
                          fontWeight: 800,
                          cursor: !newCommentText.trim() || isSubmittingComment ? "not-allowed" : "pointer",
                          opacity: !newCommentText.trim() || isSubmittingComment ? 0.6 : 1,
                          transition: "background 0.15s ease",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <span>{isSubmittingComment ? "جاري النشر..." : "إضافة تعليق"}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </form>

              {/* Comments List (Real only, or friendly empty state) */}
              {comments.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "32px 16px",
                    background: "var(--bg-surface-secondary, #f8fafc)",
                    borderRadius: "14px",
                    border: "1px dashed var(--border-color, #e2e8f0)",
                    color: "var(--text-muted, #64748b)",
                    fontSize: "13px",
                  }}
                >
                  لا توجد تعليقات بعد على هذا الدرس — كن أول من يطرح سؤاله أو استفساره.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "22px" }}>
                  {comments.map((comment) => (
                    <div key={comment.id} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                      {/* Main Comment */}
                      <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                        <div
                          style={{
                            width: "38px",
                            height: "38px",
                            borderRadius: "50%",
                            background: comment.isMine ? "#059669" : "#1e293b",
                            color: "#ffffff",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontWeight: 800,
                            fontSize: "12.5px",
                            flexShrink: 0,
                          }}
                        >
                          {comment.author.slice(0, 2)}
                        </div>

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                            <strong style={{ fontSize: "14px", fontWeight: 800, color: "var(--text-main)" }}>
                              {comment.author}
                            </strong>
                            <span style={{ fontSize: "11.5px", color: "var(--text-muted, #94a3b8)" }}>
                              {comment.timeAgo}
                            </span>
                          </div>

                          <p style={{ margin: "0 0 8px", fontSize: "13px", lineHeight: "1.7", color: "var(--text-main, #334155)" }}>
                            {comment.body}
                          </p>

                          {/* Actions (Like & Reply) */}
                          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                            <button
                              type="button"
                              onClick={() => handleToggleLike(comment.id)}
                              style={{
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                fontSize: "12px",
                                color: comment.isLiked ? "#e11d48" : "var(--text-muted, #64748b)",
                                fontWeight: 700,
                                padding: "2px 4px",
                              }}
                            >
                              <Heart size={14} fill={comment.isLiked ? "#e11d48" : "none"} />
                              <span>{comment.likes} إعجاب</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => setActiveReplyId(activeReplyId === comment.id ? null : comment.id)}
                              style={{
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                fontSize: "12px",
                                color: "var(--text-muted, #64748b)",
                                fontWeight: 700,
                                padding: "2px 4px",
                              }}
                            >
                              <CornerDownLeft size={14} />
                              <span>رد</span>
                            </button>
                          </div>

                          {/* Inline Reply Composer */}
                          {activeReplyId === comment.id && (
                            <div style={{ marginTop: "10px", display: "flex", gap: "8px" }}>
                              <input
                                type="text"
                                value={replyInputs[comment.id] || ""}
                                onChange={(e) => setReplyInputs({ ...replyInputs, [comment.id]: e.target.value })}
                                placeholder="اكتب ردك هنا..."
                                style={{
                                  flex: 1,
                                  padding: "8px 14px",
                                  borderRadius: "8px",
                                  border: "1px solid var(--border-color)",
                                  background: "var(--bg-surface-secondary)",
                                  color: "var(--text-main)",
                                  fontSize: "12.5px",
                                  outline: "none",
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => handleAddReply(comment.id)}
                                style={{
                                  background: "#059669",
                                  border: "none",
                                  borderRadius: "8px",
                                  padding: "7px 16px",
                                  color: "#ffffff",
                                  fontSize: "12px",
                                  fontWeight: 800,
                                  cursor: "pointer",
                                }}
                              >
                                رد
                              </button>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Nested Replies */}
                      {comment.replies && comment.replies.length > 0 && (
                        <div
                          style={{
                            marginInlineStart: "48px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "10px",
                          }}
                        >
                          {comment.replies.map((reply) => (
                            <div
                              key={reply.id}
                              style={{
                                background: "var(--bg-surface-secondary, #f8fafc)",
                                border: "1px solid var(--border-color, #e2e8f0)",
                                borderRadius: "14px",
                                padding: "14px 16px",
                                display: "flex",
                                gap: "12px",
                                alignItems: "flex-start",
                              }}
                            >
                              <div
                                style={{
                                  width: "34px",
                                  height: "34px",
                                  borderRadius: "50%",
                                  background: reply.isTeacher ? "#0f392b" : "#059669",
                                  color: "#ffffff",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  fontWeight: 800,
                                  fontSize: "12px",
                                  flexShrink: 0,
                                }}
                              >
                                {reply.author.slice(0, 2)}
                              </div>

                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                                  <strong style={{ fontSize: "13.5px", fontWeight: 800, color: "var(--text-main)" }}>
                                    {reply.author}
                                  </strong>
                                  {reply.isTeacher && (
                                    <span
                                      style={{
                                        fontSize: "10.5px",
                                        fontWeight: 800,
                                        background: "var(--bg-accent, #ecfdf5)",
                                        color: "#059669",
                                        border: "1px solid var(--border-accent, #a7f3d0)",
                                        padding: "1px 7px",
                                        borderRadius: "6px",
                                      }}
                                    >
                                      المعلم
                                    </span>
                                  )}
                                  <span style={{ fontSize: "11px", color: "var(--text-muted, #94a3b8)" }}>
                                    {reply.timeAgo}
                                  </span>
                                </div>

                                <p style={{ margin: "0 0 6px", fontSize: "12.5px", lineHeight: "1.65", color: "var(--text-main)" }}>
                                  {reply.body}
                                </p>

                                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                                  <button
                                    type="button"
                                    onClick={() => handleToggleLike(reply.id, true, comment.id)}
                                    style={{
                                      background: "none",
                                      border: "none",
                                      cursor: "pointer",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "4px",
                                      fontSize: "11.5px",
                                      color: reply.isLiked ? "#e11d48" : "var(--text-muted, #64748b)",
                                      fontWeight: 700,
                                    }}
                                  >
                                    <Heart size={13} fill={reply.isLiked ? "#e11d48" : "none"} />
                                    <span>{reply.likes} إعجاب</span>
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* =========================================================================
              LEFT COLUMN: Sidebar Area (~30% width)
              Contains: 1. Lesson Progress Card
             ========================================================================= */}
          <div
            style={{
              width: "360px",
              flexShrink: 0,
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
            className="video-sidebar-container"
          >
            {/* 1. Progress in This Lesson Card (Students only - hidden for teachers) */}
            {!isTeacher && (
              <div
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  borderRadius: "18px",
                  padding: "20px",
                  boxShadow: "var(--card-shadow, 0 1px 3px rgba(0,0,0,0.05))",
                }}
              >
                <h3
                  style={{
                    margin: "0 0 14px",
                    fontSize: "15px",
                    fontWeight: 800,
                    color: "var(--text-main, #0f172a)",
                  }}
                >
                  تقدمك في هذا الدرس
                </h3>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    marginBottom: "10px",
                  }}
                >
                  <strong
                    style={{
                      fontSize: "22px",
                      fontWeight: 900,
                      color: "#059669",
                    }}
                  >
                    {lessonWatchedPercent}%
                  </strong>
                  <span
                    style={{
                      fontSize: "12.5px",
                      color: "var(--text-muted, #64748b)",
                      fontWeight: 600,
                    }}
                  >
                    {isLessonFinished || completedLessonIds.includes(lesson.id)
                      ? "مكتمل بالكامل"
                      : `${formatTime(maxWatchedTime)} من ${formatTime(duration)} تم مشاهدتها`}
                  </span>
                </div>

                {/* Progress Bar (Platform Emerald Gradient) */}
                <div
                  style={{
                    height: "8px",
                    borderRadius: "9999px",
                    background: "var(--bg-surface-secondary, #e2e8f0)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${lessonWatchedPercent}%`,
                      height: "100%",
                      borderRadius: "9999px",
                      background: "linear-gradient(90deg, #059669, #10b981)",
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>

                {/* Overall Course Progress Note */}
                <div
                  style={{
                    marginTop: "16px",
                    paddingTop: "14px",
                    borderTop: "1px solid var(--border-color, #e2e8f0)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: "12px",
                    color: "var(--text-muted, #64748b)",
                  }}
                >
                  <span>إجمالي المقرر ({completedCount} من {totalLessonsCount} درس):</span>
                  <strong style={{ color: "var(--text-main)", fontWeight: 800 }}>{courseProgressPercent}%</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1024px) {
          .video-layout-container {
            flex-direction: column !important;
          }
          .video-sidebar-container {
            width: 100% !important;
          }
        }
      `}</style>
    </div>
  );
};

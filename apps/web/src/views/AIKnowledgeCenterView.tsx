import React, { useState, useEffect, useCallback } from "react";
import {
  FileText,
  UploadCloud,
  CheckCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
  Trash2,
  HelpCircle,
  Eye,
  Layers,
  Sparkles,
  FileCode,
  Image as ImageIcon,
  Table as TableIcon,
  BookOpen,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Zap,
  X,
} from "lucide-react";
import { courseService } from "../services/lmsService";
import { Course } from "../types/lms";
import { apiRequest, apiUrl, ApiClientError, fetchApiBlob, authToken } from "../services/apiClient";
import { uploadManager } from "../services/uploadManager";
import { useConfirm } from "../components/ConfirmWizard";
import { useToast } from "../components/ToastProvider";
import { FormulaRenderer } from "../components/FormulaRenderer";
import { normalizeFormulaText, containsFormulaOrMath } from "../utils/formulaUtils";

interface KnowledgeSourceItem {
  id: string;
  course_id: string;
  lesson_id?: string | null;
  filename: string;
  file_format: string;
  size_bytes: number;
  source_role: string;
  version: number;
  checksum: string;
  status: "QUEUED" | "PROCESSING" | "INDEXED" | "FAILED";
  progress_percent: number;
  unit_count: number;
  image_count: number;
  table_count: number;
  question_count: number;
  total_pages?: number | null;
  error_message?: string | null;
  file_url?: string | null;
  created_at: string;
}

interface InspectSourceState {
  id: string;
  filename: string;
  file_format: string;
  file_url: string;
  size_bytes: number | null;
  total_pages: number;
  currentPage: number;
  pageInput: string;
  viewMode: "ORIGINAL_FILE" | "FAST_PAGES";
  scale: number | "fit";
  pageLoading: boolean;
  document: {
    title?: string;
    doc_type?: string;
    total_pages?: number | null;
    total_slides?: number | null;
    hierarchy?: unknown;
  } | null;
  units: unknown[];
  outline: unknown[];
  images: unknown[];
  loadingUnits: boolean;
}

interface AIKnowledgeCenterViewProps {
  lang: string;
}


export const AIKnowledgeCenterView: React.FC<AIKnowledgeCenterViewProps> = () => {
  const confirm = useConfirm();
  const toast = useToast();
  const [selectedCourseId] = useState<string>("all");
  const [courses, setCourses] = useState<Course[]>([]);

  const [sources, setSources] = useState<KnowledgeSourceItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Background upload manager state sync
  const [activeUploads, setActiveUploads] = useState(() =>
    uploadManager.getTasks().filter(
      (t) => t.type === "knowledge_source" && (t.status === "uploading" || t.status === "queued" || t.status === "processing")
    )
  );

  useEffect(() => {
    return uploadManager.subscribe((allTasks) => {
      setActiveUploads(
        allTasks.filter(
          (t) => t.type === "knowledge_source" && (t.status === "uploading" || t.status === "queued" || t.status === "processing")
        )
      );
    });
  }, []);

  const uploading = activeUploads.length > 0;
  const currentKnowledgeTask = activeUploads[0];
  const uploadProgress = currentKnowledgeTask ? currentKnowledgeTask.progress : null;

  // Inspector modal state
  const [inspectSource, setInspectSource] = useState<InspectSourceState | null>(null);
  const [previewToken, setPreviewToken] = useState<string | null>(null);

  // Authenticated file view token & blob preview
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Test AI panel
  const [testQuery, setTestQuery] = useState("");
  const [testAnswer, setTestAnswer] = useState<string | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testRefusal, setTestRefusal] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  const updateSources = useCallback((updater: (prev: KnowledgeSourceItem[]) => KnowledgeSourceItem[]) => {
    setSources((prev) => updater(prev));
  }, []);

  // Load courses
  useEffect(() => {
    async function loadCourses() {
      try {
        const list = await courseService.getCourses();
        setCourses(list);
      } catch (err) {
        console.error("Failed to load courses", err);
      }
    }
    void loadCourses();
  }, []);

  // Backend is the single source of truth for knowledge sources.
  const fetchSources = useCallback(async () => {
    setLoading(true);
    try {
      const query = selectedCourseId && selectedCourseId !== "all"
        ? `?course_id=${encodeURIComponent(selectedCourseId)}`
        : "";
      const data = await apiRequest<KnowledgeSourceItem[]>(`/knowledge-center/sources${query}`);
      setSources(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch sources", err);
      setSources([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCourseId]);

  useEffect(() => {
    void fetchSources();
  }, [fetchSources]);

  // Polling for active processing/queued sources
  useEffect(() => {
    const hasActive = sources.some((s) => s.status === "PROCESSING" || s.status === "QUEUED");
    if (!hasActive) return;

    const interval = setInterval(() => {
      void fetchSources();
    }, 3000);

    return () => clearInterval(interval);
  }, [sources, fetchSources]);

  // Listen for background knowledge updates
  useEffect(() => {
    const handleKnowledgeSync = () => {
      fetchSources();
    };
    window.addEventListener("lms_knowledge_updated", handleKnowledgeSync);
    return () => window.removeEventListener("lms_knowledge_updated", handleKnowledgeSync);
  }, [fetchSources]);

  // Handle file upload via background upload manager
  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    let targetCourseId = selectedCourseId;
    if (!targetCourseId || targetCourseId === "all") {
      targetCourseId = courses[0]?.id || "";
    }
    if (!targetCourseId) {
      toast({ message: "لا يوجد مقرر حقيقي متاح للرفع. أعد تحميل المقررات ثم حاول مرة أخرى.", tone: "warning" });
      return;
    }

    uploadManager.enqueueKnowledgeBatchUpload({
      files: Array.from(files),
      courseId: targetCourseId,
      onSuccess: () => {
        fetchSources();
      },
    });

    toast({
      message: `جاري رفع ${files.length} ملفات في الخلفية إلى السحابة... يمكنك التنقل ومتابعة عملك بحرية.`,
      tone: "info",
    });

    const inputEl = document.getElementById("fileUploadInput") as HTMLInputElement | null;
    if (inputEl) inputEl.value = "";
  };

  // Delete source
  const handleDelete = async (sourceId: string) => {
    const ok = await confirm({
      title: "المصدر التعليمي - حذف",
      message: "هل أنت متأكد من حذف هذا المصدر وتفريغ كافة وحداته؟ هذا الإجراء لا يمكن التراجع عنه.",
      confirmLabel: "تأكيد",
      cancelLabel: "إلغاء",
      tone: "danger",
    });
    if (!ok) return;

    try {
      await apiRequest<void>(`/knowledge-center/sources/${sourceId}`, { method: "DELETE" });
      updateSources((prev) => prev.filter((s) => s.id !== sourceId));
      toast({ message: "تم حذف المصدر وجميع وحداته المعرفية بنجاح!", tone: "success" });
    } catch (err) {
      console.error("Delete error", err);
      toast({ message: "تعذر الاتصال بالسيرفر لحذف المصدر.", tone: "danger" });
    }
  };

  // Navigation helpers for fast document viewer
  const goToNextPage = useCallback(() => {
    setInspectSource((prev) => {
      if (!prev) return null;
      if (prev.currentPage >= (prev.total_pages || 1)) return prev;
      const next = prev.currentPage + 1;
      return { ...prev, currentPage: next, pageInput: String(next), pageLoading: true };
    });
  }, []);

  const goToPrevPage = useCallback(() => {
    setInspectSource((prev) => {
      if (!prev) return null;
      if (prev.currentPage <= 1) return prev;
      const next = prev.currentPage - 1;
      return { ...prev, currentPage: next, pageInput: String(next), pageLoading: true };
    });
  }, []);

  const jumpToPage = useCallback((targetPage: number) => {
    setInspectSource((prev) => {
      if (!prev) return null;
      const maxP = Math.max(1, prev.total_pages || 1);
      const valid = Math.max(1, Math.min(maxP, targetPage));
      return { ...prev, currentPage: valid, pageInput: String(valid), pageLoading: true };
    });
  }, []);

  const handleZoomIn = useCallback(() => {
    setInspectSource((prev) => {
      if (!prev) return null;
      const current = typeof prev.scale === "number" ? prev.scale : 1.0;
      return { ...prev, scale: Math.min(2.5, Math.round((current + 0.15) * 100) / 100) };
    });
  }, []);

  const handleZoomOut = useCallback(() => {
    setInspectSource((prev) => {
      if (!prev) return null;
      const current = typeof prev.scale === "number" ? prev.scale : 1.0;
      return { ...prev, scale: Math.max(0.5, Math.round((current - 0.15) * 100) / 100) };
    });
  }, []);

  const handleZoomReset = useCallback(() => {
    setInspectSource((prev) => (prev ? { ...prev, scale: 1.0 } : null));
  }, []);

  const handleZoomFit = useCallback(() => {
    setInspectSource((prev) => (prev ? { ...prev, scale: prev.scale === "fit" ? 1.0 : "fit" } : null));
  }, []);

  // Pre-load next and previous page images in browser cache
  useEffect(() => {
    if (!inspectSource || inspectSource.viewMode !== "FAST_PAGES") return;
    const { id, currentPage, total_pages } = inspectSource;
    const activeToken = previewToken || authToken();
    const tokenQuery = activeToken ? `?token=${encodeURIComponent(activeToken)}` : "";
    if (currentPage < (total_pages || 1)) {
      const nextImg = new Image();
      nextImg.src = apiUrl(`/knowledge-center/sources/${id}/preview-page/${currentPage + 1}${tokenQuery}`);
    }
    if (currentPage > 1) {
      const prevImg = new Image();
      prevImg.src = apiUrl(`/knowledge-center/sources/${id}/preview-page/${currentPage - 1}${tokenQuery}`);
    }
  }, [inspectSource, previewToken]);

  useEffect(() => {
    if (!inspectSource?.file_url) {
      setPreviewUrl(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewUrl(null);
    fetchApiBlob(inspectSource.file_url)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("File preview error", err);
          setPreviewError(err instanceof ApiClientError && err.status === 401
            ? "انتهت جلسة الدخول. سجّل الدخول مرة أخرى لعرض الملف."
            : "تعذر تحميل الملف للمعاينة.");
        }
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [inspectSource?.id, inspectSource?.file_url]);

  const closeInspectModal = useCallback(() => {
    setInspectSource(null);
    setPreviewToken(null);
  }, []);

  // Keyboard navigation for page flipping (ArrowLeft / ArrowRight) and Escape to close
  useEffect(() => {
    if (!inspectSource) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName)) return;

      if (e.key === "Escape") {
        closeInspectModal();
      } else if (e.key === "ArrowLeft" || e.key === "PageDown") {
        goToNextPage();
      } else if (e.key === "ArrowRight" || e.key === "PageUp") {
        goToPrevPage();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [inspectSource, goToNextPage, goToPrevPage, closeInspectModal]);

  // Inspect source: Instant Modal Opening & Background Unit Loading
  const handleInspect = (sourceId: string) => {
    setPreviewToken(null);
    const found = sources.find((s) => s.id === sourceId);
    const format = (found?.file_format || "").toLowerCase();
    const fileUrl = found?.file_url || `/api/v1/knowledge-center/sources/${sourceId}/view`;
    const initialPages = found?.total_pages || 1;

    // 1. Open modal INSTANTLY (0ms latency)
    setInspectSource({
      id: sourceId,
      filename: found?.filename || "غير معروف",
      file_format: format,
      file_url: fileUrl,
      size_bytes: found?.size_bytes ?? null,
      total_pages: initialPages,
      currentPage: 1,
      pageInput: "1",
      viewMode: "ORIGINAL_FILE",
      scale: 1.0,
      pageLoading: false,
      document: null,
      units: [],
      outline: [],
      images: [],
      loadingUnits: true,
    });

    // Request short-lived preview token for authenticated direct streaming
    apiRequest<{ preview_token: string }>(`/knowledge-center/sources/${sourceId}/preview-token`, {
      method: "POST",
    })
      .then((tokenData) => {
        if (tokenData?.preview_token) {
          setPreviewToken(tokenData.preview_token);
        }
      })
      .catch((err) => {
        console.error("Failed to obtain preview token", err);
      });

    // 2. Fetch units and details asynchronously in background
    apiRequest<{
      filename?: string;
      document?: { total_pages?: number | null; [key: string]: unknown };
      units?: unknown[];
      outline?: unknown[];
      images?: unknown[];
    }>(`/knowledge-center/sources/${sourceId}`)
      .then((detailData) => {
        setInspectSource((prev) => {
          if (!prev || prev.id !== sourceId) return prev;
          const totalPages = detailData?.document?.total_pages || prev.total_pages || 1;
          return {
            ...prev,
            filename: prev.filename === "غير معروف" ? (detailData?.filename || prev.filename) : prev.filename,
            total_pages: totalPages,
            document: detailData?.document ?? null,
            units: detailData?.units || [],
            outline: detailData?.outline || [],
            images: detailData?.images || [],
            loadingUnits: false,
          };
        });
      })
      .catch((err) => {
        console.error("Inspect background error", err);
        setInspectSource((prev) => (prev && prev.id === sourceId ? { ...prev, loadingUnits: false } : prev));
      });
  };

  // Test AI Q&A — Calls real backend LLM API with zero hardcoded facts
  const handleTestAI = async () => {
    const testCourseId = courses[0]?.id;
    if (!testQuery.trim() || !testCourseId) {
      setTestError("لا يوجد مقرر متاح لاختبار المساعد حاليًا.");
      return;
    }
    setTestLoading(true);
    setTestAnswer(null);
    setTestRefusal(false);
    setTestError(null);

    try {
      const data = await apiRequest<{ answer?: string; refusal?: boolean }>("/tutor/chat", {
        method: "POST",
        body: JSON.stringify({
          course_id: testCourseId,
          message: testQuery,
        }),
      });
      setTestAnswer(data.answer || null);
      setTestRefusal(data.refusal || false);
    } catch (err) {
      console.error("Test AI API error", err);
      const message = err instanceof ApiClientError && (err.status === 401 || err.status === 403)
        ? "لا تملك صلاحية استخدام المساعد لهذا المصدر."
        : "تعذر الاتصال بخدمة الذكاء الاصطناعي حالياً. يرجى التحقق من اتصال الخادم والمحاولة لاحقاً.";
      setTestError(message);
    } finally {
      setTestLoading(false);
    }
  };

  const getFormatIcon = (fmt: string) => {
    const lower = (fmt || "").toLowerCase();
    if (lower.includes("pdf")) return <FileText style={{ color: "#ef4444", width: "20px", height: "20px" }} />;
    if (lower.includes("doc")) return <FileCode style={{ color: "#2563eb", width: "20px", height: "20px" }} />;
    if (lower.includes("ppt")) return <TableIcon style={{ color: "#f59e0b", width: "20px", height: "20px" }} />;
    if (["png", "jpg", "jpeg", "webp"].includes(lower)) return <ImageIcon style={{ color: "#10b981", width: "20px", height: "20px" }} />;
    return <FileText style={{ color: "var(--text-muted, #64748b)", width: "20px", height: "20px" }} />;
  };

  const formatSize = (bytes: number) => {
    if (!bytes) return "1.2 MB";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="page-container" style={{ maxWidth: "1280px", margin: "0 auto", color: "var(--text-main, var(--text-color, inherit))" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ minWidth: 0, width: "100%" }}>
          <h1 style={{ fontSize: "20px", fontWeight: "700", display: "flex", alignItems: "center", gap: "10px", margin: 0, flexWrap: "wrap", color: "var(--text-main, var(--text-color, inherit))" }}>
            <Sparkles style={{ color: "#2563eb", flexShrink: 0 }} size={22} />
            <span>مركز المعرفة التعليمي للذكاء الاصطناعي (AI Knowledge Center)</span>
          </h1>
          <p style={{ color: "var(--text-muted, #94a3b8)", marginTop: "6px", fontSize: "13px" }}>
            تحكّم في المصادر التعليمية والمذكرات والأسئلة السابقة التي يستند إليها الذكاء الاصطناعي في الشرح والإجابة وصناعة الاختبارات والواجبات.
          </p>
        </div>
      </div>



      {/* Upload Zone */}
      <div
        style={{
          background: "var(--bg-card, var(--card-bg, rgba(255,255,255,0.04)))",
          padding: "26px",
          borderRadius: "14px",
          border: "1px solid var(--border-color, rgba(255,255,255,0.1))",
          marginBottom: "32px",
          textAlign: "center",
          color: "var(--text-main, var(--text-color, inherit))",
        }}
      >
        <UploadCloud style={{ width: "48px", height: "48px", color: "#2563eb", marginBottom: "12px" }} />
        <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "6px", color: "var(--text-main, var(--text-color, inherit))" }}>
          رفع ملفات ومصادر المعرفة من جهازك
        </h3>
        <p style={{ color: "var(--text-muted, #94a3b8)", fontSize: "13px", marginBottom: "18px" }}>
          يمكنك اختيار كتاب واحد أو عدة كتب معًا. تُحفَظ النسخ الأصلية وتُفهرَس الصفحات والصور والنصوص داخلها (PDF, Word, PowerPoint, TXT, الصور).
        </p>

        <input
          type="file"
          id="fileUploadInput"
          multiple
          accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.gif,.json,.py,.js,.ts,.tsx,.html,.css,.sql"
          style={{ display: "none" }}
          onChange={(e) => handleUpload(e.target.files)}
        />
        <button
          type="button"
          disabled={uploading}
          onClick={() => document.getElementById("fileUploadInput")?.click()}
          style={{
            padding: "12px 32px",
            borderRadius: "10px",
            background: uploading ? "#155e42" : "#2563eb",
            color: "#ffffff",
            border: "none",
            fontSize: "15px",
            fontWeight: "700",
            cursor: uploading ? "not-allowed" : "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "10px",
            boxShadow: "0 4px 14px rgba(37, 99, 235, 0.35)",
          }}
        >
          <UploadCloud style={{ width: "20px", height: "20px", color: "#ffffff" }} />
          <span style={{ color: "#ffffff" }}>
            {uploading
              ? currentKnowledgeTask && currentKnowledgeTask.status === "processing"
                ? `فهرسة: ${currentKnowledgeTask.fileName || "الملف"} (${uploadProgress}%)...`
                : uploadProgress !== null && uploadProgress < 100
                ? (() => {
                    const totalMB = ((currentKnowledgeTask?.fileSizeBytes || 0) / (1024 * 1024)).toFixed(1);
                    const loadedBytes = currentKnowledgeTask?.loadedBytes ?? ((currentKnowledgeTask?.fileSizeBytes || 0) * (uploadProgress || 0)) / 100;
                    const loadedMB = (loadedBytes / (1024 * 1024)).toFixed(1);
                    return `جاري رفع الملفات: MB ${loadedMB} من MB ${totalMB} (${uploadProgress}%)`;
                  })()
                : "جاري حفظ وتجهيز الملفات..."
              : "اختر كتابًا أو عدة ملفات لرفعها وفهرستها"}
          </span>
        </button>

        {uploading && uploadProgress !== null && currentKnowledgeTask && (
          <div style={{ marginTop: "14px", width: "100%", maxWidth: "420px", marginInline: "auto" }}>
            <div className="progress-bar-track" style={{ background: "var(--progress-track-bg, rgb(216, 219, 223))", borderRadius: "9999px", height: "8px", overflow: "hidden" }}>
              <div
                style={{
                  width: `${uploadProgress}%`,
                  height: "100%",
                  background: currentKnowledgeTask.status === "processing" ? "#0284c7" : "#10b981",
                  transition: "width 0.25s ease",
                  borderRadius: "9999px",
                }}
              />
            </div>
            <div
              style={{
                fontSize: "12.5px",
                color: "var(--text-muted, #94a3b8)",
                marginTop: "8px",
                fontWeight: "600",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              {currentKnowledgeTask.status === "processing" ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0, overflow: "hidden" }}>
                    <span style={{ color: "#0284c7", fontWeight: 600, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                      فهرسة: {currentKnowledgeTask.fileName || currentKnowledgeTask.title}
                    </span>
                    <button
                      type="button"
                      onClick={() => uploadManager.cancelUpload(currentKnowledgeTask.id)}
                      style={{
                        background: "rgba(239, 68, 68, 0.15)",
                        border: "none",
                        color: "#ef4444",
                        borderRadius: "50%",
                        width: "18px",
                        height: "18px",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        flexShrink: 0,
                        padding: 0,
                      }}
                      title="إيقاف الفهرسة (مع حفظ الملف بالسيرفر)"
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <span style={{ color: "#0284c7", fontWeight: 700, flexShrink: 0, marginInlineStart: "8px" }}>
                    {uploadProgress}%
                  </span>
                </>
              ) : uploadProgress < 100 ? (
                (() => {
                  const totalBytes = currentKnowledgeTask.fileSizeBytes || 0;
                  const totalMB = (totalBytes / (1024 * 1024)).toFixed(1);
                  const loadedBytes = currentKnowledgeTask.loadedBytes ?? (totalBytes * (uploadProgress || 0)) / 100;
                  const loadedMB = (loadedBytes / (1024 * 1024)).toFixed(1);
                  return (
                    <>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
                        <span>
                          جاري رفع الملفات: MB {loadedMB} من MB {totalMB}
                        </span>
                        <button
                          type="button"
                          onClick={() => uploadManager.cancelUpload(currentKnowledgeTask.id)}
                          style={{
                            background: "rgba(239, 68, 68, 0.15)",
                            border: "none",
                            color: "#ef4444",
                            borderRadius: "50%",
                            width: "18px",
                            height: "18px",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: "pointer",
                            flexShrink: 0,
                            padding: 0,
                          }}
                          title="إيقاف الفهرسة (مع حفظ الملف بالسيرفر)"
                        >
                          <X size={12} />
                        </button>
                      </div>
                      <span style={{ color: "#10b981", fontWeight: 700, flexShrink: 0, marginInlineStart: "8px" }}>
                        {uploadProgress}%
                      </span>
                    </>
                  );
                })()
              ) : (
                <>
                  <span style={{ color: "#10b981" }}>تم نقل الملفات بنجاح إلى الخادم، جاري بدء الفهرسة...</span>
                  <span style={{ color: "#10b981", fontWeight: 700 }}>100%</span>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Sources Table */}
      <div style={{ background: "var(--bg-card, var(--card-bg, rgba(255,255,255,0.04)))", borderRadius: "14px", border: "1px solid var(--border-color, rgba(255,255,255,0.1))", padding: "20px", marginBottom: "32px", color: "var(--text-main, var(--text-color, inherit))" }}>
        <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main, var(--text-color, inherit))" }}>
          <Layers style={{ color: "#2563eb" }} />
          المصادر المرفوعة في المنهج ({sources.length})
        </h3>

        {loading && sources.length === 0 ? (
          <p style={{ textAlign: "center", color: "var(--text-muted, #94a3b8)", padding: "20px" }}>جاري تحميل مصادر المعرفة...</p>
        ) : sources.length === 0 ? (
          <p style={{ textAlign: "center", color: "var(--text-muted, #94a3b8)", padding: "30px 0" }}>
            لا توجد مصادر تعليمية مرفوعة لهذا المقرر بعد. قم برفع مذكرات أو ملفات PDF لتغذية مركز المعرفة الذكي.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "right" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border-color, rgba(255,255,255,0.1))", color: "var(--text-muted, #94a3b8)", fontSize: "13px" }}>
                  <th style={{ padding: "12px" }}>اسم المصدر والملف</th>
                  <th style={{ padding: "12px" }}>الحجم</th>
                  <th style={{ padding: "12px" }}>الحالة</th>
                  <th style={{ padding: "12px" }}>الوحدات المفهرسة</th>
                  <th style={{ padding: "12px" }}>الصور والأشكال</th>
                  <th style={{ padding: "12px" }}>الإجراءات</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((src) => (
                  <tr key={src.id} style={{ borderBottom: "1px solid var(--border-color, rgba(255,255,255,0.08))", fontSize: "14px", color: "var(--text-main, var(--text-color, inherit))" }}>
                    <td style={{ padding: "14px 12px", fontWeight: "600", display: "flex", alignItems: "center", gap: "10px" }}>
                      {getFormatIcon(src.file_format || src.filename)}
                      <div>
                        <div>{src.filename}</div>
                        <div style={{ fontSize: "11px", color: "var(--text-muted, #94a3b8)" }}>{new Date(src.created_at).toLocaleDateString("ar-EG")}</div>
                      </div>
                    </td>
                    <td style={{ padding: "12px" }}>{formatSize(src.size_bytes)}</td>
                    <td style={{ padding: "12px" }}>
                      {src.status === "INDEXED" && (
                        <span style={{ color: "#34d399", fontWeight: "700", display: "flex", alignItems: "center", gap: "4px", fontSize: "13px" }}>
                          <CheckCircle style={{ width: "16px", height: "16px" }} /> مُفهرس ✅
                        </span>
                      )}
                      {(src.status === "PROCESSING" || src.status === "QUEUED") && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                          <span style={{ color: "#fbbf24", fontWeight: "700", display: "flex", alignItems: "center", gap: "4px", fontSize: "13px" }}>
                            <Clock style={{ width: "16px", height: "16px" }} />
                            <span>جاري الفهرسة... {src.progress_percent > 0 ? `${src.progress_percent}%` : ""}</span>
                          </span>
                          {src.progress_percent > 0 && (
                            <div className="progress-bar-track" style={{ width: "110px", height: "5px", background: "var(--progress-track-bg, rgb(216, 219, 223))", borderRadius: "9999px", overflow: "hidden" }}>
                              <div style={{ width: `${src.progress_percent}%`, height: "100%", background: "#fbbf24", transition: "width 0.3s ease" }} />
                            </div>
                          )}
                        </div>
                      )}
                      {src.status === "FAILED" && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                          <span style={{ color: "#f87171", fontWeight: "700", display: "flex", alignItems: "center", gap: "4px", fontSize: "13px" }}>
                            <AlertTriangle style={{ width: "16px", height: "16px" }} /> فشل الفهرسة
                          </span>
                          {src.error_message && (
                            <span style={{ fontSize: "11px", color: "var(--text-muted, #94a3b8)", maxWidth: "200px", lineHeight: "1.3" }} title={src.error_message}>
                              {src.error_message.length > 55 ? src.error_message.slice(0, 52) + "..." : src.error_message}
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "12px", fontWeight: "600" }}>{src.unit_count} وحدة</td>
                    <td style={{ padding: "12px", fontWeight: "600" }}>{src.image_count} شكل</td>
                    <td style={{ padding: "12px" }}>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          type="button"
                          onClick={() => handleInspect(src.id)}
                          title="معاينة الملف"
                          aria-label="معاينة الملف"
                          style={{ padding: "7px 10px", borderRadius: "6px", background: "rgba(37,99,235,0.15)", border: "1px solid #2563eb", cursor: "pointer", color: "#60a5fa", display: "flex", alignItems: "center", justifyContent: "center" }}
                        >
                          <Eye style={{ width: "16px", height: "16px" }} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(src.id)}
                          title="حذف المصدر"
                          style={{ padding: "6px 10px", borderRadius: "6px", background: "none", border: "1px solid #fca5a5", cursor: "pointer", color: "#ef4444" }}
                        >
                          <Trash2 style={{ width: "16px", height: "16px" }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Test AI Grounding Panel */}
      <div style={{ background: "var(--bg-card, var(--card-bg, rgba(255,255,255,0.04)))", borderRadius: "14px", border: "1px solid var(--border-color, rgba(255,255,255,0.1))", padding: "20px", color: "var(--text-main, var(--text-color, inherit))" }}>
        <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main, var(--text-color, inherit))" }}>
          <HelpCircle style={{ color: "#2563eb" }} />
          لوحة اختبار المجيب الذكي وتأكيد المصادر (AI Grounding Test)
        </h3>
        <p style={{ color: "var(--text-muted, #94a3b8)", fontSize: "13px", marginBottom: "16px" }}>
          اكتب أي سؤال لاختبار دقة إجابة الذكاء الاصطناعي والتأكد من استنادها المباشر للمصادر المرفوعة مع عرض الاستشهادات والمواضع.
        </p>

        <div style={{ display: "flex", gap: "10px", marginBottom: "10px", alignItems: "center" }}>
          <input
            type="text"
            placeholder="مثال: ما المقصود بعلم الكيمياء أو اكتب معادلة مثل: Fe2O3 + CO -> 2FeO + CO2"
            value={testQuery}
            dir={/[A-Za-z]/.test(testQuery) ? "ltr" : "rtl"}
            onChange={(e) => {
              const val = e.target.value;
              if (val.includes("text{") || val.includes("\\") || val.includes("$$") || val.includes("_{") || val.includes("^{") || val.includes("->") || val.includes("-->")) {
                setTestQuery(normalizeFormulaText(val));
              } else {
                setTestQuery(val);
              }
            }}
            onPaste={(e) => {
              const pasted = e.clipboardData.getData("text");
              if (pasted && (pasted.includes("text{") || pasted.includes("\\") || pasted.includes("$$") || pasted.includes("_") || pasted.includes("^") || pasted.includes("->"))) {
                e.preventDefault();
                const clean = normalizeFormulaText(pasted);
                const target = e.target as HTMLInputElement;
                const start = target.selectionStart || 0;
                const end = target.selectionEnd || 0;
                const nextVal = testQuery.slice(0, start) + clean + testQuery.slice(end);
                setTestQuery(nextVal);
              }
            }}
            onKeyDown={(e) => e.key === "Enter" && handleTestAI()}
            style={{
              flex: 1,
              padding: "12px 16px",
              borderRadius: "8px",
              border: "1.5px solid var(--border-color, #cbd5e1)",
              background: "#ffffff",
              color: "#0f172a",
              fontSize: "15px",
              fontWeight: "600",
              outline: "none",
              textAlign: /[A-Za-z]/.test(testQuery) ? "left" : "right",
            }}
          />
          <button
            type="button"
            onClick={handleTestAI}
            disabled={testLoading}
            style={{
              padding: "12px 24px",
              borderRadius: "8px",
              background: testLoading ? "#64748b" : "#2563eb",
              color: "#ffffff",
              border: "none",
              fontWeight: "700",
              fontSize: "14px",
              cursor: testLoading ? "not-allowed" : "pointer",
              boxShadow: "0 2px 8px rgba(37,99,235,0.3)",
              whiteSpace: "nowrap",
            }}
          >
            <span style={{ color: "#ffffff" }}>
              {testLoading ? "جاري البحث والإجابة..." : "اختبار الإجابة"}
            </span>
          </button>
        </div>

        {/* Live Typeset KaTeX Preview for the Text Box in White Screen */}
        {testQuery && containsFormulaOrMath(testQuery) && (
          <div
            style={{
              marginBottom: "16px",
              padding: "16px 20px",
              borderRadius: "12px",
              background: "#ffffff",
              border: "2px solid #10b981",
              boxShadow: "0 4px 14px rgba(16, 185, 129, 0.12)",
              color: "#0f172a",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px", borderBottom: "1px solid #e2e8f0", paddingBottom: "6px" }}>
              <span style={{ fontSize: "13px", color: "#059669", fontWeight: 800, display: "flex", alignItems: "center", gap: "6px" }}>
                <span>📖</span>
                معادلة كالكتاب المدرسي (شروط التفاعل والحرارة فوق السهم):
              </span>
              <span style={{ fontSize: "11px", color: "#64748b", fontWeight: 600 }}>
                رسم أكاديمي منسق LTR
              </span>
            </div>
            <div dir="ltr" style={{ padding: "8px 0", color: "#0f172a", fontSize: "16px" }}>
              <FormulaRenderer text={testQuery} />
            </div>
          </div>
        )}

        {testError && (
          <div
            style={{
              padding: "16px",
              borderRadius: "10px",
              background: "rgba(239,68,68,0.12)",
              border: "1px solid rgba(239,68,68,0.4)",
              color: "var(--text-main, var(--text-color, inherit))",
            }}
          >
            <div style={{ fontWeight: "700", marginBottom: "6px", fontSize: "14px", color: "#f87171" }}>
              ❌ تعذر تشغيل الخدمة:
            </div>
            <div style={{ fontSize: "13px", lineHeight: "1.5", color: "#fca5a5" }}>
              {testError}
            </div>
          </div>
        )}

        {testAnswer && (
          <div
            style={{
              padding: "18px",
              borderRadius: "10px",
              background: testRefusal ? "rgba(245,158,11,0.12)" : "rgba(16,185,129,0.12)",
              border: `1px solid ${testRefusal ? "rgba(245,158,11,0.4)" : "rgba(16,185,129,0.4)"}`,
              color: "var(--text-main, var(--text-color, inherit))",
            }}
          >
            <div style={{ fontWeight: "700", marginBottom: "8px", fontSize: "15px", color: testRefusal ? "#fbbf24" : "#34d399" }}>
              {testRefusal ? "⚠️ خارج نطاق مصادر المقرر المتاحة:" : "✅ إجابة موثقة ومستندة لمصادر المعلم:"}
            </div>
            <div style={{ fontSize: "14px", lineHeight: "1.6", color: "var(--text-main, var(--text-color, inherit))", fontWeight: "500" }}>
              <FormulaRenderer text={testAnswer} />
            </div>
          </div>
        )}
      </div>

      {/* Document Inspector Modal — Direct Embedded PDF Viewer */}
      {inspectSource && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "#1e293b",
              color: "#f8fafc",
              width: "100%",
              maxWidth: "1050px",
              height: "92vh",
              display: "flex",
              flexDirection: "column",
              borderRadius: "16px",
              border: "1px solid rgba(255,255,255,0.2)",
              overflow: "hidden",
              boxShadow: "0 20px 50px rgba(0,0,0,0.6)",
            }}
          >
            {/* Modal Header */}
            <div style={{ padding: "16px 24px", borderBottom: "1px solid rgba(255,255,255,0.15)", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#0f172a" }}>
              <div>
                <h3 style={{ fontSize: "18px", fontWeight: "700", margin: 0, display: "flex", alignItems: "center", gap: "10px", color: "#f8fafc" }}>
                  <BookOpen style={{ color: "#38bdf8" }} />
                  معاينة قراءة الملف داخل الموقع: {inspectSource.filename}
                </h3>
                <div style={{ fontSize: "13px", color: "#cbd5e1", marginTop: "4px" }}>
                  صيغة المستند: <strong style={{ color: "#38bdf8" }}>{inspectSource.file_format?.toUpperCase() || "PDF"}</strong>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                {inspectSource.file_url && (
                  <a
                    href={
                      previewUrl ||
                      apiUrl(
                        `/knowledge-center/sources/${inspectSource.id}/preview-file${
                          previewToken || authToken() ? `?token=${encodeURIComponent(previewToken || authToken() || "")}` : ""
                        }`
                      )
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    title="فتح المستند في نافذة كاملة جديدة"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      background: "rgba(56,189,248,0.15)",
                      border: "1px solid rgba(56,189,248,0.4)",
                      color: "#38bdf8",
                      fontSize: "13px",
                      fontWeight: "600",
                      textDecoration: "none",
                      cursor: "pointer",
                    }}
                  >
                    <ExternalLink style={{ width: "15px", height: "15px" }} />
                    فتح في نافذة كاملة
                  </a>
                )}
                <button
                  type="button"
                  onClick={closeInspectModal}
                  style={{ background: "none", border: "none", fontSize: "24px", cursor: "pointer", color: "#ffffff", padding: "4px 8px" }}
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Body: Fast Page Reader or Embedded Browser Viewer */}
            <div style={{ flex: 1, overflow: "hidden", padding: "0", background: "#0b0f19", display: "flex", flexDirection: "column" }}>
              <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
                {inspectSource.viewMode === "FAST_PAGES" ? (
                  <>
                    {/* Reader Navigation & Zoom Toolbar */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "10px 20px",
                        background: "#111827",
                        borderBottom: "1px solid rgba(255,255,255,0.1)",
                        flexWrap: "wrap",
                        gap: "10px",
                      }}
                    >
                      {/* Page Navigation */}
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <button
                          type="button"
                          onClick={goToPrevPage}
                          disabled={inspectSource.currentPage <= 1}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "6px 14px",
                            borderRadius: "6px",
                            background: inspectSource.currentPage <= 1 ? "rgba(255,255,255,0.05)" : "#2563eb",
                            color: inspectSource.currentPage <= 1 ? "#64748b" : "#ffffff",
                            border: "none",
                            cursor: inspectSource.currentPage <= 1 ? "not-allowed" : "pointer",
                            fontWeight: "700",
                            fontSize: "13px",
                          }}
                        >
                          <ChevronRight style={{ width: "16px", height: "16px" }} />
                          السابق
                        </button>

                        {/* Quick -10 Jump */}
                        {(inspectSource.total_pages || 1) > 15 && (
                          <button
                            type="button"
                            onClick={() => jumpToPage(inspectSource.currentPage - 10)}
                            disabled={inspectSource.currentPage <= 1}
                            title="الرجوع 10 صفحات"
                            style={{
                              padding: "4px 8px",
                              borderRadius: "4px",
                              background: "rgba(255,255,255,0.08)",
                              color: "#94a3b8",
                              border: "1px solid rgba(255,255,255,0.1)",
                              cursor: inspectSource.currentPage <= 1 ? "not-allowed" : "pointer",
                              fontSize: "12px",
                              fontWeight: "600",
                            }}
                          >
                            -10
                          </button>
                        )}

                        {/* Page Input Counter */}
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#f8fafc", fontSize: "13px", fontWeight: "600" }}>
                          <span>صفحة</span>
                          <input
                            type="text"
                            value={inspectSource.pageInput ?? String(inspectSource.currentPage)}
                            onChange={(e) => {
                              const val = e.target.value;
                              setInspectSource((prev) => prev ? { ...prev, pageInput: val } : null);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                const p = parseInt(inspectSource.pageInput, 10);
                                if (!isNaN(p)) jumpToPage(p);
                              }
                            }}
                            onBlur={() => {
                              const p = parseInt(inspectSource.pageInput, 10);
                              if (!isNaN(p)) jumpToPage(p);
                            }}
                            style={{
                              width: "55px",
                              textAlign: "center",
                              padding: "4px 6px",
                              borderRadius: "6px",
                              border: "1px solid #38bdf8",
                              background: "#1e293b",
                              color: "#38bdf8",
                              fontWeight: "700",
                              fontSize: "14px",
                            }}
                          />
                          <span>من {inspectSource.total_pages || 1}</span>
                        </div>

                        {/* Quick +10 Jump */}
                        {(inspectSource.total_pages || 1) > 15 && (
                          <button
                            type="button"
                            onClick={() => jumpToPage(inspectSource.currentPage + 10)}
                            disabled={inspectSource.currentPage >= (inspectSource.total_pages || 1)}
                            title="التقدم 10 صفحات"
                            style={{
                              padding: "4px 8px",
                              borderRadius: "4px",
                              background: "rgba(255,255,255,0.08)",
                              color: "#94a3b8",
                              border: "1px solid rgba(255,255,255,0.1)",
                              cursor: inspectSource.currentPage >= (inspectSource.total_pages || 1) ? "not-allowed" : "pointer",
                              fontSize: "12px",
                              fontWeight: "600",
                            }}
                          >
                            +10
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={goToNextPage}
                          disabled={inspectSource.currentPage >= (inspectSource.total_pages || 1)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "6px 14px",
                            borderRadius: "6px",
                            background: inspectSource.currentPage >= (inspectSource.total_pages || 1) ? "rgba(255,255,255,0.05)" : "#2563eb",
                            color: inspectSource.currentPage >= (inspectSource.total_pages || 1) ? "#64748b" : "#ffffff",
                            border: "none",
                            cursor: inspectSource.currentPage >= (inspectSource.total_pages || 1) ? "not-allowed" : "pointer",
                            fontWeight: "700",
                            fontSize: "13px",
                          }}
                        >
                          التالي
                          <ChevronLeft style={{ width: "16px", height: "16px" }} />
                        </button>
                      </div>

                      {/* Zoom and Mode Controls */}
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        {/* Fast Speed Tag */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "5px",
                            fontSize: "12px",
                            color: "#34d399",
                            background: "rgba(16,185,129,0.12)",
                            padding: "4px 10px",
                            borderRadius: "20px",
                            border: "1px solid rgba(16,185,129,0.3)",
                            fontWeight: "600",
                          }}
                        >
                          <Zap style={{ width: "14px", height: "14px" }} />
                          عرض فوري مباشر
                        </div>

                        {/* Zoom Controls */}
                        <div style={{ display: "flex", alignItems: "center", gap: "4px", background: "#1e293b", padding: "3px 6px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.1)" }}>
                          <button
                            type="button"
                            onClick={handleZoomOut}
                            title="تصغير"
                            style={{ background: "none", border: "none", color: "#f8fafc", cursor: "pointer", padding: "4px", display: "flex", alignItems: "center" }}
                          >
                            <ZoomOut style={{ width: "15px", height: "15px" }} />
                          </button>
                          <button
                            type="button"
                            onClick={handleZoomReset}
                            title="إعادة الحجم الافتراضي"
                            style={{ background: "none", border: "none", color: "#38bdf8", cursor: "pointer", fontSize: "12px", fontWeight: "700", padding: "0 6px", display: "flex", alignItems: "center", gap: "3px" }}
                          >
                            <RotateCcw style={{ width: "12px", height: "12px" }} />
                            {typeof inspectSource.scale === "number" ? `${Math.round(inspectSource.scale * 100)}%` : "تناسب"}
                          </button>
                          <button
                            type="button"
                            onClick={handleZoomIn}
                            title="تكبير"
                            style={{ background: "none", border: "none", color: "#f8fafc", cursor: "pointer", padding: "4px", display: "flex", alignItems: "center" }}
                          >
                            <ZoomIn style={{ width: "15px", height: "15px" }} />
                          </button>
                          <button
                            type="button"
                            onClick={handleZoomFit}
                            title="تناسب العرض"
                            style={{ background: "none", border: "none", color: "#cbd5e1", cursor: "pointer", padding: "4px", display: "flex", alignItems: "center" }}
                          >
                            <Maximize2 style={{ width: "14px", height: "14px" }} />
                          </button>
                        </div>

                        {/* Fallback to full file if requested */}
                        <button
                          type="button"
                          onClick={() => setInspectSource((prev) => prev ? { ...prev, viewMode: "ORIGINAL_FILE" } : null)}
                          title="التبديل إلى عارض المتصفح الأصلي الكامل"
                          style={{
                            padding: "5px 10px",
                            borderRadius: "6px",
                            background: "rgba(255,255,255,0.06)",
                            border: "1px solid rgba(255,255,255,0.15)",
                            color: "#cbd5e1",
                            fontSize: "12px",
                            fontWeight: "600",
                            cursor: "pointer",
                          }}
                        >
                          عارض PDF الكامل
                        </button>
                      </div>
                    </div>

                    {/* Main Scrollable Canvas for Fast Page Streaming */}
                    <div
                      style={{
                        flex: 1,
                        overflowY: "auto",
                        overflowX: "auto",
                        padding: "24px 16px",
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "flex-start",
                        background: "#090d16",
                        position: "relative",
                      }}
                    >
                      <div
                        style={{
                          maxWidth: inspectSource.scale === "fit" ? "100%" : `${(typeof inspectSource.scale === "number" ? inspectSource.scale : 1.0) * 880}px`,
                          width: inspectSource.scale === "fit" ? "100%" : "auto",
                          position: "relative",
                          transition: "width 0.15s ease",
                        }}
                      >
                        <img
                          key={`${inspectSource.id}-p${inspectSource.currentPage}`}
                          src={apiUrl(
                            `/knowledge-center/sources/${inspectSource.id}/preview-page/${inspectSource.currentPage}${
                              previewToken || authToken() ? `?token=${encodeURIComponent(previewToken || authToken() || "")}` : ""
                            }`
                          )}
                          alt={`الصفحة ${inspectSource.currentPage}`}
                          onLoad={() => setInspectSource((prev) => prev ? { ...prev, pageLoading: false } : null)}
                          onError={() => setInspectSource((prev) => prev ? { ...prev, pageLoading: false } : null)}
                          style={{
                            width: "100%",
                            height: "auto",
                            display: "block",
                            borderRadius: "8px",
                            boxShadow: "0 12px 40px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.1)",
                            background: "#ffffff",
                          }}
                        />

                        {/* Subtle loading badge while next page image is loading */}
                        {inspectSource.pageLoading && (
                          <div
                            style={{
                              position: "absolute",
                              top: "12px",
                              left: "12px",
                              background: "rgba(15,23,42,0.85)",
                              backdropFilter: "blur(6px)",
                              border: "1px solid rgba(56,189,248,0.4)",
                              color: "#38bdf8",
                              padding: "6px 12px",
                              borderRadius: "8px",
                              fontSize: "12px",
                              fontWeight: "700",
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              zIndex: 10,
                            }}
                          >
                            <RefreshCw style={{ width: "14px", height: "14px", animation: "spin 1s linear infinite" }} />
                            جاري تحميل الصفحة {inspectSource.currentPage}...
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  /* Fallback: Original PDF iframe */
                  <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
                    <div style={{ padding: "8px 16px", background: "#111827", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                      <span style={{ fontSize: "13px", color: "#94a3b8" }}>عارض المتصفح الكامل للملف الأصلي</span>
                      <button
                        type="button"
                        onClick={() => setInspectSource((prev) => prev ? { ...prev, viewMode: "FAST_PAGES" } : null)}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "6px",
                          background: "#2563eb",
                          color: "#ffffff",
                          border: "none",
                          fontSize: "12px",
                          fontWeight: "700",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <Zap style={{ width: "14px", height: "14px" }} />
                        التبديل إلى عارض الصفحات فائق السرعة
                      </button>
                    </div>
                    {previewLoading ? (
                      <div style={{ flex: 1, display: "grid", placeItems: "center", color: "#cbd5e1" }}>
                        جاري تحميل الملف للمعاينة...
                      </div>
                    ) : previewError ? (
                      <div style={{ flex: 1, display: "grid", placeItems: "center", color: "#fca5a5", padding: "24px", textAlign: "center" }}>
                        {previewError}
                      </div>
                    ) : previewUrl || previewToken || authToken() ? (
                      <iframe
                        src={
                          previewUrl ||
                          apiUrl(
                            `/knowledge-center/sources/${inspectSource.id}/preview-file${
                              previewToken || authToken() ? `?token=${encodeURIComponent(previewToken || authToken() || "")}` : ""
                            }`
                          )
                        }
                        title={inspectSource.filename}
                        style={{ width: "100%", height: "100%", flex: 1, border: "none", background: "#ffffff" }}
                      />
                    ) : (
                      <div style={{ flex: 1, display: "grid", placeItems: "center", color: "#94a3b8" }}>
                        لا يوجد ملف قابل للمعاينة.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

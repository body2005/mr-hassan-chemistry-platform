import React, { useState, useEffect, useMemo } from "react";
import {
  FileQuestion,
  Eye,
  Edit3,
  Trash2,
  Printer,
  Search,
  Calendar,
  Clock,
  CheckCircle2,
  AlertCircle,
  PenTool,
  Plus,
  X,
  FileText,
  Check,
} from "lucide-react";
import {
  quizHistoryService,
  PublishedQuizRecord,
} from "../services/quizHistoryService";
import { FormulaRenderer } from "./FormulaRenderer";

interface QuizHistorySectionProps {
  onSwitchToCreator: () => void;
  onLoadQuizIntoEditor: (quiz: PublishedQuizRecord) => void;
}

export const QuizHistorySection: React.FC<QuizHistorySectionProps> = ({
  onSwitchToCreator,
  onLoadQuizIntoEditor,
}) => {
  const [quizzes, setQuizzes] = useState<PublishedQuizRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedYear, setSelectedYear] = useState<string>("all");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"newest" | "points" | "questions">("newest");

  // Preview Modal
  const [previewQuiz, setPreviewQuiz] = useState<PublishedQuizRecord | null>(null);

  // Delete Confirm Modal
  const [deletingQuizId, setDeletingQuizId] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = quizHistoryService.subscribe((records) => {
      setQuizzes(records);
    });
    return () => unsubscribe();
  }, []);

  // Filtered and Sorted Quizzes
  const filteredQuizzes = useMemo(() => {
    return quizzes
      .filter((q) => {
        if (selectedYear !== "all" && q.academicYear !== selectedYear) return false;
        if (selectedType !== "all" && q.assessmentType !== selectedType) return false;
        if (selectedStatus !== "all" && q.status !== selectedStatus) return false;

        if (searchQuery.trim()) {
          const qText = searchQuery.toLowerCase().trim();
          const matchTitle = q.title.toLowerCase().includes(qText);
          const matchQuestions = q.questions.some(
            (item) =>
              item.question_text.toLowerCase().includes(qText) ||
              item.topic.toLowerCase().includes(qText) ||
              (item.options && item.options.some((opt) => opt.text.toLowerCase().includes(qText)))
          );
          if (!matchTitle && !matchQuestions) return false;
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === "points") {
          return b.totalPoints - a.totalPoints;
        }
        if (sortBy === "questions") {
          return b.questionsCount - a.questionsCount;
        }
        // newest (default)
        return b.id.localeCompare(a.id);
      });
  }, [quizzes, selectedYear, selectedType, selectedStatus, searchQuery, sortBy]);

  // Overall Statistics
  const stats = useMemo(() => {
    const total = quizzes.length;
    const totalQuestions = quizzes.reduce((sum, q) => sum + (q.questionsCount || q.questions?.length || 0), 0);
    const activeCount = quizzes.filter((q) => q.status === "active").length;
    const closedCount = quizzes.filter((q) => q.status === "closed").length;
    return { total, totalQuestions, activeCount, closedCount };
  }, [quizzes]);

  // Delete handler
  function handleConfirmDelete() {
    if (deletingQuizId) {
      quizHistoryService.deleteQuiz(deletingQuizId);
      setDeletingQuizId(null);
    }
  }

  // Print handler
  function handlePrintQuiz(quiz: PublishedQuizRecord) {
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    const htmlContent = `
      <!DOCTYPE html>
      <html dir="rtl" lang="ar">
      <head>
        <meta charset="utf-8" />
        <title>${quiz.title} - ورقة الاختبار</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css" />
        <style>
          @page { size: A4; margin: 20mm; }
          html, body { direction: rtl; unicode-bidi: plaintext; }
          body { font-family: 'Noto Naskh Arabic', 'Amiri', 'Segoe UI', Tahoma, sans-serif; line-height: 1.6; color: #111; margin: 0; padding: 20px; text-align: right; }
          .header { border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 20px; }
          .meta-box { display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; margin-bottom: 10px; }
          .student-info { display: flex; justify-content: space-between; font-size: 14px; margin-top: 15px; border-top: 1px dashed #666; padding-top: 10px; }
          .question, .q-title, .option-item { direction: rtl; unicode-bidi: plaintext; text-align: right; }
          .question { margin-bottom: 24px; padding-bottom: 15px; border-bottom: 1px dotted #ccc; page-break-inside: avoid; }
          .q-title { font-weight: bold; font-size: 15px; margin-bottom: 8px; }
          .points { float: left; font-size: 12px; color: #555; font-weight: normal; }
          .options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
          .option-item { border: 1px solid #ddd; padding: 6px 12px; border-radius: 4px; font-size: 13.5px; }
          .essay-space { height: 70px; border: 1px dashed #aaa; border-radius: 6px; margin-top: 8px; background: #fafafa; }
          @media print {
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <div style="text-align: center; margin-bottom: 8px;">
            <h2 style="margin: 0; font-size: 20px;">منصة التعلّم الذكية</h2>
            <h3 style="margin: 4px 0; font-size: 17px; color: #064e3b;">${quiz.title}</h3>
          </div>
          <div class="meta-box">
            <span>الصف: ${quiz.academicYearLabel}</span>
            <span>النوع: ${quiz.assessmentType === "quiz" ? "اختبار إلكتروني" : "واجب منزلي"}</span>
            <span>الزمن: ${quiz.quizDurationMinutes ? `${quiz.quizDurationMinutes} دقيقة` : "مفتوح"}</span>
            <span>الدرجة الكلية: ${quiz.totalPoints} درجة</span>
          </div>
          <div class="student-info">
            <span>اسم الطالب: ................................................................</span>
            <span>رقم الجلوس: ................</span>
            <span>الدرجة: ........ / ${quiz.totalPoints}</span>
          </div>
        </div>

        <div class="questions-list">
          ${quiz.questions
            .map(
              (q, idx) => `
            <div class="question">
              <div class="q-title">
                <span class="points">[ ${q.points} درجات ]</span>
                السؤال ${idx + 1}: ${q.question_text}
              </div>
              ${
                q.options && q.options.length > 0
                  ? `
                  <div class="options-grid">
                    ${q.options
                      .map((opt) => `<div class="option-item">(${opt.key}) ${opt.text}</div>`)
                      .join("")}
                  </div>
                  `
                  : `<div class="essay-space"></div>`
              }
            </div>
          `
            )
            .join("")}
        </div>

        <script>
          window.onload = function() {
            window.print();
          };
        </script>
      </body>
      </html>
    `;

    printWindow.document.open();
    printWindow.document.write(htmlContent);
    printWindow.document.close();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Top Banner & Stats */}
      <div
        style={{
          background: "#0f392b",
          borderRadius: "16px",
          padding: "24px",
          color: "#ffffff",
          boxShadow: "0 8px 24px rgba(6, 78, 59, 0.15)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "16px",
            marginBottom: "20px",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
              <span
                style={{
                  background: "rgba(52, 211, 153, 0.2)",
                  color: "#34d399",
                  padding: "4px 10px",
                  borderRadius: "20px",
                  fontSize: "12px",
                  fontWeight: 800,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                <FileQuestion size={13} />
                أرشيف وسجل المعلم
              </span>
              <span style={{ fontSize: "12px", opacity: 0.8 }}>
                • تم نشر {stats.total} اختبارات وواجبات حتى الآن
              </span>
            </div>
            <h2 style={{ margin: 0, fontSize: "22px", fontWeight: 800 }}>
              سجل الاختبارات والتقييمات المرفوعة
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "13px", opacity: 0.9 }}>
              استعرض جميع الاختبارات التي قمت برفعها ونشرها للطلاب، وتصفح الأسئلة ونماذج الإجابة، أو أعد استخدامها وتعديلها.
            </p>
          </div>

          <button
            type="button"
            onClick={onSwitchToCreator}
            style={{
              background: "#34d399",
              color: "#064e3b",
              border: "none",
              borderRadius: "10px",
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: 800,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              transition: "all 0.2s ease",
            }}
          >
            <Plus size={16} />
            <span>إنشاء اختبار جديد الآن</span>
          </button>
        </div>

        {/* Quick Stats Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: "12px",
          }}
        >
          <div
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "12px 16px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
            }}
          >
            <span style={{ fontSize: "11px", opacity: 0.8, display: "block" }}>إجمالي المنشور</span>
            <strong style={{ fontSize: "22px", fontWeight: 800 }}>{stats.total}</strong>
            <span style={{ fontSize: "11px", opacity: 0.7, marginInlineStart: "4px" }}>اختبار وواجب</span>
          </div>

          <div
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "12px 16px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
            }}
          >
            <span style={{ fontSize: "11px", opacity: 0.8, display: "block" }}>بنك الأسئلة</span>
            <strong style={{ fontSize: "22px", fontWeight: 800 }}>{stats.totalQuestions}</strong>
            <span style={{ fontSize: "11px", opacity: 0.7, marginInlineStart: "4px" }}>سؤال منشور</span>
          </div>

          <div
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "12px 16px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
            }}
          >
            <span style={{ fontSize: "11px", opacity: 0.8, display: "block" }}>متاح للحل الآن</span>
            <strong style={{ fontSize: "22px", fontWeight: 800, color: "#34d399" }}>
              {stats.activeCount}
            </strong>
            <span style={{ fontSize: "11px", opacity: 0.7, marginInlineStart: "4px" }}>نشط للطلاب</span>
          </div>

          <div
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "12px 16px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
            }}
          >
            <span style={{ fontSize: "11px", opacity: 0.8, display: "block" }}>منتهي الموعد</span>
            <strong style={{ fontSize: "22px", fontWeight: 800, color: "#cbd5e1" }}>
              {stats.closedCount}
            </strong>
            <span style={{ fontSize: "11px", opacity: 0.7, marginInlineStart: "4px" }}>مغلق</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          border: "1px solid var(--border-color, #e2e8f0)",
          borderRadius: "14px",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
          {/* Search Input */}
          <div
            style={{
              flex: "1 1 260px",
              position: "relative",
              display: "flex",
              alignItems: "center",
            }}
          >
            <Search
              size={16}
              style={{
                position: "absolute",
                right: "12px",
                color: "var(--text-muted, #94a3b8)",
              }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="ابحث بعنوان الاختبار أو محتوى الأسئلة..."
              style={{
                width: "100%",
                padding: "9px 36px 9px 12px",
                borderRadius: "10px",
                border: "1px solid var(--border-color, #cbd5e1)",
                background: "var(--bg-surface-secondary, #f8fafc)",
                fontSize: "13px",
                color: "var(--text-main, #0f172a)",
                outline: "none",
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  left: "10px",
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted, #94a3b8)",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Academic Year Filter */}
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(e.target.value)}
            style={{
              padding: "9px 12px",
              borderRadius: "10px",
              border: "1px solid var(--border-color, #cbd5e1)",
              background: "var(--bg-surface, #ffffff)",
              fontSize: "12.5px",
              color: "var(--text-main, #0f172a)",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            <option value="all">كل الصفوف الدراسية</option>
            <option value="1st_secondary">الصف الأول الثانوي</option>
            <option value="2nd_secondary">الصف الثاني الثانوي</option>
            <option value="3rd_secondary">الصف الثالث الثانوي</option>
          </select>

          {/* Assessment Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            style={{
              padding: "9px 12px",
              borderRadius: "10px",
              border: "1px solid var(--border-color, #cbd5e1)",
              background: "var(--bg-surface, #ffffff)",
              fontSize: "12.5px",
              color: "var(--text-main, #0f172a)",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            <option value="all">كل الأنواع (اختبارات وواجبات)</option>
            <option value="quiz">اختبار إلكتروني</option>
            <option value="assignment">واجب منزلي</option>
          </select>

          {/* Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{
              padding: "9px 12px",
              borderRadius: "10px",
              border: "1px solid var(--border-color, #cbd5e1)",
              background: "var(--bg-surface, #ffffff)",
              fontSize: "12.5px",
              color: "var(--text-main, #0f172a)",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            <option value="all">كل الحالات</option>
            <option value="active">نشط ومتاح للحل</option>
            <option value="closed">منتهي الموعد</option>
            <option value="scheduled">مجدول لاحقاً</option>
          </select>

          {/* Sort By */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "newest" | "points" | "questions")}
            style={{
              padding: "9px 12px",
              borderRadius: "10px",
              border: "1px solid var(--border-color, #cbd5e1)",
              background: "var(--bg-surface, #ffffff)",
              fontSize: "12.5px",
              color: "var(--text-main, #0f172a)",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            <option value="newest">الترتيب: الأحدث نشراً</option>
            <option value="points">الترتيب: الأعلى درجات</option>
            <option value="questions">الترتيب: الأكثر أسئلة</option>
          </select>
        </div>
      </div>

      {/* Quizzes List */}
      {filteredQuizzes.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "50px 20px",
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "16px",
            border: "1.5px dashed var(--border-color, #cbd5e1)",
          }}
        >
          <FileQuestion size={44} style={{ color: "#94a3b8", margin: "0 auto 12px" }} />
          <h3 style={{ margin: "0 0 6px", fontSize: "16px", color: "var(--text-main)" }}>
            لم يتم العثور على أي اختبارات مطابقة
          </h3>
          <p style={{ margin: "0 0 16px", fontSize: "13px", color: "var(--text-muted)" }}>
            {searchQuery || selectedYear !== "all" || selectedType !== "all" || selectedStatus !== "all"
              ? "جرب تعديل خيارات التصفية أو البحث لإظهار النتائج."
              : "لم تقم برفع أو نشر أي اختبارات حتى الآن."}
          </p>
          <button
            type="button"
            onClick={onSwitchToCreator}
            style={{
              background: "#0f392b",
              color: "#ffffff",
              border: "none",
              borderRadius: "10px",
              padding: "10px 20px",
              fontSize: "13px",
              fontWeight: 700,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <Plus size={16} />
            <span>إنشاء أول اختبار الآن</span>
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          {filteredQuizzes.map((quiz) => {
            const isQuiz = quiz.assessmentType === "quiz";
            const isActive = quiz.status === "active";
            const isClosed = quiz.status === "closed";

            return (
              <div
                key={quiz.id}
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  borderRadius: "14px",
                  padding: "18px 20px",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                  transition: "transform 0.15s ease, box-shadow 0.15s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "14px",
                }}
              >
                {/* Card Header Row */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    flexWrap: "wrap",
                    gap: "12px",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 800,
                          padding: "3px 8px",
                          borderRadius: "6px",
                          background: isQuiz ? "#ccfbf1" : "#ecfdf5",
                          color: isQuiz ? "#0f766e" : "#0f392b",
                          border: isQuiz ? "1px solid #99f6e4" : "1px solid #a7f3d0",
                        }}
                      >
                        {isQuiz ? "اختبار إلكتروني" : "واجب منزلي"}
                      </span>

                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          padding: "3px 8px",
                          borderRadius: "6px",
                          background: "var(--bg-surface-secondary, #f1f5f9)",
                          color: "var(--text-muted, #475569)",
                        }}
                      >
                        {quiz.academicYearLabel}
                      </span>

                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "3px 8px",
                          borderRadius: "6px",
                          background: "rgba(59, 130, 246, 0.1)",
                          color: "#1d4ed8",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        {quiz.creationMode === "extracted" || quiz.creationMode === "extract" ? (
                          <>
                            <FileText size={11} /> مستخرج من ملف
                          </>
                        ) : (
                          <>
                            <PenTool size={11} /> يدوي مباشر
                          </>
                        )}
                      </span>

                      {/* Status Badge */}
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          padding: "3px 8px",
                          borderRadius: "6px",
                          background: isActive ? "#dcfce7" : isClosed ? "#f1f5f9" : "#fef3c7",
                          color: isActive ? "#166534" : isClosed ? "#64748b" : "#b45309",
                          border: isActive ? "1px solid #bbf7d0" : "1px solid #e2e8f0",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        {isActive ? (
                          <>
                            <CheckCircle2 size={11} /> متاح للحل الآن
                          </>
                        ) : isClosed ? (
                          <>
                            <Clock size={11} /> منتهي الموعد
                          </>
                        ) : (
                          <>
                            <Calendar size={11} /> مجدول لاحقاً
                          </>
                        )}
                      </span>
                    </div>

                    <h3 style={{ margin: 0, fontSize: "16.5px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
                      {quiz.title}
                    </h3>
                  </div>

                  {/* Top-Right Quick Stats */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      background: "var(--bg-surface-secondary, #f8fafc)",
                      padding: "6px 14px",
                      borderRadius: "10px",
                      border: "1px solid var(--border-color, #e2e8f0)",
                    }}
                  >
                    <div style={{ textAlign: "center" }}>
                      <span style={{ fontSize: "10px", color: "var(--text-muted)", display: "block" }}>الأسئلة</span>
                      <strong style={{ fontSize: "14px", color: "var(--text-main)" }}>{quiz.questionsCount}</strong>
                    </div>
                    <div style={{ width: "1px", height: "20px", background: "var(--border-color, #e2e8f0)" }} />
                    <div style={{ textAlign: "center" }}>
                      <span style={{ fontSize: "10px", color: "var(--text-muted)", display: "block" }}>الدرجات</span>
                      <strong style={{ fontSize: "14px", color: "#0f766e" }}>{quiz.totalPoints}</strong>
                    </div>
                    {quiz.quizDurationMinutes && (
                      <>
                        <div style={{ width: "1px", height: "20px", background: "var(--border-color, #e2e8f0)" }} />
                        <div style={{ textAlign: "center" }}>
                          <span style={{ fontSize: "10px", color: "var(--text-muted)", display: "block" }}>الزمن</span>
                          <strong style={{ fontSize: "13px", color: "var(--text-main)" }}>
                            {quiz.quizDurationMinutes}د
                          </strong>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Details & Dates Row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "16px",
                    flexWrap: "wrap",
                    fontSize: "12px",
                    color: "var(--text-muted, #64748b)",
                    paddingTop: "6px",
                    borderTop: "1px solid var(--border-color, #f1f5f9)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                    <Calendar size={13} style={{ color: "#059669" }} />
                    <span>تاريخ النشر: {quiz.publishedAt}</span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                    <Clock size={13} style={{ color: "#0284c7" }} />
                    <span>
                      متاح من: {quiz.publishStartDate} ({quiz.publishStartTime})
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                    <AlertCircle size={13} style={{ color: "#dc2626" }} />
                    <span>آخر موعد: {quiz.closeDeadline}</span>
                  </div>
                </div>

                {/* Action Buttons Row */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                    paddingTop: "10px",
                    borderTop: "1px solid var(--border-color, #f1f5f9)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {/* View Preview Button */}
                    <button
                      type="button"
                      onClick={() => setPreviewQuiz(quiz)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "7px 14px",
                        borderRadius: "8px",
                        border: "1px solid var(--border-color, #cbd5e1)",
                        background: "var(--bg-surface, #ffffff)",
                        color: "var(--text-main, #0f172a)",
                        fontSize: "12px",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      <Eye size={14} style={{ color: "#0f766e" }} />
                      <span>عرض الأسئلة والإجابات</span>
                    </button>

                    {/* Print / Export Button */}
                    <button
                      type="button"
                      onClick={() => handlePrintQuiz(quiz)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "7px 14px",
                        borderRadius: "8px",
                        border: "1px solid var(--border-color, #cbd5e1)",
                        background: "var(--bg-surface, #ffffff)",
                        color: "var(--text-main, #0f172a)",
                        fontSize: "12px",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                      title="طباعة ورقة الاختبار للطالب"
                    >
                      <Printer size={14} style={{ color: "#475569" }} />
                      <span>طباعة الامتحان</span>
                    </button>

                    {/* Re-open / Edit in Creator Button */}
                    <button
                      type="button"
                      onClick={() => onLoadQuizIntoEditor(quiz)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "7px 14px",
                        borderRadius: "8px",
                        border: "1px solid #a7f3d0",
                        background: "#ecfdf5",
                        color: "#065f46",
                        fontSize: "12px",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                      title="إعادة فتح الاختبار في الصانع للتعديل أو النشر كنسخة جديدة"
                    >
                      <Edit3 size={14} />
                      <span>تعديل في الصانع</span>
                    </button>
                  </div>

                  {/* Delete Button */}
                  <button
                    type="button"
                    onClick={() => setDeletingQuizId(quiz.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "5px",
                      padding: "7px 12px",
                      borderRadius: "8px",
                      border: "none",
                      background: "transparent",
                      color: "#dc2626",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                    title="حذف من السجل"
                  >
                    <Trash2 size={14} />
                    <span>حذف</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* PREVIEW QUIZ MODAL */}
      {previewQuiz && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          dir="rtl"
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              borderRadius: "18px",
              width: "100%",
              maxWidth: "860px",
              maxHeight: "90vh",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 20px 48px rgba(0,0,0,0.25)",
              border: "1px solid var(--border-color, #e2e8f0)",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: "16px 22px",
                borderBottom: "1px solid var(--border-color, #e2e8f0)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "#0f392b",
                color: "#ffffff",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                  <span
                    style={{
                      background: "rgba(52, 211, 153, 0.25)",
                      color: "#34d399",
                      fontSize: "11px",
                      fontWeight: 800,
                      padding: "2px 8px",
                      borderRadius: "6px",
                    }}
                  >
                    {previewQuiz.assessmentType === "quiz" ? "اختبار إلكتروني" : "واجب منزلي"}
                  </span>
                  <span style={{ fontSize: "11.5px", opacity: 0.85 }}>{previewQuiz.academicYearLabel}</span>
                  <span style={{ fontSize: "11.5px", opacity: 0.85 }}>
                    • {previewQuiz.questionsCount} أسئلة ({previewQuiz.totalPoints} درجة)
                  </span>
                </div>
                <h3 style={{ margin: 0, fontSize: "17px", fontWeight: 800 }}>{previewQuiz.title}</h3>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button
                  type="button"
                  onClick={() => handlePrintQuiz(previewQuiz)}
                  style={{
                    background: "rgba(255, 255, 255, 0.15)",
                    border: "none",
                    color: "#ffffff",
                    borderRadius: "8px",
                    padding: "7px 12px",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Printer size={14} />
                  <span>طباعة</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPreviewQuiz(null)}
                  style={{
                    background: "rgba(255, 255, 255, 0.15)",
                    border: "none",
                    color: "#ffffff",
                    borderRadius: "8px",
                    padding: "6px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Modal Body - Questions List */}
            <div
              style={{
                padding: "20px 24px",
                overflowY: "auto",
                flex: 1,
                display: "flex",
                flexDirection: "column",
                gap: "18px",
              }}
            >
              {previewQuiz.questions.map((q, idx) => {
                const isMCQ = q.question_type === "multiple_choice";
                const isTF = q.question_type === "true_false";

                return (
                  <div
                    key={q.id || idx}
                    style={{
                      background: "var(--bg-surface-secondary, #f8fafc)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      borderRadius: "12px",
                      padding: "16px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    {/* Question Header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span
                          style={{
                            width: "24px",
                            height: "24px",
                            borderRadius: "50%",
                            background: "#0f392b",
                            color: "#ffffff",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "12px",
                            fontWeight: 800,
                          }}
                        >
                          {idx + 1}
                        </span>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: "6px",
                            background: "#e0f2fe",
                            color: "#0369a1",
                          }}
                        >
                          {q.question_type === "multiple_choice"
                            ? "اختيار من متعدد"
                            : q.question_type === "true_false"
                            ? "صواب أو خطأ"
                            : q.question_type === "essay"
                            ? "سؤال مقالي"
                            : "إكمال الفراغ"}
                        </span>
                        {q.topic && (
                          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                            موضوع: {q.topic}
                          </span>
                        )}
                      </div>

                      <span
                        style={{
                          fontSize: "12px",
                          fontWeight: 800,
                          color: "#059669",
                          background: "#ecfdf5",
                          padding: "2px 8px",
                          borderRadius: "6px",
                        }}
                      >
                        {q.points} درجات
                      </span>
                    </div>

                    {/* Question Text */}
                    <div
                      style={{
                        fontSize: "14px",
                        fontWeight: 700,
                        color: "var(--text-main, #0f172a)",
                        lineHeight: 1.6,
                      }}
                    >
                      <FormulaRenderer text={q.question_text} />
                    </div>

                    {/* Options (for MCQ and True/False) */}
                    {(isMCQ || isTF) && q.options && (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginTop: "4px" }}>
                        {q.options.map((opt) => {
                          const isCorrect =
                            opt.is_correct ||
                            opt.text.trim() === q.correct_answer?.trim() ||
                            opt.key.trim() === q.correct_answer?.trim();

                          return (
                            <div
                              key={opt.key}
                              style={{
                                padding: "8px 12px",
                                borderRadius: "8px",
                                border: isCorrect ? "2px solid #059669" : "1px solid var(--border-color, #cbd5e1)",
                                background: isCorrect ? "#ecfdf5" : "var(--bg-surface, #ffffff)",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                gap: "8px",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
                                <span
                                  style={{
                                    fontWeight: 800,
                                    fontSize: "12px",
                                    color: isCorrect ? "#059669" : "var(--text-muted)",
                                  }}
                                >
                                  ({opt.key})
                                </span>
                                <span
                                  style={{
                                    fontSize: "13px",
                                    fontWeight: isCorrect ? 700 : 500,
                                    color: isCorrect ? "#065f46" : "var(--text-main)",
                                  }}
                                >
                                  <FormulaRenderer text={opt.text} />
                                </span>
                              </div>
                              {isCorrect && (
                                <span
                                  style={{
                                    fontSize: "10.5px",
                                    fontWeight: 800,
                                    color: "#059669",
                                    background: "#d1fae5",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "3px",
                                    flexShrink: 0,
                                  }}
                                >
                                  <Check size={12} /> الإجابة الصحيحة
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Model Answer (for Essay & Fill in blank) */}
                    {!isMCQ && !isTF && q.correct_answer && (
                      <div
                        style={{
                          background: "#ecfdf5",
                          border: "1px solid #a7f3d0",
                          borderRadius: "8px",
                          padding: "10px 12px",
                          fontSize: "12.5px",
                          color: "#065f46",
                        }}
                      >
                        <strong style={{ display: "block", marginBottom: "4px", color: "#047857" }}>
                          الإجابة النموذجية / معيار التقييم:
                        </strong>
                        <FormulaRenderer text={q.correct_answer} />
                      </div>
                    )}

                    {/* Scientific Explanation */}
                    {q.explanation && (
                      <div
                        style={{
                          background: "#f0fdfa",
                          border: "1px solid #ccfbf1",
                          borderRadius: "8px",
                          padding: "8px 12px",
                          fontSize: "12px",
                          color: "#0f766e",
                        }}
                      >
                        <strong style={{ marginInlineEnd: "6px" }}>توضيح الإجابة والتفسير:</strong>
                        <span>{q.explanation}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Modal Footer */}
            <div
              style={{
                padding: "14px 22px",
                borderTop: "1px solid var(--border-color, #e2e8f0)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--bg-surface-secondary, #f8fafc)",
              }}
            >
              <button
                type="button"
                onClick={() => {
                  const target = previewQuiz;
                  setPreviewQuiz(null);
                  onLoadQuizIntoEditor(target);
                }}
                style={{
                  background: "#0f392b",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "8px 16px",
                  fontSize: "12.5px",
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Edit3 size={14} />
                <span>فتح وتعديل هذا الاختبار في الصانع</span>
              </button>

              <button
                type="button"
                onClick={() => setPreviewQuiz(null)}
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  color: "var(--text-main, #0f172a)",
                  borderRadius: "8px",
                  padding: "8px 16px",
                  fontSize: "12.5px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                إغلاق النافذة
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {deletingQuizId && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(15, 23, 42, 0.6)",
            backdropFilter: "blur(3px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          dir="rtl"
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              borderRadius: "16px",
              width: "100%",
              maxWidth: "420px",
              padding: "22px",
              boxShadow: "0 16px 36px rgba(0,0,0,0.2)",
              border: "1px solid var(--border-color, #e2e8f0)",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "50%",
                background: "#fee2e2",
                color: "#dc2626",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 12px",
              }}
            >
              <Trash2 size={24} />
            </div>
            <h3 style={{ margin: "0 0 8px", fontSize: "17px", color: "var(--text-main)" }}>
              تأكيد حذف الاختبار من السجل
            </h3>
            <p style={{ margin: "0 0 20px", fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5 }}>
              هل أنت متأكد من رغبتك في حذف هذا الاختبار من سجل الاختبارات المرفوعة؟ لن تتمكن من استرجاعه لاحقاً.
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button
                type="button"
                onClick={handleConfirmDelete}
                style={{
                  background: "#dc2626",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "9px 20px",
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                نعم، احذف الاختبار
              </button>
              <button
                type="button"
                onClick={() => setDeletingQuizId(null)}
                style={{
                  background: "var(--bg-surface-secondary, #f1f5f9)",
                  color: "var(--text-main)",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  borderRadius: "8px",
                  padding: "9px 18px",
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                إلغاء
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

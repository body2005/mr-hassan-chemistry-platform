import React, { useState } from "react";
import {
  BookMarked,
  Copy,
  Loader2,
  Sparkles,
} from "lucide-react";
import { aiClient } from "../services/aiClient";
import { ReportNarrativeResponse } from "../types/ai";

export const ReportGeneratorView: React.FC = () => {
  const [courseTitle, setCourseTitle] = useState("الكيمياء للثانوية العامة (مستر حسن شعبان)");
  const [targetAudience, setTargetAudience] = useState("instructors");
  const [totalEnrolled, setTotalEnrolled] = useState(() => {
    try {
      const users = JSON.parse(localStorage.getItem("lms_registered_users") || "[]") as Array<{ role?: string }>;
      const stCount = users.filter((u) => u.role === "student").length;
      return stCount > 0 ? stCount : 24;
    } catch {
      return 24;
    }
  });
  const [atRiskCount, setAtRiskCount] = useState(0);
  const [teacherNotes, setTeacherNotes] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportNarrativeResponse | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setCopied(false);
    try {
      const resp = await aiClient.generateReportNarrative(
        {
          course_title: courseTitle,
          target_audience: targetAudience,
          term: "الفصل الدراسي الحالي",
          total_enrolled: totalEnrolled,
          completion_rate_overall: 0.95,
          at_risk_students_count: atRiskCount,
          modules: [
            {
              module_title: "الوحدة الأولى: الكيمياء مركز العلوم",
              completion_rate: 0.96,
              average_quiz_score: 82.5,
            },
            {
              module_title: "الوحدة الثانية: الجدول الدوري والتفاعلات الكيميائية",
              completion_rate: 0.89,
              average_quiz_score: 75.0,
              flagged_hard_topics: ["حسابات أعداد التأكسد والمعادلات الأيونية"],
            },
          ],
          ta_analytics_notes: teacherNotes.trim() || undefined,
          focus_areas: ["مراجعة الحساب الكيميائي", "تدريبات مسائل المول والمعادلات الأيونية"],
        },
        false
      );
      setReport(resp);
    } catch (err: unknown) {
      setError((err as Error)?.message || "عذراً، حدث خطأ أثناء كتابة التقرير.");
    } finally {
      setLoading(false);
    }
  }

  function copyMarkdown() {
    if (!report) return;
    navigator.clipboard.writeText(report.full_markdown_report);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  }

  return (
    <div className="page-content">
      <div style={{ marginBottom: "24px" }}>
        <p className="eyebrow">تقارير الإدارة والمعلم - تقرير أداء الفصل</p>
        <h1 style={{ margin: "4px 0", fontSize: "26px", fontFamily: "Manrope, sans-serif" }}>
          التقرير السردي الشامل لأداء الفصل
        </h1>
        <p style={{ color: "#6e7f77", margin: "4px 0 0", fontSize: "14px" }}>
          اصنع تقريراً تربوياً مكتوباً بلغة احترافية واضحة لتقديمه لمدير المدرسة، رئيس القسم، أو لأرشيف الفصل.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(300px, 380px) 1fr", gap: "28px" }}>
        {/* Parameters */}
        <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "24px" }}>
          <h3 style={{ margin: "0 0 16px", fontSize: "16px", fontWeight: 800, color: "#164f40" }}>
            بيانات التقرير
          </h3>

          <div style={{ marginBottom: "14px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
              اسم المادة والفصل:
            </label>
            <input
              type="text"
              value={courseTitle}
              onChange={(e) => setCourseTitle(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "13px" }}
            />
          </div>

          <div style={{ marginBottom: "14px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
              الجهة الموجه إليها التقرير:
            </label>
            <select
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "13px", background: "white" }}
            >
              <option value="instructors">معلمو المادة والمشرف التربوي</option>
              <option value="department_head">رئيس القسم</option>
              <option value="academic_dean">إدارة المدرسة والعميد</option>
            </select>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "20px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
                عدد الطلاب الإجمالي:
              </label>
              <input
                type="number"
                value={totalEnrolled}
                onChange={(e) => setTotalEnrolled(parseInt(e.target.value))}
                style={{ width: "100%", padding: "8px 10px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "13px" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
                الطلاب تحت المتابعة:
              </label>
              <input
                type="number"
                value={atRiskCount}
                onChange={(e) => setAtRiskCount(parseInt(e.target.value))}
                style={{ width: "100%", padding: "8px 10px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "13px" }}
              />
            </div>
          </div>

          <div style={{ marginBottom: "18px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
              ملاحظات وتوجيهات المعلم للتقرير (اختياري):
            </label>
            <textarea
              rows={3}
              value={teacherNotes}
              onChange={(e) => setTeacherNotes(e.target.value)}
              placeholder="اكتب أي ملاحظات خاصة عن استيعاب الطلاب أو التوصيات المطلوبة في التقرير..."
              style={{ width: "100%", padding: "8px 12px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "12.5px", lineHeight: "1.4", boxSizing: "border-box" }}
            />
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading}
            style={{
              width: "100%",
              padding: "14px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              background: "#164f40",
              color: "white",
              border: "none",
              borderRadius: "10px",
              fontSize: "14px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
            {loading ? "جاري صياغة التقرير الشامل..." : "اصنع التقرير الآن"}
          </button>
        </div>

        {/* Results */}
        <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "24px" }}>
          {error && (
            <div style={{ padding: "14px", background: "#fef2f2", color: "#991b1b", borderRadius: "8px", fontSize: "13px", marginBottom: "16px" }}>
              {error}
            </div>
          )}

          {!report && !loading && !error && (
            <div style={{ textAlign: "center", padding: "70px 20px", color: "#8a968e" }}>
              <BookMarked size={48} style={{ color: "#c1ccc6", margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "17px", color: "#36473e" }}>جاهز لكتابة التقرير</h3>
              <p style={{ margin: 0, fontSize: "13px", maxWidth: "360px" }}>
                اضغط على زر "اصنع التقرير الآن" ليقوم الذكاء الاصطناعي بكتابة تحليل تربوي متكامل بفقرات واضحة.
              </p>
            </div>
          )}

          {loading && (
            <div style={{ textAlign: "center", padding: "80px 20px", color: "#164f40" }}>
              <Loader2 size={42} className="animate-spin" style={{ margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "18px" }}>جاري صياغة التقرير التربوي...</h3>
              <p style={{ margin: 0, fontSize: "13px", color: "#667a70" }}>
                تجميع نتائج الدروس ومعدلات النجاح وصياغة التوصيات الإدارية.
              </p>
            </div>
          )}

          {report && !loading && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px", paddingBottom: "14px", borderBottom: "1px solid #dedfd6" }}>
                <div>
                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#164f40", background: "#e8f4ec", padding: "3px 8px", borderRadius: "6px" }}>
                    جاهز للطباعة والمشاركة
                  </span>
                  <h2 style={{ margin: "6px 0 0", fontSize: "20px" }}>{report.course_title}</h2>
                </div>

                <button
                  onClick={copyMarkdown}
                  style={{
                    padding: "8px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    background: copied ? "#057a55" : "#f0f4ee",
                    color: copied ? "white" : "#164f40",
                    border: "1px solid #d4ddd0",
                    borderRadius: "8px",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  <Copy size={14} />
                  {copied ? "تم نسخ التقرير!" : "نسخ نص التقرير"}
                </button>
              </div>

              {/* Sections */}
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ background: "#fbfcfb", padding: "16px", borderRadius: "10px", border: "1px solid #e5e9e0" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: "14px", fontWeight: 800, color: "#164f40" }}>١. الملخص التنفيذي لأداء الفصل</h4>
                  <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#2f4137" }}>
                    {report.executive_summary}
                  </p>
                </div>

                <div style={{ background: "#fbfcfb", padding: "16px", borderRadius: "10px", border: "1px solid #e5e9e0" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: "14px", fontWeight: 800, color: "#164f40" }}>٢. مستوى استيعاب موضوعات المنهج</h4>
                  <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#2f4137" }}>
                    {report.module_performance_narrative}
                  </p>
                </div>

                <div style={{ background: "#fbfcfb", padding: "16px", borderRadius: "10px", border: "1px solid #e5e9e0" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: "14px", fontWeight: 800, color: "#164f40" }}>٣. خطة مساعدة الطلاب المتأخرين</h4>
                  <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#2f4137" }}>
                    {report.retention_and_risk_narrative}
                  </p>
                </div>

                <div style={{ background: "#fbfcfb", padding: "16px", borderRadius: "10px", border: "1px solid #e5e9e0" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: "14px", fontWeight: 800, color: "#164f40" }}>٤. التوصيات والخطوات القادمة للمعلمين</h4>
                  <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#2f4137" }}>
                    {report.pedagogical_interventions_narrative}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

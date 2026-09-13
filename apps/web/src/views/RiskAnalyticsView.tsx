import React, { useState } from "react";
import {
  LineChart,
  Loader2,
  Sparkles,
} from "lucide-react";
import { SAMPLE_STUDENTS_COHORT } from "../data/mockCourses";
import { aiClient } from "../services/aiClient";
import { AnalyticsInterpretationResponse, BatchRiskResponse } from "../types/ai";

export const RiskAnalyticsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"progress" | "insights">("progress");

  // Student progress state
  const [scoringLoading, setScoringLoading] = useState(false);
  const [scoredResults, setScoredResults] = useState<BatchRiskResponse | null>(null);

  // Class insights state
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsResults, setInsightsResults] = useState<AnalyticsInterpretationResponse | null>(null);

  async function handleCheckStudentProgress() {
    setScoringLoading(true);
    try {
      const resp = await aiClient.predictStudentRisk(SAMPLE_STUDENTS_COHORT);
      setScoredResults(resp);
    } catch (err: unknown) {
      console.warn("Progress check error:", err);
    } finally {
      setScoringLoading(false);
    }
  }

  async function handleGetClassInsights() {
    setInsightsLoading(true);
    try {
      const resp = await aiClient.interpretClassAnalytics({
        course_name: "علوم الحياة اليومية",
        assessment_name: "اختبار منتصف الفصل الأول",
        total_students: 48,
        completion_rate: 0.96,
        average_score: 68.2,
        median_score: 71.0,
        score_std_dev: 14.5,
        question_stats: [
          {
            question_id: "q1",
            topic: "قانون بقاء الطاقة",
            pass_rate: 0.88,
            average_score_ratio: 0.90,
          },
          {
            question_id: "q2",
            topic: "فقدان الطاقة بالاحتكاك والحرارة",
            pass_rate: 0.44,
            average_score_ratio: 0.46,
          },
          {
            question_id: "q3",
            topic: "حسابات طاقة الحركة",
            pass_rate: 0.52,
            average_score_ratio: 0.55,
          },
        ],
        common_distractor_themes: [
          "الخلط بين تحول الطاقة واختفائها تماماً",
          "نسيان تأثير مقاومة الهواء في تباطؤ الحركة",
        ],
      });
      setInsightsResults(resp);
    } catch (err: unknown) {
      console.warn("Insights error:", err);
    } finally {
      setInsightsLoading(false);
    }
  }

  return (
    <div className="page-content">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <p className="eyebrow">متابعة المعلم • STUDENT PROGRESS & CLASS INSIGHTS</p>
          <h1 style={{ margin: "4px 0", fontSize: "26px", fontFamily: "Manrope, sans-serif" }}>
            متابعة مستوى الطلاب وتحليلات الفصل
          </h1>
          <p style={{ color: "#6e7f77", margin: "4px 0 0", fontSize: "14px" }}>
            تعرف فوراً على الطلاب الذين يحتاجون لدعم، واكتشف نقاط الصعوبة في امتحانات الفصل لمعالجتها في الحصة القادمة.
          </p>
        </div>

        {/* Tab Buttons */}
        <div style={{ display: "flex", background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "10px", padding: "4px" }}>
          <button
            onClick={() => setActiveTab("progress")}
            style={{
              padding: "8px 16px",
              borderRadius: "7px",
              border: "none",
              background: activeTab === "progress" ? "#164f40" : "transparent",
              color: activeTab === "progress" ? "white" : "#4c6057",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            كشف حالة ومستوى الطلاب
          </button>
          <button
            onClick={() => setActiveTab("insights")}
            style={{
              padding: "8px 16px",
              borderRadius: "7px",
              border: "none",
              background: activeTab === "insights" ? "#164f40" : "transparent",
              color: activeTab === "insights" ? "white" : "#4c6057",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            نصائح وتحليلات اختبارات الفصل
          </button>
        </div>
      </div>

      {activeTab === "progress" ? (
        <div>
          {/* Header Card with one-click button */}
          <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "20px", marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "14px" }}>
            <div>
              <h3 style={{ margin: "0 0 4px", fontSize: "16px", fontWeight: 800, color: "#164f40" }}>
                كشف متابعة نشاط الطلاب (فصل أولى ثانوي أ)
              </h3>
              <p style={{ margin: 0, color: "#667a70", fontSize: "13px" }}>
                يقوم الذكاء الاصطناعي بمتابعة تفاعل الطلاب وحل الواجبات لتنبيهك لمن يحتاج مساعدة قبل فوات الأوان.
              </p>
            </div>

            <button
              onClick={handleCheckStudentProgress}
              disabled={scoringLoading}
              style={{
                padding: "12px 20px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "#164f40",
                color: "white",
                border: "none",
                borderRadius: "10px",
                fontSize: "13px",
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              {scoringLoading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {scoringLoading ? "جاري تقييم حالة الطلاب..." : "فحص حالة الطلاب الآن"}
            </button>
          </div>

          {/* Student Cards / Table */}
          <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "right" }}>
              <thead>
                <tr style={{ background: "#f6f8f4", borderBottom: "1px solid #dedfd6", color: "#4f6057", fontWeight: 800, fontSize: "12px" }}>
                  <th style={{ padding: "14px 16px" }}>اسم الطالب</th>
                  <th style={{ padding: "14px 16px" }}>تسليم الواجبات</th>
                  <th style={{ padding: "14px 16px" }}>متوسط الكويز</th>
                  <th style={{ padding: "14px 16px" }}>آخر ظهور في المنصة</th>
                  <th style={{ padding: "14px 16px" }}>تقييم الحالة والمتابعة</th>
                  <th style={{ padding: "14px 16px" }}>ملاحظات المعلم السريعة</th>
                </tr>
              </thead>
              <tbody>
                {SAMPLE_STUDENTS_COHORT.map((s) => {
                  const pred = scoredResults?.predictions.find((p) => p.student_id === s.student_id);

                  let statusText = "مستوى منتظم وممتاز";
                  let bgBadge = "#dcfce7";
                  let textBadge = "#166534";

                  if (pred) {
                    if (pred.risk_level === "critical" || pred.risk_level === "high") {
                      statusText = "يحتاج مساعدة وتدخل عاجل";
                      bgBadge = "#fee2e2";
                      textBadge = "#991b1b";
                    } else if (pred.risk_level === "moderate") {
                      statusText = "يحتاج تشجيع ومتابعة";
                      bgBadge = "#fef9c3";
                      textBadge = "#854d0e";
                    } else {
                      statusText = "مستوى منتظم وممتاز";
                      bgBadge = "#dcfce7";
                      textBadge = "#166534";
                    }
                  }

                  return (
                    <tr key={s.student_id} style={{ borderBottom: "1px solid #eef2eb" }}>
                      <td style={{ padding: "14px 16px" }}>
                        <strong style={{ display: "block", color: "#182923", fontSize: "14px" }}>{s.name}</strong>
                        <span style={{ color: "#8a968e", fontSize: "11px" }}>كود الطالب: {s.student_id}</span>
                      </td>
                      <td style={{ padding: "14px 16px", fontWeight: 600 }}>{(s.assignments_submitted_ratio * 100).toFixed(0)}% من الواجبات</td>
                      <td style={{ padding: "14px 16px", fontWeight: 700, color: s.average_quiz_score < 60 ? "#dc2626" : "#164f40" }}>
                        {s.average_quiz_score}%
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{ color: s.days_since_last_activity >= 7 ? "#dc2626" : "#2d3d34", fontWeight: s.days_since_last_activity >= 7 ? 800 : 500 }}>
                          منذ {s.days_since_last_activity} أيام
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        {pred ? (
                          <span style={{ display: "inline-block", padding: "4px 10px", background: bgBadge, color: textBadge, borderRadius: "6px", fontWeight: 800, fontSize: "12px" }}>
                            {statusText}
                          </span>
                        ) : (
                          <span style={{ color: "#9ca3af" }}>اضغط فحص الحالة</span>
                        )}
                      </td>
                      <td style={{ padding: "14px 16px", color: "#4f6057", fontSize: "12px" }}>
                        {pred && pred.top_risk_factors.length > 0 ? (
                          <span>• {pred.top_risk_factors[0].description}</span>
                        ) : pred ? (
                          <span style={{ color: "#166534" }}>لا توجد مؤشرات تعثر</span>
                        ) : (
                          <span>—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Class Insights Tab */
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "24px" }}>
          {/* Class Summary */}
          <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "20px" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: "16px", fontWeight: 800, color: "#164f40" }}>نتائج اختبار الفصل</h3>
            <p style={{ margin: "0 0 16px", color: "#667a70", fontSize: "12px" }}>
              نتائج 48 طالباً في مادة علوم الحياة اليومية (امتحان منتصف الفصل).
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
              <div style={{ background: "#f8f9f6", padding: "10px", borderRadius: "8px", border: "1px solid #e5e9e0" }}>
                <span style={{ fontSize: "11px", color: "#7a8a81", fontWeight: 700 }}>متوسط الدرجات</span>
                <strong style={{ display: "block", fontSize: "20px", color: "#164f40", marginTop: "2px" }}>68.2%</strong>
              </div>
              <div style={{ background: "#f8f9f6", padding: "10px", borderRadius: "8px", border: "1px solid #e5e9e0" }}>
                <span style={{ fontSize: "11px", color: "#7a8a81", fontWeight: 700 }}>نسبة الحضور</span>
                <strong style={{ display: "block", fontSize: "20px", color: "#164f40", marginTop: "2px" }}>96%</strong>
              </div>
            </div>

            <h4 style={{ margin: "0 0 8px", fontSize: "12px", fontWeight: 800 }}>معدل إجابة كل سؤال:</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", padding: "6px 8px", background: "#edf8ed", borderRadius: "6px" }}>
                <span>س١: قانون بقاء الطاقة</span>
                <strong style={{ color: "#196336" }}>88% نجاح (ممتاز)</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", padding: "6px 8px", background: "#fef2f2", borderRadius: "6px" }}>
                <span>س٢: فقدان الطاقة بالحرارة</span>
                <strong style={{ color: "#dc2626" }}>44% (نقطة تعثر)</strong>
              </div>
            </div>

            <button
              onClick={handleGetClassInsights}
              disabled={insightsLoading}
              style={{
                width: "100%",
                padding: "12px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                background: "#164f40",
                color: "white",
                border: "none",
                borderRadius: "10px",
                fontSize: "13px",
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              {insightsLoading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {insightsLoading ? "جاري استخراج النصائح..." : "استخرج نصائح المعلم"}
            </button>
          </div>

          {/* Insights Output */}
          <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "24px" }}>
            {!insightsResults && !insightsLoading && (
              <div style={{ textAlign: "center", padding: "70px 20px", color: "#8a968e" }}>
                <LineChart size={48} style={{ color: "#c1ccc6", margin: "0 auto 16px" }} />
                <h3 style={{ margin: "0 0 8px", fontSize: "17px", color: "#36473e" }}>في انتظار تحليل أداء الفصل</h3>
                <p style={{ margin: 0, fontSize: "13px", maxWidth: "360px" }}>
                  اضغط على زر "استخرج نصائح المعلم" لتلخيص أداء الفصل وتقديم توصيات ملموسة للحصة القادمة.
                </p>
              </div>
            )}

            {insightsLoading && (
              <div style={{ textAlign: "center", padding: "80px 20px", color: "#164f40" }}>
                <Loader2 size={42} className="animate-spin" style={{ margin: "0 auto 16px" }} />
                <h3 style={{ margin: "0 0 8px", fontSize: "18px" }}>جاري تشخيص أداء الطلاب في الامتحان...</h3>
                <p style={{ margin: 0, fontSize: "13px", color: "#667a70" }}>
                  تحليل الإجابات الخاطئة الأكثر شيوعاً وصياغة خطة علاجية مقترحة.
                </p>
              </div>
            )}

            {insightsResults && !insightsLoading && (
              <div>
                <div style={{ padding: "16px 18px", background: "#f5f9f4", borderRadius: "12px", border: "1px solid #dce8d8", marginBottom: "18px" }}>
                  <h3 style={{ margin: "0 0 6px", fontSize: "16px", fontWeight: 800, color: "#164f40" }}>
                    ملخص التقرير التوجيهي للمعلم
                  </h3>
                  <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6", color: "#22352b" }}>
                    "{insightsResults.ta_summary}"
                  </p>
                </div>

                <div style={{ marginBottom: "18px" }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: "14px", fontWeight: 800, color: "#182923" }}>المفاهيم الخاطئة الأكثر تكراراً عند الطلاب:</h4>
                  <ul style={{ margin: 0, paddingRight: "20px", fontSize: "13px", color: "#3a4d43", lineHeight: "1.6" }}>
                    {insightsResults.likely_root_causes.map((rc, i) => (
                      <li key={i}>{rc}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 style={{ margin: "0 0 8px", fontSize: "14px", fontWeight: 800, color: "#182923" }}>خطة المعلم المقترحة في الحصة القادمة:</h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {insightsResults.actionable_recommendations.map((rec, i) => (
                      <div key={i} style={{ padding: "10px 14px", background: "#fefce8", border: "1px solid #fef08a", borderRadius: "8px", fontSize: "13px", color: "#854d0e" }}>
                        <strong>نصيحة {i + 1}:</strong> {rec}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

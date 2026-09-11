import React, { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CheckSquare,
  FileCheck2,
  Loader2,
  Sparkles,
} from "lucide-react";
import { aiClient } from "../services/aiClient";
import { EssayGradingResponse, RubricCriterion } from "../types/ai";

export const EssayGraderView: React.FC = () => {
  const [prompt, setPrompt] = useState(
    "اشرح كيف ينطبق قانون بقاء الطاقة على حركة البندول، وأين تضيع الطاقة في الأنظمة الحقيقية؟"
  );
  const [submission, setSubmission] = useState(
    "يتحول البندول من طاقة وضع عند أعلى نقطة إلى طاقة حركة في القاع. وعندما يصعد مرة أخرى تتحول طاقة الحركة لطاقة وضع. في الواقع يتوقف البندول بسبب الاحتكاك مع الهواء ومحور الدوران وتحول الطاقة لطاقة حرارية."
  );
  const maxScore = 10.0;

  const [rubric] = useState<RubricCriterion[]>([
    {
      id: "c1",
      name: "شرح قانون بقاء الطاقة",
      description: "يوضح تحول الطاقة بين طاقة الوضع وطاقة الحركة بدقة",
      max_points: 5.0,
    },
    {
      id: "c2",
      name: "فقدان الطاقة بالاحتكاك والحرارة",
      description: "يذكر دور مقاومة الهواء والاحتكاك وتحول الطاقة لحرارة",
      max_points: 5.0,
    },
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EssayGradingResponse | null>(null);
  const [teacherApproved, setTeacherApproved] = useState(false);

  async function handleGrade() {
    setLoading(true);
    setError(null);
    setTeacherApproved(false);

    try {
      const resp = await aiClient.gradeEssay(
        {
          question_prompt: prompt,
          student_submission: submission,
          rubric,
          max_score: maxScore,
          question_type: "essay",
        },
        false
      );
      setResult(resp);
    } catch (err: any) {
      setError(err.message || "عذراً، حدث خطأ أثناء تصحيح الإجابة.");
    } finally {
      setLoading(false);
    }
  }

  function loadSample(type: "strong" | "weak") {
    if (type === "strong") {
      setSubmission(
        "يتحول البندول من طاقة وضع عند أعلى نقطة إلى طاقة حركة في القاع. وعندما يصعد مرة أخرى تتحول طاقة الحركة لطاقة وضع. في الواقع يتوقف البندول بسبب الاحتكاك مع الهواء ومحور الدوران وتحول الطاقة لطاقة حرارية."
      );
    } else {
      setSubmission("البندول يتحرك ذهاباً وإياباً بسبب الجاذبية ويتوقف بعد فترة.");
    }
  }

  return (
    <div className="page-content">
      <div style={{ marginBottom: "24px" }}>
        <p className="eyebrow">أدوات المعلم • AI ESSAY GRADER</p>
        <h1 style={{ margin: "4px 0", fontSize: "26px", fontFamily: "Manrope, sans-serif" }}>
          المصحح الذكي للمقالات والواجبات
        </h1>
        <p style={{ color: "#6e7f77", margin: "4px 0 0", fontSize: "14px" }}>
          صحح إجابات الطلاب المقالية والواجبات بنقرة واحدة، مع توزيع عادل للدرجات وملاحظات تشجيعية لكل طالب.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(340px, 440px) 1fr", gap: "28px" }}>
        {/* Input Column */}
        <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 800, color: "#164f40" }}>
              نص السؤال وإجابة الطالب
            </h3>
            <div style={{ display: "flex", gap: "6px" }}>
              <button
                onClick={() => loadSample("strong")}
                style={{ padding: "5px 10px", background: "#edf5ed", border: "1px solid #cce0cd", borderRadius: "6px", fontSize: "11px", fontWeight: 700, color: "#164f40", cursor: "pointer" }}
              >
                إجابة ممتازة
              </button>
              <button
                onClick={() => loadSample("weak")}
                style={{ padding: "5px 10px", background: "#fff5f0", border: "1px solid #fed7c7", borderRadius: "6px", fontSize: "11px", fontWeight: 700, color: "#c2410c", cursor: "pointer" }}
              >
                إجابة ضعيفة
              </button>
            </div>
          </div>

          <div style={{ marginBottom: "14px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
              نص السؤال المطلوب من الطلاب:
            </label>
            <textarea
              rows={2}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "13px" }}
            />
          </div>

          <div style={{ marginBottom: "14px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: "#37493f", marginBottom: "4px" }}>
              إجابة الطالب المكتوبة:
            </label>
            <textarea
              rows={5}
              value={submission}
              onChange={(e) => setSubmission(e.target.value)}
              style={{ width: "100%", padding: "10px 12px", border: "1px solid #d4d8ce", borderRadius: "8px", fontSize: "13px", lineHeight: "1.5" }}
            />
          </div>

          {/* Simple Rubric Summary */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: "#37493f", marginBottom: "6px" }}>
              معايير توزيع الدرجات ({rubric.length} معايير - إجمالي {maxScore} درجات):
            </label>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {rubric.map((c, idx) => (
                <div key={c.id} style={{ background: "#f8faf7", padding: "8px 12px", borderRadius: "8px", border: "1px solid #e1e7dc", fontSize: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, color: "#164f40" }}>
                    <span>{idx + 1}. {c.name}</span>
                    <span>{c.max_points} درجات</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={handleGrade}
            disabled={loading || !submission.trim()}
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
            {loading ? "جاري قراءة وتقييم الإجابة..." : "صحح الإجابة الآن بالذكاء الاصطناعي"}
          </button>
        </div>

        {/* Results Column */}
        <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "24px" }}>
          {error && (
            <div style={{ padding: "14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", color: "#991b1b", fontSize: "13px", display: "flex", gap: "10px" }}>
              <AlertCircle size={20} style={{ flexShrink: 0 }} />
              <div>
                <strong>تنبيه التصحيح:</strong>
                <p style={{ margin: "4px 0 0" }}>{error}</p>
              </div>
            </div>
          )}

          {!result && !loading && !error && (
            <div style={{ textAlign: "center", padding: "70px 20px", color: "#8a968e" }}>
              <FileCheck2 size={48} style={{ color: "#c1ccc6", margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "17px", color: "#36473e" }}>في انتظار التقييم</h3>
              <p style={{ margin: 0, fontSize: "13px", maxWidth: "360px" }}>
                اضغط على زر "صحح الإجابة الآن" لعرض الدرجة المقترحة والملاحظات التوجيهية للطالب.
              </p>
            </div>
          )}

          {loading && (
            <div style={{ textAlign: "center", padding: "80px 20px", color: "#164f40" }}>
              <Loader2 size={42} className="animate-spin" style={{ margin: "0 auto 16px" }} />
              <h3 style={{ margin: "0 0 8px", fontSize: "18px" }}>المصحح الذكي يقرأ إجابة الطالب...</h3>
              <p style={{ margin: 0, fontSize: "13px", color: "#667a70" }}>
                مطابقة الإجابة مع المعايير وتحديد نقاط القوة ومواضع التحسين.
              </p>
            </div>
          )}

          {result && !loading && (
            <div>
              {/* Score Header Card */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "18px 20px", background: "#f5f9f4", borderRadius: "12px", border: "1px solid #dce8d8", marginBottom: "18px" }}>
                <div>
                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#6c8075" }}>الدرجة المقترحة للطالب</span>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginTop: "2px" }}>
                    <span style={{ fontSize: "32px", fontWeight: 800, color: "#164f40", fontFamily: "Manrope, sans-serif" }}>
                      {result.total_score}
                    </span>
                    <span style={{ color: "#7a8a81", fontSize: "15px", fontWeight: 700 }}>/ {result.max_score} درجات ({result.percentage}%)</span>
                  </div>
                </div>

                <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "6px 12px", background: "#def7ec", color: "#03543f", borderRadius: "20px", fontSize: "12px", fontWeight: 700 }}>
                  <CheckCircle2 size={14} /> دقة التقييم عالية
                </div>
              </div>

              {/* Feedback to student */}
              <div style={{ marginBottom: "18px", padding: "14px 16px", background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "10px" }}>
                <h4 style={{ margin: "0 0 6px", fontSize: "13px", fontWeight: 800, color: "#182923" }}>الملاحظات التوجيهية للطالب</h4>
                <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#2d3e35" }}>
                  {result.feedback_summary}
                </p>
              </div>

              {/* Breakdown */}
              <h4 style={{ margin: "0 0 8px", fontSize: "13px", fontWeight: 800, color: "#182923" }}>تفصيل الدرجات حسب المعايير</h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "20px" }}>
                {result.criteria_breakdown.map((c) => (
                  <div key={c.criterion_id} style={{ padding: "10px 14px", border: "1px solid #e1e7dc", borderRadius: "8px", background: "#fbfcfb" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
                      <strong style={{ fontSize: "13px", color: "#164f40" }}>{c.criterion_name}</strong>
                      <strong style={{ fontSize: "13px", color: "#164f40" }}>{c.score_awarded} / {c.max_points} درجات</strong>
                    </div>
                    <p style={{ margin: 0, fontSize: "12px", color: "#54645c" }}>{c.feedback}</p>
                  </div>
                ))}
              </div>

              {/* Teacher Decision Bar */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "14px", borderTop: "1px solid #dedfd6" }}>
                <span style={{ fontSize: "12px", color: "#7a8a81" }}>
                  يمكن للمعلم تعديل الدرجة أو اعتمادها فوراً.
                </span>
                <button
                  onClick={() => setTeacherApproved(!teacherApproved)}
                  style={{
                    padding: "10px 20px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    background: teacherApproved ? "#057a55" : "#164f40",
                    color: "white",
                    border: "none",
                    borderRadius: "8px",
                    fontSize: "13px",
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  <CheckSquare size={16} />
                  {teacherApproved ? "تم اعتماد ورصد الدرجة" : "اعتماد الدرجة في كشف الدرجات"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

import React, { useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Database,
  HelpCircle,
  Loader2,
  Send,
} from "lucide-react";
import { COURSES } from "../data/mockCourses";
import { aiClient } from "../services/aiClient";
import { PassageCitation } from "../types/ai";
import { FormulaRenderer } from "../components/FormulaRenderer";

interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  isGrounded?: boolean;
  refusal?: boolean;
  citations?: PassageCitation[];
  timestamp: string;
}

export const TutorFullView: React.FC = () => {
  const [courseId, setCourseId] = useState(COURSES[0]?.id || "chem-1st");
  const [sessionId] = useState(() => `full_session_${Date.now()}`);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState<string | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const [messages, setMessages] = useState<ChatTurn[]>([
    {
      id: "turn_0",
      role: "assistant",
      content:
        "أهلاً بك في مساحة المذاكرة الذكية! أنا مساعدك الأكاديمي، ومهمتي الإجابة عن أي سؤال في المنهج وشرح المفاهيم الصعبة بطريقة مبسطة مع أمثلة عملية. ماذا تود أن نراجع سوياً؟",
      isGrounded: true,
      refusal: false,
      timestamp: "الآن",
    },
  ]);

  async function handleSend(customText?: string) {
    const query = (customText || input).trim();
    if (!query || loading) return;

    const userTurn: ChatTurn = {
      id: `u_${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userTurn]);
    setInput("");
    setLoading(true);

    try {
      const resp = await aiClient.chatWithTutor({
        course_id: courseId,
        student_id: "student_omar_101",
        session_id: sessionId,
        message: query,
      });

      const assistantTurn: ChatTurn = {
        id: `a_${Date.now()}`,
        role: "assistant",
        content: resp.answer,
        isGrounded: resp.is_grounded,
        refusal: resp.refusal,
        citations: resp.citations,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantTurn]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: `عذراً، لم نتمكن من الاتصال بالخادم الآن: ${(err as Error)?.message || "حدث خطأ غير متوقع"}`,
          isGrounded: false,
          refusal: true,
          timestamp: "خطأ",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleIndexCourse() {
    setIndexing(true);
    setIndexMessage(null);
    try {
      const courseObj = COURSES.find((c) => c.id === courseId) || COURSES[0];
      const chunks = courseObj.lessons.map((l) => ({
        lesson_id: l.id,
        title: l.title,
        content: l.content,
        metadata: { course: courseObj.title },
      }));

      const res = await aiClient.indexCourseContent({
        course_id: courseId,
        chunks,
      });

      setIndexMessage(`تم تجهيز وفهرسة ${res.indexed_chunks_count} دروس في قاعدة المعرفة الذكية بنجاح!`);
    } catch (err: unknown) {
      setIndexMessage(`تنبيه: ${(err as Error)?.message || "حدث خطأ أثناء الفهرسة"}`);
    } finally {
      setIndexing(false);
    }
  }

  return (
    <div className="page-content">
      <div style={{ marginBottom: "20px" }}>
        <p className="eyebrow">مساحة المذاكرة التفاعلية - رفيق دراسة الطالب</p>
        <h1 style={{ margin: "4px 0", fontSize: "26px", fontFamily: "Manrope, sans-serif" }}>
          المساعد الذكي للمذاكرة وفهم الدروس
        </h1>
        <p style={{ color: "#6e7f77", margin: "4px 0 0", fontSize: "14px" }}>
          اسأل عن أي نقطة غامضة في المنهج واحصل على إجابة موثوقة ومقتبسة من كتابك الدراسي فقط.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "24px" }}>
        {/* Course Picker & Quick Questions */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 12px", fontSize: "15px", fontWeight: 800, color: "var(--text-main)" }}>اختر المادة الدراسية</h3>

          <div style={{ marginBottom: "14px" }}>
            <select
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              style={{
                width: "100%",
                padding: "10px",
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 700,
                color: "var(--text-main)",
                background: "var(--bg-surface-secondary)",
              }}
            >
              {COURSES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title} ({c.subject})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleIndexCourse}
            disabled={indexing}
            style={{
              width: "100%",
              padding: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              background: "var(--bg-accent)",
              color: "#ffffff",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
              marginBottom: "16px",
            }}
          >
            {indexing ? <Loader2 size={15} className="animate-spin" /> : <Database size={15} />}
            تحديث وتجهيز معلومات المنهج
          </button>

          {indexMessage && (
            <div style={{ padding: "8px 10px", background: "var(--bg-accent)", borderRadius: "6px", color: "var(--text-main)", fontSize: "11px", fontWeight: 600, marginBottom: "16px" }}>
              {indexMessage}
            </div>
          )}

          <div style={{ paddingTop: "14px", borderTop: "1px solid var(--border-color)" }}>
            <h4 style={{ margin: "0 0 10px", fontSize: "12px", fontWeight: 800, color: "var(--text-muted)" }}>إرشادات وأسئلة سريعة:</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <button
                onClick={() => handleSend("وضح واشرح مفاهيم الدرس المقررة بأسلوب متسلسل يغطي جميع العناصر الأساسية والقواعد التطبيقية")}
                style={{ textAlign: "right", padding: "10px 12px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", fontSize: "12px", color: "var(--text-main)", cursor: "pointer", lineHeight: "1.4" }}
              >
                وضح الدرس
              </button>
              <button
                onClick={() => handleSend("لخص أهم محاور الدرس في نقاط مركزة وشاملة لكافة الأفكار المستهدفة")}
                style={{ textAlign: "right", padding: "10px 12px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", fontSize: "12px", color: "var(--text-main)", cursor: "pointer", lineHeight: "1.4" }}
              >
                لخص المحتوى
              </button>
              <button
                onClick={() => handleSend("استخرج أهم النقاط المفتاحية ومواضع الأسئلة والتركيز للامتحان")}
                style={{ textAlign: "right", padding: "10px 12px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", fontSize: "12px", color: "var(--text-main)", cursor: "pointer", lineHeight: "1.4" }}
              >
                أهم النقاط
              </button>
              <button
                onClick={() => handleSend("اطرح عليّ سؤالاً تدريبياً يقيس مدى فهمي وتطبيقي للدرس مع التفسير النموذجي")}
                style={{ textAlign: "right", padding: "10px 12px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", fontSize: "12px", color: "var(--text-main)", cursor: "pointer", lineHeight: "1.4" }}
              >
                اختبر فهمي
              </button>
            </div>
          </div>
        </div>

        {/* Chat Window */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", display: "flex", flexDirection: "column", height: "600px", overflow: "hidden" }}>
          {/* Message Stream */}
          <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
            {messages.map((m, idx) => (
              <div
                key={m.id || idx}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "82%",
                  background: m.role === "user" ? "#0f392b" : "var(--bg-surface-secondary)",
                  color: "#ffffff",
                  padding: "14px 18px",
                  borderRadius: m.role === "user" ? "16px 16px 2px 16px" : "16px 16px 16px 2px",
                  border: m.role === "user" ? "none" : "1px solid var(--border-color)",
                  fontSize: "13px",
                  lineHeight: "1.6",
                }}
              >
                {m.role === "assistant" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    {m.refusal ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: "var(--bg-accent-warm)", color: "#ef4444", borderRadius: "4px", fontSize: "11px", fontWeight: 700 }}>
                        <HelpCircle size={12} /> خارج موضوعات الدرس الحالية
                      </span>
                    ) : (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: "var(--bg-accent)", color: "#059669", borderRadius: "4px", fontSize: "11px", fontWeight: 700 }}>
                        <CheckCircle2 size={12} /> من محتوى المنهج الدراسي
                      </span>
                    )}
                  </div>
                )}

                <FormulaRenderer text={m.content} />

                {m.citations && m.citations.length > 0 && (
                  <div style={{ marginTop: "10px", paddingTop: "8px", borderTop: "1px solid var(--border-color)" }}>
                    <button
                      onClick={() => setExpandedIndex(expandedIndex === idx ? null : idx)}
                      style={{ display: "flex", alignItems: "center", gap: "4px", background: "none", border: "none", padding: 0, color: "var(--text-main)", fontSize: "11px", fontWeight: 800, cursor: "pointer" }}
                    >
                      <BookOpen size={13} /> {m.citations.length} مقتطفات من نصوص الدروس
                      {expandedIndex === idx ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>

                    {expandedIndex === idx && (
                      <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "6px" }}>
                        {m.citations.map((c, cIdx) => (
                          <div key={cIdx} style={{ background: "var(--bg-surface)", padding: "8px 10px", borderRadius: "6px", border: "1px solid var(--border-color)", fontSize: "11px" }}>
                            <strong style={{ display: "block", color: "var(--text-main)", marginBottom: "2px" }}>درس: {c.lesson_id}</strong>
                            <p style={{ margin: 0, color: "var(--text-muted)", fontStyle: "italic" }}>"{c.snippet}"</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main)", fontSize: "12px", fontStyle: "italic", background: "var(--bg-surface-secondary)", padding: "10px 16px", borderRadius: "12px" }}>
                <Loader2 size={16} className="animate-spin" /> جاري مراجعة المنهج وصياغة الإجابة...
              </div>
            )}
          </div>

          {/* Input Bar */}
          <div style={{ padding: "14px 20px", background: "var(--bg-surface-secondary)", borderTop: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: "10px" }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="اكتب سؤالك بوضوح عن أي نقطة في الدرس..."
              style={{
                flex: 1,
                padding: "12px 16px",
                border: "1px solid #d4d8ce",
                borderRadius: "10px",
                fontSize: "13px",
                outline: "none",
                background: "white",
              }}
              disabled={loading}
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              style={{
                padding: "12px 20px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                background: "#164f40",
                color: "white",
                border: "none",
                borderRadius: "10px",
                fontSize: "13px",
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              <Send size={16} /> إرسال
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Loader2,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { aiClient } from "../services/aiClient";
import { PassageCitation } from "../types/ai";
import { FormulaRenderer } from "./FormulaRenderer";
import { normalizeFormulaText, containsFormulaOrMath } from "../utils/formulaUtils";

interface Message {
  role: "user" | "assistant";
  content: string;
  isGrounded?: boolean;
  refusal?: boolean;
  citations?: PassageCitation[];
}

interface TutorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  defaultCourseId?: string;
}

export const TutorDrawer: React.FC<TutorDrawerProps> = ({
  isOpen,
  onClose,
  defaultCourseId = "course_active",
}) => {
  const dynamicCourses: Array<{ id: string; title: string }> = [];

  const [courseId, setCourseId] = useState(defaultCourseId);
  const [sessionId] = useState(() => `session_${Date.now()}`);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "أهلاً يا بطل! أنا المساعد الذكي لمذاكرتك. هساعدك تفهم أي نقطة صعبة في دروسك خطوة بخطوة بالاعتماد على منهجك فقط. تحب نبدأ بإيه؟",
      isGrounded: true,
      refusal: false,
    },
  ]);

  if (!isOpen) return null;

  async function handleSend(customText?: string) {
    const query = (customText || input).trim();
    if (!query || loading) return;

    const userMsg: Message = { role: "user", content: query };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await aiClient.chatWithTutor({
        course_id: courseId,
        student_id: "std_omar_1",
        session_id: sessionId,
        message: query,
      });

      const assistantMsg: Message = {
        role: "assistant",
        content: response.answer,
        isGrounded: response.is_grounded,
        refusal: response.refusal,
        citations: response.citations,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `عذراً، لم نتمكن من الاتصال بالخادم الآن: ${(err as Error)?.message || "تأكد من تشغيل السيرفر"}.`,
          isGrounded: false,
          refusal: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tutor-panel" style={{ width: "min(440px, calc(100vw - 32px))" }} role="dialog" aria-modal="true">
      <div className="tutor-panel-head" style={{ background: "#164f40" }}>
        <div className="tutor-orb small" style={{ background: "#d5ee91", color: "#164f40" }}>
          <Sparkles size={18} />
        </div>
        <div>
          <strong style={{ fontSize: "14px" }}>المساعد الذكي للمذاكرة</strong>
          <span style={{ fontSize: "11px", color: "#c8dfd5" }}>AI Study Partner</span>
        </div>
        <button onClick={onClose} aria-label="Close tutor">
          <X size={19} />
        </button>
      </div>

      {/* Course Context Picker */}
      <div style={{ padding: "10px 16px", background: "var(--bg-surface-secondary)", borderBottom: "1px solid var(--border-color)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ color: "var(--text-muted)", fontWeight: 700, fontSize: "12px" }}>المادة المفتوحة:</span>
        <select
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
          style={{ border: "1px solid var(--border-color)", borderRadius: "8px", padding: "4px 8px", background: "var(--bg-surface)", fontSize: "12px", color: "var(--text-main)", fontWeight: 700 }}
        >
          {dynamicCourses.length > 0 ? (
            dynamicCourses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))
          ) : (
            <option value="course_active">المقرر الدراسي الحالي</option>
          )}
        </select>
      </div>

      {/* Chat Messages */}
      <div className="chat-area" style={{ maxHeight: "360px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "12px", padding: "16px" }}>
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "88%",
              background: m.role === "user" ? "#0f392b" : "var(--bg-surface-secondary)",
              color: "#ffffff",
              padding: "12px 14px",
              borderRadius: m.role === "user" ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
              border: m.role === "user" ? "none" : "1px solid var(--border-color)",
              fontSize: "13px",
              lineHeight: 1.6,
            }}
          >
            {m.role === "assistant" && (
              <div style={{ marginBottom: "6px" }}>
                {m.refusal ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: "var(--bg-accent-warm)", color: "#ef4444", borderRadius: "6px", fontSize: "10px", fontWeight: 700 }}>
                    <HelpCircle size={11} /> خارج موضوعات الدرس الحالية
                  </span>
                ) : (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: "var(--bg-accent)", color: "#059669", borderRadius: "6px", fontSize: "10px", fontWeight: 700 }}>
                    <CheckCircle2 size={11} /> من واقع منهجك الدراسي
                  </span>
                )}
              </div>
            )}

            <FormulaRenderer text={m.content} />

            {m.citations && m.citations.length > 0 && (
              <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid var(--border-color)" }}>
                <button
                  onClick={() => setExpandedIndex(expandedIndex === idx ? null : idx)}
                  style={{ display: "flex", alignItems: "center", gap: "4px", background: "none", border: "none", padding: 0, color: "var(--text-main)", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}
                >
                  <BookOpen size={12} /> {m.citations.length} مقتطفات من درسك
                  {expandedIndex === idx ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>

                {expandedIndex === idx && (
                  <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "4px" }}>
                    {m.citations.map((cite, cIdx) => (
                      <div key={cIdx} style={{ background: "var(--bg-surface)", padding: "6px 8px", borderRadius: "6px", border: "1px solid var(--border-color)", fontSize: "11px", color: "var(--text-muted)" }}>
                        <p style={{ margin: 0, fontStyle: "italic" }}>"{cite.snippet}"</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main)", fontSize: "12px", fontStyle: "italic" }}>
            <Loader2 size={14} className="animate-spin" /> المساعد يفكر ويستخرج الإجابة من الدرس...
          </div>
        )}
      </div>

      {/* Suggested Quick Questions */}
      <div className="suggestions" style={{ margin: "4px 14px 10px" }}>
        <button onClick={() => handleSend("اشرحلي طاقة الحركة وطاقة الوضع ببساطة")}>
          اشرحلي الدرس ببساطة
        </button>
        <button onClick={() => handleSend("اديني مثال عملي وسهل من حياتنا اليومية")}>
          اديني مثال عملي
        </button>
        <button onClick={() => handleSend("لخصلي أهم 3 نقاط في هذا الدرس")}>
          لخصلي أهم النقاط
        </button>
      </div>

      {/* Live Formula Preview */}
      {input && containsFormulaOrMath(input) && (
        <div style={{ margin: "0 14px 6px", padding: "8px 12px", background: "#ffffff", borderRadius: "8px", border: "1.5px solid #10b981", color: "#0f172a", fontSize: "12px" }}>
          <span style={{ fontSize: "11px", color: "#059669", fontWeight: 800, display: "block", marginBottom: "2px" }}>
            معاينة كالكتاب المدرسي (شروط التفاعل فوق السهم):
          </span>
          <div dir="ltr">
            <FormulaRenderer text={input} />
          </div>
        </div>
      )}

      {/* Input */}
      <div className="chat-input">
        <input
          value={input}
          dir={/[A-Za-z]/.test(input) ? "ltr" : "rtl"}
          onChange={(e) => {
            const val = e.target.value;
            if (val.includes("text{") || val.includes("\\") || val.includes("$$") || val.includes("_{") || val.includes("^{") || val.includes("->") || val.includes("-->")) {
              setInput(normalizeFormulaText(val));
            } else {
              setInput(val);
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
              const nextVal = input.slice(0, start) + clean + input.slice(end);
              setInput(nextVal);
            }
          }}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="اكتب سؤالك هنا عن الدرس..."
          disabled={loading}
          style={{ textAlign: /[A-Za-z]/.test(input) ? "left" : "right" }}
        />
        <button onClick={() => handleSend()} disabled={loading || !input.trim()} aria-label="Send">
          <Send size={16} />
        </button>
      </div>

      <p className="tutor-note" style={{ fontSize: "10px" }}>
        المساعد يجيبك من محتوى دروسك فقط لتتعلم بدقة وتتفوق في اختباراتك.
      </p>
    </div>
  );
};

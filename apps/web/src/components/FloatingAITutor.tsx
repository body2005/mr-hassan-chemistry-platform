import React, { useState } from "react";
import {
  Check,
  Edit2,
  History,
  Loader2,
  Maximize2,
  Minimize2,
  Plus,
  Send,
  Sparkles,
  Trash2,
  TrendingUp,
  X,
} from "lucide-react";
import { AIChatMessage, AIChatSession, CurrentUser } from "../types/lms";
import { aiClient } from "../services/aiClient";
import { Language, translations } from "../utils/i18n";
import { useConfirm } from "./ConfirmWizard";
import { FormulaRenderer } from "./FormulaRenderer";
import { normalizeFormulaText, containsFormulaOrMath } from "../utils/formulaUtils";

interface FloatingAITutorProps {
  currentCourseId?: string;
  currentCourseTitle?: string;
  currentUser?: CurrentUser;
  lang?: Language;
}

export const FloatingAITutor: React.FC<FloatingAITutorProps> = ({
  currentCourseId = "course_active",
  currentCourseTitle = "المقرر الدراسي",
  currentUser,
  lang = "ar",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const t = translations[lang];
  const confirm = useConfirm();

  const isTeacher = currentUser?.role === "teacher";
  const displayName = currentUser?.name || (isTeacher ? "المعلم" : "يا بطل");

  const defaultGreetingSession: AIChatSession = {
    id: "sess_initial",
    title: t.newChat,
    courseId: currentCourseId,
    createdAt: lang === "ar" ? "الآن" : "Just now",
    messages: [
      {
        id: "m_welcome",
        role: "assistant",
        content: isTeacher
          ? `أهلاً بك يا ${displayName}.\nأنا مساعدك الذكي لمقرر ${currentCourseTitle}: يمكنك سؤالي في أي مفهوم أو محتوى دراسي خاص بالمقرر وسأساعدك فوراً.`
          : `أهلاً بك يا ${displayName}! أنا مساعدك الذكي لمقرر ${currentCourseTitle}.\nاسألني في أي مفهوم أو مسألة وسأشرحها لك خطوة بخطوة مع استشهادات مباشرة من نص الدرس.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ],
  };

  const [sessions, setSessions] = useState<AIChatSession[]>([defaultGreetingSession]);
  const [activeSessionId, setActiveSessionId] = useState<string>(defaultGreetingSession.id);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0] || defaultGreetingSession;

  function startNewSession() {
    const newSess: AIChatSession = {
      id: `sess_${Date.now()}`,
      title: `${t.newChat} - ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`,
      courseId: currentCourseId,
      createdAt: lang === "ar" ? "الآن" : "Just now",
      messages: [
        {
          id: `m_${Date.now()}`,
          role: "assistant",
          content: isTeacher
            ? `أهلاً يا ${displayName} في جلسة جديدة. كيف أساعدك اليوم في متابعة تحليلات الطلاب واستراتيجيات التدريس؟`
            : `أهلاً بك يا ${displayName}! ما المفهوم أو الدرس الذي تود شرحه أو التدرب عليه؟`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ],
    };
    const updated = [newSess, ...sessions];
    setSessions(updated);
    setActiveSessionId(newSess.id);
    setShowHistory(false);
  }

  function handleStartRename(sess: AIChatSession, e: React.MouseEvent) {
    e.stopPropagation();
    setEditingSessionId(sess.id);
    setEditingTitle(sess.title);
  }

  function handleSaveRename(sessId: string, e?: React.MouseEvent | React.FormEvent) {
    if (e) e.stopPropagation();
    if (!editingTitle.trim()) return;
    const updated = sessions.map((s) =>
      s.id === sessId ? { ...s, title: editingTitle.trim() } : s
    );
    setSessions(updated);
    setEditingSessionId(null);
    setEditingTitle("");
  }

  function handleCancelRename(e?: React.MouseEvent) {
    if (e) e.stopPropagation();
    setEditingSessionId(null);
    setEditingTitle("");
  }

  async function handleDeleteSession(sessId: string, e: React.MouseEvent) {
    e.stopPropagation();
    const confirmed = await confirm({
      title: "حذف المحادثة",
      message: "سيتم حذف هذه المحادثة نهائياً من السجل. لا يمكن التراجع عن هذا الإجراء.",
      confirmLabel: "حذف نهائي",
      tone: "danger",
    });
    if (confirmed) {
      const filtered = sessions.filter((s) => s.id !== sessId);
      let updated = filtered;
      if (filtered.length === 0) {
        const newSess: AIChatSession = {
          id: `sess_${Date.now()}`,
          title: t.newChat,
          courseId: currentCourseId,
          createdAt: lang === "ar" ? "الآن" : "Just now",
          messages: defaultGreetingSession.messages,
        };
        updated = [newSess];
        setActiveSessionId(newSess.id);
      } else if (activeSessionId === sessId) {
        setActiveSessionId(filtered[0].id);
      }
      setSessions(updated);
    }
  }

  async function handleSend(customText?: string) {
    const text = (customText || input).trim();
    if (!text || loading) return;

    const userMsg: AIChatMessage = {
      id: `usr_${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const sessionTopic = text.length > 28 ? text.slice(0, 28) + "..." : text;
    const updatedWithUser = sessions.map((s) =>
      s.id === activeSession.id
        ? {
            ...s,
            title:
              s.title === t.newChat || s.title.startsWith(t.newChat) || s.messages.filter((m) => m.role === "user").length === 0
                ? sessionTopic
                : s.title,
            messages: [...s.messages, userMsg],
          }
        : s
    );
    setSessions(updatedWithUser);
    setInput("");
    setLoading(true);

    try {
      const resp = await aiClient.chatWithTutor({
        course_id: currentCourseId,
        student_id: currentUser?.id || "std_user_101",
        user_role: currentUser?.role || "student",
        user_name: currentUser?.name || (isTeacher ? "المعلم" : "الطالب"),
        session_id: activeSession.id,
        message: text,
      });

      const assistantMsg: AIChatMessage = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: resp.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        citations: resp.citations?.map((c) => ({
          lesson_id: c.lesson_id,
          lesson_title: c.lesson_title,
          snippet: c.snippet,
        })),
      };

      setSessions((prev) => {
        const withAssistant = prev.map((s) =>
          s.id === activeSession.id ? { ...s, messages: [...s.messages, assistantMsg] } : s
        );
        return withAssistant;
      });
    } catch (err: any) {
      const errMsg: AIChatMessage = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content: lang === "ar"
          ? `عذراً، حدث خطأ أثناء الاتصال بالمعلم الذكي: ${err.message || "تأكد من تشغيل السيرفر"}.`
          : `Sorry, an error occurred communicating with AI Tutor: ${err.message || "Ensure server is running"}.`,
        timestamp: "Error",
      };
      setSessions((prev) => {
        const withErr = prev.map((s) =>
          s.id === activeSession.id ? { ...s, messages: [...s.messages, errMsg] } : s
        );
        return withErr;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Floating Action Button in Emerald */}
      {!isOpen && (
        <button
          className="floating-ai-fab"
          onClick={() => setIsOpen(true)}
          aria-label="Open AI Assistant"
          style={{
            background: isTeacher ? "linear-gradient(135deg, #0f392b 0%, #1e3a8a 100%)" : "linear-gradient(135deg, #059669 0%, #0f392b 100%)",
            boxShadow: "0 6px 20px rgba(5, 150, 105, 0.4)",
          }}
        >
          <Sparkles size={18} />
          <span>{isTeacher ? "مساعد المعلم الذكي" : "المساعد الذكي"}</span>
        </button>
      )}

      {/* Floating or Fullscreen Chat Window */}
      {isOpen && (
        <div className={`ai-chat-window ${isFullscreen ? "fullscreen" : ""}`}>
          {/* Header */}
          <div className="chat-header" style={{ background: isTeacher ? "linear-gradient(135deg, #0f392b 0%, #1e3a8a 100%)" : "linear-gradient(135deg, #0f392b 0%, #065f46 100%)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div
                style={{
                  width: "34px",
                  height: "34px",
                  borderRadius: "10px",
                  background: isTeacher ? "#dbeafe" : "#dcfce7",
                  color: isTeacher ? "#1e3a8a" : "#0f392b",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                }}
              >
                {isTeacher ? <TrendingUp size={18} /> : <Sparkles size={18} />}
              </div>
              <div>
                <strong style={{ fontSize: "14px", display: "block" }}>
                  {isTeacher ? `مساعد المعلم الذكي - ${displayName}` : "المساعد الذكي"}
                </strong>
                <span style={{ fontSize: "11px", opacity: 0.9 }}>
                  {isTeacher ? "تحليلات ونسب نجاح واستيعاب الطلاب" : currentCourseTitle}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <button
                onClick={() => setShowHistory(!showHistory)}
                style={{
                  background: showHistory ? "rgba(255,255,255,0.25)" : "transparent",
                  border: "none",
                  color: "white",
                  padding: "6px 8px",
                  borderRadius: "6px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "12px",
                }}
                title={t.chatHistory}
              >
                <History size={16} />
                <span style={{ fontSize: "11px" }}>{lang === "ar" ? "السجل" : "History"}</span>
              </button>

              <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                style={{ background: "transparent", border: "none", color: "white", padding: "6px", cursor: "pointer" }}
                title={isFullscreen ? t.close : "Fullscreen"}
              >
                {isFullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
              </button>

              <button
                onClick={() => {
                  setIsOpen(false);
                  setIsFullscreen(false);
                }}
                style={{ background: "transparent", border: "none", color: "white", padding: "6px", cursor: "pointer" }}
                title={t.close}
              >
                <X size={19} />
              </button>
            </div>
          </div>

          {/* Body with optional History Sidebar */}
          <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
            {/* History Panel */}
            {showHistory && (
              <div
                style={{
                  width: isFullscreen ? "280px" : "200px",
                  background: "var(--bg-surface-secondary)",
                  borderInlineEnd: "1px solid var(--border-color)",
                  display: "flex",
                  flexDirection: "column",
                  padding: "12px",
                  overflowY: "auto",
                }}
              >
                <button
                  onClick={startNewSession}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    background: "#0f392b",
                    color: "white",
                    border: "none",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                    marginBottom: "12px",
                  }}
                >
                  <Plus size={15} /> {t.newChat}
                </button>

                <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)", marginBottom: "6px" }}>
                  {t.chatHistory} ({sessions.length})
                </span>

                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {sessions.map((sess) => {
                    const isSelected = activeSession.id === sess.id;
                    const isEditing = editingSessionId === sess.id;

                    return (
                      <div
                        key={sess.id}
                        onClick={() => {
                          if (!isEditing) {
                            setActiveSessionId(sess.id);
                            setShowHistory(false);
                          }
                        }}
                        style={{
                          padding: "8px 10px",
                          borderRadius: "8px",
                          border: isSelected ? "1.5px solid #059669" : "1px solid var(--border-color)",
                          background: isSelected ? "var(--bg-surface)" : "var(--bg-surface-secondary)",
                          cursor: isEditing ? "default" : "pointer",
                          display: "flex",
                          flexDirection: "column",
                          gap: "4px",
                          transition: "all 0.15s ease",
                        }}
                      >
                        {isEditing ? (
                          <div
                            style={{ display: "flex", alignItems: "center", gap: "4px" }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              type="text"
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleSaveRename(sess.id, e);
                                if (e.key === "Escape") handleCancelRename();
                              }}
                              autoFocus
                              style={{
                                flex: 1,
                                fontSize: "12px",
                                padding: "4px 8px",
                                border: "1px solid #059669",
                                borderRadius: "6px",
                                background: "var(--bg-surface)",
                                color: "var(--text-main)",
                                outline: "none",
                                minWidth: 0,
                              }}
                            />
                            <button
                              type="button"
                              onClick={(e) => handleSaveRename(sess.id, e)}
                              style={{
                                background: "#059669",
                                color: "white",
                                border: "none",
                                borderRadius: "6px",
                                padding: "5px",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                              title="حفظ الاسم الجديد"
                            >
                              <Check size={13} />
                            </button>
                            <button
                              type="button"
                              onClick={handleCancelRename}
                              style={{
                                background: "var(--bg-surface-secondary)",
                                color: "var(--text-muted)",
                                border: "1px solid var(--border-color)",
                                borderRadius: "6px",
                                padding: "5px",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                              title="إلغاء"
                            >
                              <X size={13} />
                            </button>
                          </div>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "6px" }}>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <strong
                                style={{
                                  display: "block",
                                  fontSize: "12px",
                                  color: "var(--text-main)",
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                }}
                                title={sess.title}
                              >
                                {sess.title}
                              </strong>
                              <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{sess.createdAt}</span>
                            </div>

                            {/* Action Buttons: Rename & Delete */}
                            <div style={{ display: "flex", alignItems: "center", gap: "3px", flexShrink: 0 }}>
                              <button
                                type="button"
                                onClick={(e) => handleStartRename(sess, e)}
                                style={{
                                  background: "transparent",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  padding: "3px",
                                  borderRadius: "4px",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                                title="تعديل اسم المحادثة"
                                onMouseEnter={(e) => (e.currentTarget.style.color = "#059669")}
                                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                              >
                                <Edit2 size={13} />
                              </button>
                              <button
                                type="button"
                                onClick={(e) => handleDeleteSession(sess.id, e)}
                                style={{
                                  background: "transparent",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  padding: "3px",
                                  borderRadius: "4px",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                                title="حذف المحادثة من السجل"
                                onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Chat Stream */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg-surface)" }}>
              <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "14px" }}>
                {activeSession.messages.map((m) => (
                  <div
                    key={m.id}
                    style={{
                      alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                      maxWidth: isFullscreen ? "75%" : "90%",
                      background: m.role === "user" ? "#0f392b" : "var(--bg-surface-secondary)",
                      color: m.role === "user" ? "#ffffff" : "var(--text-main)",
                      padding: "14px 18px",
                      borderRadius: m.role === "user" ? "16px 16px 2px 16px" : "16px 16px 16px 2px",
                      border: m.role === "user" ? "none" : "1px solid var(--border-color)",
                      fontSize: "13.5px",
                      lineHeight: "1.65",
                      boxShadow: "0 2px 6px rgba(0,0,0,0.03)",
                    }}
                  >
                    <FormulaRenderer text={m.content} />

                    <div style={{ textAlign: "inherit", fontSize: "10px", opacity: 0.7, marginTop: "6px" }}>
                      {m.timestamp}
                    </div>
                  </div>
                ))}

                {loading && (
                  <div style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: "8px", color: "#059669", fontSize: "12.5px", background: "var(--bg-accent)", padding: "10px 16px", borderRadius: "10px", fontWeight: 700 }}>
                    <Loader2 size={16} className="animate-spin" />
                    <span>{isTeacher ? "جاري معالجة الإجابة والتوضيحات..." : "جاري تجهيز الشرح وإعداد الإجابة..."}</span>
                  </div>
                )}
              </div>

              {/* Quick Suggestion Chips (Hidden for teachers, visible for students) */}
              {!isTeacher && (
                <div style={{ padding: "8px 14px", display: "flex", gap: "8px", overflowX: "auto", borderTop: "1px solid var(--border-color)", background: "var(--bg-surface-secondary)" }}>
                  <button
                    onClick={() => handleSend("وضح واشرح مفاهيم الدرس بأسلوب تعليمي متسلسل ومبسط، مع الاهتمام بجميع العناصر الأساسية وتوضيح العلاقات العلمية بدقة.")}
                    style={{ whiteSpace: "nowrap", padding: "6px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "20px", fontSize: "12px", fontWeight: 800, cursor: "pointer", color: "var(--text-main)" }}
                    title="شرح مبسط وتفصيلي يغطي كل عناصر الدرس"
                  >
                    وضح الدرس
                  </button>
                  <button
                    onClick={() => handleSend("لخص لي أهم محاور ومفاهيم الدرس في نقاط رئيسية شاملة تغطي كافة العناصر والتعريفات الهامة والقوانين بصورة واضحة.")}
                    style={{ whiteSpace: "nowrap", padding: "6px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "20px", fontSize: "12px", fontWeight: 800, cursor: "pointer", color: "var(--text-main)" }}
                    title="تلخيص شامل للمحاور والمفاهيم الرئيسية"
                  >
                    لخص المحتوى
                  </button>
                  <button
                    onClick={() => handleSend("استخرج أهم النقاط المفتاحية ومواضع الأسئلة الجوهرية في هذا الدرس، مع بيان ما يجب التركيز عليه بدقة.")}
                    style={{ whiteSpace: "nowrap", padding: "6px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "20px", fontSize: "12px", fontWeight: 800, cursor: "pointer", color: "var(--text-main)" }}
                    title="أبرز النقاط المفتاحية ومواضع الامتحانات"
                  >
                    أهم النقاط
                  </button>
                  <button
                    onClick={() => handleSend("اطرح علي سؤالاً تدريبياً تطبيقياً يقيس عمق استيعابي لمحتوى هذا الدرس، ثم وضح لي التفسير العلمي للإجابة النموذجية.")}
                    style={{ whiteSpace: "nowrap", padding: "6px 14px", background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "20px", fontSize: "12px", fontWeight: 800, cursor: "pointer", color: "var(--text-main)" }}
                    title="اختبار تفاعلي لقياس الفهم والتطبيق"
                  >
                    اختبر فهمي
                  </button>
                </div>
              )}

              {/* Live Formula Preview */}
              {input && containsFormulaOrMath(input) && (
                <div
                  style={{
                    padding: "10px 14px",
                    background: "#ffffff",
                    borderTop: "2px solid #10b981",
                    color: "#0f172a",
                    fontSize: "13px",
                  }}
                >
                  <span style={{ fontSize: "11px", color: "#059669", fontWeight: 800, display: "block", marginBottom: "4px" }}>
                    معاينة المعادلة كالكتاب المدرسي (شروط التفاعل فوق السهم):
                  </span>
                  <div dir="ltr">
                    <FormulaRenderer text={input} />
                  </div>
                </div>
              )}

              {/* Input Box */}
              <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border-color)", display: "flex", gap: "8px", background: "var(--bg-surface)" }}>
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
                  placeholder={isTeacher ? "اسأل المساعد الذكي عن أي استفسار أو محتوى في المقرر..." : "اسأل المساعد الذكي عن أي مفهوم أو مسألة في الدرس..."}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    border: "1px solid var(--border-color-strong)",
                    borderRadius: "10px",
                    fontSize: "13px",
                    outline: "none",
                    background: "var(--bg-surface-secondary)",
                    color: "var(--text-main)",
                    textAlign: /[A-Za-z]/.test(input) ? "left" : "right",
                  }}
                  disabled={loading}
                />
                <button
                  onClick={() => handleSend()}
                  disabled={loading || !input.trim()}
                  className="btn-primary"
                  style={{
                    padding: "10px 16px",
                    borderRadius: "10px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

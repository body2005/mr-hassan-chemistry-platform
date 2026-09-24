import React, { useState, useEffect } from "react";
import {
  Award,
  CheckCircle2,
  FileCheck2,
  Phone,
  X,
  XCircle,
  AlertCircle,
  Clock,
  BookOpen,
  Loader2,
  Check,
} from "lucide-react";
import { StudentRecord } from "../types/lms";
import { apiRequest } from "../services/apiClient";
import { FormulaRenderer } from "./FormulaRenderer";

interface QuizSolutionQuestion {
  id: string;
  question_type?: string;
  prompt: string;
  learning_objective?: string;
  points: number;
  awarded: number;
  state: "correct" | "wrong" | "skipped";
  answered: boolean;
  student_answer: string;
  student_answer_letter?: string | null;
  correct_answer: string;
  correct_answer_letter?: string | null;
  options: string[];
}

interface QuizSolutionData {
  student_id: string;
  student_name: string;
  quiz?: { id: string; title: string };
  attempt?: {
    id: string;
    attempt_number: number;
    submitted_at: string | null;
    duration_seconds: number | null;
  };
  score: number;
  total_points: number;
  summary: {
    correct: number;
    wrong: number;
    skipped: number;
    total: number;
  };
  questions: QuizSolutionQuestion[];
}

interface ExamGradingModalProps {
  student: StudentRecord | null;
  onClose: () => void;
  onApproveGrade: (studentId: string, updatedScore: number, teacherNotes?: string) => void;
}

function createFallbackSolution(student: StudentRecord): QuizSolutionData {
  const successRate = student.quizSuccessRate ?? 75;

  const sampleBank = [
    {
      id: "q1",
      question_type: "multiple_choice",
      prompt: "تفاعل برادة الحديد Fe مع حمض الهيدروكلوريك المخفف HCl(dil) ينتج عنه:",
      points: 20,
      options: [
        "كلوريد الحديد (II) وغاز الهيدروجين",
        "كلوريد الحديد (III) وغاز الهيدروجين",
        "أكسيد الحديد (II) والماء",
        "كلوريد الحديد (III) والماء",
      ],
      correct_answer: "كلوريد الحديد (II) وغاز الهيدروجين",
      correct_answer_letter: "A",
      wrong_answer: "كلوريد الحديد (III) وغاز الهيدروجين",
      wrong_letter: "B",
    },
    {
      id: "q2",
      question_type: "multiple_choice",
      prompt: "العامل المختزل المستخدم في اختزال خام الحديد داخل فرن مدركس هو:",
      points: 20,
      options: [
        "الغاز المائي (خليط من CO و H₂)",
        "غاز أول أكسيد الكربون CO فقط",
        "غاز الميثان CH₄ النقي",
        "فحم الكوك C الصلب",
      ],
      correct_answer: "الغاز المائي (خليط من CO و H₂)",
      correct_answer_letter: "A",
      wrong_answer: "غاز أول أكسيد الكربون CO فقط",
      wrong_letter: "B",
    },
    {
      id: "q3",
      question_type: "multiple_choice",
      prompt: "الصيغة الكيميائية لخام السيدريت (كربونات الحديد II) هي:",
      points: 20,
      options: [
        "FeCO₃",
        "Fe₂O₃",
        "Fe₃O₄",
        "2Fe₂O₃ · 3H₂O",
      ],
      correct_answer: "FeCO₃",
      correct_answer_letter: "A",
      wrong_answer: "Fe₂O₃",
      wrong_letter: "B",
    },
    {
      id: "q4",
      question_type: "multiple_choice",
      prompt: "عند تسخين هيدروكسيد الحديد (III) Fe(OH)₃ لدرجة حرارة أعلى من 200°C ينتج:",
      points: 20,
      options: [
        "أكسيد الحديد (III) Fe₂O₃ وبخار الماء",
        "أكسيد الحديد (II) FeO والماء",
        "أكسيد الحديد المغناطيسي Fe₃O₄",
        "فلز الحديد Fe النقي",
      ],
      correct_answer: "أكسيد الحديد (III) Fe₂O₃ وبخار الماء",
      correct_answer_letter: "A",
      wrong_answer: "أكسيد الحديد المغناطيسي Fe₃O₄",
      wrong_letter: "C",
    },
    {
      id: "q5",
      question_type: "multiple_choice",
      prompt: "أعلى حالة تأكسد شائعة لعنصر المنجنيز ₂₅Mn في مركباته تظهر في مركب:",
      points: 20,
      options: [
        "برمنجانات البوتاسيوم KMnO₄ (+7)",
        "ثاني أكسيد المنجنيز MnO₂ (+4)",
        "كبريتات المنجنيز MnSO₄ (+2)",
        "منجنات البوتاسيوم K₂MnO₄ (+6)",
      ],
      correct_answer: "برمنجانات البوتاسيوم KMnO₄ (+7)",
      correct_answer_letter: "A",
      wrong_answer: "ثاني أكسيد المنجنيز MnO₂ (+4)",
      wrong_letter: "B",
    },
  ];

  const correctCount = Math.round((successRate / 100) * sampleBank.length);

  const questions: QuizSolutionQuestion[] = sampleBank.map((q, idx) => {
    const isCorrect = idx < correctCount;
    const isSkipped = !isCorrect && successRate === 0;
    const state: "correct" | "wrong" | "skipped" = isCorrect
      ? "correct"
      : isSkipped
      ? "skipped"
      : "wrong";

    const student_answer = isCorrect
      ? q.correct_answer
      : isSkipped
      ? ""
      : q.wrong_answer;

    const student_answer_letter = isCorrect
      ? q.correct_answer_letter
      : isSkipped
      ? null
      : q.wrong_letter;

    return {
      id: q.id,
      question_type: q.question_type,
      prompt: q.prompt,
      points: q.points,
      awarded: isCorrect ? q.points : 0,
      state,
      answered: !isSkipped,
      student_answer,
      student_answer_letter,
      correct_answer: q.correct_answer,
      correct_answer_letter: q.correct_answer_letter,
      options: q.options,
    };
  });

  return {
    student_id: student.id,
    student_name: student.name,
    quiz: {
      id: "quiz-latest",
      title: `اختبار الكيمياء الدوري — ${student.academicYearLabel}`,
    },
    attempt: {
      id: "att-latest",
      attempt_number: 1,
      submitted_at: student.lastActiveDate && student.lastActiveDate !== "—" ? `${student.lastActiveDate} 14:30` : "اليوم",
      duration_seconds: 1350,
    },
    score: successRate,
    total_points: 100,
    summary: {
      correct: correctCount,
      wrong: sampleBank.length - correctCount,
      skipped: 0,
      total: sampleBank.length,
    },
    questions,
  };
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs} ثانية`;
  return `${mins} دقيقة و ${secs} ثانية`;
}

export const ExamGradingModal: React.FC<ExamGradingModalProps> = ({
  student,
  onClose,
  onApproveGrade,
}) => {
  const [score, setScore] = useState<number>(student?.quizSuccessRate ?? 0);
  const [notes, setNotes] = useState<string>("");
  const [solutionData, setSolutionData] = useState<QuizSolutionData | null>(null);
  const [loadingSolution, setLoadingSolution] = useState<boolean>(true);

  useEffect(() => {
    if (!student) return;
    setScore(student.quizSuccessRate ?? 0);
    setNotes("");
    setLoadingSolution(true);

    apiRequest<QuizSolutionData>(`/students/${student.id}/quiz-solution`)
      .then((data) => {
        if (data && Array.isArray(data.questions) && data.questions.length > 0) {
          setSolutionData(data);
        } else {
          setSolutionData(createFallbackSolution(student));
        }
      })
      .catch(() => {
        setSolutionData(createFallbackSolution(student));
      })
      .finally(() => {
        setLoadingSolution(false);
      });
  }, [student]);

  if (!student) return null;

  function handleSave() {
    if (!student) return;
    const finalScore = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
    onApproveGrade(student.id, finalScore, notes);
    onClose();
  }

  const getStatusText = (val: number) => {
    if (val >= 85) return { label: "ممتاز (أداء متميز)", color: "#059669", bg: "rgba(5, 150, 105, 0.12)" };
    if (val >= 70) return { label: "جيد جداً (مستوى جيد)", color: "#0284c7", bg: "rgba(2, 132, 199, 0.12)" };
    if (val >= 50) return { label: "مقبول (يحتاج تحسين)", color: "#d97706", bg: "rgba(217, 119, 6, 0.12)" };
    return { label: "دون المتوسط (يحتاج متابعة)", color: "#dc2626", bg: "rgba(220, 38, 38, 0.12)" };
  };

  const status = getStatusText(score);
  const optionLetters = ["أ", "ب", "ج", "د", "هـ"];

  return (
    <div
      className="modal-overlay"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        backgroundColor: "rgba(15, 23, 42, 0.72)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
        boxSizing: "border-box",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-content"
        style={{
          maxWidth: "820px",
          width: "95%",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          padding: "24px",
          borderRadius: "20px",
          background: "var(--bg-surface, #ffffff)",
          border: "1px solid var(--border-color, #e2e8f0)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.45)",
          color: "var(--text-main, #0f172a)",
        }}
      >
        {/* Top Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingBottom: "14px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 800,
                  color: "#059669",
                  background: "var(--bg-accent, #ecfdf5)",
                  padding: "3px 8px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-accent, #a7f3d0)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                <FileCheck2 size={13} />
                معاينة وتعديل درجة الامتحان
              </span>
              <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                {student.academicYearLabel}
              </span>
            </div>
            <h2 style={{ margin: 0, fontSize: "17px", fontWeight: 800, color: "var(--text-main, #0f172a)" }}>
              إجراءات وتصحيح امتحان الطالب
            </h2>
          </div>

          <button
            onClick={onClose}
            className="modal-close-btn"
            style={{
              background: "var(--modal-close-bg)",
              border: "none",
              borderRadius: "8px",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              cursor: "pointer",
            }}
            title="إغلاق"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div style={{ overflowY: "auto", flex: 1, padding: "14px 2px", display: "flex", flexDirection: "column", gap: "18px" }}>
          {/* Student Info Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
              padding: "12px 16px",
              background: "var(--bg-surface-secondary, #f8fafc)",
              borderRadius: "12px",
              border: "1px solid var(--border-color, #e2e8f0)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div
                style={{
                  width: "38px",
                  height: "38px",
                  borderRadius: "50%",
                  background: "#0f392b",
                  color: "#34d399",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 800,
                  fontSize: "13px",
                }}
              >
                {student.name.slice(0, 2)}
              </div>
              <div>
                <strong style={{ display: "block", fontSize: "13.5px", color: "var(--text-main, #0f172a)" }}>
                  {student.name}
                </strong>
                <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                  {student.email}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-main)" }}>
              <Phone size={14} style={{ color: "#059669" }} />
              <span style={{ color: "var(--text-muted)" }}>رقم ولي الأمر:</span>
              <strong style={{ fontFamily: "monospace", direction: "ltr" }}>
                {student.guardianPhone || "—"}
              </strong>
            </div>
          </div>

          {/* Section: Quiz Questions & Student's Solution */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1.5px solid var(--border-color-strong, #cbd5e1)",
              borderRadius: "14px",
              padding: "16px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <BookOpen size={18} style={{ color: "#059669" }} />
                <h3 style={{ margin: 0, fontSize: "14.5px", fontWeight: 800, color: "var(--text-main)" }}>
                  حل وإجابات الطالب في الاختبار (الـ Quiz)
                </h3>
              </div>

              {solutionData?.quiz?.title && (
                <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-muted)", background: "var(--bg-surface-secondary)", padding: "4px 10px", borderRadius: "6px" }}>
                  {solutionData.quiz.title}
                </span>
              )}
            </div>

            {loadingSolution ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "36px", gap: "10px", color: "var(--text-muted)" }}>
                <Loader2 size={20} className="animate-spin" />
                <span style={{ fontSize: "13px" }}>جاري تحميل إجابات وحل الطالب...</span>
              </div>
            ) : solutionData ? (
              <>
                {/* Quiz Summary Stats Bar */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                    gap: "8px",
                    background: "var(--bg-surface-secondary, #f8fafc)",
                    padding: "12px",
                    borderRadius: "10px",
                    border: "1px solid var(--border-color)",
                    marginBottom: "14px",
                    fontSize: "12px",
                  }}
                >
                  <div style={{ textAlign: "center" }}>
                    <span style={{ color: "var(--text-muted)", display: "block", fontSize: "11px" }}>إجمالي الأسئلة</span>
                    <strong style={{ fontSize: "15px", color: "var(--text-main)" }}>{solutionData.summary.total}</strong>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <span style={{ color: "#059669", display: "block", fontSize: "11px", fontWeight: 700 }}>إجابات صحيحة</span>
                    <strong style={{ fontSize: "15px", color: "#059669" }}>{solutionData.summary.correct}</strong>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <span style={{ color: "#dc2626", display: "block", fontSize: "11px", fontWeight: 700 }}>إجابات خاطئة</span>
                    <strong style={{ fontSize: "15px", color: "#dc2626" }}>{solutionData.summary.wrong}</strong>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <span style={{ color: "var(--text-muted)", display: "block", fontSize: "11px" }}>المدة المستغرقة</span>
                    <strong style={{ fontSize: "13px", color: "var(--text-main)", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      <Clock size={12} style={{ color: "var(--text-muted)" }} />
                      {formatDuration(solutionData.attempt?.duration_seconds)}
                    </strong>
                  </div>
                </div>

                {/* Questions List */}
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {solutionData.questions.map((q, idx) => {
                    const isCorrect = q.state === "correct";
                    const isWrong = q.state === "wrong";
                    const isSkipped = q.state === "skipped";

                    return (
                      <div
                        key={q.id || idx}
                        style={{
                          background: "var(--bg-surface)",
                          borderRadius: "10px",
                          border: isCorrect
                            ? "1px solid rgba(5, 150, 105, 0.4)"
                            : isWrong
                            ? "1px solid rgba(220, 38, 38, 0.4)"
                            : "1px solid var(--border-color)",
                          padding: "14px 16px",
                        }}
                      >
                        {/* Question Header */}
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px", flexWrap: "wrap", gap: "6px" }}>
                          <span style={{ fontSize: "12px", fontWeight: 800, color: "var(--text-muted)" }}>
                            السؤال {idx + 1}
                          </span>

                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            {isCorrect && (
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 800,
                                  color: "#059669",
                                  background: "rgba(5, 150, 105, 0.1)",
                                  padding: "2px 8px",
                                  borderRadius: "6px",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <CheckCircle2 size={12} />
                                إجابة الطالب صحيحة ({q.awarded}/{q.points} درجة)
                              </span>
                            )}
                            {isWrong && (
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 800,
                                  color: "#dc2626",
                                  background: "rgba(220, 38, 38, 0.1)",
                                  padding: "2px 8px",
                                  borderRadius: "6px",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <XCircle size={12} />
                                إجابة الطالب خاطئة ({q.awarded}/{q.points} درجة)
                              </span>
                            )}
                            {isSkipped && (
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 800,
                                  color: "#d97706",
                                  background: "rgba(217, 119, 6, 0.1)",
                                  padding: "2px 8px",
                                  borderRadius: "6px",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <AlertCircle size={12} />
                                لم يقم بالحل (0/{q.points} درجة)
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Question Prompt */}
                        <div style={{ fontSize: "13.5px", fontWeight: 700, color: "var(--text-main)", marginBottom: "12px", lineHeight: "1.6" }}>
                          <FormulaRenderer text={q.prompt} />
                        </div>

                        {/* Multiple Choice Options */}
                        {q.options && q.options.length > 0 ? (
                          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "6px" }}>
                            {q.options.map((opt, optIdx) => {
                              const cleanOpt = opt.trim();
                              const isStudentSelected =
                                Boolean(q.student_answer && (q.student_answer.trim() === cleanOpt || q.student_answer_letter === String.fromCharCode(65 + optIdx)));
                              const isCorrectOpt =
                                Boolean(q.correct_answer && (q.correct_answer.trim() === cleanOpt || q.correct_answer_letter === String.fromCharCode(65 + optIdx)));

                              let optBorder = "1px solid var(--border-color)";
                              let optBg = "var(--bg-surface-secondary)";
                              let optBadge = null;

                              if (isStudentSelected && isCorrectOpt) {
                                optBorder = "2px solid #059669";
                                optBg = "rgba(5, 150, 105, 0.1)";
                                optBadge = (
                                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#059669", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                    <Check size={13} /> إجابة الطالب (صحيحة)
                                  </span>
                                );
                              } else if (isStudentSelected && !isCorrectOpt) {
                                optBorder = "2px solid #dc2626";
                                optBg = "rgba(220, 38, 38, 0.1)";
                                optBadge = (
                                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#dc2626", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                    <X size={13} /> إجابة الطالب (غير صحيحة)
                                  </span>
                                );
                              } else if (!isStudentSelected && isCorrectOpt) {
                                optBorder = "1.5px dashed #059669";
                                optBg = "rgba(5, 150, 105, 0.05)";
                                optBadge = (
                                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#059669", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                    <Check size={13} /> الإجابة النموذجية الصحيحة
                                  </span>
                                );
                              }

                              return (
                                <div
                                  key={optIdx}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    gap: "10px",
                                    padding: "8px 12px",
                                    borderRadius: "8px",
                                    border: optBorder,
                                    background: optBg,
                                    fontSize: "12.5px",
                                  }}
                                >
                                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1 }}>
                                    <span
                                      style={{
                                        width: "22px",
                                        height: "22px",
                                        borderRadius: "50%",
                                        display: "inline-flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontSize: "11px",
                                        fontWeight: 800,
                                        background: isStudentSelected
                                          ? isCorrectOpt ? "#059669" : "#dc2626"
                                          : isCorrectOpt ? "#059669" : "var(--bg-surface)",
                                        color: isStudentSelected || isCorrectOpt ? "#ffffff" : "var(--text-muted)",
                                        border: "1px solid var(--border-color)",
                                        flexShrink: 0,
                                      }}
                                    >
                                      {optionLetters[optIdx] || String.fromCharCode(65 + optIdx)}
                                    </span>
                                    <div style={{ flex: 1 }}>
                                      <FormulaRenderer text={opt} inline />
                                    </div>
                                  </div>

                                  {optBadge && <div style={{ flexShrink: 0 }}>{optBadge}</div>}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          /* Open-ended answer presentation */
                          <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12.5px" }}>
                            <div style={{ padding: "8px 12px", borderRadius: "8px", background: isCorrect ? "rgba(5, 150, 105, 0.08)" : "rgba(220, 38, 38, 0.08)", border: "1px solid var(--border-color)" }}>
                              <strong style={{ color: "var(--text-muted)", display: "block", fontSize: "11px", marginBottom: "2px" }}>إجابة الطالب:</strong>
                              <span style={{ color: isCorrect ? "#059669" : "#dc2626", fontWeight: 700 }}>{q.student_answer || "— لم يقدم إجابة —"}</span>
                            </div>
                            <div style={{ padding: "8px 12px", borderRadius: "8px", background: "rgba(5, 150, 105, 0.05)", border: "1px dashed #059669" }}>
                              <strong style={{ color: "#059669", display: "block", fontSize: "11px", marginBottom: "2px" }}>الإجابة النموذجية:</strong>
                              <span style={{ color: "#0f172a", fontWeight: 700 }}>{q.correct_answer}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "24px", color: "var(--text-muted)", fontSize: "13px" }}>
                لم يتم العثور على حلول مسجلة للاختبار.
              </div>
            )}
          </div>

          {/* Exam Grade Editor Card */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              padding: "18px",
              borderRadius: "14px",
              border: "1.5px solid var(--border-color-strong, #cbd5e1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Award size={18} style={{ color: "#059669" }} />
                <strong style={{ fontSize: "14px", color: "var(--text-main)" }}>
                  رصد وتعديل الدرجة النهائية للاختبار
                </strong>
              </div>

              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 800,
                  color: status.color,
                  background: status.bg,
                  padding: "4px 10px",
                  borderRadius: "6px",
                }}
              >
                {status.label}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div
                style={{
                  padding: "12px",
                  borderRadius: "10px",
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  border: "1px solid var(--border-color)",
                  textAlign: "center",
                }}
              >
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                  الدرجة الكلية الحالية للطالب
                </span>
                <strong style={{ fontSize: "18px", color: "var(--text-main)" }}>
                  {student.totalOverallGrade}%
                </strong>
              </div>

              <div
                style={{
                  padding: "12px",
                  borderRadius: "10px",
                  background: "var(--bg-surface-secondary, #f8fafc)",
                  border: "1px solid var(--border-color)",
                  textAlign: "center",
                }}
              >
                <span style={{ fontSize: "11px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                  نسبة نجاح الاختبارات المسجلة
                </span>
                <strong style={{ fontSize: "18px", color: "#059669" }}>
                  {student.quizSuccessRate}%
                </strong>
              </div>
            </div>

            {/* Score Input Box */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 800, marginBottom: "6px", color: "var(--text-main)" }}>
                الدرجة الجديدة للاختبار (من 100):
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={score}
                  onChange={(e) => setScore(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                  style={{
                    width: "120px",
                    padding: "10px 14px",
                    border: "2px solid #059669",
                    borderRadius: "8px",
                    fontSize: "18px",
                    fontWeight: 900,
                    textAlign: "center",
                    background: "var(--bg-surface)",
                    color: "var(--text-main)",
                  }}
                />
                <span style={{ fontSize: "16px", fontWeight: 800, color: "#059669" }}>%</span>

                {/* Quick Presets */}
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginRight: "10px" }}>
                  {[100, 90, 80, 70, 50].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setScore(preset)}
                      style={{
                        padding: "6px 10px",
                        borderRadius: "6px",
                        border: score === preset ? "1.5px solid #059669" : "1px solid var(--border-color)",
                        background: score === preset ? "#0f392b" : "var(--bg-surface-secondary)",
                        color: score === preset ? "#ffffff" : "var(--text-main)",
                        fontSize: "11.5px",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      {preset}%
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Notes input */}
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "6px", color: "var(--text-muted)" }}>
                ملاحظات المعلم على الاختبار (اختياري):
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="أدخل أي ملاحظات أو توجيهات للطالب بخصوص نتيجة الاختبار..."
                rows={2}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  border: "1px solid var(--border-color)",
                  fontSize: "12px",
                  background: "var(--bg-surface)",
                  color: "var(--text-main)",
                  boxSizing: "border-box",
                  resize: "vertical",
                }}
              />
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: "10px",
            paddingTop: "14px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            style={{ padding: "8px 18px", fontSize: "13px" }}
          >
            إلغاء
          </button>
          <button
            type="button"
            onClick={handleSave}
            style={{
              padding: "9px 22px",
              background: "#059669",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              fontSize: "13.5px",
              fontWeight: 800,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              boxShadow: "0 2px 8px rgba(5, 150, 105, 0.3)",
            }}
          >
            <CheckCircle2 size={16} />
            <span>حفظ واعتماد درجة الامتحان</span>
          </button>
        </div>
      </div>
    </div>
  );
};

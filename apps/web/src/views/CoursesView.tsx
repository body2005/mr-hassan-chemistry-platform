import React, { useState } from "react";
import {
  Clock3,
  Database,
  Loader2,
  Sparkles,
} from "lucide-react";
import { Course, COURSES, Lesson } from "../data/mockCourses";
import { aiClient } from "../services/aiClient";

interface CoursesViewProps {
  selectedCourseId?: string;
  onOpenTutor: (courseId: string) => void;
}

export const CoursesView: React.FC<CoursesViewProps> = ({
  selectedCourseId,
  onOpenTutor,
}) => {
  const [activeCourse, setActiveCourse] = useState<Course>(() => {
    return COURSES.find((c) => c.id === selectedCourseId) || COURSES[0];
  });
  const [activeLesson, setActiveLesson] = useState<Lesson>(activeCourse.lessons[0]);
  const [indexing, setIndexing] = useState(false);
  const [indexStatus, setIndexStatus] = useState<string | null>(null);

  async function handleIndexCourse() {
    setIndexing(true);
    setIndexStatus(null);
    try {
      const chunks = activeCourse.lessons.map((l) => ({
        lesson_id: l.id,
        title: l.title,
        content: l.content,
        metadata: { course: activeCourse.title },
      }));

      const res = await aiClient.indexCourseContent({
        course_id: activeCourse.id,
        chunks,
      });

      setIndexStatus(`تم تجهيز وفهرسة ${res.indexed_chunks_count} دروس في المساعد الذكي بنجاح!`);
    } catch (err: any) {
      setIndexStatus(`تنبيه: ${err.message}`);
    } finally {
      setIndexing(false);
    }
  }

  return (
    <div className="page-content">
      {/* Course Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <p className="eyebrow">المقرر الدراسي • {activeCourse.subject}</p>
          <h1 style={{ margin: "4px 0", fontSize: "26px", fontFamily: "Manrope, sans-serif" }}>{activeCourse.title}</h1>
          <p style={{ color: "#6e7f77", margin: "4px 0 0", maxWidth: "600px", fontSize: "14px" }}>
            {activeCourse.description}
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={handleIndexCourse}
            disabled={indexing}
            style={{
              padding: "10px 16px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "#164f40",
              color: "white",
              border: "none",
              borderRadius: "10px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            {indexing ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
            تحديث معلومات المساعد الذكي
          </button>
          <button
            onClick={() => onOpenTutor(activeCourse.id)}
            style={{
              padding: "10px 16px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "#d5ee91",
              color: "#164f40",
              border: "none",
              borderRadius: "10px",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            <Sparkles size={16} /> اسأل المساعد الذكي
          </button>
        </div>
      </div>

      {indexStatus && (
        <div style={{ padding: "12px 18px", background: "#edf8ed", border: "1px solid #cce8cc", borderRadius: "10px", color: "#196336", fontSize: "13px", fontWeight: 700, marginBottom: "20px" }}>
          {indexStatus}
        </div>
      )}

      {/* Main Course Content Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "24px" }}>
        {/* Lesson List */}
        <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "18px" }}>
          <h3 style={{ margin: "0 0 14px", fontSize: "15px", fontWeight: 800, color: "#182923" }}>قائمة الدروس</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {activeCourse.lessons.map((lesson, idx) => (
              <button
                key={lesson.id}
                onClick={() => setActiveLesson(lesson)}
                style={{
                  textAlign: "right",
                  padding: "12px 14px",
                  borderRadius: "10px",
                  border: activeLesson.id === lesson.id ? "1.5px solid #164f40" : "1px solid #e7ebe4",
                  background: activeLesson.id === lesson.id ? "#f0f5ee" : "#ffffff",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", fontWeight: 800, color: "#8a968e" }}>الدرس {idx + 1}</span>
                  <span style={{ fontSize: "11px", color: "#6a7b73" }}>{lesson.duration}</span>
                </div>
                <strong style={{ display: "block", fontSize: "13px", color: "#182923" }}>{lesson.title}</strong>
              </button>
            ))}
          </div>

          <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid #dedfd6" }}>
            <h4 style={{ margin: "0 0 8px", fontSize: "12px", color: "#8a968e" }}>مقررات الكيمياء</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {COURSES.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setActiveCourse(c);
                    setActiveLesson(c.lessons[0]);
                  }}
                  style={{
                    textAlign: "right",
                    padding: "8px 10px",
                    borderRadius: "8px",
                    background: activeCourse.id === c.id ? "#164f40" : "transparent",
                    color: activeCourse.id === c.id ? "white" : "#4c6057",
                    border: "none",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {c.title}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Active Lesson Reader */}
        <div style={{ background: "#ffffff", border: "1px solid #dedfd6", borderRadius: "16px", padding: "28px 32px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "#eef2ec", color: "#164f40", padding: "4px 10px", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
              <Clock3 size={13} /> وقت القراءة: {activeLesson.duration}
            </span>
            <button
              onClick={() => onOpenTutor(activeCourse.id)}
              style={{ display: "flex", alignItems: "center", gap: "6px", background: "#f0f5ee", border: "1px solid #cde0d2", color: "#164f40", padding: "6px 14px", borderRadius: "8px", fontSize: "12px", fontWeight: 700, cursor: "pointer" }}
            >
              <Sparkles size={14} /> اسأل المساعد الذكي عن هذا الدرس
            </button>
          </div>

          <h2 style={{ fontSize: "22px", margin: "0 0 10px", fontFamily: "Manrope, sans-serif" }}>{activeLesson.title}</h2>
          <p style={{ color: "#718078", fontStyle: "italic", marginBottom: "20px", fontSize: "13px" }}>
            {activeLesson.summary}
          </p>

          <div style={{ fontSize: "15px", lineHeight: "1.8", color: "#24362e", background: "#fafaf7", padding: "20px 24px", borderRadius: "12px", border: "1px solid #edece3" }}>
            {activeLesson.content}
          </div>

          <div style={{ marginTop: "28px", display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "18px", borderTop: "1px solid #e7ebe4" }}>
            <span style={{ color: "#8a968e", fontSize: "12px" }}>أكملت قراءة وفهم الدرس؟</span>
            <button
              style={{ padding: "10px 22px", background: "#164f40", color: "white", border: "none", borderRadius: "8px", fontWeight: 800, fontSize: "13px", cursor: "pointer" }}
            >
              تعليم الدرس كمكتمل
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

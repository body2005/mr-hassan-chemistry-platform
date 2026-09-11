import React from "react";
import {
  ArrowRight,
  Clock3,
  MessageCircleMore,
  Play,
  Sparkles,
  Trophy,
} from "lucide-react";
import { Course } from "../data/mockCourses";

interface OverviewViewProps {
  courses: Course[];
  onOpenCourse: (courseId: string) => void;
  onOpenTutor: (courseId?: string) => void;
  onNavigateTab: (tab: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  courses,
  onOpenCourse,
  onOpenTutor,
  onNavigateTab,
}) => {
  const featuredCourse = courses[0];
  const featuredLesson = featuredCourse?.lessons?.[0];

  return (
    <div className="page-content">
      {/* Dashboard Temporal Header */}
      <section className="welcome-row reveal" style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: "20px", marginBottom: "24px" }}>
        <div>
          <p className="eyebrow">لوحة تحكم الطالب • الخطة التعليمية المستمرة</p>
          <h1 style={{ fontSize: "24px", color: "var(--text-main)", margin: "4px 0" }}>متابعة الدروس والأنشطة الدراسية</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "13.5px", margin: 0 }}>
            الفصل الدراسي الحالي • تحديث الأسبوع النشط. تتبع تقدمك في المحاضرات والواجبات الدورية بدقة.
          </p>
        </div>
        <div className="weekly-goal" style={{ border: "1px solid var(--border-color)", borderRadius: "8px", padding: "12px 18px", background: "var(--bg-surface)", boxShadow: "none" }}>
          <div className="goal-ring" style={{ fontVariantNumeric: "tabular-nums" }}>
            <span style={{ fontSize: "20px", fontWeight: 800, color: "var(--text-main)" }}>{courses.length}</span>
            <small style={{ color: "var(--text-muted)" }}>/ {Math.max(1, courses.length)}</small>
          </div>
          <div>
            <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>المقررات المسجلة</span>
            <strong style={{ display: "block", fontSize: "13px", color: "var(--text-main)", fontVariantNumeric: "tabular-nums" }}>{courses.length} مقرر نشط</strong>
          </div>
        </div>
      </section>

      {/* Hero Continue Learning — Flat Accent & Functional Simplicity */}
      {featuredCourse && (
        <section
          className="hero-card reveal delay-1"
          style={{
            background: "#0f392b",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: "10px",
            padding: "26px",
            boxShadow: "none",
          }}
        >
          <div className="hero-copy" style={{ maxWidth: "680px" }}>
            <span
              className="pill"
              style={{
                background: "rgba(255,255,255,0.14)",
                color: "#ffffff",
                border: "1px solid rgba(255,255,255,0.2)",
                borderRadius: "6px",
                padding: "3px 10px",
                fontSize: "11.5px",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
              }}
            >
              <Play size={11} fill="currentColor" /> استكمل دراستك الحالية
            </span>
            <h2 style={{ fontSize: "22px", color: "#ffffff", margin: "12px 0 6px" }}>
              {featuredLesson?.title || featuredCourse.title}
            </h2>
            <p style={{ color: "rgba(255,255,255,0.8)", fontSize: "13px", margin: "0 0 16px" }}>
              {featuredCourse.subject} • {featuredLesson?.summary || featuredCourse.currentLesson || "متابعة شرح الدرس"}
            </p>
            <div className="hero-progress" style={{ height: "6px", borderRadius: "3px", background: "rgba(255,255,255,0.16)", overflow: "hidden" }}>
              <span style={{ display: "block", height: "100%", background: "#10b981", width: `${featuredCourse.progress || 0}%` }} />
            </div>
            <div className="hero-meta" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px", fontSize: "12px", color: "rgba(255,255,255,0.75)" }}>
              <span style={{ fontVariantNumeric: "tabular-nums" }}>أنجزت {featuredCourse.progress || 0}% من إجمالي المحاضرة</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <Clock3 size={13} /> متابعة نشطة اليوم
              </span>
            </div>
            <div style={{ display: "flex", gap: "10px", marginTop: "20px", flexWrap: "wrap" }}>
              <button
                className="primary-button"
                onClick={() => onOpenCourse(featuredCourse.id)}
                style={{
                  background: "#059669",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "10px 18px",
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                افتح الدرس الآن <ArrowRight size={15} />
              </button>
              <button
                onClick={() => onOpenTutor(featuredCourse.id)}
                style={{
                  padding: "10px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  color: "#ffffff",
                  background: "rgba(255,255,255,0.12)",
                  border: "1px solid rgba(255,255,255,0.2)",
                  borderRadius: "8px",
                  fontSize: "12.5px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                <Sparkles size={15} /> اسأل المساعد الذكي
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Courses & Quick Action Grid */}
      <div className="dashboard-grid">
        <section className="courses-section reveal delay-2">
          <div className="section-heading">
            <div>
              <p className="eyebrow">مقرراتك الدراسية</p>
              <h2>المواد المسجل بها</h2>
            </div>
            <button onClick={() => onNavigateTab("Courses")}>
              عرض كل الدروس <ArrowRight size={15} />
            </button>
          </div>
          {courses.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1px dashed var(--border-color)", borderRadius: "14px", padding: "40px 20px", textAlign: "center", color: "var(--text-muted)" }}>
              <p style={{ margin: "0 0 10px", fontSize: "14px" }}>لا توجد مقررات دراسية مسجلة حالياً.</p>
              <button className="primary-button" onClick={() => onNavigateTab("Courses")} style={{ padding: "8px 16px", fontSize: "12.5px" }}>
                تصفح المقررات في المتجر
              </button>
            </div>
          ) : (
            <div className="course-grid">
              {courses.map((course) => (
                <article
                  className="course-card"
                  key={course.id}
                  onClick={() => onOpenCourse(course.id)}
                  style={{ cursor: "pointer" }}
                >
                  <div className={`course-art ${course.tone || "green"}`}>
                    <span>{course.mark || ""}</span>
                    <i />
                    <b />
                  </div>
                  <div className="course-body">
                    <span className="subject">{course.subject}</span>
                    <h3>{course.title}</h3>
                    <p>{course.currentLesson || "الدرس الحالي"}</p>
                    <div className="progress-row">
                      <div>
                        <span style={{ width: `${course.progress || 0}%` }} />
                      </div>
                      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{course.progress || 0}%</strong>
                    </div>
                    <span className="lesson-count">{course.meta || `${course.lessons?.length || 0} دروس`}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <aside className="right-rail reveal delay-3">
          <section className="tutor-card" style={{ background: "#1c3830" }}>
            <div className="tutor-orb" style={{ background: "#d5ee91", color: "#164f40" }}>
              <Sparkles size={27} />
            </div>
            <span className="ai-label">رفيق المذاكرة الذكي</span>
            <h2>عندك سؤال في الدرس؟</h2>
            <p>
              اسأل في أي وقت واحصل على إجابة فورية ومبسطة من واقع مقرراتك الدراسية.
            </p>
            <button onClick={() => onOpenTutor(featuredCourse?.id)}>
              ابدأ المحادثة الآن <MessageCircleMore size={17} />
            </button>
          </section>

          <section className="achievement-card">
            <div className="achievement-icon">
              <Trophy size={21} />
            </div>
            <div>
              <span>متابعة الإنجاز</span>
              <strong>طالب مجتهد</strong>
              <p>تفاعل مستمر مع المحتوى التعليمي</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
};

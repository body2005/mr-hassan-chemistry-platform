import React, { useState } from "react";
import {
  Award,
  Book,
  CheckCircle2,
  Clock,
  GraduationCap,
  Play,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Zap,
} from "lucide-react";
import { Course, CurrentUser, StudentProfile } from "../types/lms";
import { Language, translations } from "../utils/i18n";

export interface EducationalBookItem {
  id: string;
  title: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  author: string;
  authorTitle: string;
  pagesCount: number;
  price: string;
  description: string;
  gradient: string;
  sampleTopics: string[];
}

export interface RevisionPackageItem {
  id: string;
  title: string;
  courseId: string;
  academicYear: "1st_secondary" | "2nd_secondary" | "3rd_secondary";
  teacherName: string;
  durationFormatted: string;
  price: string;
  description: string;
  workshopsCount: number;
  badge: string;
  features: string[];
}

interface GeneralHomeViewProps {
  courses: Course[];
  enrolledCourseIds: string[];
  onEnrollCourse: (courseId: string) => void;
  onNavigateToMyCourses: () => void;
  currentUser: CurrentUser;
  lang: Language;
}

export const GeneralHomeView: React.FC<GeneralHomeViewProps> = ({
  courses,
  enrolledCourseIds,
  onEnrollCourse,
  onNavigateToMyCourses,
  currentUser,
  lang,
}) => {
  const t = translations[lang];
  const isStudent = currentUser.role === "student";
  const studentYear = isStudent ? (currentUser as StudentProfile).academicYear : "1st_secondary";
  const studentYearLabel = isStudent ? (currentUser as StudentProfile).academicYearLabel : "الصف الأول الثانوي";

  // Section Filter Tabs: Courses, Books, Revisions
  const [activeCatalogSection, setActiveCatalogSection] = useState<"courses" | "books" | "revisions">("courses");

  // Purchased Books State
  const [purchasedBookIds] = useState<string[]>([]);

  // Purchased Revisions State
  const [purchasedRevisionIds] = useState<string[]>([]);

  const [notificationBanner, setNotificationBanner] = useState<string | null>(null);

  // Available Books Catalog (loaded dynamically from platform store)
  const [allBooks] = useState<EducationalBookItem[]>([]);

  // Available Revision Packages Catalog (loaded dynamically from platform store)
  const [allRevisions] = useState<RevisionPackageItem[]>([]);

  // Filter Catalog by student's academic year, showing courses with uploaded lessons
  const availableCourses = courses.filter((c) => {
    if (!c.lessons || c.lessons.length === 0) {
      return false;
    }
    if (isStudent && studentYear) {
      return c.academicYear === studentYear;
    }
    return true;
  });

  const availableBooks = allBooks.filter((b) => {
    if (isStudent && studentYear) {
      return b.academicYear === studentYear;
    }
    return true;
  });

  const availableRevisions = allRevisions.filter((r) => {
    if (isStudent && studentYear) {
      return r.academicYear === studentYear;
    }
    return true;
  });

  // Handle Book Purchase
  function handleBuyBook(book: EducationalBookItem) {
    void book;
    setNotificationBanner("المحتوى التجاري يتطلب عملية دفع وتخويل من الخادم.");
    setTimeout(() => setNotificationBanner(null), 5000);
  }

  // Handle Revision Purchase
  function handleBuyRevision(revision: RevisionPackageItem) {
    void revision;
    setNotificationBanner("المحتوى التجاري يتطلب عملية دفع وتخويل من الخادم.");
    setTimeout(() => setNotificationBanner(null), 5000);
  }

  return (
    <div className="page-container">
      {/* Toast Notification Banner */}
      {notificationBanner && (
        <div
          style={{
            background: "#047857",
            color: "white",
            padding: "14px 20px",
            borderRadius: "12px",
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            border: "1px solid #059669",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "14px", fontWeight: 700 }}>
            <CheckCircle2 size={20} />
            <span>{notificationBanner}</span>
          </div>
          <button
            onClick={onNavigateToMyCourses}
            style={{
              background: "white",
              color: "#0f392b",
              border: "none",
              padding: "6px 14px",
              borderRadius: "8px",
              fontSize: "12px",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            فتح مقرراتي
          </button>
        </div>
      )}

      {/* Header & Quick Action Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "14px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-main)", background: "var(--bg-accent)", padding: "3px 8px", borderRadius: "6px" }}>
              {t.catalogBadge}
            </span>
            <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <ShieldCheck size={14} style={{ color: "#059669" }} />
              <span>محتوى <strong>{studentYearLabel}</strong></span>
            </span>
          </div>
          <h1 style={{ margin: "4px 0 2px", fontSize: "24px", color: "var(--text-main)", fontWeight: 900 }}>
            متجر المقررات والكتب والمراجعات
          </h1>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>
            اختر تفعيل الدروس والمذكرات المعتمدة، أو الانضمام للمراجعات والورش التدريبية المكثفة.
          </p>
        </div>
      </div>

      {/* Navigation Section Filter Pills */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          marginBottom: "28px",
          overflowX: "auto",
          paddingBottom: "4px",
        }}
      >
        <button
          onClick={() => setActiveCatalogSection("courses")}
          style={{
            padding: "10px 22px",
            borderRadius: "12px",
            border: activeCatalogSection === "courses" ? "2px solid #059669" : "1px solid var(--border-color)",
            background: activeCatalogSection === "courses" ? "#0f392b" : "var(--bg-surface)",
            color: activeCatalogSection === "courses" ? "#ffffff" : "var(--text-main)",
            fontWeight: 800,
            fontSize: "13.5px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transition: "all 0.15s ease",
          }}
        >
          <Sparkles size={16} />
          <span>المقررات الدراسية الشاملة</span>
        </button>

        <button
          onClick={() => setActiveCatalogSection("books")}
          style={{
            padding: "10px 22px",
            borderRadius: "12px",
            border: activeCatalogSection === "books" ? "2px solid #059669" : "1px solid var(--border-color)",
            background: activeCatalogSection === "books" ? "#0f392b" : "var(--bg-surface)",
            color: activeCatalogSection === "books" ? "#ffffff" : "var(--text-main)",
            fontWeight: 800,
            fontSize: "13.5px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transition: "all 0.15s ease",
          }}
        >
          <Book size={16} />
          <span>الكتب والمذكرات</span>
        </button>

        <button
          onClick={() => setActiveCatalogSection("revisions")}
          style={{
            padding: "10px 22px",
            borderRadius: "12px",
            border: activeCatalogSection === "revisions" ? "2px solid #059669" : "1px solid var(--border-color)",
            background: activeCatalogSection === "revisions" ? "#0f392b" : "var(--bg-surface)",
            color: activeCatalogSection === "revisions" ? "#ffffff" : "var(--text-main)",
            fontWeight: 800,
            fontSize: "13.5px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transition: "all 0.15s ease",
          }}
        >
          <Zap size={16} />
          <span>المراجعات والورش التدريبية</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 1: المقررات الدراسية الشاملة */}
      {/* ========================================================================= */}
      {activeCatalogSection === "courses" && (
        <div style={{ marginBottom: "36px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
            <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "var(--bg-accent)", color: "#059669", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Sparkles size={18} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                  المقررات الدراسية الشاملة
                </h2>
                <span style={{ fontSize: "12px", fontWeight: 700, color: "#059669", background: "var(--bg-accent)", padding: "3px 10px", borderRadius: "20px" }}>
                  {availableCourses.length} مقرر متاح
                </span>
              </div>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginTop: "2px" }}>
                تشمل جميع الدروس والفيديوهات والكويزات والواجبات
              </span>
            </div>
          </div>

          {availableCourses.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1px dashed var(--border-color)", borderRadius: "16px", padding: "40px 20px", textAlign: "center", color: "var(--text-muted)" }}>
              <GraduationCap size={40} style={{ margin: "0 auto 12px", opacity: 0.5, color: "#059669" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "16px", color: "var(--text-main)" }}>لا توجد مقررات دراسية متاحة حالياً</h3>
              <p style={{ margin: 0, fontSize: "13px" }}>سيتم عرض المقررات الدراسية فور رفعها ونشرها من قبل المعلم.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 330px), 1fr))", gap: "18px" }}>
              {availableCourses.map((course) => {
              const isEnrolled = enrolledCourseIds.includes(course.id);
              const yearLabel =
                course.academicYear === "1st_secondary"
                  ? t.firstSecondary
                  : course.academicYear === "2nd_secondary"
                  ? t.secondSecondary
                  : t.thirdSecondary;

              return (
                <div
                  key={course.id}
                  className="course-card"
                  style={{
                    background: "var(--bg-surface)",
                    border: isEnrolled ? "2px solid #059669" : "1px solid var(--border-color)",
                    borderRadius: "12px",
                    overflow: "hidden",
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "none",
                    transition: "all 0.2s ease",
                  }}
                >
                  {/* Header Banner with Video Lesson Preview/Thumbnail Snippet */}
                  <div
                    style={{
                      background: "#0f392b",
                      padding: "18px 20px",
                      color: "white",
                      position: "relative",
                      minHeight: "155px",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      overflow: "hidden",
                    }}
                  >
                    {/* Video / Snapshot background if available.
                        Protected (locally-stored) videos resolve their real
                        source only through a POST-token handshake, so rendering
                        them as <video src> would fire a GET at that endpoint
                        (405). Thumbnails or public URLs only. */}
                    {course.lessons?.[0]?.videoUrl && !course.lessons[0].requiresProtectedPlayback && (
                      <div
                        style={{
                          position: "absolute",
                          inset: 0,
                          zIndex: 0,
                          overflow: "hidden",
                        }}
                      >
                        {course.lessons[0].thumbnailUrl ? (
                          <img
                            src={course.lessons[0].thumbnailUrl}
                            alt={course.lessons[0].title}
                            style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.55 }}
                          />
                        ) : (
                          <video
                            src={course.lessons[0].videoUrl + "#t=1"}
                            muted
                            playsInline
                            preload="metadata"
                            controlsList="nodownload nofullscreen noremoteplayback"
                            disablePictureInPicture
                            disableRemotePlayback
                            onContextMenu={(e) => e.preventDefault()}
                            style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.55, userSelect: "none" }}
                          />
                        )}
                        <div
                          style={{
                            position: "absolute",
                            inset: 0,
                            background: "rgba(9, 38, 28, 0.78)",
                          }}
                        />
                      </div>
                    )}

                    <div style={{ position: "relative", zIndex: 1, display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                      <span
                        style={{
                          background: isEnrolled ? "#059669" : "rgba(255,255,255,0.25)",
                          padding: "3px 10px",
                          borderRadius: "20px",
                          fontSize: "11.5px",
                          fontWeight: 800,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          backdropFilter: "blur(4px)",
                        }}
                      >
                        {isEnrolled ? "مشترك بالمقرر" : "مقرر شامل"}
                      </span>
                      <span style={{ fontSize: "12px", opacity: 0.95, fontWeight: 700 }}>{course.subject}</span>
                    </div>

                    <div style={{ position: "relative", zIndex: 1 }}>
                      {course.lessons?.[0] && (
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                            background: "rgba(0,0,0,0.45)",
                            padding: "2px 8px",
                            borderRadius: "6px",
                            marginBottom: "6px",
                            backdropFilter: "blur(4px)",
                          }}
                        >
                          <Play size={10} fill="#10b981" color="#10b981" />
                          <span style={{ fontSize: "11px", color: "#a7f3d0", fontWeight: 700 }}>
                            فيديو: {course.lessons[0].title}
                          </span>
                        </div>
                      )}
                      <h3 style={{ margin: "2px 0 2px", fontSize: "18px", fontWeight: 800, textShadow: "0 1px 3px rgba(0,0,0,0.5)" }}>
                        {course.title}
                      </h3>
                      <span style={{ fontSize: "12px", opacity: 0.9 }}>{yearLabel}</span>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                    <div>
                      <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 16px" }}>
                        {course.description}
                      </p>

                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                        <GraduationCap size={18} color="#059669" />
                        <div>
                          <strong style={{ fontSize: "13px", display: "block", color: "var(--text-main)" }}>{course.teacherName}</strong>
                          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{course.teacherTitle}</span>
                        </div>
                      </div>
                    </div>

                    {/* Action Button */}
                    {isEnrolled ? (
                      <button
                        className="btn-outline"
                        onClick={onNavigateToMyCourses}
                        style={{
                          width: "100%",
                          justifyContent: "center",
                          padding: "10px",
                          borderRadius: "10px",
                          fontSize: "13px",
                          fontWeight: 800,
                          gap: "6px",
                          borderColor: "#059669",
                          color: "#059669",
                        }}
                      >
                        <CheckCircle2 size={16} />
                        <span>مشترك بالفعل - فتح المقرر</span>
                      </button>
                    ) : (
                      <button
                        className="btn-primary"
                        onClick={() => onEnrollCourse(course.id)}
                        style={{
                          width: "100%",
                          justifyContent: "center",
                          padding: "10px",
                          borderRadius: "10px",
                          fontSize: "13px",
                          fontWeight: 800,
                          gap: "6px",
                        }}
                      >
                        <Plus size={15} />
                        <span>{Number(course.price || 0) > 0 ? "اختيار درس للشراء" : "الانضمام مجانًا"}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION 2: الكتب والمذكرات والملازم المعتمدة */}
      {/* ========================================================================= */}
      {activeCatalogSection === "books" && (
        <div style={{ marginBottom: "36px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
            <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "var(--bg-accent)", color: "#059669", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Book size={18} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                  الكتب والمذكرات والملازم المعتمدة
                </h2>
                <span style={{ fontSize: "12px", fontWeight: 700, color: "#059669", background: "var(--bg-accent)", padding: "3px 10px", borderRadius: "20px" }}>
                  {availableBooks.length} كتاب ومذكرة
                </span>
              </div>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginTop: "2px" }}>
                كتب الشرح المعتمدة وبنوك الأسئلة ومذكرات المراجعة النهائية
              </span>
            </div>
          </div>

          {availableBooks.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1px dashed var(--border-color)", borderRadius: "16px", padding: "40px 20px", textAlign: "center", color: "var(--text-muted)" }}>
              <Book size={40} style={{ margin: "0 auto 12px", opacity: 0.5, color: "#059669" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "16px", color: "var(--text-main)" }}>لا توجد كتب أو مذكرات منشورة حالياً</h3>
              <p style={{ margin: 0, fontSize: "13px" }}>سيتم إضافة المذكرات والكتب المعتمدة فور نشرها وتفعيلها.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 330px), 1fr))", gap: "18px" }}>
              {availableBooks.map((book) => {
                const isPurchased = purchasedBookIds.includes(book.id);

                return (
                  <div
                    key={book.id}
                    className="course-card"
                    style={{
                      background: "var(--bg-surface)",
                      border: isPurchased ? "2px solid #059669" : "1px solid var(--border-color)",
                      borderRadius: "16px",
                      overflow: "hidden",
                      display: "flex",
                      flexDirection: "column",
                      boxShadow: "var(--card-shadow)",
                      transition: "all 0.2s ease",
                    }}
                  >
                    {/* Book Card Header */}
                    <div
                      style={{
                        background: book.gradient,
                        padding: "20px",
                        color: "white",
                        position: "relative",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                        <span
                          style={{
                            background: isPurchased ? "#059669" : "rgba(255,255,255,0.2)",
                            padding: "3px 10px",
                            borderRadius: "20px",
                            fontSize: "11px",
                            fontWeight: 800,
                          }}
                        >
                          {isPurchased ? "تم الشراء والامتلاك" : "كتاب معتمد"}
                        </span>
                        <span style={{ fontSize: "12px", fontWeight: 800, background: "rgba(255,255,255,0.15)", padding: "2px 8px", borderRadius: "6px" }}>
                          {book.price}
                        </span>
                      </div>

                      <h3 style={{ margin: "6px 0 3px", fontSize: "16px", fontWeight: 800, lineHeight: 1.35 }}>
                        {book.title}
                      </h3>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11.5px", opacity: 0.9 }}>
                        <span>إعداد: {book.author}</span>
                        <span>•</span>
                        <span>{book.pagesCount} صفحة</span>
                      </div>
                    </div>

                    {/* Body Content */}
                    <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <p style={{ fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 14px" }}>
                          {book.description}
                        </p>

                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "16px" }}>
                          {book.sampleTopics.map((topic, i) => (
                            <span
                              key={i}
                              style={{
                                fontSize: "11px",
                                background: "var(--bg-accent)",
                                color: "#065f46",
                                padding: "3px 8px",
                                borderRadius: "6px",
                                fontWeight: 700,
                              }}
                            >
                              {topic}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Action Button */}
                      {isPurchased ? (
                        <button
                          className="btn-outline"
                          onClick={onNavigateToMyCourses}
                          style={{
                            width: "100%",
                            justifyContent: "center",
                            padding: "10px",
                            borderRadius: "10px",
                            fontSize: "13px",
                            fontWeight: 800,
                            gap: "6px",
                            borderColor: "#059669",
                            color: "#059669",
                          }}
                        >
                          <CheckCircle2 size={16} />
                          <span>تم الشراء - فتح وقراءة الكتاب</span>
                        </button>
                      ) : (
                        <button
                          className="btn-primary"
                          onClick={() => handleBuyBook(book)}
                          style={{
                            width: "100%",
                            justifyContent: "center",
                            padding: "10px",
                            borderRadius: "10px",
                            fontSize: "13px",
                            fontWeight: 800,
                            gap: "6px",
                            background: "#047857",
                          }}
                        >
                          <ShoppingBag size={15} />
                          <span>شراء وتحميل الكتاب - {book.price}</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION 3: المراجعات والورش التدريبية */}
      {/* ========================================================================= */}
      {activeCatalogSection === "revisions" && (
        <div style={{ marginBottom: "36px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
            <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "var(--bg-accent)", color: "#059669", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Zap size={18} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "var(--text-main)" }}>
                  المراجعات والورش التدريبية المكثفة
                </h2>
                <span style={{ fontSize: "12px", fontWeight: 700, color: "#059669", background: "var(--bg-accent)", padding: "3px 10px", borderRadius: "20px" }}>
                  {availableRevisions.length} معسكر مراجعة
                </span>
              </div>
              <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginTop: "2px" }}>
                معسكرات تدريبية، ورش حل القطاعات والمسائل، ومراجعات ليلة الامتحان الشاملة
              </span>
            </div>
          </div>

          {availableRevisions.length === 0 ? (
            <div style={{ background: "var(--bg-surface)", border: "1px dashed var(--border-color)", borderRadius: "16px", padding: "40px 20px", textAlign: "center", color: "var(--text-muted)" }}>
              <Zap size={40} style={{ margin: "0 auto 12px", opacity: 0.5, color: "#059669" }} />
              <h3 style={{ margin: "0 0 6px", fontSize: "16px", color: "var(--text-main)" }}>لا توجد مراجعات أو ورش عمل منشورة حالياً</h3>
              <p style={{ margin: 0, fontSize: "13px" }}>سيتم إضافة ورش المراجعة ومعسكرات التدريب فور نشرها من قبل المعلم.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 330px), 1fr))", gap: "18px" }}>
              {availableRevisions.map((rev) => {
                const isPurchased = purchasedRevisionIds.includes(rev.id);

                return (
                  <div
                    key={rev.id}
                    className="course-card"
                    style={{
                      background: "var(--bg-surface)",
                      border: isPurchased ? "2px solid #059669" : "1px solid var(--border-color)",
                      borderRadius: "16px",
                      overflow: "hidden",
                      display: "flex",
                      flexDirection: "column",
                      boxShadow: "var(--card-shadow)",
                      transition: "all 0.2s ease",
                    }}
                  >
                    {/* Header */}
                    <div
                      style={{
                        background: "#0f392b",
                        padding: "20px",
                        color: "white",
                        position: "relative",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                        <span
                          style={{
                            background: "#059669",
                            padding: "3px 10px",
                            borderRadius: "6px",
                            fontSize: "11px",
                            fontWeight: 800,
                          }}
                        >
                          {rev.badge}
                        </span>
                        <span style={{ fontSize: "12px", fontWeight: 800, background: "rgba(255,255,255,0.2)", padding: "2px 8px", borderRadius: "6px" }}>
                          {rev.price}
                        </span>
                      </div>

                      <h3 style={{ margin: "6px 0 3px", fontSize: "15.5px", fontWeight: 800, lineHeight: 1.35 }}>
                        {rev.title}
                      </h3>
                      <span style={{ fontSize: "11.5px", opacity: 0.85 }}>إشراف: {rev.teacherName}</span>
                    </div>

                    {/* Body Content */}
                    <div style={{ padding: "18px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <p style={{ fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 14px" }}>
                          {rev.description}
                        </p>

                        <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "14px", fontSize: "12px", color: "var(--text-muted)" }}>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Clock size={14} style={{ color: "#059669" }} /> {rev.durationFormatted}
                          </span>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Award size={14} style={{ color: "#059669" }} /> {rev.workshopsCount} ورش عمل
                          </span>
                        </div>

                        <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "16px" }}>
                          {rev.features.map((feat, idx) => (
                            <div key={idx} style={{ fontSize: "11.5px", color: "var(--text-main)", display: "flex", alignItems: "center", gap: "6px" }}>
                              <CheckCircle2 size={13} style={{ color: "#059669" }} />
                              <span>{feat}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Action Button */}
                      {isPurchased ? (
                        <button
                          className="btn-outline"
                          onClick={onNavigateToMyCourses}
                          style={{
                            width: "100%",
                            justifyContent: "center",
                            padding: "10px",
                            borderRadius: "10px",
                            fontSize: "13px",
                            fontWeight: 800,
                            gap: "6px",
                            borderColor: "#059669",
                            color: "#059669",
                          }}
                        >
                          <CheckCircle2 size={16} />
                          <span>مشترك ومفعل - فتح ورش المراجعة</span>
                        </button>
                      ) : (
                        <button
                          className="btn-primary"
                          onClick={() => handleBuyRevision(rev)}
                          style={{
                            width: "100%",
                            justifyContent: "center",
                            padding: "10px",
                            borderRadius: "10px",
                            fontSize: "13px",
                            fontWeight: 800,
                            gap: "6px",
                            background: "#047857",
                          }}
                        >
                          <Zap size={15} />
                          <span>اشترك في المراجعة - {rev.price}</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

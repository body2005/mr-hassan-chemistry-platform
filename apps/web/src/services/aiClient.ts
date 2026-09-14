import {
  AnalyticsInterpretationResponse,
  BatchRiskResponse,
  EssayGradingResponse,
  QuizDraftResponse,
  ReportNarrativeResponse,
  RubricCriterion,
  SystemHealthResponse,
  SystemMetricsResponse,
  TutorChatResponse,
} from "../types/ai";
import { UserRole, QuestionTypeConfig } from "../types/lms";
import { apiRequest } from "./apiClient";

export class AIServiceError extends Error {
  readonly status = "error" as const;
  readonly requiresReview = true;

  constructor(readonly task: string, message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "AIServiceError";
  }
}

export type QuestionTypeAllocation = QuestionTypeConfig;

class AIServiceClient {
  private async request<T>(endpoint: string, method: "GET" | "POST" = "POST", body?: unknown, headers: Record<string, string> = {}, timeoutMs = 30_000): Promise<T> {
    return apiRequest<T>(endpoint, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), timeoutMs });
  }

  // ================================================================
  // 1. QUIZ GENERATION
  // ================================================================
  async generateQuiz(payload: {
    course_id: string;
    lesson_ids?: string[];
    outline_node_id?: string;
    include_prerequisite_lessons?: boolean;
    lesson_contents: string[];
    question_count: number;
    allowed_types: string[];
    type_allocations?: QuestionTypeAllocation[];
    difficulty_distribution?: Record<string, number>;
    topics?: string[];
    target_points_per_question?: number;
    quiz_mode?: "mix" | "extract" | "generate";
    exclude_stems?: string[];
    title?: string;
  }, bypassCache = false): Promise<QuizDraftResponse> {
    const validContents = (payload.lesson_contents || []).filter(
      (c) => typeof c === "string" && c.trim().length > 0
    );

    if (!payload.course_id) {
      throw new AIServiceError(
        "quiz_generation",
        "يرجى اختيار مقرر صالح قبل توليد الاختبار.",
      );
    }

    const resp = await this.request<QuizDraftResponse>(
      "/quiz/draft",
      "POST",
      { ...payload, lesson_contents: validContents },
      { ...(bypassCache ? { "X-Cache-Bypass": "true" } : {}) },
    );

    if (payload.type_allocations && payload.type_allocations.length > 0) {
      return this.validateAndNormalizeQuiz(resp, payload);
    }
    return resp;
  }

  private validateAndNormalizeQuiz(
    rawResponse: QuizDraftResponse,
    payload: { type_allocations?: QuestionTypeAllocation[]; question_count?: number },
  ): QuizDraftResponse {
    if (!Array.isArray(rawResponse.questions)) {
      throw new AIServiceError("quiz_generation", "AI returned an invalid quiz schema");
    }
    if (payload.question_count && Math.abs(rawResponse.questions.length - payload.question_count) > 1) {
      throw new AIServiceError("quiz_generation", "AI returned an unexpected question count");
    }
    const allowedTypes = new Set<string>(payload.type_allocations?.map((a) => a.id));
    if (rawResponse.questions.some((q) => !allowedTypes.has(q.question_type))) {
      throw new AIServiceError("quiz_generation", "AI returned an unsupported question type");
    }
    return rawResponse;
  }

  // ================================================================
  // 1.1 EXTRACT QUIZ DIRECTLY FROM UPLOADED FILE
  // ================================================================
  async extractQuizFromFile(
    file: File,
    courseId: string,
    lessonId?: string
  ): Promise<QuizDraftResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("course_id", courseId);
    if (lessonId) formData.append("lesson_id", lessonId);

    return apiRequest<QuizDraftResponse>("/quiz/extract-from-file", {
      method: "POST",
      body: formData,
      timeoutMs: 60_000,
    });
  }

  // ================================================================
  // 2. ESSAY GRADING
  // ================================================================
  async gradeEssay(payload: {
    question_prompt: string;
    student_submission: string;
    rubric: RubricCriterion[];
    max_score: number;
    question_type?: string;
    context_passage?: string;
  }, bypassCache = false): Promise<EssayGradingResponse> {
    if ((payload.student_submission || "").trim().length === 0) {
      return {
        total_score: 0,
        max_score: payload.max_score,
        percentage: 0,
        criteria_breakdown: [],
        feedback_summary: "لم يقم الطالب بكتابة أي إجابة.",
        confidence_score: 1.0,
        flagged_for_human_review: false,
        requires_teacher_approval: true,
        cached: false,
      };
    }
    return this.request<EssayGradingResponse>("/grading/essay", "POST", payload, {
      ...(bypassCache ? { "X-Cache-Bypass": "true" } : {})
    });
  }

  // ================================================================
  // 3. TUTOR CHAT
  // ================================================================
  async chatWithTutor(payload: {
    course_id?: string;
    lesson_id?: string;
    student_id?: string;
    session_id?: string;
    message: string;
    user_role?: UserRole;
    user_name?: string;
    temperature?: number;
  }): Promise<TutorChatResponse> {
    return this.request<TutorChatResponse>("/tutor/chat", "POST", payload);
  }

  async indexCourseContent(payload: {
    course_id: string;
    chunks: Array<{
      lesson_id: string;
      content: string;
      title?: string;
      metadata?: Record<string, unknown>;
    }>;
  }): Promise<{ course_id: string; indexed_chunks_count: number; message: string }> {
    return this.request("/tutor/index-course", "POST", payload, {}, 60_000);
  }

  async predictStudentRisk(students: Array<{
    student_id: string;
    cohort_id?: string;
    course_id?: string;
    login_frequency_weekly: number;
    assignments_submitted_ratio: number;
    average_quiz_score: number;
    late_submissions_count: number;
    forum_posts_count: number;
    time_spent_hours_weekly: number;
    video_watch_completion_ratio: number;
    days_since_last_activity: number;
  }>): Promise<BatchRiskResponse> {
    return this.request<BatchRiskResponse>("/risk/predict", "POST", { students });
  }

  async trainRiskModel(payload: { training_data: unknown[]; model_type?: string; n_splits?: number }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("/risk/train", "POST", payload, {}, 120_000);
  }

  async interpretClassAnalytics(payload: Record<string, unknown>, bypassCache = false): Promise<AnalyticsInterpretationResponse> {
    return this.request<AnalyticsInterpretationResponse>("/analytics/interpret", "POST", payload, {
      ...(bypassCache ? { "X-Cache-Bypass": "true" } : {}),
    });
  }

  async generateReportNarrative(payload: Record<string, unknown>, bypassCache = false): Promise<ReportNarrativeResponse> {
    return this.request<ReportNarrativeResponse>("/reports/narrative", "POST", payload, {
      ...(bypassCache ? { "X-Cache-Bypass": "true" } : {}),
    }, 60_000);
  }

  async getSystemMetrics(): Promise<SystemMetricsResponse> {
    return this.request<SystemMetricsResponse>("/system/metrics", "GET", undefined, {}, 5_000);
  }

  async getSystemHealth(): Promise<SystemHealthResponse> {
    return this.request<SystemHealthResponse>("/system/health", "GET", undefined, {}, 5_000);
  }

  async clearCache(): Promise<{ status: string; message: string }> {
    return this.request("/system/cache/clear", "POST");
  }
}

export const aiClient = new AIServiceClient();

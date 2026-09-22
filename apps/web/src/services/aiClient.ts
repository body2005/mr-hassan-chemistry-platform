import {
  QuizDraftResponse,
} from "../types/ai";
import { QuestionTypeConfig } from "../types/lms";
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
    courseId?: string,
    lessonId?: string,
    targetType: "quiz" | "assignment" = "quiz",
  ): Promise<QuizDraftResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (courseId) formData.append("course_id", courseId);
    if (lessonId) formData.append("lesson_id", lessonId);
    formData.append("target_type", targetType);

    return apiRequest<QuizDraftResponse>("/quiz/extract-from-file", {
      method: "POST",
      body: formData,
      timeoutMs: 60_000,
    });
  }
}

export const aiClient = new AIServiceClient();

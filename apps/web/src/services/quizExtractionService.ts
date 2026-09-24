import {
  QuizDraftResponse,
} from "../types/quiz";
import { apiRequest } from "./apiClient";

/**
 * Extraction-only quiz service.
 *
 * The platform no longer offers AI question generation. The single remaining
 * server interaction is POST /quiz/extract-from-file, a deterministic,
 * rule-based parser (PDF/DOCX/TXT/JSON + OCR) that pulls the questions that
 * actually exist inside an uploaded file. No model inference is involved.
 */
export const quizExtractionService = {
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
  },
};

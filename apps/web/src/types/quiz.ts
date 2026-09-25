export interface CourseOption {
  key: string;
  text: string;
  is_correct: boolean;
  distractor_explanation?: string;
}

export interface RubricCriterion {
  id: string;
  name: string;
  description: string;
  max_points: number;
}

export type QuestionType =
  | "MCQ"
  | "TRUE_FALSE"
  | "FILL_BLANK"
  | "ESSAY"
  | "UNKNOWN"
  | "multiple_choice"
  | "true_false"
  | "fill_in_blank"
  | "essay"
  | "short_answer"
  | "coding"
  | "fill_in_the_blank";

export interface GeneratedQuestion {
  id: number;
  question_type: QuestionType;
  difficulty: "easy" | "medium" | "hard";
  topic: string;
  points: number | null;
  needs_points_assignment?: boolean;
  question_text: string;
  options?: CourseOption[];
  correct_answer: string | null;
  needs_review?: boolean;
  needs_answer_review?: boolean;
  answer_confidence?: "confirmed" | "unknown";
  explanation: string;
  rubric?: RubricCriterion[];
  starter_code?: string;
  withCorrection?: boolean;
  image_asset_ids?: string[];
  classification_confidence?: string | number | null;
  source_page?: number | null;
  source_block_ids?: string[] | null;
  source_checksum?: string | null;
  raw_text?: string | null;
}

export interface QuizDraftResponse {
  title: string;
  description: string;
  questions: GeneratedQuestion[];
  is_complete?: boolean;
  total_points: number | null;
  requires_teacher_approval: boolean;
  cached: boolean;
  metadata: Record<string, unknown>;
}

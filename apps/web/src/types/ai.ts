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

export interface GeneratedQuestion {
  id: number;
  question_type: "multiple_choice" | "short_answer" | "coding" | "essay" | "fill_in_the_blank" | "true_false" | "fill_in_blank";
  difficulty: "easy" | "medium" | "hard";
  topic: string;
  points: number;
  question_text: string;
  options?: CourseOption[];
  correct_answer: string | null;
  explanation: string;
  rubric?: RubricCriterion[];
  starter_code?: string;
  withCorrection?: boolean;
  image_asset_ids?: string[];
}

export interface QuizDraftResponse {
  title: string;
  description: string;
  questions: GeneratedQuestion[];
  is_complete?: boolean;
  total_points: number;
  requires_teacher_approval: boolean;
  cached: boolean;
  metadata: Record<string, unknown>;
}

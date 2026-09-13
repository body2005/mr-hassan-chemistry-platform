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
  correct_answer: string;
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

export interface CriterionGradingResult {
  criterion_id: string;
  criterion_name: string;
  score_awarded: number;
  max_points: number;
  feedback: string;
}

export interface EssayGradingResponse {
  total_score: number;
  max_score: number;
  percentage: number;
  criteria_breakdown: CriterionGradingResult[];
  feedback_summary: string;
  confidence_score: number;
  flagged_for_human_review: boolean;
  requires_teacher_approval: boolean;
  cached: boolean;
}

export interface PassageCitation {
  chunk_id: string;
  lesson_id: string;
  lesson_title?: string;
  snippet: string;
  similarity_score: number;
}

export interface TutorChatResponse {
  answer: string;
  citations: PassageCitation[];
  is_grounded: boolean;
  session_id: string;
  refusal: boolean;
}

export interface RiskFactor {
  feature: string;
  impact: "high" | "moderate" | "low";
  description: string;
}

export interface StudentRiskPrediction {
  student_id: string;
  risk_score: number;
  risk_level: "low" | "moderate" | "high" | "critical";
  top_risk_factors: RiskFactor[];
  confidence_interval: { lower: number; upper: number };
  model_version: string;
}

export interface BatchRiskResponse {
  predictions: StudentRiskPrediction[];
  total_students: number;
  at_risk_count: number;
  model_metadata: Record<string, unknown>;
}

export interface AnalyticsInterpretationResponse {
  key_findings: string[];
  likely_root_causes: string[];
  actionable_recommendations: string[];
  ta_summary: string;
  cached: boolean;
}

export interface ReportNarrativeResponse {
  course_title: string;
  executive_summary: string;
  module_performance_narrative: string;
  retention_and_risk_narrative: string;
  pedagogical_interventions_narrative: string;
  full_markdown_report: string;
  cached: boolean;
}

export interface SystemMetricsResponse {
  requests: {
    total: number;
    breakdown: Record<string, number>;
  };
  errors: Record<string, number>;
  cache: {
    hits: number;
    misses: number;
    hit_rate: number;
  };
  resource_load: {
    active_local_gpu_inferences: number;
  };
  tokens: {
    prompt_tokens_by_provider: Record<string, number>;
    completion_tokens_by_provider: Record<string, number>;
    total_tokens: number;
  };
  latency_ms: Record<string, {
    count: number;
    avg_ms?: number;
    p50_ms?: number;
    p95_ms?: number;
    p99_ms?: number;
  }>;
}

export interface SystemHealthResponse {
  status: "healthy" | "degraded";
  environment: string;
  version: string;
  provider: {
    name: string;
    healthy: boolean;
    models: string[];
    error?: string | null;
  };
  redis_connected: boolean;
}

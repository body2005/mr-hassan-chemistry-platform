"""One disclosure policy for official results and separate self-training."""

PENDING_RESULT_MESSAGE = "تم تسليم الاختبار، والنتيجة في انتظار اعتماد المدرس"


def result_is_visible(attempt) -> bool:
    # Practice is never an official grade. Unmarked essays remain pending even
    # in practice; no literal or AI marking is introduced here.
    return bool(attempt.results_approved_at or
                (attempt.is_practice and attempt.grading_status == "complete"))


def student_attempt_response(attempt):
    from app.schemas import QuizAttemptResponse
    response = QuizAttemptResponse.model_validate(attempt)
    visible = result_is_visible(attempt)
    return response.model_copy(update={
        "score": response.score if visible else None,
        "calculated_score": response.calculated_score if visible else None,
        "final_percentage": response.final_percentage if visible else None,
        "grading_status": response.grading_status if visible else "pending",
        "approval_status": "approved" if attempt.results_approved_at else
                           "practice" if visible else "pending",
    })

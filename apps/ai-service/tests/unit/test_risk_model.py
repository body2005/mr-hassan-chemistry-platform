import numpy as np
import pytest
from app.schemas.risk import RiskModelTrainRequest, StudentFeatures
from app.services.risk_service import StudentRiskEngine


def test_student_risk_engine_predictions():
    engine = StudentRiskEngine()

    high_risk_student = StudentFeatures(
        student_id="student_at_risk_1",
        login_frequency_weekly=0.5,
        assignments_submitted_ratio=0.3,
        average_quiz_score=45.0,
        late_submissions_count=4,
        forum_posts_count=0,
        time_spent_hours_weekly=1.0,
        video_watch_completion_ratio=0.1,
        days_since_last_activity=9
    )

    low_risk_student = StudentFeatures(
        student_id="student_good_1",
        login_frequency_weekly=7.0,
        assignments_submitted_ratio=1.0,
        average_quiz_score=92.0,
        late_submissions_count=0,
        forum_posts_count=5,
        time_spent_hours_weekly=8.5,
        video_watch_completion_ratio=0.95,
        days_since_last_activity=1
    )

    result = engine.predict_student_risk([high_risk_student, low_risk_student])

    assert result.total_students == 2
    assert result.predictions[0].risk_score > result.predictions[1].risk_score
    assert result.predictions[0].risk_level in ["high", "critical"]
    assert result.predictions[1].risk_level in ["low", "moderate"]

    # Check explainability factors
    high_risk_factors = [f.feature for f in result.predictions[0].top_risk_factors]
    assert "days_since_last_activity" in high_risk_factors
    assert "assignments_submitted_ratio" in high_risk_factors


def test_stratified_group_kfold_training():
    engine = StudentRiskEngine()

    # Generate synthetic training records with 3 cohorts
    records = []
    np.random.seed(42)
    for cohort in ["cohort_A", "cohort_B", "cohort_C"]:
        for i in range(30):
            is_risk = int(np.random.rand() > 0.5)
            records.append({
                "student_id": f"{cohort}_{i}",
                "cohort_id": cohort,
                "login_frequency_weekly": np.random.uniform(0.5, 8.0),
                "assignments_submitted_ratio": np.random.uniform(0.2, 1.0),
                "average_quiz_score": np.random.uniform(40.0, 95.0),
                "late_submissions_count": int(np.random.poisson(1)),
                "forum_posts_count": int(np.random.poisson(2)),
                "time_spent_hours_weekly": np.random.uniform(1.0, 10.0),
                "video_watch_completion_ratio": np.random.uniform(0.1, 1.0),
                "days_since_last_activity": int(np.random.uniform(0, 10)),
                "is_at_risk": is_risk
            })

    train_req = RiskModelTrainRequest(
        training_data=records,
        model_type="logistic_regression",
        n_splits=3
    )

    train_resp = engine.train_model(train_req)

    assert train_resp.status == "success"
    assert train_resp.grouping_strategy_used == "StratifiedGroupKFold"
    assert 0.0 <= train_resp.cv_roc_auc <= 1.0
    assert 0.0 <= train_resp.cv_brier_score <= 1.0


def test_stratified_kfold_training_flat_dataset():
    engine = StudentRiskEngine()

    # Flat dataset with no cohort key
    records = []
    np.random.seed(101)
    for i in range(50):
        records.append({
            "student_id": f"student_{i}",
            "login_frequency_weekly": np.random.uniform(0.5, 8.0),
            "assignments_submitted_ratio": np.random.uniform(0.2, 1.0),
            "average_quiz_score": np.random.uniform(40.0, 95.0),
            "late_submissions_count": 0,
            "forum_posts_count": 1,
            "time_spent_hours_weekly": 5.0,
            "video_watch_completion_ratio": 0.8,
            "days_since_last_activity": 2,
            "is_at_risk": int(i % 2 == 0)
        })

    train_req = RiskModelTrainRequest(
        training_data=records,
        model_type="logistic_regression",
        n_splits=5
    )

    train_resp = engine.train_model(train_req)

    assert train_resp.status == "success"
    assert train_resp.grouping_strategy_used == "StratifiedKFold"

import asyncio
from typing import Any, Dict, List
from app.core.logging import logger
from app.schemas.grading import EssayGradingRequest
from app.schemas.quiz import QuizGenerationRequest
from app.schemas.reports import ReportNarrativeRequest
from app.schemas.risk import RiskModelTrainRequest
from app.schemas.tutor import IndexCourseRequest
from app.services.analytics_service import analytics_service
from app.services.grading_service import grading_service
from app.services.quiz_service import quiz_service
from app.services.report_service import report_service
from app.services.risk_service import risk_engine
from app.services.tutor_service import tutor_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.batch_generate_quiz", bind=True)
def task_batch_generate_quiz(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Background task for long-running quiz generation across multi-lesson units."""
    logger.info(f"Starting async quiz generation task {self.request.id}")
    req = QuizGenerationRequest.model_validate(request_data)
    result = asyncio.run(quiz_service.generate_quiz_draft(req))
    return result.model_dump()


@celery_app.task(name="tasks.batch_grade_essays", bind=True)
def task_batch_grade_essays(self, requests_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Background task for batch grading an entire classroom's essay submissions."""
    logger.info(f"Starting async batch essay grading task {self.request.id} for {len(requests_list)} submissions")
    results = []
    for item in requests_list:
        req = EssayGradingRequest.model_validate(item)
        res = asyncio.run(grading_service.grade_essay(req))
        results.append(res.model_dump())
    return results


@celery_app.task(name="tasks.batch_index_course", bind=True)
def task_batch_index_course(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Background task for bulk chunking & pgvector indexing of newly published course materials."""
    logger.info(f"Starting async course indexing task {self.request.id}")
    req = IndexCourseRequest.model_validate(request_data)
    result = asyncio.run(tutor_service.index_course(req))
    return result.model_dump()


@celery_app.task(name="tasks.batch_generate_report_narrative", bind=True)
def task_batch_generate_report_narrative(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Background task for end-of-term or department-wide narrative report prose generation."""
    logger.info(f"Starting async report narrative task {self.request.id}")
    req = ReportNarrativeRequest.model_validate(request_data)
    result = asyncio.run(report_service.generate_report_narrative(req))
    return result.model_dump()


@celery_app.task(name="tasks.train_risk_model", bind=True)
def task_train_risk_model(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Background task for scheduled or on-demand retraining of tabular student risk models."""
    logger.info(f"Starting async risk model training task {self.request.id}")
    req = RiskModelTrainRequest.model_validate(request_data)
    result = risk_engine.train_model(req)
    return result.model_dump()

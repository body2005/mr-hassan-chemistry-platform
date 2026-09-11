from fastapi import APIRouter
from app.api.v1 import analytics, grading, quiz, reports, risk, tasks, telemetry, tutor

api_router = APIRouter()

# Register all domain routes
api_router.include_router(telemetry.router)
api_router.include_router(quiz.router)
api_router.include_router(grading.router)
api_router.include_router(tutor.router)
api_router.include_router(risk.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(tasks.router)

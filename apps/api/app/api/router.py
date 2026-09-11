from fastapi import APIRouter

from app.api.routes import (
    ai,
    ai_demo,
    analytics_report,
    auth,
    courses,
    extended_routes,
    health,
    knowledge_center,
    platform,
    telemetry,
    transcription,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(courses.router, tags=["courses"])
api_router.include_router(telemetry.router, tags=["telemetry"])
api_router.include_router(platform.router, tags=["platform"])
api_router.include_router(ai.router, tags=["ai"])
api_router.include_router(ai_demo.router, tags=["ai"])
api_router.include_router(knowledge_center.router, tags=["knowledge-center"])
api_router.include_router(extended_routes.router, tags=["extended"])
api_router.include_router(analytics_report.router, tags=["analytics"])
api_router.include_router(transcription.router, tags=["transcription"])


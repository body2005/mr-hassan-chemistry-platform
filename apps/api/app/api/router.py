from fastapi import APIRouter

from app.api.routes import (
    access_requests,
    ai_demo,
    analytics_report,
    auth,
    courses,
    extended_routes,
    health,
    platform,
    payments,
    realtime,
    telemetry,
    transcription,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(courses.router, tags=["courses"])
api_router.include_router(access_requests.router, tags=["lesson_access"])
api_router.include_router(telemetry.router, tags=["telemetry"])
api_router.include_router(platform.router, tags=["platform"])
api_router.include_router(payments.router, tags=["payments"])
api_router.include_router(realtime.router, tags=["realtime"])
api_router.include_router(ai_demo.router, tags=["ai"])
api_router.include_router(extended_routes.router, tags=["extended"])
api_router.include_router(analytics_report.router, tags=["analytics"])
api_router.include_router(transcription.router, tags=["transcription"])
api_router.add_api_route(
    "/bootstrap",
    platform.get_bootstrap_data,
    methods=["GET"],
    response_model=platform.BootstrapResponse,
    tags=["platform"],
)


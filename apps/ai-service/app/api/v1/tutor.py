from fastapi import APIRouter, Depends, Request
from app.core.security import verify_api_key
from app.schemas.tutor import (
    IndexCourseRequest,
    IndexCourseResponse,
    TutorChatRequest,
    TutorChatResponse,
)
from app.services.tutor_service import tutor_service
from app.traffic.rate_limiter import rate_limiter

router = APIRouter(prefix="/tutor", tags=["Conversational Tutor (RAG)"])


@router.post("/index-course", response_model=IndexCourseResponse, dependencies=[Depends(verify_api_key)])
async def index_course_content(
    request_data: IndexCourseRequest
) -> IndexCourseResponse:
    """
    Ingests and indexes course content chunks with dense vector embeddings into pgvector.
    """
    return await tutor_service.index_course(request_data)


@router.post("/chat", response_model=TutorChatResponse, dependencies=[Depends(verify_api_key)])
async def chat_with_tutor(
    request_data: TutorChatRequest,
    request: Request
) -> TutorChatResponse:
    """
    Interactive, grounded tutoring chat:
    - Answers grounded exclusively in retrieved course passages.
    - Resolves contextual follow-ups through bounded memory.
    - Explicitly refuses to answer when course material lacks evidence.
    - Gated by student rate limits and GPU admission control.
    """
    # Rate limit by student ID
    await rate_limiter.check_rate_limit(f"tutor:{request_data.student_id}", limit=30, window_seconds=60)

    return await tutor_service.chat(request_data)

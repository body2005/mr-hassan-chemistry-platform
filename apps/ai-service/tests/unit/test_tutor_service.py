import pytest
from app.providers.mock_provider import MockProvider
from app.schemas.tutor import CourseChunkInput, IndexCourseRequest, TutorChatRequest
from app.services.tutor_service import TutorService
from app.vector.retriever import vector_retriever


@pytest.mark.asyncio
async def test_tutor_indexing_and_grounded_response():
    mock_provider = MockProvider(embedding_dim=32)
    mock_provider.set_mock_chat_response("Based on Lesson 1, chloroplasts absorb sunlight to produce glucose.")

    service = TutorService(provider=mock_provider)
    vector_retriever.clear()

    # 1. Index course content
    index_req = IndexCourseRequest(
        course_id="bio_101",
        chunks=[
            CourseChunkInput(
                lesson_id="lesson_1",
                content="Chloroplasts are specialized organelles containing chlorophyll that conduct photosynthesis.",
                title="Cell Organelles"
            )
        ]
    )
    index_res = await service.index_course(index_req)
    assert index_res.indexed_chunks_count == 1

    # 2. Chat with question
    # Temporarily set similarity threshold low so mock vectors match
    service.settings.VECTOR_SIMILARITY_THRESHOLD = -1.0

    chat_req = TutorChatRequest(
        course_id="bio_101",
        student_id="student_1",
        session_id="session_bio_1",
        message="What do chloroplasts do?"
    )

    chat_res = await service.chat(chat_req)
    assert chat_res.is_grounded is True
    assert chat_res.refusal is False
    assert len(chat_res.citations) == 1
    assert chat_res.citations[0].lesson_id == "lesson_1"
    assert "chloroplasts" in chat_res.answer.lower()


@pytest.mark.asyncio
async def test_tutor_refusal_when_ungrounded():
    mock_provider = MockProvider(embedding_dim=32)
    service = TutorService(provider=mock_provider)
    vector_retriever.clear()

    # Strict high threshold with empty/dissimilar database
    service.settings.VECTOR_SIMILARITY_THRESHOLD = 0.99

    chat_req = TutorChatRequest(
        course_id="empty_course",
        student_id="student_2",
        session_id="session_empty",
        message="Explain quantum entanglement in depth."
    )

    chat_res = await service.chat(chat_req)
    assert chat_res.is_grounded is False
    assert chat_res.refusal is True
    assert len(chat_res.citations) == 0
    assert "do not have enough material" in chat_res.answer.lower()

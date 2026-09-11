import pytest
from httpx import AsyncClient
from app.vector.retriever import vector_retriever


@pytest.mark.asyncio
async def test_tutor_api_lifecycle(async_client: AsyncClient):
    vector_retriever.clear()

    # 1. Index course content
    index_payload = {
        "course_id": "cs_50",
        "chunks": [
            {
                "lesson_id": "week_1_c",
                "content": "In C programming, pointers store memory addresses of other variables.",
                "title": "Pointers and Memory"
            }
        ]
    }
    resp_index = await async_client.post("/api/v1/tutor/index-course", json=index_payload)
    assert resp_index.status_code == 200
    assert resp_index.json()["indexed_chunks_count"] == 1

    # 2. Chat with tutor
    chat_payload = {
        "course_id": "cs_50",
        "student_id": "student_alice",
        "session_id": "sess_alice_1",
        "message": "What is a pointer?"
    }
    resp_chat = await async_client.post("/api/v1/tutor/chat", json=chat_payload)
    assert resp_chat.status_code == 200
    data = resp_chat.json()
    assert "answer" in data
    assert "session_id" in data

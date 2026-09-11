import pytest
from app.traffic.cache import RequestCache


@pytest.mark.asyncio
async def test_cache_deterministic_key_generation():
    cache = RequestCache()
    payload_1 = {"lesson_id": "math_101", "question_count": 5, "topics": ["algebra", "geometry"]}
    payload_2 = {"topics": ["algebra", "geometry"], "question_count": 5, "lesson_id": "math_101"}

    key_1 = cache.generate_key("quiz", payload_1)
    key_2 = cache.generate_key("quiz", payload_2)

    # Identical JSON structures regardless of dict key ordering should generate identical hash keys
    assert key_1 == key_2
    assert key_1.startswith("ai_cache:quiz:v1:")


@pytest.mark.asyncio
async def test_cache_set_and_get():
    cache = RequestCache()
    key = cache.generate_key("quiz", {"test": "data"})
    test_data = {"questions": [{"id": 1, "text": "What is 2+2?"}]}

    await cache.set(key, "quiz", test_data)
    retrieved = await cache.get(key)
    assert retrieved == test_data

    # Test bypass cache flag
    bypassed = await cache.get(key, bypass_cache=True)
    assert bypassed is None

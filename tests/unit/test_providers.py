import pytest
from pydantic import BaseModel
from app.core.exceptions import SchemaValidationException
from app.providers.base import ChatMessage
from app.providers.mock_provider import MockProvider
from app.providers.utils import clean_json_string, parse_and_validate


class SampleSchema(BaseModel):
    title: str
    item_count: int
    is_valid: bool


def test_clean_json_string():
    raw_markdown = """Here is the result you requested:
```json
{
  "title": "Introduction to AI",
  "item_count": 10,
  "is_valid": true
}
```
Hope this helps!"""
    cleaned = clean_json_string(raw_markdown)
    assert cleaned.startswith("{")
    assert cleaned.endswith("}")
    assert '"title": "Introduction to AI"' in cleaned


def test_parse_and_validate_success():
    raw = '{"title": "Test Title", "item_count": 5, "is_valid": true}'
    obj = parse_and_validate(raw, SampleSchema)
    assert obj.title == "Test Title"
    assert obj.item_count == 5
    assert obj.is_valid is True


def test_parse_and_validate_failure():
    invalid_raw = '{"title": "Test Title", "item_count": "not_an_int"}'
    with pytest.raises(SchemaValidationException):
        parse_and_validate(invalid_raw, SampleSchema)


@pytest.mark.asyncio
async def test_mock_provider_structured():
    provider = MockProvider()
    provider.set_mock_structured_data({
        "title": "Calculus 101",
        "item_count": 8,
        "is_valid": True
    })

    result = await provider.generate_structured(
        messages=[ChatMessage(role="user", content="Generate syllabus")],
        schema=SampleSchema
    )
    assert isinstance(result, SampleSchema)
    assert result.title == "Calculus 101"
    assert result.item_count == 8


@pytest.mark.asyncio
async def test_mock_provider_embeddings():
    provider = MockProvider(embedding_dim=64)
    resp = await provider.generate_embeddings(["Passage 1", "Passage 2"])
    assert len(resp.embeddings) == 2
    assert len(resp.embeddings[0]) == 64

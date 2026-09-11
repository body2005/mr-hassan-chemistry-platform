import json
import re
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from app.core.exceptions import SchemaValidationException
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


def clean_json_string(raw_text: str) -> str:
    """
    Strips markdown code blocks, XML tags, or conversational prefixes to extract pure JSON.
    """
    text = raw_text.strip()

    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # Find start and end of outer JSON structure (object or array)
    start_obj = text.find("{")
    start_arr = text.find("[")

    if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
        end_obj = text.rfind("}")
        if end_obj != -1:
            text = text[start_obj:end_obj + 1]
    elif start_arr != -1:
        end_arr = text.rfind("]")
        if end_arr != -1:
            text = text[start_arr:end_arr + 1]

    return text


def parse_and_validate(raw_text: str, schema: Type[T]) -> T:
    """
    Attempts to extract JSON from raw model text and parse into target Pydantic schema.
    """
    cleaned = clean_json_string(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as jde:
        logger.error(f"JSON decode failed on model output: {jde}. Raw text preview: {raw_text[:200]}")
        raise SchemaValidationException(
            message=f"Model output is not valid JSON: {str(jde)}",
            validation_errors={"raw_sample": raw_text[:300]}
        )

    try:
        return schema.model_validate(data)
    except ValidationError as ve:
        logger.error(f"Schema validation failed: {ve}")
        raise SchemaValidationException(
            message="Model output violated expected schema structure.",
            validation_errors=ve.errors()
        )

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
)


class TrackingColumnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    data_type: Literal["text", "number", "percentage", "checkbox"]
    table_context: Literal["submissions", "students"]
    academic_year: Literal["1st_secondary", "2nd_secondary", "3rd_secondary", "all"]

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid column name")
        return value


class TrackingColumnRead(TrackingColumnCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class TrackingValueWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: StrictStr | StrictInt | StrictFloat | StrictBool = Field()


class TrackingSnapshot(BaseModel):
    columns: list[TrackingColumnRead]
    values: dict[str, dict[str, str | float | bool]]

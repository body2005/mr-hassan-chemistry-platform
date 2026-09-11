from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CourseChunkInput(BaseModel):
    lesson_id: str = Field(..., description="Unique identifier for the lesson within the course")
    content: str = Field(..., min_length=10, description="Text chunk content")
    title: Optional[str] = Field(None, description="Optional section/lesson title")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IndexCourseRequest(BaseModel):
    course_id: str = Field(..., description="Unique identifier for the course")
    chunks: List[CourseChunkInput] = Field(..., min_length=1, description="List of text chunks to index into pgvector")


class IndexCourseResponse(BaseModel):
    course_id: str
    indexed_chunks_count: int
    status: str = "success"
    message: str = "Course content successfully indexed into vector store."


class PassageCitation(BaseModel):
    chunk_id: str
    lesson_id: str
    snippet: str
    similarity_score: float = Field(..., ge=-1.0, le=1.0)


class TutorChatRequest(BaseModel):
    course_id: str = Field(..., description="Course context for RAG retrieval")
    student_id: str = Field(..., description="Student identifier for session isolation and rate limiting")
    session_id: str = Field(..., description="Conversation session ID for bounded memory tracking")
    message: str = Field(..., min_length=1, description="Student's natural language question or follow-up")
    temperature: Optional[float] = Field(0.5, ge=0.0, le=1.0)


class TutorChatResponse(BaseModel):
    answer: str
    citations: List[PassageCitation] = Field(default_factory=list)
    is_grounded: bool = True
    session_id: str
    refusal: bool = False

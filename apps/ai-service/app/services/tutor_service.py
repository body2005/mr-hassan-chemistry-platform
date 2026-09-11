from typing import List, Optional
from app.config import get_settings
from app.core.logging import logger
from app.providers.base import AIProvider, ChatMessage
from app.providers.factory import get_ai_provider
from app.schemas.tutor import (
    IndexCourseRequest,
    IndexCourseResponse,
    PassageCitation,
    TutorChatRequest,
    TutorChatResponse,
)
from app.services.memory_service import memory_manager
from app.traffic.admission import admission_controller
from app.vector.retriever import vector_retriever


class TutorService:
    """
    RAG-Powered Conversational Tutor:
    - Answers grounded exclusively in retrieved course passages.
    - Employs strict similarity threshold gating: explicitly refuses when material is lacking.
    - Maintains bounded conversational memory for contextual follow-up resolution.
    - Guards inference capacity via admission control.
    """

    REFUSAL_MESSAGE = (
        "I do not have enough material in this course's content to answer your question accurately. "
        "Please consult your instructor or the official course readings."
    )

    def __init__(self, provider: Optional[AIProvider] = None):
        self.settings = get_settings()
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        return self._provider or get_ai_provider()

    async def index_course(self, request: IndexCourseRequest) -> IndexCourseResponse:
        texts = [chunk.content for chunk in request.chunks]
        emb_response = await self.provider.generate_embeddings(texts)
        
        indexed_count = vector_retriever.index_chunks(
            course_id=request.course_id,
            chunks=request.chunks,
            embeddings=emb_response.embeddings
        )

        return IndexCourseResponse(
            course_id=request.course_id,
            indexed_chunks_count=indexed_count,
            status="success",
            message=f"Indexed {indexed_count} course content passages."
        )

    async def chat(self, request: TutorChatRequest) -> TutorChatResponse:
        # 1. Embed query
        emb_res = await self.provider.generate_embeddings([request.message])
        query_emb = emb_res.embeddings[0]

        # 2. Retrieve relevant course chunks
        scored_chunks = vector_retriever.search_similar(
            course_id=request.course_id,
            query_embedding=query_emb,
            top_k=self.settings.TOP_K_CHUNKS,
            similarity_threshold=self.settings.VECTOR_SIMILARITY_THRESHOLD
        )

        # 3. Guardrail: Grounding Check & Refusal
        if not scored_chunks:
            logger.info(f"Tutor query '{request.message[:40]}' yielded zero chunks above threshold for course '{request.course_id}'. Returning refusal.")
            memory_manager.add_user_message(request.session_id, request.message)
            memory_manager.add_assistant_message(request.session_id, self.REFUSAL_MESSAGE)

            return TutorChatResponse(
                answer=self.REFUSAL_MESSAGE,
                citations=[],
                is_grounded=False,
                session_id=request.session_id,
                refusal=True
            )

        # 4. Construct Citations
        citations: List[PassageCitation] = []
        passages_text_blocks: List[str] = []
        for idx, (chunk, sim) in enumerate(scored_chunks, start=1):
            snippet = chunk.content[:150] + "..." if len(chunk.content) > 150 else chunk.content
            citations.append(PassageCitation(
                chunk_id=chunk.chunk_id,
                lesson_id=chunk.lesson_id,
                snippet=snippet,
                similarity_score=round(max(-1.0, min(1.0, sim)), 4)
            ))
            passages_text_blocks.append(
                f"[Passage {idx}] (Lesson ID: {chunk.lesson_id}):\n{chunk.content}"
            )

        joined_passages = "\n\n".join(passages_text_blocks)

        # 5. Build Grounded Prompt with Bounded Memory
        system_instruction = (
            "You are a helpful, encouraging, and highly precise academic tutor for an online course.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Answer the student's question based STRICTLY and ONLY on the course passages provided below.\n"
            "2. When explaining concepts or providing examples, point back to the relevant passage.\n"
            "3. If the passages do not contain enough information to fully resolve the question, state so plainly.\n"
            "4. NEVER invent facts or hallucinate external knowledge not grounded in the provided passages.\n\n"
            f"=== RETRIEVED COURSE PASSAGES ===\n"
            f"{joined_passages}\n"
            f"================================="
        )

        history_messages = memory_manager.get_history_messages(request.session_id)

        prompt_messages: List[ChatMessage] = [
            ChatMessage(role="system", content=system_instruction)
        ]
        prompt_messages.extend(history_messages)
        prompt_messages.append(ChatMessage(role="user", content=request.message))

        # 6. Acquire GPU Slot & Generate Chat
        async with admission_controller.acquire_slot():
            chat_response = await self.provider.generate_chat(
                messages=prompt_messages,
                temperature=request.temperature or 0.5
            )

            memory_manager.add_user_message(request.session_id, request.message)
            memory_manager.add_assistant_message(request.session_id, chat_response.content)

            return TutorChatResponse(
                answer=chat_response.content,
                citations=citations,
                is_grounded=True,
                session_id=request.session_id,
                refusal=False
            )


tutor_service = TutorService()

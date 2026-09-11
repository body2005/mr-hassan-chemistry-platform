from collections import defaultdict, deque
from typing import Dict, List, Optional
from app.providers.base import ChatMessage


class SessionMemory:
    def __init__(self, session_id: str, max_verbatim_turns: int = 4):
        self.session_id = session_id
        self.max_verbatim_turns = max_verbatim_turns
        self.running_summary: str = ""
        self.recent_turns: deque[ChatMessage] = deque()

    def add_turn(self, role: str, content: str):
        self.recent_turns.append(ChatMessage(role=role, content=content))
        # If we have exceeded our bounded verbatim window, condense older turns into summary
        if len(self.recent_turns) > self.max_verbatim_turns:
            oldest_user = self.recent_turns.popleft()
            oldest_assistant = self.recent_turns.popleft() if self.recent_turns else None

            condensed = f"User asked: '{oldest_user.content[:100]}'."
            if oldest_assistant:
                condensed += f" Tutor explained: '{oldest_assistant.content[:100]}'."

            if self.running_summary:
                self.running_summary = f"{self.running_summary} Then, {condensed}"
            else:
                self.running_summary = f"Earlier conversation summary: {condensed}"

            # Keep summary bounded
            if len(self.running_summary) > 600:
                self.running_summary = self.running_summary[-600:]

    def get_messages_for_prompt(self) -> List[ChatMessage]:
        messages: List[ChatMessage] = []
        if self.running_summary:
            messages.append(ChatMessage(
                role="system",
                content=f"[Context from earlier in session]: {self.running_summary}"
            ))
        messages.extend(list(self.recent_turns))
        return messages


class BoundedMemoryManager:
    """
    Bounded Conversational Memory Manager:
    - Retains recent turns verbatim to resolve contextual follow-ups ("give me an example").
    - Recursively compresses older dialogue turns into a bounded running summary.
    - Prevents unbounded context growth and token bloat.
    """

    def __init__(self, max_verbatim_turns: int = 4):
        self.max_verbatim_turns = max_verbatim_turns
        self._sessions: Dict[str, SessionMemory] = defaultdict(
            lambda: SessionMemory(session_id="", max_verbatim_turns=self.max_verbatim_turns)
        )

    def get_session(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(session_id=session_id, max_verbatim_turns=self.max_verbatim_turns)
        return self._sessions[session_id]

    def add_user_message(self, session_id: str, content: str):
        session = self.get_session(session_id)
        session.add_turn(role="user", content=content)

    def add_assistant_message(self, session_id: str, content: str):
        session = self.get_session(session_id)
        session.add_turn(role="assistant", content=content)

    def get_history_messages(self, session_id: str) -> List[ChatMessage]:
        session = self.get_session(session_id)
        return session.get_messages_for_prompt()

    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)


memory_manager = BoundedMemoryManager()

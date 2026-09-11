import pytest
from app.services.memory_service import BoundedMemoryManager


def test_bounded_memory_manager_maintains_recent_and_summarizes():
    mgr = BoundedMemoryManager(max_verbatim_turns=4)
    session_id = "sess_test_101"

    # Add 4 turns (2 user, 2 assistant)
    mgr.add_user_message(session_id, "What is photosynthesis?")
    mgr.add_assistant_message(session_id, "Photosynthesis is how plants convert light to energy.")
    mgr.add_user_message(session_id, "Where does it happen?")
    mgr.add_assistant_message(session_id, "It happens in the chloroplasts.")

    session = mgr.get_session(session_id)
    assert len(session.recent_turns) == 4
    assert session.running_summary == ""

    # Add 5th and 6th turns (exceeding window)
    mgr.add_user_message(session_id, "Give me an example.")
    mgr.add_assistant_message(session_id, "For instance, tree leaves absorbing sunlight.")

    # The oldest turns should have been rolled into running_summary
    assert len(session.recent_turns) <= 4
    assert len(session.running_summary) > 0
    assert "photosynthesis" in session.running_summary.lower()

    # Prompt messages should contain system context summary + recent turns
    prompt_msgs = mgr.get_history_messages(session_id)
    assert prompt_msgs[0].role == "system"
    assert "earlier in session" in prompt_msgs[0].content.lower()
    assert prompt_msgs[-1].content == "For instance, tree leaves absorbing sunlight."

"""Unit tests for modular orchestrator agent stubs."""

from __future__ import annotations

from automated_software_developer.agent.dev_agent import DevAgent
from automated_software_developer.agent.models import StoryExecutionState
from automated_software_developer.agent.q_agent import QAgent
from automated_software_developer.agent.review_agent import ReviewAgent
from automated_software_developer.agent.task_queue import SerialTaskQueue


def test_dev_agent_creates_bundle() -> None:
    """DevAgent should deserialize execution bundle payloads."""
    agent = DevAgent()
    bundle = agent.prepare_bundle(
        {
            "summary": "initial write",
            "operations": [{"op": "write_file", "path": "README.md", "content": "ok"}],
            "verification_commands": [],
        }
    )
    assert bundle.summary == "initial write"


def test_q_and_review_agents() -> None:
    """QAgent and ReviewAgent should provide simple orchestration decisions."""
    review = ReviewAgent()
    q_agent = QAgent()
    assert q_agent.passed([])
    state = StoryExecutionState(
        story_id="S-1",
        attempt=1,
        status="failed",
        verification_results=[],
        error="verification failed",
    )
    assert review.needs_retry(state)


def test_serial_task_queue_order() -> None:
    """SerialTaskQueue should preserve item order."""
    queue = SerialTaskQueue[int, int]()
    assert queue.map([1, 2, 3], lambda item: item * 2) == [2, 4, 6]

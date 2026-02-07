"""Event broker for UI websocket/SSE streaming."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    """Event emitted to the UI."""

    event_id: str
    project_id: str
    event_type: str
    message: str
    timestamp: datetime
    reason: str | None = None
    artifact_url: str | None = None

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        event_type: str,
        message: str,
        reason: str | None = None,
        artifact_url: str | None = None,
    ) -> Event:
        return cls(
            event_id=uuid4().hex,
            project_id=project_id,
            event_type=event_type,
            message=message,
            timestamp=datetime.now(UTC),
            reason=reason,
            artifact_url=artifact_url,
        )


class EventBroker:
    """In-memory event broker for streaming updates."""

    def __init__(self) -> None:
        self._history: defaultdict[str, list[Event]] = defaultdict(list)
        self._subscribers: defaultdict[str, list[asyncio.Queue[Event]]] = defaultdict(list)

    def publish(self, event: Event) -> None:
        """Publish an event to subscribers and store in history."""
        self._history[event.project_id].append(event)
        for queue in list(self._subscribers[event.project_id]):
            queue.put_nowait(event)

    def history(self, project_id: str) -> list[Event]:
        """Return historical events for a project."""
        return list(self._history.get(project_id, []))

    def subscribe(self, project_id: str) -> asyncio.Queue[Event]:
        """Subscribe to future events for a project."""
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers[project_id].append(queue)
        return queue

    def unsubscribe(self, project_id: str, queue: asyncio.Queue[Event]) -> None:
        """Remove a subscriber queue."""
        if queue in self._subscribers.get(project_id, []):
            self._subscribers[project_id].remove(queue)

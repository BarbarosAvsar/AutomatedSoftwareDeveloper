"""Task queue abstraction used by orchestrator prompt prefetching."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Generic, TypeVar

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class TaskQueue(Generic[TInput, TOutput]):
    """Interface for queue-backed task execution."""

    def map(self, items: Iterable[TInput], fn: Callable[[TInput], TOutput]) -> list[TOutput]:
        """Apply a callable to each item and return ordered outputs."""
        raise NotImplementedError


class SerialTaskQueue(TaskQueue[TInput, TOutput]):
    """Deterministic in-process queue implementation."""

    def map(self, items: Iterable[TInput], fn: Callable[[TInput], TOutput]) -> list[TOutput]:
        """Execute tasks serially in call order."""
        return [fn(item) for item in items]


class CeleryTaskQueueStub(TaskQueue[TInput, TOutput]):
    """Placeholder API-compatible queue for future Celery integration."""

    def __init__(self, queue_name: str = "autosd") -> None:
        """Store queue metadata for a future Celery implementation."""
        self.queue_name = queue_name

    def map(self, items: Iterable[TInput], fn: Callable[[TInput], TOutput]) -> list[TOutput]:
        """Fallback to serial behavior until distributed workers are wired."""
        _ = self.queue_name
        return [fn(item) for item in items]

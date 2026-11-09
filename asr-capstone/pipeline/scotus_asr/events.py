"""Progress reporting, kept separate from the work itself.

Nothing in the pipeline prints. Instead it announces what is happening, and
whoever is listening decides what to do with that. The command line prints it;
the log file records it; a graphical interface would update a progress bar.

This is the one seam a later interface needs. Without it, the choice to print
would be baked into every module and a window would have to scrape stdout.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventKind(str, Enum):
    """What just happened.

    Inherits from `str` so the values write straight to JSON and read as
    themselves in a log line.
    """

    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    TASK_STARTED = "task_started"
    TASK_SKIPPED = "task_skipped"      # already done in an earlier run
    TASK_PROGRESS = "task_progress"    # partway through something slow
    TASK_FINISHED = "task_finished"
    TASK_RETRYING = "task_retrying"
    TASK_FAILED = "task_failed"        # gave up after the last attempt
    WARNING = "warning"                # worth knowing, not worth stopping for


@dataclass(frozen=True)
class Event:
    """One thing that happened, with enough detail to display or log it."""

    kind: EventKind
    message: str
    #: Which task this concerns, as "docket/stage/engine". Absent for run-level events.
    task_id: str | None = None
    #: How far through, from 0 to 1, when that is known.
    fraction: float | None = None
    #: Anything else worth recording: durations, counts, error text.
    detail: dict[str, Any] = field(default_factory=dict)


#: Anything that can receive events. A plain function is enough.
Listener = Callable[[Event], None]


class EventBus:
    """Passes events to whoever is listening.

    A listener that raises is dropped rather than allowed to bring down the run.
    A broken progress bar must never cost you six hours of transcription.
    """

    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        """Add a listener. It will receive every event from now on."""
        self._listeners.append(listener)

    def emit(self, event: Event) -> None:
        """Send an event to every listener."""
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                # Deliberately swallowed. Reporting is not the job.
                logger.exception("A progress listener raised; carrying on.")

    # Small helpers so callers write one line instead of building an Event.

    def task_started(self, task_id: str, message: str) -> None:
        self.emit(Event(EventKind.TASK_STARTED, message, task_id=task_id))

    def task_skipped(self, task_id: str, message: str) -> None:
        self.emit(Event(EventKind.TASK_SKIPPED, message, task_id=task_id))

    def task_progress(self, task_id: str, message: str, fraction: float | None = None) -> None:
        self.emit(Event(EventKind.TASK_PROGRESS, message, task_id=task_id, fraction=fraction))

    def task_finished(self, task_id: str, message: str, **detail: Any) -> None:
        self.emit(Event(EventKind.TASK_FINISHED, message, task_id=task_id, detail=detail))

    def task_failed(self, task_id: str, message: str, **detail: Any) -> None:
        self.emit(Event(EventKind.TASK_FAILED, message, task_id=task_id, detail=detail))

    def task_retrying(
        self, task_id: str, attempt: int, of: int, error: BaseException, wait: float
    ) -> None:
        """Announce that a task failed but is going to be tried again."""
        self.emit(
            Event(
                EventKind.TASK_RETRYING,
                f"Attempt {attempt} of {of} failed ({type(error).__name__}: {error}). "
                f"Waiting {wait:.0f}s before trying again.",
                task_id=task_id,
                detail={"attempt": attempt, "of": of, "error": str(error)},
            )
        )

    def warn(self, message: str, **detail: Any) -> None:
        self.emit(Event(EventKind.WARNING, message, detail=detail))


def log_listener(event: Event) -> None:
    """Write events to the logging system.

    Attach this and everything the run did ends up in `run.log`, which is what
    you read the morning after an unattended run.
    """
    level = logging.INFO
    if event.kind is EventKind.WARNING:
        level = logging.WARNING
    elif event.kind is EventKind.TASK_FAILED:
        level = logging.ERROR

    prefix = f"[{event.task_id}] " if event.task_id else ""
    logger.log(level, "%s%s", prefix, event.message)

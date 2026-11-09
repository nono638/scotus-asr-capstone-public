"""An append-only record of what a run has finished.

One line of JSON per task, written the moment the task ends. Append-only because
a crash can then only ever lose the last line - it can never corrupt the lines
already there, which is exactly what rewriting a whole status file risks.

The ledger is a record, not the source of truth. Whether work needs redoing is
decided by looking at both the ledger *and* the output file, because they can
disagree: a crash between finishing a file and writing its ledger line leaves a
good result unrecorded, and deleting an artifact by hand should cause it to be
rebuilt even though the ledger says otherwise.
"""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .tasks import TaskKey

#: A task that ran to completion.
STATUS_OK = "ok"
#: A task that failed every attempt. Recorded so the morning-after read shows it.
STATUS_FAILED = "failed"
#: A task skipped because its output was already there.
STATUS_SKIPPED = "skipped"


@dataclass(frozen=True)
class LedgerEntry:
    """One finished task."""

    task_id: str
    status: str
    #: When it finished, in UTC, as an ISO-8601 string.
    finished_at: str
    #: How long the work took, in seconds.
    duration_seconds: float = 0.0
    #: How many attempts it needed. More than one means something went wrong first.
    attempts: int = 1
    #: Short summary for a successful task; the error message for a failed one.
    summary: str = ""
    #: The full traceback of a failure, so it can be diagnosed later.
    error: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class Ledger:
    """Reads and appends to one run's `ledger.jsonl`."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # --- writing -----------------------------------------------------------

    def append(self, entry: LedgerEntry) -> None:
        """Add an entry and push it to disk before returning.

        Flushed immediately on purpose. A ledger that is still in a buffer when
        the power goes is a ledger that did not do its job.
        """
        with open(self.path, "a", encoding="utf-8") as stream:
            stream.write(entry.to_json() + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def record_success(
        self, key: TaskKey, duration: float, attempts: int = 1, summary: str = ""
    ) -> None:
        """Record that a task finished."""
        self.append(
            LedgerEntry(
                task_id=str(key),
                status=STATUS_OK,
                finished_at=_now(),
                duration_seconds=round(duration, 3),
                attempts=attempts,
                summary=summary,
            )
        )

    def record_failure(
        self, key: TaskKey, duration: float, attempts: int, error: BaseException
    ) -> None:
        """Record that a task gave up, keeping the traceback."""
        self.append(
            LedgerEntry(
                task_id=str(key),
                status=STATUS_FAILED,
                finished_at=_now(),
                duration_seconds=round(duration, 3),
                attempts=attempts,
                summary=f"{type(error).__name__}: {error}",
                error="".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                ),
            )
        )

    # --- reading -----------------------------------------------------------

    def entries(self) -> Iterator[LedgerEntry]:
        """Every entry, oldest first.

        A damaged final line - the signature of a crash mid-write - is skipped
        rather than allowed to stop the run.
        """
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield LedgerEntry(**json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue

    def completed_ids(self) -> set[str]:
        """Task identifiers that finished successfully.

        A task that failed and was later retried successfully appears twice; the
        success is what counts, and set membership gives that for free.
        """
        return {e.task_id for e in self.entries() if e.status == STATUS_OK}

    def failed_ids(self) -> set[str]:
        """Tasks whose most recent outcome was failure.

        Order matters here, unlike `completed_ids`: a task that failed and then
        succeeded is not a failure, so later entries overwrite earlier ones.
        """
        latest: dict[str, str] = {}
        for entry in self.entries():
            if entry.status in (STATUS_OK, STATUS_FAILED):
                latest[entry.task_id] = entry.status
        return {task_id for task_id, status in latest.items() if status == STATUS_FAILED}


def _now() -> str:
    """The current time in UTC, as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

"""The loop that runs tasks and refuses to give up on the whole run.

Two rules:

**Skip what is already done.** A task whose output file exists and whose ledger
line says it succeeded is not repeated. This is what makes a resumed run cheap.

**One failure is not the end.** Every task is wrapped. If it raises, the error is
recorded with its traceback and the loop moves to the next one. A corrupt MP3 at
case 12 must not cost you the remaining 38 cases overnight.

There is also a gentle way to stop. A file called `STOP` in the run folder (which
`cli stop` writes) is checked before each task starts, so the task in progress
finishes and is saved, and nothing new begins. Ctrl+C stops at once instead and
loses the task in progress - for a long recording, up to an hour of decoding.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Sequence

from .events import EventBus
from .ledger import Ledger
from .store import RunStore
from .tasks import Task

#: The file that asks a run to stop once the task it is on has finished.
STOP_FILE = "STOP"


@dataclass
class RunSummary:
    """What a finished run did. Printed at the end and useful in tests."""

    completed: int = 0
    skipped: int = 0
    failed: int = 0
    seconds: float = 0.0
    failures: list[tuple[str, str]] = None  # (task id, error message)
    stopped: bool = False  # ended early because a stop was asked for

    def __post_init__(self) -> None:
        if self.failures is None:
            self.failures = []

    @property
    def attempted(self) -> int:
        """Tasks that actually ran, ignoring the ones skipped as already done."""
        return self.completed + self.failed

    def describe(self) -> str:
        """A one-line summary for a human."""
        parts = [f"{self.completed} done"]
        if self.skipped:
            parts.append(f"{self.skipped} already done")
        if self.failed:
            parts.append(f"{self.failed} failed")
        line = ", ".join(parts) + f", in {self.seconds:.1f}s"
        if self.stopped:
            line += " - stopped on request, the rest is still to do"
        return line


class Runner:
    """Executes tasks, recording progress as it goes.

    Args:
        store: Where results live. Used to check whether outputs already exist.
        ledger: The record of finished work.
        events: Where progress announcements go.
        max_attempts: How many tries before a task is given up on.
        backoff_seconds: Wait before a retry, doubled each time. Helps with a
            server that is briefly refusing connections; does nothing for a model
            that runs out of memory, which is why the attempt count is small.
    """

    def __init__(
        self,
        store: RunStore,
        ledger: Ledger,
        events: EventBus,
        max_attempts: int = 3,
        backoff_seconds: float = 5.0,
    ) -> None:
        self.store = store
        self.ledger = ledger
        self.events = events
        self.max_attempts = max(1, max_attempts)
        self.backoff_seconds = backoff_seconds
        # Loaded once when a run starts. Held here so `is_done` can be asked
        # before or after a run without blowing up.
        self._completed: set[str] = ledger.completed_ids()

    def is_done(self, task: Task) -> bool:
        """Has this task already finished, in this run or an earlier one?

        Both the output file and the ledger have to agree. They can disagree in
        two ways, and the answer is "not done" for both:

        * The file is there but the ledger has no success line - the crash landed
          between the two. Cheap to redo, and redoing is the safe choice.
        * The ledger says done but the file is gone - someone deleted it, probably
          on purpose to force a rebuild.
        """
        return self.store.has(task.output) and str(task.key) in self._completed

    def run(self, tasks: Iterable[Task]) -> RunSummary:
        """Work through the tasks, in order.

        Args:
            tasks: What to do. Order matters where stages depend on each other -
                a case's transcript has to exist before it can be scored.

        Returns:
            Counts and the list of failures. Never raises for a task failure;
            only a problem with the run itself would propagate.
        """
        task_list: Sequence[Task] = list(tasks)
        summary = RunSummary()
        started = time.monotonic()

        # Read the ledger once. Re-reading per task would be the dominant cost on
        # a run that is mostly skips.
        self._completed = self.ledger.completed_ids()

        # Anything left over from an unclean shutdown is incomplete by definition.
        removed = self.store.clean_temp_files()
        if removed:
            self.events.warn(f"Cleared {removed} unfinished file(s) from a previous run.")

        # A stop request left over from before is cleared: starting the run again
        # is the newer instruction. Otherwise it would stop before doing anything.
        stop_file = self.store.path(STOP_FILE)
        if stop_file.exists():
            stop_file.unlink()
            self.events.warn("Cleared a stop request left over from before this run.")

        for task in task_list:
            if self.is_done(task):
                summary.skipped += 1
                self.events.task_skipped(str(task.key), "Already done, skipping.")
                continue

            # Checked only before work that would actually run, so a resumed run
            # still counts everything already done.
            if stop_file.exists():
                stop_file.unlink()
                summary.stopped = True
                self.events.warn(
                    f"Stopped on request before {task.key}. Finished work is saved - "
                    f"run the same command again to carry on."
                )
                break

            outcome = self._run_one(task)
            if outcome is None:
                summary.completed += 1
                self._completed.add(str(task.key))
            else:
                summary.failed += 1
                summary.failures.append((str(task.key), outcome))

        summary.seconds = time.monotonic() - started
        return summary

    def _run_one(self, task: Task) -> str | None:
        """Run a single task with retries.

        Returns:
            None if it succeeded, otherwise the error message.
        """
        self.events.task_started(str(task.key), task.description or f"Running {task.key}")
        started = time.monotonic()
        last_error: BaseException | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = task.run() or {}
                duration = time.monotonic() - started
                note = _summarize(result)
                self.ledger.record_success(task.key, duration, attempt, note)
                self.events.task_finished(
                    str(task.key),
                    f"Done in {duration:.1f}s{(' - ' + note) if note else ''}",
                    **result,
                )
                return None

            except KeyboardInterrupt:
                # A deliberate stop is not a task failure. Let it through so the
                # run ends promptly instead of retrying three times first.
                raise

            except Exception as error:  # noqa: BLE001 - isolating failures is the point
                last_error = error
                if attempt < self.max_attempts:
                    wait = self.backoff_seconds * (2 ** (attempt - 1))
                    self.events.task_retrying(
                        str(task.key), attempt, self.max_attempts, error, wait
                    )
                    time.sleep(wait)

        duration = time.monotonic() - started
        assert last_error is not None
        self.ledger.record_failure(task.key, duration, self.max_attempts, last_error)
        message = f"{type(last_error).__name__}: {last_error}"
        self.events.task_failed(
            str(task.key),
            f"Gave up after {self.max_attempts} attempt(s): {message}",
            error=message,
        )
        return message


def _summarize(result: dict) -> str:
    """Turn a task's return value into a short phrase for the log.

    Tasks return small dictionaries like `{"turns": 252, "words": 9941}`. This
    renders them as `252 turns, 9941 words` so the log reads as sentences rather
    than as dumped data structures.
    """
    if not result:
        return ""
    return ", ".join(f"{value} {name}" for name, value in result.items())

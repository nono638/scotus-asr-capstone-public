"""What a unit of work is.

The whole resume mechanism rests on one idea: **a task is identified by what it
produces.** A task is a case, a stage, and (where it matters) which model did it.
That triple maps to exactly one output file. So "has this already been done"
never needs a database - it is the same question as "is that file there".

Keeping the identity separate from the work also means the runner does not need
to know what any stage actually does.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class Stage(str, Enum):
    """The steps a case goes through, in order."""

    FETCH = "fetch"              # download audio and transcript
    TRANSCRIPT = "transcript"    # PDF to reference turns
    OCR = "ocr"                  # page images to text, for scanned transcripts
    ASR = "asr"                  # audio to a machine transcription
    SCORE = "score"              # compare the two


@dataclass(frozen=True, order=True)
class TaskKey:
    """Names one piece of work.

    Frozen and ordered so it can go in a set, be used as a dictionary key, and
    sort predictably when a run is listed.

    Attributes:
        docket: The case, e.g. `09-834`.
        stage: Which step.
        engine: Which model, for stages where more than one can run over the same
            case. Empty for stages where the question does not arise.
    """

    docket: str
    stage: Stage
    engine: str = ""

    def __str__(self) -> str:
        """A short readable identifier, used in logs and in the ledger."""
        if self.engine:
            return f"{self.docket}/{self.stage.value}/{self.engine}"
        return f"{self.docket}/{self.stage.value}"


@dataclass
class Task:
    """A `TaskKey` plus the work to do and where the result lands.

    Attributes:
        key: What this task is.
        run: Does the work. Takes no arguments - everything it needs is captured
            when the task is built - and returns a short summary for the log.
        output: The file that exists if and only if this task finished.
        description: One line for a human watching the run.
    """

    key: TaskKey
    run: Callable[[], dict]
    output: Path
    description: str = ""

    def __str__(self) -> str:
        return str(self.key)

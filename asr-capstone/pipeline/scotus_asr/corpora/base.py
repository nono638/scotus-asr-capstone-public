"""What every corpus looks like to the rest of the pipeline.

The engines, the scoring and the runner never cared that the audio came from the
Supreme Court. They need three things: a list of recordings, the audio file for
each, and a reference to score against. A corpus is whatever supplies those.

Getting the data is the part that differs from one dataset to the next - a tar
file from a university repository, a git repository with large files, one web
page per argument - so each corpus has its own small adapter. What the adapter
hands back is the same everywhere:

- `Recording`: one audio file and how long it is.
- `Transcript` (from `transcripts/model.py`): the reference, as speaker turns,
  with times when the corpus has them.

**The index on disk follows Lhotse's field names.** Lhotse is the most widely
used toolkit for preparing speech corpora; its manifests are JSON lines, one
recording per line, with `id`, `duration` and `sampling_rate`. This project does
not depend on it - it would pull in PyTorch from ordinary PyPI, the trap written
up in CLAUDE.md - but writing the same field names costs nothing and means the
index can be read by it later. The reference turns map one to one onto NIST's STM
format (`formats.py`), which is how references for long recordings are usually
exchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from ..transcripts.model import Transcript

#: Called with a short note on what preparing a corpus is doing.
Progress = Callable[[str], None]


@dataclass(frozen=True)
class Recording:
    """One audio file to transcribe and score.

    Attributes:
        id: Unique within the corpus, and safe in a filename. Every result file
            is named after it, and it fills the `docket` column of the results
            tables, which kept that name from the Supreme Court work so the
            analysis tools read every corpus the same way.
        audio_path: The audio file. Anything librosa reads - WAV, FLAC, MP3.
        audio_minutes: Its length, worked out when the index was built.
        corpus: Which corpus it belongs to.
        split: The corpus's own division, such as `dev` or `test`, if it has one.
        sampling_rate: As stored, before the engines resample to 16 kHz.
        extra: Anything else the corpus records about it, kept for analysis.
    """

    id: str
    audio_path: Path
    audio_minutes: float | None
    corpus: str
    split: str = ""
    sampling_rate: int | None = None
    extra: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    @property
    def has_audio(self) -> bool:
        """Always true here; a recording without audio is not listed."""
        return True

    @property
    def docket(self) -> str:
        """The name the Supreme Court code uses for an identifier."""
        return self.id

    @property
    def term(self) -> str:
        """Supreme Court terms do not apply; the split stands in for them."""
        return self.split

    def to_dict(self) -> dict[str, Any]:
        """One line of the index, with Lhotse's names for the shared fields."""
        return {
            "id": self.id,
            "path": str(self.audio_path),
            "duration": round((self.audio_minutes or 0) * 60, 3),
            "sampling_rate": self.sampling_rate,
            "corpus": self.corpus,
            "split": self.split,
            **({"extra": self.extra} if self.extra else {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recording":
        return cls(
            id=data["id"],
            audio_path=Path(data["path"]),
            audio_minutes=(data.get("duration") or 0) / 60 or None,
            corpus=data.get("corpus", ""),
            split=data.get("split", ""),
            sampling_rate=data.get("sampling_rate"),
            extra=data.get("extra", {}),
        )


def write_index(path: Path, recordings: Iterable[Recording]) -> None:
    """Save the recording list as JSON lines, replacing any earlier one whole."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    with open(temporary, "w", encoding="utf-8") as stream:
        for recording in recordings:
            stream.write(json.dumps(recording.to_dict()) + "\n")
    temporary.replace(path)


def read_index(path: Path) -> list[Recording]:
    """Read back what `write_index` saved."""
    with open(path, encoding="utf-8") as stream:
        return [Recording.from_dict(json.loads(line)) for line in stream if line.strip()]


class Corpus:
    """The three things a dataset adapter has to provide.

    Subclasses set `name` and implement all three methods. `root` is the folder
    the corpus lives in - downloads, unpacked files and the index all go under it,
    outside the repository.
    """

    name = ""
    #: True only for the Supreme Court, whose files are fetched one task per
    #: case. Every other corpus is prepared once, as a whole, by `prepare`.
    fetches_per_recording = False

    def __init__(self, root: Path, split: str = ""):
        self.root = Path(root)
        self.split = split

    def prepare(self, progress: Progress = lambda note: None) -> None:
        """Download and unpack whatever is missing, and build the index.

        Must be safe to run again: every step checks whether its result is
        already there, so a second call does nothing and an interrupted one
        carries on.
        """
        raise NotImplementedError

    def recordings(self) -> list[Recording]:
        """Every recording in the chosen split, in a fixed order."""
        raise NotImplementedError

    def reference(self, recording: Recording) -> Transcript:
        """The reference transcript for one recording."""
        raise NotImplementedError

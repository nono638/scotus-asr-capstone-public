"""The Supreme Court oral arguments, as a corpus like any other.

Nothing here is new: the case list is `corpus/manifest.py` and the reference is
the PDF parser in `transcripts/`. This only puts them behind the same three
methods every corpus has, so the stages do not need to know which one they are
running.

Downloading stays as it was, one task per case, because the Court serves each
argument's audio and transcript as separate files and a corpus of a thousand
arguments is best fetched, and resumed, file by file.
"""

from __future__ import annotations

from pathlib import Path

from ..corpus.manifest import Case, load_cases
from ..transcripts.model import Transcript
from .base import Corpus, Progress


class ScotusCorpus(Corpus):
    name = "scotus"
    #: The stages build a download task per case for this corpus rather than
    #: calling `prepare` once.
    fetches_per_recording = True

    def __init__(self, root: Path, split: str = "", manifest: Path | None = None):
        super().__init__(root, split)
        self.manifest = manifest or Path(root) / "manifest.json"

    def prepare(self, progress: Progress = lambda note: None) -> None:
        """Nothing to do up front; see the module note."""

    def recordings(self) -> list[Case]:
        return load_cases(self.manifest, self.root)

    def reference(self, recording: Case) -> Transcript:
        from ..transcripts.parse import parse_transcript  # needs PyMuPDF

        return parse_transcript(recording.transcript_pdf, recording.docket)

"""Earnings-22, Rev's corpus of company earnings calls with accented English.

125 calls, 119 hours, from companies in 27 countries. Rev's own transcribers made
the references, and they are verbatim: "um" and "uh", stutters, cut-off words,
repeats, punctuation and capitals are all kept - the nearest thing among public
corpora to a court reporter's record. Ten calls ("Subset 10") also have a second,
cleaned-up reference of the same audio. Transcripts CC BY-SA 4.0; the audio has no
stated licence, so no clips of it are published. Scouting notes in
`asr-capstone/datasets/earnings22.md`.

**What arrives.** The release is a folder of a GitHub repository, with the MP3s in
Git LFS. Rather than cloning, each file is fetched on its own:

    metadata.csv                                     one row per call: country, region, length
    media/<id>.mp3                                   the call, from GitHub's LFS address
    transcripts/nlp_references/<id>.nlp              the verbatim reference, untimed
    subset10/nonverbatim_transcripts/nlp_references/<id>.nlp   the cleaned-up one

The plain address of an MP3 gives Git LFS's pointer file instead of the audio - a
few lines holding the real file's size. That size is read first, so a download
that stops short is caught rather than transcribed.

**Splits.** Empty for every call; `subset10` for the ten with two references; or a
region from the metadata (`English`, `Asian`, `Spanish/Portuguese`, ...). Each
recording's split is its region, so results break down by region as they do by
term for the Supreme Court. The region is the company's home country, not checked
by ear - the paper says so.
"""

from __future__ import annotations

import csv
from pathlib import Path

import soundfile

from ..references.nlp import nlp_to_transcript, read_nlp
from ..transcripts.model import Transcript
from .base import Corpus, Progress, Recording, read_index, write_index
from .download import fetch

RAW = "https://raw.githubusercontent.com/revdotcom/speech-datasets/main/earnings22"
MEDIA = "https://media.githubusercontent.com/media/revdotcom/speech-datasets/main/earnings22"

#: The ten calls with a cleaned-up reference too (subset10/README.md).
SUBSET10 = ("4453225", "4469088", "4470684", "4483937", "4474506",
            "4485192", "4479944", "4482613", "4481952", "4482383")


def lfs_size(pointer: Path) -> int:
    """The real file's size, from a Git LFS pointer file's `size` line."""
    for line in pointer.read_text(encoding="utf-8").splitlines():
        if line.startswith("size "):
            return int(line.split()[1])
    raise ValueError(f"{pointer} is not a Git LFS pointer file")


class Earnings22Corpus(Corpus):
    name = "earnings22"

    @property
    def index(self) -> Path:
        return self.root / "recordings.jsonl"

    def _metadata(self) -> list[dict[str, str]]:
        with open(self.root / "metadata.csv", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def prepare(self, progress: Progress = lambda note: None) -> None:
        fetch(f"{RAW}/metadata.csv", self.root / "metadata.csv")
        calls = self._metadata()
        for number, row in enumerate(calls, 1):
            call = row["File ID"]
            fetch(f"{RAW}/transcripts/nlp_references/{call}.nlp",
                  self.root / "references" / f"{call}.nlp")
            if call in SUBSET10:
                fetch(f"{RAW}/subset10/nonverbatim_transcripts/nlp_references/{call}.nlp",
                      self.root / "references-nonverbatim" / f"{call}.nlp")
            pointer = fetch(f"{RAW}/media/{call}.mp3", self.root / "pointers" / f"{call}.mp3.txt")
            audio = self.root / "media" / f"{call}.mp3"
            if not audio.exists():
                progress(f"downloading call {number} of {len(calls)} ({call})")
            fetch(f"{MEDIA}/media/{call}.mp3", audio, expected_bytes=lfs_size(pointer))
        if not self.index.exists():
            progress("measuring every recording")
            write_index(self.index, self._build_index())
        progress("ready")

    def _build_index(self) -> list[Recording]:
        """Every call, with its length as decoded and its metadata."""
        recordings = []
        for row in self._metadata():
            call = row["File ID"]
            audio = self.root / "media" / f"{call}.mp3"
            info = soundfile.info(str(audio))
            recordings.append(Recording(
                id=call, audio_path=audio, audio_minutes=info.duration / 60,
                corpus=self.name, split=row["Language Family + Area Based"],
                sampling_rate=info.samplerate,
                extra={"country": row["Country by Ticker"], "ticker": row["Ticker Symbol"],
                       "subset10": call in SUBSET10},
            ))
        return recordings

    def recordings(self) -> list[Recording]:
        if not self.index.exists():
            raise FileNotFoundError(self.index)
        everything = read_index(self.index)
        if not self.split:
            return everything
        if self.split.lower() == "subset10":
            return [r for r in everything if r.id in SUBSET10]
        chosen = [r for r in everything if r.split.lower() == self.split.lower()]
        if not chosen:
            regions = sorted({r.split for r in everything})
            raise SystemExit(f"No Earnings-22 split {self.split!r}. Use subset10 or one of: "
                             f"{', '.join(regions)}")
        return chosen

    def reference(self, recording: Recording) -> Transcript:
        path = self.root / "references" / f"{recording.id}.nlp"
        return nlp_to_transcript(recording.id, read_nlp(path), source=f"earnings22 {path.name}")

    def nonverbatim_reference(self, recording: Recording) -> Transcript:
        """The cleaned-up reference, for the ten Subset 10 calls only."""
        path = self.root / "references-nonverbatim" / f"{recording.id}.nlp"
        return nlp_to_transcript(recording.id, read_nlp(path),
                                 source=f"earnings22 subset10 nonverbatim {path.name}")

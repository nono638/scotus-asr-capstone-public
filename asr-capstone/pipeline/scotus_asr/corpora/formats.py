"""The standard file formats for references and machine transcripts.

Two formats from NIST's scoring toolkit (SCTK, whose scorer is `sclite`) are the
usual way to exchange transcripts of long recordings, and most corpora ship one
or the other:

STM, for references. One line per stretch of speech:

    file channel speaker start end [<labels>] words...

Lines starting `;;` are comments. A line whose words are
`IGNORE_TIME_SEGMENT_IN_SCORING` marks a stretch to leave out of scoring
altogether; sclite drops any hypothesis word whose midpoint falls inside it.

CTM, for machine output. One line per word:

    file channel start duration word [confidence]

Reading STM lets any corpus that ships it be scored with no code of its own
beyond a download. Writing CTM lets this project's output be checked with sclite
itself, and reading it lets another system's output (EdAcc ships one from a
commercial engine) be scored alongside the models run here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ..transcripts.model import Transcript, Turn

IGNORE = "IGNORE_TIME_SEGMENT_IN_SCORING"


@dataclass(frozen=True)
class StmLine:
    """One line of an STM file."""

    file: str
    channel: str
    speaker: str
    start: float
    end: float
    labels: str
    text: str

    @property
    def ignored(self) -> bool:
        return self.text.strip() == IGNORE


def read_stm(path: Path) -> list[StmLine]:
    """Every line of an STM file, in file order.

    Raises:
        ValueError: On a line with fewer than the five required fields, naming
            the line, rather than skipping it and losing a turn of reference.
    """
    lines: list[StmLine] = []
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.startswith(";;"):
            continue
        parts = raw.split(maxsplit=5)
        if len(parts) < 5:
            raise ValueError(f"{path}, line {number}: not an STM line: {raw!r}")
        rest = parts[5] if len(parts) > 5 else ""
        labels = ""
        if rest.startswith("<"):
            close = rest.find(">")
            labels, rest = rest[1:close], rest[close + 1:]
        lines.append(StmLine(
            file=parts[0], channel=parts[1], speaker=parts[2],
            start=float(parts[3]), end=float(parts[4]),
            labels=labels, text=rest.strip(),
        ))
    return lines


def stm_to_transcript(
    recording_id: str,
    lines: Iterable[StmLine],
    clean: Callable[[str], str] = lambda text: text,
    source: str = "",
) -> Transcript:
    """Turn one recording's STM lines into a reference transcript.

    Args:
        recording_id: Becomes the transcript's identifier.
        lines: That recording's lines only.
        clean: The corpus's own tidying of a line's words - removing its noise
            tags, say. Applied here so every corpus scores plain words.
        source: Where the reference came from, recorded in the transcript.

    Returns:
        Turns in time order, with their times, and the ignored stretches.
        Lines left empty by `clean` are dropped.
    """
    transcript = Transcript(docket=recording_id, source_pdf=source)
    for line in sorted(lines, key=lambda l: (l.start, l.end)):
        if line.ignored:
            transcript.ignore.append((line.start, line.end))
            continue
        text = clean(line.text)
        if not text:
            continue
        transcript.turns.append(Turn(
            speaker=line.speaker, text=text, speaker_normalized=line.speaker,
            start=line.start, end=line.end,
        ))
    return transcript


def write_stm(transcript: Transcript, path: Path, channel: str = "1") -> None:
    """Write a transcript with timed turns as STM, for scoring with sclite."""
    rows = [
        (start, end, "excluded", IGNORE) for start, end in transcript.ignore
    ] + [
        (turn.start or 0.0, turn.end or 0.0, turn.speaker_normalized or turn.speaker, turn.text)
        for turn in transcript.turns
    ]
    with open(path, "w", encoding="utf-8") as stream:
        for start, end, speaker, text in sorted(rows):
            stream.write(f"{transcript.docket} {channel} {speaker.replace(' ', '_')} "
                         f"{start:.3f} {end:.3f} {text}\n")


def write_ctm(file_id: str, words: Iterable, path: Path, channel: str = "1") -> None:
    """Write timed words (anything with text, start, end) as CTM."""
    with open(path, "w", encoding="utf-8") as stream:
        for word in words:
            text = word.text.strip()
            if not text:
                continue
            stream.write(f"{file_id} {channel} {word.start:.3f} "
                         f"{max(word.end - word.start, 0.0):.3f} {text}\n")


@dataclass(frozen=True)
class CtmWord:
    """One line of a CTM file, shaped like the engines' own words."""

    text: str
    start: float
    end: float
    probability: float | None = None


def read_ctm(path: Path) -> dict[str, list[CtmWord]]:
    """Words per file, in time order."""
    by_file: dict[str, list[CtmWord]] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith(";;"):
            continue
        parts = raw.split()
        start, duration = float(parts[2]), float(parts[3])
        confidence = float(parts[5]) if len(parts) > 5 and parts[5] != "NA" else None
        by_file.setdefault(parts[0], []).append(
            CtmWord(parts[4], start, start + duration, confidence))
    for words in by_file.values():
        words.sort(key=lambda w: w.start)
    return by_file

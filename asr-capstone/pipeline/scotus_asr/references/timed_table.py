"""A reference as a table: one utterance per row, with its speaker and times.

Many corpora ship their transcript like this - tab- or comma-separated, a header
row, and columns for who spoke, when they started and stopped, and what they
said. CORAAL is one (`Line Spkr StTime Content EnTime`); exports from ELAN and
Praat often look the same. The columns are found by their header names, so the
order in the file does not matter and a corpus only says which names it uses.

Reading is kept apart from cleaning. Each corpus has its own markup - noise tags,
redactions, unclear speech - so it passes a `clean` function that returns the
words to score, an empty string for a row with nothing to score (a pause), or
None for a row that cannot be scored at all. A None row's time becomes an
ignored stretch, so whatever an engine writes there is not counted against it -
the same treatment as EdAcc's IGNORE_TIME_SEGMENT_IN_SCORING lines.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ..transcripts.model import Transcript, Turn


@dataclass(frozen=True)
class TimedRow:
    """One utterance: who, from when to when (seconds), and the words as written."""

    speaker: str
    start: float
    end: float
    text: str


def read_timed_table(
    path: Path,
    *,
    speaker: str = "speaker",
    start: str = "start",
    end: str = "end",
    text: str = "text",
    delimiter: str = "\t",
    encoding: str = "utf-8",
) -> list[TimedRow]:
    """Every row of a timed table, in file order.

    Quote marks are read as plain text (a transcript's quotes are words, not
    field markers), and the header's names are matched after trimming spaces.

    Raises:
        ValueError: If a named column is missing, naming the ones there are, or
            if a row's time is not a number, naming the row - rather than
            skipping it and losing part of the reference.
    """
    path = Path(path)
    with path.open(encoding=encoding, newline="") as f:
        reader = csv.reader(f, delimiter=delimiter, quoting=csv.QUOTE_NONE)
        header = [h.strip() for h in next(reader, [])]
        wanted = {"speaker": speaker, "start": start, "end": end, "text": text}
        missing = [name for name in wanted.values() if name not in header]
        if missing:
            raise ValueError(f"{path}: no column {', '.join(missing)}; the header has {header}")
        at = {key: header.index(name) for key, name in wanted.items()}
        rows = []
        for number, fields in enumerate(reader, 2):
            if not any(field.strip() for field in fields):
                continue
            try:
                rows.append(TimedRow(
                    speaker=fields[at["speaker"]].strip(),
                    start=float(fields[at["start"]]),
                    end=float(fields[at["end"]]),
                    text=fields[at["text"]].strip() if at["text"] < len(fields) else "",
                ))
            except (ValueError, IndexError) as err:
                raise ValueError(f"{path}, row {number}: {fields!r} ({err})") from None
    return rows


def rows_to_transcript(
    recording_id: str,
    rows: Iterable[TimedRow],
    clean: Callable[[str], str | None] = lambda text: text,
    source: str = "",
) -> Transcript:
    """Turn one recording's rows into a reference transcript.

    Args:
        recording_id: Becomes the transcript's identifier.
        rows: That recording's rows.
        clean: The corpus's own tidying of a row: the words to score, "" for
            nothing to score, or None for a row that cannot be scored.
        source: Where the reference came from, recorded in the transcript.

    Returns:
        Turns in time order, with their times, and the ignored stretches.
    """
    transcript = Transcript(docket=recording_id, source_pdf=source)
    for row in sorted(rows, key=lambda r: (r.start, r.end)):
        words = clean(row.text)
        if words is None:
            transcript.ignore.append((row.start, row.end))
            continue
        if not words:
            continue
        transcript.turns.append(Turn(
            speaker=row.speaker, text=words, speaker_normalized=row.speaker,
            start=row.start, end=row.end,
        ))
    return transcript

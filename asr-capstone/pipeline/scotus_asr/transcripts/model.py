"""The shapes the transcript takes on its way from PDF to reference text.

Every one of these keeps track of where its text came from - which PDF page, which
numbered line. That provenance is not decoration. When the scoring says a model
dropped forty seconds, the next question is always "show me", and being able to
point at page 84, lines 12 to 19 is the difference between a number and evidence.

The original `parse_transcript.py` threw this away, keeping only speaker and text.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Line:
    """One numbered line of a transcript page.

    Attributes:
        page: Which page of the PDF, counting from 1.
        number: The line number printed in the left margin, normally 1 to 25.
        text: What the line says, with the margin number removed.
        x0: Left edge of the text, in PDF points. Used to tell an indented
            speaker label from a continuation line.
    """

    page: int
    number: int
    text: str
    x0: float = 0.0


@dataclass(frozen=True)
class Page:
    """One page of the PDF and the numbered lines found on it."""

    number: int
    lines: list[Line] = field(default_factory=list)


@dataclass(frozen=True)
class Event:
    """Something the reporter wrote down that nobody said.

    `(Laughter.)` and its kind. These matter more than they look: the audio at
    such a moment holds a sound, so a speech detector calls it speech, and a
    model that correctly writes nothing there is scored as having dropped
    something. Without knowing where they are, the models are charged for
    behaving properly.

    Attributes:
        text: The notation as printed, parentheses and all.
        page: PDF page it appears on.
        line: Margin line number.
        after_word: How many words of the turn came before it, so the notation
            can be placed in the flat word list that scoring uses. A turn
            interrupted by laughter and then resumed puts the event in the
            middle, and a line number alone cannot say where.
        kind: `laughter`, `pause`, `recess`, `applause`, `end`, or `other`. The
            first four were the whole of the old detection rule; they are a label
            now rather than a gate, so an unfamiliar notation is recorded as
            `other` instead of being silently treated as speech.
    """

    text: str
    page: int = 0
    line: int = 0
    after_word: int = 0
    kind: str = "other"

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        return asdict(self)

    @classmethod
    def from_any(cls, data: Any) -> "Event":
        """Rebuild an event from either shape this file has ever held.

        The first version stored `[line_number, text]` and nothing else. Reference
        JSON written before the change is still on disk and still readable, so
        the two-element form is accepted and the missing fields left at zero -
        which is honest: that file genuinely does not know the page or the word
        offset.
        """
        if isinstance(data, dict):
            return cls(
                text=data.get("text", ""),
                page=int(data.get("page", 0)),
                line=int(data.get("line", 0)),
                after_word=int(data.get("after_word", 0)),
                kind=data.get("kind", "other"),
            )
        # The old two-element form, as a list or a tuple.
        line, text = (list(data) + ["", ""])[:2]
        return cls(text=str(text), line=int(line or 0), kind=classify_event(str(text)))


#: The notations the original rule looked for. Kept as labels rather than as the
#: test for whether something is a notation at all.
_EVENT_KINDS = ("laughter", "pause", "recess", "applause")


def classify_event(text: str) -> str:
    """Name what kind of notation this is, for grouping rather than for filtering."""
    lowered = text.lower().lstrip("({ ")
    for kind in _EVENT_KINDS:
        if lowered.startswith(kind):
            return kind
    # "(Whereupon, a brief recess was taken.)" - a break, not the end.
    if "whereupon" in lowered and "recess" in lowered:
        return "recess"
    if "whereupon" in lowered or "submitted" in lowered:
        return "end"
    return "other"


@dataclass
class Turn:
    """One person speaking, until somebody else does.

    Attributes:
        speaker: The label as printed, e.g. `JUSTICE KAGAN`, or `QUESTION` in the
            older transcripts that do not say which justice asked.
        text: Everything they said, with the line breaks joined up.
        speaker_normalized: The label after tidying - the form used for anything
            that counts speakers, so a reporter's typo does not become a
            thirteenth justice.
        start_page: PDF page the turn starts on.
        start_line: Margin line number it starts at.
        end_page: PDF page it ends on.
        end_line: Margin line number it ends at.
        events: Stage directions inside the turn, e.g. `(Laughter.)`. Kept rather
            than dropped: whether a system reproduces or silently tidies these is
            one of the things being measured, so they cannot be thrown away here.
            They also mark places where there is a sound but no speech, which is
            what stops a model being charged for correctly writing nothing.
        start: Seconds into the recording where the turn begins, when the
            reference says. A Supreme Court transcript does not, so these stay
            None there; most speech corpora time every turn (see `corpora/`).
        end: Seconds into the recording where the turn ends.
    """

    speaker: str
    text: str
    speaker_normalized: str = ""
    start_page: int = 0
    start_line: int = 0
    end_page: int = 0
    end_line: int = 0
    events: list[Event] = field(default_factory=list)
    start: float | None = None
    end: float | None = None

    @property
    def word_count(self) -> int:
        """How many words were spoken in this turn."""
        return len(self.text.split())

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        data = asdict(self)
        data["events"] = [event.to_dict() for event in self.events]
        data["word_count"] = self.word_count
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Turn":
        """Rebuild a turn from what `to_dict` wrote.

        `word_count` is worked out rather than stored, so it is ignored here even
        though it appears in the file. Keeping it in the JSON is for whoever reads
        the file; recomputing it on the way back in means the two can never drift
        apart.
        """
        return cls(
            speaker=data["speaker"],
            text=data["text"],
            speaker_normalized=data.get("speaker_normalized", ""),
            start_page=data.get("start_page", 0),
            start_line=data.get("start_line", 0),
            end_page=data.get("end_page", 0),
            end_line=data.get("end_line", 0),
            # Accepts both the current shape and the `[line, text]` pairs written
            # before events carried a page and a word offset, so reference JSON
            # already on disk still loads.
            events=[Event.from_any(event) for event in data.get("events", [])],
            start=data.get("start"),
            end=data.get("end"),
        )


@dataclass
class Transcript:
    """A whole argument: every turn, plus what was noticed while reading it.

    Attributes:
        docket: The case.
        turns: Who said what, in order.
        source_pdf: Where it came from.
        page_count: Pages in the PDF.
        index_started_on_page: The page where the argument ends and the
            alphabetical keyword index begins. Everything from there on is
            discarded - the index lines also start with digits, and counting them
            as speech inflates the word count by roughly a sixth.
        warnings: Things worth knowing that did not stop the parse, such as a
            page with no line numbers or a speaker label seen only once.
        ignore: Stretches of the recording, as (start, end) seconds, that are
            left out of scoring altogether. The reference has no words for them,
            and any word the model wrote there is dropped before comparing, by
            the word's midpoint - the same rule as NIST's sclite and its
            IGNORE_TIME_SEGMENT_IN_SCORING. EdAcc uses it for the passages
            speakers read aloud. Empty for the Supreme Court.
    """

    docket: str
    turns: list[Turn] = field(default_factory=list)
    source_pdf: str = ""
    page_count: int = 0
    index_started_on_page: int | None = None
    warnings: list[str] = field(default_factory=list)
    ignore: list[tuple[float, float]] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        """Total spoken words, which is what the speaking-rate check divides."""
        return sum(turn.word_count for turn in self.turns)

    @property
    def speakers(self) -> list[str]:
        """Distinct tidied speaker labels, in the order they first speak."""
        seen: list[str] = []
        for turn in self.turns:
            name = turn.speaker_normalized or turn.speaker
            if name not in seen:
                seen.append(name)
        return seen

    def full_text(self, include_speakers: bool = False) -> str:
        """Everything spoken, as one string.

        Args:
            include_speakers: Put the speaker label in front of each turn. Off for
                scoring, because a model transcribing the audio never hears
                "JUSTICE KAGAN" said aloud, so counting it as a missed word would
                punish the model for something that was never spoken.
        """
        if include_speakers:
            return "\n".join(f"{t.speaker}: {t.text}" for t in self.turns)
        return " ".join(turn.text for turn in self.turns)

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        return {
            "docket": self.docket,
            "source_pdf": self.source_pdf,
            "page_count": self.page_count,
            "index_started_on_page": self.index_started_on_page,
            "turn_count": len(self.turns),
            "word_count": self.word_count,
            "speakers": self.speakers,
            "warnings": self.warnings,
            "ignore": [list(span) for span in self.ignore],
            "turns": [turn.to_dict() for turn in self.turns],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transcript":
        """Rebuild a transcript from a file written by `to_dict`.

        This is what lets scoring run against the saved reference rather than
        re-reading the PDF. The file is the record; re-parsing could quietly
        produce something different if the parser changed between runs, and then
        a score would not correspond to the reference it claims to.
        """
        return cls(
            docket=data.get("docket", ""),
            turns=[Turn.from_dict(turn) for turn in data.get("turns", [])],
            source_pdf=data.get("source_pdf", ""),
            page_count=data.get("page_count", 0),
            index_started_on_page=data.get("index_started_on_page"),
            warnings=list(data.get("warnings", [])),
            ignore=[(float(a), float(b)) for a, b in data.get("ignore", [])],
        )

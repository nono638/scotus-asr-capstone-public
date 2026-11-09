"""Finding the places where the machine simply stopped.

The argument for this module, in one sentence: word error rate scores a system
that silently drops fourteen seconds exactly the same as one that makes the same
number of scattered small mistakes, and in a legal record those two things are not
remotely comparable. A scattered error is visible to anyone reading the transcript
and gets corrected. A missing passage reads as perfectly fluent text and nobody
ever knows it was there.

So the unit reported here is not a count of wrong words. It is **a span of the
record that is gone, and how many seconds of audio it covers** - which is the
thing a court reporter would ask about first.

How the timing is worked out
----------------------------
No separate forced-alignment model is used, because the machine's own output
already answers the question. Every word the model produced carries a timestamp.
Where the model skipped a passage, it jumped from the word before the gap to the
word after it, so the distance between those two timestamps *is* the length of
what it missed. That measurement comes free with the transcription and involves no
second model that could introduce errors of its own.

The word count is also converted to seconds at a typical speaking rate, as a
cross-check. The two numbers should roughly agree; where they disagree badly,
something else is going on and the case is worth listening to.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Sequence

from ..asr.base import Word
from .align import Alignment

#: Words per minute for appellate argument, used only to sanity-check a span's
#: measured length against its word count.
_TYPICAL_WORDS_PER_MINUTE = 175.0


@dataclass(frozen=True)
class OmittedSpan:
    """A run of the official record that the machine never produced.

    Attributes:
        ref_start_token: First missing reference token.
        ref_end_token: One past the last missing token.
        word_count: How many reference tokens are missing.
        text: What was said and not transcribed. Truncated for the results table
            but kept whole in the JSON.
        audio_start: Where in the recording the gap begins, in seconds, taken
            from the end of the last word the machine did produce.
        audio_end: Where it ends, from the start of the next word it produced.
        gap_seconds: `audio_end` minus `audio_start`. The measured length of the
            silence in the machine's own timeline.
        expected_seconds: How long those words should have taken at a normal
            speaking rate. A cross-check on `gap_seconds`.
        at_start: The gap runs from the very beginning of the recording, so there
            is no preceding word to measure from.
        at_end: The gap runs to the end, so there is no following word.
    """

    ref_start_token: int
    ref_end_token: int
    word_count: int
    text: str
    audio_start: float | None = None
    audio_end: float | None = None
    gap_seconds: float | None = None
    expected_seconds: float = 0.0
    at_start: bool = False
    at_end: bool = False

    @property
    def timing_disagrees(self) -> bool:
        """Do the measured and expected lengths disagree badly?

        True when they differ by more than a factor of two. That usually means
        the alignment smeared a large omission across the transcript rather than
        finding it in one place, and the case wants listening to rather than
        trusting.
        """
        if self.gap_seconds is None or self.expected_seconds <= 0:
            return False
        ratio = self.gap_seconds / self.expected_seconds
        return ratio < 0.5 or ratio > 2.0

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        data = asdict(self)
        data["timing_disagrees"] = self.timing_disagrees
        return data


def _merge_runs(
    alignment: Alignment, merge_gap: int
) -> list[tuple[int, int, int]]:
    """Join deletion runs that are separated by only a word or two.

    Why this is needed: a dropped passage often contains one or two very common
    words the model happened to emit anyway - "the", "Court", "Your Honor". Left
    alone, that single accidental match splits one sixty-second omission into two
    thirty-second ones, both of which may then fall under the reporting threshold.
    The worst failures would quietly vanish from the results.

    Anything the model *did* produce counts as coverage, whether it got the word
    right or wrong, because a substitution means it was still listening.

    Args:
        alignment: The comparison to walk.
        merge_gap: How many covered reference tokens may sit inside one span.

    Returns:
        `(first reference token, one past the last, machine token position)` for
        each merged run.
    """
    runs: list[tuple[int, int, int]] = []
    open_start: int | None = None
    open_end = 0
    open_hyp = 0
    covered_since_delete = 0

    for chunk in alignment.chunks:
        if chunk.kind == "delete":
            if open_start is None:
                open_start, open_hyp = chunk.ref_start, chunk.hyp_start
            open_end = chunk.ref_end
            covered_since_delete = 0
            continue

        if chunk.kind == "insert":
            # Words invented out of nothing consume no reference, so they neither
            # extend a gap nor close one.
            continue

        # equal or substitute: the model produced something here.
        if open_start is not None:
            covered_since_delete += chunk.ref_length
            if covered_since_delete > merge_gap:
                runs.append((open_start, open_end, open_hyp))
                open_start = None
                covered_since_delete = 0

    if open_start is not None:
        runs.append((open_start, open_end, open_hyp))

    return runs


def _word_time(
    tokens_source: Sequence[int], timings: Sequence[Word], token_index: int
) -> Word | None:
    """The timed word a machine token came from, if there is one."""
    if token_index < 0 or token_index >= len(tokens_source):
        return None
    source = tokens_source[token_index]
    if 0 <= source < len(timings):
        return timings[source]
    return None


def find_omissions(
    alignment: Alignment,
    hypothesis_timings: Sequence[Word] | None = None,
    min_words: int = 25,
    merge_gap: int = 2,
) -> list[OmittedSpan]:
    """Find the passages the machine did not transcribe.

    Args:
        alignment: The comparison of record against machine output.
        hypothesis_timings: The machine's words with their timestamps, in the
            same order as the words that went into the alignment. Without these
            the spans are still found, just without times attached.
        min_words: Shortest run worth reporting. The default of 25 words is
            roughly ten seconds of argument - long enough that a reader would
            find the record stopped making sense.
        merge_gap: How many words the model got anyway may sit inside one span
            before it counts as two.

    Returns:
        The spans, longest first, so the worst failure is the first thing read.
    """
    if alignment.reference is None:
        return []

    reference_tokens = alignment.reference.tokens
    spans: list[OmittedSpan] = []

    hyp_source = alignment.hypothesis.source_index if alignment.hypothesis else []
    timings = hypothesis_timings or []

    for ref_start, ref_end, hyp_position in _merge_runs(alignment, merge_gap):
        word_count = ref_end - ref_start
        if word_count < min_words:
            continue

        before = _word_time(hyp_source, timings, hyp_position - 1)
        after = _word_time(hyp_source, timings, hyp_position)

        audio_start = before.end if before else None
        audio_end = after.start if after else None
        gap = None
        if audio_start is not None and audio_end is not None:
            # Negative gaps can happen where word timestamps overlap slightly.
            gap = max(0.0, audio_end - audio_start)

        spans.append(
            OmittedSpan(
                ref_start_token=ref_start,
                ref_end_token=ref_end,
                word_count=word_count,
                text=" ".join(reference_tokens[ref_start:ref_end]),
                audio_start=audio_start,
                audio_end=audio_end,
                gap_seconds=round(gap, 3) if gap is not None else None,
                expected_seconds=round(word_count / _TYPICAL_WORDS_PER_MINUTE * 60.0, 1),
                at_start=before is None,
                at_end=after is None,
            )
        )

    spans.sort(key=lambda span: span.word_count, reverse=True)
    return spans


def summarize_omissions(spans: Sequence[OmittedSpan]) -> dict[str, Any]:
    """Roll a case's omitted spans up into a few headline numbers.

    `seconds_lost` is the one to lead with. It is the measured total where
    timings exist, which is the figure that means something outside this project:
    how much of the argument went unrecorded.
    """
    if not spans:
        return {
            "omitted_spans": 0,
            "omitted_words": 0,
            "seconds_lost": 0.0,
            "longest_span_words": 0,
            "longest_span_seconds": 0.0,
            "spans_with_odd_timing": 0,
        }

    measured = [span.gap_seconds for span in spans if span.gap_seconds is not None]
    longest = max(spans, key=lambda span: span.word_count)

    return {
        "omitted_spans": len(spans),
        "omitted_words": sum(span.word_count for span in spans),
        "seconds_lost": round(sum(measured), 1),
        "longest_span_words": longest.word_count,
        "longest_span_seconds": longest.gap_seconds or 0.0,
        "spans_with_odd_timing": sum(1 for span in spans if span.timing_disagrees),
    }

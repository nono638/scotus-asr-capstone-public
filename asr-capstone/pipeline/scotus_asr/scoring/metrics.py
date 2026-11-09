"""Scoring one case against one model, and shaping the result into table rows.

Three tables come out of a run, kept apart because they answer different
questions and have different numbers of rows:

`scores.csv`
    One row per case, model and way of comparing. This is where the headline word
    error rates live, and where the gap between the benchmark-style number and the
    verbatim number becomes visible.

`cases.csv`
    One row per case and model. Everything that is true of the whole recording -
    how long it was, how fast it was transcribed, how many seconds went missing,
    whether the speaking-rate check passed.

`omissions.csv`
    One row per missing passage. Usually the most interesting file in the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..asr.base import AsrResult
from ..config import ScoringSettings
from ..transcripts.model import Transcript
from .align import Alignment, align_words
from .coverage import Silence, find_silences, summarize_coverage
from .normalize import NORMALIZERS
from .rates import check_speaking_rate
from .omissions import OmittedSpan, find_omissions, summarize_omissions

#: Which comparison the omitted-span search runs on.
#:
#: Not `verbatim`, because punctuation would become tokens and a missing comma
#: would pad the length of a gap. Not `standard`, because it deletes filler words,
#: and a model that drops ten seconds of hesitation has still dropped ten seconds.
#: Lower-cased with punctuation removed is the honest middle: real spoken words,
#: compared without being distracted by typography.
OMISSION_BASIS = "lowercase_nopunct"


@dataclass
class ScoreRow:
    """One way of comparing one case against one model."""

    docket: str
    engine: str
    model: str
    normalizer: str
    wer: float
    hits: int
    substitutions: int
    deletions: int
    insertions: int
    reference_tokens: int
    hypothesis_tokens: int
    deletion_rate: float

    def to_row(self) -> dict[str, Any]:
        """As a CSV row."""
        return {
            "docket": self.docket,
            "engine": self.engine,
            "model": self.model,
            "normalizer": self.normalizer,
            "wer": self.wer,
            "wer_percent": round(self.wer * 100, 3),
            "hits": self.hits,
            "substitutions": self.substitutions,
            "deletions": self.deletions,
            "insertions": self.insertions,
            "reference_tokens": self.reference_tokens,
            "hypothesis_tokens": self.hypothesis_tokens,
            "deletion_rate": self.deletion_rate,
        }


@dataclass
class CaseScore:
    """Everything worked out about one case and one model.

    Attributes:
        rows: One `ScoreRow` per way of comparing.
        omissions: The passages the model did not transcribe.
        alignments: The full alignments, kept so the JSON record can be inspected
            later without rerunning anything.
        warnings: Anything noticed that did not stop the scoring.
    """

    docket: str
    engine: str
    model: str
    rows: list[ScoreRow] = field(default_factory=list)
    omissions: list[OmittedSpan] = field(default_factory=list)
    #: Stretches of audio with no word in the transcription. Counted in seconds
    #: rather than reference words, so two engines chunked differently can be
    #: compared without either one's chunking flattering it.
    silences: list[Silence] = field(default_factory=list)
    alignments: dict[str, Alignment] = field(default_factory=dict)
    audio_minutes: float = 0.0
    reference_words: int = 0
    hypothesis_words: int = 0
    words_per_minute: float = 0.0
    speaking_rate_ok: bool = True
    runtime_seconds: float = 0.0
    speed_x_realtime: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def case_row(self) -> dict[str, Any]:
        """The one-per-case-and-model row for `cases.csv`."""
        row: dict[str, Any] = {
            "docket": self.docket,
            "engine": self.engine,
            "model": self.model,
            "audio_minutes": round(self.audio_minutes, 2),
            "reference_words": self.reference_words,
            "hypothesis_words": self.hypothesis_words,
            "words_per_minute": round(self.words_per_minute, 1),
            "speaking_rate_ok": self.speaking_rate_ok,
            "runtime_seconds": round(self.runtime_seconds, 1),
            "speed_x_realtime": round(self.speed_x_realtime, 2),
            "omission_basis": OMISSION_BASIS,
        }
        row.update(summarize_omissions(self.omissions))
        row.update(summarize_coverage(self.silences, self.audio_minutes * 60))
        # The headline error rate, repeated here so the per-case table stands
        # alone without needing a join against scores.csv.
        for score in self.rows:
            row[f"wer_{score.normalizer}"] = round(score.wer * 100, 3)
        row["warnings"] = " | ".join(self.warnings)
        return row

    def omission_rows(self) -> list[dict[str, Any]]:
        """One row per missing passage, for `omissions.csv`."""
        rows = []
        for rank, span in enumerate(self.omissions, start=1):
            rows.append(
                {
                    "docket": self.docket,
                    "engine": self.engine,
                    "rank": rank,
                    "word_count": span.word_count,
                    "gap_seconds": span.gap_seconds,
                    "expected_seconds": span.expected_seconds,
                    "audio_start": span.audio_start,
                    "audio_end": span.audio_end,
                    "audio_start_clock": _clock(span.audio_start),
                    "timing_disagrees": span.timing_disagrees,
                    "at_start": span.at_start,
                    "at_end": span.at_end,
                    "ref_start_token": span.ref_start_token,
                    "ref_end_token": span.ref_end_token,
                    # Enough to recognise the passage; the whole thing is in the JSON.
                    "text": span.text[:300],
                }
            )
        return rows

    def silence_rows(self, min_seconds: float = 10.0) -> list[dict[str, Any]]:
        """One row per notable silence, for `silences.csv`.

        Only the long ones. Half-second gaps are ordinary speech rhythm and
        there are tens of thousands of them; the point of the file is to be able
        to open the audio at a moment and hear what is there.
        """
        rows = []
        for rank, silence in enumerate(
            sorted(
                (s for s in self.silences if s.seconds >= min_seconds),
                key=lambda s: -s.seconds,
            ),
            start=1,
        ):
            rows.append(
                {
                    "docket": self.docket,
                    "engine": self.engine,
                    "rank": rank,
                    "seconds": round(silence.seconds, 1),
                    "audio_start": round(silence.start, 2),
                    "audio_end": round(silence.end, 2),
                    "audio_start_clock": _clock(silence.start),
                    "at_start": silence.at_start,
                    "at_end": silence.at_end,
                }
            )
        return rows

    def to_dict(self) -> dict[str, Any]:
        """The full record, for the per-case JSON file."""
        return {
            "docket": self.docket,
            "engine": self.engine,
            "model": self.model,
            "summary": self.case_row(),
            "scores": [score.to_row() for score in self.rows],
            "alignment_summaries": {
                name: alignment.summary() for name, alignment in self.alignments.items()
            },
            "omissions": [span.to_dict() for span in self.omissions],
            "silences": self.silence_rows(),
            "warnings": self.warnings,
        }


def score_case(
    transcript: Transcript,
    result: AsrResult,
    settings: ScoringSettings,
    audio_minutes: float | None = None,
) -> CaseScore:
    """Compare one machine transcription against the official record.

    Args:
        transcript: The reference, already parsed into turns.
        result: What the model produced.
        settings: Thresholds for the omitted-span search and the rate check.
        audio_minutes: Length of the recording. Taken from the model's own
            measurement when not supplied.

    Returns:
        Every number worked out about this case and model.
    """
    # Speaker labels are dropped on purpose. Nobody says "JUSTICE KAGAN" aloud,
    # so scoring the model for not producing it would penalise it for being right.
    reference_words = transcript.full_text(include_speakers=False).split()
    # Words the model wrote inside a stretch the reference leaves out of scoring
    # are dropped here, so they count neither for nor against it.
    timed_words = drop_ignored(result.words, transcript.ignore)
    hypothesis_words = written_words([word.text for word in timed_words])

    # Fall back to splitting the text when the engine gave no word timings. The
    # scores stay valid; only the times on omitted spans are lost.
    if not hypothesis_words:
        hypothesis_words = result.text.split()

    minutes = audio_minutes if audio_minutes is not None else result.audio_seconds / 60.0
    rate, rate_ok = check_speaking_rate(
        len(reference_words),
        minutes,
        settings.words_per_minute_min,
        settings.words_per_minute_max,
    )

    score = CaseScore(
        docket=transcript.docket,
        engine=result.engine,
        model=result.model,
        audio_minutes=minutes,
        reference_words=len(reference_words),
        hypothesis_words=len(hypothesis_words),
        words_per_minute=rate,
        speaking_rate_ok=rate_ok,
        runtime_seconds=result.runtime_seconds,
        speed_x_realtime=result.speed,
    )

    if not rate_ok:
        score.warnings.append(
            f"Speaking rate is {rate:.0f} words per minute, outside the expected "
            f"{settings.words_per_minute_min:.0f} to {settings.words_per_minute_max:.0f}. "
            f"Check that the audio and the transcript are the same argument."
        )

    for name in NORMALIZERS:
        # The benchmark rule stays exactly as leaderboards compute it, so it can
        # be compared with them. The other two get the harmonise fixes, so they
        # do not count differences nobody could hear (October 2026,
        # flagged-spots-review.md).
        alignment = align_words(reference_words, hypothesis_words, normalizer=name,
                                harmonise=(name != "standard"))
        score.alignments[name] = alignment
        summary = alignment.summary()
        score.rows.append(
            ScoreRow(
                docket=transcript.docket,
                engine=result.engine,
                model=result.model,
                normalizer=name,
                wer=alignment.wer,
                hits=alignment.hits,
                substitutions=alignment.substitutions,
                deletions=alignment.deletions,
                insertions=alignment.insertions,
                reference_tokens=int(summary["reference_tokens"]),
                hypothesis_tokens=int(summary["hypothesis_tokens"]),
                deletion_rate=float(summary["deletion_rate"]),
            )
        )

    score.omissions = find_omissions(
        score.alignments[OMISSION_BASIS],
        hypothesis_timings=timed_words,
        min_words=settings.omission_min_words,
        merge_gap=settings.omission_merge_gap,
    )

    # Measured against the recording rather than the transcript, so it says the
    # same thing about any engine however that engine was chunked.
    score.silences = find_silences(result.words, minutes * 60)

    return score


def written_words(pieces: list[str]) -> list[str]:
    """The words an engine wrote, from the pieces it timed.

    Whisper times pieces, not words: "dope-themed" arrives as " dope" and "-themed",
    "2.5%" as " 2", ".5" and "%". A new word starts with a space, and a split-off piece
    starts with punctuation and no space. Scored as they are, those pieces count as
    separate words, which costs Whisper errors on the verbatim rule (14.53% against
    14.01% on OT2017; bug-audit-2026-11-05.md), so they are joined back on.

    Only an engine whose words start with spaces is touched. A word at the seam between
    two audio chunks has no space either, but it starts with a letter or digit, and stays
    its own word. Engines that give bare words come back unchanged.
    """
    if sum(1 for piece in pieces if piece[:1].isspace()) * 2 <= len(pieces):
        return pieces
    words: list[str] = []
    for piece in pieces:
        if words and piece and not piece[0].isspace() and not piece[0].isalnum():
            words[-1] += piece
        else:
            words.append(piece.strip())
    return words


def leaderboard_error_rate(reference_words: list[str], hypothesis_words: list[str]) -> float:
    """Word error rate in percent, computed the way a leaderboard computes it.

    Its normaliser reads the whole text at once, so "twenty five dollars" becomes
    "25 dollars". Our other figures normalise word by word to keep each token's place
    in the audio, which gives "20 5 dollars" and so counts errors a leaderboard would
    not. Use this only to compare with published leaderboard numbers.
    """
    import jiwer

    from .normalize import NORMALIZERS

    normal = NORMALIZERS["standard"]
    return 100 * jiwer.wer(normal(" ".join(reference_words)), normal(" ".join(hypothesis_words)))


def drop_ignored(words: list, ignore: list[tuple[float, float]]) -> list:
    """The words whose midpoint falls outside every ignored stretch.

    The midpoint, because that is how NIST's sclite decides which reference
    segment a hypothesis word belongs to; a word straddling the edge goes to
    whichever side holds most of it.
    """
    if not ignore:
        return list(words)
    return [
        word for word in words
        if not any(start <= (word.start + word.end) / 2 < end for start, end in ignore)
    ]


def _clock(seconds: float | None) -> str:
    """Seconds as `h:mm:ss`, so a span can be found in an audio player."""
    if seconds is None:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"

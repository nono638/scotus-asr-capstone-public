"""How much of the recording the model produced no words for.

The omitted-span measure counts words missing from the *transcript*. This counts
seconds missing from the *audio*, and the difference matters more than it
sounds.

Every model breaks a long recording into pieces. Whisper can only see thirty
seconds at a time and stitches about a hundred pieces per hour by itself;
Parakeet takes ten-minute pieces and this project stitches them. A measure
counted in reference words is therefore partly a measure of how a model was
chunked and by whom. Counted in seconds of audio with nothing said about them,
it is not: the recording is the same length whoever transcribed it, so two
engines can be compared without either one's chunking flattering it.

It does not distinguish silence from dropped speech, and it is not meant to. A
pause while counsel finds a page and ten seconds of argument nobody wrote down
look identical here. What it gives is a number that can be compared across
engines and then listened to - every silence carries the moment it starts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

#: Shorter than this is ordinary speech rhythm, not a hole worth reporting.
#:
#: Was 0.5s, which was too low and made the headline number mostly noise. On the
#: first cases checked, 239 of 362 "silences" were between half a second and one
#: second - the gaps between words in ordinary continuous speech, where nothing
#: is missing at all. They accounted for a third of the total silent time and
#: nobody dropped anything.
#:
#: Two seconds is the same threshold Silero uses by default to decide a speech
#: region has ended, so the measure and the detector that checks it now agree
#: about what counts as quiet.
MIN_SILENCE_SECONDS = 2.0

#: Long enough that a reader would notice the record makes no sense, on the same
#: reasoning as the 25-word omitted span - about ten seconds of argument.
NOTABLE_SILENCE_SECONDS = 10.0


@dataclass(frozen=True)
class Silence:
    """A stretch of the recording with no word in the transcription.

    Attributes:
        start: Seconds from the beginning of the recording.
        end: Seconds from the beginning.
        at_start: This is the run before the first word.
        at_end: This is the run after the last word.
    """

    start: float
    end: float
    at_start: bool = False
    at_end: bool = False

    @property
    def seconds(self) -> float:
        """How long the stretch is."""
        return max(self.end - self.start, 0.0)


def find_silences(
    words: Sequence[Any],
    audio_seconds: float,
    min_seconds: float = MIN_SILENCE_SECONDS,
) -> list[Silence]:
    """Find the stretches of audio the model said nothing about.

    The runs before the first word and after the last one count. A model that
    starts ninety seconds late has lost ninety seconds, and a measure that only
    looked between words would not see it.

    Args:
        words: What the model produced, each with `start` and `end` in seconds.
            Order does not matter; they are sorted here.
        audio_seconds: Length of the whole recording.
        min_seconds: Ignore gaps shorter than this.

    Returns:
        The stretches, in order.
    """
    timed = sorted(
        (w for w in words if getattr(w, "start", None) is not None),
        key=lambda w: w.start,
    )
    if not timed:
        # Nothing was transcribed at all, so the whole recording is a hole.
        return (
            [Silence(0.0, audio_seconds, at_start=True, at_end=True)]
            if audio_seconds > min_seconds
            else []
        )

    found: list[Silence] = []

    if timed[0].start > min_seconds:
        found.append(Silence(0.0, timed[0].start, at_start=True))

    # Words can overlap slightly where timestamps disagree, so the running end is
    # the furthest point reached rather than the previous word's end.
    reached = timed[0].end
    for word in timed[1:]:
        if word.start - reached > min_seconds:
            found.append(Silence(reached, word.start))
        reached = max(reached, word.end)

    if audio_seconds - reached > min_seconds:
        found.append(Silence(reached, audio_seconds, at_end=True))

    return found


def summarize_coverage(
    silences: Sequence[Silence],
    audio_seconds: float,
    notable_seconds: float = NOTABLE_SILENCE_SECONDS,
) -> dict[str, Any]:
    """The per-case numbers, for `cases.csv`.

    Args:
        silences: What `find_silences` found.
        audio_seconds: Length of the whole recording.
        notable_seconds: How long a silence has to be to be counted separately.

    Returns:
        Columns for the case row.
    """
    total = sum(s.seconds for s in silences)
    notable = [s for s in silences if s.seconds >= notable_seconds]
    return {
        "silent_seconds": round(total, 1),
        "silent_share_percent": round(100 * total / audio_seconds, 2)
        if audio_seconds > 0
        else 0.0,
        "silences_over_10s": len(notable),
        "longest_silence_seconds": round(
            max((s.seconds for s in silences), default=0.0), 1
        ),
        "silence_at_start_seconds": round(
            next((s.seconds for s in silences if s.at_start), 0.0), 1
        ),
        "silence_at_end_seconds": round(
            next((s.seconds for s in silences if s.at_end), 0.0), 1
        ),
    }

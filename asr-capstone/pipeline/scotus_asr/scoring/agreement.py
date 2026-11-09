"""Asking several models about the same second of audio.

When a model writes nothing for a stretch of recording and a detector hears
speech there, the cause could be any of four things: a reporter's parenthetical,
a fault in how the audio was cut into pieces, speech too faint or too far off the
microphone, or the model simply failing. They need different remedies, and a
single model cannot tell them apart.

Several models can. If one is silent where two others wrote words, the audio was
evidently transcribable and the fault is that model's - no listening required to
know whose. If every model is silent, the audio is the suspect, and that is worth
a human ear.

That is the whole idea, and it is worth what it costs: across 58 arguments it
turns roughly 1,700 suspect stretches into about two dozen that need ears.

It narrows rather than proves. Three models agreeing is evidence, not a verdict -
they share training conventions and may share a blind spot, heavy crosstalk being
the obvious candidate. What this gives is a much smaller pile to listen to and a
reason for each thing in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence

#: Where a silence sits once every engine has been asked about it.
ALL_SILENT = "all-silent"
SOME_SILENT = "some-silent"
THIS_ENGINE_ONLY = "this-engine-only"

#: How much speech a shared silence needs before it is worth anybody's time.
#:
#: Any threshold above zero, and this one is above zero for a measured reason.
#: Set at "more than nothing", 202 of Whisper's 208 shared silences qualified -
#: which would have sent someone to listen to essentially every pause in the
#: corpus. The median such stretch holds 0.36 seconds of detected speech and the
#: largest holds 2.68: the detector catching a breath or the edge of a word at
#: the boundary, not something anybody said.
#:
#: One second is about two words at the pace of appellate argument. It takes
#: Whisper's list from 202 to 10, which is a set somebody can actually work
#: through.
MIN_SPEECH_SECONDS = 1.0


class Stretch(Protocol):
    """Anything with a start and an end in seconds."""

    start: float
    end: float


@dataclass(frozen=True)
class Verdict:
    """One model's silence, and what the others did with the same seconds.

    Attributes:
        engine: The model that wrote nothing here.
        start: Seconds from the beginning of the recording.
        seconds: How long the stretch is.
        speech_seconds: How much of it a detector heard as speech, where that is
            known.
        engines_asked: How many models transcribed this recording, this one
            included.
        engines_silent: How many of them wrote nothing over these seconds.
        verdict: One of `ALL_SILENT`, `SOME_SILENT`, `THIS_ENGINE_ONLY`.
    """

    engine: str
    start: float
    seconds: float
    speech_seconds: float
    engines_asked: int
    engines_silent: int
    verdict: str

    @property
    def end(self) -> float:
        """Seconds from the beginning, at the far edge."""
        return self.start + self.seconds

    @property
    def needs_an_ear(self) -> bool:
        """Nothing here can be settled by comparing models.

        Every model wrote nothing and enough of it sounds like speech to be worth
        checking, so the remaining explanations - faint audio, off-microphone, a
        notation nobody said aloud, or a blind spot all of them share - are not
        separable this way.

        The threshold matters: see `MIN_SPEECH_SECONDS`.
        """
        return (
            self.verdict == ALL_SILENT
            and self.speech_seconds >= MIN_SPEECH_SECONDS
        )


def overlap_seconds(first: tuple[float, float], second: tuple[float, float]) -> float:
    """How many seconds two stretches share."""
    return max(0.0, min(first[1], second[1]) - max(second[0], first[0]))


def silent_over(stretches: Iterable[Stretch], start: float, end: float,
                min_share: float = 0.5) -> bool:
    """Did this model leave most of `start`-`end` without words?

    A model that wrote nothing for a tenth of a stretch has not really been
    silent over it. Requiring most of it keeps a near-miss from counting as
    agreement, which would make every verdict look more certain than it is.

    Args:
        stretches: That model's silences.
        start: Beginning of the window, in seconds.
        end: End of the window.
        min_share: How much of the window must be silent to count.

    Returns:
        Whether this model was silent over enough of the window.
    """
    window = (start, end)
    width = end - start
    if width <= 0:
        return False
    shared = sum(overlap_seconds(window, (s.start, s.end)) for s in stretches)
    return shared / width >= min_share


def verdict_for(engines_silent: int, engines_asked: int) -> str:
    """Name the pattern of agreement.

    Args:
        engines_silent: How many models wrote nothing here, including the one
            being judged.
        engines_asked: How many transcribed this recording at all.

    Returns:
        One of the three verdict names.
    """
    if engines_asked <= 1:
        # Nothing to compare against. Not the same as agreement, and calling it
        # ALL_SILENT would quietly promote one model's failure into evidence
        # about the audio.
        return SOME_SILENT
    if engines_silent >= engines_asked:
        return ALL_SILENT
    if engines_silent <= 1:
        return THIS_ENGINE_ONLY
    return SOME_SILENT


def compare(
    by_engine: Mapping[str, Sequence[Any]],
    speech_by_engine: Mapping[str, Mapping[float, float]] | None = None,
    min_share: float = 0.5,
) -> list[Verdict]:
    """Judge every silence against what the other models did.

    Args:
        by_engine: Each model's silences for one recording, keyed by engine name.
        speech_by_engine: How much speech a detector heard in each silence,
            keyed by engine name then by the silence's start time. Optional; the
            verdicts stand without it, but `needs_an_ear` cannot.
        min_share: How much of a stretch another model must also leave empty
            before it counts as silent there.

    Returns:
        One verdict per silence, across every model.
    """
    asked = len(by_engine)
    verdicts: list[Verdict] = []

    for engine, silences in by_engine.items():
        heard = (speech_by_engine or {}).get(engine, {})
        for silence in silences:
            others = sum(
                1
                for other, theirs in by_engine.items()
                if other != engine
                and silent_over(theirs, silence.start, silence.end, min_share)
            )
            verdicts.append(
                Verdict(
                    engine=engine,
                    start=round(silence.start, 2),
                    seconds=round(silence.end - silence.start, 2),
                    speech_seconds=round(float(heard.get(silence.start, 0.0)), 2),
                    engines_asked=asked,
                    engines_silent=others + 1,
                    verdict=verdict_for(others + 1, asked),
                )
            )

    return verdicts


def summarize(verdicts: Sequence[Verdict]) -> dict[str, Any]:
    """Totals for one model, for the per-case tables.

    Args:
        verdicts: Verdicts belonging to a single engine.

    Returns:
        Counts and seconds by verdict.
    """
    own = [v for v in verdicts if v.verdict == THIS_ENGINE_ONLY]
    shared = [v for v in verdicts if v.verdict == ALL_SILENT]
    return {
        "silences_judged": len(verdicts),
        "this_engine_only": len(own),
        "this_engine_only_speech_seconds": round(
            sum(v.speech_seconds for v in own), 1
        ),
        "all_engines_silent": len(shared),
        "needs_an_ear": sum(1 for v in verdicts if v.needs_an_ear),
    }

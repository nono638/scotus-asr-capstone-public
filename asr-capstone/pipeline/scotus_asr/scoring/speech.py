"""Was there speech in the stretches the model said nothing about?

`coverage.py` finds the parts of a recording with no word against them. It cannot
say whether those parts are a pause while counsel finds a page or ten seconds of
argument nobody wrote down, and that difference is the whole question.

A voice activity detector answers it. Silero v6 ships inside faster-whisper as an
ONNX model, so nothing new has to be installed, and it runs on the processor
while the card is free for transcription.

**This is the opposite use of the one the settings file warns about.** The
transcription runs with silence filtering deliberately off, because a filter that
decides what the model never hears is a known cause of dropped speech, and its
mistakes would be reported as the model's. Here the detector reads the audio and
changes nothing: it is asked whether speech was present, after the fact, in a
stretch a model already failed to transcribe. Measuring with a tool you would not
transcribe with is a reasonable thing to do, but it is worth saying out loud.

The detector is not an oracle either. It answers "does this sound like speech",
so a cough or a shuffle can register, and very quiet speech can be missed. It
turns an unknown into a measurement with a known bias, which is progress, not a
verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

#: Silero's own default. Probabilities above this count as speech.
SPEECH_THRESHOLD = 0.5

#: Ignore blips. A quarter of a second is shorter than almost any word, so
#: anything below it is more likely a noise than something a reporter would have
#: taken down.
MIN_SPEECH_MS = 250

#: No padding. The detector normally pads each speech region by 400ms on both
#: sides to avoid clipping words for transcription. Padding here would inflate
#: the very number being measured, so it is turned off.
SPEECH_PAD_MS = 0

#: How long a quiet stretch has to be before the detector will break a speech
#: region at it. **This is the setting that decides whether the measure means
#: anything.**
#:
#: Silero's default is 2000ms, chosen so transcription does not chop a sentence
#: at every breath. Used for measuring, it joins everything either side of a
#: pause shorter than two seconds into one speech region - so a one-second gap
#: between two words reads as 100% speech, and the number becomes a tautology.
#: Measured that way, the first three cases came out at 65-75% "unwritten
#: speech" in stretches that held nothing of the kind.
#:
#: 100ms lets the detector report the actual quiet, which is what is being asked
#: about.
MIN_SILENCE_MS = 100

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class SilenceVerdict:
    """What the detector heard in one stretch the model left empty.

    Attributes:
        start: Seconds from the beginning of the recording.
        seconds: How long the stretch is.
        speech_seconds: How much of it sounds like speech.
    """

    start: float
    seconds: float
    speech_seconds: float

    @property
    def speech_share(self) -> float:
        """What fraction of the stretch sounds like speech."""
        return self.speech_seconds / self.seconds if self.seconds > 0 else 0.0

    @property
    def holds_speech(self) -> bool:
        """Enough speech here to call it something the record is missing."""
        return self.speech_seconds >= MIN_SPEECH_MS / 1000


def speech_regions(audio, sampling_rate: int = SAMPLE_RATE) -> list[tuple[float, float]]:
    """Every stretch of a recording the detector thinks is speech.

    Args:
        audio: The whole recording as one-dimensional float samples.
        sampling_rate: Samples per second. Silero expects 16 kHz.

    Returns:
        `(start, end)` in seconds, in order.
    """
    from faster_whisper.vad import VadOptions, get_speech_timestamps  # noqa: PLC0415

    found = get_speech_timestamps(
        audio,
        VadOptions(
            threshold=SPEECH_THRESHOLD,
            min_speech_duration_ms=MIN_SPEECH_MS,
            min_silence_duration_ms=MIN_SILENCE_MS,
            speech_pad_ms=SPEECH_PAD_MS,
        ),
        sampling_rate=sampling_rate,
    )
    return [(r["start"] / sampling_rate, r["end"] / sampling_rate) for r in found]


def _overlap(first: tuple[float, float], second: tuple[float, float]) -> float:
    """How many seconds two stretches share."""
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def judge_silences(
    silences: Sequence[Any], regions: Sequence[tuple[float, float]]
) -> list[SilenceVerdict]:
    """Say how much speech sits inside each stretch the model left empty.

    Args:
        silences: What `coverage.find_silences` found, each with `start`, `end`.
        regions: Speech stretches from `speech_regions`.

    Returns:
        One verdict per silence, in the order given.
    """
    ordered = sorted(regions)
    verdicts: list[SilenceVerdict] = []

    for silence in silences:
        window = (silence.start, silence.end)
        # Regions are in order, so stop once they start after this window ends.
        spoken = 0.0
        for region in ordered:
            if region[0] >= window[1]:
                break
            spoken += _overlap(window, region)
        verdicts.append(
            SilenceVerdict(
                start=silence.start,
                seconds=silence.end - silence.start,
                speech_seconds=round(spoken, 2),
            )
        )

    return verdicts


def summarize_verdicts(verdicts: Sequence[SilenceVerdict]) -> dict[str, Any]:
    """Totals across one case.

    Args:
        verdicts: What `judge_silences` produced.

    Returns:
        Columns describing how much of the untranscribed audio held speech.
    """
    silent = sum(v.seconds for v in verdicts)
    spoken = sum(v.speech_seconds for v in verdicts)
    with_speech = [v for v in verdicts if v.holds_speech]
    return {
        "silences_checked": len(verdicts),
        "silent_seconds": round(silent, 1),
        "unwritten_speech_seconds": round(spoken, 1),
        "unwritten_speech_share_of_silence": round(100 * spoken / silent, 1)
        if silent > 0
        else 0.0,
        "silences_holding_speech": len(with_speech),
        "worst_unwritten_seconds": round(
            max((v.speech_seconds for v in verdicts), default=0.0), 1
        ),
    }


def level_dbfs(samples) -> float:
    """How loud a stretch of audio is, in decibels below full scale.

    Separates two things the speech detector cannot. Speech a microphone barely
    caught sits far below the recording's own level; speech at normal level that
    a model simply did not write down sits at it. Measured on one argument: the
    recording averaged -18.8, a stretch holding speech -17.6, a stretch holding
    none -40.1. Twenty decibels apart, which is not a subtle distinction.

    Compare against the whole recording rather than a fixed number. Levels differ
    between recordings - this corpus spans 2010 to 2025 and several changes of
    equipment - so an absolute threshold would mean different things in different
    years.

    Args:
        samples: Audio as floats.

    Returns:
        Decibels below full scale. Silence floors at -90 rather than diverging.
    """
    import numpy as np  # noqa: PLC0415

    block = np.asarray(samples, dtype=float)
    if block.size == 0:
        return -90.0
    rms = float(np.sqrt(np.mean(block * block)))
    # True digital silence would be minus infinity, which no table wants.
    return max(20.0 * float(np.log10(max(rms, 1e-9))), -90.0)


def load_audio(path: Path, sampling_rate: int = SAMPLE_RATE):
    """Read a recording as mono float samples at the rate Silero expects."""
    import librosa  # noqa: PLC0415

    audio, _ = librosa.load(str(path), sr=sampling_rate, mono=True)
    return audio

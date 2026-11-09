"""Whisper, run through faster-whisper.

Whisper large-v3 is the model here for one reason above accuracy: it has to be
fine-tunable later, and Whisper through Hugging Face is the best-documented
training path in open speech recognition. NVIDIA's Parakeet and Canary score
better on the leaderboards but fine-tune through NeMo, which NVIDIA supports on
Windows only under WSL2.

faster-whisper itself cannot be trained - it is a fast inference runtime built on
CTranslate2. The two paths meet at the checkpoint: the same `openai/whisper-large-v3`
is LoRA-tuned with `transformers` and `peft`, then converted back with
`ct2-transformers-converter`, which ships inside CTranslate2. So the baseline
measured here and the fine-tuned model measured later are the same weights in two
runtimes, and the comparison is honest.

Two settings are deliberately cautious, and both are explained in the settings file.
Briefly: the model is not shown its own previous output, because that is what makes
it get stuck repeating a phrase; and silence filtering is off, because it is a
known cause of quietly dropped speech and dropped speech is the thing being
measured.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..config import AsrSettings
from ..gpu import ensure_cuda_libraries, log_memory, prepare_gpu
from ..store import atomic_write_text
from .base import AsrResult, ProgressCallback, Segment, Word

#: How close to the end of the recording a word-timing crash may happen and
#: still be let go. faster-whisper 1.2.1 raises an IndexError in `find_alignment`
#: when the last fraction of a second decodes to a token with no audio frames
#: under it. 22-1008 (OT2023) hit it on all three attempts, 0.5 s from the end,
#: after "The case is submitted." had already been decoded; everything before
#: was fine and was thrown away with it. Anywhere earlier it is still an error.
_TAIL_SECONDS = 2.0


class FasterWhisperEngine:
    """Runs Whisper over a recording and returns timed words.

    The model is loaded the first time it is needed rather than in the
    constructor. Building the list of tasks for a run therefore costs nothing,
    and a run where every case is already done never touches the GPU at all.

    **One engine transcribes many recordings.** Each one holds about 4 GB of
    video memory and nothing releases it, so an engine per case fills a 24 GB
    card on the sixth. What happens then is not a crash, which is the dangerous
    part: decoding keeps working and drops from about 19 times real time to
    about 1.5, so a run that should take seven hours takes two days and every
    result it produces is still correct. It was caught by reading the speeds in
    a finished run's log, not by anything failing.

    So `partial_path` belongs to `transcribe`, not to the engine. It was the
    only per-case state here, and having it in the constructor was the reason a
    fresh engine was built for every case.

    Args:
        settings: Model, device and decoding options.
        partial_path: A default for `transcribe`, for one-off use. A run over
            many cases passes the path per call instead.
    """

    def __init__(self, settings: AsrSettings, partial_path: Path | None = None) -> None:
        self.settings = settings
        self.partial_path = partial_path
        self._model: Any = None

    @property
    def name(self) -> str:
        """Short identifier, used in filenames and results tables."""
        return f"whisper-{self.settings.model}"

    def _load(self) -> Any:
        """Load the model, once.

        Imported here rather than at the top of the file so that the rest of the
        pipeline, and most of the tests, run without faster-whisper installed and
        without a GPU present.
        """
        if self._model is not None:
            return self._model

        # Must happen before CTranslate2 loads. On Windows it looks for NVIDIA's
        # maths libraries on the PATH, and PyTorch's copies are not there, so
        # without this the first attempt to encode audio fails with a message
        # claiming cublas64_12.dll is missing when it is sitting in site-packages.
        ensure_cuda_libraries()

        # A usable card and room on it. No ceiling: faster-whisper keeps its
        # memory through CTranslate2, which PyTorch's cap does not reach. About
        # 4 GB loaded (see the class note); 5 leaves room for beam search.
        prepare_gpu(self.settings.device, 5.0, f"Whisper {self.settings.model}", cap=False)

        from faster_whisper import WhisperModel  # noqa: PLC0415 - deliberately late

        self._model = WhisperModel(
            self.settings.model,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
        )
        log_memory(f"loading Whisper {self.settings.model}")
        return self._model

    def settings_used(self) -> dict[str, Any]:
        """Everything this engine ran with, for the record.

        A superset of `_decode_kwargs`: those are the arguments faster-whisper
        takes, and the model, device and precision go to its constructor instead.
        Both belong in the record, so they are joined here and separated only
        where the library insists.
        """
        return {
            "model": self.settings.model,
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            **self._decode_kwargs(),
        }

    def _decode_kwargs(self) -> dict[str, Any]:
        """The decoding options, in the form faster-whisper expects.

        Kept separate from `settings_used` because these are passed straight
        through as `**kwargs`, so anything added that the library does not accept
        would fail the call rather than merely look untidy.
        """
        return {
            "language": self.settings.language or None,
            "beam_size": self.settings.beam_size,
            "word_timestamps": self.settings.word_timestamps,
            "condition_on_previous_text": self.settings.condition_on_previous_text,
            "vad_filter": self.settings.vad_filter,
            "temperature": list(self.settings.temperatures),
            "compression_ratio_threshold": self.settings.compression_ratio_threshold,
            "log_prob_threshold": self.settings.log_prob_threshold,
            "no_speech_threshold": self.settings.no_speech_threshold,
        }

    def transcribe(
        self,
        audio_path: Path,
        docket: str,
        on_progress: ProgressCallback | None = None,
        partial_path: Path | None = None,
    ) -> AsrResult:
        """Transcribe one recording.

        faster-whisper hands back segments lazily, one at a time as it decodes.
        That is used twice here: to report progress on a job that can run for
        twenty minutes, and to append each segment to a `.partial.jsonl` file as
        it arrives.

        About that partial file. If the machine dies an hour into a long
        recording, the partial holds everything decoded up to that point, so the
        work is visible rather than gone. A resumed run still redoes the file from
        the start, and that is on purpose: faster-whisper can be told to begin at
        an offset, but that path has documented bugs around dropped audio at the
        boundaries, and dropped audio is exactly what this project measures.
        Resuming cheaply is not worth contaminating the measurement.

        Args:
            audio_path: The recording.
            docket: The case, recorded on the result.
            on_progress: Called with (fraction done, note).
            partial_path: Where to stream segments for this recording. Given per
                call rather than per engine so one loaded model can transcribe a
                whole term - see the note on the class.

        Returns:
            The transcription.

        Raises:
            FileNotFoundError: If the audio is not there.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(
                f"No audio at {audio_path}. Run the fetch stage first - the MP3s "
                f"are kept out of version control."
            )

        # Per call, falling back to the engine's own for a single-case use.
        stream_to = partial_path if partial_path is not None else self.partial_path

        model = self._load()
        started = time.monotonic()

        segment_stream, info = model.transcribe(str(audio_path), **self._decode_kwargs())

        total_seconds = float(getattr(info, "duration", 0.0) or 0.0)
        segments: list[Segment] = []
        partial_lines: list[str] = []
        settings = self.settings_used()

        for index, raw in enumerate(_stop_at_tail_crash(segment_stream, segments, total_seconds, settings)):
            segment = _to_segment(index, raw)
            segments.append(segment)

            if stream_to is not None:
                partial_lines.append(json.dumps(segment.to_dict(), ensure_ascii=False))
                # Rewritten rather than appended so the file is always valid.
                # Cheap next to decoding, which is the only thing that costs time.
                atomic_write_text(stream_to, "\n".join(partial_lines) + "\n")

            if on_progress is not None and total_seconds > 0:
                on_progress(
                    min(segment.end / total_seconds, 1.0),
                    f"{_clock(segment.end)} of {_clock(total_seconds)}",
                )

        result = AsrResult(
            docket=docket,
            engine=self.name,
            model=self.settings.model,
            segments=segments,
            audio_seconds=total_seconds,
            runtime_seconds=time.monotonic() - started,
            language=getattr(info, "language", "") or "",
            settings=settings,
        )

        # The partial file has served its purpose once the real result exists.
        if stream_to is not None:
            stream_to.unlink(missing_ok=True)

        return result


def _stop_at_tail_crash(
    stream: Any, segments: list[Segment], total_seconds: float, settings: dict[str, Any]
) -> Any:
    """Pass segments through, ending quietly on a word-timing crash at the very end.

    See `_TAIL_SECONDS`. `segments` is the caller's list, read here to see how far
    decoding got. When the crash is let go, the time it happened is written into
    `settings`, which is saved with the transcript, so it stays visible.
    """
    try:
        yield from stream
    except IndexError:
        reached = segments[-1].end if segments else 0.0
        if total_seconds <= 0 or total_seconds - reached > _TAIL_SECONDS:
            raise
        settings["word_timing_crash_ignored_at"] = round(reached, 2)


def _to_segment(index: int, raw: Any) -> Segment:
    """Convert one faster-whisper segment into the shape this project uses.

    Written defensively with `getattr` because faster-whisper's segment type has
    gained and lost fields between versions, and a missing diagnostic field
    should not end a twenty-minute transcription.
    """
    words = [
        Word(
            text=word.word,
            start=float(word.start),
            end=float(word.end),
            probability=getattr(word, "probability", None),
        )
        for word in (getattr(raw, "words", None) or [])
    ]

    return Segment(
        index=index,
        start=float(raw.start),
        end=float(raw.end),
        text=raw.text.strip(),
        words=words,
        no_speech_prob=getattr(raw, "no_speech_prob", None),
        avg_logprob=getattr(raw, "avg_logprob", None),
        compression_ratio=getattr(raw, "compression_ratio", None),
        temperature=getattr(raw, "temperature", None),
    )


def _clock(seconds: float) -> str:
    """Seconds as `h:mm:ss`, for progress messages a person reads."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"

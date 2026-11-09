"""Mistral's Voxtral, run through transformers.

The fifth and sixth models in the study, and the first from a vendor with no
stake in any of the others. Four models in, two of them were NVIDIA's and trained
on overlapping data, so where Parakeet and Canary agreed against the rest shared
training explained it as well as shared hearing. Mistral is independent of all
four, which makes the agreement measure mean more than it did.

**Two Voxtrals, and the difference is the point.** Mistral publishes an offline
model and a streaming one, and this engine runs either:

- `Voxtral-Mini-3B-2507` (July 2025) transcribes a recording afterwards, the way
  every other model here does.
- `Voxtral-Mini-4B-Realtime-2602` (February 2026) transcribes as the audio
  arrives, the way live captioning does. It is newer and deliberately less
  accurate: Mistral's own figures put it at 6.73% against their batch model's
  5.90%, because it must commit to a word before the sentence is finished.

That gap is worth measuring on this corpus rather than reading off a leaderboard.
A courtroom transcript is made live, while people are speaking - the reporter
does not get to go away and think about it. So the question "how much accuracy
does transcribing live cost you" is not a side issue for a study of certified
records. It is closer to the real task than the batch case is.

**No timings of its own**, so `aligner.py` supplies them, the same aligner Qwen3
and Canary use. That is what caps the chunk length: the aligner takes five
minutes at a time.

**What is not here.** Mistral's most accurate model, `Voxtral Mini Transcribe 2`,
is API-only at $0.003 a minute - about $11 for this corpus. It is left out on
purpose. A hosted model can change without notice, which would leave a number in
this project that nobody, including its author, could reproduce. Every model here
is pinned to a version and re-runnable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..config import AsrSettings
from ..gpu import log_memory, mark, prepare_gpu, release_memory
from ..store import atomic_write_text
from .aligner import ForcedAligner, aligner_compute_type
from .base import (
    loop_settings,
    AsrResult,
    ProgressCallback,
    Segment,
    Word,
    decode_chunk,
    decode_with_fallback,
    sampling_options,
    watch_pace,
)
from .parakeet_engine import keep_window

#: Seconds of audio per pass.
#:
#: Voxtral itself would take far more - thirty minutes in one go - but the
#: aligner that supplies the timings handles five, so this sits just under it,
#: matching the Qwen3 engine. Measured up to four minutes with no sign of the
#: falling-off that caught Canary: words a minute rose with chunk length rather
#: than dropping, which is what a model keeping up looks like.
CHUNK_SECONDS = 280.0

#: How much neighbouring chunks share. A word straddling a seam is decoded twice
#: and the midpoint of the overlap decides which copy is kept.
OVERLAP_SECONDS = 8.0

#: Room for five minutes of argument. Appellate speech runs near 175 words a
#: minute, so this is generous without being unbounded.
MAX_NEW_TOKENS = 2048

SAMPLE_RATE = 16_000

#: What this engine needs on the card, in gigabytes, checked before anything is
#: loaded.
#:
#: Measured on 22 September 2026 rather than worked out from the parameter
#: count, and the difference between the two matters:
#:
#:   weights and aligner, sitting idle   12.2 GB
#:   peak while decoding a chunk         17.1 GB
#:
#: Arithmetic from the parameter count gives the first number - 4.7 billion
#: parameters at two bytes each is 9.4 GB, plus 1.2 GB for the aligner - and
#: the first number is the wrong one to check against. Decoding 280 seconds of
#: audio adds about 5 GB of working memory on top, and a run admitted on the
#: idle figure would hit the ceiling a minute later, which is the failure this
#: is here to prevent.
#:
#: The check matters because running short does not fail. Windows moves GPU
#: memory out to system RAM and carries on many times slower without raising
#: anything, so an unattended run turns into a run that looks fine and takes
#: all night. Better to refuse at the start than to discover it in the morning.
#:
#: 18 rather than 17.1, because the peak was measured on one recording and a
#: denser argument produces more tokens per chunk.
APPROX_VRAM_GB = 18.0

#: What the processor is told the samples are, when handed an array rather than a
#: file. Without it `apply_transcription_request` refuses outright.
AUDIO_FORMAT = "WAV"


class VoxtralEngine:
    """Runs Voxtral over a recording and returns timed words.

    Same shape as the other engines - a name and a `transcribe` - so the runner,
    the scorer and the results tables need no changes.

    Both models load on first use and are kept for the whole run. Building one
    engine per case would hold two models' worth of video memory per case; see
    the note in `faster_whisper_engine`, which learned that the expensive way.

    Args:
        settings: Model, device and precision. The decoding options belonging to
            Whisper have no counterpart here and are ignored rather than faked.
        partial_path: A default for `transcribe`, for one-off use.
    """

    def __init__(self, settings: AsrSettings, partial_path: Path | None = None) -> None:
        self.settings = settings
        self.partial_path = partial_path
        self._model: Any = None
        self._processor: Any = None
        self._aligner = ForcedAligner(
            device=settings.device, compute_type=aligner_compute_type(settings)
        )

    @property
    def name(self) -> str:
        """Short identifier, used in filenames and results tables.

        The model names already say voxtral, so it is not said twice. Checked
        case-insensitively, because the repositories are capitalised and a
        lowercase test would produce `voxtral-Voxtral-Mini-3B-2507` - the
        doubling two earlier engines here ran into.
        """
        model = self.settings.model
        return model if model.lower().startswith("voxtral") else f"voxtral-{model}"

    @property
    def _model_id(self) -> str:
        """The Hugging Face repository to load."""
        model = self.settings.model
        return model if "/" in model else f"mistralai/{model}"

    @property
    def is_realtime(self) -> bool:
        """Whether this is the streaming model rather than the batch one.

        They need different transformers classes, and the difference matters to
        the result as well as to the code: the streaming model commits to a word
        before the sentence is finished, which is what a live courtroom
        transcript has to do and what the batch model is spared.
        """
        return "realtime" in self._model_id.lower()

    def _load(self):
        """Load the model and processor, and the shared aligner, once."""
        if self._model is not None:
            return self._processor, self._model

        import torch  # noqa: PLC0415 - deliberately late, as with the others
        from transformers import AutoProcessor  # noqa: PLC0415

        # Before anything is loaded, because the alternative is not an error.
        # See the note on APPROX_VRAM_GB.
        prepare_gpu(
            self.settings.device, APPROX_VRAM_GB, self._model_id,
            bfloat16=self.settings.compute_type != "float32",
        )
        # That also sets the ceiling: past it PyTorch raises instead of letting
        # Windows page GPU memory out to system RAM. See `gpu.prepare_gpu`.

        if self.is_realtime:
            from transformers import (  # noqa: PLC0415
                VoxtralRealtimeForConditionalGeneration as Model,
            )
        else:
            from transformers import (  # noqa: PLC0415
                VoxtralForConditionalGeneration as Model,
            )

        dtype = (
            torch.bfloat16 if self.settings.compute_type in ("bfloat16", "float16")
            else torch.float32
        )
        self._processor = AutoProcessor.from_pretrained(self._model_id)
        self._model = Model.from_pretrained(
            self._model_id, dtype=dtype, device_map=self.settings.device
        ).eval()
        self._aligner.load()
        # What it really costs, now that both are on the card. This is the
        # number that should replace the estimate above once a few runs agree.
        log_memory(f"loading {self._model_id} and the aligner")
        return self._processor, self._model

    def settings_used(self) -> dict[str, Any]:
        """What was used, recorded on the result so it can be reproduced."""
        return {
            "model": self._model_id,
            "aligner": self._aligner.repo_id,
            "aligner_compute_type": self._aligner.compute_type,
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            "language": self.settings.language or "en",
            "streaming_model": self.is_realtime,
            "chunk_seconds": CHUNK_SECONDS,
            "overlap_seconds": OVERLAP_SECONDS,
            "max_new_tokens": MAX_NEW_TOKENS,
            "sample_rate": SAMPLE_RATE,
            "temperatures": list(self.settings.temperatures),
            **loop_settings(),
        }

    def _transcribe_piece(self, piece, language: str, temperature: float = 0.0) -> str:
        """Text for one chunk, with the prompt trimmed off.

        Args:
            piece: The chunk, as 16 kHz mono samples.
            language: What to transcribe it as.
            temperature: 0.0 takes the likeliest token every time, which is
                what this did unconditionally until a chunk of people talking
                over each other sent it into a repetition loop. Above zero it
                samples, which `decode_with_fallback` uses to break out of one.
        """
        import torch  # noqa: PLC0415

        processor, model = self._load()
        # `format` is required when the audio arrives as an array rather than a
        # path; without it the processor raises rather than guessing.
        inputs = processor.apply_transcription_request(
            audio=piece,
            language=language,
            model_id=self._model_id,
            sampling_rate=SAMPLE_RATE,
            format=AUDIO_FORMAT,
        ).to(self.settings.device, dtype=_dtype(self.settings.compute_type))

        with torch.no_grad():
            produced = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                **sampling_options(temperature),
            )

        # generate() returns the prompt as well; only what followed it is the
        # transcript.
        answer = produced[:, inputs["input_ids"].shape[1]:]
        return processor.batch_decode(answer, skip_special_tokens=True)[0].strip()

    def transcribe(
        self,
        audio_path: Path,
        docket: str,
        on_progress: ProgressCallback | None = None,
        partial_path: Path | None = None,
    ) -> AsrResult:
        """Transcribe one recording.

        Args:
            audio_path: The recording.
            docket: The case, recorded on the result.
            on_progress: Called with (fraction done, note).
            partial_path: Where to stream segments as they are produced, so a
                run killed part-way leaves its work behind.

        Returns:
            The transcription, with a segment per chunk and timed words.

        Raises:
            FileNotFoundError: If the audio is not there.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(
                f"No audio at {audio_path}. Run the fetch stage first - the MP3s "
                f"are kept out of version control."
            )

        import librosa  # noqa: PLC0415

        stream_to = partial_path if partial_path is not None else self.partial_path
        language = self.settings.language or "en"
        self._load()
        started = time.monotonic()

        audio, _ = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)
        total_seconds = len(audio) / SAMPLE_RATE

        segments: list[Segment] = []
        partial_lines: list[str] = []
        chunk_times: list[float] = []
        step = CHUNK_SECONDS - OVERLAP_SECONDS
        index = 0
        offset = 0.0

        while offset < total_seconds:
            first = int(offset * SAMPLE_RATE)
            last = int(min(offset + CHUNK_SECONDS, total_seconds) * SAMPLE_RATE)
            piece = audio[first:last]
            if len(piece) < SAMPLE_RATE:  # under a second left; nothing to decode
                break

            mark(f"{docket} chunk {index}", sample=True)
            chunk_started = time.monotonic()

            def work(piece=piece, offset=offset):
                # The loop check happens before alignment on purpose. A
                # repeating chunk hands the aligner two and a half times the
                # text it should, and that is what filled the card.
                text, ratio, temperature = decode_with_fallback(
                    lambda t: self._transcribe_piece(piece, language, t),
                    len(piece) / SAMPLE_RATE,
                    docket,
                    index,
                    self.settings.temperatures,
                )
                words = self._aligner.align(piece, text, language, offset)
                return text, ratio, temperature, words

            text, ratio, temperature, words = decode_chunk(work, docket, index)

            # After every chunk, not just every case. The allocator ratchets
            # up about 4 GB a chunk otherwise and fills the card by the third
            # one - see the measurements in `gpu.release_memory`. 69ms.
            release_memory()

            watch_pace(
                docket,
                index,
                time.monotonic() - chunk_started,
                chunk_times,
                retried=temperature > 0,
            )

            keep_from, keep_until = keep_window(
                offset, index, total_seconds, CHUNK_SECONDS, OVERLAP_SECONDS
            )
            kept = [w for w in words if keep_from <= w.start < keep_until]

            if kept:
                segment = Segment(
                    index=index,
                    start=kept[0].start,
                    end=kept[-1].end,
                    text="".join(w.text for w in kept).strip(),
                    words=kept,
                    # So a result carries how it was produced. A temperature
                    # above zero means the first decode was rejected as a loop.
                    compression_ratio=ratio,
                    temperature=temperature,
                )
                segments.append(segment)

                if stream_to is not None:
                    partial_lines.append(
                        json.dumps(segment.to_dict(), ensure_ascii=False)
                    )
                    atomic_write_text(stream_to, "\n".join(partial_lines) + "\n")

            if on_progress is not None and total_seconds > 0:
                done = min((offset + CHUNK_SECONDS) / total_seconds, 1.0)
                on_progress(
                    done,
                    f"{_clock(min(offset + CHUNK_SECONDS, total_seconds))}"
                    f" of {_clock(total_seconds)}",
                )

            index += 1
            offset += step

        result = AsrResult(
            docket=docket,
            engine=self.name,
            model=self.settings.model,
            segments=segments,
            audio_seconds=total_seconds,
            runtime_seconds=time.monotonic() - started,
            language=language,
            settings=self.settings_used(),
        )

        if stream_to is not None:
            stream_to.unlink(missing_ok=True)

        # Between recordings, hand back whatever PyTorch is keeping in reserve.
        # The models stay loaded - that is deliberate and is what makes the run
        # fast - but the working memory from decoding this case is of no use to
        # the next one, and holding it is how a run creeps up on the card's
        # limit over ninety cases.
        mark(f"{docket} finished", sample=True)
        release_memory()
        log_memory(f"finishing {docket}")

        return result


def _dtype(compute_type: str):
    """The torch dtype named in the settings.

    Voxtral is published in bfloat16 and the model card runs it that way, so
    `float16` is read as a request for sixteen-bit rather than for that exact
    format - the two behave the same here and mixing them raises.
    """
    import torch  # noqa: PLC0415

    return torch.float32 if compute_type == "float32" else torch.bfloat16


def _clock(seconds: float) -> str:
    """Seconds as `h:mm:ss`, matching the other engines' progress notes."""
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"

"""Qwen3-ASR, run through transformers.

The third model in the study, and the one that tests whether size explains what
the second one showed. Parakeet TDT is 0.6 billion parameters against Whisper's
1.55, so its heavier tidying of disfluent speech could have been capacity rather
than training. Qwen3-ASR-1.7B is larger than Whisper, so if the tidying persists
it is not about size.

**Two models, not one.** The transcriber produces text and no timings. Word
timings come from a separate forced aligner, which takes the audio and the
transcript and says where each word sits. That matters more here than it would
elsewhere: without timings this project loses the silence measure and the
ability to locate a dropped passage in the recording, which is two of its
measures rather than a convenience.

The aligner is cheap - one forward pass, no decoding, about a twentieth of a
second for five minutes of audio - so the cost is the extra model in memory, not
the time.

**The aligner sets the chunk size.** It handles five minutes at a time, so the
audio is cut into pieces just under that, overlapping, with the midpoint of each
overlap deciding which copy of a straddling word to keep. The transcriber alone
would take longer pieces, but there is no use for text that cannot be placed in
the recording. The seam rule is shared with the Parakeet engine, which is tested
to tile a recording with no gap and no double.

Use the `-hf` repositories. `Qwen/Qwen3-ASR-1.7B` without that suffix carries the
Qwen team's own format, and the transformers classes will not load it - the same
trap that stopped Canary-Qwen, whose Hugging Face repository holds a NeMo
training config rather than a transformers one.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..config import AsrSettings
from ..gpu import log_memory, prepare_gpu, release_memory
from ..store import atomic_write_text
from .aligner import ForcedAligner, aligner_compute_type
from .base import (
    loop_settings,
    AsrResult,
    ProgressCallback,
    Segment,
    Word,
    decode_with_fallback,
    sampling_options,
)
from .parakeet_engine import keep_window

#: Seconds of audio per pass.
#:
#: Two limits apply and the tighter one wins. Qwen document the model itself
#: as handling a single audio up to twenty minutes, so it is not the
#: constraint. The forced aligner that supplies the word timings handles five
#: minutes, and this sits just under that rather than on the limit.
#:
#: **Longer than the published long-form work uses.** Research on this model
#: cuts at 180 seconds; this is 280. That is a deviation and it was checked
#: rather than assumed: `tools/chunk_sweep.py` decoded three hard passages at
#: 60, 120, 180, 280 and 400 seconds and every one came back between 158 and
#: 188 words a minute, where real argument sits. No sign of the collapse that
#: caught Granite at 100 seconds or Parakeet at 600.
#:
#: Worth re-checking if the model or the aligner is ever changed. Being inside
#: a documented maximum is not evidence of anything - Granite had no published
#: limit at all and broke at seventy seconds.
CHUNK_SECONDS = 280.0

#: How much neighbouring chunks share. Far longer than any word, so no word can
#: span a whole overlap and be lost by the midpoint rule.
OVERLAP_SECONDS = 8.0

SAMPLE_RATE = 16_000

#: Room for five minutes of argument, and a bound on a runaway.
#:
#: Appellate speech runs near 175 words a minute, so 280 seconds holds about
#: 815 words - roughly 1,100 tokens. 2,048 is not quite twice that: generous
#: for dense questioning, and short of letting a repetition loop run for ever.
#:
#: Qwen publish no recommended value. This is the same reasoning applied to
#: Parakeet after it turned out to have no ceiling at all and returned 42,639
#: words from ten minutes of audio.
MAX_NEW_TOKENS = 2048

#: Video memory needed at the peak, transcriber and aligner together, checked
#: before loading. Measured on run-scotus250-qwen3 (75 arguments of OT2010,
#: 16-17 Oct 2026): 5.5 GB once loaded, 14.4 GB reserved at the peak. The first
#: estimate here was 10 GB, made before any run had logged it, and would have
#: admitted a card that then ran out partway through. Decoding five minutes of
#: audio costs far more than the weights.
APPROX_VRAM_GB = 16.0


class Qwen3Engine:
    """Runs Qwen3-ASR over a recording and returns timed words.

    Same shape as the other engines - a name and a `transcribe` - so the runner,
    the scorer and the result tables need no changes.

    Both models load on first use and are kept for the whole run. One engine per
    case would hold two models' worth of video memory per case; see the note in
    `faster_whisper_engine`, which learned that the expensive way.

    Args:
        settings: Model, device and precision. The decoding options belonging to
            Whisper have no counterpart here and are ignored rather than faked.
        partial_path: A default for `transcribe`, for one-off use.
    """

    def __init__(self, settings: AsrSettings, partial_path: Path | None = None) -> None:
        self.settings = settings
        self.partial_path = partial_path
        self._processor: Any = None
        self._model: Any = None
        #: Timings come from a forced aligner shared with the Canary engine.
        #: Shared deliberately rather than copied: running a second model
        #: through the identical aligner is what makes it possible to tell
        #: this engine's silence apart from the aligner's own placement
        #: error. See `aligner.py`.
        self._aligner = ForcedAligner(
            device=settings.device, compute_type=aligner_compute_type(settings)
        )

    @property
    def name(self) -> str:
        """Short identifier, used in filenames and results tables."""
        # Case-insensitive: the repository is `Qwen3-ASR-1.7B-hf` with a capital,
        # and a lowercase check prefixes it into `qwen3-asr-Qwen3-ASR-1.7B-hf`.
        model = self.settings.model
        return model if model.lower().startswith("qwen") else f"qwen3-asr-{model}"

    @property
    def _model_id(self) -> str:
        """The transcriber's repository."""
        model = self.settings.model
        return model if "/" in model else f"Qwen/{model}"

    @property
    def _aligner_id(self) -> str:
        """The forced aligner's repository."""
        return self._aligner.repo_id

    def _load(self):
        """Load the transcriber and its processor, and the shared aligner, once."""
        if self._model is not None:
            return self._processor, self._model

        import torch  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForMultimodalLM,
            AutoProcessor,
        )

        # Before anything is loaded: a usable card, room on it, and a ceiling.
        # See `gpu.prepare_gpu`.
        prepare_gpu(self.settings.device, APPROX_VRAM_GB, self._model_id)

        dtype = torch.float16 if self.settings.compute_type == "float16" else torch.float32

        self._processor = AutoProcessor.from_pretrained(self._model_id)
        self._model = (
            AutoModelForMultimodalLM.from_pretrained(self._model_id, dtype=dtype)
            .to(self.settings.device)
            .eval()
        )
        self._aligner.load()
        log_memory(f"loading {self._model_id} and the aligner")
        return self._processor, self._model

    def settings_used(self) -> dict[str, Any]:
        """What was used, recorded on the result so it can be reproduced."""
        return {
            "model": self._model_id,
            "aligner": self._aligner_id,
            "aligner_compute_type": self._aligner.compute_type,
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            # Genuinely used - passed to both the transcription request and the
            # aligner - and was missing from this record until it was noticed.
            "language": self.settings.language or "en",
            "chunk_seconds": CHUNK_SECONDS,
            "overlap_seconds": OVERLAP_SECONDS,
            "max_new_tokens": MAX_NEW_TOKENS,
            "sample_rate": SAMPLE_RATE,
            "temperatures": list(self.settings.temperatures),
            **loop_settings(),
        }

    def _transcribe_piece(self, piece, language: str, temperature: float = 0.0) -> str:
        """Text for one chunk of audio, with the prompt trimmed off.

        Args:
            piece: The chunk, as 16 kHz mono samples.
            language: What to transcribe it as.
            temperature: 0.0 is greedy. Above zero it samples, which is how
                `decode_with_fallback` breaks a repetition loop.
        """
        import torch  # noqa: PLC0415

        processor, model = self._load()
        inputs = processor.apply_transcription_request(
            audio=piece, language=language, return_tensors="pt"
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

    def _align_piece(self, piece, text: str, language: str, offset: float) -> list[Word]:
        """Word timings for one chunk, shifted to their place in the recording.

        The work itself lives in `aligner.py`, shared with the Canary engine so
        that comparing the two says something about the models rather than about
        two copies of the same code drifting apart.
        """
        return self._aligner.align(piece, text, language, offset)

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
            partial_path: Where to stream segments as they are produced.

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
        step = CHUNK_SECONDS - OVERLAP_SECONDS
        index = 0
        offset = 0.0

        while offset < total_seconds:
            first = int(offset * SAMPLE_RATE)
            last = int(min(offset + CHUNK_SECONDS, total_seconds) * SAMPLE_RATE)
            piece = audio[first:last]
            if len(piece) < SAMPLE_RATE:  # under a second left; nothing to decode
                break

            # Checked before alignment: a repeating chunk hands the aligner
            # far more text than the audio holds.
            text, ratio, temperature = decode_with_fallback(
                lambda t: self._transcribe_piece(piece, language, t),
                len(piece) / SAMPLE_RATE,
                docket,
                index,
                self.settings.temperatures,
            )
            words = self._align_piece(piece, text, language, offset)

            # The allocator ratchets up a few GB a chunk otherwise, because
            # each chunk decodes a different number of tokens and a block of
            # the wrong size cannot be reused. Voxtral filled a 24 GB card by
            # its third chunk that way and took the machine down with it. These
            # engines are smaller and have not hit the ceiling, but the
            # mechanism is identical and the call costs 69ms. See
            # `gpu.release_memory`.
            release_memory()

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

        return result


def _dtype(compute_type: str):
    """The torch dtype named in the settings."""
    import torch  # noqa: PLC0415

    return torch.float16 if compute_type == "float16" else torch.float32


def _clock(seconds: float) -> str:
    """Seconds as `h:mm:ss`, matching the other engines' progress notes."""
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"

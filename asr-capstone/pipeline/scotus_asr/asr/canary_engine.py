"""NVIDIA Canary-1b-v2, run through transformers.

The fourth model in the study, and it is here for two jobs.

**A fourth opinion.** With three models a stretch of audio that all three skip is
suspicious but thinly evidenced, and "two of three were silent" is an awkward
middle. A fourth vote makes the agreement measure finer: a silence can now be
shared by two, three or four, and only the last is unanimous.

**A control on the aligner.** Qwen3-ASR shows far more silence than Whisper or
Parakeet, and the obvious question is whether that is the model or the forced
aligner it depends on for its timings. Canary has the same dependency - see
below - so it goes through the identical aligner. If its silence looks like
Whisper's and Parakeet's, the aligner is exonerated and Qwen3's excess is real.
If it looks like Qwen3's, the aligner is the suspect and a published finding
needs revisiting. Either answer is worth having.

**Its timings are not its own.** The model card advertises word and segment
timestamps. They come from NVIDIA's own aligner run afterwards, not from the
model: the transformers documentation says they "are not part of the `generate`
output", and a check here confirmed it. The `<|timestamp|>` token sits in the
vocabulary at id 10, the shipped chat template hardcodes `<|notimestamp|>`, and
swapping one for the other changes nothing in what the decoder emits. So Canary
is a text-only model here and `aligner.py` supplies the times.

**It takes much shorter pieces than the other models.** Forty seconds, against
Qwen3's 280 and Parakeet's 300. Canary is trained on short utterances and does
not fail loudly on a long one - it transcribes the first part and stops, and the
dropped remainder reads downstream as speech it could not hear. Since that is the
measurement this project makes, a chunk set too long would not surface as a bug.
It would surface as a finding, and a false one.

The number came from measuring rather than from the model card. At 150 seconds
Canary produced 88 words a minute where the official record holds 182 and the
other three models hold 171 to 178. Fed the same argument at several lengths it
gives 138 words a minute at 20 seconds and 126 at 40, then falls away - 93 at 60,
85 at 90, 53 at 120, 41 at 150 - losing its punctuation on the same slope. The
constant records the measurements.

**A caveat worth stating in any writeup.** Canary and Parakeet are both NVIDIA
models trained on overlapping data, so they are not independent witnesses. Where
those two agree against Whisper and Qwen3, shared training is as good an
explanation as shared hearing.
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
#: Measured, not chosen. Canary is trained on short utterances and NVIDIA's own
#: card says to chunk anything over forty seconds. Feeding it more does not fail
#: - it quietly stops partway and drops the rest, which downstream is
#: indistinguishable from speech the model could not hear. That is the exact
#: measurement this project makes, so getting this number wrong would not show up
#: as a bug, it would show up as a finding.
#:
#: The first attempt used 150 seconds, sized to the decoder's 1024 position
#: embeddings. It ran, it never hit the token ceiling, and it produced 88 words a
#: minute where the official record has 182 and the other three models have 171
#: to 178. Feeding one stretch of argument at several lengths showed where it
#: goes: 138 words a minute at 20 seconds, 126 at 40, then 93 at 60, 85 at 90,
#: 53 at 120 and 41 at 150. Punctuation disappears over the same slope.
#:
#: So the limit is the encoder's training, and it bites long before the decoder's
#: position table does.
CHUNK_SECONDS = 40.0

#: How much neighbouring chunks share. A word straddling a seam is decoded twice
#: and the midpoint of the overlap decides which copy is kept, so nothing is lost
#: and nothing doubled. Eight seconds is far longer than any word.
#:
#: It is a fifth of the chunk here, which is wasteful - the same audio is decoded
#: twice - but Canary runs at fifty times real time, so the waste is cheap and
#: the alternative is trusting a narrower margin at four times as many seams.
OVERLAP_SECONDS = 8.0

#: Ceiling on one chunk's output, and a guard against a decoder that gets stuck
#: repeating itself. Forty seconds of fast argument is around 200 tokens, so this
#: is generous without being unbounded.
MAX_NEW_TOKENS = 320

#: Canary is trained on 16 kHz mono.
SAMPLE_RATE = 16_000

#: Video memory needed at the peak, model and aligner together, checked before
#: loading. The published run (run-20260921-033436) peaked at 4.1 GB reserved.
APPROX_VRAM_GB = 5.0


class CanaryEngine:
    """Runs Canary over a recording and returns timed words.

    Same shape as the other engines - a name and a `transcribe` - so the
    runner, the scorer and the results tables need no changes.

    Both models load on first use and are kept for the whole run. Building one
    engine per case would hold two models' worth of video memory per case; see
    the note in `faster_whisper_engine`, which learned that the expensive way.

    Args:
        settings: Model, device and precision. The decoding options belonging to
            Whisper - beam size, temperature fallback, the silence filter - have
            no counterpart here and are ignored rather than faked.
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
        #: How many chunks of the current recording stopped because they hit
        #: `MAX_NEW_TOKENS` rather than because the model finished. Should be
        #: zero; anything else means the chunk size needs lowering, and is
        #: recorded rather than left to be noticed as missing speech.
        #:
        #: Reset at the top of every `transcribe`. One engine transcribes a whole
        #: run, so a counter that only ever climbs makes each case report the
        #: running total of every case before it - which is what the first run
        #: did, reporting 58 truncations across the corpus where there were 3.
        self.truncated_chunks = 0

    @property
    def name(self) -> str:
        """Short identifier, used in filenames and results tables.

        The model name already says canary, so it is not said twice. Checked
        case-insensitively - the repository is `canary-1b-v2` but a capitalised
        spelling in the settings file would otherwise produce
        `canary-Canary-1b-v2`, which is the doubling two other engines here
        already ran into.
        """
        model = self.settings.model
        return model if model.lower().startswith("canary") else f"canary-{model}"

    @property
    def _model_id(self) -> str:
        """The Hugging Face repository to load."""
        model = self.settings.model
        return model if "/" in model else f"nvidia/{model}"

    def _load(self):
        """Load the model and processor, once."""
        if self._model is not None:
            return self._processor, self._model

        import torch  # noqa: PLC0415 - deliberately late, as with the others
        from transformers import (  # noqa: PLC0415
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
        )

        # Before anything is loaded: a usable card, room on it, and a ceiling.
        # See `gpu.prepare_gpu`.
        prepare_gpu(self.settings.device, APPROX_VRAM_GB, self._model_id)

        dtype = torch.float16 if self.settings.compute_type == "float16" else torch.float32
        self._processor = AutoProcessor.from_pretrained(self._model_id)
        self._model = (
            AutoModelForSpeechSeq2Seq.from_pretrained(self._model_id, dtype=dtype)
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
            "aligner": self._aligner.repo_id,
            "aligner_compute_type": self._aligner.compute_type,
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            "language": self.settings.language or "en",
            "punctuation": True,
            "chunk_seconds": CHUNK_SECONDS,
            "overlap_seconds": OVERLAP_SECONDS,
            "max_new_tokens": MAX_NEW_TOKENS,
            "sample_rate": SAMPLE_RATE,
            "truncated_chunks": self.truncated_chunks,
            "temperatures": list(self.settings.temperatures),
            **loop_settings(),
        }

    def _transcribe_piece(
        self, piece, language: str, temperature: float = 0.0
    ) -> tuple[str, bool]:
        """Text for one chunk, and whether generation ran out of room.

        Args:
            piece: The chunk, as 16 kHz mono samples.
            language: Source language, which is also the target - Canary picks
                transcription over translation by being given the same language
                twice.

        Returns:
            `(text, hit_the_ceiling)`. The flag is true when the model produced
            `MAX_NEW_TOKENS` tokens, which means the chunk was cut off rather
            than finished.
        """
        import torch  # noqa: PLC0415

        processor, model = self._load()
        # The dtype matters as much as the device. The feature extractor returns
        # 32-bit floats whatever the weights are, and moving them to the card
        # without converting fails with "Input type (float) and bias type
        # (c10::Half) should be the same" - which names neither this engine nor
        # the settings that caused it. `BatchFeature.to` converts the floating
        # point tensors and leaves the token ids alone.
        inputs = processor.apply_transcription_request(
            audio=piece,
            source_language=language,
            punctuation=True,
            return_tensors="pt",
        ).to(self.settings.device, dtype=_dtype(self.settings.compute_type))

        with torch.no_grad():
            produced = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                **sampling_options(temperature),
            )

        # generate() returns the task prompt as well; only what followed it is
        # the transcript.
        answer = produced[:, inputs["decoder_input_ids"].shape[1]:]
        hit_ceiling = answer.shape[1] >= MAX_NEW_TOKENS
        text = processor.batch_decode(answer, skip_special_tokens=True)[0].strip()
        return text, hit_ceiling

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
        # This recording's count, not the run's - see the note in __init__.
        self.truncated_chunks = 0
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

            # Canary reports separately whether it ran out of room, which is
            # a different failure from looping and is counted separately. The
            # flag comes from whichever attempt is kept.
            ceiling = {"hit": False}

            def _decode(t, piece=piece):
                text, hit = self._transcribe_piece(piece, language, t)
                ceiling["hit"] = hit
                return text

            text, ratio, temperature = decode_with_fallback(
                _decode,
                len(piece) / SAMPLE_RATE,
                docket,
                index,
                self.settings.temperatures,
            )
            if ceiling["hit"]:
                self.truncated_chunks += 1
            words: list[Word] = self._aligner.align(piece, text, language, offset)

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

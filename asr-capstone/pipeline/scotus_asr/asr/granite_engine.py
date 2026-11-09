"""IBM Granite Speech, run through transformers.

A fifth vendor, and with its Plus sibling the newest model in the study -
Granite Speech 4.1 was released in April 2026.

**The prompt decides whether it writes a record at all.** This is the thing to
know about this model, and it is not a tuning preference. Asked IBM's default
way - "can you transcribe the speech into a written format?" - it returns text
with no capital letters. Asked with the wording IBM document for 4.1, it returns
punctuation and truecasing. Same audio, same weights, same chunk:

    plain        so they are held under, if they are not detained within 100
                 miles of the border. so they've been there longer ...
    punctuated   So they are held under, if they are not detained within 100
                 miles of the border, so they've been there longer ...

The strictest of this project's three scoring rules counts capitals as part of
the record. A run made with the default prompt would report this model tidying
the record away, when it had simply been asked the wrong question. So the prompt
is a constant here rather than a setting, and it is written into every result.

**Granite Speech 3.3-8b is not supported, deliberately.** It is five times
larger, it topped the Open ASR leaderboard, and it cannot punctuate at all -
four different prompts, including the wording above and no system prompt at all,
returned byte-identical lowercase text. Punctuation and truecasing are a 4.1
capability. That is worth recording as a finding rather than a limitation: a
model reaches the top of a leaderboard whose score is computed after punctuation
is deleted, and this one is incapable of producing a certified transcript at any
size. It is not wired up here because a transcript it cannot punctuate is not a
transcript.

**No timings of its own**, so `aligner.py` supplies them, as for Qwen3, Canary
and Voxtral.
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
#: Sixty, and the number matters more here than for any other engine.
#:
#: This was 100 seconds, chosen after measuring at two minutes (122 words a
#: minute) and four minutes (297, correctly read as a repetition loop) and
#: picking something comfortably under the failure. The failure is not at four
#: minutes. It is between 60 and 80 seconds, in the gap those two probes left,
#: and 100 was on the wrong side of it.
#:
#: What that cost: on hard passages - people talking over each other, mostly -
#: Granite collapsed into repeating a phrase for the rest of the chunk. "It is
#: under Section 73. It is under Section 73." 459 words where the audio held
#: about 290. The whole chunk is then lost, because the real words were never
#: written. Over OT2017 that was a median of 480 words an argument missing and
#: an error rate of 12.94%, roughly twice every other model here, which is
#: what prompted somebody to ask whether IBM really shipped a model that bad.
#: They did not.
#:
#: Measured on the six chunks the temperature fallback could not rescue:
#:
#:            100s            60s
#:   15-1439  350 wpm LOOP    169 wpm ok
#:   16-111   314 wpm LOOP    139 wpm ok
#:   16-1011  353 wpm LOOP    149 wpm ok
#:   17-5639  347 wpm LOOP    136 wpm ok
#:   17-586   313 wpm LOOP    166 wpm ok
#:   16-1144  275 wpm LOOP    182 wpm ok
#:
#: Six for six. At 100 seconds every one of them runs at 275 to 353 words a
#: minute; at 60 they sit at 136 to 182, which is where real argument sits.
#: 45 seconds is also clean and was rejected only because it is more chunks
#: for no measured gain.
#:
#: Not the prompt, and not the settings. The prompt is IBM's own wording, the
#: decoding parameters match their model card, nothing was truncating and no
#: chunk was being dropped. Removing the system prompt changes the output by
#: exactly nothing - 459 words either way. It is the length of the audio.
CHUNK_SECONDS = 60.0

#: How much neighbouring chunks share. Longer than any word, so the midpoint rule
#: cannot lose one.
OVERLAP_SECONDS = 8.0

#: Room for a sixty-second chunk of fast argument with plenty to spare, and a
#: guard against the repetition the longer chunks showed.
MAX_NEW_TOKENS = 640

SAMPLE_RATE = 16_000

#: Roughly what this engine wants on the card, in gigabytes, checked before
#: anything is loaded.
#:
#: 2.3 billion parameters at two bytes each is about 4.6 GB, the aligner adds
#: 1.2 GB, and the rest is working room. An estimate, and the real figure is
#: logged straight after loading so it can be corrected from a run. See the
#: longer note in `voxtral_engine` for why running short is worse than failing.
APPROX_VRAM_GB = 8.0

#: The prompt, and it is load-bearing - see the module docstring. IBM's own
#: wording for 4.1.
TRANSCRIBE_PROMPT = "transcribe the speech with proper punctuation and capitalization."

#: IBM's system prompt, kept verbatim from their model card. The model was tuned
#: with it in place and this project is not in the business of finding out what
#: changes when it is removed.
SYSTEM_PROMPT = (
    "Knowledge Cutoff Date: April 2024.\n"
    "Today's Date: April 9, 2025.\n"
    "You are Granite, developed by IBM. You are a helpful AI assistant"
)


class GraniteEngine:
    """Runs Granite Speech over a recording and returns timed words.

    Same shape as the other engines - a name and a `transcribe` - so the runner,
    the scorer and the results tables need no changes.

    Both models load on first use and are kept for the whole run; see the note in
    `faster_whisper_engine`, which learned that the expensive way.

    Args:
        settings: Model, device and precision. Whisper's decoding options have no
            counterpart here and are ignored rather than faked.
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

        The model name already says granite, so it is not said twice. Checked
        case-insensitively, the way the other engines learned to.
        """
        model = self.settings.model
        return model if model.lower().startswith("granite") else f"granite-{model}"

    @property
    def _model_id(self) -> str:
        """The Hugging Face repository to load."""
        model = self.settings.model
        return model if "/" in model else f"ibm-granite/{model}"

    def _load(self):
        """Load the model and processor, and the shared aligner, once."""
        if self._model is not None:
            return self._processor, self._model

        import torch  # noqa: PLC0415 - deliberately late, as with the others
        from transformers import (  # noqa: PLC0415
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
        )

        # Before anything is loaded, because the alternative is not an
        # error - see the note on APPROX_VRAM_GB.
        prepare_gpu(
            self.settings.device, APPROX_VRAM_GB, self._model_id,
            bfloat16=self.settings.compute_type != "float32",
        )
        # That also sets the ceiling: past it PyTorch raises instead of letting
        # Windows page GPU memory out to system RAM. See `gpu.prepare_gpu`.

        self._processor = AutoProcessor.from_pretrained(self._model_id)
        self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self._model_id,
            device_map=self.settings.device,
            dtype=_dtype(self.settings.compute_type),
        ).eval()
        self._aligner.load()
        # What it really costs, now that both are on the card.
        log_memory(f"loading {self._model_id} and the aligner")
        return self._processor, self._model

    def settings_used(self) -> dict[str, Any]:
        """What was used, recorded on the result so it can be reproduced.

        The prompt is in here because it changes the output, not because it is
        interesting. Asked the default way this model writes no capitals, and a
        result scored on the strictest rule would be describing the prompt rather
        than the model.
        """
        return {
            "model": self._model_id,
            "aligner": self._aligner.repo_id,
            "aligner_compute_type": self._aligner.compute_type,
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            "language": self.settings.language or "en",
            "prompt": TRANSCRIBE_PROMPT,
            "system_prompt": SYSTEM_PROMPT,
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
            temperature: 0.0 is greedy, which is what this did unconditionally.
                Above zero it samples, which is how `decode_with_fallback`
                breaks a repetition loop. Granite is the model this project
                already knew could loop - see the note on CHUNK_SECONDS, where
                four-minute chunks produced 297 words a minute.
        """
        import torch  # noqa: PLC0415

        processor, model = self._load()
        tokenizer = processor.tokenizer
        prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"<|audio|>{TRANSCRIBE_PROMPT}"},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        wav = torch.tensor(piece).unsqueeze(0)
        inputs = processor(
            prompt, wav, device=self.settings.device, return_tensors="pt"
        ).to(self.settings.device)
        prompt_length = inputs["input_ids"].shape[-1]

        with torch.no_grad():
            produced = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                num_beams=1,
                **sampling_options(temperature),
            )

        # generate() returns the prompt as well; only what followed it is the
        # transcript.
        answer = produced[:, prompt_length:]
        return tokenizer.batch_decode(
            answer, add_special_tokens=False, skip_special_tokens=True
        )[0].strip()

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
                # Checked before alignment: a repeating chunk hands the
                # aligner far more text than it should.
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

        # Hand back the working memory from this case; the models stay loaded.
        # See the fuller note in `voxtral_engine`.
        mark(f"{docket} finished", sample=True)
        release_memory()
        log_memory(f"finishing {docket}")

        return result


def _dtype(compute_type: str):
    """The torch dtype named in the settings.

    Granite is published in bfloat16 and IBM's own example runs it that way, so
    `float16` is read as a request for sixteen bits rather than for that exact
    format.
    """
    import torch  # noqa: PLC0415

    return torch.float32 if compute_type == "float32" else torch.bfloat16


def _clock(seconds: float) -> str:
    """Seconds as `h:mm:ss`, matching the other engines' progress notes."""
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"

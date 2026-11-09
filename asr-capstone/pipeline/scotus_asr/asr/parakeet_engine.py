"""NVIDIA Parakeet, run through transformers.

The second model in the study, and the point of it is comparison: the same audio
and the same official transcript, scored the same three ways, so the only thing
that differs is the model. A leaderboard says Parakeet averages 6.34% and Whisper
large-v3 rather more, but those averages are over short clean clips. Whether that
ordering survives ninety minutes of appellate argument is the question.

No NeMo. NVIDIA's own toolkit is the usual way to run this model and it wants
WSL2 on Windows, which the scoping work flagged as a real obstacle. transformers
5.x ships Parakeet natively, so the model loads with `from_pretrained` like
anything else and the obstacle disappears.

**Long audio has to be chunked, and how it is chunked is a measurement
decision.** Whisper handles a two-hour file by itself; Parakeet does not. Cutting
a recording into ten-minute pieces and transcribing each would lose a word at
every seam, and this project measures dropped words, so that loss would be read
as the model's fault. So the pieces overlap, and a word is taken from the piece
where it sits further from the edge. Nothing is dropped and nothing is doubled.

The chunk settings are recorded on every result, because a result that cannot be
traced back to how it was produced is not evidence.

**Parakeet sometimes stops writing after a full stop, and every blank stretch is
read again because of it** (23 October 2026). Parakeet is a transducer: an
encoder turns the audio into frames, and a small decoder walks through them,
writing a word piece or "blank" at each step while remembering what it has
written. After some full stops that memory leaves it writing blank for every
frame that follows. The encoder still hears the speech, but nothing resets the
decoder until the next decode starts. In a 300-second chunk that meant up to two
and a half minutes of clear speech with no words: 319 minutes over the Supreme
Court runs, 3.4% of the Earnings-22 audio. 98% of those stretches start right
after a word ending in `.` `?` or `!`, against 6% of Parakeet's words overall.

It is the model, not this code. The same thing happens in NVIDIA's own NeMo
toolkit and at float32:
- https://github.com/m2moiz/dekho-suno-jaano/issues/228 - traced to the decoder's
  state after the full stop, on an Earnings-22 call
- https://github.com/superlinked/sie/pull/624 - NeMo 3.0.0 drops the same
  utterances; error grows with chunk length
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/discussions/42 - dropped
  sentences in a clean 120-second clip, in NeMo, unanswered by NVIDIA

Shorter chunks only shorten the stalls, and they cost accuracy elsewhere: 60, 30
and 25 seconds each did worse than 120 on long recordings. The fix, from
https://github.com/m2moiz/dekho-suno-jaano/pull/234, deals with the stall
directly. After decoding, every stretch with no word is decoded again on its own
audio, which starts the decoder fresh (`fill_gaps`). On the worst recording from
each data set it removed every blank stretch over speech, and took Parakeet's
error rate from 7.64% to 5.60% on the Supreme Court and 8.36% to 4.09% on CORAAL.
Measurements and sources: `findings/parakeet-stall/README.md`.

**The "runaways" were a bug in transformers, not the model** (26 October 2026).
A TDT decoder writes a piece and predicts how many frames to move on; zero means
"stay on this frame and write more". NeMo allows at most 10 pieces on one frame
and then moves on one frame. transformers 5.17 does that for the plain RNN-T
model but its TDT version skips the check, so nothing stops it writing on one
frame forever. 18-1323 wrote "that the question is" 127 times on one 80 ms frame;
17-130, one of the September runaways, wrote 1,958 pieces on one frame. Reported
upstream as https://github.com/huggingface/transformers/issues/49388 (fix in PR
#49401, not merged yet). `ParakeetForTDTCapped` below puts NeMo's rule back. On
normal chunks it changes nothing, word for word; on the stuck ones the chunk
comes back clean at full length, with no halving needed.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from ..config import AsrSettings
from ..gpu import log_memory, prepare_gpu, release_memory
from ..store import atomic_write_text
from .base import (
    AsrResult,
    ProgressCallback,
    Segment,
    Word,
    looks_like_a_loop,
    loop_settings,
)

logger = logging.getLogger(__name__)

#: Seconds of audio per pass.
#:
#: Five minutes, down from ten, and the length is only half the story - see
#: MAX_TOKENS_PER_SECOND below for the other half.
#:
#: NVIDIA document about 24 minutes in one go, and ten minutes was chosen as
#: comfortably inside that. Being inside a documented maximum turns out to say
#: nothing at all. At 600 seconds one passage of 16-1144 returns 42,639 words
#: from ten minutes of audio holding about 1,750, taking 260 seconds instead of
#: six, and it reproduces exactly.
#:
#: **Shortening the chunk is not by itself a fix, and it was reported as one.**
#: Three hard passages were probed at 300 seconds, all three came back clean,
#: and that was read as proof. The full run then produced five runaways at 300
#: seconds, the worst 27,937 words from 66 seconds of audio. Three clean probes
#: out of roughly 800 chunks is not evidence of safety. What actually bounds
#: this is the token ceiling.
#:
#: **Not precision either.** The failing window was decoded at float16,
#: bfloat16 and float32 - NVIDIA's config declares float32 while this project
#: forces float16, which looked like the answer - and all three produced the
#: same 42,63x words to within six.
#:
#: 300 stays because it is where the measured word rates sit closest to real
#: argument and it decodes in about six seconds. It is not load-bearing for
#: correctness any more; the ceiling is.
#:
#: **And the long blank stretches were never about the length** (23 Oct 2026).
#: They are the full-stop stall described at the top of this file, which
#: `fill_gaps` deals with. 120, 60, 30 and 25 seconds were all tried on the worst
#: recording from each data set. Shorter chunks shorten the stalls but cost
#: accuracy elsewhere, and 300 seconds with the gaps re-read beat 120 with the
#: gaps re-read on three of the four. Results: `findings/parakeet-stall/`.
CHUNK_SECONDS = 300.0

#: Generation ceiling, in tokens per second of audio.
#:
#: This engine had none, which is why a runaway reached 27,937 words from 66
#: seconds of audio. transformers falls back to a model-agnostic `max_length`
#: - 37,510 for a 300-second chunk - and warns about it on every call.
#:
#: Measured rather than guessed, which matters because a TDT transducer does
#: not count tokens the way a language model does:
#:
#:     16-1144  300s   1,799 tokens   6.00 per second
#:     17-586   300s   1,835 tokens   6.12 per second
#:     16-1215  300s   1,815 tokens   6.05 per second
#:     16-1495  300s  37,510 tokens 125.03 per second   <- ran away
#:     17-130   300s  37,510 tokens 125.03 per second   <- ran away
#:
#: Twelve is twice the fastest real speech seen and a tenth of a runaway. It
#: is a guard rail, not a target: a chunk reaching it is not truncated and
#: kept, it is decoded again.
MAX_TOKENS_PER_SECOND = 12.0

#: How many times a runaway chunk may be halved, and the shortest piece worth
#: halving. Granite Plus needs one level more - see MAX_SPLIT_DEPTH there.
MAX_SPLIT_DEPTH = 2
MIN_SPLIT_SECONDS = 40.0

#: How much neighbouring chunks share. A word straddling a seam appears in both,
#: and the midpoint of the overlap decides which copy is kept. Eight seconds is
#: far longer than any single word, so no word can span the whole overlap.
OVERLAP_SECONDS = 8.0

#: The shortest stretch with no word that is decoded again on its own.
#:
#: Four seconds, as in the fix this is taken from
#: (https://github.com/m2moiz/dekho-suno-jaano/pull/234). It found that two
#: seconds caught a little more at twice the re-reads. A real pause rarely runs
#: four seconds inside speech, and re-reading one that does costs a fraction of a
#: second and writes nothing: on the four test recordings, added words rose by 0
#: to 0.09 points on three and 0.48 on the fourth.
GAP_REREAD_SECONDS = 4.0

#: How many levels of re-read. A re-read can stall after a full stop too, leaving
#: a gap inside the gap; that is read again, and so on, three levels in all, as in
#: the same fix. No test recording needed more.
MAX_REREAD_DEPTH = 3

#: Most word pieces written on one frame before the decoder is moved on a frame.
#:
#: Ten, the checkpoint's own `max_symbols_per_step` and NeMo's default. A frame is
#: 80 ms; no real speech puts more than 3 pieces on one (checked on three normal
#: chunks of 18-1323). Over all 1,044 finished Parakeet transcripts, 22 have a
#: frame with more than ten, every one of them invented text: "a little bit of"
#: 35 times (13-1339), "not going to be able to do that" (EdAcc, CORAAL,
#: Earnings-22). See the note at the top of this file.
MAX_PIECES_PER_FRAME = 10

#: Parakeet is trained on 16 kHz mono.
SAMPLE_RATE = 16_000

#: Video memory needed at the peak, checked before loading. The published run
#: (run-20260924-064733) peaked at 2.6 GB reserved over all 61 arguments;
#: this leaves room for a denser one.
APPROX_VRAM_GB = 3.5


class ParakeetEngine:
    """Runs Parakeet over a recording and returns timed words.

    Same shape as the Whisper engine, so the runner, the scorer and the result
    tables need no changes: an engine is a name and a `transcribe`.

    The model is loaded on first use, not in the constructor, and one engine
    transcribes a whole run - see the note in `faster_whisper_engine`, which
    learned that the expensive way.

    Args:
        settings: Model, device and precision. The decoding options that belong
            to Whisper - beam size, temperature fallback, the silence filter -
            have no counterpart here and are ignored rather than faked.
        partial_path: A default for `transcribe`, for one-off use.
    """

    def __init__(self, settings: AsrSettings, partial_path: Path | None = None) -> None:
        self.settings = settings
        self.partial_path = partial_path
        self._model: Any = None
        #: Chunks where generation hit its ceiling, meaning the model was
        #: repeating rather than transcribing. Counted so a run says how often
        #: it happened instead of leaving it to be found later.
        self.runaway_chunks = 0
        #: Blank stretches decoded again, and the words that brought back. Counted
        #: for the same reason.
        self.gap_rereads = 0
        self.words_restored = 0
        self._processor: Any = None

    @property
    def name(self) -> str:
        """Short identifier, used in filenames and results tables.

        The model name already says parakeet, so it is not said twice. The
        Whisper engine prefixes because its model names - `large-v3` - do not
        say which model they belong to.
        """
        model = self.settings.model
        return model if model.startswith("parakeet") else f"parakeet-{model}"

    @property
    def _model_id(self) -> str:
        """The Hugging Face repository to load."""
        model = self.settings.model
        return model if "/" in model else f"nvidia/{model}"

    def _load(self):
        """Load the model and processor, once."""
        if self._model is not None:
            return self._processor, self._model

        import torch  # noqa: PLC0415 - deliberately late, as with faster-whisper
        from transformers import ParakeetForTDT, ParakeetProcessor  # noqa: PLC0415

        # Before anything is loaded: a usable card, room on it, and a ceiling.
        # See `gpu.prepare_gpu`.
        prepare_gpu(self.settings.device, APPROX_VRAM_GB, self._model_id)

        dtype = torch.float16 if self.settings.compute_type == "float16" else torch.float32
        self._processor = ParakeetProcessor.from_pretrained(self._model_id)
        self._model = (
            capped_tdt_class(ParakeetForTDT).from_pretrained(self._model_id, dtype=dtype)
            .to(self.settings.device)
            .eval()
        )
        log_memory(f"loading {self._model_id}")
        return self._processor, self._model

    def settings_used(self) -> dict[str, Any]:
        """What was used, recorded on the result so it can be reproduced."""
        return {
            "model": self._model_id,
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            "chunk_seconds": CHUNK_SECONDS,
            "overlap_seconds": OVERLAP_SECONDS,
            "sample_rate": SAMPLE_RATE,
            "max_tokens_per_second": MAX_TOKENS_PER_SECOND,
            "max_pieces_per_frame": MAX_PIECES_PER_FRAME,
            "loop_remedy": "split the chunk in halves",
            "max_split_depth": MAX_SPLIT_DEPTH,
            "min_split_seconds": MIN_SPLIT_SECONDS,
            "gap_reread_seconds": GAP_REREAD_SECONDS,
            "max_reread_depth": MAX_REREAD_DEPTH,
            **loop_settings(),
        }


    def _decode_once(self, piece, offset: float):
        """Decode one piece, and say whether generation hit its ceiling.

        Returns `(words, hit_ceiling, text)`. The flag catches a wasteful
        runaway; the text is there so an efficient one - repeating a long
        phrase rather than a short one - can be caught by what it says rather
        than by how much room it used.
        """
        import torch  # noqa: PLC0415

        processor, model = self._load()
        seconds = len(piece) / SAMPLE_RATE
        ceiling = max(64, int(seconds * MAX_TOKENS_PER_SECOND))

        inputs = processor(piece, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        inputs = {
            key: (value.to(self.settings.device).half()
                  if value.dtype.is_floating_point and
                  self.settings.compute_type == "float16"
                  else value.to(self.settings.device))
            for key, value in inputs.items()
        }

        with torch.no_grad():
            produced = model.generate(**inputs, max_new_tokens=ceiling)

        _, stamped = processor.decode(
            produced.sequences, durations=produced.durations,
            skip_special_tokens=True,
        )
        hit_ceiling = produced.sequences.shape[-1] >= ceiling
        text = stamped[0] if stamped else []
        return _to_words(text, offset), hit_ceiling, (
            " ".join(w.text for w in _to_words(text, offset)).strip()
        )

    def _decode_piece(self, piece, offset: float, depth: int = 0):
        """Decode one chunk, halving it if the model runs away.

        A runaway is length-specific rather than passage-specific: the same
        audio that loops at 300 seconds comes back clean at 150. So a chunk
        that hits the ceiling is split and each half decoded on its own, which
        is a real second attempt rather than a truncation. Truncating would
        leave the opening of a loop in the record and call it a transcript.

        Two levels deep at most. Below about forty seconds the pieces are
        short enough that the seam logic starts costing more than the loop.
        """
        words, hit_ceiling, text = self._decode_once(piece, offset)
        seconds = len(piece) / SAMPLE_RATE

        # Two different failures, and the ceiling only sees one of them. A
        # chunk repeating "of the process" runs out of room; a chunk repeating
        # a whole clause does not, and reads as plausible speech while being
        # just as corrupt. 16-1144 chunk 8 came back with 1,000 repeated
        # ten-word runs inside 1,737 words and never touched the ceiling.
        degenerate, why = looks_like_a_loop(text, seconds)
        if not hit_ceiling and not degenerate:
            return words

        reason = "generation hit its ceiling" if hit_ceiling else why

        self.runaway_chunks += 1
        if depth >= MAX_SPLIT_DEPTH or seconds < MIN_SPLIT_SECONDS:
            logger.warning(
                "%.0fs of audio at %.0fs in still looks wrong (%s) and cannot "
                "be split further; keeping what came back. This chunk is not "
                "trustworthy.", seconds, offset, reason,
            )
            return words

        logger.warning(
            "%.0fs of audio at %.0fs in: %s. The model is repeating itself "
            "rather than transcribing; decoding the two halves separately.",
            seconds, offset, reason,
        )
        middle = len(piece) // 2
        first = self._decode_piece(piece[:middle], offset, depth + 1)
        second = self._decode_piece(
            piece[middle:], offset + (middle / SAMPLE_RATE), depth + 1
        )
        return first + second

    def reread_gaps(self, audio, segments: list[Segment], total_seconds: float) -> int:
        """Decode every blank stretch again on its own, and put the words back.

        The remedy for the full-stop stall described at the top of this file.
        It runs on the finished transcript rather than inside each chunk, so a
        stretch that crosses from one chunk into the next is still seen whole.
        It is public because the same pass is applied to transcripts made before
        it existed (`tools/reread_parakeet_gaps.py`). Decoding is repeatable, so
        that gives the same result as transcribing again from the start.

        Args:
            audio: The whole recording, 16 kHz mono, as `load_audio` returns it.
            segments: One per chunk, as `transcribe` builds them. Changed in
                place: restored words go into the segment whose stretch they
                fall in, so the seam clean-up in `scoring/seams.py` still sees
                one segment per chunk.
            total_seconds: Length of the recording.

        Returns:
            How many words were restored.
        """
        def decode(start: float, end: float) -> list[Word]:
            self.gap_rereads += 1
            piece = audio[int(start * SAMPLE_RATE): int(end * SAMPLE_RATE)]
            if len(piece) < SAMPLE_RATE:
                return []
            words = self._decode_piece(piece, start)
            # The first word of a decode has no leading space, and every other
            # word here carries one; without it the text would read "grow.uh".
            return [w if w.text.startswith(" ") else
                    Word(" " + w.text, w.start, w.end, w.probability) for w in words]

        existing = [w for segment in segments for w in segment.words]
        added = fill_gaps(decode, existing, 0.0, total_seconds)
        _place(segments, added)
        self.words_restored += len(added)
        return len(added)

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

        stream_to = partial_path if partial_path is not None else self.partial_path
        processor, model = self._load()
        started = time.monotonic()

        audio = load_audio(audio_path)
        total_seconds = len(audio) / SAMPLE_RATE

        words: list[Word] = []
        segments: list[Segment] = []
        partial_lines: list[str] = []
        step = CHUNK_SECONDS - OVERLAP_SECONDS
        index = 0
        offset = 0.0

        while offset < total_seconds:
            first, last = int(offset * SAMPLE_RATE), int(
                min(offset + CHUNK_SECONDS, total_seconds) * SAMPLE_RATE
            )
            piece = audio[first:last]
            if len(piece) < SAMPLE_RATE:  # under a second left; nothing to decode
                break

            chunk_words = self._decode_piece(piece, offset)

            # The allocator ratchets up a few GB a chunk otherwise, because
            # each chunk decodes a different number of tokens and a block of
            # the wrong size cannot be reused. Voxtral filled a 24 GB card by
            # its third chunk that way and took the machine down with it. These
            # engines are smaller and have not hit the ceiling, but the
            # mechanism is identical and the call costs 69ms. See
            # `gpu.release_memory`.
            release_memory()

            keep_from, keep_until = keep_window(offset, index, total_seconds)
            kept = [w for w in chunk_words if keep_from <= w.start < keep_until]

            if kept:
                segment = Segment(
                    index=index,
                    start=kept[0].start,
                    end=kept[-1].end,
                    text="".join(w.text for w in kept).strip(),
                    words=kept,
                )
                segments.append(segment)
                words.extend(kept)

                if stream_to is not None:
                    partial_lines.append(
                        json.dumps(segment.to_dict(), ensure_ascii=False)
                    )
                    atomic_write_text(stream_to, "\n".join(partial_lines) + "\n")

            if on_progress is not None and total_seconds > 0:
                done = min((offset + CHUNK_SECONDS) / total_seconds, 1.0)
                on_progress(done, f"{_clock(min(offset + CHUNK_SECONDS, total_seconds))}"
                                  f" of {_clock(total_seconds)}")

            index += 1
            offset += step

        # The full-stop stall: see the top of this file.
        restored = self.reread_gaps(audio, segments, total_seconds)
        if restored:
            logger.info("[%s] %d words restored by reading blank stretches again.",
                        docket, restored)

        result = AsrResult(
            docket=docket,
            engine=self.name,
            model=self.settings.model,
            segments=segments,
            audio_seconds=total_seconds,
            runtime_seconds=time.monotonic() - started,
            language=self.settings.language or "en",
            settings=self.settings_used(),
        )

        if stream_to is not None:
            stream_to.unlink(missing_ok=True)

        return result


def frame_step(blank, durations, held, cap: int = MAX_PIECES_PER_FRAME):
    """How far each decode moves on after one step, with the per-frame limit.

    The rule NeMo uses and transformers' TDT decoding leaves out (top of this
    file). A blank always moves on at least one frame. A piece written with a
    duration of zero stays on the frame; after `cap` of those in a row, the
    decoder is moved on one frame anyway.

    Args:
        blank: Per batch item, whether this step wrote a blank (bool tensor).
        durations: The predicted frames to move on (long tensor).
        held: Pieces written in a row on the current frame so far (long tensor).
        cap: The limit.

    Returns:
        `(durations, held)`: the frames to move on, and the new count.
    """
    import torch  # noqa: PLC0415

    durations = torch.where(blank & (durations == 0), torch.ones_like(durations), durations)
    stayed = ~blank & (durations == 0)
    held = torch.where(stayed, held + 1, torch.zeros_like(held))
    forced = held >= cap
    durations = torch.where(forced, torch.ones_like(durations), durations)
    return durations, torch.where(forced, torch.zeros_like(held), held)


def capped_tdt_class(base):
    """transformers' `ParakeetForTDT` with the per-frame limit put back.

    Built from the class passed in, so transformers is still only imported
    when the model is loaded. Replaces the one method that moves the decoder
    along the frames; everything else is transformers' own.
    """
    from transformers import GenerationMixin  # noqa: PLC0415

    class ParakeetForTDTCapped(base):
        def _update_model_kwargs_for_generation(self, outputs, *args, **kwargs):
            # The same steps as transformers' TDT version, with frame_step in
            # place of its blank-only rule.
            model_kwargs = GenerationMixin._update_model_kwargs_for_generation(
                self, outputs, *args, **kwargs)
            logits = outputs.logits[:, -1, :]
            tokens = logits[:, : self.config.vocab_size].argmax(dim=-1)
            durations = logits[:, self.config.vocab_size:].argmax(dim=-1)
            if self._symbols_at_frame is None:   # generate() resets it to None
                self._symbols_at_frame = durations.new_zeros(durations.shape)
            durations, self._symbols_at_frame = frame_step(
                tokens == self.config.blank_token_id, durations, self._symbols_at_frame)
            model_kwargs["encoder_frame_idxs"] = model_kwargs["encoder_frame_idxs"] + durations
            self._step_durations.append(durations)
            self._encoder_finished = (model_kwargs["encoder_frame_idxs"]
                                      >= model_kwargs["encoder_valid_lengths"])
            return model_kwargs

    return ParakeetForTDTCapped


def load_audio(audio_path: Path):
    """The whole recording as 16 kHz mono samples, the way Parakeet was trained."""
    import librosa  # noqa: PLC0415 - deliberately late, as with torch

    audio, _ = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)
    return audio


def fill_gaps(decode, words: list[Word], start: float, end: float,
              depth: int = 0) -> list[Word]:
    """The words found by decoding each blank stretch between start and end again.

    The remedy for the full-stop stall (top of this file). A stretch of
    `GAP_REREAD_SECONDS` or more with no word - including before the first word
    and after the last - is handed to `decode`, which must decode just that
    audio from a fresh start. If what comes back has gaps of its own, they are
    read again, `MAX_REREAD_DEPTH` levels in all.

    A re-read that finds nothing is not read again. The same audio decoded the
    same way gives the same answer, so a second try would only cost time.

    Args:
        decode: `decode(start, end)` returns timed words for that stretch of the
            recording. Taken as an argument so this can be tested without a model.
        words: What is already there, in order.
        start: Where the stretch to check begins, in seconds.
        end: Where it ends.
        depth: How many re-reads deep this already is.

    Returns:
        Only the new words, in order. `words` is not changed.
    """
    edges = [start] + [t for w in words for t in (w.start, w.end)] + [end]
    added: list[Word] = []
    # edges pairs up as (start, first word's start), (a word's end, the next
    # word's start), ..., (last word's end, end): exactly the blank stretches.
    for gap_from, gap_to in zip(edges[::2], edges[1::2]):
        if gap_to - gap_from < GAP_REREAD_SECONDS:
            continue
        found = [w for w in decode(gap_from, gap_to) if gap_from <= w.start < gap_to]
        added += found
        if found and depth + 1 < MAX_REREAD_DEPTH:
            added += fill_gaps(decode, found, gap_from, gap_to, depth + 1)
    return sorted(added, key=lambda w: w.start)


def _place(segments: list[Segment], added: list[Word]) -> None:
    """Put restored words into the segment whose stretch they fall in.

    A word belongs to the last segment that starts at or before it. Segments are
    one per chunk, and keeping it that way matters: the seam clean-up compares
    neighbouring segments' edges. Changes `segments` in place.
    """
    if not added:
        return
    if not segments:
        segments.append(Segment(index=0, start=added[0].start, end=added[-1].end, text=""))
    touched = set()
    for word in added:
        home = 0
        for i, segment in enumerate(segments):
            if segment.start <= word.start:
                home = i
        segments[home].words.append(word)
        touched.add(home)
    for i in touched:
        segment = segments[i]
        segment.words.sort(key=lambda w: w.start)
        segment.start = min(segment.start, segment.words[0].start)
        segment.end = max(segment.end, segment.words[-1].end)
        segment.text = "".join(w.text for w in segment.words).strip()


def keep_window(
    offset: float, index: int, total_seconds: float,
    chunk: float | None = None, overlap: float | None = None,
) -> tuple[float, float]:
    """Which part of one chunk's words to keep, so seams neither lose nor double.

    Neighbouring chunks share `overlap` seconds, so a word near a seam is decoded
    twice. The midpoint of the shared stretch decides: the earlier chunk keeps
    what falls before it, the later chunk keeps what falls after. Every word is
    kept exactly once.

    The two ends of the recording are different. There is no earlier chunk before
    the first and no later chunk after the last, so those edges are not trimmed -
    trimming them would drop real speech, which is the thing this project
    measures.

    Args:
        offset: Where this chunk starts, in seconds from the beginning.
        index: Which chunk this is, counting from zero.
        total_seconds: Length of the whole recording.
        chunk: Seconds of audio per pass.
        overlap: Seconds neighbouring chunks share.

    Returns:
        `(keep_from, keep_until)` in seconds from the start of the recording. A
        word is kept when its start time falls inside that half-open range.
    """
    # Looked up here, not as default arguments: a default is fixed when the
    # module loads, so changing CHUNK_SECONDS afterwards (as a chunk-length test
    # does) would leave this trimming at 300 seconds without saying so.
    chunk = CHUNK_SECONDS if chunk is None else chunk
    overlap = OVERLAP_SECONDS if overlap is None else overlap
    ends_recording = offset + chunk >= total_seconds
    keep_from = offset + (overlap / 2 if index else 0.0)
    keep_until = offset + chunk - (0.0 if ends_recording else overlap / 2)
    return keep_from, keep_until


def _to_words(tokens: list[dict], offset: float) -> list[Word]:
    """Join Parakeet's sub-word pieces into words, shifted to their real time.

    The model emits pieces - `sol` then `d` for "sold" - and a new word is the
    one that starts with a space. Joining them here means the rest of the
    pipeline sees the same shape of word list Whisper produces, so scoring and
    the omitted-span search need no special case.

    Args:
        tokens: `{token, start, end}` entries, timed from the chunk's start.
        offset: Where the chunk begins in the whole recording, in seconds.

    Returns:
        Whole words, in order, timed against the recording.
    """
    words: list[Word] = []
    for piece in tokens:
        text = str(piece.get("token", ""))
        if not text:
            continue
        start = float(piece.get("start", 0.0)) + offset
        end = float(piece.get("end", start)) + offset

        if words and not text.startswith(" "):
            # A continuation of the word being built.
            previous = words[-1]
            words[-1] = Word(
                text=previous.text + text, start=previous.start, end=end,
                probability=None,
            )
        else:
            words.append(Word(text=text, start=start, end=end, probability=None))
    return words


def _clock(seconds: float) -> str:
    """Seconds as `h:mm:ss`, matching the other engine's progress notes."""
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"

"""IBM Granite Speech 4.1 2B Plus, run through transformers.

The seventh model, and the only one here that times its own words *and* says
who is speaking. Everything documented below comes from IBM's model card:
https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus

**It is not a better Granite. It is a differently-shaped one.** The Plus model
shipped alongside the 4.1-2b already in this study - 28 and 29 April 2026 -
from one release. IBM are explicit about the trade, and it is the first thing
to know:

    "Unlike the base mode, the plus model doesn't provide punctuation and
    capitalization."

and they recommend the base model "for applications where accuracy is the
primary concern with support for punctuated, capitalized transcripts".

That has a direct consequence for this project, because it already judged a
model on exactly this ground. `granite-speech-3.3-8b` is not wired up here at
all: it cannot punctuate, and the note in `granite_engine` calls a transcript
it cannot punctuate not a transcript. The same reasoning applies to this
model's *text*, so this engine is deliberately not a seventh competitor on the
verbatim rule. Scored there it would be measuring IBM's design decision, not
the model's hearing.

**So what is it here for.** Two things no other model in the study can do:

*It times its own words.* Qwen3, Canary, Voxtral and the base Granite all
depend on `aligner.py` for their timings, and `tools/archive/aligner_control.py`
measured that the aligner roughly doubles the silence it reports - 2.00x on
Parakeet's own wording. Every silence finding for those four models rests on
that one component. This model does not use it. Its timings come out of the
decoder with the words, so it is an independent check on the thing four
results depend on.

*It marks speaker turns.* `[Speaker 1]:` and `[Speaker 2]:` tags, which is the
only route in this project to measuring speaker attribution - whether a model
puts the right words in the right mouth when a Justice talks over counsel.

**What it is scored on.** The benchmark rule, which deletes punctuation and
case before scoring, so this model is not penalised for a thing IBM removed on
purpose. Its verbatim score is recorded too, and flagged, because leaving it
out would look like hiding it. See `model-usage-notes.md`.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from ..config import AsrSettings
from ..gpu import log_memory, mark, prepare_gpu, release_memory
from ..store import atomic_write_text
from .base import (
    loop_settings,
    AsrResult,
    ProgressCallback,
    Segment,
    Word,
    compression_ratio,
    decode_chunk,
    looks_like_a_loop,
    sampling_options,
    watch_pace,
)
from .parakeet_engine import keep_window

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000

#: Seconds of audio per pass.
#:
#: IBM document far more than this:
#:
#:   "Our evaluations showed that this model works well with audio segments up
#:    to 9 minutes long for ASR and SAA, and up to 3.5 minutes for timestamps."
#:
#: Three and a half minutes is 210 seconds. This engine uses timestamp mode, so
#: 210 is the documented ceiling, and the value here sits well under it.
#:
#: **The documented figure is not taken on trust, and this project has a scar
#: that explains why.** The base Granite 4.1 2B publishes no length limit at
#: all and falls apart between 60 and 80 seconds, repeating one phrase to the
#: end of the chunk. That cost seven hours of machine time and produced an
#: error rate of 12.94% that looked like a finding about IBM and was actually a
#: finding about a setting. The rule written down afterwards, at the top of
#: `model-usage-notes.md`, is that a documented maximum is not a quality
#: threshold.
#:
#: So this number was measured with `tools/chunk_sweep.py` before the run, and
#: measured widely, because the last time this project set a chunk length from
#: three clean probes it was wrong. Parakeet's 600 -> 300 change was called
#: proven on three hard passages and the full run then produced five runaways.
#:
#: 52 probes: the three standard hard spots at 30, 60, 120 and 210 seconds,
#: then ten cases at two offsets each at 120 and 210. The ten include every
#: passage the *base* Granite looped on. Not one probe looped, at any length.
#: Word rates ran 145 to 216 a minute, and real argument runs 145 to 210.
#:
#: The same passages under the base model at 100 seconds: 275 to 353 words a
#: minute, every one a loop. The two models are genuinely different here.
#:
#: 120 rather than 210, though the sweep was clean at both. IBM's figure is
#: "works well ... up to 3.5 minutes", so 210 sits exactly at the edge of what
#: they tested, and this is a measurement that would not announce itself if it
#: went wrong - a quietly truncated chunk reads downstream as speech the model
#: could not hear, which is the thing this project counts. 120 is comfortably
#: inside their tested range and still halves the number of seams against the
#: base engine's 60.
#:
#: Not matched to the base Granite's 60 on purpose. Every engine here gets the
#: longest length it is safe at - Canary 40, Parakeet 300, Qwen3 280 - because
#: extra seams cost accuracy. The base model uses 60 because it breaks above
#: about 70, and this one does not.
CHUNK_SECONDS = 120.0

#: How much neighbouring chunks share, so the midpoint rule cannot lose a word
#: at a seam. Same as every other engine here.
OVERLAP_SECONDS = 8.0

#: Generation ceiling, as tokens per second of audio.
#:
#: IBM pass a flat `max_new_tokens=10000` in timestamp mode for a 60-second
#: clip, which is about 167 tokens a second - generous enough that nothing
#: bounds a runaway. Parakeet taught this project what an unbounded ceiling
#: costs: one chunk returned 42,639 words from ten minutes of audio holding
#: about 1,750.
#:
#: Timestamp mode is expensive per word, because every word carries a `[T:N]`
#: tag, so the budget has to be far larger than the base engine's 640 tokens
#: for 60 seconds. This number is measured, not guessed.
#:
#: Measured on 16-1144 at 2300s, the passage the base Granite looped on: 1,330
#: tokens for 60 seconds of audio, which is 22.2 a second, carrying 186 words
#: and 33 labelled silences. That works out at about 7.15 tokens per word, so
#: the fastest chunk the sweep produced - 216 words a minute, or 3.6 a second -
#: would cost roughly 26 tokens a second.
#:
#: 60 is a little over twice that worst observed case. Wide enough that real
#: speech never reaches it, narrow enough to stop a runaway: the comparable
#: figure on Parakeet was a ceiling of 12 against 6.0 measured, and its
#: runaways ran at 125.
MAX_TOKENS_PER_SECOND = 60.0

#: The prompt, verbatim from IBM's model card, including the `<|audio|>` tag
#: and the worked example inside it. It is copied exactly rather than
#: paraphrased because this project already learned, on the base Granite, that
#: the prompt decides what the model produces: asked IBM's default way it
#: writes no capitals, asked IBM's 4.1 way it punctuates and truecases. Same
#: audio, same weights.
#:
#: Source: https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus
TIMESTAMP_PROMPT = (
    "<|audio|> Timestamps: Transcribe the speech. After each word, add a "
    "timestamp tag showing the end time in centiseconds, e.g. hello [T:45] "
    "world [T:82]"
)

#: The speaker-attribution prompt, also verbatim from the model card. Not used
#: by the main transcription path - it and the timestamp prompt are different
#: modes and cannot be asked at once - but kept here because measuring speaker
#: attribution is one of the two reasons this model is in the study.
SPEAKER_PROMPT = (
    "<|audio|> Speaker attribution: Transcribe and denote who is speaking by "
    "adding [Speaker 1]: and [Speaker 2]: tags before speaker turns."
)

#: IBM's system prompt, verbatim from the Plus model card, date included.
#:
#: The date is theirs, not today's. The model was tuned with this string in
#: place and this project is not in the business of finding out what changes
#: when it is altered. It differs from the base engine's copy, which carries
#: the date printed on the base card - each engine uses the string its own
#: card publishes.
SYSTEM_PROMPT = (
    "Knowledge Cutoff Date: April 2024.\n"
    "Today's Date: December 19, 2024.\n"
    "You are Granite, developed by IBM. You are a helpful AI assistant"
)

#: How many times a looping chunk may be halved before we give up on it.
#:
#: 120 -> 60 -> 30 -> 15. Three is one more level than Parakeet allows, and the
#: extra level is there because it was needed: of the two chunks this was built
#: for, one came back clean at 60 seconds and the other only at 30.
MAX_SPLIT_DEPTH = 3

#: The shortest piece worth splitting further, in seconds.
#:
#: Below about twenty seconds the seam logic starts costing more than the loop
#: does, and a piece that still repeats itself at fifteen seconds is not going
#: to be rescued by making it shorter.
MIN_SPLIT_SECONDS = 20.0

#: Roughly what this engine wants on the card, in gigabytes, checked before
#: anything loads.
#:
#: 2.3 billion parameters at two bytes each is about 4.6 GB, and unlike every
#: other engine here except Parakeet there is no aligner to load beside it -
#: this model times its own words - so it wants about 1.2 GB less than the base
#: Granite. The rest is working room. The real figure is logged straight after
#: loading so this estimate can be corrected from a run.
APPROX_VRAM_GB = 7.0

#: Splits IBM's output into alternating words and timestamp values.
#:
#: Taken from the model card's own parsing example, which uses exactly this
#: pattern. The capture group is what makes the split alternate text, number,
#: text, number, so `[::2]` is the words and `[1::2]` their end times.
TIMESTAMP_SPLIT = re.compile(r"\[T:(\d+)\]")

#: IBM transcribe a silence as a bare underscore with its own timestamp tag:
#: "Silences are transcribed as `_` and a timestamp tag also indicates their
#: end." These are not words and must not enter the transcript, but their
#: timing is kept - it is what pushes the next word's start later, which is how
#: a pause shows up in the timeline. For a project whose subject is what models
#: leave out, a model that labels its own silences is worth having.
SILENCE_TOKEN = "_"


def parse_timestamps(text: str, offset: float) -> tuple[list[Word], str]:
    """Turn IBM's tagged text into timed words.

    The tags are centiseconds *modulo 1000*, so they roll over every ten
    seconds and have to be unwrapped. IBM state the arithmetic on the model
    card:

        "The conversion from time t in seconds to timestamp is
         N = round(t*100) mod 1000. To convert back to seconds, use
         t = N/100 + 10R where R is the rollover counter."

    and their example recovers R by walking forward and adding ten seconds
    whenever the next time would otherwise go backwards. That is the loop
    below, kept deliberately close to theirs.

    **One deviation, and it is unavoidable.** IBM emit only the *end* of each
    word. `Word` needs a start as well, so each word starts where the previous
    one ended. That is exact for continuous speech, and it is why the silence
    tokens matter: an unspoken gap carries its own end time, so the word after
    it starts on the far side of the gap rather than absorbing it. Without
    that, every pause would be swallowed into the following word and this
    model's silence figures would be worthless - which is the one measurement
    it was brought in to make.

    Args:
        text: What the model returned, tags and all.
        offset: Where this chunk starts in the recording, in seconds.

    Returns:
        `(words, plain_text)` - the timed words with the silences removed, and
        the transcript with every tag stripped, which is what the scorer wants.
    """
    parts = TIMESTAMP_SPLIT.split(text)
    words: list[Word] = []
    spoken: list[str] = []

    last_end = 0.0
    rollovers = 0.0
    # A word cannot start before its chunk does, and the first word has no
    # previous end to take, so it takes the chunk's own beginning.
    previous_end = 0.0

    for token, stamp in zip(parts[::2], parts[1::2]):
        end = float(stamp) / 100.0
        # Unwrap the modulo-1000 rollover: time only moves forward, so a stamp
        # landing before the last one has wrapped past ten seconds.
        while end + rollovers < last_end:
            rollovers += 10.0
        last_end = end + rollovers

        token = token.strip()
        if not token or token == SILENCE_TOKEN:
            # A labelled silence. It writes no word, but it moves the clock, so
            # the next word starts on the far side of the pause.
            previous_end = last_end
            continue

        words.append(
            Word(
                # Leading space, matching what the aligner and the other
                # engines produce, so the scorer sees one shape of word list.
                text=f" {token}",
                start=previous_end + offset,
                end=last_end + offset,
                probability=None,
            )
        )
        spoken.append(token)
        previous_end = last_end

    return words, " ".join(spoken)


def strip_timestamps(text: str) -> str:
    """The transcript with every `[T:N]` tag and silence marker removed.

    Needed because the loop checks in `base.py` judge text by how fast it reads
    and how well it compresses. Tagged text fails both on its own merits - the
    tags repeat by construction and inflate the word count - so a perfectly
    clean chunk would be re-decoded again and again as a false alarm. That is
    the same mistake `chunk_sweep` made once by applying the word-rate test to
    20-second probes, and it is cheap to avoid.
    """
    plain = TIMESTAMP_SPLIT.sub(" ", text)
    kept = [w for w in plain.split() if w != SILENCE_TOKEN]
    return " ".join(kept)


class GranitePlusEngine:
    """Runs Granite Speech 4.1 2B Plus over a recording and returns timed words.

    Same shape as the other engines - a name and a `transcribe` - so the runner,
    the scorer and the results tables need no changes.

    The model loads on first use and is kept for the whole run. Unlike the other
    non-Parakeet engines it loads nothing else: no forced aligner, because this
    model times its own words.

    Args:
        settings: Model, device and precision. Whisper's decoding options have
            no counterpart here and are ignored rather than faked.
        partial_path: A default for `transcribe`, for one-off use.
    """

    def __init__(self, settings: AsrSettings, partial_path: Path | None = None) -> None:
        self.settings = settings
        self.partial_path = partial_path
        self._model: Any = None
        self._processor: Any = None
        #: Chunks that came back looking like a repetition loop, at any depth.
        self.looping_chunks = 0
        #: Chunks still looping after every split. These are in the results and
        #: are not trustworthy; the count is the honest headline for a run.
        self.unrecovered_chunks = 0

    @property
    def name(self) -> str:
        """Short identifier, used in filenames and results tables.

        The model name already says granite, so it is not said twice, the way
        the base engine learned to.
        """
        model = self.settings.model
        return model if model.lower().startswith("granite") else f"granite-{model}"

    @property
    def _model_id(self) -> str:
        """The Hugging Face repository to load."""
        model = self.settings.model
        return model if "/" in model else f"ibm-granite/{model}"

    def _load(self):
        """Load the model and processor once.

        Classes, dtype and device placement are IBM's, from the model card:

            processor = AutoProcessor.from_pretrained(MODEL_NAME)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                MODEL_NAME, device_map=device, dtype=torch.bfloat16)
            model.eval()

        Granite Speech needs transformers 5.8 or newer, which IBM state on the
        card. This project runs 5.17.
        """
        if self._model is not None:
            return self._processor, self._model

        from transformers import (  # noqa: PLC0415 - deliberately late
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
        )

        # Before anything is loaded, because running short of video memory on
        # Windows is not an error - the driver pages the card out to system RAM
        # and the run simply crawls. See the note on APPROX_VRAM_GB.
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
        log_memory(f"loading {self._model_id}")
        return self._processor, self._model

    def settings_used(self) -> dict[str, Any]:
        """What was used, recorded on the result so it can be reproduced.

        The prompt is in here because it changes the output, not because it is
        interesting - the base Granite writes no capitals when asked IBM's
        default way. `punctuation` records IBM's own statement about this
        model, so a reader of the results table knows its verbatim score is
        measuring a design decision rather than the model's hearing.
        """
        return {
            "model": self._model_id,
            "aligner": None,  # it times its own words
            "device": self.settings.device,
            "compute_type": self.settings.compute_type,
            "language": self.settings.language or "en",
            "prompt": TIMESTAMP_PROMPT,
            "system_prompt": SYSTEM_PROMPT,
            "chunk_seconds": CHUNK_SECONDS,
            "overlap_seconds": OVERLAP_SECONDS,
            "max_tokens_per_second": MAX_TOKENS_PER_SECOND,
            "sample_rate": SAMPLE_RATE,
            # Deliberately not the temperature ladder the other engines use.
            # It was tried on this model and failed six times out of six on
            # both chunks it was needed for - see the note on _decode_piece.
            # A looping chunk is halved instead.
            "loop_remedy": "split the chunk, not raise the temperature",
            "max_split_depth": MAX_SPLIT_DEPTH,
            "min_split_seconds": MIN_SPLIT_SECONDS,
            **loop_settings(),
            "punctuation": (
                "none - IBM state this model omits punctuation and capitalization"
            ),
            "timestamps": "native, from the model",
        }

    def _transcribe_piece(self, piece, temperature: float = 0.0) -> str:
        """Raw tagged text for one chunk, with the prompt trimmed off.

        Generation settings are IBM's - `do_sample=False, num_beams=1`, that is
        greedy with no beam search.

        Args:
            piece: The chunk, as 16 kHz mono samples.
            temperature: 0.0 is greedy, matching the model card, and every
                caller passes 0.0 today. The parameter is kept because
                `chunk_sweep` calls this directly, and because raising it is
                the remedy every *other* engine here uses - it is left
                reachable so the comparison can be made again rather than
                taken on trust. This engine escapes a loop by splitting the
                chunk instead; see `_decode_piece` for why.
        """
        import torch  # noqa: PLC0415

        processor, model = self._load()
        tokenizer = processor.tokenizer

        # IBM's own chat-template call, including their system prompt.
        prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": TIMESTAMP_PROMPT},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        wav = torch.tensor(piece).unsqueeze(0)
        inputs = processor(
            prompt, wav, device=self.settings.device, return_tensors="pt"
        ).to(self.settings.device)
        prompt_length = inputs["input_ids"].shape[-1]

        seconds = len(piece) / SAMPLE_RATE
        ceiling = max(64, int(seconds * MAX_TOKENS_PER_SECOND))

        with torch.no_grad():
            produced = model.generate(
                **inputs,
                max_new_tokens=ceiling,
                num_beams=1,
                **sampling_options(temperature),
            )

        # generate() returns the prompt as well; only what followed it is the
        # transcript.
        answer = produced[:, prompt_length:]
        return tokenizer.batch_decode(
            answer, add_special_tokens=False, skip_special_tokens=True
        )[0].strip()

    def _decode_piece(self, piece, offset: float, depth: int = 0) -> list[Word]:
        """Decode one chunk, halving it if the model starts repeating itself.

        **Why halving rather than a hotter temperature.** Every other engine
        here escapes a repetition loop by decoding again with sampling turned
        on. That was tried first and it does not work for this model. Two
        chunks of 16-285 looped, and both went through all six temperatures
        without once coming back clean - 885 words at 728 a minute, and 817 at
        436, kept as the least repetitive of six bad attempts.

        The reason is visible in the measurements. This loop is not caused by
        unlucky sampling, so re-rolling the dice cannot escape it; it is caused
        by where the window happens to start. The chunk beginning at 2464s
        loops, and the same length of audio beginning five seconds later at
        2469s comes back clean. Splitting moves the boundary. Temperature does
        not.

        Measured at the real chunk boundaries of 16-285:

            start   120s            60s             30s
            2240    570 wpm LOOP    161 wpm ok      158 wpm ok
            2300    172 wpm ok      172 wpm ok      166 wpm ok
            2464    445 wpm LOOP    565 wpm LOOP    142 wpm ok
            2524    171 wpm ok      191 wpm ok      210 wpm ok

        One of those needs a single halving and the other needs two, which is
        why `MAX_SPLIT_DEPTH` is 3 rather than Parakeet's 2.

        A split is a real second attempt, not a truncation. Truncating would
        leave the opening of a loop in the record and call it a transcript.

        Args:
            piece: The chunk, as 16 kHz mono samples.
            offset: Where this piece starts in the recording, in seconds.
            depth: How many times this piece has already been halved.

        Returns:
            Timed words for this piece, from however many decodes it took.
        """
        raw = self._transcribe_piece(piece, 0.0)
        plain = strip_timestamps(raw)
        seconds = len(piece) / SAMPLE_RATE

        degenerate, why = looks_like_a_loop(plain, seconds)
        if not degenerate:
            words, _ = parse_timestamps(raw, offset)
            return words

        self.looping_chunks += 1

        if depth >= MAX_SPLIT_DEPTH or seconds < MIN_SPLIT_SECONDS:
            logger.warning(
                "%.0fs of audio at %.0fs in still looks wrong (%s) and cannot "
                "be split further; keeping what came back. This chunk is not "
                "trustworthy, and its compression_ratio is on the segment so "
                "it can be found again.",
                seconds, offset, why,
            )
            self.unrecovered_chunks += 1
            words, _ = parse_timestamps(raw, offset)
            return words

        logger.warning(
            "%.0fs of audio at %.0fs in: %s. The model is repeating itself "
            "rather than transcribing; decoding the two halves separately.",
            seconds, offset, why,
        )
        middle = len(piece) // 2
        first = self._decode_piece(piece[:middle], offset, depth + 1)
        second = self._decode_piece(
            piece[middle:], offset + (middle / SAMPLE_RATE), depth + 1
        )
        return first + second

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

        # 16 kHz mono, which is what IBM's example feeds it.
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
                # Halving rather than a hotter temperature - see the note on
                # _decode_piece for the measurements behind that choice.
                words = self._decode_piece(piece, offset)
                # Rebuilt from the words rather than kept from the decode,
                # because a split chunk has no single piece of text: it is two
                # or four decodes stitched back together.
                text = " ".join(w.text.strip() for w in words)
                return text, compression_ratio(text), 0.0, words

            text, ratio, temperature, words = decode_chunk(work, docket, index)

            # After every chunk, not just every case. The allocator ratchets up
            # about 4 GB a chunk otherwise and fills the card by the third one -
            # see the measurements in `gpu.release_memory`. 69ms.
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

        # Hand back the working memory from this case; the model stays loaded.
        mark(f"{docket} finished", sample=True)
        release_memory()
        log_memory(f"finishing {docket}")

        return result


def _dtype(compute_type: str):
    """The torch dtype named in the settings.

    IBM publish this model in bfloat16 and their own example runs it that way,
    so `float16` is read as a request for sixteen bits rather than for that
    exact format - the same reading the base Granite engine takes.
    """
    import torch  # noqa: PLC0415

    return torch.float32 if compute_type == "float32" else torch.bfloat16


def _clock(seconds: float) -> str:
    """Seconds as `h:mm:ss`, matching the other engines' progress notes."""
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"

"""What every speech recognition model has to look like from the outside.

Models differ enormously inside - Whisper decodes thirty seconds at a time, other
models take the whole recording - but the study only cares about two things: the
words, and when each one was said. Everything below pins down that shape so a new
model can be added without touching the scoring code.

Word timings are not optional here. The headline finding this project is after is
how much audio a system silently skips, and "forty seconds went missing starting
at 1:12:30" needs times, not just text.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

#: Called during a long transcription with a fraction from 0 to 1 and a note.
ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class Word:
    """One word, and when it was said.

    Attributes:
        text: The word, with whatever punctuation the model attached to it.
        start: Seconds from the beginning of the recording.
        end: Seconds from the beginning.
        probability: The model's confidence, 0 to 1, where it reports one.
    """

    text: str
    start: float
    end: float
    probability: float | None = None


@dataclass
class Segment:
    """A stretch of speech the model decoded as a unit.

    The diagnostic fields are kept because they are how you tell a genuine silence
    from a model that gave up. A segment with a high `no_speech_prob` sitting in
    the middle of continuous argument is a strong hint that speech was dropped
    rather than absent.

    Attributes:
        index: Position in the recording, counting from zero.
        start: Seconds from the beginning.
        end: Seconds from the beginning.
        text: What the model heard.
        words: Individual words with their own timings, when asked for.
        no_speech_prob: How confident the model was that this was silence.
        avg_logprob: Average token confidence. Very low means a poor decode.
        compression_ratio: High values mean repeated text - the signature of the
            model getting stuck in a loop.
        temperature: Which decoding temperature produced this. Anything above
            zero means the first attempt was rejected and retried.
    """

    index: int
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)
    no_speech_prob: float | None = None
    avg_logprob: float | None = None
    compression_ratio: float | None = None
    temperature: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        data = asdict(self)
        data["words"] = [asdict(word) for word in self.words]
        return data


@dataclass
class AsrResult:
    """One model's transcription of one recording.

    Attributes:
        docket: The case.
        engine: Which runner produced this, e.g. `faster-whisper`.
        model: Which weights, e.g. `large-v3`.
        segments: The transcription, in order.
        audio_seconds: Length of the recording as the decoder measured it.
        runtime_seconds: How long transcribing took. Together with
            `audio_seconds` this gives the speed, which matters when estimating
            what 1,150 hours will cost.
        language: Detected or forced language.
        settings: The settings used, saved so a result can be traced back to the
            run that produced it. Two runs differing only in whether silence
            filtering was on are different experiments, and this is what records
            which was which.
    """

    docket: str
    engine: str
    model: str
    segments: list[Segment] = field(default_factory=list)
    audio_seconds: float = 0.0
    runtime_seconds: float = 0.0
    language: str = ""
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """The whole transcription as one string."""
        return " ".join(segment.text.strip() for segment in self.segments).strip()

    @property
    def words(self) -> list[Word]:
        """Every word from every segment, in order."""
        return [word for segment in self.segments for word in segment.words]

    @property
    def word_count(self) -> int:
        """How many words the model produced, counted the same way as the reference."""
        return len(self.text.split())

    @property
    def speed(self) -> float:
        """Audio seconds handled per second of wall-clock time.

        Higher is faster. A value of 10 means a 150-minute argument takes 15
        minutes. Returns 0 when the run was not timed.
        """
        if self.runtime_seconds <= 0:
            return 0.0
        return self.audio_seconds / self.runtime_seconds

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        return {
            "docket": self.docket,
            "engine": self.engine,
            "model": self.model,
            "language": self.language,
            "audio_seconds": round(self.audio_seconds, 3),
            "runtime_seconds": round(self.runtime_seconds, 3),
            "speed_x_realtime": round(self.speed, 2),
            "segment_count": len(self.segments),
            "word_count": self.word_count,
            "settings": self.settings,
            "segments": [segment.to_dict() for segment in self.segments],
        }


@runtime_checkable
class AsrEngine(Protocol):
    """Anything that can turn a recording into an `AsrResult`.

    A Protocol rather than a base class, so an engine only has to have the right
    shape. That keeps a test double to a few lines with nothing imported.
    """

    #: Short name used in filenames and in the results tables.
    name: str

    def transcribe(
        self,
        audio_path: Path,
        docket: str,
        on_progress: ProgressCallback | None = None,
    ) -> AsrResult:
        """Transcribe one recording.

        Args:
            audio_path: The audio file.
            docket: The case, recorded on the result.
            on_progress: Called now and then with how far along it is. Optional,
                because nothing about the transcription depends on it.

        Returns:
            The transcription, with word timings if the engine provides them.
        """
        ...

    def settings_used(self) -> dict[str, Any]:
        """What this engine actually ran with.

        There is one settings file for the whole project and most of it belongs
        to Whisper - beam size, temperature fallback, the silence filter. Nine of
        its thirteen speech-recognition fields mean nothing to the other engines,
        which ignore them rather than faking a use. Meanwhile what those engines
        really do depend on - how long a chunk is, how far chunks overlap, which
        aligner supplies the timings - is not in that file at all.

        So a run's recorded settings described the wrong experiment for two of
        the three engines: present and plausible and untrue. This is the one
        place an engine says what it used, and it feeds both the per-case result
        and the run's own record, so the two cannot drift apart.

        Returns:
            Settings, as plain values that survive YAML and JSON.
        """
        ...


# ---------------------------------------------------------------------------
# Noticing that a run has gone slow, while it is still going.
#
# The chunked engines that use this - Voxtral and both Granites, not yet Qwen3,
# Canary or Parakeet - do the same work the same number of times, so their
# chunks should take about the same time as each other. When one suddenly takes five times as long, the usual reason is
# that the card has run out of room and Windows has started moving GPU memory
# out to system RAM. Nothing raises. The run simply becomes fifty times slower
# and finishes some time next week, or does not finish at all.
#
# That happened on 21 September 2026: chunk two of a recording took eleven
# minutes where chunk one had taken two, and eighteen minutes later the machine
# took a kernel bugcheck. Nothing in the log called the slowdown out, so it was
# only visible afterwards by subtracting two timestamps by hand.
# ---------------------------------------------------------------------------

import logging

from ..gpu import memory_snapshot

_pace_logger = logging.getLogger(__name__)

#: How much slower than usual a chunk has to be before it is worth a warning.
#:
#: Three is high enough that ordinary variation stays quiet - chunks already
#: range from about 50 to 130 seconds depending on how densely people are
#: talking, which is a spread of roughly two and a half - and low enough to
#: catch the real thing, which was five times slower and getting worse.
SLOW_CHUNK_MULTIPLE = 3.0

#: Ignore the first few chunks. The first includes warming up the model, and a
#: single early chunk is too small a sample to have a "usual" to compare to.
PACE_SETTLES_AFTER = 2


def watch_pace(
    docket: str,
    index: int,
    seconds: float,
    history: list[float],
    retried: bool = False,
) -> None:
    """Record how long a chunk took, and complain if it was far too slow.

    Appends to `history` in place, so the caller keeps one list per recording
    and passes it back each time.

    The warning carries the video memory reading with it, because that is the
    question anybody reading the log will ask next. A slow chunk on a card with
    12 GB free is a different problem from a slow chunk on a card with 200 MB
    free, and the two need opposite responses.

    Args:
        docket: The case, for the message.
        index: Which chunk, counting from zero.
        seconds: How long this chunk took, transcription and alignment
            together.
        history: How long the earlier chunks took. Modified in place.
        retried: Whether this chunk was decoded more than once because it came
            back looking like a repetition loop. Such a chunk is slow by
            design - it paid for a wasted attempt first - so it is neither
            warned about nor counted towards the usual. Counting it would
            raise the bar and hide a real slowdown later.
    """
    if retried:
        _pace_logger.info(
            "[%s] Chunk %d took %.0fs, which is expected - it was decoded "
            "more than once to get out of a repetition loop.",
            docket,
            index,
            seconds,
        )
        return

    history.append(seconds)
    if len(history) <= PACE_SETTLES_AFTER:
        return

    earlier = history[1:-1]  # drop the first, which paid for warming up
    if not earlier:
        return
    usual = sum(earlier) / len(earlier)
    if usual <= 0 or seconds < usual * SLOW_CHUNK_MULTIPLE:
        return

    reading = memory_snapshot()
    where = (
        f"{reading.get('free_gb', '?')} GB free of "
        f"{reading.get('total_gb', '?')}, this process holding "
        f"{reading.get('torch_allocated_gb', '?')} GB"
        if reading and "error" not in reading
        else "no GPU reading available"
    )
    _pace_logger.warning(
        "[%s] Chunk %d took %.0fs against a usual %.0fs - %.1f times slower. "
        "GPU: %s. If the card is nearly full, Windows is moving GPU memory out "
        "to system RAM, which is silent and very slow; stop the run and free "
        "the card rather than letting it grind.",
        docket,
        index,
        seconds,
        usual,
        seconds / usual,
        where,
    )


def decode_chunk(work, docket: str, index: int):
    """Do one chunk's work, and give it a second chance if the card is full.

    `work` is a no-argument callable that transcribes the chunk and aligns it.

    Running out of video memory is not normally worth retrying - the second
    attempt fails the same way as the first. It is worth it here because the
    usual cause is not that the chunk is too big for the card. It is that
    blocks of the wrong size are being held from earlier chunks, and clearing
    them costs 69 milliseconds and frees several gigabytes.

    If the second attempt fails too, the chunk really is too big and the error
    is allowed through. The runner records the case as failed and carries on
    with the next one, which is the behaviour that matters: one missing row in
    a table, rather than an unattended run that stops at case three.

    Args:
        work: Transcribes and aligns one chunk. Called once, or twice.
        docket: The case, for the message.
        index: Which chunk, for the message.

    Returns:
        Whatever `work` returns.
    """
    try:
        return work()
    except Exception as error:  # noqa: BLE001 - narrowed immediately below
        if not _is_out_of_memory(error):
            raise
        _pace_logger.warning(
            "[%s] Chunk %d ran out of video memory. Clearing the cache and "
            "trying it once more. %s",
            docket,
            index,
            _memory_note(),
        )

    from ..gpu import release_memory  # noqa: PLC0415 - avoids an import cycle

    release_memory()
    return work()


def _is_out_of_memory(error: BaseException) -> bool:
    """Is this the card being full, rather than a real fault?

    Checked by name and by message rather than by importing torch's error
    class, so this module still imports on the laptop with no GPU, where
    torch may not be installed at all.
    """
    if type(error).__name__ in ("OutOfMemoryError", "CudaOutOfMemoryError"):
        return True
    return "out of memory" in str(error).lower()


def _memory_note() -> str:
    """The card's state, for a message. Never raises."""
    reading = memory_snapshot()
    if not reading or "error" in reading:
        return "No GPU reading available."
    return (
        f"{reading['free_gb']} GB free of {reading['total_gb']}, "
        f"this process holding {reading['torch_allocated_gb']} GB "
        f"with {reading['torch_reserved_gb']} GB reserved."
    )


# ---------------------------------------------------------------------------
# Catching a chunk where the model got stuck, and decoding it again.
#
# Every model here except Whisper decodes greedily and keeps whatever comes
# out. Greedy decoding on an uncertain passage can collapse into repeating a
# phrase until it runs out of room, which is a documented failure of
# autoregressive speech models rather than anything peculiar to this project.
# Voxtral did it on chunk 8 of 16-1161 - people talking over each other - and
# produced "the partisan measure, the partisan measure, the partisan
# measure..." for 1,590 words where the passage holds about 630.
#
# Whisper has handled this since it was published: check each segment, and if
# it looks like a loop, throw it away and decode it again at a higher
# temperature until it stops looking like one. `default.yaml` configures
# exactly that - `temperatures` and `compression_ratio_threshold` - and those
# settings reached faster-whisper and no other engine.
#
# Which means the comparison this project exists to make was not even-handed.
# Whisper was quietly allowed to retry its worst segments and the other engines
# were scored on theirs. This module gives them the same protection.
#
# It also fixes the memory problem that led here. A looping chunk hands the
# aligner two and a half times as much text as a real one, and that is what
# filled the card: 4.94 GB for the looping chunk against 3.35 GB for the same
# audio decoded properly.
# ---------------------------------------------------------------------------

import zlib


#: Words a minute above which a chunk is not speech any more.
#:
#: Measured rather than assumed. Across the finished runs - 61 Qwen3 cases,
#: 61 Parakeet, and the Voxtral cases so far - no clean chunk exceeds 234
#: words a minute, and the medians sit at 170 to 181. `default.yaml` puts real
#: appellate argument at 145 to 210, from 138 hand-checked arguments. The
#: confirmed repetition loop ran at 341.
#:
#: 250 sits clear of the fastest real speech seen and well under the loop.
#: Nobody talks at 250 words a minute for four minutes.
LOOP_WORDS_PER_MINUTE = 250.0

#: Compression ratio above which a chunk is repeating itself.
#:
#: A second net, for a loop that repeats something long enough not to inflate
#: the word rate much.
#:
#: **Not 2.4, and this matters.** 2.4 is Whisper's threshold and it is
#: calibrated for Whisper's 30-second segments. These chunks are 100 to 600
#: seconds, and longer natural prose compresses better simply because there is
#: more of it for the compressor to work with. Scoring the finished runs at
#: 2.4 flagged 71% of Qwen3's segments and 92% of Parakeet's, every one of
#: which reads as ordinary argument. Using it here would re-decode almost
#: every chunk, which is slow and - since the retries sample rather than take
#: the best token - would make good transcripts worse.
#:
#: Measured on this project's own output: clean chunks reach 2.66 for Voxtral,
#: 3.20 for Qwen3 and 3.50 for Parakeet. The loop was 5.62. 4.0 sits between
#: them with room on both sides.
LOOP_COMPRESSION_RATIO = 4.0

#: Shortest chunk the word-rate test may be applied to, in seconds.
#:
#: Found by it going wrong. The last chunk of a recording is whatever is left
#: over - 12 or 14 seconds, often - and over a window that short the speaking
#: rate is dominated by where the words happen to fall rather than by how fast
#: anyone is talking. Two final chunks in the Granite run were flagged at 276
#: and 303 words a minute and both were ordinary argument; their compression
#: ratios were 1.63 and 1.55, nowhere near repetition.
#:
#: The cost of that mistake is worse than a wasted minute. A flagged chunk is
#: re-decoded by sampling, and if every attempt still trips the test the least
#: repetitive one is kept - so a perfectly good greedy decode gets replaced by
#: a sampled one, which is worse on average. A false positive here actively
#: damages the transcript.
#:
#: At 45 seconds a rate of 250 words a minute means 187 words, which no
#: ordinary burst of speech reaches. Below that the compression ratio still
#: applies, and it is the test that correctly stayed quiet on both of them.
MIN_SECONDS_FOR_WORD_RATE = 45.0

#: Words of back-to-back repetition above which a chunk is a loop.
#:
#: A third net, and it catches what the other two are shaped wrong for: a chunk
#: that transcribes real argument for most of its length and then repeats one
#: short phrase. The real speech dilutes both other measures. 16-498 chunk 11
#: holds "there are" 141 words deep, and came back at 238 words a minute with a
#: compression ratio of 3.24 - under both thresholds, so nothing fired, and a
#: quarter of that chunk is not a transcript.
#:
#: **Counting how often a phrase appears does not work.** Measured over 26,161
#: chunks, the count cannot separate the two cases:
#:
#:     16x "a notice to appear"       Qwen3 17-459     genuine - Pereira v.
#:                                                     Sessions is *about*
#:                                                     notices to appear
#:     11x "Court of Military Commission"  Qwen3 16-961    genuine, the subject
#:     14x "is, is, is, is,"          Canary 16-111    a loop
#:
#: What separates them is that a loop is *contiguous*. The genuine term is
#: scattered through the chunk with argument in between; the loop repeats back
#: to back. So this counts the longest stretch that is one short phrase
#: repeating, not how often the phrase occurs.
#:
#: Thirty, with the gap measured rather than assumed. Over those 26,161 chunks,
#: the longest such stretch in a chunk the other two tests call clean is 19
#: words. The five loops they miss run 53, 56, 112, 126 and 263 words. Nothing
#: sits between 19 and 53.
#:
#: It needs no minimum duration, unlike the word rate. Periodicity does not
#: depend on how long the window is, which is why it catches two Canary chunks
#: of 29 and 32 seconds that `MIN_SECONDS_FOR_WORD_RATE` puts out of reach of
#: the rate test entirely.
LOOP_REPEATED_WORDS = 30

#: The longest phrase this looks for repeating, in words.
#:
#: Eight, and the ceiling is the point rather than a limitation. Allowing longer
#: phrases destroys the separation, because counsel and the Court genuinely read
#: things out twice. The highest stretch found in an otherwise-clean chunk, by
#: how long a phrase is allowed:
#:
#:     up to  8 words   19
#:     up to 12 words   25
#:     up to 16 words   33
#:     up to 20 words   50
#:
#: At sixteen it already exceeds the threshold, and at twenty it reaches 50
#: against the shortest real loop at 53. The culprit is quotation: 16-534 reads
#: "any property in which a foreign state has a beneficial interest" aloud
#: twice, which is a 23-word stretch of honest argument.
#:
#: The cost is that a loop repeating a phrase longer than eight words is missed
#: here. It is not missed everywhere - a long repeat compresses well, which is
#: what `LOOP_COMPRESSION_RATIO` is for.
LOOP_MAX_PERIOD = 8

#: Punctuation stripped before comparing two words.
#:
#: "is," and "is" have to match, or a loop that punctuates itself - and Granite
#: writes "uh, uh, uh," - reads as eight different words.
_TRAILING = ".,?!;:\"'"


def longest_repeated_run(text: str) -> tuple[int, int]:
    """The longest stretch that is one short phrase repeating back to back.

    Walks the words looking for a period: a distance `p` such that every word
    equals the one `p` places behind it. "no no no no" has period 1, "of the
    process of the process" has period 3. The stretch is how many words that
    covers, counting the first copy.

    Args:
        text: What the model produced for the chunk.

    Returns:
        `(words, period)` for the longest stretch found, or `(0, 0)`. The period
        is returned so a log line can say what was repeating.
    """
    words = [w.lower().strip(_TRAILING) for w in text.split()]
    total = len(words)
    longest, at_period = 0, 0

    for period in range(1, LOOP_MAX_PERIOD + 1):
        index = period
        while index < total:
            if words[index] != words[index - period]:
                index += 1
                continue
            # A repeat starts here. Walk to the end of it.
            start = index - period
            end = index
            while end < total and words[end] == words[end - period]:
                end += 1
            if end - start > longest:
                longest, at_period = end - start, period
            # Nothing inside this stretch can start a longer one at this
            # period, so carry on past it.
            index = end + 1

    return longest, at_period


def compression_ratio(text: str) -> float:
    """How much the text shrinks when compressed.

    Repeated phrases compress extremely well, so a high value is the
    signature of a model stuck in a loop. Recorded on every segment whether
    or not it triggered anything, because it is the number that says
    afterwards how close a chunk came.

    Returns 0.0 for text too short to say anything about.
    """
    stripped = text.strip()
    if len(stripped) < 50:
        return 0.0
    return len(stripped) / len(zlib.compress(stripped.encode("utf-8")))


def words_per_minute(text: str, seconds: float) -> float:
    """Speaking rate implied by this much text over this much audio."""
    if seconds <= 0:
        return 0.0
    return len(text.split()) / (seconds / 60.0)


def loop_settings() -> dict[str, float | int]:
    """Every threshold the loop check uses, for an engine's settings record.

    Engines used to record only the first two, so a run's config_used.yaml did
    not fully describe the check that decided which chunks were decoded again.
    """
    return {
        "loop_words_per_minute": LOOP_WORDS_PER_MINUTE,
        "loop_compression_ratio": LOOP_COMPRESSION_RATIO,
        "loop_min_seconds_for_word_rate": MIN_SECONDS_FOR_WORD_RATE,
        "loop_repeated_words": LOOP_REPEATED_WORDS,
        "loop_max_period": LOOP_MAX_PERIOD,
    }


#: A chunk at least this long that comes back empty is decoded again.
MIN_SECONDS_TO_EXPECT_WORDS = 20.0


def looks_like_a_loop(text: str, seconds: float) -> tuple[bool, str]:
    """Has the model got stuck repeating itself?

    Three tests, each shaped for a failure the others miss:

    * **Words a minute.** A chunk wasting its budget on "of the process of the
      process" runs far faster than anyone talks. Blind to a loop that repeats
      something long, and unusable on a short window - see
      `MIN_SECONDS_FOR_WORD_RATE`.
    * **Compression ratio.** Catches the long repeat the word rate misses.
      Blind to a chunk that is mostly real argument, because the real speech
      compresses normally and pulls the average down.
    * **Back-to-back repetition.** Catches exactly that case: real argument
      followed by one phrase repeating. This is the test that finds 16-498
      chunk 11, which held "there are" 141 words deep while reading as 238
      words a minute with a ratio of 3.24.

    Args:
        text: What the model produced for the chunk.
        seconds: How much audio the chunk holds.

    Returns:
        Whether it looks degenerate, and a short reason for the log.
    """
    # Only on a window long enough for the rate to mean anything. See
    # MIN_SECONDS_FOR_WORD_RATE.
    if seconds >= MIN_SECONDS_FOR_WORD_RATE:
        rate = words_per_minute(text, seconds)
        if rate > LOOP_WORDS_PER_MINUTE:
            return True, f"{rate:.0f} words a minute, which is not speech"

    ratio = compression_ratio(text)
    if ratio > LOOP_COMPRESSION_RATIO:
        return True, f"compression ratio {ratio:.2f}, so it is repeating itself"

    # No duration test on this one: a stretch of repetition is as telling in
    # thirty seconds as in three hundred.
    repeated, period = longest_repeated_run(text)
    if repeated >= LOOP_REPEATED_WORDS:
        return True, (
            f"{repeated} words of a {period}-word phrase repeating back to back"
        )

    return False, ""


def decode_with_fallback(
    decode,
    seconds: float,
    docket: str,
    index: int,
    temperatures=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
) -> tuple[str, float, float]:
    """Decode one chunk, and try again hotter if it comes back a loop.

    `decode(temperature)` returns the text for this chunk at that temperature.
    Zero means greedy - take the likeliest token every time - which is what
    every engine here did unconditionally before. Above zero the model samples,
    which is worse on average and is the point: a loop is a rut, and sampling
    is what gets out of it.

    Whisper keeps the last attempt when none of them pass. This keeps the
    least repetitive one instead. If every temperature produced a loop then
    the chunk is beyond saving either way, and the least bad version is a more
    defensible thing to score than whichever happened to come last.

    Args:
        decode: Called with a temperature, returns the text.
        seconds: How much audio the chunk holds, for the word rate.
        docket: The case, for the log.
        index: Which chunk, for the log.
        temperatures: Tried in order. The first is normally 0.0.

    Returns:
        `(text, compression_ratio, temperature_used)`. The last two go on the
        segment, so a result carries the evidence for how it was produced.
    """
    attempts: list[tuple[float, str, float]] = []

    for temperature in temperatures:
        text = decode(temperature)
        ratio = compression_ratio(text)
        bad, why = looks_like_a_loop(text, seconds)
        # Nothing at all from a chunk of real length is a failed decode. Silence can do it
        # too, and costs only the retries. Unchecked, the chunk vanished without a trace.
        if not text.strip() and seconds >= MIN_SECONDS_TO_EXPECT_WORDS:
            bad, why = True, "no words at all"
        attempts.append((ratio, text, temperature))

        if not bad:
            if temperature > 0:
                _pace_logger.info(
                    "[%s] Chunk %d came back clean at temperature %.1f.",
                    docket,
                    index,
                    temperature,
                )
            return text, ratio, temperature

        _pace_logger.warning(
            "[%s] Chunk %d at temperature %.1f: %s. Decoding it again.",
            docket,
            index,
            temperature,
            why,
        )

    # Nothing passed. Keep the least repetitive attempt and say so plainly -
    # this chunk is in the results and it is not trustworthy.
    ratio, text, temperature = min(attempts, key=lambda a: a[0])
    _pace_logger.warning(
        "[%s] Chunk %d still looks like a loop after %d attempts. Keeping the "
        "least repetitive one (temperature %.1f, compression ratio %.2f). Its "
        "compression_ratio is on the segment, so it can be found again.",
        docket,
        index,
        len(attempts),
        temperature,
        ratio,
    )
    return text, ratio, temperature


def sampling_options(temperature: float) -> dict:
    """What to pass `generate` for this temperature.

    Zero is greedy, and must say so rather than passing `temperature=0.0` -
    transformers warns about a temperature that will not be used, and on some
    versions divides by it.
    """
    if temperature <= 0:
        return {"do_sample": False}
    return {"do_sample": True, "temperature": float(temperature)}

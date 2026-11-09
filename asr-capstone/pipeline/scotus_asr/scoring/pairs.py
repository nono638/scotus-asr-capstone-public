"""Writing the alignment out word by word, instead of only its totals.

`metrics.py` builds the full alignment and then keeps only `alignment.summary()` -
the counts. That answers "how many words were wrong" and cannot answer "which
ones", which is the question every other measure in the project is built on.
Named entities, disfluency fidelity and the length distribution of dropped runs
all need the pairs, not the totals.

Nothing here re-transcribes anything. Both texts are already on disk after a run,
so this reads them back and re-aligns, which takes about a second per case and
needs no GPU.

One row per alignment chunk rather than per word. jiwer merges consecutive
matching words into a single `equal` chunk, so a row is either a stretch that
agrees or one specific place the two texts diverge. That keeps the file small
enough to open in a spreadsheet while losing nothing.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..asr.base import Word
from ..transcripts.model import Transcript
from .align import Alignment, align_words

#: Columns, in the order they are written.
COLUMNS = [
    "docket", "engine", "normalizer", "kind",
    "reference_text", "asr_text",
    "reference_words", "asr_words",
    "speaker", "page", "line",
    "start_seconds", "start_clock", "confidence",
]


@dataclass(frozen=True)
class WordPair:
    """One stretch where the record and the machine agree, or one difference.

    Attributes:
        docket: Case identifier.
        engine: Which system produced the transcription.
        normalizer: Which way of comparing produced this row.
        kind: equal, substitute, delete or insert. `delete` is a word in the
            official record the machine never produced; `insert` is a word the
            machine produced that nobody said.
        reference_text: The official words, joined by spaces. Empty for `insert`.
        asr_text: The machine's words. Empty for `delete`.
        reference_words, asr_words: How many words on each side.
        speaker: Who was speaking, from the official transcript. An `insert` has
            no reference word to look up, so it borrows the previous one.
        page, line: Where it sits in the transcript PDF, so a finding can be
            checked against the page.
        start_seconds: When the machine put it, for playing the audio back.
            Deletions borrow the time of the next word produced - the machine
            never made a word here, so there is no time of its own.
        start_clock: The same time as `h:mm:ss`.
        confidence: Mean of the model's per-word confidence, where it gave one.
    """

    docket: str
    engine: str
    normalizer: str
    kind: str
    reference_text: str
    asr_text: str
    reference_words: int
    asr_words: int
    speaker: str
    page: int | None
    line: int | None
    start_seconds: float | None
    start_clock: str
    confidence: float | None


def _clock(seconds: float | None) -> str:
    """Seconds as `h:mm:ss`, so a row can be found in an audio player."""
    if seconds is None:
        return ""
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _turn_lookup(transcript: Transcript) -> list[tuple[int, str, int | None, int | None]]:
    """Where each turn starts in the flat word list, with who said it.

    Scoring flattens the transcript with `full_text(include_speakers=False)`,
    which joins the turns with single spaces. So a turn's first word sits at the
    running total of every earlier turn's word count, and a reference word index
    can be walked back to the turn it came from.

    Args:
        transcript: The official record, parsed into turns.

    Returns:
        `(first_word_index, speaker, page, line)` per turn, in order.
    """
    lookup: list[tuple[int, str, int | None, int | None]] = []
    position = 0
    for turn in transcript.turns:
        lookup.append((position, turn.speaker, turn.start_page, turn.start_line))
        # Counted from the text rather than from a stored count, so this cannot
        # drift away from what scoring actually compared.
        position += len(turn.text.split())
    return lookup


def _turn_at(
    lookup: Sequence[tuple[int, str, int | None, int | None]], word_index: int
) -> tuple[str, int | None, int | None]:
    """The turn containing a given reference word.

    Args:
        lookup: Turn starts, from `_turn_lookup`.
        word_index: Position in the flat reference word list.

    Returns:
        `(speaker, page, line)`, or empties if the index is before the first turn.
    """
    for start, speaker, page, line in reversed(lookup):
        if word_index >= start:
            return speaker, page, line
    return "", None, None


def word_pairs(
    transcript: Transcript,
    asr_words: Sequence[Word],
    docket: str,
    engine: str,
    normalizer: str = "verbatim",
    alignment: Alignment | None = None,
) -> list[WordPair]:
    """Re-align one case and return the comparison, chunk by chunk.

    Args:
        transcript: The official record, parsed into turns.
        asr_words: What the machine produced, with timings.
        docket: Case identifier, copied onto every row.
        engine: Which system produced the transcription.
        normalizer: How to compare. `standard` matches published benchmarks;
            `verbatim` scores punctuation and casing as part of the record.
        alignment: A pre-computed alignment, to avoid doing the work twice.

    Returns:
        One entry per chunk, in transcript order.
    """
    reference_words = transcript.full_text(include_speakers=False).split()
    hypothesis_words = [word.text for word in asr_words]

    if alignment is None:
        alignment = align_words(reference_words, hypothesis_words, normalizer=normalizer)

    lookup = _turn_lookup(transcript)
    ref_source = alignment.reference.source_index if alignment.reference else []
    hyp_source = alignment.hypothesis.source_index if alignment.hypothesis else []

    rows: list[WordPair] = []
    last_speaker, last_page, last_line = "", None, None

    for chunk in alignment.chunks:
        ref_positions = [
            ref_source[i]
            for i in range(chunk.ref_start, min(chunk.ref_end, len(ref_source)))
        ]
        hyp_positions = [
            hyp_source[i]
            for i in range(chunk.hyp_start, min(chunk.hyp_end, len(hyp_source)))
        ]
        ref_slice = [reference_words[p] for p in ref_positions]
        hyp_slice = [hypothesis_words[p] for p in hyp_positions]

        if ref_positions:
            last_speaker, last_page, last_line = _turn_at(lookup, ref_positions[0])

        # A deletion has no words of its own, so it takes the time of the next
        # word the machine did produce. That is the point in the audio to listen
        # at to hear what went missing.
        timed = [asr_words[p] for p in hyp_positions]
        if not timed and chunk.hyp_start < len(hyp_source):
            timed = [asr_words[hyp_source[chunk.hyp_start]]]

        start = timed[0].start if timed else None
        known = [w.probability for w in timed if w.probability is not None]

        rows.append(
            WordPair(
                docket=docket,
                engine=engine,
                normalizer=normalizer,
                kind=chunk.kind,
                reference_text=" ".join(ref_slice),
                asr_text=" ".join(word.strip() for word in hyp_slice),
                reference_words=len(ref_slice),
                asr_words=len(hyp_slice),
                speaker=last_speaker,
                page=last_page,
                line=last_line,
                start_seconds=round(start, 2) if start is not None else None,
                start_clock=_clock(start),
                confidence=round(sum(known) / len(known), 4) if known else None,
            )
        )

    return rows


def event_times(
    transcript: Transcript,
    asr_words: Sequence[Word],
    normalizer: str = "verbatim",
    alignment: Alignment | None = None,
) -> list[tuple[Any, float]]:
    """Work out when in the recording each reporter notation falls.

    A notation sits at a position in the transcript, and a silence sits at a
    moment in the audio. Putting them side by side needs one to be expressed in
    the other's terms, and only the machine transcription carries times.

    So the route runs: the notation's place in its turn, to its place in the flat
    word list, through the alignment to the machine's matching word, to that
    word's timestamp. Each step already exists - `_turn_lookup` for the first and
    `source_index` for the third - and this joins them.

    It is an estimate. Where the model's word is itself mistimed the notation
    moves with it, and where the surrounding words were not transcribed at all
    the nearest match may be some way off. Good enough to ask whether a silence
    sits at a laughter break; not good enough to quote to the second.

    Args:
        transcript: The official record, parsed into turns with events.
        asr_words: What the machine produced, with timings.
        normalizer: Which way of comparing to align with.
        alignment: A pre-computed alignment, to avoid doing the work twice.

    Returns:
        `(event, seconds)` for every notation that could be placed, in order.
        Notations the alignment cannot reach are left out rather than guessed at.
    """
    reference_words = transcript.full_text(include_speakers=False).split()
    if alignment is None:
        alignment = align_words(
            reference_words, [w.text for w in asr_words], normalizer=normalizer
        )

    ref_source = alignment.reference.source_index if alignment.reference else []
    hyp_source = alignment.hypothesis.source_index if alignment.hypothesis else []
    if not ref_source or not asr_words:
        return []

    # Flat word index -> the first token that came from it.
    token_of_word: dict[int, int] = {}
    for token, word in enumerate(ref_source):
        token_of_word.setdefault(word, token)

    # Reference token -> when the machine said the word aligned against it,
    # walking the chunks once rather than searching per event.
    #
    # Position inside the chunk matters. A stretch where the two texts agree is
    # one chunk however long it runs, so stamping every token with the chunk's
    # own start time would put the whole of it at the moment the agreement began
    # - and a transcript that matched cleanly would report every notation at zero
    # seconds.
    time_of_token: dict[int, float] = {}
    for chunk in alignment.chunks:
        if chunk.hyp_start >= len(hyp_source):
            continue
        for offset, token in enumerate(
            range(chunk.ref_start, min(chunk.ref_end, len(ref_source)))
        ):
            # Within the chunk the two run in step. A deletion has no machine
            # words of its own, so its tokens take the time of the next word
            # produced - the same rule the omitted-span search uses.
            at = min(chunk.hyp_start + offset, max(chunk.hyp_end - 1, chunk.hyp_start))
            if at < len(hyp_source):
                time_of_token[token] = asr_words[hyp_source[at]].start

    lookup = _turn_lookup(transcript)
    placed: list[tuple[Any, float]] = []

    for index, turn in enumerate(transcript.turns):
        first_word = lookup[index][0] if index < len(lookup) else 0
        for event in turn.events:
            at_word = min(
                first_word + int(getattr(event, "after_word", 0)),
                len(reference_words) - 1,
            )
            token = token_of_word.get(at_word)
            if token is None:
                continue
            # The alignment does not reach every token - a deleted stretch has no
            # machine word against it - so walk forward to the next that it does.
            when = next(
                (time_of_token[t] for t in range(token, len(ref_source))
                 if t in time_of_token),
                None,
            )
            if when is not None:
                placed.append((event, round(float(when), 2)))

    return sorted(placed, key=lambda pair: pair[1])


def write_pairs(rows: Iterable[WordPair], path: Path) -> int:
    """Write the comparison as CSV.

    Args:
        rows: What `word_pairs` produced, for one case or many.
        path: Where to write. Parent directories are created.

    Returns:
        How many rows were written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            record: dict[str, Any] = asdict(row)
            writer.writerow({key: record[key] for key in COLUMNS})
            written += 1
    return written

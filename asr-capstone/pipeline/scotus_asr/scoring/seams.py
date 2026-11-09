"""Removing words that two neighbouring chunks both transcribed.

Every engine here but Whisper is fed the recording in chunks, and neighbouring
chunks deliberately share eight seconds so a word sitting on a boundary is not
lost. `keep_window` in `parakeet_engine` then decides who keeps it: the midpoint
of the shared stretch, earlier chunk before, later chunk after.

**That rule is correct, and it rests on an assumption that is not.** It assumes
both chunks agree about *when* the word was said. They often do not, because each
chunk is timed independently and a model is least accurate at its own edges. In
16-784 the word "which" is placed at 898.20s by chunk 7 and at 900.29s by chunk
8 - the same word, two seconds apart. The boundary sits at 900, so chunk 7 keeps
it for being before and chunk 8 keeps it for being after, and the transcript says
it twice.

Scored, a repeated word is an insertion, so this inflates word error rate. Worse
for a comparison, **it inflates it unevenly.** As a share of all words
transcribed, over the newest run of each engine:

    parakeet-tdt-0.6b-v3          0.001%
    canary-1b-v2                  0.015%
    granite-speech-4.1-2b         0.044%
    granite-speech-4.1-2b-plus    0.840%
    Qwen3-ASR-1.7B-hf             0.879%
    Voxtral-Mini-3B-2507          0.888%

Nearly nine hundred times between the best and the worst. A ranking that puts two
engines a tenth of a point apart is partly measuring this rather than the models.

**Why fix it here rather than in the engines.** The transcription on disk is what
the model actually produced, and that is the evidence - worth keeping exactly as
it is. This runs when a result is read back for scoring, so the correction is
uniform across engines, applies to runs already finished, and needs nothing
re-transcribed. Scoring was built to be re-runnable on its own for this kind of
reason.

**Whisper is deliberately left alone**, and not by name - see `chunk_seconds`
below.

**An exact match misses most of the repeats on the three engines at the top of that
table** (found 7 November 2026). Two decodes of one stretch often differ a little, "crack
house" and "crackhouse", and a single difference hides the whole repeat from an exact
comparison. Qwen's own settings scored better than ours on 11 of 12 test recordings, and the
gap was mostly these. So those three engines, and only those, also get a match that allows
differences. On engines with few repeats such a match mostly finds real speech, someone
echoing a question, so it is not used there; Canary on EdAcc got worse with it. That split
comes from the table above, measured long before this was found.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

from ..asr.base import Segment, Word

#: How far into each chunk to look for the repeat.
#:
#: Chunks share eight seconds, which at 145-210 words a minute is about 20-28
#: words, so thirty covers the shared stretch with a little room. Looking much
#: further would start matching phrases that genuinely recur in an argument.
SEARCH_WORDS = 30

#: The shortest repeated run treated as duplication rather than as speech.
#:
#: Three, and measured rather than picked. Counting two-word repeats adds almost
#: nothing where duplication is common - Qwen3 goes from 0.879% to 0.885% - while
#: adding the most obviously ambiguous cases, "if the" and "the agency", so it
#: buys risk for no gain.
#:
#: The evidence that three is not catching real speech is Parakeet and Canary. A
#: transducer emits times with its tokens and Canary's chunks are only forty
#: seconds, so both have trustworthy boundaries, and at this threshold they
#: duplicate 0.001% and 0.015% of their words. If a three-word rule were firing
#: on genuine repetition it would fire at about the same rate on every engine. It
#: fires five hundred times more often on the engines whose timings are
#: imprecise, which is the artifact and not the speech.
MIN_REPEAT_WORDS = 3

#: The engines that get the match allowing differences: the ones repeating near 0.9% of
#: their words in the table at the top of this file.
ENGINES_WITH_MANY_REPEATS = ("Qwen3-ASR-1.7B-hf", "Voxtral-Mini-3B-2507", "granite-speech-4.1-2b-plus")

#: How far that match looks. A little further than the exact one, since a run with
#: differences in it can be longer.
SIMILAR_SEARCH_WORDS = 40

#: At least this many words must be the same, making up this share of the later chunk's
#: words up to the end of the match. The stricter of two settings tried: the looser one
#: scored 0.01 to 0.02 better on Qwen3 but took out more real speech.
SIMILAR_MIN_WORDS = 5
SIMILAR_MIN_SHARE = 0.7

#: The match must begin this close to the later chunk's start, and end this close to the
#: earlier chunk's end. A repeat at a seam sits right there; a phrase that merely recurs
#: need not.
SIMILAR_EDGE_WORDS = 4

_PUNCTUATION = re.compile(r"[^\w\s']", flags=re.UNICODE)


def _compare(word: str) -> str:
    """A word reduced to what two chunks ought to agree about.

    Case and punctuation come off, because two chunks frequently disagree about
    them even when the word is the same - one ends a sentence where the other
    does not, so "agency." meets "agency". Comparing raw text missed most of
    Qwen3's and Voxtral's duplication for exactly that reason: 0.125% measured
    strictly against 0.879% measured this way.
    """
    return _PUNCTUATION.sub("", unicodedata.normalize("NFKC", word).lower()).strip()


def _repeated_run(earlier: list[Word], later: list[Word]) -> int:
    """How many words the end of one chunk and the start of the next share.

    Compared on the word lists rather than on segment text, because the two do
    not always tokenise the same way - Whisper has 593 segments where they
    disagree, usually over a hyphenated docket number - and a count taken from
    one cannot safely index the other.

    The longest match is taken rather than the first, so a repeat of eight words
    is removed as eight rather than as the three it also contains.
    """
    tail = [_compare(w.text) for w in earlier[-SEARCH_WORDS:]]
    head = [_compare(w.text) for w in later[:SEARCH_WORDS]]
    longest = 0
    for length in range(MIN_REPEAT_WORDS, min(len(tail), len(head)) + 1):
        if tail[-length:] == head[:length]:
            longest = length
    return longest


def _similar_run(earlier: list[Word], later: list[Word]) -> int:
    """How many words at the later chunk's start repeat the earlier chunk's end, differences allowed.

    Comparing the two ends word by word, the way difflib lines up two texts, finds the same
    stretch even with a word changed, added or left out. Counts up to the last word that
    matches, so what comes after it stays.
    """
    tail = [_compare(w.text) for w in earlier[-SIMILAR_SEARCH_WORDS:]]
    head = [_compare(w.text) for w in later[:SIMILAR_SEARCH_WORDS]]
    blocks = difflib.SequenceMatcher(None, tail, head, autojunk=False).get_matching_blocks()
    blocks = [b for b in blocks if b.size]
    if not blocks:
        return 0
    same = sum(b.size for b in blocks)
    last = blocks[-1]
    upto = last.b + last.size
    if (same < SIMILAR_MIN_WORDS or same / upto < SIMILAR_MIN_SHARE
            or blocks[0].b > SIMILAR_EDGE_WORDS or len(tail) - (last.a + last.size) > SIMILAR_EDGE_WORDS):
        return 0
    return upto


def deduplicate_seams(
    segments: list[Segment], chunk_seconds: float | None, engine: str | None = None
) -> tuple[list[Segment], int]:
    """Drop words the later of two neighbouring chunks says a second time.

    **The later chunk's copy is removed, not the earlier chunk's.** Not
    arbitrary: the midpoint rule has already awarded the region before the
    boundary to the earlier chunk, and the duplicate exists precisely because the
    later chunk timed those words as falling *after* the boundary when they did
    not. Removing its copy restores what the rule meant to do.

    Args:
        segments: One case's segments, in order.
        chunk_seconds: The chunk length the run recorded, or None if this engine
            was not chunked by this project. **None means nothing is changed**,
            and that is what excludes Whisper - its segments are utterances
            decided inside faster-whisper, not chunk boundaries this project
            created, so a repeat across one is not the artifact described above
            and may well be speech. The two look quite different: on chunked
            engines a duplicate is typically placed 2.7 to 7.1 seconds away from
            its original, on Whisper 0.00 to 0.06. Correcting a thing we did not
            cause, on a measurement we do not understand, would be worse than
            leaving a known 0.09% residual and saying so.
        engine: The engine's model name. Those in ENGINES_WITH_MANY_REPEATS also get
            the match that allows differences, after the exact one.

    Returns:
        `(segments, words_removed)`. Segments with nothing removed are returned
        unchanged, not rebuilt. `words_removed` is the count, so a caller can
        record how much this changed.
    """
    if chunk_seconds is None or len(segments) < 2:
        return segments, 0

    cleaned: list[Segment] = [segments[0]]
    removed = 0

    for later in segments[1:]:
        earlier = cleaned[-1]

        if not earlier.words or not later.words:
            # No timings to work from. Left alone rather than guessed at.
            cleaned.append(later)
            continue

        shared = _repeated_run(earlier.words, later.words)
        if engine in ENGINES_WITH_MANY_REPEATS:
            shared += _similar_run(earlier.words, later.words[shared:])
        if not shared or shared >= len(later.words):
            # Nothing repeated, or the whole later chunk is a repeat - which
            # would mean something wrong beyond a seam, so it is left for
            # `tools/sanity_check_run.py` to report rather than silently emptied.
            cleaned.append(later)
            continue

        kept = later.words[shared:]
        removed += shared

        cleaned.append(
            Segment(
                index=later.index,
                # Now starts at its first surviving word.
                start=kept[0].start,
                end=later.end,
                # Rebuilt from the words that remain. Words carry a leading
                # space by convention across every engine here, so joining them
                # reproduces the original spacing.
                text="".join(w.text for w in kept).strip(),
                words=kept,
                no_speech_prob=later.no_speech_prob,
                avg_logprob=later.avg_logprob,
                compression_ratio=later.compression_ratio,
                temperature=later.temperature,
            )
        )

    return cleaned, removed

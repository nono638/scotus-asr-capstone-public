"""Tests for removing words two neighbouring chunks both transcribed.

The risk this guards against is not a crash. It is removing a word a speaker
genuinely said, which turns an insertion into a deletion and fixes nothing.
Several of these are about refusing to act.
"""

from __future__ import annotations

from scotus_asr.asr.base import Segment, Word
from scotus_asr.scoring.seams import deduplicate_seams


def words(text: str, start: float, step: float = 0.5) -> list[Word]:
    """A word list with plausible times, one word every `step` seconds."""
    return [
        Word(text=f" {w}", start=start + i * step, end=start + (i + 1) * step)
        for i, w in enumerate(text.split())
    ]


def segment(index: int, text: str, start: float, step: float = 0.5) -> Segment:
    ws = words(text, start, step)
    return Segment(
        index=index, start=ws[0].start, end=ws[-1].end,
        text="".join(w.text for w in ws).strip(), words=ws,
    )


def test_the_later_chunk_loses_its_repeated_opening():
    """The real case from 16-784, in miniature."""
    first = segment(0, "which is a section of the bankruptcy code", 890.0)
    second = segment(1, "which is a section of the bankruptcy code that deals with", 900.0)

    cleaned, removed = deduplicate_seams([first, second], chunk_seconds=120.0)

    assert removed == 8
    assert cleaned[0].text == "which is a section of the bankruptcy code"
    assert cleaned[1].text == "that deals with"


def test_the_kept_segment_starts_at_its_first_surviving_word():
    first = segment(0, "alpha beta gamma", 10.0)
    second = segment(1, "alpha beta gamma delta", 20.0)

    cleaned, _ = deduplicate_seams([first, second], chunk_seconds=60.0)

    assert cleaned[1].words[0].text.strip() == "delta"
    assert cleaned[1].start == cleaned[1].words[0].start


def test_case_and_punctuation_do_not_prevent_a_match():
    """Two chunks often disagree about a full stop or a capital.

    Comparing raw text is what made Qwen3's duplication look like 0.125% when it
    is nearer 0.879%.
    """
    first = segment(0, "about the agency.", 10.0)
    second = segment(1, "About the Agency the rule says", 20.0)

    cleaned, removed = deduplicate_seams([first, second], chunk_seconds=280.0)

    assert removed == 3
    assert cleaned[1].text == "the rule says"


def test_the_longest_repeat_is_removed_not_the_shortest():
    first = segment(0, "one two three four five six", 10.0)
    second = segment(1, "one two three four five six seven", 20.0)

    _, removed = deduplicate_seams([first, second], chunk_seconds=120.0)

    assert removed == 6


def test_a_two_word_repeat_is_left_alone():
    """Below the threshold, because "if the" recurs in real argument."""
    first = segment(0, "it depends if the", 10.0)
    second = segment(1, "if the statute says otherwise", 20.0)

    cleaned, removed = deduplicate_seams([first, second], chunk_seconds=120.0)

    assert removed == 0
    assert cleaned[1].text == "if the statute says otherwise"


def test_nothing_happens_when_the_engine_was_not_chunked_here():
    """Whisper. Its segments are utterances from inside faster-whisper.

    A repeat across one of those is not the artifact this module is about, so it
    is left for the writeup to report rather than silently corrected.
    """
    first = segment(0, "everyone recognizes that", 10.0)
    second = segment(1, "everyone recognizes that the rule applies", 12.0)

    cleaned, removed = deduplicate_seams([first, second], chunk_seconds=None)

    assert removed == 0
    assert cleaned[1].text == "everyone recognizes that the rule applies"


def test_a_wholly_repeated_chunk_is_left_for_the_sanity_check():
    """If everything in the later chunk is a repeat, something worse is wrong.

    Emptying it here would hide that, and an empty segment would read downstream
    as speech no model could hear - which is the thing this project measures.
    """
    first = segment(0, "alpha beta gamma delta", 10.0)
    second = segment(1, "alpha beta gamma delta", 20.0)

    cleaned, removed = deduplicate_seams([first, second], chunk_seconds=120.0)

    assert removed == 0
    assert cleaned[1].text == "alpha beta gamma delta"


def test_unrelated_chunks_are_untouched_and_not_rebuilt():
    """A segment with nothing removed comes back as the same object.

    Rebuilding every segment's text would quietly change what is scored for
    reasons unconnected to seams.
    """
    first = segment(0, "the first thing to say", 10.0)
    second = segment(1, "an entirely different sentence", 20.0)

    cleaned, removed = deduplicate_seams([first, second], chunk_seconds=120.0)

    assert removed == 0
    assert cleaned[0] is first
    assert cleaned[1] is second


def test_three_chunks_in_a_row_each_get_checked():
    """The comparison uses the already-cleaned earlier chunk, not the original."""
    a = segment(0, "aa bb cc dd", 10.0)
    b = segment(1, "aa bb cc dd ee ff gg", 20.0)
    c = segment(2, "ee ff gg hh", 30.0)

    cleaned, removed = deduplicate_seams([a, b, c], chunk_seconds=120.0)

    assert removed == 4 + 3
    assert cleaned[1].text == "ee ff gg"
    assert cleaned[2].text == "hh"


def test_a_segment_without_words_is_skipped():
    plain = Segment(index=0, start=0.0, end=1.0, text="alpha beta gamma", words=[])
    after = segment(1, "alpha beta gamma delta", 20.0)

    cleaned, removed = deduplicate_seams([plain, after], chunk_seconds=120.0)

    assert removed == 0
    assert cleaned[1].text == "alpha beta gamma delta"


QWEN3 = "Qwen3-ASR-1.7B-hf"


def test_a_repeat_with_a_word_changed_is_found_on_an_engine_with_many_repeats():
    """From 09-1403: two decodes of one stretch that differ in their last word."""
    first = segment(0, "how would the plaintiff class prove lost", 270.0)
    second = segment(1, "how would the plaintiff class prove loss causation given", 276.0)

    cleaned, removed = deduplicate_seams([first, second], 280.0, QWEN3)

    assert removed == 6
    assert cleaned[1].text == "loss causation given"


def test_a_repeat_with_a_word_changed_is_left_on_other_engines():
    """Without the engine's name, or on an engine with few repeats, only exact matches count."""
    first = segment(0, "how would the plaintiff class prove lost", 270.0)
    second = segment(1, "how would the plaintiff class prove loss causation given", 276.0)

    for engine in (None, "canary-1b-v2", "parakeet-tdt-0.6b-v3"):
        _, removed = deduplicate_seams([first, second], 280.0, engine)
        assert removed == 0


def test_someone_echoing_a_short_phrase_is_kept():
    """From EdAcc: an answer that repeats the question. Too few words match."""
    first = segment(0, "did you enjoy where you grew up", 158.0)
    second = segment(1, "I do enjoy where I grew up what kind of", 160.0)

    _, removed = deduplicate_seams([first, second], 280.0, QWEN3)

    assert removed == 0


def test_a_phrase_that_recurs_away_from_the_seam_is_kept():
    """The same words, but not at the end of one chunk and the start of the next."""
    first = segment(0, "the law of the land was clear to all of us and then nobody in this room had anything else", 260.0)
    second = segment(1, "well before we go on let me say something first about the law of the land was clear", 276.0)

    _, removed = deduplicate_seams([first, second], 280.0, QWEN3)

    assert removed == 0


def test_a_chunk_that_is_all_repeat_is_still_left_for_the_sanity_check():
    first = segment(0, "one two three four five six seven", 270.0)
    second = segment(1, "one two three four five six", 276.0)

    cleaned, removed = deduplicate_seams([first, second], 280.0, QWEN3)

    assert removed == 0
    assert cleaned[1].text == "one two three four five six"

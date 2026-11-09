"""Tests for the back-to-back repetition check.

The cost of a false positive here is not a wasted minute. A flagged chunk gets
decoded again, and for most engines that means sampling - so a perfectly good
greedy decode can be replaced by a worse sampled one. Several of these tests are
therefore about the check staying quiet, using real phrases from the corpus that
it must not fire on.
"""

from __future__ import annotations

import random

from scotus_asr.asr.base import (
    LOOP_MAX_PERIOD,
    LOOP_REPEATED_WORDS,
    longest_repeated_run,
    looks_like_a_loop,
)

#: Words from the arguments in this corpus, used to build filler that compresses
#: about as well as real speech does.
#:
#: This matters more than it looks. The first version of these tests wrote
#: filler like "the case of the case of", which gzip flattens, so the
#: compression test fired before the one under test and two tests failed for a
#: reason that had nothing to do with the code. Real argument here compresses at
#: about 2.2 to 3.5.
_VOCABULARY = (
    "statute provision congress intended district appeals circuit remand vacate "
    "petitioner respondent counsel justice question record transcript hearing "
    "detention removable offense jurisdiction sovereign immunity arbitration "
    "collective waiver securities covered class action notice appear deficient "
    "concede argument brief holding precedent deference ambiguity plain meaning "
    "canon surplusage legislative history purpose remedial scheme comprehensive "
    "exclusive preempt savings clause tribal trust allotment beneficial interest "
    "execution attachment commercial activity mandamus certiorari interlocutory "
    "stipulation affidavit deposition testimony exhibit indictment arraignment "
    "suppression exclusionary attenuation inevitable discovery"
).split()


def argument(words: int, seed: int = 11) -> str:
    """Filler that stands in for real argument, compressing about as well.

    Seeded, so a failure is always the same failure.
    """
    rng = random.Random(seed)
    return " ".join(rng.choice(_VOCABULARY) for _ in range(words))


def test_a_single_word_repeating_is_found():
    """Granite Plus 16-285 chunk 22 came back like this."""
    words, period = longest_repeated_run("and then " + "no " * 60)

    assert period == 1
    assert words >= 60


def test_a_three_word_phrase_repeating_is_found():
    """Parakeet 16-498 chunk 1: "the case of" over and over."""
    words, period = longest_repeated_run("well " + "the case of " * 20)

    assert period == 3
    assert words >= 60


def test_the_period_two_case_that_slipped_through_everything():
    """The shape of 16-498 chunk 11: mostly real argument, then a loop.

    That chunk came back at 238 words a minute with a compression ratio of 3.24,
    under both older thresholds, with a quarter of it not a transcript. The
    filler here is sized so the ratio stays under 4.0, which is the whole point:
    this test fails if the repetition check is not the one that fires.
    """
    text = argument(420) + " " + "there are " * 20
    caught, why = looks_like_a_loop(text, seconds=120.0)

    assert caught
    assert "repeating back to back" in why, f"fired for the wrong reason: {why}"


def test_punctuation_does_not_hide_a_loop():
    """Granite writes "uh, uh, uh," - eight different words without stripping."""
    words, period = longest_repeated_run("well " + "uh, " * 40)

    assert period == 1
    assert words >= 40


def test_real_argument_is_left_alone():
    """Ordinary appellate prose, with the ordinary amount of repetition."""
    text = (
        "I think the statute is clear on this point and the district court "
        "agreed with that reading, but the court of appeals took a different "
        "view of what Congress intended when it wrote the provision, and that "
        "is the question before this Court today."
    )
    words, _ = longest_repeated_run(text)

    assert words < LOOP_REPEATED_WORDS
    assert looks_like_a_loop(text, seconds=120.0)[0] is False


def test_a_term_of_art_said_many_times_is_not_a_loop():
    """Qwen3 on 17-459 says "a notice to appear" sixteen times, correctly.

    Pereira v. Sessions is about notices to appear. Counting occurrences would
    flag this; counting back-to-back repetition does not, because the phrase is
    scattered through real argument.
    """
    rng = random.Random(3)
    text = " ".join(
        "a notice to appear" if i % 12 == 0 else rng.choice(_VOCABULARY)
        for i in range(220)
    )
    words, _ = longest_repeated_run(text)

    assert words < LOOP_REPEATED_WORDS
    assert looks_like_a_loop(text, seconds=275.0)[0] is False


def test_a_quoted_phrase_said_twice_is_not_a_loop():
    """16-534 reads the statute aloud twice - a 23-word stretch, honestly.

    This is why `LOOP_MAX_PERIOD` is eight rather than sixteen.
    """
    quote = "any property in which a foreign state has a beneficial interest"
    text = f"the section says {quote} and I will read it again {quote} so that is the test"
    words, _ = longest_repeated_run(text)

    assert words < LOOP_REPEATED_WORDS


def test_a_stammer_is_not_a_loop():
    """"the the the" happens in real speech and must stay."""
    text = (
        "so the the the question is whether the statute reaches that conduct "
        "and I I think it does not for the reasons in our brief"
    )
    words, _ = longest_repeated_run(text)

    assert words < LOOP_REPEATED_WORDS


def test_it_needs_no_minimum_duration():
    """Unlike the word rate, which is switched off below 45 seconds.

    Two Canary chunks of 29 and 32 seconds were loops the rate test could never
    see.
    """
    text = "she said " + "is, " * 30
    caught, _ = looks_like_a_loop(text, seconds=31.0)

    assert caught


def test_empty_and_short_text_is_safe():
    assert longest_repeated_run("") == (0, 0)
    assert longest_repeated_run("one") == (0, 0)
    assert looks_like_a_loop("", seconds=120.0)[0] is False


def test_the_period_searched_is_bounded():
    """A phrase longer than LOOP_MAX_PERIOD repeating is not found by this test.

    Deliberate, and documented on the constant: allowing longer phrases makes
    genuine quotation indistinguishable from a loop. The compression ratio is
    the net for those.
    """
    phrase = " ".join(f"word{n}" for n in range(LOOP_MAX_PERIOD + 4))
    words, _ = longest_repeated_run(" ".join([phrase] * 6))

    assert words < LOOP_REPEATED_WORDS

"""Tests for catching a model stuck repeating itself.

Voxtral did this on chunk 8 of 16-1161, a passage where a Justice and counsel
talk over each other. It produced "the partisan measure, the partisan measure,
the partisan measure..." - 1,590 words where the audio holds about 630 - and
the aligner, handed two and a half times the text it should have been, ran the
card out of memory.

Every model in this study except Whisper decoded greedily and kept whatever
came out. Whisper has re-decoded its own bad segments since it was published,
and `default.yaml` configures exactly that. Those settings reached
faster-whisper and no other engine, which means Whisper was quietly allowed to
retry its worst segments while the other four were scored on theirs.

The thresholds are the delicate part and most of these tests are about them.
Too sensitive and every clean chunk gets re-decoded by sampling, which is
slower and worse. Too lax and the loops get through.
"""

from __future__ import annotations

import logging

from scotus_asr.asr.base import (
    LOOP_COMPRESSION_RATIO,
    LOOP_WORDS_PER_MINUTE,
    compression_ratio,
    decode_with_fallback,
    looks_like_a_loop,
    sampling_options,
    words_per_minute,
)

#: A real chunk of argument, taken from this project's own output: the
#: segment with the highest compression ratio in the finished 16-285 run.
#:
#: Deliberately the hardest clean case rather than an easy one, and
#: deliberately real. Two earlier attempts at this fixture were written by
#: repeating one paragraph several times, which is itself repetitive - they
#: scored 9.13 and 12.72 and would have "proved" that ordinary argument
#: trips the detector.
#:
#: 695 words over 261 seconds: 160 words a minute, compression ratio 2.66.
CLEAN_SEGMENT = (
    "representative and say, Representative, please, let's go before the "
    "arbitrator, and you represent all three. Certainly, Your Honor. There "
    "are many instances where the union will take a grievance with respect to "
    "overtime that's not paid to multiple people on the same shift. This "
    "court's decisions with respect to the steelworkers' trilogy all involve "
    "arbitration situations that involve multiple parties. Let's say the "
    "arbitral forum says, the rules of the arbitral forum says you can "
    "proceed individually, and you can proceed collectively, but only if the "
    "class represents more than 50 people. Is that all right under your "
    "theory? That's a rule of the arbitral forum, and the employee takes the "
    "rules of the forum as they find them. So you have a right to act "
    "collectively, but only if there are 51 or more of you. What, no, Your "
    "Honor, what you have an opportunity to do is to try and utilize the "
    "rules that are available in the forum without the employer intervening "
    "through a prohibition that's violative of such a system. No, no, no, the "
    "hypothetical, the chief can protect his own question, the hypothetical "
    "is the contract says you have to have 50. Oh, I understood. I'm sorry, I "
    "misunderstood. Understanding of the question. Well, I misunderstood the "
    "question. I thought we were talking about the arbitral forum itself has "
    "rules as opposed to the arbitration agreement between the arbiters. No, "
    "the arbitral forum has rules, just like the federal rules of civil "
    "procedure. And what you're saying is, well, once you get into federal "
    "court, of course you've got to follow the rules of the forum. And we "
    "have arbitral forums as well. And I'm saying that those rules are "
    "equivalent. The employee takes the rules of the forum as they find them. "
    "What is prohibited here under the National Labor Relations Act is an "
    "agreement by the employer that's imposed that limits the employee's "
    "right to take the rules as they find them. No, no, okay. So it would be "
    "okay if the forum said that. It's not okay if there's an agreement "
    "between the employer and the employee that limits their right to "
    "proceed. So while the employer has, well, and why can the arbitral forum "
    "enforce the rule that says, basically, you cannot act collectively if "
    "it's fewer than 50 people? Because the prohibition in the National Labor "
    "Relations Act in Section 8A1 runs to employer interference, restraint, "
    "or coercion with respect to the rules, with respect to exercise of "
    "rights under Section 7. It doesn't say anything about the forum's "
    "involvement. Well, but most arbitration agreements tell you what the "
    "forum is, whether it's the AAA or something else. So if the employer- "
    "employee agreement says you shall arbitrate this under this particular "
    "arbitration forum, and those rules say we'll do collective arbitration, "
    "but only if you have more than 51 people, because we think it's more "
    "efficient to have a smaller number arbitrate individually. That would be "
    "okay under your position. Yes, Your Honor. And what if the rules of the "
    "arbitral forum say no class arbitration? Your Honor, it would be just as "
    "though in the analogous circumstances Congress said there were to be no "
    "class actions in court. The employee, our position is that the "
    "employee's right to proceed is in the forum under the rules of the "
    "forum. The thing that is prohibited... If that's the rule, you have not "
    "achieved very much. Because instead of having an agreement that says no "
    "class action, no class arbitration, you have an agreement requiring "
    "arbitration before the XYZ Arbitration Association, which has rules that "
    "don't allow class arbitration. Well, the provisions of the National "
    "Labor Relations Act run to prohibitions against employer interference. "
    "Is there any arbitral forum? I know the AAA allows class arbitration. "
    "The National Academy of Arbitrators filed a brief, a meekus brief in "
    "this case, Your Honor, supporting the position that the Board took in "
    "Murphy Oil, and it addresses the circumstances under which in both labor "
    "arbitration and employment arbitration, employees are able to proceed in "
    "joint, collective, representative actions. There's one anomaly here, and "
    "I think you agreed that... "
)

#: How long that segment covers, for the word rate.
CLEAN_SECONDS = 261.0

#: What the failure actually looked like: 1,590 words where the audio held
#: about 630, at a compression ratio of 5.62.
REAL_LOOP = "the partisan measure, " * 300


# ---------------------------------------------------------------------------
# The two measures
# ---------------------------------------------------------------------------


def test_the_loop_that_happened_is_caught():
    """341 words a minute, compression ratio 5.62. Both tests should fire."""
    caught, why = looks_like_a_loop(REAL_LOOP, 280)
    assert caught
    assert "words a minute" in why or "repeating" in why


def test_real_argument_is_left_alone():
    """Four minutes of genuine back-and-forth must not be re-decoded."""
    caught, why = looks_like_a_loop(CLEAN_SEGMENT, CLEAN_SECONDS)
    assert not caught, why


def test_the_compression_threshold_is_not_whispers():
    """2.4 is calibrated for 30-second segments and does not transfer.

    Scoring this project's finished runs at 2.4 flagged 71% of the Qwen3 run
    and 92% of Parakeet's, every one of which reads as ordinary argument -
    longer natural prose compresses better whatever it says. Using 2.4 here
    would re-decode almost every chunk, and since the retries sample rather
    than take the likeliest token, it would make good transcripts worse.

    The measured ceiling for clean chunks in this project is 3.50.
    """
    assert LOOP_COMPRESSION_RATIO > 3.50, "must clear the worst clean chunk seen"
    assert LOOP_COMPRESSION_RATIO < 5.62, "must still catch the loop that happened"


def test_the_word_rate_threshold_sits_between_speech_and_nonsense():
    """Fastest clean chunk measured was 234 wpm; the loop ran at 341."""
    assert LOOP_WORDS_PER_MINUTE > 234
    assert LOOP_WORDS_PER_MINUTE < 341


def test_a_short_chunk_says_nothing_either_way():
    """Too little text to judge, and a ratio on 20 characters is noise."""
    assert compression_ratio("Thank you, counsel.") == 0.0
    caught, _ = looks_like_a_loop("Thank you, counsel.", 280)
    assert not caught


def test_word_rate_needs_a_duration():
    """Never divide by zero in a check that runs on every chunk."""
    assert words_per_minute("some words here", 0) == 0.0


# ---------------------------------------------------------------------------
# The fallback itself
# ---------------------------------------------------------------------------


def test_a_clean_chunk_is_decoded_once():
    """The common path. Sampling is worse on average, so it must not happen
    unless the first attempt actually looks broken."""
    tried = []

    def decode(temperature):
        tried.append(temperature)
        return CLEAN_SEGMENT

    text, ratio, used = decode_with_fallback(
        decode, CLEAN_SECONDS, "16-285", 0
    )

    assert tried == [0.0], "a clean chunk must not be decoded twice"
    assert used == 0.0
    assert ratio > 0


def test_a_looping_chunk_is_decoded_again_hotter(caplog):
    """Greedy decoding is a rut; sampling is what gets out of it."""
    def decode(temperature):
        return REAL_LOOP if temperature == 0.0 else CLEAN_SEGMENT

    with caplog.at_level(logging.INFO):
        text, ratio, used = decode_with_fallback(decode, 280, "16-1161", 8)

    assert used == 0.2, "should stop at the first temperature that works"
    assert "partisan measure, the partisan" not in text
    assert "16-1161" in caplog.text


def test_every_temperature_is_tried_before_giving_up():
    """Stepping up is the whole mechanism."""
    tried = []

    def decode(temperature):
        tried.append(temperature)
        return REAL_LOOP

    decode_with_fallback(decode, 280, "16-1161", 8,
                         temperatures=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))

    assert tried == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def test_when_nothing_works_the_least_repetitive_attempt_is_kept(caplog):
    """Whisper keeps the last attempt; this keeps the best.

    If every temperature loops then the chunk is beyond saving either way,
    and the least bad version is a more defensible thing to score than
    whichever happened to come last.
    """
    outputs = {
        0.0: "the partisan measure, " * 300,   # worst
        0.2: "the partisan measure, " * 200,
        0.4: "the partisan measure, " * 60,    # least repetitive
        0.6: "the partisan measure, " * 250,
    }

    with caplog.at_level(logging.WARNING):
        text, ratio, used = decode_with_fallback(
            lambda t: outputs[t], 280, "16-1161", 8,
            temperatures=(0.0, 0.2, 0.4, 0.6))

    assert used == 0.4
    assert "still looks like a loop" in caplog.text


def test_a_failed_chunk_carries_its_own_evidence(caplog):
    """The compression ratio goes on the segment so a suspect chunk can be
    found again in the results rather than having to be guessed at."""
    with caplog.at_level(logging.WARNING):
        _text, ratio, _used = decode_with_fallback(
            lambda t: REAL_LOOP, 280, "16-1161", 8, temperatures=(0.0, 0.2))

    assert ratio > LOOP_COMPRESSION_RATIO


# ---------------------------------------------------------------------------
# What gets passed to generate
# ---------------------------------------------------------------------------


def test_zero_asks_for_greedy_rather_than_a_zero_temperature():
    """Passing temperature=0.0 makes transformers warn about a setting that
    will not be used, and on some versions divide by it."""
    assert sampling_options(0.0) == {"do_sample": False}
    assert "temperature" not in sampling_options(0.0)


def test_above_zero_turns_sampling_on():
    options = sampling_options(0.4)
    assert options["do_sample"] is True
    assert options["temperature"] == 0.4


# ---------------------------------------------------------------------------
# Short chunks, where the word rate stops meaning anything
# ---------------------------------------------------------------------------


def test_a_short_final_chunk_of_normal_speech_is_not_flagged():
    """The real false positive, from the Granite run.

    The last chunk of a recording is whatever is left over. Over 14 seconds
    the speaking rate is dominated by where the words happen to fall, and two
    such chunks were flagged at 276 and 303 words a minute while being
    ordinary argument.

    This matters more than a wasted minute: a flagged chunk gets re-decoded by
    sampling, and if nothing passes, the least repetitive attempt is kept. So
    a false positive replaces a good greedy decode with a worse sampled one.
    """
    text = (
        "they said, well, yeah, that's the way it is in that industry, and "
        "those people aren't underpaid, so we're going to leave it alone and "
        "let the agency sort out what the rule should look like."
    )
    caught, why = looks_like_a_loop(text, 14.0)
    assert not caught, why


def test_a_short_chunk_that_really_is_repeating_is_still_caught():
    """Dropping the word-rate test below 45s must not disarm the other one."""
    caught, why = looks_like_a_loop("the partisan measure, " * 60, 14.0)
    assert caught
    assert "repeating" in why


def test_the_word_rate_still_applies_to_a_full_chunk():
    """86 of the Granite run's catches were full chunks at 319-329 wpm."""
    caught, why = looks_like_a_loop("word " * 550, 100.0)
    assert caught


def test_an_empty_chunk_tries_the_next_temperature():
    from scotus_asr.asr.base import decode_with_fallback

    answers = {0.0: "", 0.2: "some real words were said here"}
    text, _, temperature = decode_with_fallback(lambda t: answers[t], 60.0, "d", 0, [0.0, 0.2])
    assert text == answers[0.2] and temperature == 0.2


def test_a_short_empty_piece_is_not_retried():
    from scotus_asr.asr.base import decode_with_fallback

    calls = []
    decode_with_fallback(lambda t: calls.append(t) or "", 3.0, "d", 0, [0.0, 0.2])
    assert calls == [0.0]

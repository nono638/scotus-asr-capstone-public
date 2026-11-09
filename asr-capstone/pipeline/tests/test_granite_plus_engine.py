"""Tests for the Granite Plus timestamp parser.

The parser is the part of this engine that can be wrong quietly. A decoding
mistake shows up as nonsense text, which anyone would notice; a rollover
mistake shows up as plausible words carrying wrong times, which would flow
straight into the silence figures this model was brought in to check.

IBM's tags are centiseconds modulo 1000, so they wrap every ten seconds:
https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus
"""

from __future__ import annotations

from scotus_asr.asr.granite_plus_engine import parse_timestamps, strip_timestamps


def test_simple_words_get_their_end_times():
    """The plain case from IBM's own example: hello [T:45] world [T:82]."""
    words, text = parse_timestamps("hello [T:45] world [T:82]", 0.0)

    assert text == "hello world"
    assert [w.text for w in words] == [" hello", " world"]
    assert words[0].end == 0.45
    assert words[1].end == 0.82


def test_a_word_starts_where_the_one_before_it_ended():
    """IBM give only end times, so starts are taken from the previous end."""
    words, _ = parse_timestamps("one [T:100] two [T:250]", 0.0)

    assert words[0].start == 0.0        # nothing before it; the chunk's own start
    assert words[0].end == 1.0
    assert words[1].start == 1.0        # where the previous word ended
    assert words[1].end == 2.5


def test_timestamps_unwrap_past_ten_seconds():
    """A tag that goes backwards has wrapped, and gains ten seconds.

    999 centiseconds is 9.99s. The next tag reads 50, which is not 0.5s - time
    does not run backwards - it is 10.50s.
    """
    words, _ = parse_timestamps("near [T:999] far [T:050]", 0.0)

    assert words[0].end == 9.99
    assert words[1].end == 10.50


def test_it_unwraps_twice_over_a_longer_chunk():
    """Two separate wraps, which any chunk past twenty seconds will produce.

    The counter carries forward rather than resetting, so a tag only gains ten
    seconds when it would otherwise move time backwards. 900 after 100 is a
    normal forward step inside the same ten-second window, not a third wrap.
    """
    words, _ = parse_timestamps(
        "a [T:900] b [T:100] c [T:900] d [T:100]", 0.0
    )

    assert [round(w.end, 2) for w in words] == [9.0, 11.0, 19.0, 21.0]


def test_silence_is_not_a_word_but_does_move_the_clock():
    """IBM transcribe a silence as `_`. It must not enter the transcript.

    This is the behaviour the silence measurement depends on. The word after a
    pause has to start on the far side of it, not absorb it - otherwise every
    gap disappears into the following word and this model reports no silence
    at all.
    """
    words, text = parse_timestamps("spoke [T:100] _ [T:400] again [T:450]", 0.0)

    assert text == "spoke again"
    assert [w.text for w in words] == [" spoke", " again"]
    # the three seconds of silence are a gap between the two words, not part
    # of either of them
    assert words[0].end == 1.0
    assert words[1].start == 4.0
    assert words[1].end == 4.5


def test_the_chunk_offset_is_added_to_every_time():
    """Times come back relative to the recording, not to the chunk."""
    words, _ = parse_timestamps("word [T:200]", 120.0)

    assert words[0].start == 120.0
    assert words[0].end == 120.0 + 2.0


def test_text_with_no_tags_yields_nothing():
    """A chunk where the model ignored the prompt produces no timed words.

    The engine falls back to the untagged text for the transcript in that case
    rather than dropping the chunk, so this returning empty is the signal for
    that path, not a crash.
    """
    words, text = parse_timestamps("just some words with no tags at all", 0.0)

    assert words == []
    assert text == ""


def test_stripping_tags_leaves_the_plain_transcript():
    """What the loop checks are handed.

    Tagged text compresses far better than prose and carries roughly twice the
    tokens, so judging it directly would flag every clean chunk as a loop.
    """
    plain = strip_timestamps("hello [T:45] _ [T:60] world [T:82]")

    assert plain == "hello world"


def test_stripping_copes_with_text_that_has_no_tags():
    plain = strip_timestamps("nothing tagged here")

    assert plain == "nothing tagged here"

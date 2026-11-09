"""Tests for counting the audio a model said nothing about.

This measure exists to compare engines chunked differently, so its edges matter.
A model that starts ninety seconds late or stops two minutes early has lost that
time, and a measure that only looked between words would report neither.
"""

from __future__ import annotations

from dataclasses import dataclass

from scotus_asr.scoring.coverage import find_silences, summarize_coverage


@dataclass
class W:
    """A timed word, the only shape this measure needs."""

    start: float
    end: float


def test_continuous_speech_leaves_no_holes():
    words = [W(0.0, 1.0), W(1.0, 2.0), W(2.0, 3.0)]

    assert find_silences(words, audio_seconds=3.0) == []


def test_a_gap_between_words_is_found():
    silences = find_silences([W(0.0, 1.0), W(10.0, 11.0)], audio_seconds=11.0)

    assert len(silences) == 1
    assert silences[0].start == 1.0
    assert silences[0].end == 10.0
    assert silences[0].seconds == 9.0


def test_a_late_start_counts():
    """A model that begins ninety seconds in has lost ninety seconds."""
    silences = find_silences([W(90.0, 91.0)], audio_seconds=91.0)

    assert len(silences) == 1
    assert silences[0].at_start
    assert silences[0].seconds == 90.0


def test_an_early_finish_counts():
    silences = find_silences([W(0.0, 1.0)], audio_seconds=121.0)

    assert len(silences) == 1
    assert silences[0].at_end
    assert silences[0].seconds == 120.0


def test_nothing_transcribed_means_the_whole_recording_is_a_hole():
    """The worst case has to read as the worst case, not as a clean sheet."""
    silences = find_silences([], audio_seconds=3600.0)

    assert len(silences) == 1
    assert silences[0].seconds == 3600.0
    assert silences[0].at_start and silences[0].at_end


def test_ordinary_speech_rhythm_is_not_a_hole():
    """Quarter-second pauses between words are speech, not silence."""
    words = [W(0.0, 1.0), W(1.25, 2.0), W(2.3, 3.0)]

    assert find_silences(words, audio_seconds=3.0) == []


def test_a_word_nested_inside_another_does_not_invent_a_gap():
    """Word timestamps disagree, so a short word can sit wholly inside a longer
    one. The running position has to be the furthest point reached, not the last
    word's end - otherwise the clock appears to jump backwards and the next real
    word looks like it follows a silence.

    Here the middle word ends at 4.6 while the first reached 5.0. Measuring from
    4.6 would report a 0.6s hole that does not exist.
    """
    words = [W(0.0, 5.0), W(4.5, 4.6), W(5.2, 6.0)]

    assert find_silences(words, audio_seconds=6.0) == []


def test_words_arriving_out_of_order_are_sorted_first():
    silences = find_silences([W(10.0, 11.0), W(0.0, 1.0)], audio_seconds=11.0)

    assert len(silences) == 1
    assert silences[0].start == 1.0


def test_a_gap_exactly_at_the_threshold_is_not_a_silence():
    """The threshold is where speech rhythm stops and a hole starts.

    Two seconds is ordinary - a speaker pausing, or being interrupted. It has to
    be longer than that to count, or the measure fills up with punctuation.
    """
    assert find_silences([W(0.0, 1.0), W(3.0, 4.0)], audio_seconds=4.0) == []

    longer = find_silences([W(0.0, 1.0), W(3.5, 4.0)], audio_seconds=4.0)
    assert len(longer) == 1
    assert longer[0].seconds == 2.5


def test_the_summary_reports_share_and_the_long_ones():
    silences = find_silences(
        [W(0.0, 1.0), W(30.0, 31.0), W(33.0, 34.0)], audio_seconds=100.0
    )
    summary = summarize_coverage(silences, audio_seconds=100.0)

    # 29s to the second word, then 66s after the last. The 2s gap in between
    # sits exactly on the threshold and is speech rhythm, not a hole.
    assert summary["silent_seconds"] == 95.0
    assert summary["silent_share_percent"] == 95.0
    assert summary["silences_over_10s"] == 2
    assert summary["longest_silence_seconds"] == 66.0
    assert summary["silence_at_end_seconds"] == 66.0
    assert summary["silence_at_start_seconds"] == 0.0


def test_a_perfectly_covered_recording_summarises_as_zero():
    summary = summarize_coverage([], audio_seconds=100.0)

    assert summary["silent_seconds"] == 0.0
    assert summary["silent_share_percent"] == 0.0
    assert summary["silences_over_10s"] == 0
    assert summary["longest_silence_seconds"] == 0.0


def test_no_audio_length_does_not_divide_by_zero():
    assert summarize_coverage([], audio_seconds=0.0)["silent_share_percent"] == 0.0

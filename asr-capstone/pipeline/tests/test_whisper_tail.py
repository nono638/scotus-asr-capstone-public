"""A word-timing crash in the last moment of a recording keeps what was decoded."""

import pytest

from scotus_asr.asr.base import Segment
from scotus_asr.asr.faster_whisper_engine import _stop_at_tail_crash


def _crashing_stream(ends):
    """Segments ending at the given times, then the IndexError faster-whisper raises."""
    for index, end in enumerate(ends):
        yield Segment(index=index, start=end - 4.0, end=end, text="words")
    raise IndexError("boolean index did not match indexed array along axis 0")


def _drain(ends, total_seconds):
    segments, settings = [], {}
    for raw in _stop_at_tail_crash(_crashing_stream(ends), segments, total_seconds, settings):
        segments.append(raw)
    return segments, settings


def test_a_crash_half_a_second_from_the_end_keeps_every_segment():
    """22-1008: decoded to 4212.18 s of 4212.7 s, then the crash."""
    segments, settings = _drain([4207.52, 4212.18], 4212.7)
    assert len(segments) == 2
    assert settings["word_timing_crash_ignored_at"] == 4212.18


def test_a_crash_earlier_in_the_recording_is_still_an_error():
    with pytest.raises(IndexError):
        _drain([100.0, 104.0], 4212.7)

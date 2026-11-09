"""Tests for measuring what is in a stretch of audio.

The loudness figure separates two things a speech detector cannot: speech a
microphone barely caught, and speech at normal level that a model simply did not
write down. Only the second is the model's fault.
"""

from __future__ import annotations

import math

import numpy as np

from scotus_asr.scoring.coverage import Silence
from scotus_asr.scoring.speech import judge_silences, level_dbfs


def _tone(seconds: float, amplitude: float, rate: int = 16_000):
    """A steady tone, so its level is predictable."""
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    return amplitude * np.sin(2 * math.pi * 440 * t)


def test_a_louder_signal_reads_louder():
    assert level_dbfs(_tone(1.0, 0.5)) > level_dbfs(_tone(1.0, 0.05))


def test_full_scale_is_near_zero():
    """A sine at full amplitude sits about 3 dB below full scale."""
    assert -4.0 < level_dbfs(_tone(1.0, 1.0)) < -2.0


def test_halving_the_amplitude_costs_about_six_decibels():
    loud, quiet = level_dbfs(_tone(1.0, 0.4)), level_dbfs(_tone(1.0, 0.2))

    assert 5.5 < loud - quiet < 6.5


def test_digital_silence_floors_rather_than_diverging():
    """True silence is minus infinity, which no table wants in a column."""
    assert level_dbfs(np.zeros(16_000)) == -90.0


def test_an_empty_stretch_does_not_divide_by_zero():
    assert level_dbfs(np.array([])) == -90.0


def test_the_twenty_decibel_gap_measured_on_real_audio_is_reproduced():
    """On case 17-965: the recording averaged -18.8 dBFS, a stretch holding
    speech -17.6, one holding none -40.1. Those are far enough apart that a
    simple amplitude ratio distinguishes them."""
    speech_like = level_dbfs(_tone(1.0, 0.15))
    room_tone = level_dbfs(_tone(1.0, 0.015))

    assert speech_like - room_tone > 15.0


def test_a_silence_with_no_speech_regions_reports_none():
    verdicts = judge_silences([Silence(10.0, 20.0)], regions=[])

    assert len(verdicts) == 1
    assert verdicts[0].speech_seconds == 0.0
    assert not verdicts[0].holds_speech


def test_speech_inside_a_silence_is_counted_and_clipped_to_it():
    """A speech region running past the edges contributes only the shared part."""
    verdicts = judge_silences([Silence(10.0, 20.0)], regions=[(5.0, 15.0)])

    assert verdicts[0].speech_seconds == 5.0
    assert verdicts[0].speech_share == 0.5
    assert verdicts[0].holds_speech

"""Tests for asking several models about the same second of audio.

The verdicts decide where a human has to listen, so the ways they can be
generously wrong matter more than the ways they can be strictly wrong. Calling a
stretch "every model missed this" when only one did would send someone to the
audio for nothing; calling it "one model's fault" when the audio is unusable
would blame the wrong thing.
"""

from __future__ import annotations

from scotus_asr.scoring.agreement import (
    ALL_SILENT,
    SOME_SILENT,
    THIS_ENGINE_ONLY,
    compare,
    silent_over,
    summarize,
    verdict_for,
)
from scotus_asr.scoring.coverage import Silence


def test_every_model_silent_means_the_audio_is_the_suspect():
    assert verdict_for(engines_silent=3, engines_asked=3) == ALL_SILENT


def test_one_model_silent_among_several_is_that_model_s_fault():
    assert verdict_for(engines_silent=1, engines_asked=3) == THIS_ENGINE_ONLY


def test_a_split_decision_is_neither():
    assert verdict_for(engines_silent=2, engines_asked=3) == SOME_SILENT


def test_a_lone_model_is_never_evidence_about_the_audio():
    """With nothing to compare against, silence says nothing about the recording.

    Returning ALL_SILENT here would be arithmetically true and badly misleading:
    it would promote one model's failure into a claim about the audio, and send
    someone to listen to a recording that two other models might transcribe
    perfectly.
    """
    assert verdict_for(engines_silent=1, engines_asked=1) == SOME_SILENT


def test_a_brief_overlap_does_not_count_as_agreement():
    """A model quiet for a tenth of a stretch was not silent over it.

    Without this, near-misses accumulate into agreement and every verdict looks
    more certain than the evidence supports.
    """
    theirs = [Silence(10.0, 11.0)]  # one second of a ten-second window

    assert not silent_over(theirs, 10.0, 20.0)
    assert silent_over([Silence(10.0, 18.0)], 10.0, 20.0)


def test_silence_spread_across_several_gaps_still_counts():
    """What matters is how much of the window is empty, not in how many pieces."""
    theirs = [Silence(10.0, 13.0), Silence(14.0, 17.0), Silence(18.0, 19.0)]

    assert silent_over(theirs, 10.0, 20.0)


def test_an_empty_window_is_not_silence():
    assert not silent_over([Silence(0.0, 10.0)], 5.0, 5.0)


def test_three_models_are_judged_against_each_other():
    shared = Silence(100.0, 110.0)
    by_engine = {
        "alpha": [shared, Silence(200.0, 210.0)],   # the second is alpha's alone
        "beta": [Silence(100.0, 110.0)],
        "gamma": [Silence(100.0, 110.0)],
    }

    verdicts = {(v.engine, v.start): v for v in compare(by_engine)}

    assert verdicts[("alpha", 100.0)].verdict == ALL_SILENT
    assert verdicts[("alpha", 100.0)].engines_silent == 3
    assert verdicts[("alpha", 200.0)].verdict == THIS_ENGINE_ONLY
    assert verdicts[("alpha", 200.0)].engines_silent == 1
    assert verdicts[("beta", 100.0)].verdict == ALL_SILENT


def test_a_stretch_two_of_three_missed_is_a_split_decision():
    by_engine = {
        "alpha": [Silence(50.0, 60.0)],
        "beta": [Silence(50.0, 60.0)],
        "gamma": [],
    }

    verdicts = compare(by_engine)

    assert all(v.verdict == SOME_SILENT for v in verdicts)
    assert all(v.engines_silent == 2 for v in verdicts)


def test_speech_is_attached_where_it_is_known():
    by_engine = {"alpha": [Silence(10.0, 20.0)], "beta": [Silence(10.0, 20.0)]}
    heard = {"alpha": {10.0: 8.5}}

    verdicts = {v.engine: v for v in compare(by_engine, speech_by_engine=heard)}

    assert verdicts["alpha"].speech_seconds == 8.5
    assert verdicts["beta"].speech_seconds == 0.0


def test_only_shared_silence_holding_speech_needs_an_ear():
    """Quiet that every model agreed on, and that sounds like nothing, is just
    quiet. It is the ones that sound like speech that are unresolved."""
    by_engine = {"alpha": [Silence(10.0, 20.0)], "beta": [Silence(10.0, 20.0)]}

    with_speech = compare(by_engine, speech_by_engine={"alpha": {10.0: 9.0}})
    assert [v.needs_an_ear for v in with_speech if v.engine == "alpha"] == [True]

    without = compare(by_engine)
    assert not any(v.needs_an_ear for v in without)


def test_a_fragment_of_speech_does_not_send_anyone_to_the_audio():
    """The detector finds a breath at the edge of almost every pause.

    Measured on the real corpus: with the threshold at "more than nothing", 202
    of Whisper's 208 shared silences qualified - every pause in 61 hours. The
    median holds 0.36 seconds. A second is about two words, and takes that list
    to 10.
    """
    by_engine = {"alpha": [Silence(10.0, 20.0)], "beta": [Silence(10.0, 20.0)]}

    fragment = compare(by_engine, speech_by_engine={"alpha": {10.0: 0.4}})
    assert not any(v.needs_an_ear for v in fragment)

    real = compare(by_engine, speech_by_engine={"alpha": {10.0: 1.5}})
    assert any(v.needs_an_ear for v in real)


def test_a_models_own_failures_are_totalled_separately():
    by_engine = {
        "alpha": [Silence(10.0, 20.0), Silence(50.0, 55.0)],
        "beta": [Silence(10.0, 20.0)],
        "gamma": [Silence(10.0, 20.0)],
    }
    heard = {"alpha": {10.0: 9.0, 50.0: 4.0}}

    verdicts = [v for v in compare(by_engine, speech_by_engine=heard)
                if v.engine == "alpha"]
    totals = summarize(verdicts)

    assert totals["silences_judged"] == 2
    assert totals["this_engine_only"] == 1
    assert totals["this_engine_only_speech_seconds"] == 4.0
    assert totals["all_engines_silent"] == 1
    assert totals["needs_an_ear"] == 1

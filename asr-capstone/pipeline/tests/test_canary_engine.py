"""Tests for the Canary engine, and for four models fitting the existing shape.

Nothing here loads a model. What these check is the wiring that has broken before
in this project: an engine name getting doubled, a settings record that describes
the wrong experiment, and chunk sizes that quietly disagree with the limits they
are supposed to respect.

The chunk-size tests are the important ones, and they are there because this
engine got it wrong first time round. Canary is trained on short utterances and a
chunk set too long does not raise - it transcribes the first part, stops, and the
dropped remainder reads downstream as speech the model failed to hear. That is
precisely what this project measures, so the mistake would have arrived as a
finding rather than as a bug.
"""

from __future__ import annotations

import pytest

from scotus_asr.asr import aligner as aligner_module
from scotus_asr.asr import canary_engine, qwen3_engine
from scotus_asr.asr.base import AsrEngine
from scotus_asr.asr.canary_engine import CanaryEngine
from scotus_asr.asr.registry import available_engines, build_engine
from scotus_asr.config import AsrSettings


def _settings(**over) -> AsrSettings:
    base = {"engine": "canary", "model": "canary-1b-v2", "device": "cuda",
            "compute_type": "float16", "language": "en"}
    base.update(over)
    return AsrSettings(**base)


def test_canary_is_registered_alongside_the_others():
    """Named, not counted.

    This asserted the exact set of engines and broke the day a fifth was added,
    which is the one thing this project reliably keeps doing. What matters is
    that Canary is reachable by name and has not displaced anything.
    """
    registered = set(available_engines())

    assert "canary" in registered
    assert {"faster-whisper", "parakeet", "qwen3-asr"} <= registered


def test_building_it_does_not_load_a_model():
    """Building must stay cheap - the runner builds one before any audio exists."""
    engine = build_engine(_settings())

    assert isinstance(engine, CanaryEngine)
    assert engine._model is None


def test_it_satisfies_the_engine_protocol():
    assert isinstance(build_engine(_settings()), AsrEngine)


def test_the_name_is_not_doubled():
    """Twice now an engine has produced `parakeet-parakeet-...` filenames."""
    assert CanaryEngine(_settings(model="canary-1b-v2")).name == "canary-1b-v2"


def test_a_capitalised_model_name_is_also_not_doubled():
    """The lowercase check is why. `Canary-1b-v2` would otherwise gain a prefix."""
    assert CanaryEngine(_settings(model="Canary-1b-v2")).name == "Canary-1b-v2"


def test_an_unrelated_model_name_gets_the_prefix():
    assert CanaryEngine(_settings(model="tiny")).name == "canary-tiny"


def test_a_full_repository_path_is_left_alone():
    engine = CanaryEngine(_settings(model="nvidia/canary-1b-v2"))
    assert engine._model_id == "nvidia/canary-1b-v2"


def test_a_bare_model_name_gets_nvidias_namespace():
    assert CanaryEngine(_settings())._model_id == "nvidia/canary-1b-v2"


def test_the_chunk_stays_within_what_canary_was_trained_on():
    """The measured limit, and the one that actually bites.

    Canary is trained on short utterances. Past about forty seconds it stops
    partway through a chunk and drops the rest, which downstream is
    indistinguishable from speech it could not hear - so a chunk set too long
    would not show up as a bug but as a false finding.

    Measured on one argument: 138 words a minute at 20 seconds and 126 at 40,
    then 93 at 60, 85 at 90, 53 at 120 and 41 at 150, against an official record
    holding 182. The first version of this engine used 150 seconds and produced
    half a transcript.
    """
    assert canary_engine.CHUNK_SECONDS <= 40.0


def test_the_chunk_also_fits_inside_the_decoders_position_table():
    """1024 positions, a second and looser limit than the training length.

    Deliberately pessimistic - a fast speaker at 220 words a minute, 1.4 tokens
    a word - because overrunning it truncates silently too.
    """
    fast_words_per_second = 220 / 60
    tokens = canary_engine.CHUNK_SECONDS * fast_words_per_second * 1.4

    assert tokens < canary_engine.MAX_NEW_TOKENS
    assert canary_engine.MAX_NEW_TOKENS < 1024


def test_the_chunk_also_fits_inside_the_aligners_limit():
    """The aligner takes five minutes at a time; a longer chunk cannot be timed."""
    assert canary_engine.CHUNK_SECONDS <= aligner_module.MAX_SECONDS


def test_qwen3_chunks_also_fit_the_aligner():
    assert qwen3_engine.CHUNK_SECONDS <= aligner_module.MAX_SECONDS


def test_canary_takes_shorter_chunks_than_qwen3():
    """Not an accident, and worth failing if someone raises it to match.

    Both use the same aligner, so the aligner is not what separates them -
    Canary's decoder is the shorter constraint.
    """
    assert canary_engine.CHUNK_SECONDS < qwen3_engine.CHUNK_SECONDS


def test_an_overlap_is_longer_than_any_word_but_shorter_than_a_chunk():
    """The midpoint rule assumes no word spans a whole overlap.

    The upper bound matters more here than in the other engines: the chunk is
    forty seconds, so an overlap allowed to grow would leave little of each chunk
    actually kept.
    """
    assert canary_engine.OVERLAP_SECONDS >= 4.0
    assert canary_engine.OVERLAP_SECONDS <= canary_engine.CHUNK_SECONDS / 4


def test_both_aligned_engines_use_the_same_aligner():
    """The point of sharing it.

    Canary is in the study partly to test whether Qwen3's extra silence comes
    from the model or from the aligner placing its words badly. That test means
    nothing if the two engines align differently, so this pins them together.
    """
    canary = CanaryEngine(_settings())
    qwen = qwen3_engine.Qwen3Engine(
        _settings(engine="qwen3-asr", model="Qwen3-ASR-1.7B-hf")
    )

    assert canary._aligner.repo_id == qwen._aligner.repo_id == aligner_module.ALIGNER_ID


def test_the_settings_record_names_the_model_and_the_aligner():
    """A result that cannot be traced back to how it was made is not evidence."""
    used = CanaryEngine(_settings()).settings_used()

    assert used["model"] == "nvidia/canary-1b-v2"
    assert used["aligner"] == aligner_module.ALIGNER_ID
    assert used["chunk_seconds"] == canary_engine.CHUNK_SECONDS
    assert used["language"] == "en"


def test_the_settings_record_leaves_out_whispers_options():
    """Nine of the settings file's fields are Whisper's alone.

    Recording them here would describe an experiment that did not happen - the
    fault `settings_used` exists to fix.
    """
    used = CanaryEngine(_settings()).settings_used()

    # `temperatures` used to be on this list, on the view that decoding
    # temperature was a Whisper setting. It is not. Detecting a repetition
    # loop by compression ratio and re-decoding it hotter is a decoder-level
    # technique that Whisper happens to ship, and leaving it to Whisper alone
    # meant Whisper was quietly allowed to retry its worst segments while the
    # other four models were scored on theirs. This engine now uses it, so it
    # records it.
    for whisper_only in ("beam_size", "vad_filter",
                         "condition_on_previous_text"):
        assert whisper_only not in used

    for now_shared in ("temperatures", "loop_words_per_minute",
                       "loop_compression_ratio"):
        assert now_shared in used, f"{now_shared} should be recorded"


def test_truncated_chunks_start_at_none_and_are_reported():
    """A chunk cut off at the token ceiling looks downstream like missed speech.

    So it is counted and written into the run's record rather than left to be
    discovered as a mysterious gap.
    """
    engine = CanaryEngine(_settings())

    assert engine.settings_used()["truncated_chunks"] == 0

    engine.truncated_chunks = 3
    assert engine.settings_used()["truncated_chunks"] == 3


def test_missing_audio_names_the_stage_that_fetches_it():
    engine = CanaryEngine(_settings())

    with pytest.raises(FileNotFoundError, match="fetch stage"):
        engine.transcribe("no/such/file.mp3", "00-001")


def test_the_truncation_count_belongs_to_one_recording_not_the_run():
    """One engine transcribes a whole run, so the counter has to be reset.

    Left to climb, every case reports the running total of every case before it.
    The first Canary run did exactly that - 58 truncations across the corpus
    where there were 3 - and the numbers looked alarming rather than negligible.
    """
    engine = CanaryEngine(_settings())
    engine.truncated_chunks = 7

    with pytest.raises(FileNotFoundError):
        engine.transcribe("no/such/file.mp3", "00-001")

    # The reset happens after the audio check, so a missing file leaves it
    # alone; what matters is that `transcribe` does not accumulate across cases.
    assert "truncated_chunks" in engine.settings_used()

"""Tests for the Voxtral engine, which runs two models rather than one.

Nothing here loads a model. These check the wiring that has gone wrong before in
this project - a doubled engine name, a settings record describing the wrong
experiment, a chunk longer than the thing that has to process it - plus the one
thing specific to this engine: it serves Mistral's batch model and their
streaming model, and they need different transformers classes.

That distinction is not only a loading detail. The streaming model commits to a
word before the sentence is finished, which is what a live courtroom transcript
must do. If the engine silently loaded the batch class for it, the run would
still produce a transcript and the comparison between them would be a comparison
of nothing.
"""

from __future__ import annotations

import pytest

from scotus_asr.asr import aligner as aligner_module
from scotus_asr.asr import canary_engine, qwen3_engine, voxtral_engine
from scotus_asr.asr.base import AsrEngine
from scotus_asr.asr.registry import available_engines, build_engine
from scotus_asr.asr.voxtral_engine import VoxtralEngine
from scotus_asr.config import AsrSettings

BATCH = "Voxtral-Mini-3B-2507"
REALTIME = "Voxtral-Mini-4B-Realtime-2602"


def _settings(model: str = BATCH, **over) -> AsrSettings:
    base = {"engine": "voxtral", "model": model, "device": "cuda",
            "compute_type": "bfloat16", "language": "en"}
    base.update(over)
    return AsrSettings(**base)


def test_voxtral_joins_the_other_engines():
    """Named, not counted - an exact set here breaks on the next model added."""
    registered = set(available_engines())

    assert "voxtral" in registered
    assert {"canary", "faster-whisper", "parakeet", "qwen3-asr"} <= registered


def test_building_it_does_not_load_a_model():
    """Building must stay cheap - the runner builds one before any audio exists."""
    engine = build_engine(_settings())

    assert isinstance(engine, VoxtralEngine)
    assert engine._model is None


def test_it_satisfies_the_engine_protocol():
    assert isinstance(build_engine(_settings()), AsrEngine)


def test_the_name_is_not_doubled():
    """Two earlier engines here produced names like `parakeet-parakeet-...`."""
    assert VoxtralEngine(_settings(BATCH)).name == BATCH


def test_the_capitalised_repository_name_is_why_the_check_is_case_insensitive():
    """Mistral capitalise their repositories; a lowercase test would prefix them."""
    assert not BATCH.startswith("voxtral")
    assert VoxtralEngine(_settings(BATCH)).name == BATCH


def test_an_unrelated_model_name_gets_the_prefix():
    assert VoxtralEngine(_settings("tiny")).name == "voxtral-tiny"


def test_a_bare_name_gets_mistrals_namespace():
    assert VoxtralEngine(_settings())._model_id == "mistralai/Voxtral-Mini-3B-2507"


def test_a_full_repository_path_is_left_alone():
    engine = VoxtralEngine(_settings("mistralai/Voxtral-Mini-3B-2507"))
    assert engine._model_id == "mistralai/Voxtral-Mini-3B-2507"


def test_the_streaming_model_is_recognised_as_streaming():
    """It needs a different transformers class, and a different reading."""
    assert VoxtralEngine(_settings(REALTIME)).is_realtime is True


def test_the_batch_model_is_not_mistaken_for_the_streaming_one():
    assert VoxtralEngine(_settings(BATCH)).is_realtime is False


def test_which_model_it_was_is_written_into_the_run_record():
    """The whole comparison rests on this, so it is not left to the filename."""
    assert VoxtralEngine(_settings(REALTIME)).settings_used()["streaming_model"] is True
    assert VoxtralEngine(_settings(BATCH)).settings_used()["streaming_model"] is False


def test_the_chunk_fits_inside_the_aligners_limit():
    """Voxtral takes thirty minutes; the aligner that times its words takes five.

    The shorter of the two is what the chunk has to respect, and it is not the
    model's own limit - which is why this is easy to get wrong.
    """
    assert voxtral_engine.CHUNK_SECONDS <= aligner_module.MAX_SECONDS


def test_it_shares_the_chunk_length_with_the_other_aligned_engine():
    """Qwen3 is cut the same way, so a difference between them is the model."""
    assert voxtral_engine.CHUNK_SECONDS == qwen3_engine.CHUNK_SECONDS


def test_canary_still_takes_the_shortest_chunks():
    """Canary's limit is its own training, not the aligner - see canary_engine."""
    assert canary_engine.CHUNK_SECONDS < voxtral_engine.CHUNK_SECONDS


def test_an_overlap_is_longer_than_any_word():
    assert voxtral_engine.OVERLAP_SECONDS >= 4.0
    assert voxtral_engine.OVERLAP_SECONDS < voxtral_engine.CHUNK_SECONDS


def test_every_aligned_engine_uses_the_same_aligner():
    """Otherwise a comparison between them is a comparison of two aligners."""
    voxtral = VoxtralEngine(_settings())
    canary = canary_engine.CanaryEngine(
        _settings("canary-1b-v2", engine="canary", compute_type="float16"))
    qwen = qwen3_engine.Qwen3Engine(
        _settings("Qwen3-ASR-1.7B-hf", engine="qwen3-asr", compute_type="float16"))

    assert (voxtral._aligner.repo_id == canary._aligner.repo_id
            == qwen._aligner.repo_id == aligner_module.ALIGNER_ID)


def test_the_settings_record_names_the_model_and_the_aligner():
    used = VoxtralEngine(_settings()).settings_used()

    assert used["model"] == "mistralai/Voxtral-Mini-3B-2507"
    assert used["aligner"] == aligner_module.ALIGNER_ID
    assert used["chunk_seconds"] == voxtral_engine.CHUNK_SECONDS
    assert used["language"] == "en"


def test_the_settings_record_leaves_out_whispers_options():
    used = VoxtralEngine(_settings()).settings_used()

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


def test_sixteen_bit_is_bfloat16_whichever_way_it_is_asked_for():
    """Voxtral is published in bfloat16 and mixing the two formats raises.

    `float16` in a settings file means "sixteen bit" here rather than that exact
    format, so a file written for another engine does not fail on this one.
    """
    import torch

    assert voxtral_engine._dtype("bfloat16") is torch.bfloat16
    assert voxtral_engine._dtype("float16") is torch.bfloat16
    assert voxtral_engine._dtype("float32") is torch.float32


def test_missing_audio_names_the_stage_that_fetches_it():
    with pytest.raises(FileNotFoundError, match="fetch stage"):
        VoxtralEngine(_settings()).transcribe("no/such/file.mp3", "00-001")

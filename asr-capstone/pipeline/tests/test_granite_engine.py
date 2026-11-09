"""Tests for the Granite Speech engine.

Nothing here loads a model. Most of these check the same wiring every engine in
this project has got wrong at least once, but two are specific to this one and
they are the reason the file exists.

**The prompt is load-bearing.** Asked IBM's default way, Granite writes no
capital letters. Asked the way IBM document for 4.1, it writes punctuation and
truecasing. The strictest of this project's three scoring rules counts capitals
as part of the record, so a run made with the wrong prompt would report the model
tidying the record away when it had been asked the wrong question. The prompt is
therefore a constant, it is asserted here, and it is written into every result.

**The chunk length is measured, not chosen.** Granite holds about 122 words a
minute at two minutes and jumps to 297 at four, which is a repetition loop rather
than speech.
"""

from __future__ import annotations

import pytest

from scotus_asr.asr import aligner as aligner_module
from scotus_asr.asr import canary_engine, granite_engine, voxtral_engine
from scotus_asr.asr.base import AsrEngine
from scotus_asr.asr.granite_engine import GraniteEngine
from scotus_asr.asr.registry import available_engines, build_engine
from scotus_asr.config import AsrSettings

MODEL = "granite-speech-4.1-2b"


def _settings(model: str = MODEL, **over) -> AsrSettings:
    base = {"engine": "granite", "model": model, "device": "cuda",
            "compute_type": "bfloat16", "language": "en"}
    base.update(over)
    return AsrSettings(**base)


def test_granite_joins_the_other_engines():
    registered = set(available_engines())

    assert "granite" in registered
    assert {"canary", "faster-whisper", "parakeet", "qwen3-asr", "voxtral"} <= registered


def test_building_it_does_not_load_a_model():
    engine = build_engine(_settings())

    assert isinstance(engine, GraniteEngine)
    assert engine._model is None


def test_it_satisfies_the_engine_protocol():
    assert isinstance(build_engine(_settings()), AsrEngine)


def test_the_name_is_not_doubled():
    assert GraniteEngine(_settings()).name == MODEL


def test_an_unrelated_model_name_gets_the_prefix():
    assert GraniteEngine(_settings("tiny")).name == "granite-tiny"


def test_a_bare_name_gets_ibms_namespace():
    assert GraniteEngine(_settings())._model_id == "ibm-granite/granite-speech-4.1-2b"


def test_a_full_repository_path_is_left_alone():
    engine = GraniteEngine(_settings("ibm-granite/granite-speech-4.1-2b"))
    assert engine._model_id == "ibm-granite/granite-speech-4.1-2b"


def test_the_prompt_asks_for_punctuation_and_capitals():
    """The one setting that decides whether this model writes a record.

    IBM's default prompt - "can you transcribe the speech into a written
    format?" - returns text with no capital letters. This wording is theirs, from
    the 4.1 card, and it returns both.
    """
    prompt = granite_engine.TRANSCRIBE_PROMPT.lower()

    assert "punctuation" in prompt
    assert "capitalization" in prompt or "capitalisation" in prompt


def test_the_prompt_is_recorded_with_every_result():
    """It changes the output, so a result that does not name it is not evidence."""
    used = GraniteEngine(_settings()).settings_used()

    assert used["prompt"] == granite_engine.TRANSCRIBE_PROMPT
    assert used["system_prompt"] == granite_engine.SYSTEM_PROMPT


def test_the_chunk_stays_inside_what_granite_handles():
    """Measured: 122 words a minute at two minutes, 297 at four.

    Real argument runs near 180, so 297 is the model repeating itself. A chunk
    set past the limit does not raise - it produces text that reads downstream as
    speech nobody said.
    """
    assert granite_engine.CHUNK_SECONDS <= 120.0


def test_the_chunk_also_fits_the_aligner():
    assert granite_engine.CHUNK_SECONDS <= aligner_module.MAX_SECONDS


def test_it_takes_shorter_chunks_than_voxtral():
    """Voxtral is capped by the aligner; Granite by its own behaviour, sooner."""
    assert granite_engine.CHUNK_SECONDS < voxtral_engine.CHUNK_SECONDS


def test_the_token_ceiling_leaves_room_for_the_chunk():
    """A fast speaker at 220 words a minute, 1.4 tokens a word, still fits."""
    tokens = granite_engine.CHUNK_SECONDS * (220 / 60) * 1.4

    assert tokens < granite_engine.MAX_NEW_TOKENS


def test_every_aligned_engine_uses_the_same_aligner():
    granite = GraniteEngine(_settings())
    canary = canary_engine.CanaryEngine(
        _settings("canary-1b-v2", engine="canary", compute_type="float16"))

    assert granite._aligner.repo_id == canary._aligner.repo_id == aligner_module.ALIGNER_ID


def test_the_settings_record_names_the_model_and_the_aligner():
    used = GraniteEngine(_settings()).settings_used()

    assert used["model"] == "ibm-granite/granite-speech-4.1-2b"
    assert used["aligner"] == aligner_module.ALIGNER_ID
    assert used["chunk_seconds"] == granite_engine.CHUNK_SECONDS


def test_the_settings_record_leaves_out_whispers_options():
    used = GraniteEngine(_settings()).settings_used()

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
    import torch

    assert granite_engine._dtype("bfloat16") is torch.bfloat16
    assert granite_engine._dtype("float16") is torch.bfloat16
    assert granite_engine._dtype("float32") is torch.float32


def test_missing_audio_names_the_stage_that_fetches_it():
    with pytest.raises(FileNotFoundError, match="fetch stage"):
        GraniteEngine(_settings()).transcribe("no/such/file.mp3", "00-001")

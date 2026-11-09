"""Tests for the Qwen3-ASR engine's pure logic.

Most of this engine is glue against two models, which a test cannot exercise
without a GPU. What it can pin is the repository names - and those matter more
than they look. `Qwen/Qwen3-ASR-1.7B` and `Qwen/Qwen3-ASR-1.7B-hf` are different
formats, and only the second loads with transformers. Getting it wrong fails
after a four-gigabyte download.

The chunk seams are the shared rule from the Parakeet engine, tested there.
"""

from __future__ import annotations

from scotus_asr.asr.parakeet_engine import keep_window
from scotus_asr.asr.qwen3_engine import (
    CHUNK_SECONDS,
    OVERLAP_SECONDS,
    Qwen3Engine,
)
from scotus_asr.config import AsrSettings


def _engine(model: str = "Qwen3-ASR-1.7B-hf") -> Qwen3Engine:
    return Qwen3Engine(AsrSettings(engine="qwen3-asr", model=model))


def test_a_bare_model_name_gets_the_qwen_owner():
    assert _engine()._model_id == "Qwen/Qwen3-ASR-1.7B-hf"


def test_a_full_repository_name_is_left_alone():
    assert _engine("Qwen/Qwen3-ASR-0.6B-hf")._model_id == "Qwen/Qwen3-ASR-0.6B-hf"


def test_the_aligner_is_not_optional():
    """Without it there are no word timings, and without those this project
    loses the silence measure and the location of every dropped passage."""
    assert _engine()._aligner_id.endswith("Qwen3-ForcedAligner-0.6B-hf")


def test_the_engine_name_does_not_repeat_itself():
    """The model name already says qwen, so the label should not say it twice."""
    assert _engine().name == "Qwen3-ASR-1.7B-hf"


def test_chunks_stay_inside_the_aligner_limit():
    """The forced aligner handles five minutes. Chunks must leave a margin."""
    assert CHUNK_SECONDS < 300
    assert OVERLAP_SECONDS < CHUNK_SECONDS / 2


def test_the_chunks_tile_a_recording_with_no_gap():
    """Same rule as Parakeet, different sizes - so check it holds at these."""
    total = 3600.0
    step = CHUNK_SECONDS - OVERLAP_SECONDS

    windows, offset, index = [], 0.0, 0
    while offset < total:
        windows.append(keep_window(offset, index, total, CHUNK_SECONDS, OVERLAP_SECONDS))
        offset += step
        index += 1

    assert windows[0][0] == 0.0
    assert windows[-1][1] >= total
    for (_, ends), (starts, _) in zip(windows, windows[1:]):
        assert ends == starts

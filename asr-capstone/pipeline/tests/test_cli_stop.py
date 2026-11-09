"""Tests for `cli stop`: asking a run, by name, to end after its current recording."""

from __future__ import annotations

from scotus_asr.cli import main
from scotus_asr.runner import STOP_FILE


def test_stop_leaves_a_request_in_the_named_run(tmp_path):
    run_dir = tmp_path / "run-scotus250-qwen3"
    run_dir.mkdir()

    code = main(["stop", "--run-id", str(run_dir)])

    assert code == 0
    assert (run_dir / STOP_FILE).exists()


def test_stop_needs_a_run_name(tmp_path):
    """Guessing "the most recent run" could stop the wrong one, or none."""
    assert main(["stop"]) == 2


def test_stop_on_a_mistyped_name_creates_nothing(tmp_path):
    run_dir = tmp_path / "run-no-such-thing"

    code = main(["stop", "--run-id", str(run_dir)])

    assert code == 1
    assert not run_dir.exists()

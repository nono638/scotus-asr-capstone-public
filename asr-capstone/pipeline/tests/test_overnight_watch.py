"""The overnight watcher's choice of when to come back, and what counts as saved."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from overnight_watch import (  # noqa: E402
    configs_of, decide, progress_at, row_label, run_dir_for, saved_since,
)

RUNNING = {"state": "running", "exit_code": None}
QUIET = dict(item_minutes=30, heartbeat_minutes=0.1, quiet_minutes=1,
             quiet_limit=45, routine_due=False)


def test_all_well_means_keep_waiting():
    assert decide(RUNNING, True, False, **QUIET) is None


def test_ended_queue_is_reported_with_its_code():
    event = decide({"state": "crashed", "exit_code": -1073741819}, False, False, **QUIET)
    assert event.startswith("ended") and "-1073741819" in event


def test_dead_process_that_never_said_so():
    assert decide(RUNNING, False, False, **QUIET).startswith("died")


def test_first_result_comes_before_routine():
    event = decide(RUNNING, True, True, **{**QUIET, "routine_due": True})
    assert event.startswith("first result")


def test_stale_heartbeat_counts_only_after_the_grace_period():
    stale = {**QUIET, "heartbeat_minutes": 12}
    assert decide(RUNNING, True, False, **stale).startswith("no heartbeat")
    assert decide(RUNNING, True, False, **{**stale, "item_minutes": 2}) is None


def test_quiet_too_long():
    assert decide(RUNNING, True, False, **{**QUIET, "quiet_minutes": 50}).startswith("quiet")


def test_saved_counts_transcripts_only_since_the_item_started():
    since = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    ledger = [
        {"task_id": "10-1/asr/Qwen3", "status": "ok", "finished_at": "2026-10-17T11:59:00+00:00"},
        {"task_id": "10-2/asr/Qwen3", "status": "ok", "finished_at": "2026-10-17T12:05:00+00:00"},
        {"task_id": "10-2/score/Qwen3", "status": "ok", "finished_at": "2026-10-17T12:06:00+00:00"},
        {"task_id": "10-3/asr/Qwen3", "status": "failed", "finished_at": "2026-10-17T12:30:00+00:00"},
    ]
    saved, failed = saved_since(ledger, since)
    assert [r["task_id"] for r in saved] == ["10-2/asr/Qwen3"]
    assert [r["task_id"] for r in failed] == ["10-3/asr/Qwen3"]


def test_progress_is_when_the_current_chunk_began(tmp_path):
    # Read from the files, so a freshly started watcher still sees an old hang.
    started = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    gpu = [
        {"at": "2026-10-17T12:10:00+00:00", "note": "10-1 chunk 1"},
        {"at": "2026-10-17T12:20:00+00:00", "note": "10-1 chunk 2"},
        {"at": "2026-10-17T12:20:05+00:00", "note": "10-1 chunk 2"},
        {"at": "2026-10-17T13:30:00+00:00", "note": "10-1 chunk 2"},
    ]
    moved = progress_at(started, tmp_path / "no-ledger.jsonl", gpu)
    assert moved == datetime(2026, 10, 17, 12, 20, tzinfo=timezone.utc)
    assert progress_at(started, tmp_path / "no-ledger.jsonl", []) == started


def test_a_row_for_another_corpus_is_labelled_with_it():
    row = {"config": "config/qwen3.yaml config/corpora/edacc.yaml config/corpora/edacc-dev.yaml"}
    assert row_label(row) == "qwen3 (edacc)"
    assert row_label({"config": "config/corpus.yaml"}) == "whisper"
    assert len(configs_of(row)) == 3


def test_a_run_folder_comes_from_the_row_settings():
    """EdAcc's runs live beside the corpus, not among the Supreme Court's."""
    runs = Path("D:/scotus-corpus/runs")
    edacc = {"config": "config/parakeet.yaml config/corpora/edacc.yaml", "run": "run-edacc-parakeet"}
    assert run_dir_for(edacc, runs).parent.name == "runs"
    assert "edacc" in str(run_dir_for(edacc, runs)).lower()
    assert run_dir_for({"run": "r"}, runs) == runs / "r"

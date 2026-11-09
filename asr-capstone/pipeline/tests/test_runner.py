"""Tests for the task loop: resuming, isolating failures, retrying.

These are the tests that stand in for "leave it running overnight and see".
"""

from __future__ import annotations

import pytest

from scotus_asr.events import EventBus
from scotus_asr.ledger import Ledger
from scotus_asr.runner import STOP_FILE, Runner
from scotus_asr.store import RunStore
from scotus_asr.tasks import Stage, Task, TaskKey


def make_runner(tmp_path, max_attempts=3):
    """A runner writing into a temporary folder, with no waiting between tries."""
    store = RunStore(tmp_path / "run-1")
    ledger = Ledger(store.root / "ledger.jsonl")
    return Runner(store, ledger, EventBus(), max_attempts=max_attempts,
                  backoff_seconds=0.0), store, ledger


def writing_task(store, docket, calls, fail_times=0):
    """A task that records that it ran and writes its output file."""
    output = store.reference_path(docket)
    state = {"attempts": 0}

    def work():
        state["attempts"] += 1
        calls.append(docket)
        if state["attempts"] <= fail_times:
            raise RuntimeError(f"{docket} failed on purpose")
        store.write_json(output, {"docket": docket})
        return {"turns": 1}

    return Task(key=TaskKey(docket, Stage.TRANSCRIPT), run=work, output=output)


def test_a_task_runs_and_writes_its_output(tmp_path):
    runner, store, _ = make_runner(tmp_path)
    calls = []

    summary = runner.run([writing_task(store, "09-834", calls)])

    assert summary.completed == 1
    assert calls == ["09-834"]
    assert store.has(store.reference_path("09-834"))


def test_finished_work_is_not_repeated(tmp_path):
    """The whole point of resuming: run it twice, it works once."""
    runner, store, _ = make_runner(tmp_path)
    calls = []

    runner.run([writing_task(store, "09-834", calls)])
    summary = runner.run([writing_task(store, "09-834", calls)])

    assert summary.skipped == 1
    assert summary.completed == 0
    assert calls == ["09-834"]


def test_deleting_the_output_forces_the_work_to_be_done_again(tmp_path):
    """Deleting a result by hand is how you ask for it to be rebuilt."""
    runner, store, _ = make_runner(tmp_path)
    calls = []

    runner.run([writing_task(store, "09-834", calls)])
    store.reference_path("09-834").unlink()
    runner.run([writing_task(store, "09-834", calls)])

    assert calls == ["09-834", "09-834"]


def test_an_output_with_no_ledger_entry_is_redone(tmp_path):
    """The crash between writing the file and recording it.

    Redoing is the safe choice: the file might be from an interrupted write that
    happened to be the right size.
    """
    runner, store, _ = make_runner(tmp_path)
    calls = []

    store.write_json(store.reference_path("09-834"), {"stale": True})
    runner.run([writing_task(store, "09-834", calls)])

    assert calls == ["09-834"]


def test_one_failure_does_not_stop_the_others(tmp_path):
    """A corrupt file at case two must not cost you cases three, four and five."""
    runner, store, _ = make_runner(tmp_path, max_attempts=1)
    calls = []

    tasks = [
        writing_task(store, "a", calls),
        writing_task(store, "b", calls, fail_times=99),
        writing_task(store, "c", calls),
    ]
    summary = runner.run(tasks)

    assert summary.completed == 2
    assert summary.failed == 1
    assert [name for name, _ in summary.failures] == ["b/transcript"]
    assert store.has(store.reference_path("c"))


def test_a_task_that_fails_once_is_tried_again(tmp_path):
    runner, store, _ = make_runner(tmp_path, max_attempts=3)
    calls = []

    summary = runner.run([writing_task(store, "09-834", calls, fail_times=1)])

    assert summary.completed == 1
    assert calls == ["09-834", "09-834"]


def test_failures_are_recorded_with_their_traceback(tmp_path):
    """Read the morning after: what failed, and why."""
    runner, store, ledger = make_runner(tmp_path, max_attempts=1)

    runner.run([writing_task(store, "bad", [], fail_times=99)])

    entries = list(ledger.entries())
    assert len(entries) == 1
    assert entries[0].status == "failed"
    assert "failed on purpose" in entries[0].summary
    assert "RuntimeError" in entries[0].error


def test_a_later_success_clears_an_earlier_failure(tmp_path):
    """Fix the problem, run again, and the task is no longer listed as failed."""
    runner, store, ledger = make_runner(tmp_path, max_attempts=1)

    runner.run([writing_task(store, "09-834", [], fail_times=99)])
    assert ledger.failed_ids() == {"09-834/transcript"}

    runner.run([writing_task(store, "09-834", [])])
    assert ledger.failed_ids() == set()
    assert "09-834/transcript" in ledger.completed_ids()


def test_stopping_deliberately_is_not_treated_as_a_failure(tmp_path):
    """Ctrl-C should stop promptly, not retry three times first."""
    runner, store, _ = make_runner(tmp_path, max_attempts=3)
    attempts = []

    def interrupted():
        attempts.append(1)
        raise KeyboardInterrupt

    task = Task(
        key=TaskKey("09-834", Stage.ASR, "whisper"),
        run=interrupted,
        output=store.asr_path("09-834", "whisper"),
    )

    with pytest.raises(KeyboardInterrupt):
        runner.run([task])

    assert len(attempts) == 1


def stop_asked_during(store, docket, calls):
    """A task that, while it runs, gets asked to stop - the morning pause."""
    task = writing_task(store, docket, calls)
    work = task.run

    def work_then_ask():
        (store.root / STOP_FILE).write_text("stop")
        return work()

    return Task(key=task.key, run=work_then_ask, output=task.output)


def test_a_stop_request_lets_the_current_task_finish_then_ends(tmp_path):
    """The recording in progress is saved; nothing new starts."""
    runner, store, _ = make_runner(tmp_path)
    calls = []

    summary = runner.run([
        stop_asked_during(store, "a", calls),
        writing_task(store, "b", calls),
        writing_task(store, "c", calls),
    ])

    assert calls == ["a"]
    assert summary.completed == 1
    assert summary.stopped
    assert store.has(store.reference_path("a"))
    assert not (store.root / STOP_FILE).exists()


def test_a_stopped_run_carries_on_where_it_left_off(tmp_path):
    runner, store, _ = make_runner(tmp_path)
    calls = []

    runner.run([stop_asked_during(store, "a", calls), writing_task(store, "b", calls)])
    summary = runner.run([writing_task(store, "a", calls), writing_task(store, "b", calls)])

    assert calls == ["a", "b"]
    assert summary.skipped == 1
    assert summary.completed == 1
    assert not summary.stopped


def test_a_stop_request_left_from_before_does_not_block_a_new_start(tmp_path):
    """Starting the command again is the newer instruction."""
    runner, store, _ = make_runner(tmp_path)
    (store.root / STOP_FILE).write_text("stop")
    calls = []

    summary = runner.run([writing_task(store, "a", calls)])

    assert calls == ["a"]
    assert not summary.stopped


def test_leftover_temporary_files_are_cleared_before_a_run(tmp_path):
    runner, store, _ = make_runner(tmp_path)
    (store.root / "asr").mkdir(parents=True)
    (store.root / "asr" / "x.json.tmp").write_text("half")

    runner.run([])

    assert list(store.root.rglob("*.tmp")) == []


def test_a_damaged_last_ledger_line_does_not_stop_the_run(tmp_path):
    """The signature of a crash mid-write. Skip the line, keep the rest."""
    runner, store, ledger = make_runner(tmp_path)
    runner.run([writing_task(store, "a", [])])

    with open(ledger.path, "a", encoding="utf-8") as stream:
        stream.write('{"task_id": "b/transcr')  # cut off

    assert "a/transcript" in ledger.completed_ids()

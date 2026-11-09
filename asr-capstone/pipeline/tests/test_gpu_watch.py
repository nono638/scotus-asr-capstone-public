"""Tests for the things added after the crash of 21 September 2026.

That night a run died and left nothing to diagnose it with. The machine took a
kernel bugcheck - the Windows graphics scheduler faulting - and rebooted. The
only surviving clue was that one chunk had taken eleven minutes where the same
work took two an hour earlier, and that had to be worked out by subtracting two
timestamps by hand.

Two things are being pinned down here, and they are both about what survives
and what gets noticed:

- A memory reading must reach the disk before the next one is taken. A kernel
  crash does not unwind anything, so a line still sitting in the operating
  system's write buffer is a line that was never written.
- A chunk running far slower than its neighbours must produce a warning while
  the run is still going, because that is the only warning this failure gives.
"""

from __future__ import annotations

import json
import logging
import time

import pytest

from scotus_asr import gpu
from scotus_asr.asr.base import decode_chunk, watch_pace


# ---------------------------------------------------------------------------
# The reading itself
# ---------------------------------------------------------------------------


def test_a_reading_has_the_fields_needed_to_tell_the_two_cases_apart():
    """Whole-card numbers and this-process numbers, or nothing at all.

    The diagnostic question is "was the card full, and if so was it us?", and
    answering it needs both. On the work laptop there is no GPU and the answer
    is an empty reading, which is fine - it must not be an exception.
    """
    reading = gpu.memory_snapshot()

    if not reading:
        return  # no GPU on this machine; nothing to check

    assert "error" not in reading, reading
    for field in (
        "free_gb",
        "used_gb",
        "total_gb",
        "torch_allocated_gb",
        "torch_reserved_gb",
    ):
        assert field in reading
        assert isinstance(reading[field], (int, float))

    # Reserved is what PyTorch took from the driver in order to hand it out, so
    # it can never be less than what it handed out.
    assert reading["torch_reserved_gb"] >= reading["torch_allocated_gb"]
    assert reading["free_gb"] + reading["used_gb"] == reading["total_gb"]


def test_a_reading_never_raises():
    """Called from inside a warning path, where an exception would be absurd."""
    assert isinstance(gpu.memory_snapshot(), dict)


def test_releasing_memory_is_safe_with_or_without_a_gpu():
    """Called between every pair of cases, so it has to be dull."""
    gpu.release_memory()
    gpu.release_memory()


# ---------------------------------------------------------------------------
# The recorder
# ---------------------------------------------------------------------------


def test_every_line_is_on_the_disk_before_the_next_one_is_written(tmp_path):
    """The whole point. Read the file from a separate handle while it is open.

    If the recorder only flushed to Python's buffer, a reader opening the file
    independently would see nothing until it closed. That is exactly the state
    the machine was in when it crashed.
    """
    path = tmp_path / "gpu-memory.jsonl"
    recorder = gpu.MemoryRecorder(path, every_seconds=0.1)
    recorder.start()
    try:
        time.sleep(0.45)
        # Deliberately a fresh read, not through the recorder's own handle.
        written = path.read_text(encoding="utf-8").splitlines()
    finally:
        recorder.stop()

    assert len(written) >= 2, f"only {len(written)} line(s) reached the disk"
    for line in written:
        row = json.loads(line)  # each line must be complete, not half-flushed
        assert "at" in row
        assert "note" in row


def test_a_note_says_which_chunk_a_reading_belongs_to(tmp_path):
    """A number alone says the card was full; a note says what filled it."""
    path = tmp_path / "gpu-memory.jsonl"
    recorder = gpu.MemoryRecorder(path, every_seconds=60)  # timer will not fire
    recorder.start()
    try:
        recorder.sample("16-285 chunk 3")
        recorder.sample("16-285 chunk 4")
    finally:
        recorder.stop()

    notes = [json.loads(line)["note"] for line in path.read_text().splitlines()]
    assert "16-285 chunk 3" in notes
    assert "16-285 chunk 4" in notes


def test_marking_does_nothing_when_no_run_is_recording():
    """Engines call `mark` unconditionally, including under test and in scripts."""
    gpu.stop_recording()
    gpu.mark("nobody is listening", sample=True)  # must not raise


def test_the_run_recorder_can_be_started_and_stopped_repeatedly(tmp_path):
    """`stop_recording` runs in a `finally`, so it may be called twice."""
    gpu.start_recording(tmp_path / "one.jsonl", every_seconds=60)
    gpu.mark("during", sample=True)
    gpu.stop_recording()
    gpu.stop_recording()

    assert (tmp_path / "one.jsonl").exists()


# ---------------------------------------------------------------------------
# Noticing a slow chunk
# ---------------------------------------------------------------------------


def test_ordinary_variation_between_chunks_stays_quiet(caplog):
    """Chunks already range about two and a half to one.

    Appellate argument is not evenly paced - a chunk of dense questioning
    produces far more tokens than a chunk of one advocate talking. A check that
    fired on that would be noise, and noise is why the real warning gets
    ignored.
    """
    history: list[float] = []
    with caplog.at_level(logging.WARNING):
        for index, seconds in enumerate([180.0, 50.0, 130.0, 58.0, 120.0, 61.0]):
            watch_pace("TEST", index, seconds, history)

    assert caplog.text == ""


def test_the_chunk_that_actually_happened_is_caught(caplog):
    """The real numbers from 21 September: about 2 minutes, then 11 minutes."""
    history: list[float] = []
    with caplog.at_level(logging.WARNING):
        for index, seconds in enumerate([202.0, 126.0, 118.0, 122.0, 680.0]):
            watch_pace("16-285", index, seconds, history)

    assert "16-285" in caplog.text
    assert "Chunk 4" in caplog.text
    # The reader's next question is how full the card was, so the warning
    # carries the answer rather than making them go and look.
    assert "GPU" in caplog.text


def test_the_first_chunk_is_not_held_against_the_rest(caplog):
    """The first chunk pays for warming up the model and runs long every time.

    Counting it in the usual would raise the bar and hide a genuine slowdown
    later; comparing against it would fire on every second chunk.
    """
    history: list[float] = []
    with caplog.at_level(logging.WARNING):
        for index, seconds in enumerate([400.0, 60.0, 62.0, 59.0]):
            watch_pace("TEST", index, seconds, history)

    assert caplog.text == ""


def test_nothing_is_said_before_there_is_a_usual_to_compare_to(caplog):
    """Two chunks is not a baseline. One slow one out of two proves nothing."""
    history: list[float] = []
    with caplog.at_level(logging.WARNING):
        watch_pace("TEST", 0, 100.0, history)
        watch_pace("TEST", 1, 900.0, history)

    assert caplog.text == ""


def test_every_chunk_is_recorded_even_when_it_is_unremarkable():
    """The history is what the next comparison is made against."""
    history: list[float] = []
    for index, seconds in enumerate([100.0, 60.0, 62.0]):
        watch_pace("TEST", index, seconds, history)

    assert history == [100.0, 60.0, 62.0]


# ---------------------------------------------------------------------------
# Surviving a chunk that does not fit
# ---------------------------------------------------------------------------


class _FakeOutOfMemory(Exception):
    """Stands in for torch's error, which needs a GPU to raise for real."""

    def __str__(self) -> str:
        return "CUDA out of memory. Tried to allocate 2.00 GiB"


def test_a_chunk_that_runs_out_of_memory_is_tried_once_more(caplog):
    """The second attempt has several gigabytes the first did not.

    The cache is cleared in between, and the usual cause of the failure is
    blocks of the wrong size being held from earlier chunks rather than the
    chunk genuinely being too big.
    """
    attempts = []

    def work():
        attempts.append(1)
        if len(attempts) == 1:
            raise _FakeOutOfMemory()
        return "the transcript", ["words"]

    with caplog.at_level(logging.WARNING):
        text, words = decode_chunk(work, "16-285", 4)

    assert (text, words) == ("the transcript", ["words"])
    assert len(attempts) == 2
    assert "ran out of video memory" in caplog.text
    assert "16-285" in caplog.text


def test_a_chunk_that_fails_twice_is_allowed_to_fail():
    """Then it really is too big, and the runner should record the case.

    One missing row in a table beats an unattended run that stops at case
    three, so the error is passed up rather than swallowed.
    """
    def work():
        raise _FakeOutOfMemory()

    with pytest.raises(_FakeOutOfMemory):
        decode_chunk(work, "16-285", 4)


def test_an_ordinary_error_is_not_retried():
    """Only running out of memory is worth a second go.

    Retrying a genuine fault wastes a chunk's worth of time and buries the
    real error under a misleading warning about video memory.
    """
    attempts = []

    def work():
        attempts.append(1)
        raise ValueError("the audio was the wrong shape")

    with pytest.raises(ValueError):
        decode_chunk(work, "16-285", 4)
    assert len(attempts) == 1


def test_a_chunk_that_works_first_time_is_not_disturbed():
    """The common path, and it must not clear the cache for nothing."""
    calls = []

    def work():
        calls.append(1)
        return "fine"

    assert decode_chunk(work, "16-285", 0) == "fine"
    assert len(calls) == 1


def test_capping_memory_is_safe_with_or_without_a_gpu():
    """Called before every load, and a backstop must never be the thing that
    stops a run."""
    gpu.cap_memory()
    gpu.cap_memory(0.92)


def test_a_chunk_that_was_re_decoded_is_not_reported_as_slow(caplog):
    """It is slow by design: it paid for a wasted attempt before the good one.

    This fired for real on chunk 8 of 16-1161, which took 115s against a
    usual 37s because the first decode came back a repetition loop and was
    thrown away. The warning told the reader to go and look at video memory,
    and the reading it carried showed 10.39 GB free. Right number, wrong
    story.
    """
    history: list[float] = []
    with caplog.at_level(logging.WARNING):
        for index, seconds in enumerate([90.0, 37.0, 38.0, 36.0]):
            watch_pace("16-1161", index, seconds, history)
        watch_pace("16-1161", 8, 115.0, history, retried=True)

    assert caplog.text == ""


def test_a_re_decoded_chunk_does_not_raise_the_bar_for_the_others(caplog):
    """Counting its time towards the usual would hide a real slowdown later."""
    history: list[float] = []
    for index, seconds in enumerate([90.0, 37.0, 38.0, 36.0]):
        watch_pace("16-1161", index, seconds, history)
    watch_pace("16-1161", 8, 115.0, history, retried=True)

    assert 115.0 not in history

    # A genuinely slow chunk afterwards must still be caught.
    with caplog.at_level(logging.WARNING):
        watch_pace("16-1161", 9, 400.0, history)
    assert "times slower" in caplog.text

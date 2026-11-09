"""Tests for how the transcription tasks are built.

One thing is really being guarded here, and it cost two runs before anyone
noticed. Every engine holds about 4 GB of video memory for as long as it exists,
so building one per case fills a 24 GB card on the sixth. Nothing raises. The
sixth case decodes at about 19 times real time and the seventh at about 1.5,
every number stays correct, and a seven-hour run quietly becomes a two-day one.

A failure that produces right answers slowly is the kind a test suite has to
catch, because no one reading the results will.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scotus_asr import stages
from scotus_asr.config import load_config
from scotus_asr.corpus.manifest import Case
from scotus_asr.events import EventBus
from scotus_asr.store import RunStore


class CountingEngine:
    """Stands in for the real engine and records how it was called."""

    built = 0
    name = "whisper-test"

    def __init__(self) -> None:
        type(self).built += 1
        self.calls: list[tuple[str, Path | None]] = []

    def transcribe(self, audio_path, docket, on_progress=None, partial_path=None):
        self.calls.append((docket, partial_path))
        raise AssertionError("not meant to run in this test")


@pytest.fixture
def engine(monkeypatch):
    """Replace the real engine with one that counts how many are made."""
    CountingEngine.built = 0
    made: list[CountingEngine] = []

    def build(settings, partial_path=None):
        assert partial_path is None, (
            "The engine must not be given a per-case path. Holding one is what "
            "forced a new engine, and a new model, for every case."
        )
        made.append(CountingEngine())
        return made[-1]

    monkeypatch.setattr(stages, "build_engine", build)
    return made


def _cases(count: int, tmp_path: Path) -> list[Case]:
    """Cases that look like they have audio, without any audio existing."""
    return [
        Case(
            docket=f"00-{number:03d}",
            file_stem=f"00-{number:03d}",
            folder=tmp_path / f"case_{number}",
            argued="2011-01-01",
            transcript_url="https://example.invalid/t.pdf",
            audio_url="https://example.invalid/a.mp3",
            audio_minutes=60.0,
            expected_turns=None,
            expected_words=None,
        )
        for number in range(count)
    ]


def test_ten_cases_share_one_engine(tmp_path, engine):
    """The whole point. Ten engines would be forty gigabytes of video memory."""
    store = RunStore(tmp_path / "run")
    tasks = stages.build_asr_tasks(
        _cases(10, tmp_path), load_config(), store, EventBus()
    )

    assert len(tasks) == 10
    assert CountingEngine.built == 1


def test_an_engine_is_built_even_with_nothing_to_do(tmp_path, engine):
    """Cheap, because the model does not load until the first transcription."""
    store = RunStore(tmp_path / "run")
    tasks = stages.build_asr_tasks([], load_config(), store, EventBus())

    assert tasks == []


def test_each_case_still_streams_to_its_own_partial_file(tmp_path, engine):
    """Sharing the engine must not make two cases write to one partial file.

    That file is what survives a crash an hour into a long recording, so two
    cases sharing one would lose the very thing it exists to protect.
    """
    store = RunStore(tmp_path / "run")
    cases = _cases(3, tmp_path)
    tasks = stages.build_asr_tasks(cases, load_config(), store, EventBus())

    # Each task closes over its own path; check they are three distinct ones
    # named after their own case.
    paths = [task.run.__defaults__[-1] for task in tasks]
    assert len(set(paths)) == 3
    for case, path in zip(cases, paths):
        assert case.docket in path.name


def test_cases_without_audio_are_left_out(tmp_path, engine):
    """A transcript-only case is normal, not an error."""
    cases = _cases(3, tmp_path)
    cases[1] = Case(
        docket="00-999",
        file_stem="00-999",
        folder=tmp_path / "silent",
        argued="2003-01-01",
        transcript_url="https://example.invalid/t.pdf",
        audio_url=None,
        audio_minutes=None,
        expected_turns=None,
        expected_words=None,
    )

    tasks = stages.build_asr_tasks(cases, load_config(), RunStore(tmp_path / "r"),
                                   EventBus())

    assert len(tasks) == 2
    assert all("00-999" not in str(task.key) for task in tasks)

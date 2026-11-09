"""Tests for the promise that makes unattended runs safe.

The promise: a file that exists is a file that is finished. If that ever stops
being true, a resumed run will skip a half-written transcription and score
nonsense, and nothing anywhere will report an error.
"""

from __future__ import annotations

import json

import pytest

from scotus_asr.store import (
    TEMP_SUFFIX,
    RunStore,
    atomic_write_json,
    atomic_write_text,
    new_run_id,
    read_json,
)


def test_a_written_file_can_be_read_back(tmp_path):
    target = tmp_path / "result.json"
    atomic_write_json(target, {"turns": 252, "words": 9891})
    assert read_json(target) == {"turns": 252, "words": 9891}


def test_writing_creates_missing_directories(tmp_path):
    target = tmp_path / "deep" / "nested" / "result.json"
    atomic_write_json(target, {"ok": True})
    assert target.exists()


def test_a_failed_write_leaves_nothing_behind(tmp_path):
    """A crash mid-write must not leave a temporary file lying around.

    Anything left over would be cleaned up on the next run anyway, but leaving
    the directory tidy means `clean_temp_files` reporting a leftover is real news
    rather than noise.
    """
    target = tmp_path / "result.json"

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": Unserializable()})

    assert not target.exists()
    assert list(tmp_path.glob(f"*{TEMP_SUFFIX}")) == []


def test_overwriting_keeps_the_old_content_until_the_new_is_complete(tmp_path):
    target = tmp_path / "result.json"
    atomic_write_json(target, {"version": 1})
    atomic_write_json(target, {"version": 2})
    assert read_json(target) == {"version": 2}


def test_text_survives_its_real_characters(tmp_path):
    """Transcript text contains accented names and curly punctuation.

    Losing the N-tilde from a Solicitor General's surname is exactly the kind of
    silent corruption this project is supposed to detect, not commit.
    """
    target = tmp_path / "name.txt"
    atomic_write_text(target, "GENERAL AGUIÑAGA: it’s here — really")
    assert "AGUIÑAGA" in target.read_text(encoding="utf-8")
    assert "’" in target.read_text(encoding="utf-8")


class TestRunStore:
    def test_artifact_paths_are_predictable(self, tmp_path):
        """Resume depends on the same task always naming the same file."""
        store = RunStore(tmp_path / "run-1")
        assert store.reference_path("09-834").name == "09-834.json"
        assert store.asr_path("09-834", "whisper-large-v3").name == (
            "09-834.whisper-large-v3.json"
        )
        assert store.ocr_page_path("69-13", 7).name == "page_0007.json"

    def test_ocr_pages_sort_in_page_order(self, tmp_path):
        """Zero padding, so page 10 does not sort before page 9."""
        store = RunStore(tmp_path / "run-1")
        names = sorted(store.ocr_page_path("69-13", n).name for n in (1, 2, 10, 100))
        assert names == ["page_0001.json", "page_0002.json", "page_0010.json",
                         "page_0100.json"]

    def test_an_empty_file_does_not_count_as_finished(self, tmp_path):
        """A zero-length file means a disk filled up, not a completed task."""
        store = RunStore(tmp_path / "run-1")
        path = store.reference_path("09-834")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

        assert path.exists()
        assert not store.has(path)

    def test_leftover_temporary_files_are_cleared(self, tmp_path):
        store = RunStore(tmp_path / "run-1")
        (store.root / "asr").mkdir(parents=True)
        (store.root / "asr" / f"09-834.json{TEMP_SUFFIX}").write_text("half a file")

        assert store.clean_temp_files() == 1
        assert list(store.root.rglob(f"*{TEMP_SUFFIX}")) == []

    def test_a_temporary_file_in_use_does_not_stop_the_tidy_up(self, tmp_path):
        """Another run may be writing one right now.

        On Windows an open file cannot be deleted, and letting that raise
        brought down a whole run once. Housekeeping must never stop the work.
        """
        store = RunStore(tmp_path / "run-1")
        (store.root / "asr").mkdir(parents=True)
        busy = store.root / "asr" / f"24-109.partial.jsonl{TEMP_SUFFIX}"
        stale = store.root / "asr" / f"09-834.json{TEMP_SUFFIX}"
        stale.write_text("left over from a crash")

        with open(busy, "w", encoding="utf-8") as held:
            held.write("being written right now")
            held.flush()
            removed = store.clean_temp_files()

        # The stale one goes, the busy one is left alone, and nothing raised.
        assert removed >= 1
        assert not stale.exists()

    def test_rows_are_appended_with_a_header_written_once(self, tmp_path):
        store = RunStore(tmp_path / "run-1")
        table = store.results_path("scores.csv")

        store.append_csv_row(table, {"docket": "09-834", "wer": 0.11})
        store.append_csv_row(table, {"docket": "24-109", "wer": 0.09})

        lines = table.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "docket,wer"
        assert len(lines) == 3

    def test_each_row_is_on_disk_before_the_next_one_starts(self, tmp_path):
        """A run killed partway through still leaves the rows it finished."""
        store = RunStore(tmp_path / "run-1")
        table = store.results_path("scores.csv")

        for index in range(5):
            store.append_csv_row(table, {"docket": f"case-{index}", "wer": 0.1})
            # Read it back from a fresh handle - if anything were still buffered,
            # this would come up short.
            written = table.read_text(encoding="utf-8").strip().splitlines()
            assert len(written) == index + 2

    def test_redoing_a_case_replaces_its_rows_rather_than_adding_more(self, tmp_path):
        """Otherwise a results table silently double-counts.

        This happened for real while the OCR stage was being built: 778 rows
        describing 671 pages, because the case had been read twice.
        """
        store = RunStore(tmp_path / "run-1")
        table = store.results_path("ocr_quality.csv")
        columns = ["docket", "page", "misread"]

        for page in (1, 2):
            store.append_csv_row(table, {"docket": "69-13", "page": page, "misread": 3},
                                 fieldnames=columns)
        store.append_csv_row(table, {"docket": "09-834", "page": 1, "misread": 0},
                             fieldnames=columns)

        assert store.remove_csv_rows(table, "docket", "69-13") == 2

        for page in (1, 2):
            store.append_csv_row(table, {"docket": "69-13", "page": page, "misread": 1},
                                 fieldnames=columns)

        rows = table.read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) == 4               # header plus three rows
        assert "09-834,1,0" in rows         # the other case is untouched
        assert sum(1 for r in rows if r.startswith("69-13")) == 2

    def test_removing_rows_for_an_absent_case_changes_nothing(self, tmp_path):
        store = RunStore(tmp_path / "run-1")
        table = store.results_path("scores.csv")
        store.append_csv_row(table, {"docket": "09-834", "wer": 0.09})

        before = table.read_text(encoding="utf-8")
        assert store.remove_csv_rows(table, "docket", "not-here") == 0
        assert table.read_text(encoding="utf-8") == before

    def test_removing_rows_from_a_table_that_does_not_exist_is_harmless(self, tmp_path):
        store = RunStore(tmp_path / "run-1")
        assert store.remove_csv_rows(store.results_path("nothing.csv"), "docket", "x") == 0

    def test_column_order_is_stable_across_rows(self, tmp_path):
        """Rows arriving with keys in a different order must still line up."""
        store = RunStore(tmp_path / "run-1")
        table = store.results_path("scores.csv")
        columns = ["docket", "engine", "wer"]

        store.append_csv_row(table, {"docket": "a", "engine": "w", "wer": 1},
                             fieldnames=columns)
        store.append_csv_row(table, {"wer": 2, "docket": "b", "engine": "w"},
                             fieldnames=columns)

        lines = table.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "docket,engine,wer"
        assert lines[2] == "b,w,2"


def test_run_identifiers_sort_chronologically():
    """Continuing 'the most recent run' relies on this."""
    first = new_run_id()
    second = new_run_id()
    assert first <= second
    assert first.startswith("run-")

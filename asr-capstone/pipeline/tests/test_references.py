"""Tests for the reference readers in scotus_asr/references/."""

from __future__ import annotations

import pytest

from scotus_asr.references.timed_table import TimedRow, read_timed_table, rows_to_transcript

TABLE = (
    "Line\tSpkr\tStTime\tContent\tEnTime\n"
    "1\tA\t0.0\tWell, \"they\" said so\t2.5\n"
    "2\tB\t2.4\t(pause 0.30)\t2.7\n"
    "\n"
    "3\tB\t2.7\tskip me\t4.0\n"
    "4\tA\t1.0\tearlier but listed later\t1.5\n"
)


@pytest.fixture
def table(tmp_path):
    path = tmp_path / "t.txt"
    path.write_text(TABLE, encoding="utf-8")
    return path


def test_columns_are_found_by_name_and_quotes_are_text(table):
    rows = read_timed_table(table, speaker="Spkr", start="StTime", end="EnTime", text="Content")
    assert rows[0] == TimedRow("A", 0.0, 2.5, 'Well, "they" said so')
    assert len(rows) == 4   # the blank line is skipped


def test_a_missing_column_is_named(table):
    with pytest.raises(ValueError, match="Speaker"):
        read_timed_table(table, speaker="Speaker", start="StTime", end="EnTime", text="Content")


def test_a_bad_time_names_the_row(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("Spkr\tStTime\tContent\tEnTime\nA\tsoon\thi\t1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="row 2"):
        read_timed_table(path, speaker="Spkr", start="StTime", end="EnTime", text="Content")


def test_rows_become_timed_turns_in_time_order_with_ignored_stretches(table):
    rows = read_timed_table(table, speaker="Spkr", start="StTime", end="EnTime", text="Content")

    def clean(text):
        if text.startswith("(pause"):
            return ""
        if text == "skip me":
            return None
        return text

    transcript = rows_to_transcript("R", rows, clean=clean, source="t.txt")
    assert [t.text for t in transcript.turns] == ['Well, "they" said so', "earlier but listed later"]
    assert transcript.turns[1].start == 1.0 and transcript.turns[1].speaker == "A"
    assert transcript.ignore == [(2.7, 4.0)]
    assert transcript.source_pdf == "t.txt"

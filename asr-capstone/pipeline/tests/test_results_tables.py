"""The results tables must declare every column they are given.

`append_csv_row` writes a header only when the file is new and passes
`extrasaction="ignore"`. So a column the declared list leaves out is dropped from
every row, silently - no warning, no error, and a results file that looks
complete. A measure added to `case_row` without a matching entry in
`CASES_COLUMNS` simply does not get recorded.

That is the failure these tests exist to catch, because nothing else will.
"""

from __future__ import annotations

from scotus_asr.scoring.coverage import Silence
from scotus_asr.scoring.metrics import CaseScore, ScoreRow
from scotus_asr.scoring.normalize import NORMALIZERS
from scotus_asr.stages import (
    CASES_COLUMNS,
    OMISSIONS_COLUMNS,
    SCORES_COLUMNS,
    SILENCES_COLUMNS,
)


def _scored() -> CaseScore:
    """A case score carrying one of everything `case_row` can produce."""
    score = CaseScore(
        docket="00-001",
        engine="test-engine",
        model="test",
        audio_minutes=60.0,
        reference_words=10_000,
        hypothesis_words=9_900,
        words_per_minute=170.0,
        speaking_rate_ok=True,
        runtime_seconds=200.0,
        speed_x_realtime=18.0,
    )
    # One row per way of comparing, so every wer_ column appears.
    for name in NORMALIZERS:
        score.rows.append(
            ScoreRow(
                docket="00-001", engine="test-engine", model="test", normalizer=name,
                wer=0.06, hits=9000, substitutions=300, deletions=400, insertions=200,
                reference_tokens=9700, hypothesis_tokens=9500, deletion_rate=0.04,
            )
        )
    score.silences = [Silence(10.0, 40.0), Silence(100.0, 105.0)]
    return score


def test_every_column_case_row_produces_is_declared():
    """The one that matters. An undeclared column is written nowhere."""
    produced = set(_scored().case_row())
    declared = set(CASES_COLUMNS)

    missing = sorted(produced - declared)
    assert not missing, (
        "case_row() produces columns CASES_COLUMNS does not declare, so they "
        "would be dropped from cases.csv without any error:\n  "
        + "\n  ".join(missing)
    )


def test_no_column_is_declared_that_is_never_produced():
    """A declared column that never arrives is written as an empty field.

    Harmless next to the other direction, but it means a reader sees a column of
    blanks and has to work out whether the measure failed or never existed.
    """
    produced = set(_scored().case_row())
    stale = sorted(set(CASES_COLUMNS) - produced)

    assert not stale, f"declared but never produced: {stale}"


def test_a_new_way_of_comparing_needs_no_edit_here():
    """The error-rate columns are built from NORMALIZERS, not typed out."""
    for name in NORMALIZERS:
        assert f"wer_{name}" in CASES_COLUMNS


def test_the_silence_columns_survived_being_added():
    """These were added while cases.csv already existed, which is exactly the
    situation that drops them. They are in the declared list now."""
    for column in ("silent_seconds", "silent_share_percent", "silences_over_10s",
                   "longest_silence_seconds"):
        assert column in CASES_COLUMNS


def test_the_other_tables_declare_what_they_write():
    """Those three always passed a column list; this pins that they still match."""
    score = _scored()
    score.silences = [Silence(10.0, 40.0)]

    assert set(score.rows[0].to_row()) <= set(SCORES_COLUMNS)
    for row in score.silence_rows():
        assert set(row) <= set(SILENCES_COLUMNS)
    # omission_rows needs OmittedSpan objects; the column list is checked for
    # shape rather than by producing one.
    assert "docket" in OMISSIONS_COLUMNS and "audio_start" in OMISSIONS_COLUMNS

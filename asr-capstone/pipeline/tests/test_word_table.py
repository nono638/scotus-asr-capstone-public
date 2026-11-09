"""tools/word_table.py: one row per reference word, built the way crowd.py lines words up.

Uses the made-up court case from test_crowd_golden.py, so the table can be checked
against crowd.py's frozen tables: how many models wrote each word must give the
same counts as heard-by.csv.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from test_crowd_golden import CAPSTONE, GOLDEN, SAID, _make_run

sys.path.insert(0, str(CAPSTONE / "tools"))
import word_table  # noqa: E402


def _table(tmp_path: Path) -> pd.DataFrame:
    runs = tmp_path / "runs"
    paths = {}
    for name, text in SAID.items():
        for recording in ("17-1234", "18-5678"):
            paths[name] = _make_run(runs, name, text, recording)
    out = tmp_path / "words.csv"
    command = [sys.executable, str(CAPSTONE / "tools" / "word_table.py"),
               "--corpus", "scotus", "--out", str(out)]
    for name, path in paths.items():
        command += ["--model", f"{name}={path}"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return pd.read_csv(out)


def test_counts_match_crowds_heard_by_table(tmp_path):
    table = _table(tmp_path)
    ok = table[[c for c in table.columns if c.startswith("ok_")]]
    assert list(ok.columns) == [f"ok_{m}" for m in SAID]
    heard = ok.sum(axis=1).value_counts()
    golden = pd.read_csv(GOLDEN / "heard-by.csv").set_index("heard_by")["words"]
    for n, words in golden.items():
        assert heard.get(n, 0) == words, n


def test_the_conditions_are_filled_in(tmp_path):
    table = _table(tmp_path)
    first = table[table.recording == "17-1234"]
    by_token = first.drop_duplicates("token").set_index("token")
    assert by_token.loc["chevron", "word_type"] == "legal"
    assert by_token.loc["garre", "word_type"] == "name"
    assert by_token.loc["1291", "word_type"] == "number"
    assert by_token.loc["the", "word_type"] == "function"
    assert set(first.role) == {"justice", "advocate"}
    # "Well," opens Justice Kagan's turn right after a dash: both conditions.
    well = first[first.token == "well"].iloc[0]
    assert well.words_to_turn == 0 and well.near_dash == 1
    assert first.local_rate.notna().all() and (first.local_rate > 0).all()


def test_rate_counts_words_in_the_window():
    assert word_table.local_rates([0.0, 1.0, 2.0, 10.0, None]) == [0.5, 0.5, 0.5, 0.167, None]


def test_one_stray_lower_case_word_does_not_make_everything_a_name():
    """EdAcc's C60 has a Vietnamese place name in lower case in an all-capitals
    reference; that switched the name check on and labelled every word a name."""
    import crowd
    capitals = ["HI", "MY", "NAME", "IS", "ANH", "FROM", "đà", "NANG"] * 10
    assert not crowd.can_spot_names(capitals)
    assert crowd.can_spot_names("Mr. Garre, isn't that so?".split())
    assert word_table.word_type("stare", "STARE", set(), False, legal_possible=False) == "content"

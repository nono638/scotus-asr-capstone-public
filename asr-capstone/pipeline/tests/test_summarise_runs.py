"""Tests for tools/summarise_runs.py: pooling each run's own scores into one table."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parents[2]


def make_scored_run(runs_dir: Path, run: str, engine: str, counts: dict) -> None:
    """A run folder with one transcription per recording and its results tables.

    `counts` is {recording: (substitutions, deletions, insertions, reference words,
    audio minutes, seconds taken)}.
    """
    folder = runs_dir / run
    (folder / "asr").mkdir(parents=True)
    (folder / "results").mkdir()
    scores, cases = [], []
    for recording, (s, d, i, ref, minutes, seconds) in counts.items():
        (folder / "asr" / f"{recording}.{engine}.json").write_text("{}", encoding="utf-8")
        for rule in ("standard", "lowercase_nopunct", "verbatim"):
            scores.append({"docket": recording, "engine": engine, "normalizer": rule,
                           "substitutions": s, "deletions": d, "insertions": i,
                           "reference_tokens": ref})
        cases.append({"docket": recording, "engine": engine, "audio_minutes": minutes,
                      "runtime_seconds": seconds})
    pd.DataFrame(scores).to_csv(folder / "results" / "scores.csv", index=False)
    pd.DataFrame(cases).to_csv(folder / "results" / "cases.csv", index=False)


def test_errors_are_pooled_over_every_word(tmp_path):
    """A long recording counts for more than a short one, and speed is overall."""
    runs = tmp_path / "runs"
    # 10 errors in 100 words, then 10 in 900: pooled is 20 in 1000 = 2%,
    # not the 5.6% an average of the two rates would give.
    make_scored_run(runs, "run-a", "engine-a", {"R1": (5, 3, 2, 100, 10.0, 60.0),
                                                "R2": (4, 4, 2, 900, 50.0, 540.0)})
    make_scored_run(runs, "run-b", "engine-b", {"R1": (0, 1, 0, 100, 10.0, 6.0),
                                                "R2": (0, 0, 0, 900, 50.0, 54.0)})
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, str(CAPSTONE / "tools" / "summarise_runs.py"),
                             "--runs-dir", str(runs), "--out", str(out)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr

    engines = pd.read_csv(out / "engines.csv").set_index("engine")
    assert list(engines.index) == ["engine-b", "engine-a"]      # best first
    a = engines.loc["engine-a"]
    assert a.wer_standard == 2.0 and a.recordings == 2
    assert (a.swapped_pct, a.dropped_pct, a.added_pct) == (0.9, 0.7, 0.4)
    assert a.speed_x_realtime == 6.0 and a.audio_hours == 1.0 and a.hours_taken == 0.17

    per = pd.read_csv(out / "per-recording.csv")
    assert len(per) == 4
    assert per.set_index(["engine", "docket"]).loc[("engine-a", "R1"), "wer_standard"] == 10.0


def test_a_ctm_needs_settings_to_know_its_corpus(tmp_path):
    result = subprocess.run([sys.executable, str(CAPSTONE / "tools" / "summarise_runs.py"),
                             "--runs-dir", str(tmp_path), "--out", str(tmp_path / "out"),
                             "--ctm", "company=x.ctm"],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode != 0 and "--config" in result.stderr

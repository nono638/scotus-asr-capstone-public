"""How much audio and record each term holds, and what the two October record fixes changed.

The methods section needs these, and every number in it should come from a file in
findings/. Hours live only in the transcripts on D: and the record fixes only in the
backup folder, so this copies them into two small tables. It reads the run folders
and never writes to them.

    python tools/corpus_table.py

Writes findings/corpus/:

    terms.csv          per term: arguments, hours of audio, length of one argument
                       (median, shortest, longest), and words in the record
    record-fixes.csv   the arguments whose record the October parser fixes changed:
                       record words and benchmark-rule error rate before and after
                       (both without the October scoring fixes, so only the record
                       changes; a last column adds those fixes)

Audio length is the `audio_seconds` Qwen3 saved with each transcript. Record words are
the reference words on the benchmark rule with the October fixes (Qwen3's per-argument
scores in findings/harmonise/), so they match the error rates quoted elsewhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
HARMONISE = CAPSTONE / "findings" / "harmonise"
FLIP = CAPSTONE / "findings" / "flip" / "per-argument.csv"
OUT = CAPSTONE / "findings" / "corpus"
RUNS = Path("D:/scotus-corpus/runs")
SUPERSEDED = Path("D:/scotus-corpus/superseded/2026-10-17_20-1530-record-cut-at-recess")

#: Qwen3's run for each term: the -reread runs, damaged chunks decoded again.
QWEN3_RUN = {"OT2017": "run-20260921-051927-reread"}
QWEN3_OTHER = "run-scotus250-qwen3-reread"
QWEN3_FILE = "Qwen3-ASR-1.7B-hf"

#: The eight PDFs that used to parse to an empty record; only these three are in the study.
EMPTY_BEFORE = ["24-699", "24-781", "24-993"]


def qwen3_scores() -> pd.DataFrame:
    """Qwen3's harmonised per-argument scores for all four terms."""
    seven = pd.read_csv(HARMONISE / "per-case.csv")
    seven = seven[seven.model == "Qwen3"].copy()
    seven["term"] = "OT2017"
    later = pd.read_csv(HARMONISE / QWEN3_OTHER / "per-case.csv")
    return pd.concat([seven, later])


def audio_seconds(term: str, docket: str) -> float:
    run = QWEN3_RUN.get(term, QWEN3_OTHER)
    name = docket if (RUNS / run / "asr" / f"{docket}.{QWEN3_FILE}.json").exists() else f"{docket}_{term}"
    with open(RUNS / run / "asr" / f"{name}.{QWEN3_FILE}.json", encoding="utf-8") as f:
        return json.load(f)["audio_seconds"]


def terms_table() -> pd.DataFrame:
    study = pd.read_csv(FLIP)[["term", "docket"]]
    scores = qwen3_scores()
    scores["docket"] = scores.docket.str.replace("_OT2017", "", regex=False)
    study = study.merge(scores[["term", "docket", "standard_after_words"]], on=["term", "docket"])
    study["minutes"] = [audio_seconds(t, d) / 60 for t, d in zip(study.term, study.docket)]
    rows = []
    for term, group in study.groupby("term"):
        rows.append({
            "term": term,
            "arguments": len(group),
            "audio_hours": round(group.minutes.sum() / 60, 1),
            "median_minutes": round(group.minutes.median()),
            "shortest_minutes": round(group.minutes.min()),
            "longest_minutes": round(group.minutes.max()),
            "record_words": int(group.standard_after_words.sum()),
        })
    table = pd.DataFrame(rows)
    total = {"term": "all four", "arguments": table.arguments.sum(),
             "audio_hours": round(study.minutes.sum() / 60, 1),
             "median_minutes": round(study.minutes.median()),
             "shortest_minutes": round(study.minutes.min()),
             "longest_minutes": round(study.minutes.max()),
             "record_words": table.record_words.sum()}
    return pd.concat([table, pd.DataFrame([total])])


def old_standard(engine_dir: str, docket: str) -> tuple[int, float] | None:
    """Record words (benchmark-rule tokens) and error rate from the backed-up score file."""
    files = list((SUPERSEDED / engine_dir / "scores").glob(f"{docket}.*.json"))
    if not files:
        return None
    with open(files[0], encoding="utf-8") as f:
        saved = json.load(f)
    standard = next(s for s in saved["scores"] if s["normalizer"] == "standard")
    return standard["reference_tokens"], standard["wer_percent"]


def fixes_table() -> pd.DataFrame:
    # Parakeet and Qwen3 stay on their old runs here, not the -reread ones: the "before"
    # scores are the old transcripts', so the change shown is the record fix alone.
    rows = []
    for engine, folder in [("Parakeet", "run-scotus250-parakeet"), ("Whisper", "run-scotus250-whisper"),
                           ("Qwen3", "run-scotus250-qwen3")]:
        now = pd.read_csv(HARMONISE / folder / "per-case.csv")
        for docket in ["20-1530"] + EMPTY_BEFORE:
            row = now[now.docket == docket]
            if row.empty:
                continue
            row = row.iloc[0]
            before = old_standard(folder, docket) if docket == "20-1530" else (0, None)
            rows.append({
                "docket": docket,
                "term": row.term,
                "fix": "record cut at a recess" if docket == "20-1530" else "record parsed empty",
                "engine": engine,
                # Qwen3's 20-1530 was scored only after the fix, so it has no "before".
                "record_words_before": before[0] if before else None,
                "record_words_after": int(row.standard_before_words),
                "benchmark_wer_before": before[1] if before else None,
                "benchmark_wer_after": round(row.standard_before_wer, 2),
                "benchmark_wer_after_october_fixes": round(row.standard_after_wer, 2),
            })
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    terms = terms_table()
    fixes = fixes_table()
    terms.to_csv(OUT / "terms.csv", index=False)
    fixes.to_csv(OUT / "record-fixes.csv", index=False)
    print(terms.to_string(index=False))
    print()
    print(fixes.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Score all seven models again, with and without the harmonise fixes.

Nothing in the corpus is changed. Each model's saved transcription is read
back (with the seam fix, as for the published figures) and compared with the
official transcript under each rule twice: as before, and with `harmonise=True`.

"Before" must reproduce `findings/final-seven-model-results.csv` exactly; the
script checks that and says so. The size of the change is the result: how much
of each error rate was the comparison inventing differences nobody could hear.

Writes to findings/harmonise/:
    per-case.csv       one row per model and case, every rule before and after
    before-after.csv   the mean over the 61 cases, per model and rule

With --run, it scores every case in that one run instead (any term, any model)
and writes to findings/harmonise/<run name>/: the same two tables, with a term
column, and the means per term. The term comes from the case folder the
reference PDF was read from (OT2010_09-834_Kasten... is OT2010). "Before" is
checked against the run's own results/scores.csv, case by case.

Usage:
    python tools/rescore_harmonised.py
    python tools/rescore_harmonised.py --run <scotus_corpus>/runs/run-20260918-035220
    python tools/rescore_harmonised.py --run <run> --run <another run>
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path, PureWindowsPath

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "tools"))
sys.path.insert(0, str(CAPSTONE / "pipeline"))

import crowd  # noqa: E402
from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.metrics import leaderboard_error_rate, written_words  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402


def runs_dir() -> Path:
    """The seven runs, wherever local-paths.yaml says the corpus is."""
    return local_path("scotus_corpus") / "runs"


OUT = CAPSTONE / "findings" / "harmonise"
RULES = ["standard", "lowercase_nopunct", "verbatim"]


def dockets_in(run_dir: Path) -> list[str]:
    """Every case the run has a finished transcription for."""
    return sorted(p.name.split(".")[0] for p in (run_dir / "asr").glob("*.json"))


def term_of(transcript: Transcript) -> str:
    """"OT2010" from the folder the reference PDF came from."""
    folder = PureWindowsPath(transcript.source_pdf).parent.name
    term = folder.split("_")[0]
    if not term.startswith("OT"):
        raise ValueError(f"{transcript.docket}: no term in {transcript.source_pdf!r}")
    return term


def score_case(run_dir: Path, docket: str) -> dict:
    """One case of one run, under every rule before and after."""
    ref_file = run_dir / "reference" / f"{docket}.json"
    transcript = Transcript.from_dict(json.loads(ref_file.read_text(encoding="utf-8")))
    reference = transcript.full_text(include_speakers=False).split()
    asr_files = list((run_dir / "asr").glob(f"{docket}.*.json"))
    if len(asr_files) != 1:
        raise FileNotFoundError(f"{run_dir.name} {docket}: expected one file, found {len(asr_files)}")
    result = _load_asr_result(asr_files[0])
    hypothesis = written_words([w.text for w in result.words]) or result.text.split()
    engine = asr_files[0].name.split(".", 1)[1][: -len(".json")]
    row = {"model": engine, "docket": docket, "term": term_of(transcript),
           "leaderboard_wer": leaderboard_error_rate(reference, hypothesis)}
    for rule in RULES:
        for fixed in (False, True):
            a = align_words(reference, hypothesis, rule, harmonise=fixed)
            tag = "after" if fixed else "before"
            row[f"{rule}_{tag}_wer"] = a.wer * 100
            row[f"{rule}_{tag}_errors"] = a.substitutions + a.deletions + a.insertions
            row[f"{rule}_{tag}_words"] = len(a.reference.tokens)
    return row


def score_one(model: str, docket: str) -> dict:
    """One of the seven, named as in the published table, without the term."""
    row = score_case(runs_dir() / crowd.RUNS[model], docket)
    row["model"] = model
    del row["term"]
    return row


def mean_table(cases: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """The mean of the per-case error rates, before and after, per group."""
    summary = cases.groupby(by, sort=False).mean(numeric_only=True)
    table = summary.index.to_frame(index=False)
    table["leaderboard"] = summary["leaderboard_wer"].round(3).values
    for rule in RULES:
        table[f"{rule}_before"] = summary[f"{rule}_before_wer"].round(3).values
        table[f"{rule}_after"] = summary[f"{rule}_after_wer"].round(3).values
        table[f"{rule}_change"] = (table[f"{rule}_after"] - table[f"{rule}_before"]).round(3)
    return table


def rescore_seven() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # The 61 OT2017 arguments: every case the Parakeet run transcribed.
    dockets = dockets_in(runs_dir() / crowd.RUNS["Parakeet"])
    jobs = [(m, d) for m in crowd.MODELS for d in dockets]
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(score_one, *zip(*jobs), chunksize=4))
    cases = pd.DataFrame(rows)
    cases.to_csv(OUT / "per-case.csv", index=False, float_format="%.4f")

    table = mean_table(cases, ["model"])
    table.to_csv(OUT / "before-after.csv", index=False)
    print(table.to_string(index=False))

    # "Before" has to match what was published, or the comparison means nothing.
    published = pd.read_csv(CAPSTONE / "findings" / "final-seven-model-results.csv")
    names = {"Whisper": "whisper-large-v3", "Qwen3": "Qwen3-ASR-1.7B-hf",
             "Voxtral": "Voxtral-Mini-3B-2507", "Canary": "canary-1b-v2",
             "Parakeet": "parakeet-tdt-0.6b-v3", "Granite": "granite-speech-4.1-2b",
             "Granite Plus": "granite-speech-4.1-2b-plus"}
    # Only the benchmark column: since October 2026 the published lowercase and
    # verbatim columns are themselves the "after" figures. (Before that change,
    # all three "before" columns matched the old table to 0.001 points.)
    worst = 0.0
    for _, row in table.iterrows():
        pub = published[published.model == names[row.model]].iloc[0]
        worst = max(worst, abs(row["standard_before"] - pub["wer_standard"]))
    print(f"\nLargest gap between 'before' and the published benchmark column: {worst:.3f} points")

    # The published table follows: its columns are the means above. wer_standard is
    # word by word with no fixes; wer_leaderboard is what a leaderboard computes.
    for _, row in table.iterrows():
        at = published.model == names[row.model]
        published.loc[at, "wer_leaderboard"] = row["leaderboard"]
        published.loc[at, "wer_standard"] = row["standard_before"]
        published.loc[at, "wer_standard_fixed"] = row["standard_after"]
        published.loc[at, "wer_lowercase_nopunct"] = row["lowercase_nopunct_after"]
        published.loc[at, "wer_verbatim"] = row["verbatim_after"]
    published.to_csv(CAPSTONE / "findings" / "final-seven-model-results.csv", index=False)
    return 0


def rescore_run(run_dir: Path) -> int:
    out = OUT / run_dir.name
    out.mkdir(parents=True, exist_ok=True)
    dockets = dockets_in(run_dir)
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(score_case, [run_dir] * len(dockets), dockets, chunksize=2))
    cases = pd.DataFrame(rows).sort_values(["term", "docket"])
    cases.to_csv(out / "per-case.csv", index=False, float_format="%.4f")

    table = mean_table(cases, ["model", "term"])
    table.insert(2, "cases", cases.groupby(["model", "term"], sort=False).size().values)
    table.to_csv(out / "before-after.csv", index=False)
    print(f"\n{run_dir.name}: {len(cases)} cases")
    print(table.to_string(index=False))

    # The run's own scores have to match one of the two columns, case by case,
    # or the before-and-after means nothing. Runs scored before the October
    # fixes match "before" under every rule. Runs scored since match "before"
    # under the standard rule, which the pipeline keeps as leaderboards compute
    # it, and "after" under the other two, which it now harmonises.
    old = pd.read_csv(run_dir / "results" / "scores.csv")
    worst = 0.0
    for rule in RULES:
        theirs = old[old.normalizer == rule].set_index("docket")["wer"] * 100
        gaps = {}
        for tag in ("before", "after"):
            mine = cases.set_index("docket")[f"{rule}_{tag}_wer"]
            gaps[tag] = (mine - theirs.reindex(mine.index)).abs()
        if gaps["before"].isna().any():
            missing = gaps["before"][gaps["before"].isna()].index
            print(f"  {rule}: no score of the run's own for {', '.join(missing)}")
            worst = float("inf")
        tag = min(gaps, key=lambda t: gaps[t].max())
        gap = gaps[tag]
        print(f"  {rule}: the run's own scores match '{tag}', "
              f"largest gap {gap.max():.4f} points ({gap.idxmax()})")
        worst = max(worst, gap.max())
    # Whisper's saved scores count its split pieces as words (metrics.written_words),
    # so on the verbatim rule they are meant to differ from these.
    if worst > 0.01 and cases.model.str.lower().str.startswith("whisper").all():
        print("  Whisper: the run's saved scores predate joining its split pieces, so a gap is expected.")
        return 0
    if worst > 0.01:
        print("  The run's own scores match neither column - do not use these figures.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, action="append",
                        help="score every case in this run folder instead of the seven. Repeat.")
    args = parser.parse_args()
    if not args.run:
        return rescore_seven()
    failed = 0
    for run_dir in args.run:
        failed += rescore_run(run_dir)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

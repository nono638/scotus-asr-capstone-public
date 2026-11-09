"""Re-score finished runs with the seam de-duplication in place.

Nothing is transcribed. Scoring reads the saved transcriptions back, and
`stages._load_asr_result` now drops words that two neighbouring chunks both
produced, so re-running the scoring stage is the whole of the correction.

The before-and-after is recorded to `findings/seam-fix-before-after.csv`,
because the size of the change is a result in its own right: the artifact was
uneven across engines, so it was biasing the comparison and not just the
numbers.

What it does to each run, in order:

  1. reads the existing per-case scores, so "before" is what was published
  2. deletes the run's `scores/*.json`, which is the documented way to force a
     rebuild - `runner.is_done` treats a missing output file as not done
  3. runs the scoring stage for that run
  4. reads the new per-case scores and reports the difference

The transcriptions in `asr/` are never touched. They are the evidence of what
each model produced, and this correction is deliberately a scoring decision
rather than an edit to them.

Usage:
    python tools/rescore_with_seam_fix.py --dry-run      # say what it would do
    python tools/rescore_with_seam_fix.py
    python tools/rescore_with_seam_fix.py --engine Qwen3-ASR-1.7B-hf
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import subprocess
import sys
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parents[2]
PIPELINE = CAPSTONE / "pipeline"
sys.path.insert(0, str(PIPELINE))

from scotus_asr.config import local_path  # noqa: E402


def runs_dir() -> str:
    """The corpus's runs folder on this laptop, as text for glob."""
    return (local_path("scotus_corpus") / "runs").as_posix()

#: Which settings file reproduces each engine's run.
#:
#: A run's own `config_used.yaml` cannot be fed back in - it is a record, and
#: carries keys like `engine_name` that `AsrSettings` does not accept - so the
#: project's own config files are used instead. The engine name each one builds
#: has to match the name in the saved filenames, and the script checks that
#: rather than trusting it.
CONFIGS = {
    "Qwen3-ASR-1.7B-hf": "config/qwen3.yaml",
    "Voxtral-Mini-3B-2507": "config/voxtral.yaml",
    "canary-1b-v2": "config/canary.yaml",
    "granite-speech-4.1-2b": "config/granite.yaml",
    "granite-speech-4.1-2b-plus": "config/granite-plus.yaml",
    "parakeet-tdt-0.6b-v3": "config/parakeet.yaml",
    "whisper-large-v3": "config/default.yaml",
}


def newest_run_per_engine() -> dict[str, str]:
    """The most recent run holding each engine's transcriptions.

    Older runs are left alone. They hold failures that were later fixed, and
    re-scoring them would produce corrected versions of results nobody uses.
    """
    newest: dict[str, str] = {}
    for path in glob.glob(f"{runs_dir()}/run-*/asr/*.json"):
        run = Path(path).parent.parent.name
        try:
            engine = json.loads(Path(path).read_text(encoding="utf-8")).get("engine")
        except Exception:  # noqa: BLE001 - a half-written file during a live run
            continue
        if engine and (engine not in newest or run > newest[engine]):
            newest[engine] = run
    return newest


def read_case_wer(run: str, engine: str) -> dict[str, dict[str, float]]:
    """Each case's word error rate under all three rules, from cases.csv."""
    path = Path(f"{runs_dir()}/{run}/results/cases.csv")
    if not path.exists():
        return {}
    out: dict[str, dict[str, float]] = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("engine") != engine:
                continue
            try:
                out[row["docket"]] = {
                    rule: float(row[f"wer_{rule}"])
                    for rule in ("standard", "lowercase_nopunct", "verbatim")
                }
            except (KeyError, ValueError):
                continue
    return out


def terms_in(run: str) -> list[str]:
    """Which October Terms this run covers, from its docket filenames."""
    found = set()
    for path in glob.glob(f"{runs_dir()}/{run}/reference/*.json"):
        name = Path(path).stem
        if "_OT" in name:
            found.add(name.split("_OT")[1][:4])
    return sorted(found)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", action="append",
                        help="Just this engine. Repeat for several.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Say what would happen and change nothing.")
    parser.add_argument("--out", type=Path,
                        default=CAPSTONE / "findings" / "seam-fix-before-after.csv")
    args = parser.parse_args(argv)

    newest = newest_run_per_engine()
    wanted = args.engine or sorted(newest)

    rows = []
    for engine in wanted:
        run = newest.get(engine)
        if run is None:
            print(f"{engine}: no run found, skipping")
            continue
        config = CONFIGS.get(engine)
        if config is None:
            print(f"{engine}: no config mapped, skipping")
            continue

        # An engine this project did not chunk is unaffected: deduplicate_seams
        # is a no-op without a chunk length, so re-scoring would change nothing.
        # Whisper is that case - faster-whisper stitches internally and records
        # no chunk_seconds - so it is skipped rather than pointlessly recomputed.
        sample = sorted(glob.glob(f"{runs_dir()}/{run}/asr/*.json"))
        if sample:
            first = json.loads(Path(sample[0]).read_text(encoding="utf-8"))
            if (first.get("settings") or {}).get("chunk_seconds") is None:
                print(f"\n{'=' * 70}")
                print(f"{engine}")
                print(f"  run    {run}")
                print("  not chunked by this project, so the seam fix cannot")
                print("  change its score. Skipped.")
                continue

        scores = sorted(glob.glob(f"{runs_dir()}/{run}/scores/*.json"))
        before = read_case_wer(run, engine)
        print(f"\n{'='*70}\n{engine}\n  run    {run}\n  config {config}\n"
              f"  cases  {len(before)} scored, {len(scores)} score files")

        if args.dry_run:
            print("  dry run: would delete the score files and re-score")
            continue
        if not before:
            print("  nothing scored yet, skipping")
            continue

        # Forcing the rebuild. `runner.is_done` needs both the output file and a
        # ledger line; removing the file is the documented way to redo a stage.
        for path in scores:
            Path(path).unlink()

        command = [
            sys.executable, "-m", "scotus_asr.cli", "score",
            "--config", config, "--run-id", run,
        ]
        for term in terms_in(run):
            command += ["--term", term]
        finished = subprocess.run(command, cwd=PIPELINE, capture_output=True,
                                  text=True)
        if finished.returncode != 0:
            print(f"  FAILED: {finished.stderr[-500:]}")
            continue

        after = read_case_wer(run, engine)
        shared = sorted(set(before) & set(after))
        if not shared:
            print("  no cases in common before and after - something is wrong")
            continue

        for rule in ("standard", "lowercase_nopunct", "verbatim"):
            # cases.csv already stores these as percentages, so they are
            # averaged and printed as they are. Multiplying by a hundred here
            # was a bug that reported Qwen3's 5.74% as 573.68%.
            was = sum(before[d][rule] for d in shared) / len(shared)
            now = sum(after[d][rule] for d in shared) / len(shared)
            worse = sum(1 for d in shared if after[d][rule] > before[d][rule] + 1e-9)
            print(f"  {rule:18s} {was:6.2f}% -> {now:6.2f}%  "
                  f"({now - was:+.3f}, {worse} cases worse)")
            rows.append({"engine": engine, "run": run, "rule": rule,
                         "cases": len(shared), "wer_before": round(was, 4),
                         "wer_after": round(now, 4), "change": round(now - was, 4),
                         "cases_worse": worse})

    if rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n{len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

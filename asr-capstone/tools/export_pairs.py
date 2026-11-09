"""Turn a finished run into a side-by-side comparison of record against machine.

Reads the reference and the machine transcription a run already wrote, re-aligns
them, and saves the result as CSV. No GPU, no re-transcription - about a second
per case.

Two files come out of it, into the run's own `results/` folder:

  word_pairs.csv         every chunk, agreement and difference alike
  word_pairs_errors.csv  differences only, which is the one to open first

Usage:
    python tools/export_pairs.py                     # the newest run
    python tools/export_pairs.py --run run-20260916-041602
    python tools/export_pairs.py --normalizer standard
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.scoring.normalize import NORMALIZERS  # noqa: E402
from scotus_asr.scoring.pairs import word_pairs, write_pairs  # noqa: E402
# The same loader the score stage uses. It drops words that two neighbouring
# chunks both transcribed. This script used to read the JSON itself and skipped
# that step, so its tables disagreed with scores.csv for the chunked engines.
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="Run folder name. Default: the newest one.")
    parser.add_argument(
        "--runs-dir", type=Path,
        help="Where the runs live. Default: <scotus_corpus>/runs, from "
             "local-paths.yaml. The three "
             "hand-checked sample cases are in the repository's own runs/ folder.",
    )
    parser.add_argument(
        "--normalizer",
        default="all",
        choices=["all", *NORMALIZERS],
        help="How to compare. Default: all three, with a column saying which.",
    )
    args = parser.parse_args()

    runs_dir = args.runs_dir or local_path("scotus_corpus") / "runs"
    if args.run:
        run_dir = runs_dir / args.run
    else:
        candidates = sorted(p for p in runs_dir.glob("run-*") if p.is_dir())
        if not candidates:
            print(f"No runs found in {runs_dir}")
            return 1
        run_dir = candidates[-1]

    if not run_dir.is_dir():
        print(f"No such run: {run_dir}")
        return 1

    print(f"Run: {run_dir.name}")

    names = list(NORMALIZERS) if args.normalizer == "all" else [args.normalizer]
    all_rows = []

    for asr_path in sorted((run_dir / "asr").glob("*.json")):
        docket = asr_path.name.split(".")[0]
        reference_path = run_dir / "reference" / f"{docket}.json"
        if not reference_path.exists():
            print(f"  {docket}: no reference on disk, skipping")
            continue

        transcript = Transcript.from_dict(
            json.loads(reference_path.read_text(encoding="utf-8"))
        )
        result = _load_asr_result(asr_path)
        words, engine = result.words, result.engine
        if not words:
            print(f"  {docket}: no word timings, skipping")
            continue

        for name in names:
            rows = word_pairs(
                transcript, words, docket=docket, engine=engine, normalizer=name
            )
            all_rows.extend(rows)
            errors = sum(1 for row in rows if row.kind != "equal")
            print(f"  {docket} [{name}]: {len(rows)} chunks, {errors} differences")

    if not all_rows:
        print("Nothing to write.")
        return 1

    results = run_dir / "results"
    full = results / "word_pairs.csv"
    errors_only = results / "word_pairs_errors.csv"

    written = write_pairs(all_rows, full)
    written_errors = write_pairs((r for r in all_rows if r.kind != "equal"), errors_only)

    print(f"\n{written} rows -> {full}")
    print(f"{written_errors} rows -> {errors_only}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

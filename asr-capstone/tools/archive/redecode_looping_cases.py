"""Transcribe again the cases whose saved output still contains a loop.

A duplicated word at a seam can be corrected after the fact, because the word is
there and only needs removing. A repetition loop cannot: the words a model
should have written were never written, so the only fix is to decode the audio
again. This does that, for the few cases that need it.

The cases are chosen by `looks_like_a_loop`, which now includes the back-to-back
repetition test. That test is what makes this worth doing - it finds loops the
word-rate and compression tests are shaped wrong for, a chunk that transcribes
real argument and then repeats one phrase. Parakeet's 16-498 holds "the case of"
263 words deep inside an otherwise ordinary chunk.

Running it again is not pointless even where nothing about that engine changed,
because the remedy now fires where it previously did not: a flagged chunk is
decoded hotter for most engines, and split in half for Parakeet and Granite Plus.

The old transcription is copied to `asr-before-phase2/` inside the run first.
Nothing is thrown away - a re-decode that comes back worse has to be visible.

Usage:
    python tools/redecode_looping_cases.py --dry-run
    python tools/redecode_looping_cases.py
    python tools/redecode_looping_cases.py --engine parakeet-tdt-0.6b-v3
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parents[2]
PIPELINE = CAPSTONE / "pipeline"
sys.path.insert(0, str(PIPELINE))

PLAN = CAPSTONE / "findings" / "phase2-redecode-plan.json"


def loops_in(path: Path) -> list[tuple[int, str]]:
    """Which chunks of one saved transcription still look like a loop."""
    from scotus_asr.asr.base import looks_like_a_loop

    data = json.loads(path.read_text(encoding="utf-8"))
    found = []
    for segment in data.get("segments") or []:
        text = segment["text"]
        if len(text.split()) < 20:
            continue
        caught, why = looks_like_a_loop(text, segment["end"] - segment["start"])
        if caught:
            found.append((segment["index"], why))
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", action="append", help="Just this engine.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args(argv)
    from scotus_asr.config import local_path

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    wanted = args.engine or sorted(plan)

    summary = []
    for engine in wanted:
        entry = plan.get(engine)
        if entry is None:
            print(f"{engine}: not in the plan, skipping")
            continue
        run, config, dockets = entry["run"], entry["config"], entry["cases"]
        run_dir = local_path("scotus_corpus") / "runs" / run
        backup = run_dir / "asr-before-phase2"

        print(f"\n{'=' * 72}")
        print(f"{engine}")
        print(f"  run    {run}")
        print(f"  config {config}")
        print(f"  cases  {', '.join(dockets)}")

        before = {}
        for docket in dockets:
            path = run_dir / "asr" / f"{docket}.{engine}.json"
            if path.exists():
                before[docket] = loops_in(path)

        for docket, found in before.items():
            for index, why in found:
                print(f"    {docket} chunk {index}: {why}")

        if args.dry_run:
            print("  dry run: would back up, delete and decode again")
            continue

        # Keep the old transcription. A re-decode that comes back worse must be
        # visible rather than lost.
        backup.mkdir(parents=True, exist_ok=True)
        for docket in dockets:
            for folder, suffix in (("asr", ".json"), ("scores", ".json")):
                path = run_dir / folder / f"{docket}.{engine}{suffix}"
                if path.exists():
                    shutil.copy2(path, backup / f"{folder}-{path.name}")
                    # Removing the output is how `runner.is_done` is told to
                    # redo a stage; the ledger line stays as the record.
                    path.unlink()

        command = [sys.executable, "-m", "scotus_asr.cli", "run",
                   "--config", config, "--run-id", run]
        for docket in dockets:
            command += ["--case", docket]
        finished = subprocess.run(command, cwd=PIPELINE, capture_output=True,
                                  text=True)
        if finished.returncode != 0:
            print(f"  FAILED: {finished.stderr[-800:]}")
            continue

        for docket in dockets:
            path = run_dir / "asr" / f"{docket}.{engine}.json"
            if not path.exists():
                print(f"    {docket}: no output written")
                continue
            after = loops_in(path)
            was = len(before.get(docket, []))
            now = len(after)
            verdict = ("fixed" if now == 0 else
                       "improved" if now < was else
                       "unchanged" if now == was else "WORSE")
            print(f"    {docket}: {was} looping chunk(s) -> {now}  [{verdict}]")
            for index, why in after:
                print(f"        chunk {index} still: {why}")
            summary.append((engine, docket, was, now, verdict))

    if summary:
        print(f"\n{'=' * 72}")
        fixed = sum(1 for *_, v in summary if v == "fixed")
        worse = [s for s in summary if s[-1] == "WORSE"]
        print(f"{len(summary)} cases decoded again, {fixed} now clean")
        if worse:
            print("came back worse, and the old version is in asr-before-phase2/:")
            for engine, docket, was, now, _ in worse:
                print(f"  {engine} {docket}: {was} -> {now}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

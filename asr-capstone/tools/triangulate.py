"""Ask every model that transcribed a recording about the same seconds of it.

Where one model wrote nothing and the others wrote words, the audio was
evidently transcribable and the fault is that model's. Where every model wrote
nothing, the audio is the suspect and somebody has to listen.

That is the point of this: it sorts the stretches nobody transcribed into the
ones a comparison settles and the small number it cannot.

Loads no audio. The silences come from each transcription's own word timings and
the speech figures from `silence_speech.csv`, both already on disk, so this runs
in seconds rather than the half hour `check_silences.py` takes.

Writes `triangulation.csv` into each run's results folder, holding that run's own
verdicts, so every run owns its findings the way it owns everything else.

Usage:
    python tools/triangulate.py
    python tools/triangulate.py --runs-dir <scotus_corpus>/runs
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.scoring.agreement import ALL_SILENT, THIS_ENGINE_ONLY, compare  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.scoring.coverage import find_silences  # noqa: E402

COLUMNS = [
    "docket", "engine", "start", "seconds", "speech_seconds",
    "engines_asked", "engines_silent", "verdict", "needs_an_ear", "start_clock",
]


def clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def silences_from(path: Path):
    """One transcription's silences, from its own word timings.

    Through the score stage's own loader, so seam duplicates are dropped and
    these silences match silences.csv and check_silences.py.
    """
    result = _load_asr_result(path)
    if not result.words:
        return []
    return find_silences(result.words, float(result.audio_seconds))

def speech_heard(run: Path) -> dict[tuple[str, str], dict[float, float]]:
    """How much speech a detector found in each silence, by (docket, engine)."""
    path = run / "results" / "silence_speech.csv"
    if not path.exists():
        return {}
    found: dict[tuple[str, str], dict[float, float]] = defaultdict(dict)
    with open(path, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            found[(row["docket"], row["engine"])][
                round(float(row["silence_start"]), 2)
            ] = float(row["speech_seconds"])
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path,
                        help="default: <scotus_corpus>/runs, from local-paths.yaml")
    parser.add_argument(
        "--min-share", type=float, default=0.5,
        help="How much of a stretch another model must also leave empty before "
             "it counts as silent there. Default 0.5.",
    )
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="RUN",
        help="Skip this run folder. Repeat for several. Use it for a run still "
             "being written: a half-finished re-run of a model would supersede "
             "the finished one for the cases it has reached and not for the "
             "rest, mixing two experiments in one column.",
    )
    args = parser.parse_args()
    if args.runs_dir is None:
        args.runs_dir = local_path("scotus_corpus") / "runs"

    # Every transcription on disk, grouped by the recording it came from, and
    # then by which model made it.
    #
    # One entry per (recording, model), and the newest run wins. A model can have
    # transcribed the same case more than once - a re-run after a fix, or a
    # single-case trial while an engine was being built - and counting both would
    # tell the comparison that five models were asked when four were, with one of
    # them voting twice. Keeping the newest is also what a re-run is for.
    #
    # Run folders are named `run-<timestamp>`, so sorting by name is sorting by
    # age, and a later assignment replaces an earlier one.
    latest: dict[str, dict[str, tuple[Path, Path]]] = defaultdict(dict)
    superseded = 0
    for run in sorted(r for r in args.runs_dir.glob("run-*") if r.name not in args.exclude):
        for path in sorted((run / "asr").glob("*.json")):
            if "partial" in path.name:
                continue
            docket = path.name.split(".")[0]
            engine = path.name.split(".", 1)[1].rsplit(".json", 1)[0]
            superseded += engine in latest[docket]
            latest[docket][engine] = (run, path)

    work: dict[str, list[tuple[Path, Path, str]]] = {
        docket: [(run, path, engine) for engine, (run, path) in by_engine.items()]
        for docket, by_engine in latest.items()
    }
    if superseded:
        print(f"{superseded} earlier transcription(s) superseded by a later run "
              f"of the same model.")

    heard = {run: speech_heard(run) for run in sorted(r for r in args.runs_dir.glob("run-*") if r.name not in args.exclude)}

    compared = {d: rows for d, rows in work.items() if len(rows) > 1}
    print(f"{len(work)} recordings on disk, {len(compared)} transcribed by more "
          f"than one model\n")
    if not compared:
        print("Nothing to compare. Run a second engine over the same cases first.")
        return 1

    rows: dict[Path, list[dict]] = defaultdict(list)
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for docket, entries in sorted(compared.items()):
        by_engine = {engine: silences_from(path) for _, path, engine in entries}
        speech = {
            engine: heard.get(run, {}).get((docket, engine), {})
            for run, _, engine in entries
        }
        run_of = {engine: run for run, _, engine in entries}

        for verdict in compare(by_engine, speech, min_share=args.min_share):
            rows[run_of[verdict.engine]].append({
                "docket": docket,
                "engine": verdict.engine,
                "start": verdict.start,
                "seconds": verdict.seconds,
                "speech_seconds": verdict.speech_seconds,
                "engines_asked": verdict.engines_asked,
                "engines_silent": verdict.engines_silent,
                "verdict": verdict.verdict,
                "needs_an_ear": verdict.needs_an_ear,
                "start_clock": clock(verdict.start),
            })
            counts = totals[verdict.engine]
            counts[verdict.verdict] += 1
            counts["needs_an_ear"] += int(verdict.needs_an_ear)

    for run, run_rows in rows.items():
        out = run / "results" / "triangulation.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(run_rows)
        print(f"{len(run_rows):>7,} verdicts -> {out}")

    print(f"\n{'model':26} {'silences':>9} {'its own':>9} {'all silent':>11}"
          f" {'needs an ear':>13}")
    for engine, counts in sorted(totals.items()):
        judged = sum(v for k, v in counts.items() if k != "needs_an_ear")
        print(f"{engine:26} {judged:9,} {counts[THIS_ENGINE_ONLY]:9,}"
              f" {counts[ALL_SILENT]:11,} {counts['needs_an_ear']:13,}")

    print("\n'Its own' means other models transcribed those seconds - no listening")
    print("needed to know whose failure it was. 'Needs an ear' means every model")
    print("was silent and something there sounds like speech.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

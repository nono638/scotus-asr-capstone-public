"""Ask a speech detector what is in the audio each model left untranscribed.

The coverage measure says how many seconds of a recording carry no word. It
cannot say whether that is a pause or argument nobody wrote down. This runs
Silero VAD over the audio and answers that, per silence and per case.

One recording, loaded once, checked against every engine that transcribed it -
the audio is the same file whichever model was pointed at it, and loading a
ninety-minute MP3 is the slow part.

Writes `silence_speech.csv` into each run's results folder: one row per silence,
with how much of it sounds like speech and where to listen.

Usage:
    python tools/check_silences.py --runs-dir <scotus_corpus>/runs
    python tools/check_silences.py --runs-dir <scotus_corpus>/runs --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.asr.base import Word  # noqa: E402
from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.scoring.coverage import find_silences  # noqa: E402
from scotus_asr.scoring.speech import (  # noqa: E402
    judge_silences,
    load_audio,
    speech_regions,
    summarize_verdicts,
)
from scotus_asr.scoring.speech import SAMPLE_RATE, level_dbfs  # noqa: E402

COLUMNS = [
    "docket", "engine", "silence_start", "silence_seconds",
    "speech_seconds", "speech_share", "holds_speech",
    # How loud the stretch is, and how that compares to the recording it sits
    # in. The relative figure is the useful one: speech a microphone barely
    # caught sits far below its recording's level, speech at normal level that a
    # model did not write down sits at it. Levels differ across a corpus
    # spanning fifteen years, so an absolute number would not travel.
    "level_dbfs", "level_vs_recording_db",
    "start_clock",
]


def clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def words_from(path: Path) -> tuple[list[Word], float]:
    """Read one transcription back as a flat word list.

    Through the score stage's own loader, so words two neighbouring chunks both
    transcribed are dropped here too. Without that, a seam duplicate covers a
    gap and these silences disagree with silences.csv.
    """
    result = _load_asr_result(path)
    return result.words, float(result.audio_seconds)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path,
                        help="default: <scotus_corpus>/runs, from local-paths.yaml")
    parser.add_argument("--cases-dir", type=Path,
                        help="default: <scotus_corpus>/cases, from local-paths.yaml")
    parser.add_argument("--limit", type=int, help="Stop after this many recordings.")
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
    if args.cases_dir is None:
        args.cases_dir = local_path("scotus_corpus") / "cases"

    manifest = json.loads(
        (args.cases_dir / "manifest.json").read_text(encoding="utf-8")
    )
    folder_of = {e["case_id"]: e for e in manifest}

    # Every transcription on disk, grouped by the case it came from, so each
    # recording is loaded and checked once however many models transcribed it.
    work: dict[str, list[tuple[Path, Path]]] = {}
    for run in sorted(r for r in args.runs_dir.glob("run-*") if r.name not in args.exclude):
        for path in sorted((run / "asr").glob("*.json")):
            if "partial" in path.name:
                continue
            docket = path.name.split(".")[0]
            if docket in folder_of:
                work.setdefault(docket, []).append((run, path))

    dockets = sorted(work)[: args.limit] if args.limit else sorted(work)
    print(f"{len(dockets)} recording(s), "
          f"{sum(len(work[d]) for d in dockets)} transcription(s)\n")

    rows: dict[Path, list[dict]] = {}
    started = time.monotonic()

    for number, docket in enumerate(dockets, start=1):
        entry = folder_of[docket]
        mp3 = args.cases_dir / entry["folder"] / f"{entry['docket']}_audio.mp3"
        if not mp3.exists():
            print(f"[{number}/{len(dockets)}] {docket}: no audio, skipping")
            continue

        audio = load_audio(mp3)
        regions = speech_regions(audio)
        # Once per recording, so every silence in it can be read against its own
        # argument rather than an absolute number.
        recording_level = level_dbfs(audio)

        for run, path in work[docket]:
            words, audio_seconds = words_from(path)
            if not words:
                continue
            engine = path.name.split(".", 1)[1].rsplit(".json", 1)[0]
            silences = find_silences(words, audio_seconds)
            verdicts = judge_silences(silences, regions)
            summary = summarize_verdicts(verdicts)

            for v in verdicts:
                first = int(v.start * SAMPLE_RATE)
                last = int((v.start + v.seconds) * SAMPLE_RATE)
                level = level_dbfs(audio[first:last])
                rows.setdefault(run, []).append({
                    "docket": docket,
                    "engine": engine,
                    "silence_start": round(v.start, 2),
                    "silence_seconds": round(v.seconds, 2),
                    "speech_seconds": v.speech_seconds,
                    "speech_share": round(v.speech_share, 3),
                    "holds_speech": v.holds_speech,
                    "level_dbfs": round(level, 1),
                    "level_vs_recording_db": round(level - recording_level, 1),
                    "start_clock": clock(v.start),
                })

            print(f"[{number}/{len(dockets)}] {docket} {engine:22} "
                  f"{summary['silent_seconds']:7.0f}s silent, "
                  f"{summary['unwritten_speech_seconds']:6.0f}s of it speech "
                  f"({summary['unwritten_speech_share_of_silence']:.0f}%)")

    for run, run_rows in rows.items():
        out = run / "results" / "silence_speech.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(run_rows)
        print(f"\n{len(run_rows):,} rows -> {out}")

    print(f"\nin {(time.monotonic() - started) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

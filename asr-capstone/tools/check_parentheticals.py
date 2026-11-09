"""Were the models silent where the reporter wrote a notation?

Where the transcript says `(Laughter.)` there is a sound in the audio and no
speech. A model that writes nothing there is right, and a speech detector, which
hears laughter as speech, will nonetheless mark it as something missed. So some
of what is currently counted against the models is them behaving correctly.

This puts the two side by side. For every notation it works out roughly when in
the recording it falls, then asks whether each model was silent there.

A model silent at a laughter break is doing its job. A model that transcribed
something there wrote down a sound nobody said as words - which is the opposite
fault and worth seeing.

Writes `notations.csv` into each run's results folder. Loads no audio.

Usage:
    python tools/check_parentheticals.py
    python tools/check_parentheticals.py --runs-dir <scotus_corpus>/runs
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.asr.base import Word  # noqa: E402
from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.scoring.coverage import find_silences  # noqa: E402
from scotus_asr.scoring.pairs import event_times  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402

COLUMNS = [
    "docket", "engine", "kind", "text", "page", "line",
    "audio_seconds", "audio_clock", "model_was_silent", "silence_seconds",
]

#: How close a silence has to start to the notation to count as covering it. The
#: placement is an estimate routed through the alignment, so a few seconds of
#: slack is honest rather than generous.
NEAR_SECONDS = 4.0


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

def covering(silences, when: float):
    """The silence sitting at this moment, if there is one."""
    for silence in silences:
        if silence.start - NEAR_SECONDS <= when <= silence.end + NEAR_SECONDS:
            return silence
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path,
                        help="default: <scotus_corpus>/runs, from local-paths.yaml")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="RUN",
        help="Skip this run folder. Repeat for several. Use it for a run still "
             "being written, whose half-finished results would be concatenated "
             "alongside the finished run of the same model.",
    )
    args = parser.parse_args()
    if args.runs_dir is None:
        args.runs_dir = local_path("scotus_corpus") / "runs"

    rows: dict[Path, list[dict]] = defaultdict(list)
    tally: dict[str, Counter] = defaultdict(Counter)
    no_events = 0

    for run in sorted(r for r in args.runs_dir.glob("run-*")
                      if r.name not in args.exclude):
        for path in sorted((run / "asr").glob("*.json")):
            if "partial" in path.name:
                continue
            docket = path.name.split(".")[0]
            engine = path.name.split(".", 1)[1].rsplit(".json", 1)[0]

            reference = run / "reference" / f"{docket}.json"
            if not reference.exists():
                continue
            transcript = Transcript.from_dict(
                json.loads(reference.read_text(encoding="utf-8"))
            )
            if not any(turn.events for turn in transcript.turns):
                no_events += 1
                continue

            words, audio_seconds = words_from(path)
            if not words:
                continue
            silences = find_silences(words, audio_seconds)

            for event, when in event_times(transcript, words):
                quiet = covering(silences, when)
                rows[run].append({
                    "docket": docket,
                    "engine": engine,
                    "kind": event.kind,
                    "text": event.text[:80],
                    "page": event.page,
                    "line": event.line,
                    "audio_seconds": when,
                    "audio_clock": clock(when),
                    "model_was_silent": quiet is not None,
                    "silence_seconds": round(quiet.seconds, 1) if quiet else 0.0,
                })
                tally[engine][event.kind] += 1
                if quiet is not None:
                    tally[engine][f"{event.kind}:silent"] += 1

    if not rows:
        print("No notations placed. Re-run the transcripts stage first - reference "
              "JSON written before notations carried a word offset cannot be "
              f"placed. ({no_events} transcriptions had no notations at all.)")
        return 1

    for run, run_rows in rows.items():
        out = run / "results" / "notations.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(run_rows)
        print(f"{len(run_rows):>6,} notations -> {out}")

    print(f"\n{'model':26} {'notation':12} {'placed':>8} {'model silent':>13}")
    for engine, counts in sorted(tally.items()):
        for kind in sorted(k for k in counts if ":" not in k):
            silent = counts[f"{kind}:silent"]
            print(f"{engine:26} {kind:12} {counts[kind]:8,} {silent:13,}"
                  f"  ({100 * silent / counts[kind]:.0f}%)")

    print("\nA model silent at a laughter break is behaving correctly - there is a")
    print("sound there and no speech. Those seconds should not be counted against")
    print("it, and the detector alone cannot tell them from missed argument.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

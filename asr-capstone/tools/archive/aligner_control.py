"""Is the silence the model's, or the aligner's?

The coverage measure says how much of a recording has no word stamped against
it. It is built entirely on word timings, and only two of the six models in
this study produce their own. Whisper and Parakeet time their own words;
Qwen3, Canary, Voxtral and Granite hand back text and nothing else, so a
forced aligner is given the audio and the words and asked where each one sits.

Measured across the study, the split follows the timing method rather than the
model:

    Voxtral   aligner   78% of its silence holds speech
    Qwen3     aligner   75%
    Parakeet  native    57%
    Whisper   native    13%

Two readings. Either the aligned models really do drop more speech, or the
aligner places words loosely and leaves gaps nobody actually left. Those look
identical in the results and they call for opposite responses - the first is a
finding, the second is a measurement error that would have to be corrected
before any of it is reported.

**This settles it by changing one thing.** Parakeet times its own words. Take
Parakeet's transcript - the same words, unchanged - and run it through the
same aligner the other four use. Same model, same text, same audio. The only
difference is where the timings came from.

    if aligned-Parakeet looks like native-Parakeet   the aligner is sound and
                                                     the aligned models really
                                                     are leaving speech out
    if aligned-Parakeet looks like Qwen3 or Voxtral  the aligner invents the
                                                     gaps and the silence
                                                     measure is measuring the
                                                     aligner

Usage:
    python tools/aligner_control.py --limit 10
    python tools/aligner_control.py --run run-20260919-052219
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.asr.aligner import ForcedAligner  # noqa: E402
from scotus_asr.asr.base import Word  # noqa: E402
from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.scoring.coverage import find_silences  # noqa: E402
from scotus_asr.scoring.speech import SAMPLE_RATE, load_audio  # noqa: E402

#: Seconds of audio per alignment pass.
#:
#: The same as the Qwen3 and Voxtral engines use, because the point is to put
#: the aligner in the position it is normally in. Its own ceiling is 300.
WINDOW_SECONDS = 280.0

COLUMNS = [
    "docket", "engine", "audio_seconds",
    "native_silent_seconds", "native_silent_share", "native_silences_over_10s",
    "aligned_silent_seconds", "aligned_silent_share", "aligned_silences_over_10s",
    "words",
]


def native_words(data: dict) -> list[Word]:
    """The word timings the model produced itself."""
    out = []
    for segment in data.get("segments", []):
        for w in segment.get("words", []):
            if w.get("start") is None:
                continue
            out.append(Word(text=w["text"], start=float(w["start"]), end=float(w["end"])))
    return out


def realign(aligner: ForcedAligner, audio, words: list[Word], language: str) -> list[Word]:
    """Time the same words again, with the aligner instead of the model.

    The words are cut into windows by their own timings and each window is
    aligned against its own stretch of audio. That is exactly the position the
    aligner is in during a normal run - it is handed one chunk of audio and
    the text belonging to it - so this measures the aligner doing its usual
    job, not a harder or easier one.
    """
    if not words:
        return []

    out: list[Word] = []
    total = len(audio) / SAMPLE_RATE
    start = 0.0
    while start < total:
        stop = min(start + WINDOW_SECONDS, total)
        inside = [w for w in words if start <= w.start < stop]
        if inside:
            piece = audio[int(start * SAMPLE_RATE): int(stop * SAMPLE_RATE)]
            text = " ".join(w.text.strip() for w in inside).strip()
            if text and len(piece) >= SAMPLE_RATE:
                out.extend(aligner.align(piece, text, language, start))
        start = stop
    return out


def measure(words: list[Word], audio_seconds: float) -> tuple[float, float, int]:
    """Silent seconds, the share of the recording they are, and how many are long."""
    silences = find_silences(words, audio_seconds)
    total = sum(s.seconds for s in silences)
    long = sum(1 for s in silences if s.seconds >= 10)
    share = total / audio_seconds if audio_seconds else 0.0
    return total, share, long


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path,
                        help="default: <scotus_corpus>/runs, from local-paths.yaml")
    parser.add_argument("--cases-dir", type=Path,
                        help="default: <scotus_corpus>/cases, from local-paths.yaml")
    parser.add_argument("--run", default="run-20260919-052219",
                        help="Which run to take transcripts from. Must be a model "
                             "that times its own words - Parakeet or Whisper.")
    parser.add_argument("--limit", type=int, help="Stop after this many recordings.")
    parser.add_argument("--out", type=Path,
                        help="Where to write the table. Default: the run's results folder.")
    args = parser.parse_args(argv)
    if args.runs_dir is None:
        args.runs_dir = local_path("scotus_corpus") / "runs"
    if args.cases_dir is None:
        args.cases_dir = local_path("scotus_corpus") / "cases"

    run = args.runs_dir / args.run
    files = sorted((run / "asr").glob("*.json"))
    if not files:
        print(f"No transcriptions in {run / 'asr'}", file=sys.stderr)
        return 1
    if args.limit:
        files = files[: args.limit]

    aligner = ForcedAligner(device="cuda", compute_type="float16")
    aligner.load()

    rows = []
    started = time.monotonic()
    print(f"{len(files)} recording(s) from {args.run}\n")
    print(f"{'case':16s} {'native':>18} {'through the aligner':>22}")

    for n, path in enumerate(files, 1):
        data = json.loads(path.read_text(encoding="utf-8"))
        docket = data.get("docket", path.stem.split(".")[0])
        engine = data.get("engine", "?")
        words = native_words(data)
        if not words:
            print(f"{docket:16s}  no native timings, skipped")
            continue

        # Finding the right recording, and this took two goes to get right.
        #
        # Some dockets carry the term as a suffix - "15-1204_OT2017" - while
        # the folder puts it in front: "OT2017_15-1204_Jennings". Globbing the
        # whole docket finds nothing for those. But simply stripping the
        # suffix is worse than useless, because a case argued twice keeps the
        # same docket number: "15-1204" matches both OT2016_15-1204 and
        # OT2017_15-1204, which are different arguments. Taking the first
        # match paired the OT2017 transcript with the OT2016 audio and the
        # aligner, asked to place words that are not in the recording,
        # reported 38% of it silent. That went into a result before it was
        # caught.
        #
        # So: use the term when the docket carries one, and fall back to the
        # bare number only when it does not.
        stem, _, term = docket.partition("_")
        found = []
        if term:
            found = list(args.cases_dir.glob(f"*{term}_{stem}*/*.mp3"))
        if not found:
            found = list(args.cases_dir.glob(f"*{stem}*/*.mp3"))
        if not found:
            print(f"{docket:16s}  audio not found, skipped")
            continue

        # And check it anyway. A recording whose length disagrees with the
        # transcription's is the wrong recording, whatever the name said.
        claimed = float(data.get("audio_seconds") or 0)
        if claimed and len(found) > 0:
            import soundfile  # noqa: PLC0415
            actual = soundfile.info(str(found[0])).duration
            if abs(actual - claimed) > 30:
                print(f"{docket:16s}  audio is {actual:.0f}s but the transcript "
                      f"was made from {claimed:.0f}s - wrong recording, skipped")
                continue

        audio = load_audio(found[0])
        seconds = len(audio) / SAMPLE_RATE

        n_sec, n_share, n_long = measure(words, seconds)
        a_sec, a_share, a_long = measure(realign(aligner, audio, words, "en"), seconds)

        rows.append({
            "docket": docket, "engine": engine, "audio_seconds": round(seconds, 1),
            "native_silent_seconds": round(n_sec, 1),
            "native_silent_share": round(n_share * 100, 2),
            "native_silences_over_10s": n_long,
            "aligned_silent_seconds": round(a_sec, 1),
            "aligned_silent_share": round(a_share * 100, 2),
            "aligned_silences_over_10s": a_long,
            "words": len(words),
        })
        print(f"{docket:16s} {n_share*100:7.2f}% quiet, {n_long:3d} long"
              f"    {a_share*100:7.2f}% quiet, {a_long:3d} long")

    if not rows:
        print("Nothing measured.")
        return 1

    out = args.out or (run / "results" / "aligner_control.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    native = sum(r["native_silent_share"] for r in rows) / len(rows)
    aligned = sum(r["aligned_silent_share"] for r in rows) / len(rows)
    print(f"\n{len(rows)} recordings, {(time.monotonic()-started)/60:.1f} min")
    print(f"  the same transcript, timed by the model:    {native:6.2f}% of audio quiet")
    print(f"  the same transcript, timed by the aligner:  {aligned:6.2f}% of audio quiet")
    if native > 0:
        print(f"  the aligner leaves {aligned/native:.2f} times as much of the "
              f"recording unaccounted for")
    print(f"\n{len(rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

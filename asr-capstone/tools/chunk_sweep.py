"""Is each model's chunk length safe, or merely permitted?

Granite Speech 4.1 was run over the whole of OT2017 at 100-second chunks and
scored 12.94% against every other model's 5.9 to 7.2, leaving a median of 480
words an argument out of the record. That was not the model. Past about
seventy seconds Granite stops transcribing a hard passage and repeats one
phrase to the end of the piece - "It is under Section 73" several hundred
times - and the whole chunk is lost. At sixty seconds it scored 8.20% (8.38% after
September's corrections).

The setting had been chosen by measuring at two minutes and at four minutes,
correctly calling four a repetition loop, and picking 100 as comfortably under
it. The failure was in the gap between those two probes. Seven hours of
machine time went into a number that measured the wrong chunk length.

**A documented maximum is not a quality threshold.** IBM publish no limit at
all for Granite and it broke at seventy seconds. NVIDIA document 24 minutes
for Parakeet, on an A100 with three times this machine's memory. Qwen publish
20 minutes for Qwen3-ASR while the long-form research on it uses 180-second
chunks. Fitting inside the stated limit says nothing about whether the
transcript is any good.

**What this measures, and why it needs no reference transcript.** Appellate
argument runs near 175 words a minute; the band measured across 138 arguments
is 145 to 210. A model that has stopped transcribing and started repeating
itself jumps to 300 and beyond, and the text compresses far better than
language does. Both are visible from the output alone, so a chunk length can
be checked in minutes instead of by running the corpus and scoring it.

Hard passages are where this shows. The defaults below are places where models
demonstrably failed - people talking over each other - rather than easy ones.

Usage:
    python tools/chunk_sweep.py                      # every chunked engine
    python tools/chunk_sweep.py --engine granite
    python tools/chunk_sweep.py --engine parakeet --lengths 120,300,600
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.asr.base import compression_ratio, looks_like_a_loop  # noqa: E402
from scotus_asr.config import AsrSettings, local_path  # noqa: E402
from scotus_asr.scoring.speech import SAMPLE_RATE, load_audio  # noqa: E402

# The loop test is the pipeline's own - `looks_like_a_loop` in asr/base.py,
# with its three checks (words a minute, compression ratio, back-to-back
# repetition). This tool used to carry a copy of the first two, which drifted
# when the third was added, so a sweep could pass a length the engine would
# then flag in a real run.

#: Where to probe, and these are not easy passages. Each is a place some model
#: lost the thread: crosstalk, a Justice interrupting counsel mid-sentence.
#: An easy stretch of one advocate talking would clear every length and prove
#: nothing.
HARD_SPOTS = [
    ("16-1144", 2300),   # Granite looped here at 100s
    ("17-586", 4232),    # 309 words lost in the 100s Granite run
    ("16-1215", 1108),   # 305 words lost
]

#: The engines this project chunks itself, and the lengths worth probing for
#: each. Whisper is absent: its stitching happens inside faster-whisper.
#: name here -> (registry name, model, lengths to probe)
#:
#: The registry name is not always the short one - Qwen3 registers as
#: "qwen3-asr" - so it is written out rather than guessed at.
ENGINES = {
    "parakeet": ("parakeet",  "parakeet-tdt-0.6b-v3",  [60, 120, 300, 600, 900]),
    "qwen3":    ("qwen3-asr", "Qwen3-ASR-1.7B-hf",     [60, 120, 180, 280, 400]),
    "canary":   ("canary",    "canary-1b-v2",          [20, 40, 80, 150]),
    "voxtral":  ("voxtral",   "Voxtral-Mini-3B-2507",  [60, 120, 180, 280, 400]),
    "granite":  ("granite",   "granite-speech-4.1-2b", [30, 60, 100, 140]),
    # IBM document 3.5 minutes (210s) for this model's timestamp mode. 210 is
    # in the list to test that claim rather than to assume it - the base
    # Granite documented no limit at all and broke at seventy seconds.
    "granite-plus": ("granite-plus", "granite-speech-4.1-2b-plus",
                     [30, 60, 120, 210]),
}


def release_between_engines() -> None:
    """Give the card back, so the next engine can have it."""
    import gc  # noqa: PLC0415
    import torch  # noqa: PLC0415

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def build(key: str, registry_name: str, model: str):
    """One loaded engine, and a function that decodes a piece with it.

    Every engine but Parakeet exposes `_transcribe_piece`. Parakeet's one-piece
    decoder is `_decode_once`, which also applies its generation ceiling, so
    the sweep decodes exactly the way a real run does.
    """
    from scotus_asr.asr.registry import build_engine  # noqa: PLC0415

    settings = AsrSettings(engine=registry_name, model=model, device="cuda",
                           compute_type="bfloat16" if key in ("voxtral", "granite", "granite-plus")
                           else "float16", language="en")
    engine = build_engine(settings)

    if key == "parakeet":
        def decode(piece):
            _, _, text = engine._decode_once(piece, 0.0)
            return text
    elif key == "granite-plus":
        # Two differences from the others. Its _transcribe_piece takes a
        # temperature rather than a language, and what comes back is studded
        # with [T:N] tags. The tags have to come off before the word rate and
        # the compression ratio mean anything - tagged text is repetitive by
        # construction, so every clean chunk would read as a loop.
        from scotus_asr.asr.granite_plus_engine import (  # noqa: PLC0415
            strip_timestamps,
        )

        def decode(piece):
            return strip_timestamps(engine._transcribe_piece(piece, 0.0))
    else:
        def decode(piece):
            out = engine._transcribe_piece(piece, "en")
            return out[0] if isinstance(out, tuple) else out   # Canary returns a flag too

    return engine, decode


def sweep(key: str, registry_name: str, model: str, lengths: list[int], spots, cases_dir: Path):
    """Decode the same hard passages at each length and report what came back."""
    from scotus_asr.asr import (  # noqa: PLC0415
        canary_engine, granite_engine, granite_plus_engine, parakeet_engine,
        qwen3_engine, voxtral_engine,
    )
    current = {
        "parakeet": parakeet_engine, "qwen3": qwen3_engine, "canary": canary_engine,
        "voxtral": voxtral_engine, "granite": granite_engine,
        "granite-plus": granite_plus_engine,
    }[key].CHUNK_SECONDS

    print(f"\n{'='*78}\n{model}   (this project currently uses {current:.0f}s)\n{'='*78}")
    engine, decode = build(key, registry_name, model)

    rows = []
    print(f"{'case':10s} {'length':>7}  {'words':>6} {'wpm':>6} {'ratio':>7}  verdict")
    for docket, at in spots:
        found = list(cases_dir.glob(f"*{docket.split('_')[0]}*/*.mp3"))
        if not found:
            print(f"{docket:10s}  audio not found, skipped")
            continue
        audio = load_audio(found[0])
        total = len(audio) / SAMPLE_RATE
        for secs in lengths:
            start = min(at, max(0, total - secs - 1))
            piece = audio[int(start * SAMPLE_RATE): int((start + secs) * SAMPLE_RATE)]
            if len(piece) < SAMPLE_RATE * 5:
                continue
            began = time.monotonic()
            try:
                text = decode(piece)
            except Exception as error:                      # noqa: BLE001
                print(f"{docket:10s} {secs:6d}s   failed: {str(error)[:52]}")
                rows.append({"engine": model, "docket": docket, "chunk_seconds": secs,
                             "words": "", "words_per_minute": "", "compression_ratio": "",
                             "verdict": "error", "seconds": ""})
                continue
            words = len(text.split())
            wpm = words / (secs / 60)
            ratio = compression_ratio(text)
            bad, _ = looks_like_a_loop(text, secs)
            mark = "LOOP" if bad else "ok"
            here = "  <- current" if abs(secs - current) < 1 else ""
            print(f"{docket:10s} {secs:6d}s  {words:6d} {wpm:6.0f} {ratio:7.2f}  "
                  f"{mark}{here}")
            rows.append({"engine": model, "docket": docket, "chunk_seconds": secs,
                         "words": words, "words_per_minute": round(wpm, 1),
                         "compression_ratio": round(ratio, 2), "verdict": mark,
                         "seconds": round(time.monotonic() - began, 1)})
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=sorted(ENGINES), action="append",
                        help="Repeat for several. Default: all of them.")
    parser.add_argument("--lengths", help="Comma-separated seconds, overriding the defaults.")
    parser.add_argument("--case", action="append", help="docket:seconds. Repeat for several.")
    parser.add_argument("--cases-dir", type=Path,
                        help="default: <scotus_corpus>/cases, from local-paths.yaml")
    parser.add_argument("--out", type=Path,
                        default=CAPSTONE / "findings" / "chunk-sweep.csv")
    args = parser.parse_args(argv)
    if args.cases_dir is None:
        args.cases_dir = local_path("scotus_corpus") / "cases"

    spots = HARD_SPOTS
    if args.case:
        spots = [(c.split(":")[0], int(c.split(":")[1])) for c in args.case]

    chosen = args.engine or sorted(ENGINES)
    lengths_override = [int(x) for x in args.lengths.split(",")] if args.lengths else None

    rows = []
    for key in chosen:
        registry_name, model, lengths = ENGINES[key]
        rows += sweep(key, registry_name, model, lengths_override or lengths,
                      spots, args.cases_dir)
        # Hand the card back before the next model is loaded. Without this the
        # sweep holds every engine it has already built, and the last one in
        # the list - Voxtral, which wants 18 GB - is refused outright. The
        # first run of this tool reported "Not enough video memory" for all
        # fifteen of Voxtral's probes and swept four engines instead of five.
        release_between_engines()

    if rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n{len(rows)} rows -> {args.out}")

        print("\nsafe length per engine (longest with no loop on any probe):")
        for key in chosen:
            _, model, _ = ENGINES[key]
            mine = [r for r in rows if r["engine"] == model and r["verdict"] in ("ok", "LOOP")]
            bad = {r["chunk_seconds"] for r in mine if r["verdict"] == "LOOP"}
            good = sorted({r["chunk_seconds"] for r in mine if r["verdict"] == "ok"} - bad)
            print(f"  {model:26s} clean at {good if good else 'nothing tested'}"
                  f"{'   looped at ' + str(sorted(bad)) if bad else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

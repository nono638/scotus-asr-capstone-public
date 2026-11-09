"""Fix Parakeet transcripts made before the gap re-read, without transcribing again.

Parakeet's decoder can stop writing after a full stop and stay stopped until it
is reset, which left up to two and a half minutes of clear speech blank in our
runs. Since 23 October 2026 the engine reads every blank stretch of 4+ seconds
again on its own (`ParakeetEngine.reread_gaps`; why, with sources, at the top of
`parakeet_engine.py` and in `findings/parakeet-stall/`).

Transcripts made before that are fixed here with the same method, which decodes
only the gaps instead of all of the audio. Decoding is
repeatable, so the result is the same as running the fixed engine from the
start.

    python tools/reread_parakeet_gaps.py --source run-earnings22-parakeet \\
        --config config/parakeet.yaml --config config/corpora/earnings22.yaml

writes a new run folder beside the old one, `run-earnings22-parakeet-reread`:
the old run's references, a settings file saying what was done, and every
transcript with its gaps read again. **The old run folder is only read, never
changed.** Score the new one the usual way:

    python -m scotus_asr.cli score --config ... --run-id run-earnings22-parakeet-reread

The `--config` files are the ones the old run's queue row names (they say where
the audio is). Paths are relative to `pipeline/`, as in the queue. A transcript
whose recording the settings do not list is skipped and named - EdAcc's test and
dev splits are two settings, so that run is done in two passes. A transcript
already in the new folder is skipped, so a stopped run carries on.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import yaml

CAPSTONE = Path(__file__).resolve().parent.parent
PIPELINE = CAPSTONE / "pipeline"
sys.path.insert(0, str(PIPELINE))

from scotus_asr.asr import parakeet_engine  # noqa: E402
from scotus_asr.asr.base import Segment, Word  # noqa: E402
from scotus_asr.asr.parakeet_engine import ParakeetEngine, load_audio  # noqa: E402
from scotus_asr.config import load_config  # noqa: E402
from scotus_asr.corpora.registry import build_corpus  # noqa: E402
from scotus_asr.store import atomic_write_text  # noqa: E402


def raw_segments(data: dict) -> list[Segment]:
    """The segments exactly as the old run wrote them.

    Not through `stages._load_asr_result`, which drops words repeated at chunk
    seams. That clean-up belongs to scoring and runs again when the new run is
    scored; doing it here as well would change what is on disk.
    """
    return [
        Segment(
            index=s.get("index", i), start=s["start"], end=s["end"], text=s["text"],
            words=[Word(w["text"], w["start"], w["end"], w.get("probability"))
                   for w in s.get("words", [])],
        )
        for i, s in enumerate(data.get("segments", []))
    ]


def new_run_folder(source: Path, target: Path) -> None:
    """Make the new run's folder: its references and a settings file.

    References are copied so the new run scores against exactly the records the
    old one did. The settings are the old run's, plus the re-read's own, so the
    run says how it was made.
    """
    (target / "asr").mkdir(parents=True, exist_ok=True)
    reference = target / "reference"
    reference.mkdir(exist_ok=True)
    for path in (source / "reference").glob("*"):
        if path.is_file() and not (reference / path.name).exists():
            shutil.copy2(path, reference / path.name)

    used = yaml.safe_load((source / "config_used.yaml").read_text(encoding="utf-8"))
    used.setdefault("asr", {}).update(
        gap_reread_seconds=parakeet_engine.GAP_REREAD_SECONDS,
        max_reread_depth=parakeet_engine.MAX_REREAD_DEPTH,
        gap_reread_from=source.name,
    )
    atomic_write_text(target / "config_used.yaml",
                      yaml.safe_dump(used, sort_keys=False, allow_unicode=True))


def copy_ledger_lines(source: Path, target: Path) -> int:
    """Copy the old run's "reference built" and "transcribed" lines into the new run.

    The queue runner counts a recording as done only when its file is there and
    the ledger has an ok line for it. Without these lines, a queue row naming the
    new run (to add recordings to it) would transcribe every recording again from
    the start. Copied only for transcripts the new folder holds, and only once.
    Returns how many lines were added.
    """
    from scotus_asr.ledger import STATUS_OK, Ledger, LedgerEntry
    have = {p.name.split(".")[0] for p in (target / "asr").glob("*.json")}
    ledger = Ledger(target / "ledger.jsonl")
    already = ledger.completed_ids()
    added = 0
    for entry in Ledger(source / "ledger.jsonl").entries():
        docket, stage = entry.task_id.split("/")[:2]
        if (entry.status != STATUS_OK or stage not in ("transcript", "asr")
                or docket not in have or entry.task_id in already):
            continue
        summary = entry.summary + (f"; gaps re-read from {source.name}" if stage == "asr" else "")
        ledger.append(LedgerEntry(**{**entry.__dict__, "summary": summary}))
        already.add(entry.task_id)
        added += 1
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", required=True, help="The old Parakeet run, e.g. run-earnings22-parakeet.")
    parser.add_argument("--config", action="append", required=True,
                        help="Settings files from the old run's queue row, relative to pipeline/.")
    parser.add_argument("--run-id", help="The new run's name. Default: the old one plus -reread.")
    parser.add_argument("--case", action="append", help="Only these recordings (repeatable).")
    parser.add_argument("--ledger-only", action="store_true",
                        help="Decode nothing; only add the ledger lines a re-read folder made "
                             "before 23 Oct 2026 is missing (see copy_ledger_lines).")
    args = parser.parse_args()

    config = load_config([p if Path(p).is_absolute() else PIPELINE / p for p in args.config])
    source = config.paths.runs_dir / args.source
    target = config.paths.runs_dir / (args.run_id or f"{args.source}-reread")
    if not (source / "asr").is_dir():
        print(f"No transcripts in {source / 'asr'}")
        return 1
    if target == source:
        print("The new run must not be the old one: the old one is only read.")
        return 1

    if args.ledger_only:
        if not (target / "asr").is_dir():
            print(f"No re-read folder at {target}")
            return 1
        print(f"{target.name}: {copy_ledger_lines(source, target)} ledger lines added")
        return 0

    audio_of = {case.docket: case.audio_path for case in build_corpus(config).recordings()}
    new_run_folder(source, target)
    engine = ParakeetEngine(config.asr)

    files = sorted((source / "asr").glob("*.json"))
    if args.case:
        files = [f for f in files if f.name.split(".")[0] in args.case]
    print(f"{source.name} -> {target.name}: {len(files)} transcripts")

    done = skipped = 0
    for path in files:
        out = target / "asr" / path.name
        if out.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        docket = data["docket"]
        if docket not in audio_of:
            print(f"  {docket}: not in these settings' recordings, skipped")
            skipped += 1
            continue

        started = time.monotonic()
        rereads_before = engine.gap_rereads
        audio = load_audio(audio_of[docket])
        segments = raw_segments(data)
        restored = engine.reread_gaps(audio, segments, len(audio) / parakeet_engine.SAMPLE_RATE)

        data["segments"] = [s.to_dict() for s in segments]
        data["segment_count"] = len(segments)
        data["word_count"] = sum(len(s.words) for s in segments)
        data["settings"] = {**data.get("settings", {}),
                            "gap_reread_seconds": parakeet_engine.GAP_REREAD_SECONDS,
                            "max_reread_depth": parakeet_engine.MAX_REREAD_DEPTH}
        # What this pass did, kept apart from the original decode's own numbers.
        data["gap_reread"] = {
            "from_run": source.name,
            "rereads": engine.gap_rereads - rereads_before,
            "words_restored": restored,
            "seconds_taken": round(time.monotonic() - started, 1),
        }
        atomic_write_text(out, json.dumps(data, ensure_ascii=False))
        done += 1
        print(f"  {docket}: {restored} words restored from "
              f"{data['gap_reread']['rereads']} re-reads, {data['gap_reread']['seconds_taken']}s",
              flush=True)

    print(f"Done: {done} written, {skipped} skipped. Runaway chunks: {engine.runaway_chunks}. "
          f"Ledger lines added: {copy_ledger_lines(source, target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

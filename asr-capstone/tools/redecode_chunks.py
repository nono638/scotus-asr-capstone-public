"""Decode again only the chunks of a run that came out damaged, into a new run folder.

Two faults damaged chunks of the engines that get their word times from the forced
aligner (bug-audit-2026-11-05.md, both fixed in the code on 6 November 2026):

- One token with no letter or digit, such as "--", made the aligner return fewer words
  than the engine wrote, and the whole chunk then took the aligner's bare words: no
  punctuation, which the verbatim rule counts against the engine. The engine's own text
  was not saved, so the punctuation can only come back by decoding the chunk again.
- A chunk could come back with next to nothing and be dropped without a trace. The model
  itself does this: Qwen3 wrote only "None" for 280 s of speech in one CORAAL interview, and
  "Thank you, Mr. President." for 280 s of an earnings call, the same at every temperature.
  The same audio in shorter windows reads normally. So, as for Parakeet's stall
  (findings/parakeet-stall/), such a chunk is read again in half-length windows, and
  redecode.csv says so. It is a fault of the engine that these repairs hide: "halves" in
  that file lists every one, so it can be reported.

    python tools/redecode_chunks.py --corpus coraal --source run-coraal-qwen3
    python tools/redecode_chunks.py --corpus edacc --source run-edacc-canary --missing-only

writes `<source>-reread` beside the old run, which is only read: every transcript, with the
damaged chunks replaced, and redecode.csv saying what happened to each. A stripped chunk
should come back with the same words plus its punctuation, so that file compares the words.
A recording already in the new folder is skipped, so a stopped run carries on.

Each chunk goes through the engine's own transcribe(), on a file holding just that chunk's
samples, so it takes the same path as the first time, fallbacks included.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import difflib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.asr.base import Segment, Word  # noqa: E402
from scotus_asr.asr.parakeet_engine import keep_window  # noqa: E402
from scotus_asr.asr.registry import build_engine  # noqa: E402
from scotus_asr.config import AsrSettings, local_path  # noqa: E402
from scotus_asr.store import atomic_write_text  # noqa: E402

SAMPLE_RATE = 16000
PUNCTUATION = re.compile(r"[.,?!;:]")
#: A chunk this short can have no punctuation for honest reasons.
FEW_WORDS = 10
#: A long chunk with fewer words than this has probably been given up on.
THIN_WORDS, THIN_SECONDS = 20, 100.0
#: A window with fewer words than this a second is split again, down to this many seconds.
MIN_WORDS_A_SECOND, MIN_WINDOW = 0.2, 30.0


def bare(words: list[str]) -> list[str]:
    return [t for t in (re.sub(r"[^\w]", "", w.lower()) for w in words) if t]


def overlap_of(chunk: float, step: float) -> float:
    return chunk - step


def damaged(data: dict, chunk: float, step: float, missing_only: bool) -> list[tuple[int, str]]:
    """The chunks to decode again: (index, "stripped" or "missing")."""
    segments = data.get("segments", [])
    have = {s.get("index") for s in segments}
    total = data.get("audio_seconds") or 0
    found = []
    for s in segments:
        words = s["text"].split()
        whole_chunk = (s["index"] + 1) * step + overlap_of(chunk, step) <= total
        if chunk >= THIN_SECONDS and len(words) < THIN_WORDS and whole_chunk:
            found.append((s["index"], "thin"))
        elif not missing_only and len(words) >= FEW_WORDS and not any(PUNCTUATION.search(w) for w in words):
            found.append((s["index"], "stripped"))
    found += [(i, "missing") for i in range(int(total // step)) if i not in have and i * step + chunk <= total]
    return sorted(found)


def decode_chunk(engine, audio, offset: float, chunk: float, docket: str) -> Segment | None:
    """One chunk through the engine's own transcribe(). Its first segment is the chunk: a
    file this long makes the loop go round once more for the last few seconds, which is
    a repeat of what the real run's next chunk covers."""
    import soundfile as sf
    first, last = int(offset * SAMPLE_RATE), int((offset + chunk) * SAMPLE_RATE)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "chunk.wav"
        # 32-bit float, so the samples are exactly the ones the first run decoded.
        sf.write(str(path), audio[first:last], SAMPLE_RATE, subtype="FLOAT")
        result = engine.transcribe(path, docket)
    return next((s for s in result.segments if s.index == 0), None)


def replace(segment: Segment | None, index: int, offset: float, keep: tuple[float, float]) -> Segment | None:
    """That segment on the recording's clock, cut to what this chunk keeps at its seams."""
    if segment is None:
        return None
    words = [Word(w.text, w.start + offset, w.end + offset, w.probability) for w in segment.words]
    kept = [w for w in words if keep[0] <= w.start < keep[1]]
    if not kept:
        return None
    return dataclasses.replace(segment, index=index, start=kept[0].start, end=kept[-1].end,
                               text="".join(w.text for w in kept).strip(), words=kept)


def read_in_halves(engine, audio, offset: float, chunk: float, overlap: float, index: int, docket: str,
                   keep: tuple[float, float], template: Segment | None) -> Segment | None:
    """A chunk the engine gave up on, read again in windows half as long, and half again where
    a window is given up on too, down to about 30 s. Windows overlap as chunks do, and each
    keeps its share of the overlap, so no word comes twice."""

    def read(start: float, length: float) -> list[Word]:
        """Words on the recording's clock for this span, each kept by one window only."""
        window, words, at, n = length / 2, [], start, 0
        end = min(start + length, len(audio) / SAMPLE_RATE)
        while at < end - overlap:
            lo, hi = keep_window(at - start, n, end - start, window, overlap)
            got = decode_chunk(engine, audio, at, window, docket)
            found = [Word(w.text, w.start + at, w.end + at, w.probability) for w in got.words] if got else []
            if len(found) < window * MIN_WORDS_A_SECOND and window >= 2 * MIN_WINDOW:
                found = read(at, window)
            words += [w for w in found if start + lo <= w.start < start + hi]
            at += window - overlap
            n += 1
        return words

    kept = [w for w in read(offset, chunk) if keep[0] <= w.start < keep[1]]
    if not kept:
        return None
    base = template or Segment(index=index, start=0.0, end=0.0, text="", words=[])
    return dataclasses.replace(base, index=index, start=kept[0].start, end=kept[-1].end,
                               text="".join(w.text for w in kept).strip(), words=kept)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--corpus", required=True, help="scotus, edacc, coraal or earnings22")
    parser.add_argument("--source", required=True, help="The old run's folder name.")
    parser.add_argument("--missing-only", action="store_true", help="Only chunks with no words at all.")
    parser.add_argument("--case", action="append", help="Only these recordings (repeatable).")
    parser.add_argument("--chunks", help="With one --case: only these chunk indexes, comma-separated.")
    parser.add_argument("--dry-run", action="store_true", help="Say what would be decoded, and stop.")
    parser.add_argument("--run-id", help="The new run's name. Default: the old one plus -reread.")
    args = parser.parse_args()

    root = local_path("scotus_corpus") if args.corpus == "scotus" else local_path("asr_corpora") / args.corpus
    source = root / "runs" / args.source
    target = root / "runs" / (args.run_id or f"{args.source}-reread")
    used = yaml.safe_load((source / "config_used.yaml").read_text(encoding="utf-8"))
    known = {f.name for f in dataclasses.fields(AsrSettings)}
    settings = AsrSettings(**{k: v for k, v in used["asr"].items() if k in known})
    engine = build_engine(settings)
    module = sys.modules[type(engine).__module__]
    chunk, overlap = module.CHUNK_SECONDS, module.OVERLAP_SECONDS
    step = chunk - overlap

    audio_of = json.loads((CAPSTONE / "explorer" / args.corpus / "local-audio.json").read_text(encoding="utf-8"))
    files = sorted((source / "asr").glob("*.json"))
    if args.case:
        files = [f for f in files if f.name.split(".")[0] in args.case]

    plan, seconds = {}, 0.0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        docket = data["docket"]
        where = audio_of.get(docket) or audio_of.get(docket.replace("_OT2017", ""))
        chunks = damaged(data, chunk, step, args.missing_only) if where else []
        if args.chunks:
            wanted = {int(x) for x in args.chunks.split(",")}
            have = {i: k for i, k in damaged(data, chunk, step, False)}
            chunks = [(i, have.get(i, "asked")) for i in sorted(wanted)]
        if chunks:
            plan[path] = (where, chunks)
            seconds += len(chunks) * chunk
    print(f"{source.name}: {len(files)} transcripts, {sum(len(c) for _, c in plan.values())} chunks to decode in "
          f"{len(plan)} recordings, {seconds / 3600:.1f} h of audio", flush=True)
    if args.dry_run:
        return 0

    import librosa
    (target / "asr").mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "reference", target / "reference", dirs_exist_ok=True)
    used["asr"]["redecoded_from"] = source.name
    atomic_write_text(target / "config_used.yaml", yaml.safe_dump(used, sort_keys=False, allow_unicode=True))
    log_path = target / "redecode.csv"
    fresh = not log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        log = csv.writer(handle)
        if fresh:
            log.writerow(["recording", "index", "kind", "old_words", "new_words", "same_words", "marks_before",
                          "marks_after", "temperature", "seconds"])
        for path in files:
            out = target / "asr" / path.name
            if out.exists():
                continue
            if path not in plan:
                shutil.copy2(path, out)
                continue
            where, chunks = plan[path]
            data = json.loads(path.read_text(encoding="utf-8"))
            docket = data["docket"]
            audio, _ = librosa.load(where, sr=SAMPLE_RATE, mono=True)
            total = len(audio) / SAMPLE_RATE
            by_index = {s["index"]: s for s in data["segments"]}
            for index, kind in chunks:
                started = time.monotonic()
                offset = index * step
                keep = keep_window(offset, index, total, chunk, overlap)
                first = decode_chunk(engine, audio, offset, chunk, docket)
                new = replace(first, index, offset, keep)
                old = by_index.get(index)
                gave_up = kind in ("missing", "thin") and (new is None or len(new.words) < THIN_WORDS)
                if gave_up:
                    kind += " halves"
                    new = read_in_halves(engine, audio, offset, chunk, overlap, index, docket, keep, first)
                    if new is not None and old is not None and len(new.words) <= len(old["words"]):
                        new = None   # no better: the chunk really has little in it
                old_words = old["text"].split() if old else []
                new_words = new.text.split() if new else []
                same = difflib.SequenceMatcher(None, bare(old_words), bare(new_words), autojunk=False).ratio() if old else 0.0
                count = lambda ws: sum(1 for w in ws if PUNCTUATION.search(w))
                log.writerow([docket, index, kind, len(old_words), len(new_words), f"{same:.4f}", count(old_words),
                              count(new_words), new.temperature if new else "", f"{time.monotonic() - started:.1f}"])
                handle.flush()
                print(f"  {docket} chunk {index} ({kind}): {len(old_words)} -> {len(new_words)} words, same {same:.3f}, "
                      f"marks {count(old_words)} -> {count(new_words)}, {time.monotonic() - started:.0f}s", flush=True)
                if new is not None:
                    by_index[index] = new.to_dict()
            data["segments"] = [by_index[i] for i in sorted(by_index)]
            data["segment_count"] = len(data["segments"])
            data["word_count"] = sum(len(s["words"]) for s in data["segments"])
            data["redecoded"] = {"from_run": source.name, "chunks": [[i, k] for i, k in chunks]}
            atomic_write_text(out, json.dumps(data, ensure_ascii=False))
    print(f"{target.name}: finished", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Words a speech engine wrote where nobody said anything.

An "invented word" here is an insertion - a word the engine wrote that has no
counterpart in the reference - sitting on audio that is quiet: the speech
detector hears little or no speech there and the level is well below the
recording's own. A stenographer can mishear, but does not write words into a
silence. A machine sometimes does, and this finds where.

For each recording, each engine's transcription is lined up against the
reference the way tools/crowd.py lines them up (seam duplicates removed, ignored
stretches dropped, the `standard` rule with the harmonise fixes, one shared
vocabulary). Every `insert` chunk gets a time span from the engine's own word
timings, and the audio there is measured: how much of it Silero VAD calls speech,
and how loud it is against the whole recording.

The Supreme Court reference has no times, so there "the record has nothing" means
the alignment calls it an insertion. EdAcc's and CORAAL's reference turns are
timed, so there the span must also overlap no reference turn, and no stretch the
reference left out of scoring (a row with a bleeped name or unclear speech in
CORAAL, a read-aloud passage in EdAcc): somebody was talking there too.

Earnings-22's reference has no times either, so it is treated like the Supreme
Court's.

Recordings and runs come from tools/lineup.py: four Supreme Court terms, EdAcc's
test and dev splits, CORAAL's eight components (ROC, PRV, DCB, ATL, DCA, DTA, LES,
VLD), and Earnings-22's regions.

Usage:
    python tools/find_invented_words.py                      # everything
    python tools/find_invented_words.py --terms 2017 --limit 2
    python tools/find_invented_words.py --edacc dev
    python tools/find_invented_words.py --coraal             # all eight components
    python tools/find_invented_words.py --earnings22         # every region

Besides its own files in findings/invented-words/, it writes the shared format
every finder writes (findings/failures/README.md) to findings/failures/invented/:
candidates.csv (the real cases only) and counts.csv. The shortlist there is
picked by hand.

Each recording's measurements are kept in findings/invented-words/cache/, so a
second run only redoes what is missing and the thresholds can be changed without
loading any audio again. A saved one is used only while it is newer than every
transcript and reference it came from (lineup.fresh), so a recording transcribed
again, or a run swapped for another, is measured again on its own. Processor only. Loading the audio and
running the detector is the slow part, ten to fifteen seconds an argument.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from types import SimpleNamespace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowd  # noqa: E402
import lineup  # noqa: E402

from scotus_asr.scoring.pairs import _clock  # noqa: E402
from scotus_asr.scoring.speech import (  # noqa: E402
    SAMPLE_RATE, judge_silences, level_dbfs, load_audio, speech_regions)

OUT = crowd.CAPSTONE / "findings" / "invented-words"
SHARED = crowd.CAPSTONE / "findings" / "failures" / "invented"

#: The quiet test. Under a fifth of the span sounds like speech to the detector,
#: and the span is at least 15 dB below the recording as a whole. Speech in these
#: recordings sits near the recording's level; a stretch with nobody talking sits
#: 20 dB or more under it (see level_dbfs in scoring/speech.py).
MAX_SPEECH_SHARE = 0.2
MIN_DB_BELOW = 15.0

#: A one-word insertion can be timed at a tenth of a second or less. Measure at
#: least this much audio, centred on it, so the level is not read off a few
#: samples.
MIN_SPAN = 0.5

#: Another engine's insertion counts as the same one if it falls in the same
#: reference gap (give or take a token) or within this many seconds of it.
SHARED_SLACK = 1.0

CONTEXT = 5

#: Words that say nothing on their own: fillers, small words, replies, and the
#: hedges a court reporter leaves out ("you know", "I mean", "I think").
NOT_CONTENT = (crowd.FILLERS | crowd.FUNCTION_WORDS | crowd.DISCOURSE | crowd.REPLIES
               | crowd.BACKCHANNELS | crowd.NUMBER_WORDS | {"know", "mean", "think", "guess"})

#: Whisper, and now and then Parakeet, write a speaker's name the way a
#: transcript prints it - "MR.", "JUSTICE KAGAN.", "CHAIRMAN BERNANKE.",
#: "Trevor Burrus, Jr.:" - into the pause where one speaker hands over to the
#: next. Nobody says these. A word in capitals, or one ending in a colon.
LABEL = re.compile(r"^[A-Z]{2,}[.,]?$|:$")

COLUMNS = ["corpus", "term", "docket", "engine", "start", "end", "start_clock", "words",
           "n_words", "content_words", "speech_share", "level_dbfs", "level_vs_recording_db",
           "confidence", "shared_with", "at_edge", "speaker_label", "engine_context",
           "record_context"]


def recordings(terms: list[str], edacc: list[str], coraal: list[str],
               earnings22: list[str] = []) -> list[dict]:
    """Every recording to check: these Supreme Court terms, EdAcc splits, CORAAL
    parts and Earnings-22 regions."""
    jobs = []
    for corpus, parts in [("scotus", terms), ("edacc", edacc), ("coraal", coraal),
                          ("earnings22", earnings22)]:
        if parts:
            jobs += lineup.recordings(corpus, parts)
    return jobs


def load(job: dict, tries: int = 10) -> dict:
    """lineup.load(), waiting if another process is still writing that cache file."""
    for attempt in range(tries):
        try:
            return lineup.load(job)
        except (EOFError, gzip.BadGzipFile):
            if attempt == tries - 1:
                raise
            time.sleep(30)


def ignored(job: dict) -> list[tuple[float, float]]:
    """The stretches the reference leaves out of scoring (none for the Supreme Court)."""
    data = json.loads(job["models"][0].reference_file(job["docket"]).read_text(encoding="utf-8"))
    return [(float(a), float(b)) for a, b in data.get("ignore", [])]


def is_content(token: str) -> bool:
    """A word that means something, not a filler, a small word, a lone letter or a number."""
    return len(token) > 1 and not any(ch.isdigit() for ch in token) and token not in NOT_CONTENT


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def inserts(job: dict, name: str, lined: tuple) -> list[dict]:
    """One row for each run of words this engine wrote that the reference does not have."""
    transcript, reference_words, alignment, words = lined
    hyp = alignment.hypothesis
    ref_source = alignment.reference.source_index

    # Where the record starts and ends, in this engine's time: its first and last
    # word that matched the reference. Anything outside is before the argument is
    # called or after it is submitted.
    matched = [hyp.source_index[k] for c in alignment.chunks if c.kind == "equal"
               for k in range(c.hyp_start, c.hyp_end)]
    first_said = words[matched[0]].start if matched else 0.0
    last_said = words[matched[-1]].end if matched else 0.0
    turn_times = [(t.start, t.end) for t in transcript.turns if t.start is not None]

    rows = []
    for chunk in alignment.chunks:
        if chunk.kind != "insert":
            continue
        tokens = hyp.tokens[chunk.hyp_start:chunk.hyp_end]
        # A word the engine wrote twice in a row is a stutter the reporter tidied
        # away ("could -- could"), not a new word.
        beside = set(hyp.tokens[max(0, chunk.hyp_start - 1):chunk.hyp_start]
                     + hyp.tokens[chunk.hyp_end:chunk.hyp_end + 1])
        i0, i1 = hyp.source_index[chunk.hyp_start], hyp.source_index[chunk.hyp_end - 1]
        mine = words[i0:i1 + 1]
        start, end = min(w.start for w in mine), max(w.end for w in mine)
        probs = [w.probability for w in mine if w.probability is not None]

        gap = chunk.ref_start
        at = ref_source[gap] if gap < len(ref_source) else len(reference_words)
        before = " ".join(w.text.strip() for w in words[max(0, i0 - CONTEXT):i0])
        after = " ".join(w.text.strip() for w in words[i1 + 1:i1 + 1 + CONTEXT])
        rows.append({
            "corpus": job["corpus"], "term": job["term"], "docket": job["docket"],
            "engine": name, "start": round(start, 2), "end": round(end, 2),
            "start_clock": _clock(start),
            "words": " ".join(w.text.strip() for w in mine),
            "n_words": len(tokens),
            "content_words": " ".join(t for t in tokens if is_content(t) and t not in beside),
            "confidence": round(sum(probs) / len(probs), 3) if probs else None,
            "gap": gap,
            "at_edge": gap == 0 or gap >= len(ref_source) or end <= first_said or start >= last_said,
            "ref_overlap": round(sum(overlap((start, end), t) for t in turn_times), 2),
            "engine_context": f"{before} [{' '.join(w.text.strip() for w in mine)}] {after}".strip(),
            "record_context": " ".join(reference_words[max(0, at - CONTEXT):at] + ["^"]
                                       + reference_words[at:at + CONTEXT]),
        })
    return rows


def mark_shared(rows: list[dict]) -> None:
    """Note which other engines inserted words at the same place."""
    for row in rows:
        others = {o["engine"] for o in rows
                  if o["engine"] != row["engine"]
                  and (abs(o["gap"] - row["gap"]) <= 1
                       or overlap((row["start"] - SHARED_SLACK, row["end"] + SHARED_SLACK),
                                  (o["start"], o["end"])) > 0)}
        row["shared_with"] = " ".join(sorted(others))


def measure(rows: list[dict], audio, regions) -> None:
    """Speech share and level of each insertion's stretch of audio."""
    recording_level = level_dbfs(audio)
    for row in rows:
        start, end = row["start"], row["end"]
        if end - start < MIN_SPAN:
            middle = (start + end) / 2
            start, end = max(0.0, middle - MIN_SPAN / 2), middle + MIN_SPAN / 2
        verdict = judge_silences([SimpleNamespace(start=start, end=end)], regions)[0]
        level = level_dbfs(audio[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)])
        row["speech_share"] = round(verdict.speech_share, 3)
        row["level_dbfs"] = round(level, 1)
        row["level_vs_recording_db"] = round(level - recording_level, 1)


def cache_file(job: dict) -> Path:
    return OUT / "cache" / job["corpus"] / job["term"] / f"{job['docket']}.json.gz"


def check(job: dict) -> dict:
    """Every insertion in one recording, every engine, measured. Cached."""
    path = cache_file(job)
    # Not just "is there a file": on 23 Oct 2026 every Parakeet transcript was
    # swapped for its re-read one, and the old file would keep its old insertions.
    if lineup.fresh(path, job):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)

    lined = load(job)
    rows = []
    for name, one in lined.items():
        rows += inserts(job, name, one)
    mark_shared(rows)

    audio = load_audio(job["audio"])
    measure(rows, audio, speech_regions(audio))
    result = {"seconds": round(len(audio) / SAMPLE_RATE, 1),
              "engines": list(lined), "rows": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(result, stream)
    return result


def is_quiet(row: pd.Series) -> bool:
    quiet = (row["speech_share"] < MAX_SPEECH_SHARE
             and row["level_vs_recording_db"] <= -MIN_DB_BELOW)
    # A timed reference (EdAcc, CORAAL): a reference turn, or a stretch left out
    # of scoring, over the span means somebody was talking there, whatever the
    # alignment made of it. The Supreme Court reference has no times, so both
    # are always 0 there.
    return quiet and row["ref_overlap"] == 0 and row["ignore_overlap"] == 0


def clearest(candidates: pd.DataFrame, how_many: int = 30) -> pd.DataFrame:
    """The plainest cases, spread over engines and terms, Supreme Court first.

    Only stretches inside the argument with at least one content word. Within
    each term and engine: not shared with another engine first, then not just
    after a reporter's dash (someone cut off, so overlapping speech the record
    left out is likely), then real words before speaker labels (there are many
    labels and they are all alike), then most content words, then least speech,
    then quietest. Then take one from each group in turn, at most two from any
    one recording.
    """
    pool = candidates[~candidates["at_edge"] & (candidates["n_content"] > 0)].copy()
    pool["shared"] = pool["shared_with"] != ""
    pool["after_dash"] = pool["record_context"].str.contains(r"-\s*\^")
    pool = pool.sort_values(["shared", "after_dash", "speaker_label", "n_content",
                             "speech_share", "level_vs_recording_db"],
                            ascending=[True, True, True, False, True, True])
    chosen, per_recording = [], {}
    for corpus in ["scotus", "edacc", "coraal", "earnings22"]:
        groups = [list(g.itertuples(index=False)) for _, g in
                  pool[pool["corpus"] == corpus].groupby(["term", "engine"])]
        while len(chosen) < how_many and any(groups):
            for group in groups:
                while group:
                    row = group.pop(0)
                    key = (row.corpus, row.docket)
                    if per_recording.get(key, 0) < 2:
                        per_recording[key] = per_recording.get(key, 0) + 1
                        chosen.append(row)
                        break
                if len(chosen) >= how_many:
                    break
    return pd.DataFrame(chosen, columns=pool.columns)


SHARED_COLUMNS = ["corpus", "part", "recording", "engine", "kind", "subkind", "start", "end",
                  "record", "engine_wrote", "record_context", "engine_context", "others_right",
                  "evidence", "start_clock", "content_words", "n_content", "shared_with",
                  "speech_share", "level_vs_recording_db", "confidence"]


def write_shared(candidates: pd.DataFrame, counts: pd.DataFrame, engines: dict) -> None:
    """The real cases in the format every finder shares (findings/failures/README.md).

    Real means quiet, inside the recording (not at an edge), not a speaker label,
    and holding at least one content word. `others_right` names the engines that
    wrote nothing there: the recording's other engines less those that inserted
    words at the same place. Subkind `phrase` is three words or more, else `word`.
    """
    real = candidates[~candidates["at_edge"] & ~candidates["speaker_label"]
                      & (candidates["n_content"] > 0)].copy()
    real["shared_with"] = real["shared_with"].fillna("")
    real["part"], real["recording"] = real["term"], real["docket"]
    real["kind"] = "invented"
    real["subkind"] = real["n_words"].map(lambda n: "phrase" if n >= 3 else "word")
    real["record"] = ""
    real["engine_wrote"] = real["words"]
    real["others_right"] = [
        " ".join(e for e in engines[(r.corpus, r.term, r.docket)]
                 if e != r.engine and e not in r.shared_with.split())
        for r in real.itertuples()]
    real["evidence"] = [f"{r.speech_share:.0%} speech, "
                        f"{-r.level_vs_recording_db:.0f} dB below the recording"
                        for r in real.itertuples()]
    SHARED.mkdir(parents=True, exist_ok=True)
    real[SHARED_COLUMNS].to_csv(SHARED / "candidates.csv", index=False)

    keys = ["corpus", "term", "engine"]
    out = counts[["arguments", "hours"]].rename(columns={"arguments": "recordings"})
    out["quiet_insertions"] = counts["quiet_candidates"]
    out["candidates"] = real.groupby(keys).size()
    out["alone"] = real[real["shared_with"] == ""].groupby(keys).size()
    out = out.fillna(0).astype({"candidates": int, "alone": int})
    out["candidates_per_hour"] = (out["candidates"] / out["hours"]).round(2)
    out["hours"] = out["hours"].round(1)
    out = out.reset_index().rename(columns={"term": "part"})
    # The website reads these by name: the shared columns first, the extras after.
    out = out[["corpus", "part", "engine", "recordings", "hours", "candidates",
               "candidates_per_hour", "quiet_insertions", "alone"]]
    out.to_csv(SHARED / "counts.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--terms", nargs="+", metavar="YEAR",
                        help="Supreme Court terms, e.g. 2010 2017 (default: all four)")
    parser.add_argument("--edacc", nargs="*", metavar="SPLIT",
                        help="EdAcc splits, test and/or dev (default: both)")
    parser.add_argument("--coraal", nargs="*", metavar="PART",
                        help="CORAAL components, e.g. ROC PRV DCB ATL (default: all eight)")
    parser.add_argument("--earnings22", nargs="*", metavar="REGION",
                        help="Earnings-22 regions, e.g. Asian (default: all)")
    parser.add_argument("--limit", type=int, help="only the first N recordings of each, to try it out")
    args = parser.parse_args()

    # Nothing chosen means everything. A bare --edacc, --coraal or --earnings22
    # means all its parts.
    if args.terms is None and args.edacc is None and args.coraal is None and args.earnings22 is None:
        terms, edacc, coraal = lineup.PARTS["scotus"], lineup.PARTS["edacc"], lineup.PARTS["coraal"]
        earnings22 = lineup.PARTS["earnings22"]
    else:
        terms = [t if t.startswith("OT") else f"OT{t}" for t in args.terms or []]
        edacc = [] if args.edacc is None else (args.edacc or lineup.PARTS["edacc"])
        coraal = [] if args.coraal is None else ([p.upper() for p in args.coraal]
                                                 or lineup.PARTS["coraal"])
        earnings22 = [] if args.earnings22 is None else (args.earnings22 or lineup.PARTS["earnings22"])

    jobs = recordings(terms, edacc, coraal, earnings22)
    if args.limit:
        keep = {}
        for job in jobs:
            keep.setdefault((job["corpus"], job["term"]), [])
            if len(keep[(job["corpus"], job["term"])]) < args.limit:
                keep[(job["corpus"], job["term"])].append(job)
        jobs = [job for group in keep.values() for job in group]
    print(f"{len(jobs)} recording(s)")

    started = time.monotonic()
    rows, hours, engines = [], [], {}
    for number, job in enumerate(jobs, 1):
        cached = lineup.fresh(cache_file(job), job)
        result = check(job)
        # Worked out here rather than cached, so the older cache files need no redo.
        skipped = ignored(job)
        for row in result["rows"]:
            row["ignore_overlap"] = round(sum(overlap((row["start"], row["end"]), s)
                                              for s in skipped), 2)
        rows += result["rows"]
        engines[(job["corpus"], job["term"], job["docket"])] = result["engines"]
        for engine in result["engines"]:
            hours.append({"corpus": job["corpus"], "term": job["term"], "engine": engine,
                          "docket": job["docket"], "hours": result["seconds"] / 3600})
        print(f"[{number}/{len(jobs)}] {job['term']} {job['docket']}: "
              f"{len(result['rows'])} insertions{' (cached)' if cached else ''} "
              f"{(time.monotonic() - started) / 60:.1f} min", flush=True)

    table = pd.DataFrame(rows)
    # These two are worked out again from the cached words, so the word lists
    # above can change without loading any audio.
    table["content_words"] = table["content_words"].apply(
        lambda text: " ".join(t for t in text.split() if is_content(t)))
    table["speaker_label"] = table["words"].apply(
        lambda text: any(LABEL.search(w) for w in text.split()))
    table["n_content"] = table["content_words"].str.split().str.len().fillna(0).astype(int)
    table["quiet"] = table.apply(is_quiet, axis=1)
    candidates = table[table["quiet"]].sort_values(["corpus", "term", "docket", "start"])

    OUT.mkdir(parents=True, exist_ok=True)
    candidates[COLUMNS].to_csv(OUT / "candidates.csv", index=False)
    clearest(candidates)[COLUMNS].to_csv(OUT / "clearest-30.csv", index=False)

    keys = ["corpus", "term", "engine"]
    counts = pd.DataFrame(hours).groupby(keys).agg(arguments=("docket", "nunique"),
                                                   hours=("hours", "sum"))
    counts["insert_chunks"] = table.groupby(keys).size()
    counts["quiet_candidates"] = candidates.groupby(keys).size()
    counts["of_which_speaker_labels"] = candidates[candidates["speaker_label"]].groupby(keys).size()
    counts = counts.fillna(0).astype({"insert_chunks": int, "quiet_candidates": int,
                                      "of_which_speaker_labels": int})
    counts["candidates_per_hour"] = (counts["quiet_candidates"] / counts["hours"]).round(2)
    write_shared(candidates, counts, engines)
    counts["hours"] = counts["hours"].round(1)
    counts.reset_index().to_csv(OUT / "counts.csv", index=False)

    print(f"\n{len(table):,} insertions, {len(candidates):,} on quiet audio")
    print(counts.to_string())
    print(f"\nin {(time.monotonic() - started) / 60:.1f} min -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

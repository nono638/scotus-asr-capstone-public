"""Stretches of clear speech an engine left out, with nothing to show the gap.

A "silent skip" here is a run of reference words that one engine did not write
at all, while the transcript around it reads on as if nothing was said. Whisper
is known to do this in fast back-and-forth talk, but every engine is checked.

For each recording, each engine is lined up against the reference with
tools/lineup.py. Every run of `delete` chunks is a stretch the engine left out.
Runs split by one or two words the engine wrote anyway are joined, the same way
the scoring stage joins its "omitted spans" (merge gap 2), so one long skip is
not counted as three short ones. A stretch is kept as a skip when:

1. at least 5 reference words are missing;
2. it is not at the very start or end of the recording;
3. one speaker said it: every word is from turns of one speaker, there is no
   reporter's dash near it (Supreme Court: someone cutting in), and on EdAcc and
   CORAAL no other speaker's turn overlaps it in time. Overlapping talk is a
   different, already known story and is left out here on purpose;
4. the speech is clear: at least one other engine wrote 80% or more of the
   missing words;
5. it is not a false start said again right beside it ("I'm I'm I'm a ... I'm a
   rebel"): fewer than 70% of the missing words come again, in the same order,
   in the record just before or after. Leaving out a restart is the edits
   finder's story;
6. it says something: at least two different content words are missing, so a
   run of "it's it's the the the" or "yeah yeah mm-hm" does not count;
7. the engine really wrote nothing there: at most a fifth of the word count of
   its own words fall inside that stretch of time (a stray "yeah" is allowed);
8. the times are usable: the stretch lasts at least 0.1 s a word;
9. the words are not in the engine's own output file after all (70% of them,
   in order and close together, within a minute). The line-up drops words timed inside stretches
   the reference does not score, and an aligner that squeezes words early can
   push real words there;
10. there is speech: Silero VAD hears speech in at least 60% of it.

Where the speech is, in seconds, comes from the engines that did write the
words (the median, over those engines, of their first and last word times). The skipping engine's
own neighbouring words are no use for this: Whisper stretches the word before
or after a skip over the whole gap, so its own timeline often shows no gap.

A skip within 2 seconds of a place where the pipeline cut the audio into chunks
is marked `at_seam` (the cut is the middle of the overlap between two chunks,
where the transcript switches from one chunk's words to the next's). Those are
our pipeline's doing, not the engine's, so they are counted on their own and
kept out of the shortlist. Chunk lengths come from
each run's config_used.yaml; Parakeet's extra half-splits come from its run.log.
Whisper decodes the whole file itself and has no pipeline seams.

Subkinds: `whole-turn` (the stretch is one or more complete turns of the
speaker), `long` (15 or more words), `short` (5 to 14).

Usage:
    python tools/find_skips.py                      # all three data sets
    python tools/find_skips.py --corpus coraal edacc
    python tools/find_skips.py --corpus scotus --limit 3   # a trial, saves nothing

Writes findings/failures/skips/candidates.csv and counts.csv, and
omissions-check.csv: what this finder made of each "omitted span" (25+ words)
the scoring stage flagged in the runs, as a cross-check. shortlist.csv is
picked by hand; when it exists, its hand-written columns (interest, clarity,
explanation, heard) are kept and the rest is refreshed from the new candidates.

The speech measurements are kept in findings/failures/skips/cache/, one small
file a recording, so a second run only loads audio for stretches it has not
measured yet. Processor only.
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import gzip
import json
import re
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowd  # noqa: E402
import lineup  # noqa: E402

from scotus_asr.scoring.normalize import normalize_tokens  # noqa: E402
from scotus_asr.scoring.pairs import _clock  # noqa: E402
from scotus_asr.scoring.speech import SAMPLE_RATE, load_audio, speech_regions  # noqa: E402

OUT = crowd.CAPSTONE / "findings" / "failures" / "skips"

MIN_WORDS = 5          # missing reference words
LONG_WORDS = 15        # this many or more is a "long" skip
MERGE_GAP = 2          # words the engine wrote anyway that may sit inside one skip
OTHERS_SHARE = 0.8     # another engine wrote this share of the missing words
MIN_SPEECH = 0.6       # share of the stretch Silero hears as speech
ENGINE_WORDS = 0.2     # the skipping engine may have this share of words inside
RESTART_SHARE = 0.7    # this share of the missing words said again, in order, right beside it
OVERLAP_SLACK = 0.1    # seconds another speaker's turn may touch it (timing slop)
SEAM_SLACK = 2.0       # seconds either side of a chunk cut that count as "at a seam"
VAD_PAD = 3.0          # seconds of audio either side given to the detector
MIN_CONTENT = 2        # different content words among the missing ones
MIN_SECONDS_PER_WORD = 0.1  # a span shorter than this a word has unusable times
RAW_REACH = 60.0       # seconds either side searched in the engine's raw output
CONTEXT = 6

NOT_CONTENT = (crowd.FILLERS | crowd.FUNCTION_WORDS | crowd.DISCOURSE | crowd.REPLIES
               | crowd.BACKCHANNELS | crowd.NUMBER_WORDS
               | {"know", "mean", "think", "guess", "like", "kind", "sort", "really", "am",
                  "going", "gonna", "wanna", "gotta", "got", "get", "em", "cause"})

SHARED = ["corpus", "part", "recording", "engine", "kind", "subkind", "start", "end",
          "record", "engine_wrote", "record_context", "engine_context", "others_right",
          "evidence"]
EXTRA = ["start_clock", "words", "content_words", "seconds", "speech_share", "engine_gap",
         "engine_words_inside", "at_seam", "seam", "speaker", "ref_start_token"]
HAND = ["interest", "clarity", "explanation", "heard"]


# --- where the pipeline cut the audio -------------------------------------------

def chunk_settings(run_dir: Path) -> tuple[float, float] | None:
    """(chunk seconds, overlap seconds) the run used, or None if it did not chunk."""
    config = yaml.safe_load((run_dir / "config_used.yaml").read_text(encoding="utf-8"))
    asr = config.get("asr", {})
    if not asr.get("chunk_seconds"):
        return None
    return float(asr["chunk_seconds"]), float(asr.get("overlap_seconds", 0.0))


def half_splits(run_dir: Path) -> dict[str, list[float]]:
    """Where Parakeet split a runaway chunk in two, by recording, from its run.log.

    The log says "300s of audio at 1460s in: ... decoding the two halves
    separately" and names the recording on the progress lines before it.
    """
    log = run_dir / "run.log"
    found: dict[str, list[float]] = {}
    if not log.exists():
        return found
    current = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        named = re.search(r"\[([^/\]]+)/asr/", line)
        if named:
            current = named.group(1)
        if "halves separately" in line.lower() and current:
            cut = re.search(r"(\d+)s of audio at (\d+)s in", line)
            if cut:
                found.setdefault(current, []).append(int(cut.group(2)) + int(cut.group(1)) / 2)
    return found


SEAM_INFO: dict[Path, tuple] = {}


def seams(run, recording: str, seconds: float) -> list[tuple[float, float]]:
    """Stretches of the recording near a chunk cut, for one engine's run.

    Chunk k starts at k * (chunk - overlap), and the chunk before it runs on for
    `overlap` seconds more. Words before the middle of that shared stretch are
    kept from the earlier chunk, words after it from the later one, so the middle
    is where the transcript switches from one decode to the next: the seam.
    Anything within SEAM_SLACK of it counts as at the seam.
    """
    if run.run_dir not in SEAM_INFO:
        SEAM_INFO[run.run_dir] = (chunk_settings(run.run_dir), half_splits(run.run_dir))
    settings, splits = SEAM_INFO[run.run_dir]
    if settings is None:
        return []
    chunk, overlap = settings
    zones, cut = [], chunk - overlap
    while cut < seconds:
        middle = cut + overlap / 2
        zones.append((middle - SEAM_SLACK, middle + SEAM_SLACK))
        cut += chunk - overlap
    zones += [(at - SEAM_SLACK, at + SEAM_SLACK) for at in splits.get(recording, [])]
    return zones


# --- one engine's skips ------------------------------------------------------------

def matched_times(alignment, words) -> dict[int, tuple[float, float]]:
    """For each reference token this engine wrote exactly, the time of that word."""
    times = {}
    source = alignment.hypothesis.source_index
    for chunk in alignment.chunks:
        if chunk.kind == "equal":
            for k in range(chunk.ref_end - chunk.ref_start):
                word = words[source[chunk.hyp_start + k]]
                times[chunk.ref_start + k] = (word.start, word.end)
    return times


def stretches(alignment) -> list[tuple[int, int, int]]:
    """(first token, one past the last, hypothesis position) of each run of
    deleted reference tokens, joining runs split by MERGE_GAP tokens or fewer."""
    runs, open_at, end, hyp_at, covered = [], None, 0, 0, 0
    for chunk in alignment.chunks:
        if chunk.kind == "delete":
            if open_at is None:
                open_at, hyp_at = chunk.ref_start, chunk.hyp_start
            end, covered = chunk.ref_end, 0
        elif chunk.kind != "insert" and open_at is not None:
            covered += chunk.ref_end - chunk.ref_start
            if covered > MERGE_GAP:
                runs.append((open_at, end, hyp_at))
                open_at, covered = None, 0
    if open_at is not None:
        runs.append((open_at, end, hyp_at))
    return runs


def is_content(token: str) -> bool:
    return len(token) > 1 and not any(ch.isdigit() for ch in token) and token not in NOT_CONTENT


def turn_bounds(turn_of: list[int]) -> dict[int, tuple[int, int]]:
    """First and one-past-last reference token of each turn."""
    bounds: dict[int, list[int]] = {}
    for k, turn in enumerate(turn_of):
        bounds.setdefault(turn, [k, k + 1])[1] = k + 1
    return {t: (a, b) for t, (a, b) in bounds.items()}


def skips_in(job: dict, name: str, lined: dict, times: dict, seconds: float) -> list[dict]:
    """Every stretch this engine left out, with the checks it passed or failed."""
    transcript, reference_words, alignment, words = lined[name]
    ref = alignment.reference
    turn_of_word = lineup.word_turns(transcript)
    turn_of = [turn_of_word[i] for i in ref.source_index]
    bounds = turn_bounds(turn_of)
    turns = transcript.turns
    timed = [(t.start, t.end, t.speaker) for t in turns if t.start is not None]
    timed.sort()
    starts = [t[0] for t in timed]
    hyp_source = alignment.hypothesis.source_index
    word_starts = [w.start for w in words]
    run = next(m for m in job["models"] if m.name == name)
    seam_zones = seams(run, job["docket"], seconds)
    mine = times[name]

    rows = []
    for r0, r1, hyp_at in stretches(alignment):
        missing = [k for k in range(r0, r1) if k not in mine]
        if len(missing) < MIN_WORDS:
            continue
        w0, w1 = ref.source_index[r0], ref.source_index[r1 - 1] + 1
        row = {"corpus": job["corpus"], "part": job["term"], "recording": job["docket"],
               "engine": name, "kind": "skips", "words": len(missing),
               "missing_tokens": [ref.tokens[k] for k in missing],
               "ref_start_token": r0, "ref_end_token": r1, "reason": ""}

        # Where the engine was just before and just after.
        before = hyp_source[hyp_at - 1] if hyp_at > 0 else None
        after = hyp_source[hyp_at] if hyp_at < len(hyp_source) else None
        # The engine's own last word before and first word after (for matching
        # the scoring stage's omitted spans, which are timed this way).
        row["gap_start"] = words[before].end if before is not None else None
        row["gap_end"] = words[after].start if after is not None else None
        if before is None or after is None or r0 == 0 or r1 >= len(ref.tokens):
            row["reason"] = "edge"
            rows.append(row)
            continue
        row["engine_gap"] = round(max(0.0, words[after].start - words[before].end), 2)

        # Who said it.
        speakers = {turns[t].speaker for t in turn_of[r0:r1]}
        row["speaker"] = " / ".join(sorted(speakers))
        whole = bounds[turn_of[r0]][0] == r0 and bounds[turn_of[r1 - 1]][1] == r1
        row["subkind"] = "whole-turn" if whole else "long" if len(missing) >= LONG_WORDS else "short"

        # Which other engines wrote it, and where in the recording it is.
        right, spans, shares = [], [], []
        for other in lined:
            if other == name:
                continue
            got = [times[other][k] for k in missing if k in times[other]]
            share = len(got) / len(missing)
            shares.append(f"{other} {len(got)}")
            if share >= OTHERS_SHARE:
                right.append(other)
                spans.append((min(t[0] for t in got), max(t[1] for t in got)))
        row["others_right"] = " ".join(right)
        row["others_wrote"] = ", ".join(shares)

        # The record and the engine, side by side.
        row["record"] = " ".join(reference_words[w0:w1])
        row["record_context"] = " ".join(reference_words[max(0, w0 - CONTEXT):w0] + ["["]
                                         + reference_words[w0:w1] + ["]"]
                                         + reference_words[w1:w1 + CONTEXT]).replace("[ ", "[").replace(" ]", "]")
        content = [ref.tokens[k] for k in missing if is_content(ref.tokens[k])]
        row["content_words"] = " ".join(content)

        if spans:
            start = statistics.median(s for s, _ in spans)
            end = max(start + 0.1, statistics.median(e for _, e in spans))
        else:
            start, end = words[before].end, words[after].start
        # An aligner sometimes stamps a run of words all at one instant. Then
        # the other engines' times say little; take in the skipping engine's
        # own gap as well, and give up on the stretch if it is still too short.
        if end - start < MIN_SECONDS_PER_WORD * len(missing):
            start = min(start, row["gap_start"])
            end = max(end, row["gap_end"])
        row["start"], row["end"] = round(start, 2), round(end, 2)
        row["start_clock"] = _clock(start)
        row["seconds"] = round(end - start, 2)

        # What the engine itself wrote inside that time (word middles inside it).
        lo = bisect.bisect_left(word_starts, start - 30)
        hi = bisect.bisect_right(word_starts, end + 30)
        inside = [i for i in range(lo, hi) if start <= (words[i].start + words[i].end) / 2 <= end]
        row["engine_words_inside"] = len(inside)
        row["engine_wrote"] = " ".join(words[i].text.strip() for i in inside)
        first, last = (inside[0], inside[-1]) if inside else (after, before)
        row["engine_context"] = (" ".join(w.text.strip() for w in words[max(0, first - CONTEXT):first])
                                 + " [" + row["engine_wrote"] + "] "
                                 + " ".join(w.text.strip() for w in words[last + 1:last + 1 + CONTEXT]))

        zones = [z for z in seam_zones if z[0] < end and start < z[1]]
        row["at_seam"] = bool(zones)
        row["seam"] = f"{zones[0][0] + SEAM_SLACK:.0f}s" if zones else ""

        # The checks, in order; the first one failed is the reason.
        if len(speakers) > 1:
            row["reason"] = "two speakers"
        elif job["corpus"] == "scotus" and any(
                crowd.near_interruption(reference_words, i) for i in range(w0, w1)):
            row["reason"] = "interruption"
        elif timed and other_speaker_overlap(timed, starts, start, end, speakers) > OVERLAP_SLACK:
            row["reason"] = "overlap"
        elif is_restart(ref.tokens, r0, r1):
            row["reason"] = "restart"
        elif len(set(content)) < MIN_CONTENT:
            row["reason"] = "small words only"
        elif not right:
            row["reason"] = "unclear"
        elif len(inside) > ENGINE_WORDS * len(missing):
            row["reason"] = "engine wrote there"
        elif end - start < MIN_SECONDS_PER_WORD * len(missing):
            row["reason"] = "timing unclear"
        rows.append(row)
    return rows


def is_restart(tokens: list[str], r0: int, r1: int) -> bool:
    """The missing words are said again just before or after: a false start.

    "they're they're gonna go to that, they're going to go to that university"
    written once lines up as the first try left out. That is the engine tidying
    a restart (the edits finder's story), not a skip. The words have to come
    back in the same order, so a few common small words nearby do not count.
    """
    gone = tokens[r0:r1]
    reach = len(gone) + 3
    for beside in (tokens[max(0, r0 - reach):r0], tokens[r1:r1 + reach]):
        same = difflib.SequenceMatcher(None, gone, beside, autojunk=False)
        if sum(block.size for block in same.get_matching_blocks()) >= RESTART_SHARE * len(gone):
            return True
    return False


def other_speaker_overlap(timed, starts, start, end, speakers) -> float:
    """Seconds of another speaker's turns inside start..end."""
    total = 0.0
    lo = bisect.bisect_left(starts, start - 120)
    for t0, t1, who in timed[lo:]:
        if t0 >= end:
            break
        if who not in speakers:
            total += max(0.0, min(t1, end) - max(t0, start))
    return total


def raw_words(run, recording: str) -> list[tuple[float, str]]:
    """Every word in the engine's own output file, before anything is removed."""
    data = json.loads(run.asr_file(recording).read_text(encoding="utf-8"))
    return [(w["start"], w["text"]) for segment in data["segments"]
            for w in segment.get("words", [])]


def in_raw_output(raw: list[tuple[float, str]], row: dict) -> bool:
    """Whether the engine did write these words, near here, in its own file.

    The shared word list leaves out words timed inside a stretch the reference
    does not score, and seam repeats. A forced aligner that squeezes a run of
    words twenty seconds early can push real words into one of those and they
    vanish from the line-up. Qwen3 on CORAAL did exactly that. So look in the
    raw output, a minute either side: 70% of the missing words in the same
    order, close together, means the engine wrote them.
    """
    near = [text for start, text in raw
            if row["start"] - RAW_REACH <= start <= row["end"] + RAW_REACH]
    tokens = normalize_tokens(near, "standard", harmonise=True).tokens
    gone = row["missing_tokens"]
    # Anchor on the longest run the two share, then ask for the rest close by,
    # so a few common words scattered over two minutes do not count.
    longest = difflib.SequenceMatcher(None, gone, tokens, autojunk=False).find_longest_match()
    if longest.size < 2:
        return False
    first = max(0, longest.b - longest.a - 2)
    window = tokens[first:first + len(gone) + 4]
    same = difflib.SequenceMatcher(None, gone, window, autojunk=False)
    return sum(b.size for b in same.get_matching_blocks()) >= RESTART_SHARE * len(gone)


# --- speech measurement, cached ----------------------------------------------------

def cache_file(job: dict) -> Path:
    return OUT / "cache" / job["corpus"] / job["term"] / f"{job['docket']}.json.gz"


def read_cache(job: dict) -> dict:
    path = cache_file(job)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return {"seconds": None, "speech": {}}


def write_cache(job: dict, cache: dict) -> None:
    path = cache_file(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(cache, stream)


def span_key(row: dict) -> str:
    return f"{row['start']:.2f}-{row['end']:.2f}"


def measure(job: dict, rows: list[dict], cache: dict) -> bool:
    """Speech share of every stretch that passed the other checks. True if new."""
    todo = [r for r in rows if not r["reason"] and span_key(r) not in cache["speech"]]
    if not todo:
        return False
    audio = load_audio(job["audio"])
    for row in todo:
        lo = max(0.0, row["start"] - VAD_PAD)
        piece = audio[int(lo * SAMPLE_RATE):int((row["end"] + VAD_PAD) * SAMPLE_RATE)]
        regions = [(a + lo, b + lo) for a, b in speech_regions(piece)]
        speech = sum(max(0.0, min(b, row["end"]) - max(a, row["start"])) for a, b in regions)
        cache["speech"][span_key(row)] = round(speech / max(row["end"] - row["start"], 0.01), 3)
    return True


def recording_seconds(job: dict, cache: dict) -> float:
    if cache["seconds"] is None:
        data = json.loads(job["models"][0].asr_file(job["docket"]).read_text(encoding="utf-8"))
        cache["seconds"] = float(data["audio_seconds"])
    return cache["seconds"]


def load(job: dict, tries: int = 10) -> dict:
    """lineup.load, waiting if the cache file is being written right now."""
    for attempt in range(tries):
        try:
            return lineup.load(job)
        except (EOFError, gzip.BadGzipFile, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(20)


def check(job: dict) -> tuple[list[dict], float, list[str]]:
    """Every left-out stretch in one recording, every engine, checked and measured."""
    lined = load(job)
    cache = read_cache(job)
    seconds = recording_seconds(job, cache)
    times = {name: matched_times(one[2], one[3]) for name, one in lined.items()}
    rows = []
    for name in lined:
        rows += skips_in(job, name, lined, times, seconds)
    raw = {}
    for row in rows:
        if not row["reason"]:
            if row["engine"] not in raw:
                run = next(m for m in job["models"] if m.name == row["engine"])
                raw[row["engine"]] = raw_words(run, job["docket"])
            if in_raw_output(raw[row["engine"]], row):
                row["reason"] = "in raw output"
    changed = measure(job, rows, cache)
    for row in rows:
        if row["reason"]:
            continue
        row["speech_share"] = cache["speech"][span_key(row)]
        if row["speech_share"] < MIN_SPEECH:
            row["reason"] = "no speech"
    if changed or not cache_file(job).exists():
        write_cache(job, cache)
    return rows, seconds, list(lined)


def evidence(row: pd.Series) -> str:
    others = row["others_right"].split()
    return (f"{row['words']} words dropped; {row['speech_share']:.0%} speech over "
            f"{row['seconds']:.1f}s; {' and '.join(others)} wrote them "
            f"(of {row['words']}: {row['others_wrote']})"
            + (f"; at a chunk seam ({row['seam']})" if row["at_seam"] else ""))


# --- tables ------------------------------------------------------------------------

def counts_table(table: pd.DataFrame, hours: pd.DataFrame) -> pd.DataFrame:
    keys = ["corpus", "part", "engine"]
    counts = hours.groupby(keys).agg(recordings=("recording", "nunique"), hours=("hours", "sum"))
    found = table[table["reason"] == ""]
    clean, seam = found[~found["at_seam"]], found[found["at_seam"]]
    counts["left_out_stretches"] = table.groupby(keys).size()
    for reason in ["edge", "two speakers", "interruption", "overlap", "restart",
                   "small words only", "unclear", "engine wrote there", "timing unclear",
                   "in raw output", "no speech"]:
        counts[f"not_{reason.replace(' ', '_')}"] = table[table["reason"] == reason].groupby(keys).size()
    counts["skips"] = clean.groupby(keys).size()
    counts["skipped_words"] = clean.groupby(keys)["words"].sum()
    for subkind in ["short", "long", "whole-turn"]:
        counts[subkind] = clean[clean["subkind"] == subkind].groupby(keys).size()
    counts["skips_25_plus"] = clean[clean["words"] >= 25].groupby(keys).size()
    counts["at_seam"] = seam.groupby(keys).size()
    counts["at_seam_words"] = seam.groupby(keys)["words"].sum()
    counts = counts.fillna(0)
    for column in counts.columns:
        if column != "hours":
            counts[column] = counts[column].astype(int)
    counts["skips_per_hour"] = (counts["skips"] / counts["hours"]).round(2)
    counts["skipped_words_per_hour"] = (counts["skipped_words"] / counts["hours"]).round(1)
    counts["hours"] = counts["hours"].round(1)
    # The shared columns every finder's counts.csv starts with (the website reads them).
    counts["candidates"] = counts["skips"]
    counts["candidates_per_hour"] = counts["skips_per_hour"]
    first = ["hours", "candidates", "candidates_per_hour"]
    counts = counts[first + [c for c in counts.columns if c not in first]]
    return counts.reset_index()


def omitted_spans(jobs: list[dict]) -> pd.DataFrame:
    """The scoring stage's omitted spans (25+ words) for these recordings.

    Each run writes results/omissions.csv; a run with none writes no file.
    """
    wanted = {(m.run_dir, job["docket"]): (job, m.name) for job in jobs for m in job["models"]}
    rows = []
    for run_dir in {m.run_dir for job in jobs for m in job["models"]}:
        path = run_dir / "results" / "omissions.csv"
        if not path.exists():
            continue
        for _, span in pd.read_csv(path).iterrows():
            if (run_dir, str(span["docket"])) in wanted:
                job, name = wanted[(run_dir, str(span["docket"]))]
                rows.append({"corpus": job["corpus"], "part": job["term"],
                             "recording": job["docket"], "engine": name,
                             "omitted_words": span["word_count"],
                             "audio_start": span["audio_start"], "audio_end": span["audio_end"],
                             "ref_start_token": span["ref_start_token"],
                             "text": str(span["text"])[:200]})
    return pd.DataFrame(rows)


def check_omissions(table: pd.DataFrame, jobs: list[dict]) -> pd.DataFrame:
    """What this finder made of each of the scoring stage's omitted spans.

    Matched by time: the omitted span's start (the engine's last word before
    it) against the same engine's stretches here, give or take 3 seconds, or
    failing that by reference position (the two use slightly different word
    lists, so token numbers drift a little).
    """
    spans = omitted_spans(jobs)
    if spans.empty:
        return spans
    verdicts = []
    for _, span in spans.iterrows():
        mine = table[(table["recording"] == span["recording"]) & (table["engine"] == span["engine"])]
        near = mine[((mine["gap_start"] - span["audio_start"]).abs() <= 3)
                    | ((mine["start"] <= span["audio_end"] + 3) & (mine["end"] >= span["audio_start"] - 3))]
        if near.empty:
            near = mine[(mine["ref_start_token"] - span["ref_start_token"]).abs() <= 40]
        if near.empty:
            verdicts.append(("not found", 0))
            continue
        best = near.sort_values("words", ascending=False).iloc[0]
        verdict = best["reason"] or ("skip at seam" if best["at_seam"] else "skip")
        verdicts.append((verdict, best["words"]))
    spans["verdict"] = [v for v, _ in verdicts]
    spans["words_here"] = [w for _, w in verdicts]
    return spans


def refresh_shortlist(candidates: pd.DataFrame) -> None:
    """Keep the hand-written columns of shortlist.csv, refresh the rest."""
    path = OUT / "shortlist.csv"
    if not path.exists():
        return
    picks = pd.read_csv(path, dtype=str, keep_default_na=False)
    key = ["corpus", "recording", "engine", "ref_start_token"]
    fresh = candidates.astype({"ref_start_token": str})
    merged = picks[key + HAND].merge(fresh, on=key, how="left", indicator=True)
    lost = merged[merged["_merge"] == "left_only"]
    for _, row in lost.iterrows():
        print(f"shortlist: {row['recording']} {row['engine']} token {row['ref_start_token']} "
              f"is no longer a candidate; kept as it was")
    kept = merged[merged["_merge"] == "both"][SHARED + HAND + EXTRA]
    stale = picks[picks.set_index(key).index.isin(lost.set_index(key).index)]
    pd.concat([kept, stale[kept.columns.intersection(stale.columns)]]).to_csv(path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", nargs="+", choices=list(lineup.PARTS),
                        default=list(lineup.PARTS))
    parser.add_argument("--limit", type=int, help="only the first N recordings of each part")
    args = parser.parse_args()

    jobs = []
    for corpus in args.corpus:
        for job in lineup.recordings(corpus):
            same = [j for j in jobs if (j["corpus"], j["term"]) == (corpus, job["term"])]
            if not args.limit or len(same) < args.limit:
                jobs.append(job)
    print(f"{len(jobs)} recording(s)")

    started = time.monotonic()
    rows, hours = [], []
    for number, job in enumerate(jobs, 1):
        found, seconds, engines = check(job)
        rows += found
        hours += [{"corpus": job["corpus"], "part": job["term"], "engine": e,
                   "recording": job["docket"], "hours": seconds / 3600} for e in engines]
        kept = sum(1 for r in found if not r["reason"])
        print(f"[{number}/{len(jobs)}] {job['corpus']} {job['term']} {job['docket']}: "
              f"{len(found)} stretches, {kept} skips "
              f"{(time.monotonic() - started) / 60:.1f} min", flush=True)

    table = pd.DataFrame(rows)
    for column in EXTRA + SHARED + ["others_wrote", "speech_share"]:
        if column not in table:
            table[column] = None
    table["reason"] = table["reason"].fillna("")
    table["at_seam"] = table["at_seam"].fillna(False).astype(bool)

    found = table[table["reason"] == ""].copy()
    found["evidence"] = found.apply(evidence, axis=1)
    found = found.sort_values(["corpus", "part", "recording", "start", "engine"])

    counts = counts_table(table, pd.DataFrame(hours))
    if args.limit:
        print("(a trial with --limit: nothing saved)")
    else:
        # Only the data sets run this time are replaced; the others are kept.
        OUT.mkdir(parents=True, exist_ok=True)
        out = found[SHARED + EXTRA + ["others_wrote"]].astype(str)
        saved = OUT / "candidates.csv"
        if saved.exists():
            old = pd.read_csv(saved, dtype=str, keep_default_na=False)
            out = pd.concat([old[~old["corpus"].isin(args.corpus)], out], ignore_index=True)
        out.to_csv(saved, index=False)
        saved = OUT / "counts.csv"
        everything = counts
        if saved.exists():
            old = pd.read_csv(saved)
            everything = pd.concat([old[~old["corpus"].isin(args.corpus)], counts], ignore_index=True)
        everything.to_csv(saved, index=False)
        refresh_shortlist(out)
        crosscheck = check_omissions(table, jobs)
        saved = OUT / "omissions-check.csv"
        if saved.exists():
            old = pd.read_csv(saved)
            crosscheck = pd.concat([old[~old["corpus"].isin(args.corpus)], crosscheck], ignore_index=True)
        crosscheck.to_csv(saved, index=False)
        print(pd.crosstab([crosscheck["corpus"], crosscheck["engine"]], crosscheck["verdict"]).to_string())

    print(counts[["corpus", "part", "engine", "hours", "left_out_stretches", "skips",
                  "skipped_words", "at_seam", "skips_per_hour"]].to_string(index=False))
    print(f"\nin {(time.monotonic() - started) / 60:.1f} min -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

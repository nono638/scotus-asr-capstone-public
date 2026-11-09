"""Places where a speech engine broke down, rather than misheard.

The other four finders look for mistakes a listener could make: a wrong word, a
word over silence, grammar tidied, a sentence left out. This one looks for the
engine (or our pipeline around it) not working at all for a while. Three kinds:

  blackout  30 seconds or more where the engine wrote (almost) nothing, while the
            reference has words there, another engine wrote most of them, and
            Silero VAD hears some speech. A chunk that came back empty, or Parakeet's
            decoder stuck after a full stop (findings/parakeet-stall/). Unlike a
            skip, any number of speakers may be talking.
  loop      the same phrase of 2-6 words written 4 or more times in a row (one word:
            8 times), or a passage of 8 words or more written 3 or more times within
            five minutes (60 words in all), where neither the reference nor
            any other engine repeats itself like that at the same moment. A decoder
            stuck repeating itself ("Okay. Okay. Okay. ..." 169 times). People
            repeat themselves too ("no, no, no, no"); then the other engines write
            the repeat as well, which is why they are asked.
  artifact  text that is not speech: letters from another alphabet than the
            reference's (Hangul, Cyrillic, Chinese), the replacement character
            left by a broken text encoding, model tags ("<|...|>", "[BLANK_AUDIO]",
            "(Laughter)"), music symbols, a stray backslash or "____", markdown
            "*emphasis*", stock subtitle lines ("thanks for watching") the
            reference does not have, and "words" of 25 letters or more with no
            hyphen. Artifact words close together (within a minute) are one case.

Each case is read off the engine's own output file (the raw words, before the
line-up drops anything), and placed against the reference with tools/lineup.py:
each reference word gets the time other engines gave it when they wrote it
exactly. A blackout is thrown out when:

  - the reference has few words there (under 15, or under one every 4 seconds);
  - no other engine wrote half or more of the reference words there;
  - the engine did write them, only timed elsewhere: it matched 30% or more of
    them in the line-up, or 50% of them turn up in its own file within a minute
    (Qwen3's aligner sometimes squeezes a run of words early);
  - Silero hears speech in less than a quarter of it. This is only a guard against a
    misplaced reference: noisy, laughing talk often reads 30-40% speech.

A blackout or loop within 2 seconds of a place where the pipeline cut the audio
into chunks is marked `at_seam`; find_skips.py explains the seams.

Every case has the shared columns (findings/failures/README.md). The subkind is
blackout, loop or artifact; `what` says more (empty stretch, "okay" x170,
Hangul x210). per-recording.csv gives, per recording and engine, the seconds in
each kind and `broken_share`, the share of the recording they cover.

Usage:
    python tools/find_breakdowns.py                      # every data set
    python tools/find_breakdowns.py --corpus earnings22 coraal
    python tools/find_breakdowns.py --recording 4426736 MP3-A   # a few, saves nothing

Writes findings/failures/breakdown/: candidates.csv, counts.csv, per-recording.csv.
The speech measurements are kept in findings/failures/breakdown/cache/ (one small
file a recording), so a second run loads audio only for new stretches.
Processor only.
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import json
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowd  # noqa: E402
import find_skips as skips  # noqa: E402  (seams, speech cache, line-up loading)
import lineup  # noqa: E402

from scotus_asr.scoring.normalize import normalize_tokens  # noqa: E402
from scotus_asr.scoring.pairs import _clock  # noqa: E402
from scotus_asr.scoring.speech import SAMPLE_RATE, load_audio, speech_regions  # noqa: E402

OUT = crowd.CAPSTONE / "findings" / "failures" / "breakdown"

MIN_BLACKOUT = 30.0     # seconds with (almost) no engine word
GAP = 10.0              # a pause this long between two engine words starts an empty stretch
STRAY = 3               # engine words that may sit inside one blackout
MIN_REF_WORDS = 15      # reference words in a blackout
SECONDS_PER_REF_WORD = 4.0  # ...and at least one every this many seconds
OTHERS_SHARE = 0.5      # another engine wrote this share of them
OWN_SHARE = 0.3         # the engine itself matched this share: words there, timed elsewhere
RAW_SHARE = 0.5         # ...or this share is in its own file within RAW_REACH
RAW_REACH = 60.0
MIN_SPEECH = 0.25       # share of a blackout Silero hears as speech (only a guard: the
                        # reference and another engine already say someone spoke)
VAD_PAD = 3.0

LOOP_REPEATS = 4        # a 2-6 word phrase this many times in a row
WORD_REPEATS = 8        # a single word this many times (people stammer "the the the the")
LOOP_LONGEST = 6
PASSAGE = 8             # a passage of this many words...
PASSAGE_REPEATS = 3     # ...written this many times...
PASSAGE_REACH = 300.0   # ...within this many seconds
LOOP_JOIN = 60.0        # copies of a passage this close are one loop
LOOP_WINDOW = 15.0      # seconds either side where the reference may repeat it too
PASSAGE_SHORT = 60      # a passage loop must hold this many words in all
OTHERS_REACH = 3.0      # seconds either side where another engine may repeat itself too

ARTIFACT_JOIN = 60.0    # artifact words this close are one case
LONG_WORD = 25          # letters in a "word" with no hyphen, slash or dot
STOCK = ["thanks for watching", "thank you for watching", "subtitles by", "please subscribe",
         "like and subscribe", "transcribed by", "captioned by", "amara org"]
MUSIC = set("♪♫♬🎵🎶")
CONTEXT = 6
SHOWN = 60              # words of a long stretch written into the record / engine_wrote columns

SHARED = ["corpus", "part", "recording", "engine", "kind", "subkind", "start", "end",
          "record", "engine_wrote", "record_context", "engine_context", "others_right",
          "evidence"]
EXTRA = ["what", "start_clock", "seconds", "ref_words", "engine_words", "others_repeat", "speech_share",
         "at_seam", "seam", "ref_start_token"]


# --- the engine's own words, and where the reference words fall ---------------------

def raw_words(run, recording: str) -> list[tuple[float, float, str]]:
    """(start, end, text) of every word in the engine's own output file."""
    data = json.loads(run.asr_file(recording).read_text(encoding="utf-8"))
    words = [(w["start"], w["end"], w["text"].strip()) for s in data["segments"]
             for w in s.get("words", []) if w.get("start") is not None]
    return sorted(words, key=lambda w: w[0])


def reference_placing(lined: dict, name: str, times: dict) -> list[float | None]:
    """A time for each reference token, from the *other* engines that wrote it
    exactly (the median of theirs), or None where none did."""
    tokens = len(lined[name][2].reference.tokens)
    placed: list[float | None] = []
    for k in range(tokens):
        got = [times[o][k][0] for o in times if o != name and k in times[o]]
        placed.append(statistics.median(got) if got else None)
    return placed


def tokens_between(placed: list[float | None], start: float, end: float) -> tuple[int, int] | None:
    """First and one-past-last reference token placed inside start..end."""
    inside = [k for k, t in enumerate(placed) if t is not None and start <= t <= end]
    return (inside[0], inside[-1] + 1) if inside else None


def show(words: list[str]) -> str:
    if len(words) <= SHOWN:
        return " ".join(words)
    return " ".join(words[:SHOWN]) + f" ... ({len(words)} words)"


def contexts(row: dict, reference_words, ref, r0, r1, raw, i0, i1) -> None:
    """record / engine_wrote and their contexts, the stretch in [brackets]."""
    if r0 is not None and r1 > r0:
        w0, w1 = ref.source_index[r0], ref.source_index[r1 - 1] + 1
        row["record"] = show(reference_words[w0:w1])
        row["record_context"] = (" ".join(reference_words[max(0, w0 - CONTEXT):w0]) + " ["
                                 + row["record"] + "] " + " ".join(reference_words[w1:w1 + CONTEXT]))
    else:
        row["record"], row["record_context"] = "", ""
    texts = [w[2] for w in raw]
    row["engine_wrote"] = show(texts[i0:i1])
    row["engine_context"] = (" ".join(texts[max(0, i0 - CONTEXT):i0]) + " ["
                             + row["engine_wrote"] + "] " + " ".join(texts[i1:i1 + CONTEXT]))


def others_right(lined, name, times, r0, r1) -> str:
    """The other engines that wrote half or more of reference tokens r0..r1 exactly."""
    if r0 is None or r1 <= r0:
        return ""
    return " ".join(o for o in times if o != name
                    and sum(1 for k in range(r0, r1) if k in times[o]) >= OTHERS_SHARE * (r1 - r0))


# --- blackouts ------------------------------------------------------------------------

def empty_stretches(raw: list, seconds: float) -> list[tuple[float, float, int, int]]:
    """(start, end, first word inside, one past the last word inside) of each
    stretch of MIN_BLACKOUT or more with at most STRAY engine words in it."""
    gaps = []   # (start, end, index of the word after the gap)
    last_end = 0.0
    for i, w in enumerate(raw):
        if w[0] - last_end >= GAP:
            gaps.append((last_end, w[0], i))
        last_end = max(last_end, w[1])
    if seconds - last_end >= GAP:
        gaps.append((last_end, seconds, len(raw)))
    out = []
    for g in gaps:
        if out and g[2] - out[-1][3] <= STRAY:
            # Join it to the stretch before: only a few stray words between them.
            out[-1] = (out[-1][0], g[1], out[-1][2], g[2])
        else:
            out.append((g[0], g[1], g[2], g[2]))
    return [s for s in out if s[1] - s[0] >= MIN_BLACKOUT]


def in_own_file(raw, gone: list[str], start: float, end: float) -> float:
    """Share of the missing reference tokens found, in order, in the engine's own
    file within RAW_REACH of the stretch."""
    near = [w[2] for w in raw if start - RAW_REACH <= w[0] <= end + RAW_REACH]
    tokens = normalize_tokens(near, "standard", harmonise=True).tokens
    same = difflib.SequenceMatcher(None, gone, tokens, autojunk=False)
    return sum(b.size for b in same.get_matching_blocks()) / max(len(gone), 1)


def blackouts(job, name, lined, times, placed, raw, seconds) -> list[dict]:
    transcript, reference_words, alignment, _ = lined[name]
    ref = alignment.reference
    rows = []
    for start, end, i0, i1 in empty_stretches(raw, seconds):
        row = {"corpus": job["corpus"], "part": job["term"], "recording": job["docket"],
               "engine": name, "kind": "breakdown", "subkind": "blackout",
               "start": round(start, 2), "end": round(end, 2), "seconds": round(end - start, 1),
               "engine_words": i1 - i0, "reason": ""}
        span = tokens_between(placed, start, end)
        r0, r1 = span if span else (None, None)
        row["ref_words"] = (r1 - r0) if span else 0
        row["ref_start_token"] = r0
        row["others_right"] = others_right(lined, name, times, r0, r1)
        contexts(row, reference_words, ref, r0, r1, raw, i0, i1)
        row["what"] = ("nothing written" if i1 == i0 else f"{i1 - i0} stray words") + \
            (", at the start" if start < GAP else ", at the end" if end > seconds - GAP else "")
        if row["ref_words"] < max(MIN_REF_WORDS, (end - start) / SECONDS_PER_REF_WORD):
            row["reason"] = "few reference words"
        elif not row["others_right"]:
            row["reason"] = "no other engine wrote it"
        else:
            own = sum(1 for k in range(r0, r1) if k in times[name]) / (r1 - r0)
            if own >= OWN_SHARE:
                row["reason"] = "words there, timed elsewhere"
            elif in_own_file(raw, ref.tokens[r0:r1], start, end) >= RAW_SHARE:
                row["reason"] = "in raw output"
        rows.append(row)
    return rows


# --- loops ----------------------------------------------------------------------------

def repeats_at(tokens: list[str], i: int, n: int) -> int:
    """How many times tokens[i:i+n] comes in a row from i."""
    phrase, count = tokens[i:i + n], 1
    while tokens[i + count * n:i + (count + 1) * n] == phrase:
        count += 1
    return count


def short_loops(tokens: list[str]) -> list[tuple[int, int, int, int]]:
    """(first token, one past the last, phrase length, repeats) of every 1-6 word
    phrase written LOOP_REPEATS or more times in a row."""
    out, i = [], 0
    while i < len(tokens):
        best = (0, 0)
        for n in range(1, LOOP_LONGEST + 1):
            if i + n > len(tokens):
                break
            count = repeats_at(tokens, i, n)
            if count >= (WORD_REPEATS if n == 1 else LOOP_REPEATS) and count * n > best[0] * best[1]:
                best = (count, n)
        if best[0]:
            out.append((i, i + best[0] * best[1], best[1], best[0]))
            i += best[0] * best[1]
        else:
            i += 1
    return out


def passage_loops(tokens: list[str], when: list[float]) -> list[tuple[int, int, int, int]]:
    """(first token, one past the last, PASSAGE, copies) of every stretch where an
    8-token passage comes PASSAGE_REPEATS or more times within PASSAGE_REACH."""
    where: dict[tuple, list[int]] = {}
    for i in range(len(tokens) - PASSAGE + 1):
        where.setdefault(tuple(tokens[i:i + PASSAGE]), []).append(i)
    marked = [0] * len(tokens)
    for at in where.values():
        if len(at) < PASSAGE_REPEATS:
            continue
        for a in range(len(at) - PASSAGE_REPEATS + 1):
            close = at[a:a + PASSAGE_REPEATS]
            if when[close[-1]] - when[close[0]] <= PASSAGE_REACH and all(
                    q - p >= PASSAGE for p, q in zip(close, close[1:])):
                for p in close:
                    for k in range(p, p + PASSAGE):
                        marked[k] = max(marked[k], len(at))
    out, i = [], 0
    while i < len(tokens):
        if marked[i]:
            j = i
            while j < len(tokens) and (marked[j] or any(marked[j:j + PASSAGE])):
                j += 1
            if out and when[i] - when[out[-1][1] - 1] <= LOOP_JOIN:
                out[-1] = (out[-1][0], j, PASSAGE, max(out[-1][3], max(marked[i:j])))
            else:
                out.append((i, j, PASSAGE, max(marked[i:j])))
            i = j
        else:
            i += 1
    return out


def repeats_in(tokens: list[str], phrase: list[str]) -> int:
    """The most times phrase comes in a row anywhere in tokens."""
    best, n = 0, len(phrase)
    for i in range(len(tokens) - n + 1):
        if tokens[i:i + n] == phrase:
            best = max(best, repeats_at(tokens, i, n))
    return best


def tokenised(raw) -> tuple[list[str], list[int], list[float]]:
    """An engine's raw words as scoring tokens, with each token's word and time."""
    norm = normalize_tokens([w[2] for w in raw], "standard", harmonise=True)
    return norm.tokens, norm.source_index, [raw[s][0] for s in norm.source_index]


def most_repeats(tokens: list[str]) -> int:
    """The most times any phrase of 1-6 tokens comes in a row in tokens."""
    best = 1
    for i in range(len(tokens)):
        for n in range(1, LOOP_LONGEST + 1):
            if i + 2 * n <= len(tokens) and tokens[i:i + n] == tokens[i + n:i + 2 * n]:
                best = max(best, repeats_at(tokens, i, n))
    return best


def words_only(tokens: list[str]) -> str:
    """The tokens without numbers, as one string with a space either side: engines and
    the reference write figures differently ("$758.8 million", "758 point 8 million"),
    which would hide that a passage of figures really was read out more than once."""
    return " " + " ".join(x for x in tokens if x.isalpha()) + " "


def copies_in(tokens: list[str], phrase: list[str]) -> int:
    """How many times phrase comes in tokens, numbers left out of both."""
    return words_only(tokens).count(words_only(phrase)) if words_only(phrase).strip() else 0


def best_copies(tokens: list[str], pieces: list[list[str]]) -> int:
    """The most copies of any of these pieces in tokens."""
    return max((copies_in(tokens, piece) for piece in pieces), default=0)


def others_repeat(others: dict, phrase, form: str, start: float, end: float) -> int:
    """How often the other engines repeat themselves at the same moment: for a short
    loop, the most times any 1-6 token phrase comes in a row there (a real stutter may
    be heard as other words); for a passage, the copies of it within RAW_REACH."""
    best = 0
    for tokens, _, when in others.values():
        if form == "phrase":
            lo, hi = bisect.bisect_left(when, start - OTHERS_REACH), bisect.bisect_right(when, end + OTHERS_REACH)
            best = max(best, most_repeats(tokens[lo:hi]))
        else:
            lo, hi = bisect.bisect_left(when, start - RAW_REACH), bisect.bisect_right(when, end + RAW_REACH)
            best = max(best, best_copies(tokens[lo:hi], phrase))
    return best


def passage_spans(tokenised_one) -> list[tuple[float, float]]:
    """(start, end) of each passage loop in one engine's words."""
    tokens, _, when = tokenised_one
    return [(when[a], when[b - 1]) for a, b, _, _ in passage_loops(tokens, when) if b - a >= PASSAGE_SHORT]


def loops(job, name, lined, times, placed, raw, seams, tokenised_all, spans_all) -> list[dict]:
    transcript, reference_words, alignment, _ = lined[name]
    ref = alignment.reference
    tokens, source, when = tokenised_all[name]
    others = {o: v for o, v in tokenised_all.items() if o != name}
    rows = []
    found = [(a, b, n, c, "phrase") for a, b, n, c in short_loops(tokens)]
    taken = [(a, b) for a, b, *_ in found]
    for a, b, n, c in passage_loops(tokens, when):
        if not any(a < tb and ta < b for ta, tb in taken) and b - a >= PASSAGE_SHORT:
            found.append((a, b, n, c, "passage"))
    for a, b, n, copies, form in found:
        i0, i1 = source[a], source[b - 1] + 1
        start, end = raw[i0][0], raw[i1 - 1][1]
        phrase = tokens[a:a + n]
        # A passage is compared piece by piece (every 8 tokens in its first 60),
        # since where its copies start is arbitrary.
        pieces = [tokens[k:k + PASSAGE] for k in range(a, min(b, a + PASSAGE_SHORT) - PASSAGE + 1)]
        span = tokens_between(placed, start - LOOP_WINDOW, end + LOOP_WINDOW)
        nearby = ref.tokens[span[0]:span[1]] if span else ref.tokens
        if form == "phrase":
            # The phrase itself nearby, or any stammer right at that moment: the
            # engine may have misheard a real repeat ("where -- where -- where"
            # written "we're we're we're").
            close = tokens_between(placed, start - OTHERS_REACH, end + OTHERS_REACH)
            in_ref = max(repeats_in(nearby, phrase),
                         most_repeats(ref.tokens[close[0]:close[1]]) if close else 0)
            what = f'"{" ".join(phrase)}" x{copies}'
        else:
            in_ref = best_copies(ref.tokens, pieces)
            what = f'a passage of {b - a} words, "{" ".join(phrase)} ..." x{copies}'
        row = {"corpus": job["corpus"], "part": job["term"], "recording": job["docket"],
               "engine": name, "kind": "breakdown", "subkind": "loop", "what": what,
               "start": round(start, 2), "end": round(end, 2), "seconds": round(end - start, 1),
               "engine_words": i1 - i0, "ref_words": in_ref, "reason": ""}
        r0, r1 = span if span else (None, None)
        row["ref_start_token"] = r0
        row["others_right"] = others_right(lined, name, times, r0, r1)
        contexts(row, reference_words, ref, r0, r1, raw, i0, i1)
        row["others_repeat"] = others_repeat(others, phrase if form == "phrase" else pieces, form, start, end)
        if in_ref * 2 >= copies:
            row["reason"] = "the reference repeats it too"
        elif row["others_repeat"] * 2 >= copies or (form == "passage" and any(
                s < end and start < e for o, spans in spans_all.items() if o != name for s, e in spans)):
            # For a passage, another engine with its own passage loop over the same
            # stretch means the speaker said it again (its numbers may be worded
            # differently, "RMB" heard as "9 B", so the copies need not match).
            row["reason"] = "another engine repeats too"
        zones = [z for z in seams if z[0] < end and start < z[1]]
        row["at_seam"], row["seam"] = bool(zones), (f"{zones[0][0] + skips.SEAM_SLACK:.0f}s" if zones else "")
        rows.append(row)
    return rows


# --- artifacts ------------------------------------------------------------------------

def scripts_of(text: str) -> set[str]:
    """The alphabets of the letters in text, other than Latin ("HANGUL", "CYRILLIC")."""
    out = set()
    for ch in text:
        if ch.isalpha() and ord(ch) > 0x24F:
            script = unicodedata.name(ch, "UNKNOWN").split()[0]
            if script != "LATIN":
                out.add(script)
    return out


# A tag in square or angle brackets, or a sound in round ones: "(laughs)", "(Laughter)".
# Not "(eVTOL)" or "(CAGR)": an acronym in brackets is speech.
TAG = re.compile(r"^(\[[^\]]*\]|<\|[^>]*\|>|\([a-z][a-z ]*\)|\([A-Z][a-z]+(?: [a-z]+)*\))[.,!?]?$")
EMPHASIS = re.compile(r"^\*[A-Za-z]|[A-Za-z]\*[.,!?;:]*$")


def artifact_of(word: str, allowed: set[str]) -> str | None:
    """What kind of artifact a raw word is, or None."""
    foreign = scripts_of(word) - allowed
    if foreign:
        return sorted(foreign)[0].title()
    if "�" in word:
        return "broken character"
    if TAG.match(word) or "<|" in word:
        return "tag"
    if MUSIC & set(word):
        return "music symbol"
    if "\\" in word:
        return "backslash"
    if "__" in word:
        return "blank"
    if EMPHASIS.search(word):
        return "markdown"
    letters = sum(ch.isalpha() for ch in word)
    if letters >= LONG_WORD and not re.search(r"[-/.—–_]", word):
        return "long word"
    return None


def artifacts(job, name, lined, times, placed, raw) -> list[dict]:
    transcript, reference_words, alignment, _ = lined[name]
    ref = alignment.reference
    reference_text = " ".join(reference_words)
    allowed = scripts_of(reference_text)
    flagged = [(i, kind) for i, w in enumerate(raw) if (kind := artifact_of(w[2], allowed))]
    # Stock subtitle lines, over runs of words, when the reference has no such line.
    plain = [re.sub(r"[^\w]", "", w[2].lower()) for w in raw]
    ref_plain = " ".join(re.sub(r"[^\w ]", " ", reference_text.lower()).split())
    for phrase in STOCK:
        n = len(phrase.split())
        if phrase in ref_plain:
            continue
        for i in range(len(plain) - n + 1):
            if " ".join(plain[i:i + n]) == phrase:
                flagged += [(k, "stock phrase") for k in range(i, i + n)]
    flagged.sort()
    groups: list[list[tuple[int, str]]] = []
    for i, kind in flagged:
        if groups and (i == groups[-1][-1][0] or raw[i][0] - raw[groups[-1][-1][0]][1] <= ARTIFACT_JOIN):
            if i != groups[-1][-1][0]:
                groups[-1].append((i, kind))
        else:
            groups.append([(i, kind)])
    rows = []
    for group in groups:
        i0, i1 = group[0][0], group[-1][0] + 1
        start, end = raw[i0][0], raw[i1 - 1][1]
        kinds: dict[str, int] = {}
        for _, kind in group:
            kinds[kind] = kinds.get(kind, 0) + 1
        span = tokens_between(placed, start, end)
        r0, r1 = span if span else (None, None)
        row = {"corpus": job["corpus"], "part": job["term"], "recording": job["docket"],
               "engine": name, "kind": "breakdown", "subkind": "artifact",
               "what": ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])),
               "start": round(start, 2), "end": round(end, 2), "seconds": round(end - start, 1),
               "engine_words": len(group), "ref_words": (r1 - r0) if span else 0,
               "ref_start_token": r0, "reason": ""}
        row["others_right"] = others_right(lined, name, times, r0, r1)
        contexts(row, reference_words, ref, r0, r1, raw, i0, i1)
        rows.append(row)
    return rows


# --- one recording ----------------------------------------------------------------------

def measure(job: dict, rows: list[dict], cache: dict) -> bool:
    """Speech share of each blackout still standing. True if anything was new."""
    todo = [r for r in rows if r["subkind"] == "blackout" and not r["reason"]
            and skips.span_key(r) not in cache["speech"]]
    if not todo:
        return False
    audio = load_audio(job["audio"])
    for row in todo:
        lo = max(0.0, row["start"] - VAD_PAD)
        piece = audio[int(lo * SAMPLE_RATE):int((row["end"] + VAD_PAD) * SAMPLE_RATE)]
        regions = [(a + lo, b + lo) for a, b in speech_regions(piece)]
        speech = sum(max(0.0, min(b, row["end"]) - max(a, row["start"])) for a, b in regions)
        cache["speech"][skips.span_key(row)] = round(speech / max(row["end"] - row["start"], 0.01), 3)
    return True


def cache_file(job: dict) -> Path:
    return OUT / "cache" / job["corpus"] / job["term"] / f"{job['docket']}.json.gz"


def check(job: dict) -> tuple[list[dict], float, list[str]]:
    """Every breakdown in one recording, every engine."""
    lined = skips.load(job)
    path = cache_file(job)
    cache = _read(path)
    seconds = skips.recording_seconds(job, cache)
    times = {name: skips.matched_times(one[2], one[3]) for name, one in lined.items()}
    raws = {name: raw_words(next(m for m in job["models"] if m.name == name), job["docket"])
            for name in lined}
    tokenised_all = {name: tokenised(raw) for name, raw in raws.items()}
    spans_all = {name: passage_spans(one) for name, one in tokenised_all.items()}
    rows = []
    for name in lined:
        run = next(m for m in job["models"] if m.name == name)
        raw = raws[name]
        placed = reference_placing(lined, name, times)
        seam_zones = skips.seams(run, job["docket"], seconds)
        found = blackouts(job, name, lined, times, placed, raw, seconds)
        for row in found:
            zones = [z for z in seam_zones if z[0] < row["end"] and row["start"] < z[1]]
            row["at_seam"], row["seam"] = bool(zones), (
                " ".join(f"{z[0] + skips.SEAM_SLACK:.0f}s" for z in zones) if zones else "")
        rows += found
        rows += loops(job, name, lined, times, placed, raw, seam_zones, tokenised_all, spans_all)
        rows += artifacts(job, name, lined, times, placed, raw)
    changed = measure(job, rows, cache)
    for row in rows:
        if row["subkind"] == "blackout" and not row["reason"]:
            row["speech_share"] = cache["speech"][skips.span_key(row)]
            if row["speech_share"] < MIN_SPEECH:
                row["reason"] = "no speech"
    if changed or not path.exists():
        _write(path, cache)
    for row in rows:
        row["start_clock"] = _clock(row["start"])
    return rows, seconds, list(lined)


def _read(path: Path) -> dict:
    import gzip
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return {"seconds": None, "speech": {}}


def _write(path: Path, cache: dict) -> None:
    import gzip
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(cache, stream)


def evidence(row: pd.Series) -> str:
    if row["subkind"] == "blackout":
        return (f"{row['seconds']:.0f}s with {row['what']}; the reference has {row['ref_words']} words "
                f"there; {row['speech_share']:.0%} speech; {row['others_right']} wrote them"
                + (f"; chunk cut at {row['seam']}" if row["at_seam"] else ""))
    if row["subkind"] == "loop":
        return (f"{row['what']} over {row['seconds']:.0f}s; the reference has it {row['ref_words']} "
                f"time(s) there" + (f"; at a chunk cut ({row['seam']})" if row["at_seam"] else ""))
    return f"{row['what']} over {row['seconds']:.0f}s"


# --- tables -----------------------------------------------------------------------------

def per_recording(table: pd.DataFrame, hours: pd.DataFrame) -> pd.DataFrame:
    keys = ["corpus", "part", "recording", "engine"]
    out = hours.rename(columns={"hours": "seconds"}).assign(seconds=lambda d: d.seconds * 3600)
    out = out.set_index(keys)
    found = table[table["reason"] == ""]
    for subkind in ["blackout", "loop", "artifact"]:
        mine = found[found["subkind"] == subkind].groupby(keys)
        out[f"{subkind}s"] = mine.size()
        out[f"{subkind}_seconds"] = mine["seconds"].sum()
    out = out.fillna(0)
    broken = out[["blackout_seconds", "loop_seconds", "artifact_seconds"]].sum(axis=1)
    out["broken_share"] = (broken / out["seconds"]).clip(upper=1).round(4)
    for c in ["blackouts", "loops", "artifacts"]:
        out[c] = out[c].astype(int)
    for c in ["seconds", "blackout_seconds", "loop_seconds", "artifact_seconds"]:
        out[c] = out[c].round(1)
    return out.reset_index()


def counts_table(table: pd.DataFrame, hours: pd.DataFrame) -> pd.DataFrame:
    keys = ["corpus", "part", "engine"]
    counts = hours.groupby(keys).agg(recordings=("recording", "nunique"), hours=("hours", "sum"))
    found = table[table["reason"] == ""]
    counts["candidates"] = found.groupby(keys).size()
    for subkind in ["blackout", "loop", "artifact"]:
        mine = found[found["subkind"] == subkind].groupby(keys)
        counts[f"{subkind}s"] = mine.size()
        counts[f"{subkind}_minutes"] = mine["seconds"].sum() / 60
    for reason in ["few reference words", "no other engine wrote it", "words there, timed elsewhere",
                   "in raw output", "no speech", "the reference repeats it too",
                   "another engine repeats too"]:
        counts[f"not_{reason.replace(' ', '_').replace(',', '')}"] = (
            table[table["reason"] == reason].groupby(keys).size())
    counts = counts.fillna(0)
    for c in counts.columns:
        if c.endswith("_minutes"):
            counts[c] = counts[c].round(1)
        elif c != "hours":
            counts[c] = counts[c].astype(int)
    counts["candidates_per_hour"] = (counts["candidates"] / counts["hours"]).round(2)
    counts["hours"] = counts["hours"].round(1)
    first = ["hours", "candidates", "candidates_per_hour"]
    return counts[first + [c for c in counts.columns if c not in first]].reset_index()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", nargs="+", choices=list(lineup.PARTS), default=list(lineup.PARTS))
    parser.add_argument("--recording", nargs="+", help="only these recordings (a trial, saves nothing)")
    args = parser.parse_args()

    jobs = [job for corpus in args.corpus for job in lineup.recordings(corpus)
            if not args.recording or job["docket"] in args.recording]
    print(f"{len(jobs)} recording(s)")
    started = time.monotonic()
    rows, hours = [], []
    for number, job in enumerate(jobs, 1):
        found, seconds, engines = check(job)
        rows += found
        hours += [{"corpus": job["corpus"], "part": job["term"], "engine": e,
                   "recording": job["docket"], "hours": seconds / 3600} for e in engines]
        kept = [r for r in found if not r["reason"]]
        print(f"[{number}/{len(jobs)}] {job['corpus']} {job['term']} {job['docket']}: "
              f"{len(kept)} kept of {len(found)} "
              f"{(time.monotonic() - started) / 60:.1f} min", flush=True)

    table = pd.DataFrame(rows)
    for column in SHARED + EXTRA + ["reason"]:
        if column not in table:
            table[column] = None
    table["reason"] = table["reason"].fillna("")
    table["at_seam"] = table["at_seam"].fillna(False).astype(bool)
    found = table[table["reason"] == ""].copy()
    found["evidence"] = found.apply(evidence, axis=1) if len(found) else []
    found = found.sort_values(["corpus", "part", "recording", "start", "engine"])
    hours = pd.DataFrame(hours)
    counts = counts_table(table, hours)
    each = per_recording(table, hours)

    if args.recording:
        pd.set_option("display.width", 250, "display.max_colwidth", 120)
        print(table[["recording", "engine", "subkind", "start", "end", "what", "ref_words",
                     "others_right", "speech_share", "reason"]].to_string(index=False))
        print("(a trial with --recording: nothing saved)")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    # Only the data sets run this time are replaced; the others are kept.
    for name, new in [("candidates.csv", found[SHARED + EXTRA].astype(str)),
                      ("counts.csv", counts), ("per-recording.csv", each)]:
        saved = OUT / name
        if saved.exists():
            old = pd.read_csv(saved, dtype=str if name == "candidates.csv" else None,
                              keep_default_na=name != "candidates.csv")
            new = pd.concat([old[~old["corpus"].isin(args.corpus)], new], ignore_index=True)
        new.to_csv(saved, index=False)
    print(counts[["corpus", "part", "engine", "hours", "blackouts", "loops", "artifacts",
                  "candidates_per_hour"]].to_string(index=False))
    print(f"\nin {(time.monotonic() - started) / 60:.1f} min -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

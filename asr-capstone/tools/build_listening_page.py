"""Build the listening page: random flagged spots to label by ear.

Step 5 of the plan in `flagged-spots-review.md`. A random sample of spots from
both of `crowd.py`'s lists, each with:

  - one audio clip covering the sentence before, the sentence with the spot and
    the sentence after; the page plays a 10-second bite, the one sentence or all
    three as slices of it
  - the official words and every model's own words over those three sentences,
    the spot highlighted; each model word carries its time within the clip, so
    the page can highlight the word being spoken as the clip plays

The listener labels each spot (what kind of difference, and who is right) on
the page, which saves the labels in the browser and in the page's own database,
and has a button to copy them all out as JSON for `compare_labels.py`. The sorter's and
the judge's labels are NOT on the page, so the labels made by ear are blind to
them; they go to `answers.json` beside the page, for comparing afterwards.

No GPU. Loads each argument once (about 20 seconds each).

Usage:
    python tools/build_listening_page.py --out <folder> [--n 200]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "tools"))
sys.path.insert(0, str(CAPSTONE / "pipeline"))

import clips  # noqa: E402
import crowd  # noqa: E402
from clips import cases_dir, runs_dir  # noqa: E402,F401  (kept importable from here)
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.pairs import _clock  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402


TEMPLATE = CAPSTONE / "tools" / "listening_page" / "template.html"
#: The shared widgets every page uses (app-roadmap.md, "One set of widgets on every page").
WIDGETS = CAPSTONE / "web" / "widget"
SEED = 2026

#: Words ending in a full stop that don't end a sentence.
ABBREVIATIONS = {"mr.", "ms.", "mrs.", "dr.", "v.", "vs.", "no.", "nos.", "inc.", "co.", "corp.",
                 "st.", "jr.", "sr.", "e.g.", "i.e.", "u.s.", "u.s.c.", "stat.", "cir.", "f.",
                 "ct.", "s.", "art.", "sec.", "id.", "cf.", "al.", "etc.", "p.", "pp.", "l.", "mt."}
SENTENCE_END = re.compile(r"[.?!][\"')\]]*$")
#: Longest a clip may be before it is trimmed around the spot, and shortest
#: worth listening to (overlapping speech can squeeze a sentence to a blip).
CAP = {"sentence": 40.0, "three": 75.0}
MIN_LEN = {"sentence": 3.0, "three": 6.0}


# ---------------------------------------------------------------------------
# Picking the spots
# ---------------------------------------------------------------------------

def sample(n: int) -> pd.DataFrame:
    """A plain random sample from both lists together, so the mix is the real one."""
    against = pd.read_csv(CAPSTONE / "findings/crowd/against-the-record.csv", keep_default_na=False)
    hard = pd.read_csv(CAPSTONE / "findings/crowd/hard-passages.csv", keep_default_na=False)
    against["list"] = ["added" if d.startswith("machines") else "against" for d in against["direction"]]
    hard["list"] = "hard"
    hard["record_normalised"] = ""
    hard["machines_wrote"] = ""
    keep = ["list", "docket", "clock", "words", "record", "record_normalised", "machines_wrote",
            "what_happened", "tags", "machines", "models_right"]
    both = pd.concat([against[keep], hard[keep]], ignore_index=True)
    # Sample first, then add the judge's labels, so the sample doesn't depend on
    # the judge's file (which can be mid-rewrite).
    picked = both.sample(n, random_state=SEED).reset_index(drop=True)
    judge_file = CAPSTONE / "findings/crowd/judge.csv"
    if judge_file.exists():
        judge = pd.read_csv(judge_file, keep_default_na=False)
        key = ["docket", "clock", "record", "machines_wrote"]
        judge = judge.drop_duplicates(key)[key + ["judge_primary", "judge_secondary", "judge_reason"]]
        picked = picked.merge(judge, on=key, how="left")
    return picked


def find_start(case: dict, row) -> int | None:
    """Where a listed spot starts in the official tokens."""
    ref, n = case["reference"], int(row.words)
    for i in range(len(ref)):
        if _clock(case["times"][i]) != row.clock:
            continue
        if row.list == "against" and " ".join(ref[i:i + n]) == row.record_normalised:
            # Several identical words can share one second; take the flagged one.
            if all(sum(case["wrote"][m][j] != ref[j] for m in crowd.MODELS) >= 6
                   for j in range(i, i + n)):
                return i
        if row.list == "hard":
            first, last = case["ref_source"][i], case["ref_source"][i + n - 1]
            if " ".join(case["reference_words"][first:last + 1]) == row.record:
                return i
        if row.list == "added":
            if sum(case["added"][m].get(i) == row.machines_wrote for m in crowd.MODELS) >= 6:
                return i
    return None


# ---------------------------------------------------------------------------
# Sentences, and every model's words over them
# ---------------------------------------------------------------------------

def ends_sentence(word: str) -> bool:
    w = word.lower().strip("\"')]")
    if w in ABBREVIATIONS or re.fullmatch(r"(?:[a-z]\.){2,}", w):
        return False
    return bool(SENTENCE_END.search(word))


def sentence_bounds(words: list[str], turn_starts: set[int]) -> list[tuple[int, int]]:
    """(first, end) word index of each sentence. A change of speaker also ends one."""
    bounds, first = [], 0
    for i, w in enumerate(words):
        if ends_sentence(w) or (i + 1) in turn_starts:
            bounds.append((first, i + 1))
            first = i + 1
    if first < len(words):
        bounds.append((first, len(words)))
    return bounds


def merge(parts: list[tuple]) -> list[dict]:
    """Join neighbouring words of the same part into one segment.

    A part may carry a third item, (start, end) in seconds from the start of the
    spot's clip; those words also go in the segment's "w" list as [text, start,
    end], which the page uses to highlight each word as the clip plays.
    """
    out = []
    for part, text, *timed in parts:
        if out and out[-1]["r"] == part and part != "who" and text:
            out[-1]["t"] += " " + text
        else:
            out.append({"r": part, "t": text})
        if timed and text:
            out[-1].setdefault("w", []).append([text, *timed[0]])
    return out


def model_segments(al, words, start: int, end: int,
                   p0: int, s0: int, s1: int, n1: int, clip_from: float = 0.0) -> list[dict]:
    """One model's own words over the three sentences, each tagged with its part.

    Words are placed by which official word they line up against, not by time,
    because the models' timings disagree by seconds where people talk over each
    other. Parts: "pre"/"post" (the sentences either side), "sent" (the one with
    the spot), "spot" (the words against the flagged official words, plus any
    extra words written inside or right next to them).
    """
    # `al` is this model lined up against the whole argument, done once per
    # argument by the caller rather than once per spot.
    hyp_idx, last_before = [], -1
    for chunk in al.chunks:
        if chunk.kind in ("equal", "substitute"):
            for k, i in enumerate(range(chunk.ref_start, chunk.ref_end)):
                if start <= i < end:
                    hyp_idx.append(chunk.hyp_start + k)
                elif i < start:
                    last_before = max(last_before, chunk.hyp_start + k)
        elif chunk.kind == "insert" and start <= chunk.ref_start <= end:
            hyp_idx.extend(range(chunk.hyp_start, chunk.hyp_end))
    hs = al.hypothesis.source_index
    if hyp_idx:
        a, b = hs[min(hyp_idx)], hs[max(hyp_idx)] + 1
    else:
        a = b = hs[last_before] + 1 if last_before >= 0 else 0

    src = al.reference.source_index
    n_words = (src[-1] + 1) if src else 0
    at = lambda ref_token: src[ref_token] if ref_token < len(src) else n_words
    token_pos = [None] * len(al.hypothesis.tokens)
    for chunk in al.chunks:
        if chunk.kind in ("equal", "substitute"):
            for k in range(chunk.hyp_end - chunk.hyp_start):
                token_pos[chunk.hyp_start + k] = at(chunk.ref_start + k)
        elif chunk.kind == "insert":
            for h in range(chunk.hyp_start, chunk.hyp_end):
                token_pos[h] = at(chunk.ref_start)
    word_pos = {}
    for h, w in enumerate(hs):
        if token_pos[h] is not None:
            word_pos.setdefault(w, token_pos[h])

    keep = [i for i in range(len(words)) if (a <= i < b) or p0 <= word_pos.get(i, -1) < n1]
    parts = []
    for i in keep:
        if i == a and a == b:
            parts.append(("spot", ""))
        pos = word_pos.get(i, s0)
        part = "spot" if a <= i < b else "pre" if pos < s0 else "post" if pos >= s1 else "sent"
        text = words[i].text.strip()
        if text and words[i].start is not None and words[i].end is not None:
            parts.append((part, text, (round(words[i].start - clip_from, 2), round(words[i].end - clip_from, 2))))
        elif text:
            parts.append((part, text))
    if a == b and (not keep or keep[-1] < a):
        parts.append(("spot", ""))
    return merge(parts)


# ---------------------------------------------------------------------------
# One spot
# ---------------------------------------------------------------------------

def build_spot(case: dict, loaded: dict, row, start: int, spot_id: str, out: Path) -> dict:
    end = start if row.list == "added" else start + int(row.words)
    rw, src, times = case["reference_words"], case["ref_source"], case["times"]
    if end > start:
        first, last = src[start], src[end - 1] + 1
    else:
        first = last = src[min(start, len(src) - 1)]

    token_of = {}
    for t, w in enumerate(src):
        token_of.setdefault(w, t)

    def time_of(w: int) -> float:
        for k in range(w, len(rw)):
            if k in token_of and times[token_of[k]] is not None:
                return times[token_of[k]]
        return times[-1] + 2.0

    turn_starts = {s for s, *_ in case["turns"] if s > 0}
    bounds = sentence_bounds(rw, turn_starts)
    hit = [n for n, (f, e) in enumerate(bounds) if f < max(last, first + 1) and e > first]
    s0, s1 = bounds[hit[0]][0], bounds[hit[-1]][1]
    p0 = bounds[hit[0] - 1][0] if hit[0] > 0 else s0
    n1 = bounds[hit[-1] + 1][1] if hit[-1] + 1 < len(bounds) else s1

    t_spot = times[start] or 0.0
    span = {"sentence": [time_of(s0) - 0.35, time_of(s1) + 0.15],
            "three": [time_of(p0) - 0.35, time_of(n1) + 0.15]}
    trimmed = {}
    for key in ("sentence", "three"):
        a, b = span[key]
        if b - a < MIN_LEN[key]:
            extra = (MIN_LEN[key] - (b - a)) / 2
            a, b = a - extra, b + extra
        trimmed[key] = b - a > CAP[key]
        if trimmed[key]:
            a = max(a, t_spot - CAP[key] / 2)
            b = a + CAP[key]
        span[key] = [max(0.0, a), b]
    t1 = times[end] if end < len(times) and times[end] else t_spot
    bite_start = max(0.0, t_spot - 3.0)
    span["bite"] = [bite_start, min(max(t1 + 3.0, bite_start + 10.0), bite_start + 16.0)]

    # One clip covering all three views; the page plays slices of it.
    clip_from = min(v[0] for v in span.values())
    clip_to = max(v[1] for v in span.values())
    docket = row.docket.split("_")[0]
    clip = f"clips/{spot_id}.mp3"
    clips.cut_clip(clips.audio_for(docket, "OT2017"), clip_from, clip_to, out / clip)

    starts = {s: spk for s, spk, *_ in case["turns"]}
    parts = []
    for w in range(p0, n1):
        if w in starts and w > p0:
            parts.append(("who", starts[w] + ":"))
        part = "spot" if first <= w < last else "pre" if w < s0 else "post" if w >= s1 else "sent"
        if w == first and first == last:
            parts.append(("spot", ""))
        parts.append((part, rw[w]))

    lines = {m: model_segments(loaded[m][0], loaded[m][1], start, end, p0, s0, s1, n1, clip_from)
             for m in crowd.MODELS}
    speaker, page, line = crowd._turn_at(case["turns"], src[min(start, len(src) - 1)])
    return {
        "id": spot_id,
        "docket": docket,
        "case": clips.case_name(docket, "OT2017"),
        "clock": row.clock, "speaker": speaker, "page": page, "line": line,
        "sentence_words": s1 - s0,
        "official": merge(parts),
        "qwen": lines["Qwen3"],
        "others": {m: l for m, l in lines.items() if m != "Qwen3"},
        "clip": clip,
        "views": {k: [round(v[0] - clip_from, 2), round(v[1] - clip_from, 2)] for k, v in span.items()},
        "trimmed": trimmed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=200)
    args = parser.parse_args()
    (args.out / "clips").mkdir(parents=True, exist_ok=True)

    rows = sample(args.n)
    by_docket = defaultdict(list)
    for k, row in enumerate(rows.itertuples()):
        by_docket[row.docket].append((f"s{k + 1:03d}", row))

    # The seven runs, as crowd.py reads them: each knows its own file names.
    seven = crowd.seven(runs_dir())
    spots, answers, missing = {}, {}, []
    for n, (docket, items) in enumerate(sorted(by_docket.items()), 1):
        print(f"[{n}/{len(by_docket)}] {docket}: {len(items)} spots", flush=True)
        case = crowd.load_case(runs_dir(), docket)
        # Each model lined up against the whole argument once, kept as
        # (alignment, words) for every spot in it.
        loaded = {}
        for m in crowd.MODELS:
            run = seven.by_name(m)
            transcript = Transcript.from_dict(json.loads(run.reference_file(docket).read_text(encoding="utf-8")))
            words = _load_asr_result(run.asr_file(docket)).words
            al = align_words(transcript.full_text(include_speakers=False).split(),
                             [w.text for w in words], "standard",
                             harmonise=True, vocabulary=case["vocabulary"])
            loaded[m] = (al, words)
        for spot_id, row in items:
            start = find_start(case, row)
            if start is None:
                missing.append(f"{spot_id} {docket} {row.clock}")
                continue
            spots[spot_id] = build_spot(case, loaded, row, start, spot_id, args.out)
            answers[spot_id] = {
                "list": row.list, "docket": docket, "clock": row.clock, "record": row.record,
                "what_happened": row.what_happened, "tags": row.tags, "machines": row.machines,
                "models_right": int(row.models_right),
                **{field: value if isinstance(value := getattr(row, field, None), str) else None
                   for field in ("judge_primary", "judge_secondary", "judge_reason")},
            }

    ordered = [spots[k] for k in sorted(spots)]
    (args.out / "answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False), encoding="utf-8")
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("/*TOKENS*/", (WIDGETS / "tokens.css").read_text(encoding="utf-8"))
            .replace("/*LISTEN*/", (WIDGETS / "listen.js").read_text(encoding="utf-8"))
            .replace("/*SPOTS*/[]", json.dumps(ordered, ensure_ascii=False)))
    (args.out / "listening.html").write_text(page, encoding="utf-8")
    print(f"\n{len(ordered)} spots built, {len(missing)} could not be re-found")
    for m in missing:
        print("  missing:", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

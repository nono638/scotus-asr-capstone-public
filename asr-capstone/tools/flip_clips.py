"""A short clip for every dot in Figure 1: where Qwen3 and Whisper disagree most.

Figure 1 on the website has one dot per argument. Clicking a dot plays 12 seconds
of that argument with both engines' words highlighted as they are spoken. The 12
seconds are where they disagree most on the verbatim rule, read in the direction of
that argument's result: the stretch where the engine that lost the argument on the
verbatim rule made the most errors the winner did not (record words one got right
and the other did not). Added words are left out of the choice: Qwen3's added words
pile up where two of its 280-second pieces join, and a clip chosen by them plays a
join, not the flip. For most arguments that is
Qwen3's lower-case "court", missing dashes and punctuation; where Qwen3 won, it is
usually a Whisper blow-up (a stretch in capitals, speaker labels written as words).

Plain "most disagreement either way" was tried first and mostly found Whisper's rare
blow-ups, which tells the opposite of what the figure shows.

    python tools/flip_clips.py [--limit N]

Writes:
    findings/flip/listen-windows.csv   which 12 seconds, and how many words each
                                       engine got wrong there (verbatim rule)
    site/clips/flip/<term>-<docket>.mp3
    site/clips/flip/words.json         each clip's words, for the page

The clips are not in git (they can be cut again); the CSV is. No GPU; reads the
runs and never writes to them.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "tools"))
sys.path.insert(0, str(CAPSTONE / "pipeline"))

import clips  # noqa: E402
import crowd  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.normalize import normalize_tokens  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402

WINDOW = 12.0
LEAD = 0.3   # start a little before the first word, so it isn't clipped
OUT = CAPSTONE / "site" / "clips" / "flip"
FINDINGS = CAPSTONE / "findings" / "flip"

def right_and_added(alignment) -> tuple[list[bool], dict[int, int], set[int]]:
    """Which record tokens this engine got right, how many tokens it added at each
    gap, and which of its own words differ from the record."""
    right = [False] * len(alignment.reference.tokens)
    added: dict[int, int] = {}
    wrong_words = set()
    hs = alignment.hypothesis.source_index
    for chunk in alignment.chunks:
        if chunk.kind == "equal":
            for i in range(chunk.ref_start, chunk.ref_end):
                right[i] = True
        else:
            if chunk.kind == "insert":
                added[chunk.ref_start] = added.get(chunk.ref_start, 0) + chunk.hyp_end - chunk.hyp_start
            wrong_words.update(hs[h] for h in range(chunk.hyp_start, chunk.hyp_end))
    return right, added, wrong_words


def one_argument(term: str, docket: str, winner: str) -> tuple[dict, dict] | None:
    loaded = {}
    for engine in ("Qwen3", "Whisper"):
        run = clips.run_for(engine, term)
        name = clips.file_name(run, docket, term)
        transcript = Transcript.from_dict(json.loads(run.reference_file(name).read_text(encoding="utf-8")))
        loaded[engine] = (transcript, _load_asr_result(run.asr_file(name)).words)
    reference = loaded["Qwen3"][0].full_text(include_speakers=False).split()
    # One shared word list, so the record is joined ("e mails" -> "emails") the
    # same way for both engines and their record tokens line up one for one.
    vocabulary = set(normalize_tokens(reference, "verbatim", harmonise=True).tokens)
    for _, words in loaded.values():
        vocabulary |= set(normalize_tokens([w.text for w in words], "verbatim", harmonise=True).tokens)

    found = {}
    for engine, (_, words) in loaded.items():
        al = align_words(reference, [w.text for w in words], "verbatim", harmonise=True, vocabulary=vocabulary)
        found[engine] = (al, words, *right_and_added(al))
    q_al, q_words, q_right, q_added, q_wrong = found["Qwen3"]
    w_al, w_words, w_right, w_added, w_wrong = found["Whisper"]
    if q_al.reference.tokens != w_al.reference.tokens:
        raise ValueError(f"{docket}: the two alignments joined the record differently")

    # A time for every record token: Whisper's timing where it wrote the token,
    # else Qwen3's, else the last time before it.
    times = crowd.token_times(w_al, w_words)
    q_times = crowd.token_times(q_al, q_words)
    times = [t if t is not None else q for t, q in zip(times, q_times)]
    # +1 for each record word the verbatim loser got wrong and the winner right,
    # -1 the other way round.
    sign = 1 if winner == "Whisper" else -1
    events = []   # (time, weight)
    for i, t in enumerate(times):
        if t is None:
            continue
        if q_right[i] != w_right[i]:
            events.append((t, sign if w_right[i] else -sign))
    if not events:
        return None
    events.sort()
    starts = [t for t, _ in events]
    running = [0]
    for _, weight in events:
        running.append(running[-1] + weight)
    # The 12 seconds with the highest total, starting at one of the events.
    best, start = None, starts[0]
    for k, t in enumerate(starts):
        n = running[bisect.bisect_left(starts, t + WINDOW)] - running[k]
        if best is None or n > best:
            best, start = n, t
    a, b = max(0.0, start - LEAD), start - LEAD + WINDOW

    in_window = [i for i, t in enumerate(times) if t is not None and a <= t < b]
    src = q_al.reference.source_index
    record_words = sorted({src[i] for i in in_window})
    clip = f"clips/flip/{term}-{docket}.mp3"
    clips.cut_clip(clips.audio_for(docket, term), a, b, CAPSTONE / "site" / clip)
    data = {
        "clip": clip,
        "case": clips.case_name(docket, term),
        "from": round(a, 2),
        "lines": [
            {"who": "Record", "t": " ".join(reference[w] for w in record_words)},
            {"who": "Qwen3", "w": clips.timed_words(q_words, a, b, q_wrong)},
            {"who": "Whisper", "w": clips.timed_words(w_words, a, b, w_wrong)},
        ],
    }
    row = {
        "term": term, "docket": docket, "clip_start": round(a, 2), "clip_seconds": WINDOW,
        "verbatim_winner": winner,
        "loser_errors_minus_winner": best,
        "qwen3_wrong": sum(not q_right[i] for i in in_window) + sum(q_added.get(i, 0) for i in in_window),
        "whisper_wrong": sum(not w_right[i] for i in in_window) + sum(w_added.get(i, 0) for i in in_window),
        "record_tokens": len(in_window),
    }
    return data, row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="first N arguments only, for trying it")
    args = parser.parse_args()
    arguments = pd.read_csv(FINDINGS / "per-argument.csv")
    # An exact tie (one argument) goes to Whisper, the usual verbatim winner.
    arguments["winner"] = ["Qwen3" if q < w else "Whisper"
                           for q, w in zip(arguments.Qwen3_verbatim, arguments.Whisper_verbatim)]
    arguments = arguments[["term", "docket", "winner"]]
    if args.limit:
        arguments = arguments.head(args.limit)
    OUT.mkdir(parents=True, exist_ok=True)
    words, rows = {}, []
    for n, (term, docket, winner) in enumerate(arguments.itertuples(index=False), 1):
        print(f"[{n}/{len(arguments)}] {term} {docket}", flush=True)
        made = one_argument(term, docket, winner)
        if made:
            words[f"{term}-{docket}"] = made[0]
            rows.append(made[1])
    (OUT / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    table = pd.DataFrame(rows)
    if not args.limit:
        table.to_csv(FINDINGS / "listen-windows.csv", index=False)
    print(table.describe().round(1).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""One row per reference word: did each model get it right, and what was going on around it.

The input for the error model (H2 in heilmeier-notes.md): the conditions reporters
complain about - people talking over each other, fast speech, unclear speech, hard
words - measured for every word, next to whether each model wrote it.

The words are lined up exactly as tools/crowd.py lines them up (its `load_case`), so
a word counted wrong here is a word counted wrong there.

Columns:

    corpus, recording, index    which word: its position among the scored tokens
    time                        seconds into the recording (from the pivot model's
                                timings; empty where it left the word out)
    token, original             the scored token, and the record's word it came from
    word_type                   number, legal, name, filler, function or content
    speaker, role               who said it; role is justice / advocate on the
                                Supreme Court, speaker elsewhere
    words_to_turn               reference words to the nearest change of speaker
                                (capped at 50)
    near_dash                   a reporter's dash within two words (an interruption)
    local_rate                  words per second within 3 s either side
    disfluency_near             a filler or a repeated word within two words
    ok_<model>                  1 if that model wrote this word, 0 if not

Usage (same model choices as crowd.py):

    python tools/word_table.py --corpus scotus --out <scotus_corpus>/word-table.csv.gz
    python tools/word_table.py --corpus edacc --runs-dir <asr_corpora>/edacc/runs \\
        --out <asr_corpora>/edacc/word-table.csv.gz

One term at a time, three engines given by hand (the four-term error model):

    python tools/word_table.py --corpus scotus --term 2021 --pivot Whisper \\
        --model Whisper=<runs>/run-scotus250-whisper --model Qwen3=<runs>/run-scotus250-qwen3 \\
        --model Parakeet=<runs>/run-scotus250-parakeet \\
        --out <scotus_corpus>/word-tables/three-engines-OT2021.csv.gz
"""

from __future__ import annotations

import argparse
import bisect
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowd  # noqa: E402

RATE_WINDOW = 3.0       # seconds either side for the local speaking rate
TURN_CAP = 50           # words_to_turn beyond this is "far from any change"


def word_type(token: str, original: str, lower_words: set[str], names_possible: bool,
              legal_possible: bool = True) -> str:
    """One label per word, most specific first.

    Legal terms are looked for only in court speech: matched one token at a time,
    "stare", "ex" and "en" are just words in a conversation.
    """
    if any(ch.isdigit() for ch in token + original) or token in crowd.NUMBER_WORDS:
        return "number"
    if legal_possible and token in crowd.LEGAL_TERMS:
        return "legal"
    if names_possible and crowd.looks_like_a_name(original, lower_words):
        return "name"
    if token in crowd.FILLERS or token in crowd.BACKCHANNELS:
        return "filler"
    if token in crowd.FUNCTION_WORDS:
        return "function"
    return "content"


def role_of(speaker: str, corpus: str) -> str:
    if corpus != "scotus":
        return "speaker"
    return "justice" if "JUSTICE" in speaker.upper() else "advocate"


def local_rates(times: list[float | None]) -> list[float | None]:
    """Words per second in a window around each word, from the word timings."""
    known = sorted(t for t in times if t is not None)
    rates = []
    for t in times:
        if t is None:
            rates.append(None)
            continue
        lo = bisect.bisect_left(known, t - RATE_WINDOW)
        hi = bisect.bisect_right(known, t + RATE_WINDOW)
        rates.append(round((hi - lo) / (2 * RATE_WINDOW), 3))
    return rates


def rows_for(case: dict, names: list[str], corpus: str) -> list[dict]:
    """The table's rows for one recording, from crowd.load_case's output."""
    reference = case["reference"]
    rw = case["reference_words"]
    lower_words = {w.strip(".,?!;:-'\"") for w in rw if w.islower()}
    names_possible = crowd.can_spot_names(rw)
    turn_starts = sorted({start for start, *_ in case["turns"] if start > 0})
    rates = local_rates(case["times"])

    rows = []
    for i, right in enumerate(reference):
        source = case["ref_source"][i]
        speaker, _, _ = crowd._turn_at(case["turns"], source)
        k = bisect.bisect_left(turn_starts, source)
        gaps = [abs(source - turn_starts[j]) for j in (k - 1, k) if 0 <= j < len(turn_starts)]
        neighbours = reference[max(0, i - 2):i] + reference[i + 1:i + 3]
        row = {
            "corpus": corpus,
            "recording": case["docket"],
            "index": i,
            "time": case["times"][i],
            "token": right,
            "original": rw[source],
            "word_type": word_type(right, rw[source], lower_words, names_possible,
                                   legal_possible=corpus == "scotus"),
            "speaker": speaker,
            "role": role_of(speaker, corpus),
            "words_to_turn": min(gaps + [TURN_CAP]),
            "near_dash": int(crowd.near_interruption(rw, source)),
            "local_rate": rates[i],
            "disfluency_near": int(any(w in crowd.FILLERS for w in neighbours)
                                   or right in neighbours),
        }
        for model in names:
            row[f"ok_{model}"] = int(case["wrote"][model][i] == right)
        rows.append(row)
    return rows


def in_terms(terms: list[str]) -> set[str]:
    """The Supreme Court arguments in these terms, from the listing a run uses."""
    sys.path.insert(0, str(crowd.CAPSTONE / "pipeline"))
    from scotus_asr.config import load_config
    from scotus_asr.corpora.registry import build_corpus
    from scotus_asr.corpus.manifest import select

    config = load_config(crowd.CAPSTONE / "pipeline" / "config" / "corpus.yaml")
    return {case.docket for case in select(build_corpus(config).recordings(), terms=terms)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", required=True, help="the corpus column (scotus, edacc...). Not only a label: 'scotus' "
                             "is what switches on legal terms and justice/advocate roles")
    parser.add_argument("--set", type=Path, help="a model-set file (default: the Supreme Court's seven)")
    parser.add_argument("--runs-dir", type=Path, help="use every engine found in this runs folder")
    parser.add_argument("--models", help="with --runs-dir: only these engines, comma-separated")
    parser.add_argument("--model", action="append", metavar="NAME=RUN", help="a model by hand. Repeat.")
    parser.add_argument("--pivot", help="the model whose timings place the words in time")
    parser.add_argument("--term", action="append", metavar="YEAR",
                        help="only this October Term's arguments, e.g. 2021 (Supreme Court). Repeat for several")
    parser.add_argument("--limit", type=int, help="only the first N recordings, to try it out")
    parser.add_argument("--out", type=Path, required=True, help="the table, .csv or .csv.gz")
    args = parser.parse_args()

    chosen = crowd.choose_models(args)
    recordings, missing = chosen.shared_recordings()
    if missing:
        print(f"  {len(set().union(*missing.values()))} recording(s) left out: not every model has them")
    if args.term:
        # A run can hold several terms (Whisper's September run has 2010 and 2017),
        # so the runs alone cannot say which term a table covers.
        wanted = in_terms(args.term)
        recordings = [r for r in recordings if r in wanted]
    if args.limit:
        recordings = recordings[:args.limit]
    print(f"{args.corpus}: {', '.join(chosen.names)} on {len(recordings)} recordings "
          f"(times from {chosen.pivot})")

    rows = []
    for n, docket in enumerate(recordings, 1):
        rows += rows_for(crowd.load_case(None, docket, chosen), chosen.names, args.corpus)
        print(f"  {n}/{len(recordings)} {docket}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"Wrote {len(rows):,} words to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

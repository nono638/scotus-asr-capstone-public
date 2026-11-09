"""Which cases do the judges need to read again? Those whose prompt has changed, and only those.

prompt_prints() takes a fingerprint of the meaning prompt of every case in full-v1. Taken before
and after a repair, a case whose fingerprint changed was shown to the judges differently, and
its old answer no longer counts. That answer moves to answers-<judge>-full-v1-superseded.csv, kept
for the record, so the next run of tools/judge_failures.py asks it again, as it does any case with no
answer. New cases have no answer anyway. A case now marked "gone" is not asked.

    python tools/reask_changed.py --prints before.csv            # take the fingerprints
    python tools/reask_changed.py --compare before.csv after.csv [--move]
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import multiprocessing as mp
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
JUDGE = CAPSTONE / "findings" / "judge"
ANSWERS = ["answers-claude-sonnet-5-5-full-v1.csv", "answers-qwen3.8-27b-full-v1.csv"]
sys.path.insert(0, str(CAPSTONE / "tools"))


def _setup():
    import judge_failures as J
    J.SAMPLE = J.OUT / "full-v1.csv"
    J.SUFFIX = "-full-v1"
    J.norm = functools.lru_cache(maxsize=200000)(J.norm)
    return J


def _work(rows):
    J = _setup()
    cache, out = {}, []
    for row in rows:
        r = {"case": row["case"]}
        try:
            c = J.Case(row, cache)
            message = J.meaning_message_v4(c, "minute")
            r["print"] = hashlib.sha1(message.encode("utf-8")).hexdigest()[:16]
            r["others"] = J.other_engines(c)
            r["text_print"] = hashlib.sha1(message.replace(r["others"], "").encode("utf-8")).hexdigest()[:16] if r["others"] else r["print"]
        except Exception as e:
            r["err"] = repr(e)[:200]
        out.append(r)
    return out


def prints(path: str) -> int:
    full = pd.read_csv(JUDGE / "full-v1.csv", dtype=str, keep_default_na=False)
    if "not_counted" in full:
        full = full[~full.not_counted.str.startswith("gone")]
    groups = [g.to_dict("records") for _, g in full.groupby(["corpus", "part", "recording"])]
    rows = []
    with mp.Pool(5) as pool:
        for n, got in enumerate(pool.imap_unordered(_work, groups)):
            rows += got
            if n % 200 == 0:
                print(n, "of", len(groups), flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(path, index=False)
    print(f"{len(t):,} fingerprints; errors {t['err'].notna().sum() if 'err' in t else 0}")
    return 0


def compare(before: str, after: str, move: bool) -> int:
    a, b = pd.read_csv(before).set_index("case"), pd.read_csv(after).set_index("case")
    full = pd.read_csv(JUDGE / "full-v1.csv", dtype=str, keep_default_na=False).set_index("case")
    shared = b.index.intersection(a.index)
    changed = shared[a.loc[shared, "print"] != b.loc[shared, "print"]]
    words = shared[a.loc[shared, "text_print"] != b.loc[shared, "text_print"]]
    print(f"{len(b):,} live cases; prompt changed on {len(changed):,}: the text itself on {len(words):,}, "
          f"only the other-engines sentence on {len(changed) - len(words):,}; {len(b.index.difference(a.index)):,} new")
    print(full.loc[changed].groupby(["corpus", "engine"]).size().to_string())
    gone = full.index[full.get("not_counted", pd.Series("", index=full.index)).str.startswith("gone")]
    for name in ANSWERS:
        path = JUDGE / name
        table = pd.read_csv(path, dtype=str, keep_default_na=False)
        meaning = table.ask == "meaning"
        stale = meaning & table.case.isin(changed)
        print(f"{name}: {stale.sum():,} meaning answers superseded; {(meaning & table.case.isin(gone)).sum():,} on cases now gone; "
              f"{meaning.sum() - stale.sum():,} stand")
        if move and stale.any():
            out = JUDGE / name.replace(".csv", "-superseded.csv")
            table[stale].to_csv(out, mode="a", header=not out.exists(), index=False, lineterminator="\n")
            table[~stale].to_csv(path, index=False, lineterminator="\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--prints", metavar="OUT")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--move", action="store_true", help="Move the superseded answers out.")
    args = parser.parse_args()
    raise SystemExit(prints(args.prints) if args.prints else compare(*args.compare, args.move))

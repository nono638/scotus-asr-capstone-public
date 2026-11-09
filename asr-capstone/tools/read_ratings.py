"""Read the ratings CSV that the public site's admin page downloads (admin.html).

    python tools/read_ratings.py ratings-all-2026-11-20.csv            # a short summary
    python tools/read_ratings.py ratings-all-2026-11-20.csv --split    # one file per licence

In Python:

    import read_ratings
    t = read_ratings.load("ratings-all-2026-11-20.csv")

One row per person per case. `features` becomes one True/False column per question
(f_overlap, f_stumble, ... f_cant_tell), `played` a list, and the times real
timestamps. The `uid` is the only thing that links one person's ratings; there are no
emails or names in the file.

--split writes one file per licence beside the input, because CORAAL's corrections
(CC BY-NC-SA 4.0) must not be merged with EdAcc's (CC BY-SA 4.0) in anything
published (going-public.md, section 1).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

FEATURES = ["overlap", "stumble", "name", "number", "written", "soundalike", "small", "oneside", "none", "cant_tell"]
SLUG = {"CC BY 4.0": "scotus", "CC BY-SA 4.0": "edacc", "CC BY-NC-SA 4.0": "coraal"}


def undo_formula_guard(text: str) -> str:
    """The admin page puts a ' before a cell starting with = + - @ (so a spreadsheet
    doesn't run it); take it off again."""
    return text[1:] if len(text) > 1 and text[0] == "'" and text[1] in "=+-@" else text


def load(path: str | Path) -> pd.DataFrame:
    t = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in t.columns:
        t[col] = t[col].map(undo_formula_guard)
    picked = t.features.str.split(";")
    for f in FEATURES:
        t[f"f_{f}"] = picked.map(lambda got, f=f: f in got)
    t["played"] = t.played.map(lambda s: [p for p in s.split(";") if p])
    for col in ("created", "updated"):
        t[col] = pd.to_datetime(t[col], utc=True, errors="coerce")
    return t


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--split", action="store_true", help="write one CSV per licence beside the input")
    args = parser.parse_args()
    t = load(args.csv)
    print(f"{len(t)} ratings of {t.case.nunique()} cases by {t.uid.nunique()} people")
    if len(t):
        print(t.groupby("corpus").size().to_string())
        print("\nWho got it right:\n" + t.who_right.value_counts().to_string())
        print("\nIs the record right:\n" + t.record_right.value_counts().to_string())
    if args.split:
        raw = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
        for licence, part in raw.groupby("licence"):
            out = args.csv.with_name(f"{args.csv.stem}-{SLUG.get(licence, 'other')}.csv")
            part.to_csv(out, index=False)
            print(f"wrote {out.name}: {len(part)} rows, {licence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

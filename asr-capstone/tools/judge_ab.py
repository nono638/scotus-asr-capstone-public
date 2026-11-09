"""Tally the blind A/B review of two judge prompts (findings/judge/ab-review/).

Claude agents saw each case's two answer sets as X and Y, at random, and marked
each part right / partly / wrong and said which set was better. This unblinds
them with the key and counts by prompt version.

    python tools/judge_ab.py [key.json]

The key is kept away from the review folder until the review is done; it is
then saved beside the verdicts as key.json.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_failures as J  # noqa: E402

AB = J.OUT / "ab-review"
SCORE = {"right": 1.0, "partly": 0.5, "wrong": 0.0}


def main() -> int:
    key_path = Path(sys.argv[1]) if len(sys.argv) > 1 else AB / "key.json"
    key = json.loads(key_path.read_text(encoding="utf-8"))
    rows, misses, overall = [], [], Counter()
    for path in sorted((AB / "verdicts").glob("s*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        version = key[d["case"]]
        name = lambda xy: version.get(xy, xy)   # "X" -> "0.2", "tie" -> "tie"
        overall[name(d["overall"]["better"])] += 1
        for part, v in d["parts"].items():
            if part == "misses":
                for xy in ("X", "Y"):
                    misses.append({"case": d["case"], "prompt": version[xy], **v[xy]})
                rows.append({"case": d["case"], "part": part, "better": name(v["better"])})
                continue
            rows.append({"case": d["case"], "part": part, "better": name(v["better"]),
                         **{f"score {version[xy]}": SCORE.get(v[xy], 0.0) for xy in ("X", "Y")}})
    r = pd.DataFrame(rows)
    print(f"Cases: {r.case.nunique()}. Overall better: {dict(overall)}\n")
    print("== Which prompt's answer was better, part by part (cases)")
    print(pd.crosstab(r.part, r.better).to_string(), "\n")
    print("== Share right (right 1, partly 0.5, wrong 0), part by part")
    print(r.groupby("part")[["score 0.2", "score 0.3"]].mean().round(2).dropna().to_string(), "\n")
    m = pd.DataFrame(misses)
    print("== Misses lists, summed over all cases")
    print(m.groupby("prompt")[["real_and_matter", "trivial", "not_real", "important_missed"]].sum().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

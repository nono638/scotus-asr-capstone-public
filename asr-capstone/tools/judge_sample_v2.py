"""Score the judges on sample-v2 (300 rows drawn at random) against Claude's blind answer key.

sample-v2 asks only the meaning question, a minute either side, so it can say which judge
to trust with that question on every row. Each judge's answers are compared with the key
in claude-review-v2/, written by Claude agents that never saw a judge's answer. Claude is
a careful reader, not the truth: nobody has listened to these spots.

Agreement comes with a 95% interval (Wilson), and two judges are compared case by case:
on the cases where exactly one of them agrees with the key, a sign test says how likely a
split that uneven is by chance.

sample-v3 is the same 300 rows plus 50 spots where every engine agrees against the
reference (a001-a050), asked with prompt 0.4, which adds the misspoke question. Those
50 are scored apart: they are not a random draw.

    python tools/judge_sample_v2.py                      # sample-v2, prompt 0.3
    python tools/judge_sample_v2.py --sample sample-v3   # prompt 0.4
"""

from __future__ import annotations

import argparse
import json
import sys
from math import comb, sqrt
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_failures as J  # noqa: E402

KEY = J.OUT / "claude-review-v2"   # r001-r300 and a001-a050
#: "changed", "opposite" and "garbled" all mean the reader is told something else (or
#: nothing); "same" and "reworded" mean they aren't. The split a bulk run would act on.
MATTERS = {"changed", "opposite", "garbled"}


def key() -> pd.DataFrame:
    rows = [{"case": d["case"], **d["own"]} for d in
            (json.loads(p.read_text(encoding="utf-8")) for p in sorted(KEY.glob("[ra]*.json")))]
    return pd.DataFrame(rows).set_index("case")


def answers(model: str, sample: str) -> pd.DataFrame:
    path = J.OUT / f"answers-{J.tag(model)}-{sample}.csv"
    if not path.exists():
        return pd.DataFrame()
    a = pd.read_csv(path, dtype=str, keep_default_na=False)
    a = a[(a.ask == "meaning") & (a.valid == "True")].drop_duplicates("case", keep="last")
    a["answer"] = a.answer.map(json.loads)
    fields = ["meaning", "severity", "follow_up", "reference_doubt", "misspoke"]
    return pd.DataFrame({f: a.answer.map(lambda x: x.get(f, "")).values for f in fields}, index=a.case.values)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (centre - half), 100 * (centre + half)


def sign_test(only_a: int, only_b: int) -> float:
    n = only_a + only_b
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n)


JUDGES = {"claude-haiku-5-5": "Haiku, thinking", "claude-sonnet-5-5": "Sonnet",
          "claude-sonnet-5-5-high": "Sonnet, high effort",
          "qwen3.8:27b": "Qwen 27B, thinking"}


def table(k: pd.DataFrame, judged: dict, cases) -> dict:
    """Agreement with the key on these cases, one row per judge; returns the hits."""
    hits, rows = {}, []
    for name, a in judged.items():
        both = a.index.intersection(k.index).intersection(cases)
        if not len(both):
            continue
        exact = a.loc[both, "meaning"] == k.loc[both, "meaning"]
        matters = a.loc[both, "meaning"].isin(MATTERS) == k.loc[both, "meaning"].isin(MATTERS)
        gap = pd.to_numeric(a.loc[both, "severity"]) - pd.to_numeric(k.loc[both, "severity"])
        hits[name] = {"exact": exact, "matters": matters}
        lo, hi = wilson(int(exact.sum()), len(both))
        lo2, hi2 = wilson(int(matters.sum()), len(both))
        rows.append({"judge": name, "cases": len(both),
                     "same meaning label %": round(100 * exact.mean()), "interval": f"{lo:.0f}-{hi:.0f}",
                     "same matters / doesn't %": round(100 * matters.mean()), "interval ": f"{lo2:.0f}-{hi2:.0f}",
                     "severity above key": round(gap.mean(), 2), "severity 2+ off": int((gap.abs() >= 2).sum())})
    if rows:
        print(pd.DataFrame(rows).set_index("judge").to_string(), "\n")
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="sample-v2")
    args = parser.parse_args()
    k = key()
    sample = pd.read_csv(J.OUT / f"{args.sample}.csv", dtype=str, keep_default_na=False).set_index("case")
    print(f"Answer key: {len(k.index.intersection(sample.index))} of {len(sample)} cases\n")
    judged = {name: a for model, name in JUDGES.items() if len(a := answers(model, args.sample))}

    random_rows = sample.index[sample.source == "random"]
    print("The random rows:")
    hits = table(k, judged, random_rows)

    names = list(hits)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            for measure in ("exact", "matters"):
                both = hits[x][measure].index.intersection(hits[y][measure].index)
                a, b = hits[x][measure][both], hits[y][measure][both]
                only_x, only_y = int((a & ~b).sum()), int((b & ~a).sum())
                print(f"{measure:8} {x} vs {y}: only the first agrees {only_x}, only the second {only_y}, "
                      f"chance {sign_test(only_x, only_y):.2f}")

    print("\nBy kind (same meaning label %):")
    by = []
    for name, h in hits.items():
        s = sample.loc[h["exact"].index]
        for kind in ("meaning", "edits", "invented", "skips"):
            part = h["exact"][s.kind == kind]
            if len(part):
                by.append({"judge": name, "kind": kind, "cases": len(part), "%": round(100 * part.mean())})
    if by:
        print(pd.DataFrame(by).pivot(index="kind", columns="judge", values="%").to_string())
    print("\nThe key's labels:", k.loc[k.index.intersection(random_rows)].meaning.value_counts().to_dict())

    # 0.4's new follow-up answer should go with "reworded".
    for name, a in judged.items():
        new = a[a.follow_up == "same meaning, other words"]
        if len(new):
            print(f"{name}: 'same meaning, other words' {len(new)} times; the key says "
                  f"{k.loc[k.index.intersection(new.index)].meaning.value_counts().to_dict()}")

    agree_rows = sample.index[sample.source == "all-agree"]
    if len(agree_rows):
        print("\nThe spots where every engine agrees against the reference:")
        table(k, judged, agree_rows)
        ka = k.loc[k.index.intersection(agree_rows)]
        for field in ("reference_doubt", "misspoke"):
            print(f"{field}: the key {ka[field].value_counts().to_dict()}")
            for name, a in judged.items():
                both = a.index.intersection(ka.index)
                same = (a.loc[both, field] == ka.loc[both, field]).sum()
                print(f"  {name}: {a.loc[both, field].value_counts().to_dict()}; same as the key {same}/{len(both)}")
        for name, a in judged.items():
            r = a.loc[a.index.intersection(random_rows)]
            print(f"misspoke on the random rows, {name}: {r.misspoke.value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

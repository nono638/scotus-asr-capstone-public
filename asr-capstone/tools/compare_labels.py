"""How well do the rules, the judge and a second person agree with labels made by ear?

Step 5 of `flagged-spots-review.md`, following `labelling-guidelines.md`
(version 0.2). Each spot on the listening bench is labelled once by a person, by
ear, ticking any of eight yes/no questions, or "none" or "can't tell". "Copy all
labels" on the page, or Claude reading its database (collection `labels-v02`),
gives a JSON file of spot id -> {guide, ticks, played, verdict, note}.

Compared, question by question and over the whole set of ticks:
  judge  vs ear   the judge, which only reads the text, against the ear
  rules  vs ear   the first-pass rules, on the six questions they cover
  second vs ear   another person (with --second), the most the judge can be expected to reach

Statistics: per question, raw agreement and Cohen's kappa (agreement beyond what
chance would give; blank when one side never says yes). Over the whole set of
ticks per spot, Krippendorff's alpha with the MASI distance, which gives partial
credit when two sets partly overlap (Passonneau 2006). A spot marked "can't tell"
by either side is left out of that pair.

Writes findings/crowd/label-agreement.csv (one row per spot) and prints tables.

Usage:
    python tools/compare_labels.py --labels ear.json --answers findings/crowd/listening-bench-answers.json
    python tools/compare_labels.py --labels ear.json --answers ... --second friend.json
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

CAPSTONE = Path(__file__).resolve().parent.parent
GUIDE = "0.2"
QUESTIONS = ["overlap", "stumble", "name", "number", "written", "soundalike", "small", "oneside"]
#: The rules' kinds (crowd.py), as questions. The rules have no sound-alike or
#: one-side-only check, so they are compared on the other six only.
RULE_KINDS = {
    "speaker change or overlap": "overlap", "disfluency": "stumble", "name or legal term": "name",
    "number or citation": "number", "not a real difference": "written", "small word or ending": "small",
}


def ticks_of(answer: list[str] | None) -> frozenset[str] | None:
    """Ticks as a set of questions; None when unanswered or "can't tell"."""
    if not answer or "cant" in answer:
        return None
    return frozenset(k for k in answer if k in QUESTIONS)   # "none" -> empty set


def masi(a: frozenset, b: frozenset) -> float:
    """MASI distance between two sets (Passonneau 2006): 0 the same, 1 nothing shared."""
    if a == b:
        return 0.0
    union = a | b
    jaccard = len(a & b) / len(union)
    monotonicity = 2 / 3 if (a <= b or b <= a) else 1 / 3 if a & b else 0.0
    return 1 - jaccard * monotonicity


def alpha_masi(pairs: list[tuple[frozenset, frozenset]]) -> float | None:
    """Krippendorff's alpha for two labellers who both labelled every item, MASI distance."""
    if len(pairs) < 2:
        return None
    observed = sum(masi(a, b) for a, b in pairs) / len(pairs)
    values = [v for pair in pairs for v in pair]
    expected = sum(masi(a, b) for a, b in combinations(values, 2)) / (len(values) * (len(values) - 1) / 2)
    return None if expected == 0 else 1 - observed / expected


def load_people(path: Path) -> dict[str, dict]:
    labels = json.loads(path.read_text(encoding="utf-8"))
    return {spot: l for spot, l in labels.items() if l.get("guide") == GUIDE}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--second", type=Path, help="a second person's labels, same format")
    args = parser.parse_args()

    ear = load_people(args.labels)
    second = load_people(args.second) if args.second else {}
    answers = json.loads(args.answers.read_text(encoding="utf-8"))
    judge = {}
    judge_file = CAPSTONE / "findings" / "crowd" / "judge-bench.csv"
    if judge_file.exists():
        for _, j in pd.read_csv(judge_file, keep_default_na=False).iterrows():
            if str(j["guide"]) == GUIDE:
                judge[j["spot"]] = j["judge_ticks"].split("; ")

    rows = []
    for spot, l in ear.items():
        a = answers.get(spot, {})
        rule_kinds = [a.get("what_happened", "")] + [t for t in str(a.get("tags", "")).split("; ") if t]
        rows.append({
            "spot": spot, "docket": a.get("docket"), "clock": a.get("clock"), "record": a.get("record"),
            "ear": ticks_of(l.get("ticks")),
            "judge": ticks_of(judge.get(spot)),
            "rules": frozenset(RULE_KINDS[k] for k in rule_kinds if k in RULE_KINDS),
            "second": ticks_of((second.get(spot) or {}).get("ticks")),
            "played": "; ".join(l.get("played") or []),
            "verdict": l.get("verdict"), "note": l.get("note", ""),
        })
    table = pd.DataFrame(rows)
    if table.empty or table["ear"].isna().all():
        print("No spots labelled by ear under version", GUIDE, "yet.")
        return 0
    out = table.copy()
    for col in ("ear", "judge", "rules", "second"):
        out[col] = out[col].map(lambda s: "; ".join(sorted(s)) if s is not None else "")
    out.to_csv(CAPSTONE / "findings" / "crowd" / "label-agreement.csv", index=False)
    print(f"{table['ear'].notna().sum()} spots labelled by ear (guidelines {GUIDE}); "
          f"{len(judge)} judged; {table['second'].notna().sum()} by a second person")
    unheard = table[table["ear"].notna() & (table["played"] == "")]
    if len(unheard):
        print(f"{len(unheard)} of them with no clip played: {', '.join(unheard['spot'])}")
    print()

    comparisons = [("judge", "ear"), ("rules", "ear"), ("second", "ear")]
    summary, per_question = [], []
    for x, y in comparisons:
        both = table[table[x].notna() & table[y].notna()]
        if both.empty:
            continue
        questions = [q for q in QUESTIONS if x != "rules" or q in RULE_KINDS.values()]
        pairs = list(zip(both[x], both[y]))
        if x == "rules":   # compare only what the rules can see
            pairs = [(a, b & frozenset(questions)) for a, b in pairs]
        alpha = alpha_masi(pairs)
        summary.append({"pair": f"{x} vs {y}", "spots": len(both),
                        "same set": sum(a == b for a, b in pairs) / len(pairs),
                        "alpha (MASI)": alpha})
        for q in questions:
            xs = [q in a for a, _ in pairs]
            ys = [q in b for _, b in pairs]
            kappa = cohen_kappa_score(xs, ys) if len(set(xs)) > 1 and len(set(ys)) > 1 else None
            per_question.append({"pair": f"{x} vs {y}", "question": q,
                                 f"yes ({x})": sum(xs), f"yes ({y})": sum(ys),
                                 "agree": sum(a == b for a, b in zip(xs, ys)) / len(xs), "kappa": kappa})

    print("Over the whole set of ticks per spot:")
    print(pd.DataFrame(summary).round(2).to_string(index=False))
    print("\nQuestion by question (kappa blank where one side never said yes):")
    pq = pd.DataFrame(per_question)
    for pair, group in pq.groupby("pair", sort=False):
        x, y = pair.split(" vs ")
        print(f"\n{pair}")
        print(group[["question", f"yes ({x})", f"yes ({y})", "agree", "kappa"]].round(2).to_string(index=False))

    heard = table[table["ear"].notna()]
    longer = heard["played"].str.contains("three")
    if longer.any() and (~longer).any():
        print("\nDoes hearing the three-sentence clip go with more overlap ticks?")
        for name, part in (("played three sentences", heard[longer]), ("did not", heard[~longer])):
            share = sum("overlap" in s for s in part["ear"]) / len(part)
            print(f"  {name}: {share:.0%} of {len(part)} spots ticked overlap")

    print("\nWho got it right, by ear:")
    print(heard["verdict"].fillna("not given").value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

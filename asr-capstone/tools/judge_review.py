"""Tally Claude's review of the Gemma judge (findings/judge/claude-review/).

Each case was read twice by Claude: first answered from the text alone, without
seeing Gemma's answers ("own"), then each of Gemma's answers marked agree,
partly or disagree with a reason ("review"). This prints the counts for
findings/judge/README.md.

    python tools/judge_review.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_failures as J  # noqa: E402

REVIEW = J.OUT / "claude-review"


def main() -> int:
    sample = pd.read_csv(J.SAMPLE, dtype=str, keep_default_na=False).set_index("case")
    answers = pd.read_csv(J.OUT / "answers-gemma4-26b.csv", dtype=str, keep_default_na=False)
    answers = answers[answers.prompt == answers.ask.map(J.PROMPT)].drop_duplicates(
        ["case", "ask", "variant"], keep="last")
    gemma = {(r.case, f"{r.ask}/{r.variant}"): json.loads(r.answer) for r in answers.itertuples()}

    verdicts, own, misses, listen = [], [], [], []
    for path in sorted(REVIEW.glob("s*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        case = d["case"]
        for key, v in d["review"].items():
            if isinstance(v, dict) and "verdict" in v:
                verdicts.append({"case": case, "request": key, "verdict": v["verdict"]})
        for item in d["review"].get("misses", []):
            misses.append({"case": case, **{k: item.get(k, "") for k in ("is_real", "matters", "severity_fair")}})
        g = gemma.get((case, "labelled/minute"), {})
        o = d["own"]
        own.append({"case": case, "kind": sample.loc[case, "kind"], "source": sample.loc[case, "source"],
                    "claude_meaning": o.get("meaning"), "gemma_meaning": g.get("meaning"),
                    "claude_severity": o.get("severity"), "gemma_severity": g.get("severity"),
                    "claude_noticeable": o.get("noticeable"), "gemma_noticeable": g.get("noticeable"),
                    "claude_plausible": o.get("more_plausible"),
                    "overlooked": len(d["review"].get("overlooked", []))})
        if d.get("worth_a_listen", {}).get("yes"):
            listen.append(f"{case} {sample.loc[case, 'corpus']} {sample.loc[case, 'engine']}: "
                          f"{d['worth_a_listen'].get('why', '')}")

    v = pd.DataFrame(verdicts)
    print("== Claude's verdict on each Gemma answer")
    table = pd.crosstab(v.request, v.verdict)
    print(table.to_string())
    print("all:", v.verdict.value_counts().to_dict(), "\n")

    o = pd.DataFrame(own)
    print("== Meaning at the minute, Claude (rows, answered first) against Gemma (columns)")
    print(pd.crosstab(o.claude_meaning, o.gemma_meaning).to_string())
    print(f"Same verdict: {(o.claude_meaning == o.gemma_meaning).sum()} of {len(o)}\n")
    o["gap"] = pd.to_numeric(o.gemma_severity) - pd.to_numeric(o.claude_severity)
    print("Gemma's severity minus Claude's, by kind (mean):", o.groupby("kind").gap.mean().round(1).to_dict())
    print("  Gemma higher in", (o.gap > 0).sum(), "cases, lower in", (o.gap < 0).sum(), ", equal in", (o.gap == 0).sum())
    print("Noticeable (Claude rows, Gemma columns):")
    print(pd.crosstab(o.claude_noticeable, o.gemma_noticeable).to_string())
    print("Claude's view of which version was really said:", o.claude_plausible.value_counts().to_dict(), "\n")

    m = pd.DataFrame(misses)
    print(f"== Gemma's misses items, checked one by one ({len(m)})")
    for col in ("is_real", "matters", "severity_fair"):
        print(f"  {col}:", m[col].value_counts().to_dict())
    print("Differences that matter which Gemma's list left out:", int(o.overlooked.sum()), "\n")

    print("== Worth a listen")
    for line in listen:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

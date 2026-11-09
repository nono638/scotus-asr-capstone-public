"""Build the judge bench: the 300 combo-v1 cases, to label by ear.

For the test of which combination of questions finds the interesting cases
(future-work-llm-judge.md): Sonnet's answers to several narrow questions are
combined by a small model, and these labels are what it learns from. Each case
gets a clip (4 s either side of the spot, at least 10 s), the record's words
around the spot, the engine's own words lit up as the clip plays, and one other
engine (one that got it right, if any did). The judge's answers and the rule's
label are not on the page, so the labels are blind to them.

The cases are shown in a random order, mixed across data sets, so labelling only
the first 150 still gives a fair spread. Earnings-22 audio has no stated licence,
so its cases are text only unless --earnings-audio (the site plays none of it).

Clips are cut with the website's own card maker (build_site.make_card). Needs the
recordings, so the 5090 laptop; no GPU.

    python tools/build_judge_bench.py --out <folder> [--earnings-audio]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "tools"))

import build_site  # noqa: E402
import lineup  # noqa: E402

COMBO = CAPSTONE / "findings" / "judge" / "combo-v1.csv"
TEMPLATE = CAPSTONE / "tools" / "judge_bench" / "template.html"
WIDGETS = CAPSTONE / "web" / "widget"
SEED = 2026
CORPUS = {"scotus": "Supreme Court", "coraal": "CORAAL", "edacc": "EdAcc", "earnings22": "Earnings-22"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--earnings-audio", action="store_true", help="cut clips for Earnings-22 too")
    args = parser.parse_args()

    # make_card writes its clip under build_site.SITE; point that at the bench's folder.
    build_site.SITE = args.out
    build_site.DATASETS["earnings22"]["clips"] = args.earnings_audio

    rows = pd.read_csv(COMBO, dtype=str, keep_default_na=False)
    rows = rows.sample(frac=1, random_state=SEED).reset_index(drop=True)
    rows["bench"] = [f"b{i + 1:03d}" for i in range(len(rows))]

    cases, missing = {}, []
    for corpus in CORPUS:
        jobs = {(j["term"], j["docket"]): j for j in lineup.recordings(corpus)}
        mine = rows[rows.corpus == corpus].sort_values(["recording", "start"])
        for n, r in enumerate(mine.itertuples(), 1):
            print(f"[{corpus} {n}/{len(mine)}] {r.bench} {r.recording} {r.engine} {r.start}", flush=True)
            card = build_site.make_card(r.kind, r, jobs, "", 0.0)
            if card is None:
                missing.append(r.bench)
                continue
            cases[r.bench] = {
                "id": r.bench, "case": r.case, "corpus": CORPUS[corpus], "where": card["where"],
                "engine": r.engine, "clip": card["clip"], "views": card["views"], "lines": card["lines"],
            }

    ordered = [cases[b] for b in rows.bench if b in cases]
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("/*TOKENS*/", (WIDGETS / "tokens.css").read_text(encoding="utf-8"))
            .replace("/*LISTEN*/", (WIDGETS / "listen.js").read_text(encoding="utf-8"))
            .replace("/*COMPARE*/", (WIDGETS / "compare.js").read_text(encoding="utf-8"))
            .replace("/*CASES*/[]", json.dumps(ordered, ensure_ascii=False)))
    (args.out / "judge-bench.html").write_text(page, encoding="utf-8")
    clips = sorted((args.out / "clips").rglob("*.mp3"))
    print(f"\n{len(ordered)} cases; {len(clips)} clips, {sum(c.stat().st_size for c in clips) / 1e6:.1f} MB; "
          f"page {len(page) / 1e6:.2f} MB; {len(missing)} not found {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

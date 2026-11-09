"""Every Parakeet run before and after the gap re-read, from the pipeline's own scores.

Reads results/scores.csv of each old run and its -reread twin (scored with
`scotus_asr.cli score`), standard rule, and adds up the words.

    python full_pass.py    # -> findings/parakeet-stall/full-pass.csv
"""
import csv
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parents[3]
RUNS = [("Earnings-22", "D:/asr-corpora/earnings22/runs/run-earnings22-parakeet"),
        ("CORAAL", "D:/asr-corpora/coraal/runs/run-coraal-parakeet"),
        ("EdAcc", "D:/asr-corpora/edacc/runs/run-edacc-parakeet"),
        ("Supreme Court OT2017", "D:/scotus-corpus/runs/run-20260924-064733"),
        ("Supreme Court, other terms", "D:/scotus-corpus/runs/run-scotus250-parakeet")]


def scores(run: str) -> dict:
    """{recording: (wrong, dropped, added, reference words)} on the standard rule."""
    with open(Path(run, "results/scores.csv"), encoding="utf-8") as f:
        return {r["docket"]: [int(r[k]) for k in ("substitutions", "deletions", "insertions", "reference_tokens")]
                for r in csv.DictReader(f) if r["normalizer"] == "standard"}


def rate(rows, i=None) -> float:
    ref = sum(r[3] for r in rows)
    errors = sum(r[i] for r in rows) if i is not None else sum(sum(r[:3]) for r in rows)
    return round(100 * errors / ref, 2)


out = []
for name, old in RUNS:
    before, after = scores(old), scores(old + "-reread")
    both = sorted(set(before) & set(after))
    b, a = [before[k] for k in both], [after[k] for k in both]
    pct = lambda r: 100 * sum(r[:3]) / r[3]
    out.append({
        "data_set": name, "recordings": len(both),
        "wer_before": rate(b), "wer_after": rate(a),
        "dropped_before": rate(b, 1), "dropped_after": rate(a, 1),
        "added_before": rate(b, 2), "added_after": rate(a, 2),
        "wrong_before": rate(b, 0), "wrong_after": rate(a, 0),
        # 0.05 points either way counts as the same.
        "better": sum(pct(after[k]) < pct(before[k]) - 0.05 for k in both),
        "worse": sum(pct(after[k]) > pct(before[k]) + 0.05 for k in both),
    })
    print(out[-1])

with open(CAPSTONE / "findings/parakeet-stall/full-pass.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)

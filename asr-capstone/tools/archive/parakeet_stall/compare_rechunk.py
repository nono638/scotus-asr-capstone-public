"""Gaps over speech for the original Parakeet run and each re-chunked version.

Same gap rule as parakeet_gaps.py: 4+ s with no Parakeet word while Whisper and
Qwen3 each wrote 8+ words there.
"""
import json
from pathlib import Path

SP = Path(__file__).parent
CASES = {
    "20-543": ("D:/scotus-corpus/runs", "scotus250"),
    "4482311": ("D:/asr-corpora/earnings22/runs", "earnings22"),
    "DCB_se3_ag4_m_02_1": ("D:/asr-corpora/coraal/runs", "coraal"),
    "EDACC-C52": ("D:/asr-corpora/edacc/runs", "edacc"),
}


def words(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(w["start"], w["end"]) for s in d["segments"] for w in s["words"]]


def gaps(pw, others):
    out = []
    for a, b in zip(pw, pw[1:]):
        if b[0] - a[1] >= 4 and min(sum(a[1] <= w[0] < b[0] for w in o) for o in others) >= 8:
            out.append(b[0] - a[1])
    return out


for rid, (runs, tag) in CASES.items():
    others = [words(next(Path(runs, f"run-{tag}-{e}", "asr").glob(f"{rid}.*.json"))) for e in ("whisper", "qwen3")]
    versions = {"300 s (as run)": next(Path(runs, f"run-{tag}-parakeet", "asr").glob(f"{rid}.*.json"))}
    for c in ("300+reread", "120", "120+reread", "60", "30", "25-15"):
        p = SP / f"rechunk-{c}" / f"{rid}.json"
        if p.exists():
            versions[f"{c} s"] = p
    print(f"{rid}  (Whisper {len(others[0])} words, Qwen3 {len(others[1])})")
    for label, p in versions.items():
        pw = words(p)
        g = gaps(pw, others)
        print(f"   {label:<15} {len(pw):6d} words   {len(g):3d} gaps, {sum(g):6.1f} s blank, longest {max(g, default=0):5.1f} s")

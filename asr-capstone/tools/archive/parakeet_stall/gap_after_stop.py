"""Do Parakeet's gaps over speech start right after a sentence end (. ? !)?

Compares the word before each gap (4+ s blank, Whisper and Qwen3 each 8+ words
inside) with the base rate over all Parakeet words.
"""
import json, sys
from pathlib import Path

RUNS, PARA, OTHERS = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
END = (".", "?", "!")
def words(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    return [(w["start"], w["end"], w["text"].strip()) for s in d["segments"] for w in s["words"]]
gap_end = gap_n = all_end = all_n = 0
for p in sorted((RUNS / PARA / "asr").glob("*.json")):
    rec = p.name.split(".")[0]
    hits = [list((RUNS / o / "asr").glob(rec + ".*.json")) for o in OTHERS]
    if not all(hits):
        continue
    others = [words(h[0]) for h in hits]
    pw = words(p)
    all_n += len(pw); all_end += sum(w[2].endswith(END) for w in pw)
    for a, b in zip(pw, pw[1:]):
        if b[0] - a[1] >= 4 and min(sum(a[1] <= w[0] < b[0] for w in o) for o in others) >= 8:
            gap_n += 1; gap_end += a[2].endswith(END)
print(f"{PARA}: gaps after a sentence end {gap_end}/{gap_n} = {100*gap_end/gap_n:.0f}%;"
      f"  all words ending a sentence {100*all_end/all_n:.0f}%")

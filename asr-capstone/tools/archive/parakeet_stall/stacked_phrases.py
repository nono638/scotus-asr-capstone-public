"""Stock phrases Parakeet stamps on a single instant, before and after the re-read.

Looking for loops in the re-read words turned up something else: four or more
words all given the same start time, and nearly always a stock phrase ("a very
important thing", "I think that's a good idea", "going to be able to do that").
Nobody says six words in one 80 ms frame, and none of the restored ones is in
the reference. This counts them in the old transcripts and in the -reread ones,
to see whether the re-read made them or they were there already.

    python stacked_phrases.py    # -> findings/parakeet-stall/stacked-phrases.csv
"""
import csv
import json
from collections import Counter
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parents[3]
RUNS = [("Earnings-22", "D:/asr-corpora/earnings22/runs/run-earnings22-parakeet"),
        ("CORAAL", "D:/asr-corpora/coraal/runs/run-coraal-parakeet"),
        ("EdAcc", "D:/asr-corpora/edacc/runs/run-edacc-parakeet"),
        ("Supreme Court OT2017", "D:/scotus-corpus/runs/run-20260924-064733"),
        ("Supreme Court, other terms", "D:/scotus-corpus/runs/run-scotus250-parakeet")]
MIN_WORDS = 4


def words(path: Path) -> list[tuple]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(w["start"], w["end"], w["text"]) for s in data["segments"] for w in s.get("words", [])]


def stacks(ws) -> list[tuple]:
    """(start, phrase) for every start time shared by MIN_WORDS words or more."""
    count = Counter(round(w[0], 2) for w in ws)
    return [(t, " ".join(w[2].strip() for w in ws if round(w[0], 2) == t))
            for t, n in count.items() if n >= MIN_WORDS]


rows = []
for name, old in RUNS:
    row = {"data_set": name, "words_before": 0, "stacks_before": 0, "stacked_words_before": 0,
           "words_restored": 0, "stacks_added": 0, "stacked_words_added": 0}
    phrases = Counter()
    for new_file in sorted(Path(old + "-reread", "asr").glob("*.json")):
        before = words(Path(old, "asr", new_file.name))
        after = words(new_file)
        kept = set(before)
        added = [w for w in after if w not in kept]  # in the transcript's order, not sorted
        old_stacks, new_stacks = stacks(before), stacks(added)
        row["words_before"] += len(before)
        row["stacks_before"] += len(old_stacks)
        row["stacked_words_before"] += sum(len(p.split()) for _, p in old_stacks)
        row["words_restored"] += len(added)
        row["stacks_added"] += len(new_stacks)
        row["stacked_words_added"] += sum(len(p.split()) for _, p in new_stacks)
        phrases.update(p.lower().strip(".,?! ") for _, p in old_stacks + new_stacks)
    row["commonest"] = "; ".join(f"{p} ({n})" for p, n in phrases.most_common(3))
    rows.append(row)
    print(row)

with open(CAPSTONE / "findings/parakeet-stall/stacked-phrases.csv", "w", newline="", encoding="utf-8") as f:
    out = csv.DictWriter(f, fieldnames=list(rows[0]))
    out.writeheader()
    out.writerows(rows)

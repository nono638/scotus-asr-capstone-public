"""Parakeet's blank stretches over speech, per data set, as one CSV.

A gap: 4+ s with no Parakeet word while Whisper and Qwen3 each wrote 8+ words
there. Only recordings all three engines have done. Also counts how many gaps
start right after a word ending a sentence, against the base rate.
"""
import csv, json, sys
from pathlib import Path
SETS = [("Supreme Court", "D:/scotus-corpus/runs", "scotus250"), ("Earnings-22", "D:/asr-corpora/earnings22/runs", "earnings22"),
        ("CORAAL", "D:/asr-corpora/coraal/runs", "coraal"), ("EdAcc", "D:/asr-corpora/edacc/runs", "edacc")]
END = (".", "?", "!")
def load(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    return d["audio_seconds"], [(w["start"], w["end"], w["text"].strip()) for s in d["segments"] for w in s["words"]]
out = csv.writer(open(sys.argv[1], "w", newline="", encoding="utf-8"))
out.writerow(["data_set", "recordings", "audio_hours", "gaps_over_speech", "blank_minutes", "blank_pct_of_audio",
              "longest_gap_seconds", "gaps_after_sentence_end", "gaps_after_sentence_end_pct", "all_words_ending_sentence_pct"])
for name, runs, tag in SETS:
    n = secs = 0; gaps = []; after = 0; words_all = words_end = 0
    for p in sorted(Path(runs, f"run-{tag}-parakeet", "asr").glob("*.json")):
        rec = p.name.split(".")[0]
        hits = [list(Path(runs, f"run-{tag}-{e}", "asr").glob(rec + ".*.json")) for e in ("whisper", "qwen3")]
        if not all(hits):
            continue
        audio, pw = load(p); others = [load(h[0])[1] for h in hits]
        n += 1; secs += audio; words_all += len(pw); words_end += sum(w[2].endswith(END) for w in pw)
        for a, b in zip(pw, pw[1:]):
            if b[0] - a[1] >= 4 and min(sum(a[1] <= w[0] < b[0] for w in o) for o in others) >= 8:
                gaps.append(b[0] - a[1]); after += a[2].endswith(END)
    out.writerow([name, n, round(secs/3600, 1), len(gaps), round(sum(gaps)/60), round(100*sum(gaps)/secs, 1),
                  round(max(gaps), 1), after, round(100*after/len(gaps)), round(100*words_end/words_all)])

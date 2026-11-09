"""Write the four-recording test (score_rechunk + compare_rechunk) as one CSV."""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
SP = Path(__file__).parent
sys.path.insert(0, r"C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline")
import yaml
from scotus_asr.config import ScoringSettings
from scotus_asr.scoring.metrics import score_case
from scotus_asr.stages import _load_asr_result
from scotus_asr.transcripts.model import Transcript
CASES = {"20-543": ("D:/scotus-corpus/runs", "scotus250", "Supreme Court"),
         "4482311": ("D:/asr-corpora/earnings22/runs", "earnings22", "Earnings-22"),
         "DCB_se3_ag4_m_02_1": ("D:/asr-corpora/coraal/runs", "coraal", "CORAAL"),
         "EDACC-C52": ("D:/asr-corpora/edacc/runs", "edacc", "EdAcc")}
def words(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return [(w["start"], w["end"]) for s in d["segments"] for w in s["words"]]
def gaps(pw, others):
    return [b[0]-a[1] for a, b in zip(pw, pw[1:])
            if b[0]-a[1] >= 4 and min(sum(a[1] <= w[0] < b[0] for w in o) for o in others) >= 8]
out = csv.writer(open(sys.argv[1], "w", newline="", encoding="utf-8"))
out.writerow(["data_set", "recording", "version", "wer_standard", "dropped_pct", "wrong_pct", "added_pct",
              "words", "gaps_over_speech", "blank_seconds", "longest_gap_seconds"])
for rid, (runs, tag, name) in CASES.items():
    run = Path(runs, f"run-{tag}-parakeet")
    scoring = ScoringSettings(**yaml.safe_load((run / "config_used.yaml").read_text(encoding="utf-8"))["scoring"])
    ref = Transcript.from_dict(json.loads((run / "reference" / f"{rid}.json").read_text(encoding="utf-8")))
    others = {e: next(Path(runs, f"run-{tag}-{e}", "asr").glob(f"{rid}.*.json")) for e in ("whisper", "qwen3")}
    versions = {"Whisper": others["whisper"], "Qwen3": others["qwen3"],
                "Parakeet 300 s (as run)": next((run / "asr").glob(f"{rid}.*.json"))}
    for c, label in [("300+reread", "Parakeet 300 s + gap re-read"), ("120", "Parakeet 120 s"),
                     ("120+reread", "Parakeet 120 s + gap re-read"), ("60", "Parakeet 60 s"),
                     ("30", "Parakeet 30 s"), ("25-15", "Parakeet 25 s, 15 s overlap")]:
        versions[label] = SP / f"rechunk-{c}" / f"{rid}.json"
    ow = [words(p) for p in others.values()]
    for label, p in versions.items():
        res = _load_asr_result(p)
        r = score_case(ref, res, scoring, audio_minutes=res.audio_seconds / 60).rows[0]
        n = r.reference_tokens
        g = gaps(words(p), ow) if label.startswith("Parakeet") else []
        out.writerow([name, rid, label, round(100*(r.substitutions+r.deletions+r.insertions)/n, 2),
                      round(100*r.deletions/n, 2), round(100*r.substitutions/n, 2), round(100*r.insertions/n, 2),
                      len(words(p)), len(g) if label.startswith("Parakeet") else "",
                      round(sum(g), 1) if label.startswith("Parakeet") else "",
                      round(max(g, default=0), 1) if label.startswith("Parakeet") else ""])

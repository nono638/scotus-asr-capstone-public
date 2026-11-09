"""Earnings-22 Subset 10: each engine scored against two human references of the same calls.

Rev had ten calls transcribed twice: verbatim (fillers, restarts and stutters kept) and
cleaned up. Scoring each engine against both shows which transcriber's style it writes
closest to. The cleaned-up reference is also scored against the verbatim one, as if it
were an engine, to show how far apart the two humans are. Same runs and scoring settings
as the published Earnings-22 numbers (Parakeet: the re-read run).

    python tools/subset10_two_refs.py   (processor only, a few minutes)

Writes findings/earnings22/subset10-two-references.csv: one row per transcriber, call,
reference and rule, with the counts.
"""
import sys
from pathlib import Path

import pandas as pd
import yaml

CAP = Path(r"C:\Users\noahc\code\Fall-2026\asr-capstone")
sys.path.insert(0, str(CAP / "pipeline"))
from scotus_asr.asr.base import AsrResult, Segment  # noqa: E402
from scotus_asr.config import ScoringSettings  # noqa: E402
from scotus_asr.corpora.earnings22 import Earnings22Corpus  # noqa: E402
from scotus_asr.scoring.metrics import score_case  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402

ROOT = Path("D:/asr-corpora/earnings22")
RUNS = {"Whisper": "run-earnings22-whisper", "Qwen3": "run-earnings22-qwen3",
        "Parakeet": "run-earnings22-parakeet-reread"}
corpus = Earnings22Corpus(ROOT, split="subset10")
recs = corpus.recordings()
print(len(recs), "calls,", round(sum(r.audio_minutes for r in recs) / 60, 1), "hours")

rows = []


def add(who, rec, result, scoring):
    for ref_name, ref in (("verbatim", corpus.reference(rec)), ("clean", corpus.nonverbatim_reference(rec))):
        for r in score_case(ref, result, scoring, rec.audio_minutes).rows:
            rows.append({"who": who, "call": rec.id, "reference": ref_name, "rule": r.normalizer,
                         "errors": r.substitutions + r.deletions + r.insertions,
                         "sub": r.substitutions, "del": r.deletions, "ins": r.insertions,
                         "ref_words": r.reference_tokens})


for engine, run in RUNS.items():
    run_dir = ROOT / "runs" / run
    scoring = ScoringSettings(**yaml.safe_load((run_dir / "config_used.yaml").read_text(encoding="utf-8")).get("scoring", {}))
    for rec in recs:
        add(engine, rec, _load_asr_result(next((run_dir / "asr").glob(f"{rec.id}.*.json"))), scoring)

# The two human references against each other: the clean one scored as if it were an engine.
for rec in recs:
    text = corpus.nonverbatim_reference(rec).full_text(include_speakers=False)
    secs = rec.audio_minutes * 60
    add("Clean transcriber", rec, AsrResult(rec.id, "clean", "nlp", [Segment(0, 0.0, secs, text, [])], secs), scoring)

t = pd.DataFrame(rows)
t.to_csv(CAP / "findings" / "earnings22" / "subset10-two-references.csv", index=False)
pooled = t.groupby(["rule", "who", "reference"])[["errors", "sub", "del", "ins", "ref_words"]].sum()
pooled["wer"] = (100 * pooled.errors / pooled.ref_words).round(2)
for what in ("sub", "del", "ins"):
    pooled[what] = (100 * pooled[what] / pooled.ref_words).round(2)
wide = pooled.wer.unstack("reference")
wide["closer to"] = wide.idxmin(axis=1)
pd.set_option("display.width", 200)
print(wide)
print(pooled[["sub", "del", "ins", "ref_words"]])
per = t[t.rule == "lowercase_nopunct"].pivot_table(index=["who", "call"], columns="reference", values=["errors", "ref_words"], aggfunc="sum")
w = (100 * per["errors"] / per["ref_words"]).round(1)
print(w.assign(gap=(w.verbatim - w.clean).round(1)).gap.unstack("who"))

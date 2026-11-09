"""The gap re-read on recordings picked at random, not for their holes.

The four test recordings were the worst in each data set, so they flatter the
fix. This picks 3 more per data set at random (seed 23, leaving those four out,
only recordings all three engines have done), and compares Parakeet before and
after the re-read, with Whisper and Qwen3 beside them.

    python sample_check.py pick     # print the picks, to pass to the re-read tool
    python sample_check.py score    # after the re-read: findings/parakeet-stall/random-sample.csv
"""
import csv
import json
import random
import sys
from pathlib import Path

import yaml

CAPSTONE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CAPSTONE / "pipeline"))
from scotus_asr.config import ScoringSettings  # noqa: E402
from scotus_asr.scoring.metrics import score_case  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402

SETS = [("Supreme Court", "D:/scotus-corpus/runs", "scotus250"),
        ("Earnings-22", "D:/asr-corpora/earnings22/runs", "earnings22"),
        ("CORAAL", "D:/asr-corpora/coraal/runs", "coraal"),
        ("EdAcc", "D:/asr-corpora/edacc/runs", "edacc")]
TESTED = {"20-543", "4482311", "DCB_se3_ag4_m_02_1", "EDACC-C52"}
PER_SET = 3


def ids(run: Path) -> set[str]:
    return {p.name.split(".")[0] for p in (run / "asr").glob("*.json")}


def picks(runs: str, tag: str) -> list[str]:
    shared = set.intersection(*(ids(Path(runs, f"run-{tag}-{e}")) for e in ("parakeet", "whisper", "qwen3")))
    return random.Random(23).sample(sorted(shared - TESTED), PER_SET)


def score(run: Path, rid: str, ref: Transcript, scoring: ScoringSettings):
    res = _load_asr_result(next((run / "asr").glob(f"{rid}.*.json")))
    r = score_case(ref, res, scoring, audio_minutes=res.audio_seconds / 60).rows[0]  # standard rule
    n = r.reference_tokens
    return [round(100 * (r.substitutions + r.deletions + r.insertions) / n, 2),
            round(100 * r.deletions / n, 2), round(100 * r.insertions / n, 2), n]


if sys.argv[1] == "pick":
    for name, runs, tag in SETS:
        print(f"{name}: {' '.join(picks(runs, tag))}")
else:
    out = csv.writer(open(CAPSTONE / "findings/parakeet-stall/random-sample.csv", "w", newline="", encoding="utf-8"))
    out.writerow(["data_set", "recording", "reference_words", "parakeet_before", "parakeet_after",
                  "dropped_before", "dropped_after", "added_before", "added_after",
                  "words_restored", "whisper", "qwen3"])
    for name, runs, tag in SETS:
        old = Path(runs, f"run-{tag}-parakeet")
        scoring = ScoringSettings(**yaml.safe_load((old / "config_used.yaml").read_text(encoding="utf-8"))["scoring"])
        for rid in picks(runs, tag):
            ref = Transcript.from_dict(json.loads((old / "reference" / f"{rid}.json").read_text(encoding="utf-8")))
            before = score(old, rid, ref, scoring)
            new = Path(runs, f"run-{tag}-parakeet-reread")
            after = score(new, rid, ref, scoring)
            restored = json.loads(next((new / "asr").glob(f"{rid}.*.json")).read_text(encoding="utf-8"))["gap_reread"]["words_restored"]
            whisper = score(Path(runs, f"run-{tag}-whisper"), rid, ref, scoring)[0]
            qwen3 = score(Path(runs, f"run-{tag}-qwen3"), rid, ref, scoring)[0]
            row = [name, rid, before[3], before[0], after[0], before[1], after[1], before[2], after[2],
                   restored, whisper, qwen3]
            out.writerow(row)
            print(*row)

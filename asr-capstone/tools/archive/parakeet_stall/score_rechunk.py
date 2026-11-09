"""Score each Parakeet version of the four test recordings, plus Whisper and Qwen3.

Scored the way the scoring stage does it, with each run's own settings and
reference; nothing is written anywhere.
"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, r"C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline")
from scotus_asr.config import ScoringSettings  # noqa: E402
from scotus_asr.scoring.metrics import score_case  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402

SP = Path(__file__).parent
CASES = {
    "20-543": ("D:/scotus-corpus/runs", "scotus250"),
    "4482311": ("D:/asr-corpora/earnings22/runs", "earnings22"),
    "DCB_se3_ag4_m_02_1": ("D:/asr-corpora/coraal/runs", "coraal"),
    "EDACC-C52": ("D:/asr-corpora/edacc/runs", "edacc"),
}
RULE = sys.argv[1] if len(sys.argv) > 1 else None

for rid, (runs, tag) in CASES.items():
    run = Path(runs, f"run-{tag}-parakeet")
    used = yaml.safe_load((run / "config_used.yaml").read_text(encoding="utf-8"))
    scoring = ScoringSettings(**used.get("scoring", {}))
    ref = Transcript.from_dict(json.loads((run / "reference" / f"{rid}.json").read_text(encoding="utf-8")))
    versions = {e: next(Path(runs, f"run-{tag}-{e}", "asr").glob(f"{rid}.*.json")) for e in ("whisper", "qwen3")}
    versions["parakeet 300 s"] = next((run / "asr").glob(f"{rid}.*.json"))
    for c in ("300+reread", "120", "120+reread", "60", "30", "25-15"):
        p = SP / f"rechunk-{c}" / f"{rid}.json"
        if p.exists():
            versions[f"parakeet {c} s"] = p
    print(rid)
    for label, p in versions.items():
        res = _load_asr_result(p)
        score = score_case(ref, res, scoring, audio_minutes=res.audio_seconds / 60)
        rows = {r.normalizer: r for r in score.rows}
        r = rows.get(RULE) or next(iter(rows.values()))
        n = r.reference_tokens
        print(f"   {label:<18} {r.normalizer:<10} WER {100*(r.substitutions+r.deletions+r.insertions)/n:5.2f}%"
              f"   dropped {100*r.deletions/n:5.2f}%  wrong {100*r.substitutions/n:5.2f}%  added {100*r.insertions/n:5.2f}%")

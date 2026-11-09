"""Transcribe whole recordings with the real engine at a shorter chunk length.

Usage: parakeet_rechunk.py CHUNK_SECONDS OUT_DIR AUDIO=ID [AUDIO=ID ...]
Writes OUT_DIR/<ID>.json in the run's asr/ format; nothing else is touched.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline")
from scotus_asr.asr import parakeet_engine as pe  # noqa: E402
from scotus_asr.config import AsrSettings  # noqa: E402

chunk, _, overlap = sys.argv[1].partition("/")
chunk, overlap = float(chunk), float(overlap or 8)
pe.OVERLAP_SECONDS = overlap
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
pe.CHUNK_SECONDS = chunk
# keep_window's defaults were fixed at import; change them too or it trims at 300 s.
pe.keep_window.__defaults__ = (chunk, pe.OVERLAP_SECONDS)

engine = pe.ParakeetEngine(AsrSettings(engine="parakeet", model="parakeet-tdt-0.6b-v3",
                                       device="cuda", compute_type="float16", language="en"))
for pair in sys.argv[3:]:
    audio, rid = pair.split("=")
    result = engine.transcribe(Path(audio), rid)
    d = result.to_dict()
    (out / f"{rid}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"{rid}: {d['word_count']} words, {result.runtime_seconds:.0f}s, runaways so far {engine.runaway_chunks}",
          flush=True)

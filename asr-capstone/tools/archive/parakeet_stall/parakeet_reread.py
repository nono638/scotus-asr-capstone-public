"""Re-read Parakeet's blank stretches with a fresh decoder, and splice the words in.

Usage: parakeet_reread.py IN_JSON AUDIO OUT_JSON

Any stretch of GAP_SECONDS or more with no word (including the very start and
end) is decoded again on its own audio. A new decode starts the decoder from
scratch, which is what gets it past a full stop it stalled on. New gaps inside
a re-read are re-read in turn, up to MAX_DEPTH levels. Nothing is written but
OUT_JSON.
"""
import json
import sys
from pathlib import Path

import librosa

sys.path.insert(0, r"C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline")
from scotus_asr.asr import parakeet_engine as pe  # noqa: E402
from scotus_asr.asr.base import Word  # noqa: E402
from scotus_asr.config import AsrSettings  # noqa: E402

GAP_SECONDS = 4.0
MAX_DEPTH = 3
SR = pe.SAMPLE_RATE

engine = pe.ParakeetEngine(AsrSettings(engine="parakeet", model="parakeet-tdt-0.6b-v3",
                                       device="cuda", compute_type="float16", language="en"))
stats = {"rereads": 0, "seconds": 0.0, "found": 0}


def reread(audio, start, end, depth):
    """Words for start..end, decoded alone; its own gaps re-read in turn."""
    piece = audio[int(start * SR): int(end * SR)]
    if len(piece) < SR:
        return []
    stats["rereads"] += 1
    stats["seconds"] += end - start
    got = [w for w in engine._decode_piece(piece, start) if start <= w.start < end]
    return fill(audio, got, start, end, depth + 1) if depth + 1 < MAX_DEPTH else got


def fill(audio, words, start, end, depth):
    """`words` with every gap of GAP_SECONDS or more between start and end re-read."""
    edges = [start] + [t for w in words for t in (w.start, w.end)] + [end]
    out = list(words)
    for gap_from, gap_to in zip(edges[::2], edges[1::2]):   # end of one word -> start of next
        if gap_to - gap_from >= GAP_SECONDS:
            new = reread(audio, gap_from, gap_to, depth)
            stats["found"] += len(new)
            out += new
    return sorted(out, key=lambda w: w.start)


src, audio_path, dst = sys.argv[1:4]
d = json.loads(Path(src).read_text(encoding="utf-8"))
audio, _ = librosa.load(audio_path, sr=SR, mono=True)
old = [Word(**{k: w[k] for k in ("text", "start", "end")}, probability=None)
       for s in d["segments"] for w in s["words"]]
new = fill(audio, old, 0.0, len(audio) / SR, 0)
seen = {(w.start, w.text) for w in old}
added = [w for w in new if (w.start, w.text) not in seen]

# Each added word goes into the segment (chunk) whose stretch it falls in, so the
# seam clean-up still sees one segment per chunk.
starts = [s["start"] for s in d["segments"]]
for w in added:
    i = max([k for k, t in enumerate(starts) if t <= w.start] or [0])
    seg = d["segments"][i]
    seg["words"].append({"text": w.text, "start": w.start, "end": w.end, "probability": None})
for seg in d["segments"]:
    seg["words"].sort(key=lambda w: w["start"])
    seg["text"] = "".join(w["text"] for w in seg["words"]).strip()
d["word_count"] = sum(len(s["words"]) for s in d["segments"])
d["settings"]["gap_reread_seconds"] = GAP_SECONDS
Path(dst).parent.mkdir(parents=True, exist_ok=True)
Path(dst).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
print(f"{Path(src).name}: {stats['rereads']} re-reads over {stats['seconds']:.0f}s of audio, "
      f"{len(added)} words added, runaways {engine.runaway_chunks}", flush=True)

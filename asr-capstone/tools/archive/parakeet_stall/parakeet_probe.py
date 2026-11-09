"""Re-decode a stretch where Parakeet went silent, several ways, and count words.

Usage: parakeet_probe.py AUDIO CHUNK_START GAP_START GAP_END
Writes nothing anywhere; prints word counts and text for each variant.
"""
import sys
import time

import librosa
import torch
from transformers import ParakeetForTDT, ParakeetProcessor

sys.path.insert(0, r"C:\Users\noahc\code\Fall-2026\asr-capstone\pipeline")
from scotus_asr.asr.parakeet_engine import _to_words  # noqa: E402

AUDIO, C0, G0, G1 = sys.argv[1], *map(float, sys.argv[2:5])
SR = 16_000
ID = "nvidia/parakeet-tdt-0.6b-v3"

audio, _ = librosa.load(AUDIO, sr=SR, mono=True, offset=C0, duration=300.0)
proc = ParakeetProcessor.from_pretrained(ID)
models = {}


def model(dtype):
    if dtype not in models:
        models[dtype] = ParakeetForTDT.from_pretrained(ID, dtype=dtype).to("cuda").eval()
    return models[dtype]


def decode(start, length, dtype, label):
    """Decode audio[start:start+length] (seconds into the chunk) the engine's way."""
    piece = audio[int(start * SR): int((start + length) * SR)]
    inputs = proc(piece, sampling_rate=SR, return_tensors="pt")
    inputs = {k: (v.to("cuda").to(dtype) if v.dtype.is_floating_point else v.to("cuda"))
              for k, v in inputs.items()}
    t = time.time()
    with torch.no_grad():
        out = model(dtype).generate(**inputs, max_new_tokens=int(len(piece) / SR * 12))
    _, stamped = proc.decode(out.sequences, durations=out.durations, skip_special_tokens=True)
    words = _to_words(stamped[0], C0 + start)
    inside = [w for w in words if G0 <= w.start < G1]
    print(f"{label:<34} {len(words):5d} words, {len(inside):4d} in the gap  ({time.time()-t:.1f}s)")
    print("    gap text:", "".join(w.text for w in inside)[:220].strip() or "(nothing)")
    return inside


rel0, rel1 = G0 - C0, G1 - C0
decode(0, 300, torch.float16, "300 s chunk, float16 (as run)")
decode(0, 300, torch.float32, "300 s chunk, float32")
decode(max(0, rel0 - 30), 150, torch.float16, "150 s chunk, float16")
decode(max(0, rel0 - 10), 60, torch.float16, "60 s chunk, float16")
print("peak GPU memory %.1f GB" % (torch.cuda.max_memory_allocated() / 1e9))

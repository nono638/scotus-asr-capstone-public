"""Where do Parakeet's silent stretches fall inside its 300-second chunks?

A gap is 4+ seconds with no Parakeet word while Whisper or Qwen3 wrote 8+ words
there. Chunks start every 292 s (300 s with 8 s overlap). If the gaps are a
chunking bug they should pile up at one position in the chunk; if they are the
model they should be spread evenly.
"""
import json
import sys
from pathlib import Path

import numpy as np

RUNS = Path(sys.argv[1])
PARA, OTHERS = sys.argv[2], sys.argv[3:]
STEP = 292.0


def words(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return [(w["start"], w["end"], w["text"]) for s in d["segments"] for w in s["words"]]


rows = []
AUDIO = []
for p in sorted((RUNS / PARA / "asr").glob("*.json")):
    rec = p.name.split(".")[0]
    other = {}
    for o in OTHERS:
        hits = list((RUNS / o / "asr").glob(rec + ".*.json"))
        if hits:
            other[o] = words(hits[0])
    if len(other) < len(OTHERS):
        continue
    pw = words(p)
    AUDIO.append(json.loads(p.read_text(encoding="utf-8"))["audio_seconds"])
    starts = [w[0] for w in pw]
    for a, b in zip(pw, pw[1:]):
        g0, g1 = a[1], b[0]
        if g1 - g0 < 4:
            continue
        n = {o: sum(g0 <= w[0] < g1 for w in ws) for o, ws in other.items()}
        if min(n.values()) < 8:
            continue
        rows.append((rec, g0, g1, g0 % STEP, n))

print(len(rows), "gaps over speech")
pos = np.array([r[3] for r in rows])
hist, edges = np.histogram(pos, bins=np.arange(0, 301, 25))
for h, e in zip(hist, edges):
    print(f"{e:5.0f}-{e+25:3.0f}s into chunk: {'#' * h} {h}")
lengths = np.array([r[2] - r[1] for r in rows])
print("gap length: median %.1f s, max %.1f s, total %.0f s" % (np.median(lengths), lengths.max(), lengths.sum()))
for r in sorted(rows, key=lambda r: r[1] - r[2])[:15]:
    print(f"{r[0]:>12} {r[1]:8.1f}-{r[2]:8.1f} ({r[2]-r[1]:5.1f}s) {r[3]:5.1f}s into chunk  others {r[4]}")

# Does the gap run to the end of the chunk's kept window (next chunk takes over)?
def to_boundary(r):
    end_in = (r[2] - 4.0) % STEP          # next keep window starts at k*292+4... 
    return min(end_in, STEP - end_in) < 1.5 or r[2] % STEP < 5.5
edge = [r for r in rows if to_boundary(r)]
print(f"\n{len(edge)} of {len(rows)} gaps end within ~1.5 s of a chunk hand-over;"
      f" {sum(r[2]-r[1] for r in edge):.0f} of {lengths.sum():.0f} s")
print(f"{len(AUDIO)} recordings, {sum(AUDIO)/3600:.1f} h; missing {lengths.sum()/60:.0f} min = {lengths.sum()/sum(AUDIO)*100:.1f}% of audio")

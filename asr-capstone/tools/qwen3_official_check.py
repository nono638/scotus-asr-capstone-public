"""Do Qwen's own recommended settings score better than ours? A check on a sample.

Our Qwen3 runs use 280 s chunks at fixed cuts with 8 s of overlap, at float16. Qwen's own wrapper
(qwen_asr/inference, checked 6 November 2026) uses at most 180 s when timestamps are wanted, cut
at the quietest point near the target, at bfloat16, with no overlap. This decodes a sample of
recordings the official way, without the aligner since only the words are scored, and compares
with our run on the benchmark and verbatim rules. Writes findings/qwen3-official-check.csv.

Two things to keep the comparison fair. Our line-ups leave out what falls in a stretch the data
set marks as ignored; with no word times to do that here, those stretches are muted before
decoding. And `verbatim_ours` includes any chunk that lost its punctuation (repaired by
redecode_chunks.py), so read the verbatim columns on recordings that had none.

Rows already in the file are kept, and each official text is saved under OFFICIAL_TEXT.

    python tools/qwen3_official_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CAPSTONE / "tools"), str(CAPSTONE / "pipeline")]

import lineup  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402

MODEL = "Qwen/Qwen3-ASR-1.7B-hf"
SR = 16000
MAX_NEW = 4096
OFFICIAL_TEXT = Path("D:/scotus-corpus/experiments/qwen3-official")
RESULTS = CAPSTONE / "findings" / "qwen3-official-check.csv"
#: A fixed sample: long enough to hold several chunks, spread over the data sets and parts.
SAMPLE = {"scotus": ["OT2010", "OT2017", "OT2021", "OT2025"], "coraal": ["ROC", "DCB", "ATL"],
          "earnings22": ["English", "Asian", "Germanic"], "edacc": ["test", "dev"]}


def quiet_cut(audio: np.ndarray, target: float, expand: float = 5.0, window: float = 0.1) -> int:
    """The official split: the quietest point within a few seconds of the target."""
    lo, hi = int((target - expand) * SR), min(len(audio), int((target + expand) * SR))
    size = int(window * SR)
    power = np.convolve(np.abs(audio[lo:hi]), np.ones(size), "valid")
    return lo + int(np.argmin(power)) + size // 2


def main() -> int:
    import librosa
    import torch
    from transformers import AutoProcessor, Qwen3ASRForConditionalGeneration

    processor = AutoProcessor.from_pretrained(MODEL)
    model = Qwen3ASRForConditionalGeneration.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda").eval()

    def decode(piece) -> str:
        inputs = processor.apply_transcription_request(audio=piece, language="en", return_tensors="pt") \
            .to("cuda", dtype=torch.bfloat16)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=MAX_NEW, do_sample=False)
        return processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()

    rows = pd.read_csv(RESULTS, dtype={"recording": str}).to_dict("records") if RESULTS.exists() else []
    done = {r["recording"] for r in rows}
    OFFICIAL_TEXT.mkdir(parents=True, exist_ok=True)
    for corpus, parts in SAMPLE.items():
        for part in parts:
            jobs = sorted((j for j in lineup.recordings(corpus, [part])), key=lambda j: j["docket"])
            # The middle one by name: not chosen for how it scores.
            job = jobs[len(jobs) // 2]
            if job["docket"] in done:
                continue
            lined = lineup.load(job)
            transcript, reference, _, words = lined["Qwen3"]
            ours = [w.text.strip() for w in words]
            audio, _ = librosa.load(str(job["audio"]), sr=SR, mono=True)
            for quiet_from, quiet_to in transcript.ignore or []:
                audio[int(quiet_from * SR):int(quiet_to * SR)] = 0
            start, texts, gave_up = 0, [], 0
            while start < len(audio):
                seconds = (len(audio) - start) / SR
                cut = quiet_cut(audio, start / SR + 180) if seconds > 180 else len(audio)
                text = decode(audio[start:cut])
                if len(text.split()) < 20 and (cut - start) / SR > 100:
                    gave_up += 1
                texts.append(text)
                start = cut
            official = " ".join(texts).split()
            (OFFICIAL_TEXT / f"{job['docket']}.txt").write_text("\n".join(texts), encoding="utf-8")
            row = {"corpus": corpus, "part": part, "recording": job["docket"], "minutes": round(len(audio) / SR / 60, 1),
                   "pieces_gave_up": gave_up, "words_ours": len(ours), "words_official": len(official)}
            for rule, name in [("standard", "benchmark"), ("verbatim", "verbatim")]:
                a = align_words(reference, ours, rule, harmonise=True)
                b = align_words(reference, official, rule, harmonise=True)
                row[f"{name}_ours"] = round(a.wer * 100, 2)
                row[f"{name}_official"] = round(b.wer * 100, 2)
            rows.append(row)
            print(row, flush=True)
            pd.DataFrame(rows).to_csv(RESULTS, index=False)
    t = pd.DataFrame(rows)
    print("\nmean change, official minus ours:", {k: round((t[f"{k}_official"] - t[f"{k}_ours"]).mean(), 2) for k in ["benchmark", "verbatim"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

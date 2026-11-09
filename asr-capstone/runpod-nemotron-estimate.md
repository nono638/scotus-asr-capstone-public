# Nemotron 3.5 Transcribe on RunPod: what it would take and cost

Researched 8 November 2026. Research only: nothing was rented, logged in to or paid for.
Prices are as RunPod's page showed them that day. **Every speed, time and dollar figure
marked "estimate" is my own arithmetic, not a measurement or a quote.**

## Summary

- **Bottom line (estimate).** Transcribing all four data sets (about 626 hours of audio)
  on one rented RTX PRO 6000 (96 GB) would cost about **$12** at the middle speed guess,
  between $5 and $28 across the range, plus about $3.50 for a first test run. The four
  Supreme Court terms alone (310 h) would cost about $6, between $3 and $14.
- **What fits in $25.** A pilot of 5 arguments (about $3-5) plus all four Supreme Court
  terms fits in every case. All four data sets fit too, unless the model turns out to be
  slow on long recordings with word times switched on. Then they come to about $33 on
  Community Cloud, and more on Secure Cloud.
- **Recommendation.** Run the 5-argument pilot first, on an RTX PRO 6000 in full
  precision (BF16), with word timestamps on, and time it. The speed it shows decides
  everything else. At 100x real time or better, do all four data sets in one sitting. At
  under about 50x, do the four Supreme Court terms and leave EdAcc, CORAAL and
  Earnings-22 for the laptop. Use Secure Cloud for CORAAL and Earnings-22 (see Licences).
  When finished, **terminate** the pod (stopping is not enough) and delete any volume.
- **Cheaper ways to know about.** NVIDIA lists a 4-bit build for the RTX 5090, but that
  is the 32 GB desktop card. A 4-bit build (GGUF) might fit the 24 GB laptop with little
  room to spare. Nobody has published a test on a 24 GB card. Hosted APIs exist:
  DeepInfra charges $0.12 per audio hour (full precision), and OpenRouter lists a provider
  at $0.06. All four data sets would be about $75 or $38 there, with no setup.
- **Biggest uncertainty.** Speed on long, crosstalk-heavy recordings. NVIDIA's figures
  come from batches of short clips. Word timestamps, which this project needs, switch
  off the fastest settings. My range runs from 40x to 300x real time, a factor of 7.5.

## 1. The model, checked against NVIDIA's card

Nothing in this repository mentioned the model before this note. What the earlier notes
said, checked against the Hugging Face model card [1]:

| Earlier note | What the card says | Verdict |
|---|---|---|
| 30B hybrid Mamba-Transformer mixture of experts, about 4.3B active | "34B (4.3B active), including the audio encoder." The language part is Nemotron-3.5 Lightning 30B-A3B; the audio encoder is about 800M; a speaker encoder about 99M. "Mamba-2–Transformer hybrid Mixture of Experts" | **Corrected: 34B in all**, not 30B. 4.3B active is right. |
| All weights must be in memory | True of any mixture of experts. The full-precision file is one `model.safetensors` of 67.5 GB [2] | **Corrected: 67.5 GB**, not about 60 |
| Verbatim or clean output chosen by prompt | Verbatim: "Audio transcription. Language: as spoken. Wording: verbatim, including fillers and repetitions." Clean: "omit fillers and accidental repetitions; keep the remaining spoken wording unchanged." | Right |
| Up to about 1 hour per request | "up to 1 hour of audio, with a 65,536-token context". Offline only, not streaming | Right. Supreme Court arguments since 2021 run 82-83 min on average and up to 159, so they must be cut. |
| Runs on NeMo + vLLM (Python 3.13) or transformers from source | vLLM 0.32.0 with the NeMo Speech main branch; the install example uses Python 3.13 and `uv`. Also transformers "from source", SGLang-Omni 0.2.0, and GGML (NeMo-Speech.cpp) | Right, plus two more routes |
| Fits a 24 GB card only quantised (NVFP4 or GGUF) | The hardware table lists "RTX 5090, NVFP4" and GGML. That is the 32 GB desktop card, not the 24 GB laptop. No 24 GB card is listed. | **Partly wrong** - see section 6 |

Other facts from the card [1]:

- Word timestamps come from built-in CTC heads: "word text, start and end times in
  seconds". They need `VLLM_USE_V2_MODEL_RUNNER=0` and do not work with DFlash2, the
  fastest speculative decoder.
- Speaker labels (`<spk:0>` etc.) and a diarisation output are built in.
- Precisions: BF16 (the reference), FP8 and NVFP4, as separate checkpoints. The FP8
  files total 34.7 GB, the NVFP4 files 21.6 GB [2].
- Supported GPUs in the table include A100 80GB (BF16), H100 and H200 (BF16, FP8),
  L40S 48GB (FP8 only), RTX PRO 6000 Blackwell (BF16, FP8, NVFP4) and RTX 5090 (NVFP4).
- Linux. Windows only through WSL2, or natively with GGML.
- Known errors, from the card: "substitutions, deletions, repetitions, hallucinated speech,
  incorrect language choice". It recommends testing long recordings, overlapping speakers
  and noise.
- Earnings-22 on the card: 5.29 WER on the short Open ASR subset, **11.99 long-form**.
  Not directly comparable with this project's figures (different text normalisation), but
  in the same range as Qwen3's 11.34% here.

## 2. How much audio

| Data set | Recordings | Hours | On disk now (this laptop) | Source of the hours |
|---|---|---|---|---|
| Supreme Court OT2017 | 61 | 61.1 | 1.76 GB MP3 | `findings/corpus/terms.csv` |
| Supreme Court, four terms (2010, 2017, 2021, 2025) | 258 | 310.1 | 8.93 GB MP3 | same |
| EdAcc (test 40 = 18.2 h, dev 36) | 76 | 35.6 | 8.20 GB WAV | `findings/failures/meaning/README.md`, `findings/edacc/README.md` |
| CORAAL, all 8 parts | 271 | 160.9 (measured) | 51.1 GB WAV (44.1 kHz) | `datasets/coraal.md` |
| Earnings-22 | 125 | 118.9 | 1.91 GB MP3 | `datasets/earnings22.md` |
| **All four data sets** | **730** | **625.5** | **70.1 GB** | |

Sizes were read from `D:/scotus-corpus/cases` and `D:/asr-corpora/` on 8 November
(nothing changed). The model works at 16 kHz mono, so CORAAL and EdAcc can shrink a lot
before upload. At 16 kHz FLAC they would be about 11 GB and 2.5 GB (estimate: 115 MB an
hour as raw 16 kHz audio, about 60% after FLAC). The MP3s can go as they are.

## 3. RunPod: which cards, and prices

From RunPod's pricing page, 8 November 2026 [3]. On-demand Pods, per hour:

| Card | Memory | Can run | Secure Cloud | Community Cloud |
|---|---|---|---|---|
| H200 | 141 GB | BF16, roomy | $5.29 | $3.59 |
| H100 NVL | 94 GB | BF16 | $3.19 | $2.59 |
| H100 SXM | 80 GB | BF16 (tight: about 10 GB left for working memory), FP8 | $3.99 | $2.69 |
| H100 PCIe | 80 GB | same | $2.89 | $1.99 |
| **RTX PRO 6000** | **96 GB** | **BF16 with room to spare, FP8, NVFP4** | **$2.49** | **$1.69** |
| A100 SXM / PCIe | 80 GB | BF16 only (no FP8 on that generation), tight | $1.79 | $1.39 / $1.19 |
| L40S | 48 GB | FP8 only (34.7 GB of weights) | $1.09 | $0.79 |
| RTX 5090 | 32 GB | NVFP4 only (21.6 GB of weights) | $1.19 | $0.69 |

- **Full precision (BF16, 67.5 GB of weights):** H100, H100 NVL, H200, A100 80GB or
  RTX PRO 6000. The PRO 6000 is the best fit: the most memory left over for working
  memory, and the cheapest card with room. That is the card used in the estimates below.
- **Quantised:** L40S (FP8) or RTX 5090 (NVFP4). Cheaper per hour, but then the result is
  not the reference model, which matters when it is compared with the other engines.
- **Serverless** is dearer per hour (H100 $5.39, PRO 6000 $3.49, A100 $2.72) [3]. It
  bills cold starts (loading the model into the card) but not image pulls [5]. It suits
  many small requests, not a one-off batch, so Pods are the better choice here.
- **Spot (interruptible) pods:** RunPod's current pricing pages do not list them. A
  mirror of an older docs page says they could be stopped with a 5-second warning [6].
  Treat as not available and not needed: the job is short.

Storage and transfer [3][4]:

- Container disk: $0.10 per GB a month, only while running. **Erased when the pod stops.**
- Volume disk: $0.10 per GB a month while running, **$0.20 while stopped**.
- Network volume: $0.07 per GB a month (under 1 TB), billed whether a pod runs or not.
- "No fees for data ingress or egress."

Gotchas [4]:

- Billing is per second for compute and storage.
- A stopped pod still bills its volume disk. A 150 GB volume left stopped is $30 a month
  (estimate: 150 x $0.20), which would eat the whole credit. Terminate, don't stop.
- When the balance reaches $0, pods stop. "Pods without one [a network volume] are
  terminated", and "their data cannot be recovered". Download transcripts as they finish.
- Starting an on-demand pod needs at least one hour's worth of credit for it.
- Time spent uploading audio to a running GPU pod is billed GPU time. Upload first (or
  let the pod download the audio from the source sites), then start the work.
- A network volume ties pods to one data centre, so the card you want may not be free
  there.

## 4. Speed

**Published figures** [1]:

- On one H100 80 GB, BF16, "batched English ASR", "approximate": 410x real time with MTP2
  speculative decoding, 270x with MTP8, 340x and 260x with DFlash2. The card says
  "Throughput depends on recording length, output length, batch size, and GPU memory
  settings" and gives no batch size.
- NVIDIA's own server (NIM), NVFP4 with DFlash2, on an RTX PRO 6000: "up to 2,238 seconds
  of audio per second". The open vLLM version is "roughly two times slower".
- Nobody has published a figure for hour-long recordings or for the GGUF builds [7].

**My estimate for this project: 40x to 300x real time, middle 100x**, on an H100 or
RTX PRO 6000 in BF16. Why lower than NVIDIA's:

- Word timestamps need the older vLLM runner and rule out DFlash2.
- Long recordings mean few recordings fit in memory at once, so batches are small.
- A rough check (estimate): an hour of argument is about 10,000 words, perhaps 13,000
  text tokens. One stream decoding at 150-250 tokens a second takes 50-90 seconds, so
  40-70x for one recording at a time. Speculative decoding and running 4-8 recordings
  side by side would lift that to a few hundred.
- For comparison, Qwen3-ASR (1.7B) runs at about 10x on the laptop, one chunk at a time.

## 5. Estimates

**All figures in this table are estimates.** Assumptions: RTX PRO 6000, BF16, Community
Cloud $1.69/h and Secure Cloud $2.49/h; speeds 300x / 100x / 40x (fast / middle / slow);
setup overhead as stated. The pilot is the first session: starting the pod, installing
NeMo Speech and vLLM (10-20 min), downloading 67.5 GB of weights (5-15 min at
100-250 MB/s), loading and warming up (5-10 min), and testing and fixing problems (an hour
or more the first time). Later sessions reuse a network volume with the environment and
weights on it, so about 30 minutes each. Storage is extra: a 120 GB network volume costs
about $0.28 a day, $8.40 if left for a month.

| Job | Audio | GPU-hours (fast / middle / slow) | Community $ (fast / middle / slow) | Secure $ (fast / middle / slow) |
|---|---|---|---|---|
| (a) Pilot, 5 Supreme Court arguments, first session | about 5 h | 1.5 / 2.0 / 3.1 | 2.5 / 3.4 / 5.3 | 3.7 / 5.0 / 7.8 |
| (b) OT2017 | 61.1 h | 0.7 / 1.1 / 2.0 | 1.2 / 1.9 / 3.4 | 1.7 / 2.8 / 5.0 |
| (c) Four terms (includes OT2017) | 310.1 h | 1.5 / 3.6 / 8.3 | 2.6 / 6.1 / 14.0 | 3.8 / 9.0 / 20.6 |
| (d) All four data sets (includes (c)) | 625.5 h | 3.1 / 7.3 / 16.6 | 5.2 / 12.3 / 28.1 | 7.7 / 18.2 / 41.3 |

How rows (b) to (d) are built: audio hours divided by speed, plus 0.5 h of overhead
((d) gets 1.0 h, for converting and moving the extra data sets).

**What fits in $25 (estimate).**

| Plan | Middle | Slow |
|---|---|---|
| Pilot + four terms, Community | $9.50 + storage | $19.30 + storage |
| Pilot + all four data sets, Community | $15.70 + about $2 storage = **about $18** | **about $33: does not fit** |
| Pilot + all four data sets, Secure | about $25: borderline | about $49: does not fit |
| Pilot on Community, Supreme Court on Community, the other three on Secure | about $21 | does not fit |

Hosted API for comparison (prices quoted, totals are my arithmetic):

| Job | DeepInfra, $0.12 an audio hour [8] | OpenRouter's cheapest, $0.061 an audio hour [9] |
|---|---|---|
| Pilot, 5 h | $0.60 | $0.31 |
| OT2017 | $7.33 | $3.74 |
| Four terms | $37.21 | $18.98 |
| All four data sets | $75.06 | $38.28 |

## 6. What it would take in practice

**Setup on the pod.**

- Start from RunPod's PyTorch template (Linux, CUDA), or an official vLLM image at the
  version the card names, v0.32.0 (whether that image exists was not checked).
- Follow the card's quick start: `uv sync --extra asr --extra vllm` in the NeMo Speech
  repository (Python 3.13 in its own environment on the pod), `hf download` of the
  checkpoint, then `vllm serve` with the card's flags [1]. Set the audio length limit to
  3,600 seconds; the default is shorter [7].
- Or NVIDIA's NeMo-Speech.cpp, which added this model in v0.3.0 (30 October 2026) and
  batches requests on CUDA [10]. A container for it is on NGC.
- NVIDIA's NIM container is the fastest, but has its own terms, separate from the model's
  licence. Not looked into further.
- Disk: about 150 GB (weights 67.5 GB, environment, audio, outputs).

**Getting the audio up.**

- Supreme Court: no upload needed. The pod can download the MP3s from supremecourt.gov,
  as `fetch` does, or take the 8.9 GB of MP3s from the laptop.
- EdAcc, CORAAL, Earnings-22: either let the pod download them from their sources
  (Edinburgh DataShare, lingtools.uoregon.edu, Rev's GitHub; data-centre downloads are
  fast and free), or convert to 16 kHz FLAC on the laptop first (about 15 GB with
  Earnings-22's MP3s, estimate) and upload.
- Upload with `runpodctl send`/`receive`, or `scp`/`rsync` over the pod's SSH port.
  Upload to a network volume from a cheap CPU pod first, so no GPU time is spent waiting.
- At, say, 20 Mbit/s of upload (not measured), 15 GB takes about 1.7 hours.
- Cut anything over an hour. Every Supreme Court argument after 2020 needs at least two
  pieces. Shorter pieces (for example 10 minutes, with overlap) also batch better.

**Getting transcripts back.**

- The model returns text plus word start and end times as JSON. Even with word times,
  all 626 hours should come to well under 1 GB, about 100 MB compressed (estimate:
  about 6 million words at about 80 bytes each).
- Download with `runpodctl` or `scp` after each data set, not at the end.

**How it plugs into the pipeline** (description only, nothing written):

- Every engine writes one JSON file per recording, `asr/<recording>.<engine>.json` in the
  run folder (`store.asr_path`). It holds `docket`, `engine`, `model`, `audio_seconds`,
  `runtime_seconds`, `settings` and `segments`; each segment has `start`, `end`, `text`
  and `words` (each word `text`, `start`, `end`) (`asr/base.py`).
- A small converter on the laptop would turn the model's JSON into that shape. One
  segment per piece of audio, word times shifted by the piece's start. `settings` should
  record `chunk_seconds` and the overlap, so `stages._load_asr_result` drops words two
  pieces both wrote, as it does for Qwen3.
- The score stage takes the engine name from the config (`build_engine(config.asr).name`).
  So it needs a small `nemotron` entry in `asr/registry.py` whose name matches the files.
  It never transcribes; it only names the files. Then
  `run-<corpus>-nemotron/asr/` plus `score` on the laptop gives the same `scores.csv`,
  and `crowd.py`, `lineup.py` and the failure searches pick it up like any other engine.
- `tools/summarise_runs.py` can also score a CTM file made elsewhere. That is a quicker
  first look, but the lineup tools read the JSON files.
- Prompts: run the verbatim prompt for the record rule. The clean prompt is a second run,
  and could be compared against Earnings-22's two references.

**Licences.**

- **The model: OpenMDW-1.1** [11]. "permission is hereby granted, free of charge, to deal
  in the Model Materials without restriction". It "does not impose any restrictions or
  obligations with respect to any use, modification, or sharing of any outputs."
  Conditions apply only if you hand on the weights: keep the licence and notices. Rights
  end if you sue claiming the model infringes a patent or copyright. The card says it is
  "ready for commercial or non-commercial use". So the transcripts can be published like
  the other engines' (see `going-public.md`, "The engines' transcripts").
- **Supreme Court:** public domain, no concern.
- **EdAcc (CC BY-SA 4.0):** processing on a rented machine is a use, not sharing. Fine.
- **CORAAL (CC BY-NC-SA 4.0):** copying it to a server you rent, for non-commercial
  research, is reproduction for a non-commercial purpose, which the licence allows (my
  reading). Paying RunPod does not make it commercial: money goes out, not in. Delete it
  from the pod and volume afterwards. Use Secure Cloud (RunPod's own data centres), not
  Community Cloud, whose machines belong to individual hosts. The interviews are of real
  people, even with names bleeped.
- **Earnings-22 (audio has no licence):** processing it on a rented machine is the same
  use as processing it on the laptop, which the project already does. Publishing audio is
  the problem, and this does not publish anything (my reading). Lowest risk: have the
  pod download it from Rev's GitHub, use Secure Cloud, delete afterwards.
- A hosted API also processes the audio on someone else's machine. DeepInfra says "zero
  retention" [8]. OpenRouter's page says nothing about retention [9].

## 7. Alternatives

**On the 5090 laptop (24 GB), quantised.**

- **Not with vLLM and the NVFP4 checkpoint.** Its files are 21.6 GB, leaving about 2 GB
  of the card's 23.9 for working memory. NVIDIA's "RTX 5090" row means the 32 GB desktop
  card. vLLM would also need WSL2 and a separate Python 3.13 environment, because NeMo
  will not install on 3.14 (`CLAUDE.md`).
- **Possibly with GGUF through NeMo-Speech.cpp.** AtomicChat's GGUF builds [12]: a 4-bit
  decoder (AD-NVFP4 or AD-IQ4_NL) is 19.68 GB, and every decoder needs a 1.67 GB encoder.
  That is 21.4 GB, again tight. The 2-bit AD-Q2_0_L (15.55 GB, "for 24 GB Macs") leaves
  about 6.5 GB. Their 16 GB setting holds about 7 minutes of audio per request, so 24 GB
  would mean chunks of a few minutes, like the 280-second chunks Qwen3 already uses
  (estimate).
- **Quality cost, as AtomicChat measured it:** every decoder from 15.55 GB up is
  "within ±0.18 points of BF16" on English, German, French and Spanish (LibriSpeech and
  MLS, 6.7 hours, on an A100). That is clean read speech, not crosstalk, so it may not
  hold on court audio. The results would also no longer be the reference model.
- **Windows:** the card says GGML runs on native Windows. NeMo-Speech.cpp v0.1.0 shipped
  Windows x64 builds [10]. Whether v0.3.0, the first with this model, has a Windows CUDA
  build was not confirmed.
- **Speed (estimate):** 10-40x real time, so 626 hours would take about 16-63 hours of
  laptop time. That is roughly the size of the earlier overnight queues, at no cost but
  electricity, on the 330 W charger.
- **Not now:** the Qwen judge is on the card, and Ollama holds about 21 GB while loaded.
  Nothing has been tested on a 24 GB card by anyone.

**Hosted APIs.**

- **DeepInfra:** $0.00200 a minute ($0.12 an audio hour), BF16, recordings up to an hour,
  word timestamps, a custom instruction field (verbatim works), diarisation, "zero
  retention" [8]. Needs an account and an API key, which is Noah's decision.
- **OpenRouter:** Prime Intellect at $0.000017 a second ($0.061 an hour) and DeepInfra at
  $0.000033 ($0.119) [9]. Word timestamps "when the routed provider supports them". It
  doesn't say which precision Prime Intellect serves. File size limit not stated.
- **Together AI** lists "Nemotron 3.5 ASR", but that is the different 0.6B streaming
  model, not this one [13].
- **NVIDIA NIM** on NGC: the fastest route NVIDIA describes, but under separate terms [14].

## Open questions

| Question | How to settle it |
|---|---|
| Real speed on hour-long arguments with word times on | The pilot, timed |
| Best chunk length for this model (a full hour, or shorter pieces) | The pilot: try two lengths on the same arguments, as `chunk_sweep.py` does |
| Does a 4-bit or 2-bit GGUF fit and run on the 24 GB laptop, and how fast | One test after the Qwen judge finishes |
| Does the quantised model lose accuracy on crosstalk | Score the same 5 arguments in BF16 (RunPod) and GGUF (laptop) |
| Is there a Windows CUDA build of NeMo-Speech.cpp v0.3.0 | Its releases page |

## Sources

1. NVIDIA, model card, NVIDIA-Nemotron-3.5-Transcribe-30B-A4B: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B
2. File listings (sizes): https://huggingface.co/api/models/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B/tree/main, https://huggingface.co/api/models/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-FP8/tree/main, https://huggingface.co/api/models/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-NVFP4/tree/main
3. RunPod pricing: https://www.runpod.io/pricing
4. RunPod docs, Pod pricing: https://docs.runpod.io/pods/pricing; Pod overview: https://docs.runpod.io/pods/overview
5. RunPod docs, Serverless pricing: https://docs.runpod.io/serverless/pricing
6. Spot pods, from a mirror of a RunPod docs pull request (not RunPod's current pages): https://github.kakarurec.workers.dev/runpod/docs/pull/626/files/8e5aebdb3740725f1f0d080d1f112ba8267e20ee
7. Secondary guide (memory per precision, audio length setting): https://aicybr.com/blog/nvidia-nemotron-3-5-transcribe-local-speech-diarization-guide
8. DeepInfra, model page: https://deepinfra.com/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B
9. OpenRouter, model page: https://openrouter.ai/nvidia/nemotron-3.5-transcribe
10. NeMo-Speech.cpp releases: https://github.com/NVIDIA/NeMo-Speech.cpp/releases (v0.1.0: https://github.com/NVIDIA/NeMo-Speech.cpp/releases/tag/v0.1.0); NGC container: https://catalog.ngc.nvidia.com/orgs/nvidia/-/containers/nemo-speech.cpp
11. OpenMDW License 1.1: https://openmdw.ai/license/1-1/
12. AtomicChat GGUF builds: https://huggingface.co/AtomicChat/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-GGUF; write-up: https://hermes-ai.net/news/atomicchat-makes-nvidia-s-nemotron-3-5-transcribe-run-on-consumer-gpus/
13. Together AI (the 0.6B streaming model): https://together.ai/models/nvidia-nemotron-35-asr
14. NVIDIA NIM on NGC: https://catalog.ngc.nvidia.com/orgs/nim/nvidia/containers/nemotron-transcribe/-

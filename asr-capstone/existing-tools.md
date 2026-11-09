# Existing tools for "bring your own audio and transcript" (checked 7 November 2026)

The question: is there already a tool where a non-expert brings their own audio and their
own "source of truth" transcript, runs several local speech engines over it, and gets word
error rates, error categories and a way to listen to each error? If so, `app-roadmap.md`
phases 1-8 would be reinventing it.

Short answer: **every piece exists somewhere, but nothing puts them together.** Scoring,
alignment, normalising and a "listen to the utterance" viewer are all solved and free to
reuse. What no tool does is take a long recording plus a court-style transcript, run
today's open engines over it on your own machine, and show a non-expert the errors that
change meaning, each one playable.

Searched the web on 7 November 2026. Anything marked **(unverified)** I could not confirm
from the project's own page.

## Comparison table

Columns: **Local** = runs on your machine. **BYO** = takes your own audio and your own
reference. **Engines** = runs several engines itself (not just scores files you made).
**Beyond WER** = error categories past substitution/deletion/insertion. **Play** = audio
playback tied to errors.

| Tool | What it is | Local | BYO | Engines | Beyond WER | Play | Licence | Maintained |
|---|---|---|---|---|---|---|---|---|
| jiwer | Python WER/CER library, text alignment printout | yes | text only | no | no | no | Apache-2.0 | yes, 4.0.0 June 2025 |
| whisper-normalizer | The OpenAI/Whisper normaliser as a package | yes | text only | no | no | no | MIT (unverified) | yes, updated Oct 2026 |
| HF `evaluate` (wer) | Wrapper around jiwer | yes | text only | no | no | no | Apache-2.0 | slowing; HF points LLM users to LightEval |
| Rev fstalign | WER and alignment with synonyms, punctuation and case WER, entity-class WER, speaker-switch WER, side-by-side file | yes (Docker/CMake; Windows not stated) | text only | no | some (entity classes, punctuation, case) | no | Apache-2.0 | yes, updated Nov 2026 |
| NIST SCTK / sclite | The classic scorer, detailed reports | yes (Docker) | text only | no | no | no | public domain (unverified) | slow but alive |
| MeetEval + meeteval-viz | Meeting WER variants; HTML alignment viewer, several systems side by side | yes | text (STM/CTM) | no | no | not mentioned | MIT | yes |
| error-align / corti-canal (Corti) | Better alignment (one word to many); `canal report` makes an HTML word-by-word report from a CSV | yes | text only | no | no | no | not checked | beta (0.1.0b) |
| Speechmatics `sm-metrics` | WER with a `--diff` view | yes | text only | no | no | no | MIT | package deprecated, bug fixes only to end of 2025 |
| EBU BenchmarkSTT | WER, diff counts, word diffs, for non-academic users | yes | text only | no | no | no | MIT | last activity 2024 |
| ASR-NL-benchmark | Dutch: sclite wrapper with a small local web page | yes (Docker) | text (STM/CTM) | no | spelling variants only | no | in repo, not read | unclear |
| Open ASR Leaderboard code (HF) | One `run_eval.py` per model family (incl. NeMo, Qwen, Granite), shared normaliser, long-form chunk-then-join scoring | yes (GPU) | Hub datasets; own data not documented | yes, many | no | no | Apache-2.0 | yes, July 2026 |
| Picovoice speech-to-text-benchmark | WER, latency, cost for cloud APIs, Whisper, Picovoice | yes / cloud | fixed public sets | yes | no | no | Apache-2.0 | yes |
| Argmax OpenBench | Diarization and transcription benchmark; folder of `audio/` + `reference/` | yes / cloud | **yes** | yes (mostly cloud, plus WhisperX, own wrappers) | DER/JER, no error types | no | MIT | yes |
| Ryfter/asr-bench | CLI: local Whisper sizes (faster-whisper, WhisperX) on **your own audio** and reference; markdown report; hallucination flag | yes (Windows, PowerShell, 5090 in its example) | **yes** (txt/SRT/VTT) | Whisper only; Canary via NIM untested | S/D/I plus a repeat/compression hallucination check | no | MIT | active, 0 stars |
| AssemblyAI huggingface-benchmarking | Runs 6 cloud vendors on HF datasets | no | own data needs code edits | yes (cloud) | no | no | not stated | small (6 commits) |
| pipecat stt-benchmark | "Semantic WER": an LLM judge (Claude) counts only meaning errors (names, numbers, negations) | partly | not documented | cloud vendors | **yes, meaning vs formatting** | no | BSD-2 | yes |
| NVIDIA NeMo Speech Data Explorer + Comparison Tool | Local Dash web app: table of utterances, WER/CER, highlighted diff, waveform and **playback per utterance**; comparison tool for **two** models | yes | **yes**, via a JSON manifest of short utterances | no (NeMo's own script fills `pred_text`) | word accuracy table, no error types | per utterance, not per error | Apache-2.0 (NeMo's) | in current NeMo docs; activity (unverified) |
| NeMo asr_evaluator | Runs a NeMo model on a manifest, WER grouped by metadata (gender, length) | yes | manifest | NeMo models only | no | no | Apache-2.0 | 2023 code (unverified now) |
| asrmetrics (Imperial Global Singapore) | Flask dashboard: upload audio + reference + hypothesis, WER, confusion of common substitutions, segment playback | yes | **yes** | no | substitution confusions | per segment | none stated | 0 stars |
| momaoalo/ASR-Evaluation | Local Flask workbench (Arabic/English), scoring views, saved runs, HTML/CSV export; can call 2 cloud APIs | yes | **yes** | 2 cloud | no | not mentioned | "no reuse licence granted" | active Oct 2026 |
| HF Spaces (e.g. Devion333/compare-ASR-models, avtnshm Indic ASR comparison) | Gradio: upload a clip, tick models, paste a reference, get WER | cloud (HF) | **yes**, short clips | yes, small HF models | no | the clip only | varies | hobby |
| distil-whisper/hallucination-analysis Space | WER, insertion error rate, repeated 5-grams, coloured diff beside the audio player | cloud (HF) | no (TED-LIUM, precomputed) | 2 Whisper models | **insertions/repeats as hallucination** | per sample | not stated | demo |
| CorentinJ/transcription-diff | Runs Whisper, diffs against the expected text | yes | yes, up to 30 s | Whisper only | no | no | MIT | small |
| Label Studio | General labelling tool; ASR templates (pick the best hypothesis, correct a transcript with audio) | yes | yes | no | only what you define | yes | Apache-2.0 | yes |
| Oriserve/ASR_arena Space | "Speech To Text Arena" | cloud | (unverified) | (unverified) | (unverified) | (unverified) | - | - |
| Artificial Analysis STT leaderboard | Ranks vendors on AA-WER (own data, lowercased, fillers removed, chunk-then-join) | no | no | yes | no | no | proprietary | yes |

No speech-to-text arena with blind human votes turned up. The arenas found (TTS Arena,
Artificial Analysis Speech Arena, Scale's Voice Showdown) are for speech synthesis or voice
agents.

## Research on errors beyond WER

- **Atwany et al. 2025**, "Lost in Transcription, Found in Distribution Shift" (Findings of
  ACL 2025). Hallucination Error Rate (HER): an LLM (GPT-4o mini) labels each error as
  hallucination or not. 20 models, includes legal and medical shift. No code release found.
- **Koudounas et al. 2025**, "Hallucination Benchmark for Speech Foundation Models"
  (SHALLOW, arXiv 2510.16567, under review). Four text-only scores: lexical fabrication,
  phonetic fabrication (Metaphone distances), morphological error (grammar, parse),
  semantic error (embeddings, NLI contradiction). They say the code and a synthetic set are
  released; I found no link **(unverified)**.
- **LASER** (Parulekar and Jyothi, EMNLP 2025). An LLM rubric for ASR scoring, aimed at
  Indian languages. Code on GitHub.
- **Koenecke et al. 2024**, "Careless Whisper" (FAccT). A harm taxonomy for Whisper
  hallucinations. No tool.
- Court and legal: a 2024 study of French legal ASR against court reporters' transcripts
  (arXiv 2408.11940) used WER and a phonetic distance. Vendors (Speechmatics, Verbit, Rev)
  publish claims, not tools. The Speech-to-Text Institute (an industry non-profit) turned up
  only in a Verbit announcement. **No open tool for court-transcript QA was found**, and no
  parser for deposition ASCII exports (page and line), which matches what `app-roadmap.md`
  already says.

## Verdict

**Already exists. Reuse it, do not rebuild it:**

- Scoring and alignment: jiwer (already used) and whisper-normalizer (already the benchmark
  rule). fstalign already does punctuation-aware and case-aware WER, which is close to the
  verbatim rule, so it is worth citing as prior art for that rule.
- A multi-engine alignment viewer: meeteval-viz makes standalone HTML pages showing several
  systems against one reference. It could be borrowed from, or cited.
- An utterance browser with playback: NeMo Speech Data Explorer. If someone only wants to
  click through utterances and listen, writing a NeMo manifest from the run folders would
  give them that for free.
- Running many engines: the Open ASR Leaderboard code has a runner per model family,
  including chunk-then-join for long recordings. Worth comparing with the pipeline's
  chunking and citing.
- Hallucination and meaning-error ideas: HER, SHALLOW and pipecat's semantic WER all
  separate "meaning changed" from "formatting differed". The project's LLM judge belongs in
  that line of work and should cite them.

**Genuinely missing (this is the contribution):**

1. One local tool that does all of it in a row for a non-expert: bring a long recording and
   a real-world transcript, pick several current open engines (Qwen3-ASR, Voxtral, Granite,
   Canary, Parakeet, Whisper), chunk, score, find errors, and listen. The closest tools each
   do one slice. asr-bench takes your own audio but runs only Whisper and has no viewer. NeMo
   SDE has the viewer but needs short utterances, a NeMo manifest and someone to run the
   models first. OpenBench takes an `audio/` + `reference/` folder but is about diarization
   and cloud APIs.
2. Named, meaning-level error types found by rule, such as negation flips, invented words,
   grammar edits and skipped speech, shown as a list you can play. The research defines
   hallucination scores, but none of them ships a tool that points to the spot in the audio.
3. Two scoring rules side by side (benchmark against verbatim) on the same run.
4. Court formats: reading a deposition ASCII transcript with page and line, and a reference
   check before hours of GPU time. Nothing found.

Honest framing for the paper: the new part is the integration, the error-type finder and
the court angle, not the WER maths. Most of the tool is glue around existing libraries. That
is a fair capstone contribution as long as the paper says so and cites the tools above.

## Sources

- jiwer: https://pypi.org/project/jiwer/ and https://jitsi.github.io/jiwer/usage
- whisper-normalizer: https://github.com/kurianbenoy/whisper_normalizer
- Hugging Face evaluate: https://github.com/huggingface/evaluate
- fstalign: https://github.com/revdotcom/fstalign and https://github.com/revdotcom/fstalign/blob/develop/docs/Usage.md
- NIST SCTK: https://github.com/usnistgov/SCTK
- MeetEval: https://github.com/fgnt/meeteval ; viewer demo https://fgnt.github.io/meeteval_viz
- error-align: https://pypi.org/project/error-align/ ; paper https://arxiv.org/abs/2509.24478
- corti-canal: https://pypi.org/project/corti-canal/
- Speechmatics sm-metrics: https://docs.speechmatics.com/speech-to-text/accuracy-benchmarking and https://github.com/speechmatics/speechmatics-python
- EBU BenchmarkSTT: https://github.com/ebu/benchmarkstt
- ASR-NL-benchmark: https://github.com/opensource-spraakherkenning-nl/ASR_NL_benchmark
- Open ASR Leaderboard code: https://github.com/huggingface/open_asr_leaderboard ; paper https://arxiv.org/abs/2510.06961
- Picovoice benchmark: https://github.com/Picovoice/speech-to-text-benchmark
- Argmax OpenBench: https://github.com/argmaxinc/OpenBench
- asr-bench: https://github.com/Ryfter/asr-bench
- AssemblyAI benchmarking: https://github.com/AssemblyAI-Solutions/huggingface-benchmarking
- pipecat stt-benchmark: https://github.com/pipecat-ai/stt-benchmark
- SpeechLoop (old, 2022): https://github.com/robmsmt/SpeechLoop
- GitHub topic list: https://github.com/topics/asr-benchmark
- NeMo Speech Data Explorer: https://docs.nvidia.com/nemo/speech/latest/tools/speech_data_explorer.html
- NeMo Comparison Tool: https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/tools/comparison_tool.html
- NeMo asr_evaluator (2023 PR): https://github.com/NVIDIA/NeMo/pull/5728
- asrmetrics: https://github.com/ImperialGlobalSingapore/asrmetrics
- ASR-Evaluation: https://github.com/momaoalo/ASR-Evaluation
- HF Spaces: https://huggingface.co/spaces/Devion333/compare-ASR-models , https://avtnshm-indic-asr-comparison.hf.space , https://huggingface.co/spaces/distil-whisper/hallucination-analysis , https://huggingface.co/spaces/Oriserve/ASR_arena
- transcription-diff: https://github.com/CorentinJ/transcription-diff
- Label Studio ASR template: https://labelstud.io/templates/asr_hypotheses.html
- Artificial Analysis method: https://artificialanalysis.ai/methodology/speech-to-text
- Atwany et al. 2025: https://aclanthology.org/2025.findings-acl.1190 ; https://arxiv.org/abs/2502.12414
- Koudounas et al. 2025 (SHALLOW): https://arxiv.org/abs/2510.16567
- LASER: https://arxiv.org/abs/2510.07437 ; code https://github.com/Amparulekar/LASER-metric
- Careless Whisper: https://arxiv.org/abs/2402.08021
- French legal ASR study: https://arxiv.org/abs/2408.11940

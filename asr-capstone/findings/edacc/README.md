# EdAcc results (16 October 2026)

Five engines on the test split of EdAcc, the Edinburgh International Accents of English
Corpus: 40 video-call conversations between friends, 18.2 hours, 157,504 reference words.
Many of the speakers have English as a second language. The audio, the runs and the full
transcriptions are on the 5090 laptop at `D:/asr-corpora/edacc/`, outside the repository.

**Only the benchmark rule (`wer_standard`) is fair here.** EdAcc's reference is upper case
with no punctuation and numbers spelt out. The verbatim rule charges every capital and
comma, so it reads about 96% for every engine and means nothing. The commercial engine
scores 21% on it only because its output is in the same style as the reference.

**With the October fixes, the figures to quote** (`benchmark.csv`, from
`tools/benchmark_tables.py`; the table below is the older one, without them): test split
Qwen3 11.70%, Parakeet 13.41%, Whisper 14.54%, Canary 16.50%, commercial 17.46%, Granite
18.48%; all 76 conversations Qwen3 11.22%, Parakeet 12.82%, Whisper 13.94%, Canary 15.69%,
Granite 17.85%.

| Engine | Error rate | Swapped | Dropped | Added | Speed (x real time) | Hours for 18.2 h of audio |
|---|---|---|---|---|---|---|
| Qwen3 | **11.8%** | 4.4% | 5.3% | 2.2% | 6.9 | 2.6 |
| Parakeet | 13.5% | 5.2% | 6.5% | 1.9% | 32.9 | 0.6 |
| Whisper | 14.7% | 4.4% | 8.5% | 1.8% | 20.4 | 0.9 |
| Canary | 16.7% | 5.5% | 9.5% | 1.7% | 20.4 | 0.9 |
| Commercial engine (shipped with EdAcc) | 18.0% | 7.3% | 8.9% | 1.8% | - | - |
| Granite | 18.6% | 5.4% | 11.6% | 1.7% | 4.9 | 3.7 |

On the Supreme Court, Qwen3 scored 4.4% on the same rule, so this speech gives it about
two and a half times as many errors. Qwen3 beat the commercial engine on every one of the
40 conversations. Qwen3 stays first and Granite last, as on the Supreme Court;
Parakeet moves up from third of these five there to second here, ahead of Whisper and Canary.

Parakeet's row is from `run-edacc-parakeet-reread` (23 October): its decoder can stall
after a full stop, and every blank stretch is now read again (`../parakeet-stall/`).
Before that it scored 14.0%, with 7.1% dropped. Its speed is the first pass's. The
`crowd/` tables below still use the old Parakeet run.

Voxtral and Granite Plus were left out on purpose. Granite Plus takes about 11 hours here,
and neither did well enough on the Supreme Court to be worth it. About a dozen
conversations of Voxtral were done before it was stopped; they are kept in
`D:/asr-corpora/edacc/partial-runs/` in case it is backfilled.

## What the five heard together (`crowd/`)

- **6.1% of the reference words were written by none of the five.** No way of combining
  these engines can recover them. Some will be the transcriber's mistakes, not the
  engines'.
- **They make the same mistakes.** When Qwen3 misses a word, each of the others misses
  it too 80-84% of the time, a little more than on the Supreme Court (76-78% for Parakeet
  and Canary).
- **A vote does not help.** With Qwen3 as the base it scores 12.2%, worse than Qwen3
  alone, because the weaker engines drop words and outvote it. With four engines (before
  Granite) the vote was 11.4%, a little better than Qwen3.

## Files

| File | What it holds | Made by |
|---|---|---|
| `engines.csv` | one row per engine: error rate under each rule, swapped/dropped/added, hours, speed | `tools/summarise_runs.py` |
| `per-recording.csv` | the same per engine and conversation | `tools/summarise_runs.py` |
| `crowd/` | the comparison across engines; the files are described under `crowd/` in `../README.md` | `tools/crowd.py --runs-dir D:/asr-corpora/edacc/runs` |

To rebuild `engines.csv` with the commercial engine's row:

    python tools/summarise_runs.py --runs-dir D:/asr-corpora/edacc/runs --out findings/edacc \
        --ctm company=D:/asr-corpora/edacc/unpacked/edacc_v1.0/test/company.ctm \
        --config pipeline/config/corpora/edacc.yaml

Speed includes loading each recording and scoring it, not only transcribing. The speaker
labels EdAcc gives (first or second language) are in the corpus index, not here; the
README that comes with EdAcc says they may not be reliable.

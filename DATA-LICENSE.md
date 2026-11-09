# What licence covers what

The code is under the MIT licence (`LICENSE`). Everything else in this repository is
covered by the table below. Where a file mixes data sets (many CSVs under
`asr-capstone/findings/` have a `corpus` column), each row carries the licence of its own
data set: the rows are collected side by side, not merged into one work.

| Material | Licence |
|---|---|
| Code (`asr-capstone/tools/`, the pipeline, the website's scripts) | MIT |
| My own text, charts, tables and scores (notes, findings READMEs, figures, the paper) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), Noah Collin, except where noted |
| Supreme Court of the United States audio and transcripts, and engine transcripts of them | No copyright claimed by the Court; the audio is a federal work (17 U.S.C. § 105). Engine text and my labels: CC BY 4.0 |
| EdAcc (Sanabria et al. 2023) reference text, clips and engine transcripts | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) ([source](https://datashare.ed.ac.uk/handle/10283/8983)) |
| Earnings-22 (Del Rio et al. 2022, Rev) reference text and engine transcripts | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), covering "the transcripts and associated text files" ([source](https://github.com/revdotcom/speech-datasets/blob/main/earnings22/LICENSE.md)). No Earnings-22 audio is included |
| CORAAL (Kendall & Farrington 2023) reference text, clips, engine transcripts, and anything adapted from them | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): no commercial use ([source](https://oraal.github.io/coraal)) |

Rows with `corpus` = `coraal` stay under CC BY-NC-SA 4.0 wherever they appear; they may not
be reused commercially, even when the rest of the same file could be.

**Speech engines.** The transcripts were made with Whisper large-v3 (OpenAI, MIT /
Apache-2.0), Qwen3-ASR 1.7B (Alibaba, Apache-2.0), Voxtral Mini 3B (Mistral, Apache-2.0),
Canary 1B v2 and Parakeet TDT 0.6B v3 (NVIDIA, CC BY 4.0), and Granite Speech 4.1 2B and
2B Plus (IBM, Apache-2.0). None of these licences limits publishing the output.

**Third-party code used, not included.** The pipeline reads PDFs with PyMuPDF, which is
AGPL-3.0. It is installed as a dependency, not distributed here, and the MIT licence above
covers only this repository's own code.

Details and sources: `asr-capstone/going-public.md`, section 1.

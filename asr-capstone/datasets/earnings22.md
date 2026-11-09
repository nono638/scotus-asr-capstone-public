# Earnings-22: scouting notes

Written 18 October 2026. Nothing was downloaded except READMEs, the metadata table, the
repository's file list, and one call's reference files (about 1 MB of text) to see the
format. "My count" means I worked it out from those files. The sources are listed at the
bottom, and every fact points to one by number, like [1].

**In short:** 125 earnings calls, 119 hours, companies from 27 countries. Rev's own paid
transcribers made the references, **verbatim**: um and uh, stutters, cut-off words,
repeats, punctuation and capitals are all kept. Ten of the calls also have a second,
cleaned-up reference. As far as I know, no other public corpus has two references for the
same calls, and that fits the project's benchmark-against-verbatim argument well. Audio
is 1.9 GB of MP3. The transcripts are CC BY-SA 4.0. The audio's licence is less clear (see
section 2).

## 1. Size and where it lives

| | Value | Source |
|--|--|--|
| Calls | 125 | [1] [3] |
| Hours | 119 (118.9 by summing `metadata.csv`) | [1] [3], my count from [4] |
| Countries | 27, by where the company is based | [3] |
| Regions | 7 "language regions" (table below) | [3] |
| Call length | 15 min to 2 h 3 min, median about 59 min | my count from [4] |
| Speakers | Not published. There is no speaker table, only speaker numbers within each call. The one call I opened (4485192) has 10 | [5], my count |
| Audio download | 1.91 GB, 125 MP3s (largest 114 MB) | my count from the Git LFS pointer files [2] |
| Transcript download | About 82 MB of text: plain references 20 MB, force-aligned references 38 MB, normalisation files 23 MB | my count from [2] |

**Regions.** Accent is assumed from the company's home country, not checked by ear.
The paper says so plainly [3].

| Region | Countries | Calls | Hours |
|--|--|--|--|
| Spanish/Portuguese | Argentina, Brazil, Chile, Colombia, Portugal, Spain | 31 | 28.9 |
| Asian | China, India, Indonesia, Japan, South Korea, Turkey | 28 | 25.3 |
| English | Australia, Canada, South Africa, UK, US | 26 | 22.9 |
| Other Romance | France, Greece, Italy | 13 | 15.6 |
| Germanic | Denmark, Germany, Sweden | 12 | 13.5 |
| Slavic | Poland, Russia | 10 | 7.7 |
| African | Ghana, Nigeria | 5 | 5.1 |

Countries and hours are from the paper's Tables 1 and 2 [3]. The calls column matches
`metadata.csv` [4].

**Where it lives.** The original release is on GitHub at `revdotcom/speech-datasets`, in
the `earnings22/` folder [1]. The MP3s are stored in Git LFS, so you need `git lfs pull`
after a sparse checkout of just that folder [6]. Several Hugging Face copies exist, and
they differ:

| Copy | What it is | Size | Source |
|--|--|--|--|
| GitHub `revdotcom/speech-datasets` | The original: whole calls as MP3, NLP references, normalisation files, metadata | 1.9 GB audio + about 82 MB text | [1] [2] |
| HF `distil-whisper/earnings22`, config `full` | All 125 whole calls, with the metadata columns and one plain-text `transcription` per call | 1.89 GB | [7] [8] |
| HF `distil-whisper/earnings22`, config `chunked` | 57,391 clips of up to 20 s, cut at punctuation using Wav2Vec2 timings. The text keeps capitals, punctuation, "uh" and `<inaudible>` | 24 GB (decoded 16 kHz audio) | [7] [8], rows seen in [9] |
| HF `revdotcom/earnings22` | Only a loading script (6.9 kB). No dataset card, and the viewer is off | — | [10] |
| HF `esb/datasets`, config `earnings22` | ESB benchmark version: segmented and split into train 105 h, dev 5 h and test 5 h. Labelled "punctuated & cased", with "junk tokens" removed | — | [11] |
| HF `hf-audio/open-asr-leaderboard`, config `earnings22` | The leaderboard's old short-form test set: 2,741 segments, 5.4 h, from just **6 calls** (4470290 Argentina, 4479741 Denmark, 4432298 and 4450488 Poland, 4483338 Sweden, 4485244 US). Verbatim-style text with "uh", "um" and cut-off words | 1.1 GB | my count from [12] |
| HF `ArtificialAnalysis/Earnings22-Cleaned-AA` | 6 calls, about 115 min in all, with references re-checked by hand. They say model error rates dropped 5.6 points on average after the fixes. Labelled Apache-2.0, which doesn't match the CC BY-SA source | — | [13] |
| HF `hf-audio/asr-leaderboard-longform`, config `earnings22` | All 125 whole calls, used for the leaderboard's long-form table | 13.3 GB | [14] |

The GitHub copy is the only one with the NLP files: speaker numbers, entity tags, the
normalisation choices, and the separate verbatim and cleaned-up references for the ten
calls in Subset 10. The Hugging Face copies flatten all that into a single text string.

## 2. Licence

- **Transcripts: CC BY-SA 4.0.** The `LICENSE.md` text says it covers "the transcripts and
  associated text files that are used for alignment" [15]. You can republish them, with
  credit, under the same licence.
- **Audio: not clearly licensed.** The licence file only covers the text. The paper says
  most calls came from seekingalpha.com and a few from company websites, and it cites a
  fair-use court case (*Swatch v. Bloomberg*) for earnings calls [3]. The Hugging Face
  copies label the whole dataset CC BY-SA 4.0 [11] [14]. Rev itself never says so for
  the audio.
- **The 2023 journal article** is CC BY-NC-ND 4.0, but that covers the paper, not the
  data [16].

**Short clips on a private web page:** probably fine. A few seconds of a public earnings
call, credited to Rev's Earnings-22 and the company, is a small fair-use quote, and the
page is private. But it is weaker than the Supreme Court audio, which is public domain.
The website plan says to leave a clip out when the licence is unclear. By that rule,
Earnings-22 clips need Noah's decision first (uncertain; I am not a lawyer).

## 3. Layout and audio format

The repository layout, from [2]:

```
earnings22/
  LICENSE.md  README.md  metadata.csv
  media/<id>.mp3                               125 calls (Git LFS)
  transcripts/
    nlp_references/<id>.nlp                    the verbatim references, no timings
    force_aligned_nlp_references/<id>.aligned.nlp   same, with word times from forced alignment
    normalizations/<id>.norm.json              spoken-form choices for numbers etc.
    README.md, images/e22_werbyregion.png      the paper's results
  subset10/
    README.md  LICENSE.md
    media/            links to ../../media/<id>.mp3
    verbatim_transcripts/{nlp_references,normalizations}/   links to the main files
    nonverbatim_transcripts/{nlp_references,normalizations}/ a NEW cleaned-up reference
```

- **File names** are mostly 7-digit numbers (like `4485192`). A few Ghana/Nigeria calls
  have long names instead, like `MP3-A` or `mtngh_fy18_call_audio_04032019` [2].
- **`metadata.csv` columns** [4]: File ID, Ticker Symbol, Country by Ticker, UN Defined
  (UN region), Major Dialect Family, Language Family + Area Based (the paper's 7 regions),
  File Length (seconds), Sampling Rate (Hz).
- **Audio:** MP3, one file per call. The sample rates vary: 24 kHz (64 calls),
  16 kHz (29), 22.05 kHz (17), 44.1 kHz (7), 11.025 kHz (5), and one each at 8, 32 and
  48 kHz [4]. The 8 and 11 kHz files are phone quality. Everything has to be resampled to
  16 kHz anyway.
- **Subset 10** has ten calls chosen at random, 11.1 hours in all [17], my count from [4]:
  4453225 and 4469088 (South Africa), 4470684 and 4483937 (UK), 4474506 and 4485192
  (US), 4479944 and 4482613 (India), 4481952 and 4482383 (Australia). In `subset10/` the
  media and verbatim folders are git symlinks (mode 120000) to the main files, so the
  verbatim reference *is* the main reference [2]. None of these ten calls is among the
  leaderboard's six.
- **Oddity:** `force_aligned_nlp_references/4453076.aligned.nlp` is only 2.9 KB, against
  80–700 KB for the others, while its plain `.nlp` is a normal 119 KB. The aligned copy
  looks truncated [2].

## 4. The reference format (NLP files)

One token per line, fields split by `|`, with a header row. The README documents eight
columns, `token|speaker|ts|endTs|punctuation|case|tags|wer_tags` [1] [18]. **The files I
opened differ from that.** They have `token|speaker|ts|endTs|punctuation|prepunctuation|case|tags`,
with no `wer_tags` column. The aligned version adds `oldTs|oldEndTs|ali_comment` [5].
Here is the start of 4485192.nlp [5]:

```
token|speaker|ts|endTs|punctuation|prepunctuation|case|tags
Good|0|||||UC|[]
morning|0|||||LC|[]
...
Year|0|||||UC|[]
2022|0|||||N/A|['0:YEAR']
Earnings|0|||||UC|[]
Conference|0|||||UC|[]
Call|0|||.||UC|[]
```

- **token:** a word with its capitals already applied. Hyphenated words stay one token.
  A cut-off word ends in "-" (`question-`, `A-`). Tags look like `<inaudible>` [5].
- **speaker:** a number, unique only within the call. No names (Earnings-21 has names,
  Earnings-22 does not) [5] [19].
- **ts / endTs:** **empty** in `nlp_references`, filled in the `force_aligned` copy. In
  call 4485192, 411 of 10,147 aligned tokens (4%) have no time, marked `del`. The aligned
  file also has more tokens than the plain one (10,147 against 9,830), and I don't know
  why. Rev doesn't say how the alignment was done; the `sub(edgewell)` comments suggest it
  was against an ASR transcript (uncertain) [5].
- **punctuation / prepunctuation:** the mark after (or before) the token. In 4485192 these
  are `,` (1,113), `.` (431), `?` (35) and `…` (5) [5].
- **case:** UC / LC / CA / MC, as in the README [1]. Numbers show `N/A`. This column
  duplicates the token's own capitals.
- **tags:** entity labels such as `['0:YEAR']`. The numeric ID links the token to an entry
  in `<id>.norm.json`, which lists spoken forms with probabilities. For "2022", for
  example: "twenty twenty two" (0.83), "two thousand twenty two" (0.15), and so on [5].
  The classes in 4485192 are CONTRACTION 243, CARDINAL 78, ABBREVIATION 49, PERCENT 47,
  MONEY 45, FALLBACK 42, YEAR 11, ALPHANUMERIC 11, WEBSITE 2, ORDINAL 1 (my count) [5].
  FALLBACK marks cut-off words and odd symbols [19].

**What the reference keeps:**

| Feature | Kept? | Evidence |
|--|--|--|
| Punctuation | Yes, after each token | [5] |
| Capitals | Yes, in the token itself | [5] |
| um / uh | Yes. 79 "um" and 71 "uh" in a 62-minute call. The cleaned-up version of the same call has none | my count, [5] |
| Cut-off words / false starts | Yes, as `word-` (19 in 4485192). The paper uses "ends in -" to define fragments | [3] [5] |
| Repeats ("the the") | Yes. 188 immediate repeats in the verbatim version, against 6 in the cleaned-up one | my count, [5] |
| Trailing off | `…` as punctuation | [5] |
| Non-speech noises | Mostly removed ("atmospheric information" was stripped [3]), but `<laugh>` survives | [3] [5] |

**Could it support the verbatim rule? Yes, with one caveat.** Everything the verbatim
rule counts is there: punctuation, capitals and disfluencies. Rev's own scorer can even
switch on case and punctuation scoring (`--use-case`, `--use-punctuation`) [20]. The
caveat is that it is *Rev's* verbatim style, not a court reporter's [21]. Two examples:
there is no "--" for an interruption, and small numbers are written as words while
larger ones use digits. A model's "error" under the verbatim rule will partly be a
difference in house style. That holds for any non-court reference, though. And Subset 10
can *measure* how much a style choice moves the score, because it has two human
references for the same audio [17] [22].

## 5. Conventions

From Rev's style guide (the paper cites v4.0.1 [3]; the copy I read is v4.0.2 [21]) and
from what I saw in the files:

- **Unintelligible:** Rev's editor uses `[inaudible 00:00:00]`. In Earnings-22 it is the
  token `<inaudible>`. The angle brackets were added in the August 2024 update [6] [21].
  There were 4 in call 4485192 [5].
- **Crosstalk:** the token `<crosstalk>` (2 in 4485192) [5] [6]. It replaces the
  overlapping words rather than transcribing both speakers.
- **Numbers:** under 10 written as words, 10 and above as digits. Percentages use the
  sign (`2.5%`), and money looks like `$5 million` (written as two tokens, `$5` and
  `million`) [21] [5]. Years are digits. `10-K` and `COVID-19` stay as written, tagged
  ALPHANUMERIC [5].
- **Fillers:** "um" and "uh" in verbatim. Interjections like "Mm-hmm" use Rev's fixed
  spellings [21].
- **Stutters:** `m- m- movies` style, a hyphen with no comma after a partial word [21].
- **Laughter:** `(laughs)` in the style guide, the token `<laugh>` in the NLP files [21] [5].
- **Contractions:** written as spoken in verbatim. The CONTRACTION tag lets a scorer
  accept "we will" for "we'll" [19] [5].

## 6. How it was scored, and the published numbers

**The paper.** It used Rev's `fstalign` tool [1]. `fstalign` lines the reference up with
the hypothesis and allows several matches as correct:

- number spellings, from `norm.json`;
- synonyms like "i'm"/"i am" and "okay"/"ok";
- a cut-off word with or without its hyphen;
- `<unk>` in place of any `<tag>`.

By default it ignores case and punctuation [20]. Error rates were micro-averaged, so
long calls count for more [3]. Four commercial systems were tested, and only Rev's are
named [3] [23]:

| System | WER, all 125 calls |
|--|--|
| Rev.ai Async V2 (end-to-end) | 13.8% |
| "Provider 1" | 18.1% |
| Rev.ai Async V1 (Kaldi) | 21.0% |
| "Provider 2" | 22.8% |

The results by region are only given as a chart. English and Germanic come out best,
Asian and Other Romance worst. Compared with the English region, the gap is significant
for Asian (p = 0.004), Other Romance (p = 0.012) and Spanish/Portuguese (p = 0.035) [3].

**Subset 10, two references (McNamara et al. 2024)** [22]. These are WERs against the
verbatim (V) and cleaned-up (NV) references:

| System | V-WER | NV-WER |
|--|--|--|
| Parakeet-TDT-1.1B | 14.94 | 12.16 |
| Parakeet-CTC-1.1B | 14.70 | 12.22 |
| Canary-1B (the paper notes one file hallucinated badly, which skews it) | 14.83 | 8.26 |
| OpenAI API (probably Whisper-large-v3-based) | 13.11 | 6.41 |
| Rev.ai, verbatim setting | 7.74 | 14.57 |
| Rev.ai, non-verbatim setting | 14.06 | 5.37 |

The same audio scores roughly twice as well or badly depending on the reference style.
That is the project's argument, shown on someone else's data. (The paper's exact
normalisation is not described in what I read.)

**Open ASR Leaderboard** (results files as of October 2026) [24] [25]. All of these use
the leaderboard's text normaliser, which is based on Whisper's English one: lowercase,
no punctuation, fillers dropped [26].

| Model | Cleaned-AA, 6 calls (current column) | Old short-form, 6 calls, 5.4 h | Long-form, all 125 calls |
|--|--|--|--|
| Qwen3-ASR-1.7B | 5.84 | 9.72 | not listed |
| Qwen3-ASR-0.6B | 7.83 | 10.77 | not listed |
| Parakeet-TDT-0.6B-v3 | 5.85 | 10.77 | 14.58 |
| Parakeet-TDT-0.6B-v2 | 6.76 | 10.78 | 13.25 |
| Whisper large-v3 | 7.99 | 11.59 | 13.16 |
| Whisper large-v3-turbo | 8.09 | 11.07 | 13.10 |
| Canary-Qwen-2.5B (for reference) | 6.41 | 10.04 | 13.59 |

- The leaderboard's "Earnings22" is only 6 calls, mostly European accents, and none from
  Asia or Africa. Only the long-form table uses all 125 calls, and Qwen3-ASR isn't in it.
  Running Qwen3 on the whole corpus would fill that gap.
- (23 Oct 2026) We have now run all three on all 125 calls (`findings/earnings22/`):
  Qwen3 11.34%, Parakeet 11.79% (after its full-stop fix), Whisper 12.42%
  (`benchmark.csv`, with the October fixes; 12.05, 12.56 and 14.13 without them). That is
  our benchmark rule, not the leaderboard's normaliser, and our own
  chunking, so it is not the same measurement as the long-form column; the order is
  what to compare. Qwen3 is worst of the three on the Asian calls (19.3%) because of
  three interpreted Korean calls: it writes the Korean in Hangul, which the English-only
  reference counts as wrong, and on 4481766 a looping piece was kept. Without those
  three it is first there too (15.1% against 16.7% and 17.0%, mean per call).
- The short-form figures for Qwen3 come from the leaderboard's own runs of the `-hf`
  checkpoints [24].
- The long-form table also has a CORAAL column. Whisper large-v3 scores 18.89 there,
  Parakeet v2 17.64 and Parakeet v3 15.57 [25].
- (23 Oct 2026) The long-form Parakeet numbers probably include its full-stop stall. The
  leaderboard decodes each whole file in one pass with local attention and greedy
  decoding (`nemo_asr/run_eval_long.py`), so a decoder that gets stuck after a
  full stop is never reset. On our Earnings-22 runs, Parakeet left 3.4% of the
  audio blank that way before the fix. See `findings/parakeet-stall/`.

## 7. Earnings-21

Yes, it exists. It is the same team's earlier set, same format [19] [27].

| | Earnings-21 | Earnings-22 |
|--|--|--|
| Calls / hours | 44 / about 39 h | 125 / 119 h |
| Focus | Named entities across 9 financial sectors, calls from 2020 | Accents, 27 countries |
| Audio | 770 MB MP3 in plain git, no LFS | 1.9 GB MP3 in Git LFS |
| Speakers | `speaker-metadata.csv` with **names** | numbers only |
| Extras | RTTM files for diarisation, Eval-10 (a 10 h subset), word bias lists, outputs of 6 systems (Amazon, Google, Kaldi, Microsoft, Rev, Speechmatics) | Subset 10 with a second, non-verbatim reference |
| Licence | CC BY-SA 4.0 | CC BY-SA 4.0 (transcripts) |
| Leaderboard long-form WER: Whisper v3 / Parakeet v2 / v3 | 9.71 / 10.75 / 9.96 | 13.16 / 13.25 / 14.58 |

Sources: [19] [2] [25]. Earnings-21 is easier and mostly about entities. Earnings-22 is
the accent set. Earnings-21 got a reference fix in August 2024 [6].

## 8. Recommendation

**Yes, add it after CORAAL.** Three reasons:

1. **It is the only corpus found so far where the verbatim rule is fair.** The
   references are professional, verbatim, punctuated and capitalised [3] [5]. Subset 10
   gives two human references for the same 11 hours [17]. That lets the write-up show how
   much the reference style alone moves the score, with a source outside the project
   [22].
2. **Second-language English at scale.** 119 hours, 27 countries, and region labels
   already in the metadata [4]. It tests the EdAcc finding on far more audio.
3. **Cheap to get.** 1.9 GB of audio, and the transcripts are small and open [2] [15].

**First trial (about 11 hours).**

- Step 1: two calls with `--limit` to check the reader. Use 4485192 (US, 62 min, the one
  I examined) and 4481952 (Australia, 62 min). Both are in Subset 10.
- Step 2: all of **Subset 10** (10 calls, 11.1 h), scored against both references with
  both rules.
- One gap: Subset 10 has no strongly accented calls. It is all English-region countries
  plus India [4].
- Step 3 (optional), a short accent spread of about 2.5 h: one short call per remaining
  region. These are 4474955 (China, 15 min), 4471586 (Russia, 21 min), 4468919
  (Argentina, 20 min), 4482110 (Greece, 23 min), 4480850 (Sweden, 45 min) and
  `2020-03-0230487MTN-Ghana-2019-Annual-Results-Call` (Ghana, 51 min) [4].
- The full 119 h can go into the queue later.

**Reader work needed.** NLP is new; the project reads only STM and CTM today
(`pipeline/scotus_asr/corpora/formats.py`).

- **`read_nlp(path)`.** Read the header row and pick columns by name, because the files
  don't match the README (`prepunctuation` is there, `wer_tags` isn't).
  - Rebuild each word as prepunctuation + token + punctuation.
  - Join consecutive tokens with the same speaker into one `Turn`.
- **Timings.** The plain references have none. That's fine for whole-call scoring,
  which is how the arguments are scored now. For clips or turn times, read the
  `force_aligned` copy, but allow for missing times (`del` rows) and the broken
  4453076 file.
- **Tags.** Treat `<inaudible>`, `<crosstalk>` and `<laugh>` the way EdAcc's and SCOTUS's
  unclear-speech tags are treated. They are not words to score.
- **Numbers.** No extra work for the benchmark rule: the existing normaliser handles
  "$5 million" and "2.5%". `norm.json` could be used later to accept other spoken
  forms, but it isn't needed for the first trial.
- **A corpus class** like `edacc.py`, reading `metadata.csv` for region, country and
  length, with a `variant` setting for `verbatim` or `nonverbatim` (Subset 10 only).
- **Download.** A sparse checkout of `earnings22/` plus `git lfs pull` gets everything
  [6]. For single calls, the usual LFS address
  `https://media.githubusercontent.com/media/revdotcom/speech-datasets/main/earnings22/media/<id>.mp3`
  should work, but I haven't tested it. The audio is MP3 at mixed sample rates, so
  resample to 16 kHz as for the SCOTUS MP3s.
- **Tests.** Parse the 4485192 header and first lines shown above. Check that a
  `question-` cut-off and a `<crosstalk>` token come through as expected.

## Sources

1. Earnings-22 README: https://github.com/revdotcom/speech-datasets/blob/main/earnings22/README.md
2. Repository file list (GitHub API, sizes and modes; LFS pointer files give audio sizes): https://api.github.com/repos/revdotcom/speech-datasets/git/trees/main?recursive=1 and e.g. https://raw.githubusercontent.com/revdotcom/speech-datasets/main/earnings22/media/4453225.mp3
3. Del Rio et al. 2022, "Earnings-22: A Practical Benchmark for Accents in the Wild": https://arxiv.org/abs/2203.15591 (PDF https://arxiv.org/pdf/2203.15591)
4. metadata.csv: https://github.com/revdotcom/speech-datasets/blob/main/earnings22/metadata.csv
5. One call's files, 4485192: https://github.com/revdotcom/speech-datasets/blob/main/earnings22/transcripts/nlp_references/4485192.nlp, .../force_aligned_nlp_references/4485192.aligned.nlp, .../normalizations/4485192.norm.json, and the cleaned-up version .../subset10/nonverbatim_transcripts/nlp_references/4485192.nlp
6. Repository README (release notes, sparse checkout, Git LFS): https://github.com/revdotcom/speech-datasets/blob/main/README.md
7. distil-whisper/earnings22 card: https://huggingface.co/datasets/distil-whisper/earnings22
8. Its sizes: https://datasets-server.huggingface.co/size?dataset=distil-whisper/earnings22
9. Its first rows: https://datasets-server.huggingface.co/rows?dataset=distil-whisper/earnings22&config=chunked&split=test&offset=0&length=8
10. revdotcom/earnings22 on HF: https://huggingface.co/datasets/revdotcom/earnings22
11. ESB datasets card: https://huggingface.co/datasets/esb/datasets
12. Open ASR Leaderboard test data, earnings22 config (all 2,741 rows read through the viewer API): https://huggingface.co/datasets/hf-audio/open-asr-leaderboard and https://datasets-server.huggingface.co/rows?dataset=hf-audio/open-asr-leaderboard&config=earnings22&split=test&offset=0&length=100
13. Earnings22-Cleaned-AA card: https://huggingface.co/datasets/ArtificialAnalysis/Earnings22-Cleaned-AA
14. Long-form leaderboard data: https://huggingface.co/datasets/hf-audio/asr-leaderboard-longform
15. Earnings-22 LICENSE.md: https://github.com/revdotcom/speech-datasets/blob/main/earnings22/LICENSE.md
16. Journal version (Research in Language 21(3), 2023): https://czasopisma.uni.lodz.pl/research/article/view/21579
17. Subset 10 README: https://github.com/revdotcom/speech-datasets/blob/main/earnings22/subset10/README.md
18. fstalign NLP format: https://github.com/revdotcom/fstalign/blob/develop/docs/NLP-Format.md
19. Earnings-21 README (entity classes, Eval-10): https://github.com/revdotcom/speech-datasets/blob/main/earnings21/README.md
20. fstalign README and usage (synonyms, normalisations, --use-case, --use-punctuation): https://github.com/revdotcom/fstalign/blob/develop/README.md, https://github.com/revdotcom/fstalign/blob/develop/docs/Usage.md, https://github.com/revdotcom/fstalign/blob/develop/sample_data/synonyms.rules.txt
21. Rev Transcription Style Guide v4.0.2: https://cf-public.rev.com/styleguide/transcription/Rev+Transcription+Style+Guide+v4.0.1.pdf (v5: https://cf-public.rev.com/styleguide/transcription/Transcription+Style+Guide+v5.pdf)
22. McNamara et al. 2024, "Style-agnostic evaluation of ASR using multiple reference transcripts": https://arxiv.org/abs/2412.07937 (tables in https://arxiv.org/html/2412.07937v1)
23. Earnings-22 results README: https://github.com/revdotcom/speech-datasets/blob/main/earnings22/transcripts/README.md
24. Leaderboard short-form results: https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results/blob/e85ed601d17ab0e008721a19fc9cba36b4ee9c9c/english_short_latest.csv (revision named in the Space's `init.py`, https://huggingface.co/spaces/hf-audio/open_asr_leaderboard)
25. Leaderboard long-form results: https://huggingface.co/datasets/hf-audio/leaderboard_longform/blob/4f164c2c904b630d9777323b5d2e7f1f549d0143/longform_latest.csv
26. Leaderboard repository (datasets, normaliser): https://github.com/huggingface/open_asr_leaderboard and https://github.com/huggingface/open_asr_leaderboard/tree/main/normalizer
27. Del Rio et al. 2021, "Earnings-21": https://arxiv.org/abs/2104.11348

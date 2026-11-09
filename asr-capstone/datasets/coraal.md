# CORAAL: scouting notes

Corpus of Regional African American Language, University of Oregon.
Checked 18 October 2026. The archive sizes below come from the server's own headers
(HTTP HEAD requests), not from a download.

Since then:
- 19-21 Oct 2026: ROC, PRV and DCB downloaded and run with Qwen3, Whisper and
  Parakeet (114 interviews, 73 hours; `findings/coraal/`).
- 23 Oct 2026: the other five downloaded too (ATL, DCA, DTA, LES, VLD; 18.4 GB, the
  sizes as below), so all 8 components are on the 5090 laptop: 271 interviews,
  160.9 hours measured, as the guide says. Every reference reads with the same
  reader, Detroit's 2023 release included. Not run yet.

Main sources, used throughout:

- Download page: https://lingtools.uoregon.edu/coraal/ ("DL" below)
- CORAAL User Guide, June 2023, 49 pages:
  https://lingtools.uoregon.edu/coraal/userguide/CORAALUserGuide_current.pdf ("UG", with page)
- Project home (oraal.uoregon.edu/coraal now redirects here): https://oraal.github.io/coraal
- Koenecke et al. 2020: https://doi.org/10.1073/pnas.1915768117 (full text:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7149386), code: https://github.com/stanford-policylab/asr-disparities

## Short version

- 8 components, 159.5 hours, about 1.68 million words, 231 + 40 = 271 recordings.
  Current release is **v. 2023.06**. There has been no new release since, though the
  guide promised one "later in 2023". (UG p. 4, 12; DL)
- The whole corpus is **32.63 GB** to download (32,631,446,995 bytes, 86 files). The
  guide says "≈32.1 GB". (DL headers; UG p. 13)
- Audio is WAV, 44.1 kHz, 16-bit, mono. Transcripts come as TextGrid, ELAN and
  tab-separated text, all with the same content. (UG p. 12)
- Licence: CC BY-NC-SA 4.0. Non-commercial use, cite the corpus, share derived
  material under the same licence. Short clips on a private page are fine. (UG p. 16)
- Recommendation: **ROC first (2.88 GB, about 12-13 h), then PRV (3.27 GB, 14 h)**.
  Together that is 6.14 GB and about 26-27 hours. Adding DCB (8.09 GB, 46 h) gives
  Koenecke's three sites: 14.23 GB, about 72 hours. See section 8.

## 1. Components, sizes, hours

| Code | Place, year recorded | Version | Hours | Words | Recordings | Primary speakers | How recorded |
|---|---|---|---|---|---|---|---|
| ATL | Atlanta GA, 2017-18 | 2020.05 | 8.62 | 93,525 | 14 | 13 | Digital, Zoom H5 |
| DCA | Washington DC, 1968-69 | 2018.10.06 | 34.02 | 333,537 | 74 | 68 | Reel-to-reel tape, digitised 2013 |
| DCB | Washington DC, 2015-17 | 2018.10.06 | 46.04 | 515,189 | 63 | 48 | Digital, Marantz PMD661 |
| DTA | Detroit MI, 1966 | 2023.06 | 25.12 | 240,767 | 40 | 40 | Reel-to-reel tape, digitised 2019 |
| LES | Lower East Side NY, 2008-09 | 2021.07 | 8.44 | 102,171 | 15 | 10 | Digital, Zoom H4 |
| PRV | Princeville NC, 2003-04 | 2018.10.06 | 13.95 | 156,176 | 32 | 16 | Cassette tape, digitised 2006-08 |
| ROC | Rochester NY, 2016-17 | 2020.05 | 11.80 (or 13.2, see below) | 126,140 | 19 | 15 | Digital, Zoom H2N |
| VLD | Valdosta GA, 2017-19 | 2021.07 | 11.49 | 111,973 | 14 | 12 | Digital, Marantz PMD661 |
| **Total** | | **2023.06** | **159.49** | **1,679,478** | **271** | | |

Sources: hours and words, UG p. 12 table. Recordings, speakers and equipment, UG
pp. 28-35 and 41-44. Versions, DL. The 271 is my sum of the recording counts.

Uncertain: **ROC hours.** The table on UG p. 12 says 11.80 h and 126,140 words. The ROC
section on UG p. 34 says "totaling 13.2 hours and 138.9K words". I could not tell which
is current. Also, DCB and PRV list some files with more than one interviewee
("Primary.Spkr" column, UG p. 37).

Download sizes, in bytes, from the server headers of each file on DL (checked 18 Oct
2026). 1 MB = 1,000,000 bytes.

| Code | Audio parts | Audio (bytes) | Text files .tar.gz | Metadata .txt | TextGrids .tar.gz | ELAN .tar.gz | Everything |
|---|---|---|---|---|---|---|---|
| ATL | 4 | 1,714,069,613 | 512,506 | 6,603 | 847,530 | 990,223 | 1,716,426,475 (1.72 GB) |
| DCA | 10 | 7,507,757,449 | 1,971,578 | 44,081 | 3,128,471 | 3,759,043 | 7,516,660,622 (7.52 GB) |
| DCB | 14 | 8,083,737,370 | 2,816,920 | 43,302 | 4,234,932 | 5,032,172 | 8,095,864,696 (8.10 GB) |
| DTA | 10 | 5,156,051,982 | 1,428,948 | 31,226 | 2,352,507 | 2,770,966 | 5,162,635,629 (5.16 GB) |
| LES | 3 | 1,785,907,634 | 546,430 | 7,957 | 921,486 | 1,071,225 | 1,788,454,732 (1.79 GB) |
| PRV | 4 | 3,264,278,790 | 894,006 | 20,393 | 1,566,520 | 1,884,045 | 3,268,643,754 (3.27 GB) |
| ROC | 5 | 2,878,728,984 | 801,537 | 9,748 | 1,188,803 | 1,406,326 | 2,882,135,398 (2.88 GB) |
| VLD | 4 | 2,197,777,243 | 667,292 | 7,476 | 1,002,765 | 1,170,913 | 2,200,625,689 (2.20 GB) |
| **Total** | 54 | 32,588,309,065 | | | | | **32,631,446,995 (32.63 GB)** |

All transcript and metadata files together are only 9.8 MB. The audio is everything.

Two small mismatches with the guide (UG p. 13): it gives DTA as 4.6 GB compressed
(the server says 5.16 GB) and the total as ≈32.1 GB (the server says 32.63 GB). The
other components match to one decimal place.

Unpacked size is not published. My estimate: 44.1 kHz 16-bit mono WAV is about
318 MB per hour, so roughly 50 GB for all 159.5 hours. That is an estimate, not
measured.

## 2. Licence and terms of use

- **Licence:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0
  (CC BY-NC-SA 4.0). "This means you are free to use and reuse the corpus for
  non-commercial purposes, but that you must cite the original corpus and any
  derivative versions of CORAAL you develop and wish to share with others must be
  distributed using the same license." (UG p. 16; DL "Licensing")
- **Commercial use:** DCB, PRV, ATL and VLD can also be had under other licences,
  "such as those for commercial purposes". Contact Tyler Kendall. Not needed for a
  capstone. (UG p. 16)
- **Short clips on a private web page:** yes. CC BY-NC-SA allows sharing and adapting
  the material for non-commercial purposes, with credit, a link to the licence, a note
  that it was changed (clipped), and the clips themselves under the same licence
  (https://creativecommons.org/licenses/by-nc-sa/4.0/). A private page is a smaller
  step than that. Precedent: the Koenecke repository publishes about 6,100 CORAAL clips
  as MP3 and WAV files on public GitHub (https://github.com/stanford-policylab/asr-disparities,
  folder `input/CORAAL_audio`). The project's own CORAAL Explorer streams whole
  recordings in the browser (https://lingtools.uoregon.edu/coraal/explorer/browse.php).
  Suggested line under each clip: "Audio: CORAAL (Kendall & Farrington 2023),
  CC BY-NC-SA 4.0, clipped."
- **Citation is required** (asked for in the guide, and required by the licence):
  Kendall, Tyler and Charlie Farrington. 2023. *The Corpus of Regional African American
  Language.* Version 2023.06. Eugene, OR: The Online Resources for African American
  Language Project. https://doi.org/10.7264/1ad5-6t35. Each component also has its own
  suggested citation (UG pp. 16-18). For ROC: King, Farrington, Kendall, Mullen, Arnson
  and Jenson, 2020, *CORAAL: ROC (Rochester, NY 2016)*, Version 2020.05. For PRV:
  Rowe, Wolfram, Kendall, Farrington and Josler, 2018, *CORAAL: PRV (Princeville, NC
  2004)*, Version 2018.10.06. For DCB: Kendall, Quartey, Farrington, McLarty, Arnson
  and Josler, 2018, *CORAAL: DCB (Washington DC 2016)*, Version 2018.10.06.
- **Anonymity:** names, addresses, workplaces and schools are already bleeped out
  of the audio (UG pp. 24-26). A clip should never try to undo that.

## 3. Download mechanics

- **URL pattern:**
  `https://lingtools.uoregon.edu/coraal/<comp>/<version>/<COMP>_<kind>_<version>.<ext>`,
  where `<comp>` is lower case. `<kind>` is `audio_partNN` (tar.gz), `textfiles`
  (tar.gz), `textgrids` (tar.gz), `elanfiles` (tar.gz) or `metadata` (plain `.txt`).
  Example: `https://lingtools.uoregon.edu/coraal/roc/2020.05/ROC_audio_part01_2020.05.tar.gz`.
  (DL page links)
- **Ready-made list of every file:** http://lingtools.uoregon.edu/coraal/coraal_download_list.txt
  (also https://tinyurl.com/coraalfiles). 87 lines: the user guide plus the 86 corpus
  files. The guide suggests `wget -i` on that list. (UG p. 13)
- The server allows resumed downloads (`Accept-Ranges: bytes` on the archives).
- The audio parts mean nothing on their own. They just split the files into
  downloads. The guide suggests moving everything into one folder after unpacking.
  Each recording's metadata row gives its `Audio.Folder` and `Tarball`, so the
  metadata file tells you which part holds which recording. (UG pp. 12-13, 37)
- **Audio:** uncompressed WAV, "generally 44.1 kHz, 16 bit, mono". Every component
  section says 44.1 kHz, 16 bit, mono. DCB, DTA and VLD were made from higher-rate
  originals that were down-sampled. (UG pp. 12, 28-35, 41-45)
- **Transcripts:** one per recording, same base name as the WAV (for example
  `DCA_se2_ag1_m_05_1.wav` / `.txt` / `.TextGrid` / `.eaf`). The TextGrid is the
  original. The `.txt` and `.eaf` are made from it by script and "contain identical
  information". (UG pp. 12, 27, 36)
- **File names:** `<COMP>_se<n>_ag<n>_<f|m|n>_<NN>_<file number>`. `se0` means no
  social-class grouping. Interviewers are `<COMP>_int_NN`. (UG pp. 36, 40)
- **Other routes, not recommended for this project:**
  - A Hugging Face copy, `bezzam/coraal`, holds whole recordings with one cleaned
    text per recording and no timings (https://huggingface.co/datasets/bezzam/coraal;
    build script https://github.com/ebezzam/prepare_coraal).
  - TalkBank has a CHAT version with the time links removed
    (https://talkbank.org/ca/access/CORAAL.html).

  The original download keeps the per-line timings.

## 4. Transcript format (.txt)

The guide only says the text files are "tab-delimited text", made by a Praat script
from the TextGrids, with "the same timestamp information" (UG p. 27). It does not list
the columns. Code that reads these files fills the gap:

- Columns, in order: **`Line`, `Spkr`, `StTime`, `Content`, `EnTime`**, with a header
  row. My sources:
  - Koenecke's loader reads `Spkr`, `StTime`, `Content` and `EnTime` by name
    (https://github.com/stanford-policylab/asr-disparities/blob/master/src/utils/snippet_generation.py).
  - The project's own R helper uses `Line`, `Spkr`, `StTime`, `EnTime` and `Content`
    (https://lingtools.uoregon.edu/coraal/explorer/R/CORAAL_web.R).
  - The Hugging Face build script skips one header line and takes `Content` from the
    4th field (https://github.com/ebezzam/prepare_coraal/blob/main/push_to_huggingface.py).

  The exact order of `Line` and `Spkr` is my reading of these. Confirm it on the
  first real file.
- **One row per utterance per speaker.** Each speaker has their own TextGrid tier, so
  the interviewer's lines are in the same file under their own `Spkr` code (for example
  `DCB_int_01`). (UG pp. 19, 22-23)
- **Silent pauses are rows too.** The empty TextGrid intervals come through as
  `Content` like `(pause 0.52)`. Koenecke drops rows matching `(pause \d+(\.\d{1,2})?)`.
  The R helper drops `^\(pause .*?\)$`. Utterances are split at pauses of about
  60-70 ms. (snippet_generation.py; CORAAL_web.R; UG p. 19)
- **Time units: seconds**, as decimals, from the start of the WAV. Koenecke's code
  checks for a snippet at 8.9467-12.4571 in `DCB_se1_ag1_f_01_1` (snippet_generation.py).
- **Reading tip:** the R helper reads with `quote=""`, so quote marks inside `Content`
  are plain text. In Python, use `csv.QUOTE_NONE`. The file encoding is not documented.
  Expect UTF-8 and check. (CORAAL_web.R)
- **Possible extra tier:** some TextGrids have a "misc" tier for interlopers. The
  metadata column `Is.Misc.Tier` flags them. I did not confirm how a misc tier shows up
  in the `.txt` (probably as its own `Spkr` value). (UG pp. 27, 40)

No example file is printed in the guide or on the Explorer pages. Here are real
`Content` texts from Koenecke's ground truth. Each one is several utterances by one
speaker, joined, from `DCB_se1_ag2_f_01_1`. The times are in their file names, in
milliseconds. Source:
https://github.com/stanford-policylab/asr-disparities/blob/master/input/CORAAL_transcripts.csv

```
179.711-185.563 s  The people. The neighborhood, like all of that.
216.285-231.548 s  It's sirens. It's people out all hours of the night. It's just confusion. But it- it- it w- it used to be worse around here. I know that, but it's getting better. But it's just different. It's an adjustment.
293.006-305.864 s  Um, either either I was up top, on Seventh and /RD-ADDRESS-3/ all the neighborhood kids or I was down bottom uh, at the playground at the elementary school /RD-SCHOOL-2/.
```

A `.txt` file would hold the same text split into utterance rows, one row per line
of the TextGrid tier, with `(pause …)` rows in between. That layout is pieced together
from the code above. I have not seen it in a file.

## 5. Transcription conventions (UG pp. 19-26)

The guide says the transcripts are meant as "a proxy to the original recording", "not
to make an exact, textually accurate representation" (UG p. 19). Grammar is kept as
spoken ("she run", "they kids"). Accent is not spelled out ("in" for "-ing" is written
"-ing"). Laughter, filled pauses and restarts are kept. Three passes per file: a
transcriber, a graduate-student editor, then a redaction pass. (UG pp. 19, 24)

| Mark | What it means | Example | For scoring |
|---|---|---|---|
| `(pause 0.52)` row | Silent stretch | own row | **Delete** the row. |
| `[ … ]` | Overlapping speech, marked for all speakers, at word boundaries | `Or is he [retired? No?]` / `[No, he was] in the reserve` | **Keep the words, drop the brackets.** Flag the stretch as overlap. Koenecke left out every snippet with a bracket. |
| `/unintelligible/`, `/inaudible/` | Talk that could not be made out | `I can appreciate that /unintelligible/, [but at] that time` | **Cannot be scored: ignore this time stretch.** Delete from the reference, and do not count the engine's words there as insertions. |
| `/??/` | Unclear syllables, one `?` per syllable, for under 3 syllables | | **Cannot be scored: ignore**, as above. |
| `/best guess/` | Unsure transcription, the transcriber's best guess | | **Uncertain reference.** Safest is to ignore the stretch. Koenecke kept these words. It cannot be told apart from the next row by machine. |
| `/Folumbus/` | Mispronounced word, written as said | `Christopher /Folumbus/ I mean Columbus.` | Same slashes as a best guess. Treat as uncertain (ignore), or keep it and expect every engine to "miss" it. |
| `/RD-NAME-2/`, `/RD-ADDRESS-3/`, `/RD-SCHOOL-4/`, `/RD-WORK-n/` | Redacted. The number is syllables. The audio is replaced by a tone. | `on Seventh and /RD-ADDRESS-3/` | **Cannot be scored: ignore this time stretch.** The engines hear a beep, not a name. |
| `<laugh>`, `<cough>`, `<clears throat>`, `<inhale>`, `<ts>` (teeth suck), `<pp>` (lip trill), `<sound effect>`… | Non-speech sounds | `Well we're all different. <laugh>` | **Delete.** |
| `( … )` | Line-level notes: `(laughing)`, `(whispered)`, `(singing)`, `(breathy)`, `(atypical pronunciation)`, `(X language)` | `what up dog (atypical pronunciation)` | **Delete the note.** Words sung, or in another language (`/eyou tu restes/ (Creole language)`), are better ignored. |
| `word-` and `w-` | Restart, or a cut-off word | `it- it- it w- it used to be` | Full words: **keep**. Cut-off pieces (`w-`, `di-`): **delete** or make optional. Engines rarely write them. Koenecke kept them as words. |
| `uh`, `um`, `ah`, `mm` | Filled pauses, with commas around them | `at the, um, other campus` | **Delete** (Koenecke did, and so does Whisper's normaliser). |
| `Uh-huh`, `Mm-hm`, `Uh-uh`, `Nuh-uh`, `Mm-mm` | Backchannels with set spellings | | Keep, but make spellings match both sides. Koenecke deleted `mhm`, `hm`, `huh`. |
| Numbers as words | `twenty-two years`, `o eight` for '08 | | Normalise both sides (engines write digits). |
| Reduced forms | `gonna`, `wanna`, `hafta`, `gotta`, `tryna`, `finna`, `sposta`, `musta`/`woulda`/`coulda`, `'em`, `lemme`, `cause`, `til`, `whatchu`, `gotcha` | | Map both sides to one form. Koenecke mapped `gonna` to `going to` and `tryna` to `trying to`. |
| Dialect words | `aight`, `aks`, `finna`, `hisself`, `bruh`, `mama`… | | Keep. Koenecke changed `aks` to `ask` in the reference. |
| Acronyms, spelled words | `TV`, `DC`, `ASAP`, `B-O-O-N-K` | | Make both sides match (`T V` → `TV`). |
| Punctuation and case | Normal English punctuation. No quotation marks. | | Delete as usual. |

Also worth knowing:

- **Cut sections.** A few interviews have cut sections, for example
  `DCB_se1_ag4_f_01` from 537.8 to 671.8 s. Reading passages and word lists were
  removed too. The metadata `Notes` column lists them. The guide does not say whether
  the audio was cut out or silenced. (UG pp. 26-27)
- **Recordings are trimmed** to the conversation part of each interview. (UG p. 36)

## 6. Koenecke et al. 2020, PNAS 117(14): 7684-7689

Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC7149386, plus the code at
https://github.com/stanford-policylab/asr-disparities.

- **Components:** DCB (DC, recorded 2016), PRV (Princeville, 2004 cassette) and ROC
  (Rochester, 2016). The paper names places, not codes. The repo's clip folders are
  `dcb`, `prv` and `roc`. The white speakers came from Voices of California
  (Sacramento, Humboldt County).
- **Engines:** Amazon, Apple, Google, IBM and Microsoft cloud ASR.
- **Snippet rules** (from `snippet_generation.py`):
  - Interviewee lines only. Pause rows dropped.
  - A line is usable if it does not overlap in time with the lines before or after
    it, and has no `[` or `]` in it.
  - Back-to-back usable lines are joined into one snippet, cut straight from the WAV
    with no padding.
  - Snippets kept only if **5 to 50 seconds** long.
  - After cleaning, snippets need at least **5 words** (`clean_WER.py`).
  - The paper adds that only adults with generally good audio were used.
- **Matching:** propensity-score matching on age, gender and log duration.
  **2,141 snippets per race, 19.8 hours in all, 73 Black and 42 white speakers.**
  The 19.8 hours is for both races together, so I read it as about 10 hours of CORAAL.
- **Text normalisation** (`transcript_cleaning_functions.py`, applied to reference
  and engine output alike):
  - In the reference, delete `/unintelligible/`, `/inaudible/`, `/RD-…/` and `/??/`.
    Delete anything in `<>`, `()` and brackets.
  - Change `aks` to `ask` and `busses` to `buses`.
  - On both sides: lower case, drop apostrophes, punctuation to spaces, numbers to
    words, a list of spelling fixes (`gonna` → `going to`, `ok` → `okay`, `cuz` →
    `cause`, state names, compass directions).
  - Delete filler words (`um uh mm hm ooh woo mhm huh ha`) and ten swear words. The
    swear words were dropped because some cloud engines censor them.
  - Other slash words, such as best guesses and mispronunciations, are kept with the
    slashes stripped.
- **WER:** `jiwer.wer(reference, hypothesis)` for each snippet
  ((S + D + I) / N), then averaged over snippets. It is not pooled over all words.
- **Headline numbers:**
  - Average WER **0.35 for Black speakers and 0.19 for white speakers**, across the
    five engines.
  - Best engine Microsoft: 0.27 against 0.15. Worst engine Apple: 0.45 against 0.23.
  - Black men 0.41, Black women 0.30, white men 0.21, white women 0.17.
  - Median WER by place: Princeville 0.38, DC 0.31, Rochester 0.20, Sacramento 0.18,
    Humboldt 0.15.
  - Snippets with WER over 0.5: 23% for Black speakers and 1.6% for white speakers.
  - On matched identical short phrases, Microsoft scored 0.13 against 0.07.
- **The repo lists the snippet selection.** The clips are in `input/CORAAL_audio/`:
  dcb 3,669, prv 1,666 and roc 800 (6,135 files, mostly MP3). Each is named
  `<recording>_<start ms>_<end ms>`. `input/CORAAL_transcripts.csv` holds each
  snippet's reference and the five engines' outputs. `output/Matched_WER.csv` appears
  to hold the matched set, but I did not open it.
  - So their exact snippets can be rebuilt from our own download: same file, same
    start and end.
  - DCB and PRV have not changed since 2018.10.06. ROC gained files in 2020.05 (UG
    p. 9). So the times should still line up, but this is an inference.
  - Their clips are pre-2020 cuts of the corpus.

## 7. Later work that tests ASR on CORAAL

| Work | What they ran | Numbers |
|---|---|---|
| Whisper paper, Radford et al. 2022 (https://arxiv.org/abs/2212.04356) | "the 231 interviews from CORAAL", meaning all of v. 2021.07 before DTA. Short form used Koenecke's (FairSpeech) snippet script. Long form used whole interviews. | Short form: large-v2 **16.2%** against wav2vec2 35.6%. Long form: large-v2 **19.6%**, tiny 33.1%. Commercial engines are only shown in a figure. (Table 2, Appendix D.4) |
| Open ASR Leaderboard, Hugging Face (https://github.com/huggingface/open_asr_leaderboard; results https://huggingface.co/datasets/hf-audio/leaderboard_longform, file `longform_latest.csv`, updated 30 Sep 2026) | Whole recordings from `bezzam/coraal`. Text is all speakers joined. `/unintelligible/` is **not** removed by that script. | `coraal_avg` WER: Whisper large-v3 **18.89**, large-v3-turbo 17.87, Parakeet TDT 0.6b-v2 **17.64**, Parakeet TDT 0.6b-v3 **15.57**, Canary-Qwen-2.5B 19.05, ElevenLabs Scribe v2 10.67 (best). **No Qwen3-ASR row.** I did not check how `coraal_avg` is averaged (probably over the 8 components). |
| Li, Cohen and Pakhomov 2024, "Reexamining Racial Disparities in ASR… Confounding by Provenance" (https://arxiv.org/abs/2407.13982) | Whisper large-v2, v. 2021.07 (no DTA). Interviewee-only "clean" subset. Also fine-tuned. | Pre-trained WER by component (%), as listed: ATL 21.05, DCA 22.12, DCB 19.78, LES 13.67, PRV 26.55, ROC 33.16, VLD 19.09. The paper contradicts itself on which of PRV, ROC and LES got which number. Main point: tape-era recordings (DCA, PRV) and recording setup affect WER. Do not read every gap between sites as dialect. |
| Mojarad et al. 2024 (https://arxiv.org/abs/2409.03059) | About 10 h of CORAAL-derived speech in six transcript versions, two of them from ASR (Rev, Whisper) | Human-against-human WER between the transcripts was 10-20%. The choice of reference matters a lot. (From the abstract only.) |
| Mojarad and Tang, Interspeech 2025 (https://www.isca-archive.org/interspeech_2025/mojarad25_interspeech.html) | wav2vec 2.0 with and without a language model | Consonant-cluster reduction and ING reduction raise WER a little. No headline WER read. |

The Mojarad 2024 finding is worth carrying into the write-up. CORAAL's transcripts
were made to help sociolinguists search the recordings, not as a verbatim record
(UG p. 19). Human transcripts of this speech disagree with each other by 10-20%.

## 8. Recommendation

| Step | Components | Hours | Download (audio + text files + metadata) | Why |
|---|---|---|---|---|
| Smoke test | ROC part 1 only, plus `ROC_textfiles` and metadata | about 2-3 h (estimate) | 602.5 MB | Try 2 recordings with `--limit`. The metadata file says which recordings are in part 1. |
| **Trial** | **ROC** | 11.8 (or 13.2) | **2,879,540,269 bytes (2.88 GB)** | Modern digital recordings, one interviewer, 19 files. Koenecke site. On the leaderboard and in Whisper's set. |
| **First full run** | **ROC + PRV** | about 26-27 | **6,144,733,458 bytes (6.14 GB)** | Inside the 10-40 h target. Adds 2004 cassette audio and rural NC speech. Koenecke's worst site (median 0.38). |
| Koenecke's full set | ROC + PRV + DCB | about 72-73 | 14,231,331,050 bytes (14.23 GB) | Same three sites as the PNAS paper, so their snippet list can be redone with open models. |
| Later, to keep the queue full | ATL, VLD, LES, DCA, DTA | 87.7 | 18.4 GB | Older tape (DCA 1968, DTA 1966) against new digital (ATL, VLD, LES). Lets recording quality be separated from place. |

- **Skip the TextGrid and ELAN archives.** They hold the same text as the `.txt`
  files (UG p. 12). Download them later only if a tier question comes up.
- **Order by need:** `<COMP>_metadata_*.txt` and `<COMP>_textfiles_*.tar.gz` first
  (tiny), then the audio parts.
- **GPU time, rough:** from `overnight-log.md` on the 5090, Parakeet runs about 46x
  real time, Whisper 20-25x and Qwen3 about 10x. All three together come to about
  10 minutes of GPU per hour of audio. So ROC is about 2 GPU hours, ROC + PRV about
  4.5, the Koenecke set about 12, and all of CORAAL about 27. Qwen3 is most of it.
- **Disk:** unpacked WAV is about 318 MB per hour (estimate). ROC + PRV is about
  8.5 GB unpacked, ROC + PRV + DCB about 23 GB, on top of the archives until they are
  deleted.
- Per the plan in `next-session-plan.md`, ask before any download over a few GB. ROC
  (2.9 GB) is at that line. The smoke test (0.6 GB) is under it.

Audio part sizes for the recommended components, in bytes:

```
ROC_audio_part01_2020.05  601,718,376     PRV_audio_part01_2018.10.06  797,045,351
ROC_audio_part02_2020.05  617,531,670     PRV_audio_part02_2018.10.06  919,479,624
ROC_audio_part03_2020.05  797,355,036     PRV_audio_part03_2018.10.06  982,116,581
ROC_audio_part04_2020.05  549,776,743     PRV_audio_part04_2018.10.06  565,637,234
ROC_audio_part05_2020.05  312,347,159
DCB parts 01-14 (2018.10.06): 807,328,059  646,803,359  471,156,371  478,496,612
  904,081,541  670,401,934  594,417,668  633,462,590  664,400,237  530,685,203
  468,514,884  521,037,029  564,766,923  128,184,960
```

## Open questions to settle on the first real file

- The column order of the `.txt` files, and how a misc tier shows up.
- Whether cut sections of an interview are silent or removed from the audio.
- ROC: 11.8 or 13.2 hours (the metadata column `CORAAL.Length.of.Transcript` will
  settle it).
- How to score `/best guess/` stretches: ignore them (safer) or keep them (Koenecke).
  The choice changes the numbers, so report both if cheap.

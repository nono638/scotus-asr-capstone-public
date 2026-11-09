# Where this was left off

Last worked on 16 October 2026. Written to be read cold, after a gap.

**Numbers corrected 6 November 2026.** `midterm/numbers-pack.md` and `findings/` hold the
right figures. Older sections below still quote some from before the corrections (Whisper
verbatim 14.53, 15.76, 14.72, 15.07; 203 and 187; the leaderboard column; Earnings-22
12.05, 12.56, 14.13). What changed and what's left: `bug-audit-2026-11-05.md`.

**Going public is the plan (6 November 2026), not done yet; everything is still private.**
Before then: listen to a sample of the serious clips, re-decode the stripped and vanished
chunks on the GPU once Qwen finishes, and choose where it lives. Credits and page bugs are
fixed. Qwen's partial answers are kept off the pages by `SHOW_QWEN = False` in
`tools/build_site.py` (the one place they enter: `judged()`), so a full rebuild is safe now;
turn it on once Qwen has read every case.

**The website and the four whole-recording pages were rebuilt and republished on 7 November
2026**, same links, on the `-reread` runs and Sonnet's complete answers, Qwen left out. Every
card was cut again from the current runs. New page `ai.html`, "How AI was used", linked from
every page's bar and foot and summarised on the front page. Also fixed: misquoted
`engine_wrote` (display, and the finder for its next run), rows with no real time shown as
unknown with no clip, the data page's wording, CORAAL speaker labels. The recording pages now
have audio for 24 arguments (29.2 h), all 76 EdAcc calls and 51 CORAAL interviews (33.2 h).
What's left: `bug-audit-2026-11-05.md`.

**Later on 7 November the site was republished again** (same link; the recording pages
unchanged): the error-model sections say it was re-fitted on the repaired runs and holds
without Parakeet (figures read from `findings/error-model/`; the Supreme Court bars are still
the 23 October three-engine fit by term, which was not re-fitted), and each data-set page
now counts Sonnet's "opposite" answers per engine and how often it doubts the reference
(Earnings-22 27%, the others 1-3%), computed in `build_site.py` from the judge files.

Everything below is committed and pushed to
`github.com/nono638/scotus-asr-capstone`.

> **The capstone is the ASR work only (decided with Professor Hagstrom, 16 Oct
> 2026).** The 12 October idea of moving the main question to steno is dropped for
> the capstone. Beam search (`steno-plan.md`) carries on as a personal project
> outside it, on the work laptop.
>
> **Deadlines (from the syllabus, read 15 Oct 2026).** Midterm draft and code
> walkthrough due 28 October, **moved to 8 November** (the user, 27 Oct): 10-12 pages covering the introduction with a literature
> review, methods, and preliminary results. Final paper due 13 December: 15-20 pages,
> Quarto with a rendered PDF preferred, plus a link to a repository with all code and
> data. Presentation of 10-15 minutes the week of 14 December, pitched at peers and
> non-technical managers. Grade: proposal 10%, midterm 10%, final paper 60%,
> presentation 20%. The syllabus itself is in the top folder, kept out of git.
>
> **The proposal as submitted** is the PDF "_Same Room, Same Problems_ ..." in the
> top folder, kept out of git: a five-page essay in the first person, written from
> a court reporter's side, with no section headings and no citations. It is not
> `proposal/proposal.md`, which is an earlier, more technical draft. The midterm
> builds on the submitted one. What it promised: CORAAL, bankruptcy hearings if
> time permits, a website pairing the audio with the record and the machines, the
> drop-in tool with notes on normalising transcripts, fine-tuning Qwen3 (expected
> gain under 1%), and more work on speaker identification, which nothing here
> measures yet.
>
> **The midterm (8 November 2026).** The paper is `midterm/draft.md`, built into a PDF
> by `midterm/make_pdf.py` (12-point, single-spaced, about 13 pages plus references).
> It was written in conversation: Noah answered questions and made the decisions, Claude
> drafted the text and checked every number against `findings/`. The paper's AI-use
> statement says this, and says what the language models did in the analysis. Noah
> arranges the code walkthrough with the professor himself.

---

## The state of it in one paragraph

Seven speech recognition models have been run over the 61 arguments of October
Term 2017 and scored three ways against the certified transcript. Two faults in
this project's own measuring were found and fixed in September, and everything
was re-scored. In October a word-by-word comparison of all seven models was added
(`findings/crowd/`): which words every model hears, which they all miss, whether a
vote among them helps, and where they agree with each other against the record.
The notebook at `notebooks/first-look.ipynb` is the short write-up. What is
missing is not more models - it is a human baseline, and listening to the short
lists the comparisons produced.

## A general tool, not only a Supreme Court one (16 October 2026)

Part of the project is now a general ASR bench: any corpus with a reference,
any set of models, the same scoring and the same word-by-word comparison.
`project-overview.md` says why; `pipeline/README.md` ("Other corpora") says how.

- **Corpora are adapters** in `pipeline/scotus_asr/corpora/`: each one downloads
  its data, lists its recordings and reads its reference into speaker turns.
  The Supreme Court is one of them, wrapped round the old code, so its numbers
  do not move. Shared parts: a resuming downloader, a safe unpacker, NIST
  STM/CTM readers and writers, an index with Lhotse's field names.
- **A settings file per corpus serves every model**: `--config config/qwen3.yaml
  --config config/corpora/edacc.yaml`. `--limit N` tries the first N.
- **The comparison takes any models.** `tools/crowd.py` with no arguments is the
  seven, unchanged (`pipeline/config/model-sets/scotus-seven.yaml`). `--set`,
  `--runs-dir` (every engine in a folder) or `--model Name=run` for anything else.
  Thresholds are written for n models and give the old numbers at seven. It
  writes `runs-used.csv` so a table says which runs made it.
- **EdAcc is the first other corpus** (video calls, many second-language
  speakers; `D:/asr-corpora/edacc/`, outside the repo). Its reference is upper
  case without punctuation, so only the `standard` rule is fair there - the
  verbatim rule reads about 96% and means nothing. Five engines on the whole test
  split (40 conversations, 18.2 hours, 157,504 reference words), results in
  `findings/edacc/`:

  | Engine | Error rate | Speed (x real time) |
  |---|---|---|
  | Qwen3 | **11.7%** (4.4% on the Supreme Court) | 6.9 |
  | Parakeet | 13.4% | 32.9 |
  | Whisper | 14.5% | 20.4 |
  | Canary | 16.5% | 20.4 |
  | commercial engine shipped with EdAcc (`company.ctm`) | 17.5% | - |
  | Granite | 18.5% | 4.9 |

  Qwen3 beat the commercial engine on all 40 conversations. 6.1% of the words
  were written by none of the five; the engines share most of their misses (80-84%
  of Qwen3's, a little more than on the Supreme Court); and a vote of all five
  (12.2%) is worse than Qwen3 alone. Voxtral and Granite Plus were dropped:
  slow, and not good enough on the Supreme Court to be worth it.
  Surprise: the conversations labelled all first-language English were not the
  easiest for Qwen3 (12.9%, against 11.4% for all second-language), but the labels
  are unreliable and two hard L1 conversations (C52, C45) carry that. Engines also
  add the most words there, which may mean the reference skipped crosstalk: worth
  a listen.
- **New corpora get three engines by default: Qwen3, Whisper and Parakeet**
  (decided 16 October 2026). The rest are backfilled only if a result calls for
  them; a fixed `--run-id run-<corpus>-<engine>` makes that one command. The
  commands are in `pipeline/README.md` ("Other corpora").
- **Which words go wrong: a first model** (16 October 2026, `findings/error-model/`).
  A logistic regression of every word for every engine on the conditions around it.
  The conditions explain about 38 times as much as the engine on the Supreme Court
  (McFadden R-squared 0.226 against 0.006), about 9 times on EdAcc (0.062 against
  0.007). Odds of an error: 5.5 times for the first word after a speaker change, 6.4
  near a reporter's dash, 14.8 for a legal term, 5.0 for a name; worst engine against
  best, 2.6. This is H2 in `heilmeier-notes.md`, and the core result for the midterm.
- **Next: a bring-your-own-data application** (planned 16 October 2026): your own
  audio and transcript in, engines of your choice, scores and error kinds out, with a
  gallery and an evaluation site later. Phased; the plan and progress are in
  `app-roadmap.md`. Phase 0 (groundwork) is done.
- **A rough preliminary website** (18 October 2026), private:
  https://claude.ai/artifact/3Q9MW1VB1ZgMNPPkLsTELX. One page - findings, Figure 1,
  how much of each term is done, a first gallery of passages no engine got, the tool's
  roadmap, the queue. Not polished on purpose. Rebuilt from `findings/` and the queue by
  `tools/build_site.py` into `site/`, then republished to the same link (the
  `asr-work` skill does this after each batch).
- **The website rebuilt from shared widgets** (19 October 2026, same link). The
  opening states the flip; Figure 1 is interactive (switch rules, filter by term,
  hover, click a dot to hear the 12 seconds where Qwen3 and Whisper disagree most -
  `tools/flip_clips.py`, `findings/flip/listen-windows.csv`); the coverage grid and
  the error model respond too; 14 passages play at 5, 10 or 20 seconds with the words
  lit (8 no engine or one engine got, 6 invented words). Built from `web/widget/`, which
  the listening bench's builder now shares (it rebuilds the same 200 spots; the live
  bench was left as it is, holding the labels). `tools/check_page.py` checks either page
  in Edge before publishing. Clips (35 MB) are cut again, not kept in git.
- **CORAAL onboarded** (19 October): Rochester and Princeville, 51 interviews, 27 hours,
  in `D:/asr-corpora/coraal/`; read through a general `references/timed_table.py`.
  Queued after EdAcc dev. A two-interview Qwen3 trial scored 6.4% and 7.5% (benchmark).
  `datasets/coraal.md` and `datasets/earnings22.md` hold the scouting.
- **CORAAL, all 271 interviews, three engines** (finished 25 October, 01:08): the five
  other parts (ATL, DCA, DTA, LES, VLD; 157 interviews) added to ROC, PRV and DCB. No
  failed recordings. Standard-rule medians by part run from ROC (Parakeet and Qwen3 7.3%,
  Whisper 10.7%) to PRV (Qwen3 20.5%, Parakeet 19.0%, Whisper 25.1%); Qwen3 is 14.2% on
  all 271. Worst is DCA_se1_ag4_m_02_1 (39.1% Qwen3), whose record leaves speech out.
  Worth a look: Qwen3 quietly skips seven short stretches on DTA_se2_ag3_f_01_1
  (210 words, e.g. a question at about 1205 s), a "skips" example. The four failure
  searches were last run before these parts, so CORAAL's share of them will grow when
  re-run. The queue is empty: every row is done or on hold.
- **A fifth failure search: breakdowns** (25 October, `findings/failures/breakdown/`,
  `tools/find_breakdowns.py`): 30 s+ with nothing written (empty chunks, Parakeet's
  stall), loops, and text that isn't speech (Hangul, Cyrillic, "Thanks for watching!").
  155 cases: 23 blackouts, 42 loops, 90 artifacts; Granite on EdAcc worst (10 empty
  chunks, 18 loops). Finds every known breakdown; DCB_se1_ag2_f_02_1's "empty chunk" is
  really words timed two minutes late. `per-recording.csv` gives each recording's broken
  share. Not on the website yet. The four other searches now cover all 271 CORAAL
  interviews: meaning 24,410 candidates in all (CORAAL 10,247), edits 4,506, invented
  735, skips 764.
- **Earnings-22, all 125 calls, three engines** (finished 23 October,
  `findings/earnings22/`). Benchmark rule: Qwen3 11.34%, Parakeet 11.79% (after its
  full-stop fix), Whisper 12.42%. Qwen3 is worst on the Asian calls (19.3%) only
  because of three interpreted Korean calls (Hangul against an English-only reference,
  and one kept loop on 4481766); without them it is first there too. Whisper keeps
  9% of the restarts the transcribers wrote. Two Qwen3 loops were kept (MP3-A chunk
  11, 4481766 chunk 8): re-run or report as Qwen3 errors is still to decide.
- **Two human references for the same calls** (1 November, `tools/subset10_two_refs.py`,
  `findings/earnings22/subset10-two-references.csv`). Earnings-22's Subset 10 (10 calls,
  11.1 h) has a verbatim and a cleaned-up reference. Fillers kept, punctuation and capitals
  ignored: the two humans differ by 13.4% (the clean one leaves out 9.6% of the verbatim
  words). Whisper is 7.1% from the clean one and 13.0% from the verbatim one; Parakeet 9.8%
  from verbatim and 15.4% from clean; Qwen3 in between (10.0% clean, 11.3% verbatim) and,
  with fillers removed, closer to verbatim: it drops "uh" but keeps restarts. Whisper is
  closer to the clean transcriber on all 10 calls, Parakeet closer to the verbatim one on 9.
  Whisper's figures match McNamara et al. 2024's OpenAI engine (13.1% and 6.4%).
- **Invented words** (19 October, `findings/invented-words/`): of 76,106 added words,
  990 fall on quiet audio; 532 are Whisper writing speaker names into pauses (489 in
  OT2010); 48 are real words inside an argument. 30 clearest listed for the bench.
- **Interesting failures first** (19-20 October; the user's direction: names, speaker
  labels and capitals are dull, show where ASR fails in a way that matters). Four kinds,
  found the same way on all three data sets, in `findings/failures/` (one README there
  for the shared format; one finder each: `tools/find_meaning_changes.py`,
  `find_invented_words.py`, `find_edits.py`, `find_skips.py`, all reading
  `tools/lineup.py`, which lines every engine up against every reference and caches it):
  - meaning changes - a lost or added "not" runs 0.25-0.49 an hour per engine on the
    Supreme Court, 0.33-0.48 on Earnings-22, about 2-3 on EdAcc and CORAAL; most "other
    word" swaps are plain mishearings (an upper bound);
  - invented words - 0.05 an hour on the Supreme Court, 0.17 EdAcc, 0.38 CORAAL, about 1
    on Earnings-22 (where a reference that leaves speech out inflates it);
  - the engine edits the speaker - on CORAAL every engine rewrites African American
    English grammar as standard English (Whisper most: 35% of "they working", 36% of
    habitual be; "she help" becomes "she helped" about half the time); Whisper keeps 6% of
    the Supreme Court's restarts, Qwen3 70%;
  - silent skips - Parakeet dropped clear one-speaker speech about 1.5 times an hour
    everywhere (474 on the Supreme Court, up to 186 words). That was its decoder stall
    (Parakeet bullet below); since the re-read it is about 0.5 an hour (157 on the
    Supreme Court, none over 22 words), still the most of the three except on CORAAL,
    where Whisper skips more. Whisper's long skips all cross speakers.
  116 shortlisted cases, read by a machine judge, none heard yet - the next listening job.
  (23 October: all four searches re-run on Parakeet's re-read transcripts and all 125
  Earnings-22 calls; the 21 Parakeet skip cards were fixed by the re-read and came out.)
- **An LLM judge on the failure cases** (23 October, `findings/judge/`,
  `tools/judge_failures.py`): Gemma 4 26B through Ollama on 40 fixed cases (20 shortlist,
  16 random, 4 controls), asked whether the meaning changed or flipped, how much it
  matters, whether the rule was right, which version was said (blind), which engine keeps
  the meaning, and what the rules missed. Shown the rule's evidence, it repeated it even
  over two identical texts, so the rule now gets its own request (prompt 0.2; controls 16
  of 16). A minute of context is enough for 31 of 36 verdicts. Good on negations,
  numbers, invented phrases and restarts; can't judge "would a reader notice". Found
  things the rules miss: "done did" → "didn't do it" (meaning search skips differences
  over 3 words), possessive "they" → "their", and a Supreme Court "Thank you." wrongly
  called invented.
  24-25 October: prompt 0.3 (tested blind against 0.2), then seven judges on the same 40
  cases: Haiku 5.5 and Sonnet 5.5 through the API (key in the git-ignored `API keys/`),
  Gemma 4 26B and 31B and Qwen 3.8 27B on the card. Sonnet is the best overall, at $3.35
  for the 40; Qwen 3.8 is the best local judge; every judge matches Claude's meaning
  verdict 67-81% of the time. Write-up: `notebooks/llm-judge.ipynb`.
- **Both judges finished** (3 November). Sonnet has read all 37,261 places in full-v1;
  Qwen 3.8 read the 19,111 it was aimed at (23,468 in all). Same label on 80% of the
  cases both read, Qwen agrees with 84% of Sonnet's serious cases and 91% of its
  reversals (`notebooks/findings.ipynb`, re-run that day). Run GPU jobs on the 330 W
  charger: on USB-C the card ran 3-4 times slower. What's left for the judges, such as
  asking Qwen twice with temperature on: `future-work-llm-judge.md`. **Started again
  4 November, 01:32:** Qwen is reading the other 13,793 cases, 500 at a time in random
  order, about 21 s a case, so about 3.4 days. `tools/run_qwen_judge.ps1` runs it in its
  own window (close the window to stop; run it again to carry on); the log is
  `D:/scotus-corpus/experiments/judge/qwen-full-v1.log`. Its answers file is left
  uncommitted until it finishes.
- **Clips on the data page's serious rows** (5 November, same link). `tools/build_row_clips.py`:
  2,599 rows (Sonnet's opposite or severity 3-4, not Earnings-22) have a Play button, about
  17 s around the error, plus a box to show only those rows. The clips are joined into 10
  Ogg Opus files at 24 kbps (105.5 MB), since the host allows 511 files a page and 15 MB a
  file; `data/row-clips.json` says where each case is. Run it after `build_data.py`. Not
  heard yet. Two things found on the way:
  - `errors.csv` had doubled line endings, so in the browser every row's id began with a
    line break and the page counted 37,416 rows (37,415 is right). Fixed in `build_data.py`.
  - **13 CORAAL rows have no real time** (11 "ain't", 2 "finna", in the edits search): they
    start at 0 and end far into the recording. Two are in the serious set (f08874, f15905)
    and get no clip. Still to do: find out why the search lost their place, and whether
    the judges were shown the wrong text for them. (Answered by the audit: 25 rows, a
    fallback to time 0 in `find_edits.py`, fixed 6 November. After the rebuild only 5 rows
    have no real time, all "gone after the repair"; the data page shows them as unknown.)
  - **Links between artifacts must be letters, digits and hyphens after the `#`.** claude.ai
    passes only a plain `#name` to the page, never `.`, `@`, `=` or a query string, so every
    link into a recording opened the list, and the whole-recording pages' menu links to the
    site's pages landed on its home page. Now `#r-<data set>-<seconds>-<recording>` (in the
    name `-` is written `-h`, `_` is `-u`) and `#go-data`; `site.js` and `explorer.js` must
    agree on this. Fixed 5 November.
  - **Stronger error highlights, on the record and the engines alike** (5 November; the
    user found the old tint and thin wavy line nearly invisible, on an engine's line above
    all). Now a yellow highlighter for any difference, bright yellow where every engine
    differs, and a bold solid colour for the errors the searches found (`--mark*` and
    `--e-*` in `tokens.css`, separate from the charts' `--k-*`). An engine's dropped word
    still has nothing to highlight on its own line; it shows on the record's only.
  - **"Every engine missed this" was wrong for words the scoring drops.** `build_explorer.py`
    counted any record word with no match, and "um", "--" and merged pieces ("a way" scored
    as "away") can never match, so they claimed every engine. Fixed; the built transcript
    files were corrected from the real alignment, leaving 235,449 such words of 441,385.
    Only this highlight used the count, so no result or table changes.
  - **One error painted every word timed inside its span,** up to 9,687 words, which the
    stronger colours made obvious. `explorer.js` now marks only the words the case quotes.
- **Bug audit, 5 November: `bug-audit-2026-11-05.md`.** Not fixed yet, and it changes numbers
  the site and the midterm quote: Whisper's verbatim 14.53 is really 14.01, the site shows
  Parakeet from before its fix, "benchmark rule" means two rules, and the aligner stripped
  punctuation from some Qwen3 and Voxtral chunks (needs a GPU re-decode). Read it before
  quoting a figure.
- **The website reworked** (29 October, same link), after the user's list of what was
  wrong (memory note `pages-need-rework`):
  - Cards play about 15 and 30 seconds, each edge moved up to 5 s to fall between
    sentences (`clips.snap_window`); buttons say the real length, the longer one shows
    more text, the record's words are timed and its passage marked.
  - Each data-set page: a link to the data set, the big picture (error rate per engine,
    rule counts per hour), a box on who wrote the reference with checked links
    (`SOURCES` in `build_site.py`), then five sections by what an error does to a
    reader (says the opposite, gets a fact wrong, adds words, leaves out, rewrites),
    filled from the shortlists and then from Sonnet's judged cases. Preliminary.
  - Gone from the Supreme Court page: Figure 1, the rule switch, the seven-engine table
    (the user finds ASR-against-reporter scoring unsurprising).
  - New `compare.html` and `data.html`: `tools/build_data.py` writes `site/data/`
    (git-ignored): `errors.csv` (every case, 37,415 rows, with both judges' answers),
    `recordings.csv` (every recording x engine, 2,342 rows, error rates counted from
    the same line-ups as the failure searches) and the smaller tables in six bundles.
  - The whole-recording pages are now one artifact per data set (URLs in
    `tools/explorer_page/published.json`), audio as Opus at 14 kbps, every found error
    highlighted by section, player controls and keys (Space, arrows, J/K for errors),
    and `#r-<data set>-<seconds>-<recording>` opens a recording at a moment.
    Supreme Court https://claude.ai/artifact/3pzYvWbX1WtcdLqqycpPQS (258 arguments, audio
    for 20, 24.6 h); EdAcc https://claude.ai/artifact/Tkzb4Nj8s7hyqTGUS8D9E7 (76, audio
    for all since 6 November, 35.6 h; `BUDGET_MB` went from 215 to 245, so the next rebuild
    of the other two also picks a little more audio); CORAAL https://claude.ai/artifact/UmA8KeREAGjcBPok4pjMZr (271, audio
    for 46, 28.6 h); Earnings-22 https://claude.ai/artifact/M5Q1JCD8EWz9wwr8FMMkXa (125,
    text only). The old single explorer below (CK7C...) is superseded and no longer linked.
    More audio, if wanted (measured 6 November, not started): Supreme Court in full would be
    2.0 GB and CORAAL 1.0 GB against 256 MB a page. Options: play Supreme Court from
    supremecourt.gov (its server allows seeking; whether claude.ai allows it needs a small
    test page); or keep only 10 s either side of errors (Supreme Court, every case, 146 MB;
    CORAAL, all but plain differences, 131 MB), with the player skipping the gaps; or split
    into about 14 pages. A full `build_explorer.py` run reads the judges through
    `build_site.judged()`, so `SHOW_QWEN` keeps Qwen's unfinished answers out of it too
    (rebuilt that way on 7 November).
- **The recording explorer** (23 October, https://claude.ai/artifact/CK7CSqhV8e97d2YnUmCk4c,
  linked from the site's top bar as "Every recording"). Pick any of the 573 recordings,
  then read the reference beside every engine 30 seconds at a time (differences marked),
  see its error rates, its failure cases and every file behind it, and listen with the
  words lit up. A data page shows all 195 findings CSVs as tables. Built by
  `tools/build_explorer.py` into `explorer/` (ignored by git apart from `index.html`);
  checked by `tools/check_explorer.py`. Limits of the host shape it: 256 MB and 511
  files a page, at most 64 MB a publish, no compressed files (the transcripts are gzip
  written as base64 text) and no audio from other sites. So only 14 recordings (about 8
  hours) have full audio on the page; Earnings-22 has none (no licence). On the 5090
  laptop, `python tools/explore_local.py` serves the same page with every recording's
  audio and opens any file behind it. Room is left for about 7 more hours of audio.
- **The website is now four pages from one template** (20 October, same link): a front
  page and one page per data set (`site/scotus.html`, `edacc.html`, `coraal.html`), each
  leading with the four kinds as cards to hear, then error rates, then the data set's own
  extras (Figure 1 and the error model on the Supreme Court), then progress. Template
  `tools/site_page/dataset.html`; per-data-set wording in `DATASETS` in
  `tools/build_site.py`. EdAcc and CORAAL error rates by part in
  `findings/<corpus>/engines-by-part.csv` (`summarise_runs.py --index`). On Princeville,
  Parakeet (19.9% since its full-stop fix, 20.5% before) edges Qwen3 (20.7%) - the
  first place Qwen3 is not first. Since the fix it also edges Qwen3 on Rochester and
  Princeville together (14.03% against 14.39%).
- **The ASR queue, replenished 18 October**: EdAcc's 36 dev recordings for five
  engines, then the twelve Supreme Court terms not yet done (2011-2016, 2018-2020,
  2022-2024) for Parakeet, Whisper and Qwen3 - about 165 GPU hours. OT2020 (argued by
  telephone, almost no crosstalk) first; the rest spread across the years. A queue row
  can now name several settings files, so any corpus with a config can be queued.
- **Parakeet stops writing after a full stop** (23 October 2026, `findings/parakeet-stall/`).
  Parakeet's long blank stretches over clear speech (up to 154 s; 319 minutes over the
  Supreme Court runs, 3.4% of the Earnings-22 audio) are a decoder stall, not the model
  failing to hear. 98% start right after a word ending a sentence, against 6% of its
  words overall. The decoder gets stuck, and in our 300-second chunks only the next
  chunk reset it. Others report the same in NVIDIA's own NeMo, so it is the model, but
  a pipeline can avoid it. The fix: decode every blank stretch of 4+ seconds again on
  its own (from [dekho-suno-jaano PR #234](https://github.com/m2moiz/dekho-suno-jaano/pull/234)).
  On the worst recording from each data set, Parakeet's error rate fell from 7.6% to 5.6%
  (Supreme Court), 9.4% to 8.0% (Earnings-22), 8.4% to 4.1% (CORAAL) and 28.1% to 26.1%
  (EdAcc). Shorter chunks were tested and are not the answer.
  **The re-read has been applied to every existing Parakeet transcript** (same day,
  `tools/reread_parakeet_gaps.py`, into new `run-*-parakeet-reread` folders; the old
  runs are untouched). Standard rule, every recording: Supreme Court 7.24% to 6.18%,
  Earnings-22 14.47% to 12.56%, CORAAL 12.45% to 12.11%, EdAcc 13.25% to 12.92%;
  111,036 words brought back, 665 of 760 recordings better and 10 worse. Parakeet is
  now worst of the three on 100 of 258 arguments on the benchmark rule (205 before) and
  second in OT2021 and OT2025. Two side effects are written up: Korean calls with an
  interpreter get worse, and Parakeet's habit of stamping a stock phrase ("a very
  important thing") on one instant shows up a little more. The tools, the flip, the
  error model and the website now read the `-reread` runs. **Still on the old Parakeet
  run:** the seven-engine OT2017 analyses (the table below, `findings/crowd/`, the
  seven-engine error model, the listening bench), because the bench's labels are tied
  to that set.

## The numbers, so you do not have to go looking

61 arguments, all seven models, after both September corrections and the
October scoring fixes (see "The scoring was inventing differences" below).

| model | params | benchmark rule (leaderboard) | benchmark rule | verbatim rule | times worse | speed |
|---|---|---|---|---|---|---|
| Qwen3-ASR | 1.7B | 4.90% | **4.44%** | 15.55% | 3.5x | 4.6x\* |
| Whisper large-v3 | 1.55B | 6.16% | 5.71% | **14.53%** | 2.5x | 18.2x |
| Voxtral Mini 3B | 4.7B | 6.62% | 6.12% | 15.71% | 2.6x | 7.1x |
| Granite 4.1 2B Plus | 2.3B | 7.03% | 6.42% | 29.05%† | 4.5x | 1.6x |
| Canary-1b-v2 | 0.98B | 7.19% | 6.68% | 16.12% | 2.4x | 35.3x\* |
| Parakeet TDT | 0.6B | 7.39% | 6.94% | 18.18% | 2.6x | 47.0x |
| Granite 4.1 2B | 2.3B | 8.38% | 7.84% | 17.21% | 2.2x | 7.9x |

Parakeet here is from before its full-stop fix. After it (`run-20260924-064733-reread`):
6.22%, **5.77%**, 17.18%, 3.0x, 42.7x with the re-read - third on the benchmark rule,
just behind Whisper, and fifth verbatim.

Also in `findings/final-seven-model-results.csv`. Each figure is the mean of the
61 per-case rates. "Leaderboard" is the benchmark rule exactly as leaderboards
compute it, quirks included, for comparing with published numbers; the other
two columns use the October fixes, and "times worse" compares those two.

\* Measured before the GPU memory fix of 21 September, while the card was quietly
paging; probably too low, Qwen3's most of all. Error rates are unaffected.
† IBM removed punctuation and capitalisation from this model on purpose, so this
measures that decision rather than its hearing.

**The claim to lead with** is the gap, not the ordering: every model is two to
four and a half times worse scored as a record than scored the way benchmarks score, and the
model that wins the benchmark rule by the widest margin has one of the widest
gaps. A leaderboard still recommends the wrong model for this work.

**The claim not to lead with any more.** An earlier version said benchmark rank
and verbatim rank are close to unrelated. Much of that turned out to be one of
our own faults. Among the six models that punctuate the rank correlation is +0.89.

## Seven sets of ears (October 2026)

`tools/crowd.py`, results in `findings/crowd/`, write-up in the notebook.

- **87% of the official words are heard by all seven models; 1.6% by none.** That
  1.6% is a floor no combination of these models can get under. Qwen3 alone misses
  3.6%.
- **A vote does not beat the best model.** Built without looking at the official
  transcript, and once with each model as the pivot, the vote scores 5.0% to 6.4%:
  better than most of the models alone, never as good as Qwen3's 4.5%. The vote
  fixes wrong and added words but leaves out about 10,000 more words than Qwen3
  does: repeated words and second speakers that most models drop. Qwen3 and
  Granite Plus each get over 13,000 words right where most of the others are
  wrong, and the majority overrules them.
- **The models share their mistakes.** Every pair misses the same words 8 to 15
  times more often than chance would give - most of all Whisper and Voxtral, which
  shares Whisper's encoder. Seven models are not seven independent ears.
- **The hard words are crosstalk.** Words the models split over or all miss sit
  next to the reporter's interruption dash more than half the time, against 9% for
  ordinary words, and 81% of the 1,587 hard passages do. The reporter wrote both
  voices; the machines kept one.
- **Where six or more models agree against the record, plain mishearing is rare.**
  A hand read of 157 random flagged spots (`flagged-spots-review.md`) found about
  47 overlapping speech, 36 disfluencies the record keeps, 35 not real differences
  at all, 13 names and legal terms, 18 small words that need an ear, and only about
  6 clear mishearings of clear speech. That was text only - nobody listened yet.

## The scoring was inventing differences (12 October 2026)

A small web page showing flagged spots with their audio made the labels look
wrong, so 157 random spots were read by hand (`flagged-spots-review.md`). Two
problems came out of it.

- **The comparison counted differences nobody could hear.** Whisper's normaliser
  deletes anything in parentheses ("3553(e)" lost its "e"), turns every 's into
  "is" ("Vogt's" became "vogt is"), and splits hyphenated words; the engines'
  word timings split "U.S." into "U" and ".S.". Fixed in
  `pipeline/scotus_asr/scoring/harmonise.py`, tested with real spots in
  `pipeline/tests/test_harmonise.py`. Every model went down by 0.4 to 0.6 points
  on the benchmark rule; no rank changed. 592 of the 1,337 "machines add words"
  spots were lone subsection letters; that list is now 372.
- **The sorting named which rule fired first, not what happened.** `crowd.py` now
  gives every spot two labels - what happened in the speech, and what the
  machines did - from checks that all run, picked in a fixed order. Spots no
  check claims ("other", 819 of them) go to a language model,
  `tools/judge_spots.py`, which says what kind of difference and why, never who
  is right. The judge is Gemma 4 31B, run locally through Ollama: a mid-sized
  open model, not a frontier one, reading text only. Its labels are in
  `findings/crowd/judge.csv`; for the hard passages it sees all seven models'
  versions (the first run showed it only Qwen3's and was redone). It is held to
  the same terms as a person on the listening page - the same nine descriptions,
  and as many kinds as fit, each primary or secondary - because the labels should
  follow what a person hears, and the judge should follow the labels.

The rule-based labels have not yet been checked against labels made by ear. The
overlap check in particular may be too generous: it calls about half the
"record has it" spots overlap, where the hand read found about a third.

## A local LLM fixing the formatting (October 2026)

`tools/llm_format.py`, results in `findings/llm-format/`, write-up in
`notebooks/llm-formatting.ipynb`. Gemma 4 31B through Ollama reformatted every
model's transcript of 15 arguments three ways: formatting only with the words
locked in code; plus removing doubled words and obvious mishearings; and a
conservative proofread.

- **Formatting alone helps every model, without changing a word.** Qwen3 goes
  from 15.70% to 13.48% verbatim - past Whisper, raw (14.70%) or formatted
  (13.92%). Granite Plus goes from 29.28% to 17.43%. Most of it is the
  reporter's "--" dash, which no speech model writes.
- **It holds on all 61 arguments** (run overnight 13 October, step 1, Qwen3
  only; `findings/llm-format/*-gemma4-31b-all.csv`). Qwen3 goes from 15.88% to
  13.45% verbatim, against raw Whisper's 14.75%. Formatting helped in 60 of 61
  arguments (the exception, 16-476, got 0.26 points worse) and put Qwen3 ahead of
  raw Whisper in 54. On the 46 arguments the 15-argument run never saw: 15.94%
  to 13.45%, the same gain. Standard rule: 4.90% to 4.53%. The formatted
  transcripts are on `D:/scotus-corpus/experiments/llm-format/`, outside the repo.
- **Letting the LLM change words helps some models and hurts others.** It helps
  Whisper, Voxtral, Canary and Granite a little, mostly by cutting stray junk
  words; it hurts Qwen3 and Parakeet, because it deletes repetitions the record
  keeps ("for -- for -- for years"). The best two results tie: Qwen3 formatted
  only (13.48%) and Whisper with light fixes (13.44%).
- **The formatting penalty** (verbatim minus the words-only rule) shrinks to
  about 7.7 to 9.4 points for every model. The rest needs the audio.
- **What the word-changing steps fixed and broke** (sorted by hand in October,
  not saved as a table). Fixed: misheard names and legal terms - "comedy" to
  comity, "council" to counsel, Breyer, Freytag, Blackledge, AEDPA, de minimis -
  and Whisper's stray junk words. Broke: repetitions the record keeps (3,877 at
  step 2), short words smoothed away ("is it there is" to "there is"), and at
  step 3 the speakers' grammar ("is" to "are"). Never fixed: words the speech
  model left out, mostly crosstalk. Across all seven models step 2 added about
  900 errors and step 3 removed about 300.
- **The "versus" line in the step 2 and 3 prompts backfired.** The LLM also
  rewrote spoken "Loving against Virginia" as "versus", and once "Bandemer and
  Vieth" as "Bandemer versus Vieth": about 126 words broken against 104 fixed.
  Drop it on any re-run.

## Where each kind of finding is written down

| Question | File |
|---|---|
| What are the seven models, and how is each used here? | `model-usage-notes.md` |
| What are the results, and which run produced them? | `findings/README.md` and the CSVs beside it |
| How do I run the pipeline and the tools? | `pipeline/README.md` |
| Why does the project exist, what is being measured? | `project-overview.md` |
| The eight questions the professor wants the proposal to answer | `heilmeier-summary.md` (short), `heilmeier-notes.md` (everything) |
| What do court transcription vendors claim? | `vendor-claims.md` |
| Can you get the audio of an FTR-recorded hearing? | `court-audio-access.md` |
| What did the scoping work in September assume? | `scoping-report.md` (a dated record) |
| Why did the laptop crash, and what stops it? | the GPU section at the end of `model-usage-notes.md` |
| The findings: which rules are right, serious errors per hour beside the error rate, doubt about the "true" transcript, the two judges (30 Oct, Sonnet on every case) | `notebooks/findings.ipynb` |
| The first write-up (seven engines, Supreme Court only, 13 Oct) | `notebooks/first-look.ipynb` |
| Can a local LLM fix the formatting? | `notebooks/llm-formatting.ipynb` |
| Can a language model judge the failure cases? | `notebooks/llm-judge.ipynb` |
| What are the flagged spots really, and how are they sorted? | `flagged-spots-review.md` |
| Which differences does the scoring forgive, and why? | `pipeline/scotus_asr/scoring/harmonise.py` |
| How to run a language model on this card safely | the Ollama paragraph at the end of `model-usage-notes.md` |
| How would the models do on accented or unclear speech? (started: EdAcc) | `future-work-harder-speech.md` |
| What to look for with the LLM judge: inversions, a trust map, who's right, how much needs an LLM | `future-work-llm-judge.md` |
| How to run over another corpus, or compare any set of models | `pipeline/README.md` ("Other corpora"), `pipeline/scotus_asr/corpora/`, `pipeline/scotus_asr/model_sets.py` |
| ASR, beam search, or both? The options taken to the professor, and what he said | `professor-meeting-2026-10-15.md` (kept out of git; on disk only) |
| Do vendors overstate accuracy off the record? Did lawyers go back to stenographers? | `digital-reporting-claims.md` (17 Oct: FTR's homepage says 98%; no documented regret wave) |
| Does the winner change with the scoring rule, argument by argument? (Figure 1) | `findings/flip/` (`tools/flip.py`) |
| Does the error model hold in every term? | `findings/error-model/three-engines-by-term/` |
| The numbers for the midterm's results section | `midterm/numbers-pack.md` |
| The midterm's methods, as an outline with every number's file | `midterm/methods-outline.md`; hours and the record fixes in `findings/corpus/` (`tools/corpus_table.py`) |
| The website, and how it is rebuilt | `site/` (`tools/build_data.py`, then `tools/build_site.py`); published at https://claude.ai/artifact/3Q9MW1VB1ZgMNPPkLsTELX |
| What runs when I say "do some ASR work" | `pipeline/overnight-queue.csv`; `overnight_watch.py --queue` for progress |
| The plan for the next session (paste it in plan mode) | `next-session-plan.md` (carried out 18-19 Oct) |
| CORAAL and Earnings-22: size, licence, format, how others scored them | `datasets/coraal.md`, `datasets/earnings22.md` |
| One recording at a time: transcripts side by side, errors highlighted, its files | the whole-recording pages, one per data set (`tools/build_explorer.py <data set>`, `tools/explore_local.py <data set>`; URLs in `tools/explorer_page/published.json`) |
| Words engines wrote into quiet audio | `findings/invented-words/` (`tools/find_invented_words.py`) |
| What does a language model say about the failure cases? | `findings/judge/` (`tools/judge_failures.py`) |
| The shared widgets every page uses, and the browser check | `web/widget/`; `tools/check_page.py` |
| What is a "true and accurate" transcript, and according to whom? Law (28 U.S.C. § 753(b), CPLR 5525), NCRA opinions, Hansard, history, linguistics, ASR styles (3 Nov; quotes still to check in a library are listed at the end) | `literature/true-and-accurate-transcripts/report.md`, sources in `notes/` |

`model-usage-notes.md` is the one to read before touching any engine. Its rule -
**a documented maximum is not a quality threshold** - was written after two
settings taken on trust cost a run each.

## Open work, roughly in order of value

**1. The human floor. Nothing else scales the results without it.**
A verbatim error rate of 15% means nothing until somebody knows what two
professionals score against each other. Oyez does not work for this - it appears
to edit the Court's own transcripts rather than transcribe independently. Three
routes, best first:

- commission a certified reporter for one or two arguments from the same audio;
- ask Heritage Reporting whether draft and final transcripts differ, and by how
  much;
- ask Oyez directly how theirs are produced, which settles it either way.

New in October 2026, and now the plan: federal bankruptcy courts sell the FTR audio
and the filed transcript of the same hearing for a few dollars, and I hold an RPR, so
I can make the second transcript myself, blind. Budget about $100. The steps, and how
to choose hearings, are in `court-audio-access.md` ("The $100 plan"). Next action:
register for PACER, then pick hearings on CourtListener.

**1b. Ask Taylor Jones for the "Testifying while Black" audio** (added 1 November 2026).
The 83 stimulus clips the 27 Philadelphia court reporters transcribed are not published;
with them the engines could be scored on the same audio as the reporters. A draft email is
in `midterm/drafts/email-taylor-jones.md` (local only, git-ignored), for Noah to send
himself. Nothing here sends messages on his behalf (see `CLAUDE.md`).

**1c. Ask CUNY's HRPP before collecting anyone's ratings** (added 7 November 2026). The
public site will let people make an account and rate clips (Cloudflare Pages plus
Firebase, chosen 7 Nov; `going-public.md`). Analysing those ratings is probably human
subjects research, likely exempt, but the HRPP decides. A draft email is in
`midterm/drafts/email-hrpp-ratings.md` (local only, git-ignored), for Noah to send himself
after telling his professor. Noah's own ratings don't wait for this.

**1d. Deploy the public site** (built 7 November 2026). `tools/build_public.py` writes
`public/` (git-ignored): the site and the four whole-recording pages as a normal static
site, plus accounts, `rate.html` (the bench's questions, blind to the judge until saved),
an admin CSV export and the privacy and contributor pages. Checked in Edge in its test
mode by `tools/check_public.py`; Firebase and `hosting/firestore.rules` are untested until
the project exists. Noah's steps, about 2-3 hours: `hosting/SETUP.md`. Ratings stay
limited to the allowlist until the HRPP answers (1c). Made ready for Cloudflare on 8 Nov
(`hosting/cloudflare-readiness.md`): security headers and a strict Content-Security-Policy,
a small `_worker.js` so clips can start mid-file (Pages can't otherwise), a real 404.
Two decisions still Noah's: the contact address and the date emails are deleted (SETUP
step 0); then the go-live checklist at the end of SETUP.

**2. Listen, on the listening bench** (https://claude.ai/artifact/EXPd6H8ScWUMjqhpZZrDgs,
private). 200 random flagged spots, each with audio
and every model's words (each word highlighted as the clip plays), built by
`tools/build_listening_page.py`. Labelled by the rules in
`labelling-guidelines.md`: once, by ear, ticking eight yes/no questions, then who
is right - blind to the sorter's and the judge's labels (kept in `answers.json`
beside the page). The reading pass was dropped on 15 October. The guidelines are at
version 0.2: pilot 20 spots, fix them, freeze as 1.0, then run
`judge_spots.py --bench` and compare. Then compare: how often
the rules and the judge agree with the ear is the number that says whether the
counts in `findings/crowd/` can be quoted. The page keeps every label in the
browser as well as the account, and says beside the count which one is saving
(fixed 12 October, after the account's copy was found empty).
When the labelling is done, press "Copy all labels" and paste into a JSON file,
or Claude exports the page's `labels-v02` collection; then run
`python tools/compare_labels.py --labels <file> --answers findings/crowd/listening-bench-answers.json`.
Also still to hear:
- the small-word spots in `findings/crowd/against-the-record.csv`, where all the
  machines heard one thing and the record has another. These are where a
  reporter's slip or edit would show, and a reporter is the right judge.
- the silence list at the end of the notebook: 12 moments, 52 seconds in all,
  where every model wrote nothing and a speech detector hears speech. This replaces
  the old "eighteen", which compared four models before the September fixes.

**3. Before the next corpus run** - done 16 October 2026, apart from the last
sentence. Every engine, Whisper included, now calls `gpu.prepare_gpu` before
loading: it refuses if PyTorch sees no card (the processor-only build), checks
free memory against the engine's own `APPROX_VRAM_GB`, and sets the ceiling.
The ceiling is worked out from the card in use (leave 8%, at least 1.5 GB, and
never plan on what other programs hold), which is the old 92% on the 5090, so
nothing measured there changes. Qwen3's figure is 16 GB: it peaked at 14.4
GB on OT2010, well above the first estimate of 10. The aligner's precision is now its own
setting, `engine_options: {aligner_compute_type: ...}`, recorded in every
result; left unset it keeps the old rule (float16 for Qwen3 and Canary, float32
for Voxtral and Granite), so the published runs stay reproducible. **Still to
decide:** whether new runs should all use one aligner precision - doing so
changes Qwen3's timings between OT2017 and later terms. Then the six copies of
the chunk loop could become one helper in `asr/base.py` - not done yet because
it changes the engines that produced the published numbers.

**3b. Qwen3's repeats at the joins between its pieces** (found 19 October 2026 while
picking Figure 1's clips). The scoring removes words written twice where two 280-second
pieces overlap only when the repeat matches word for word; "seatbelt" against
"seatbelts" breaks the match and the whole repeat stays. In OT2017 the 10 seconds round
each join hold 37% of Qwen3's added words in 7.4% of the time: about 1,700 extra words,
0.26 points of its error rate on both rules. No ranking or finding changes. A looser
match in `scoring/seams.py` would fix it, but it changes the scoring behind the
published numbers, so it waits for a decision.

**4. A frontier model for the formatting.** The same tool, the same 15
arguments, with Claude or another hosted model in place of Gemma: one more
backend in `ask()`. The transcripts are public domain. Worth trying the step 1
prompt first, since it is the one that helped every model. Then a narrower
word step than step 2: allowed to fix names and legal terms only, never
repetitions or grammar, which should keep most of the fixes and little of the
damage.

**5. The other fourteen terms.** 148 arguments of 1,037 have been transcribed,
but outside October Term 2017 only by Whisper. Checked on `D:` on 16 October 2026:

| What | Arguments | Models | Run |
|---|---|---|---|
| October Term 2017 | 61 | all seven | the runs listed in `findings/README.md` |
| October Term 2010 | 77 | Whisper only | `run-20260918-035220`, the same run as Whisper's 2017 cases |
| October Term 2025, the first corpus trial | 8 | Whisper only | `run-20260917-041257` |
| Hand-checked sample: Braidwood (OT2024), Callais (OT2025) | 2 | Whisper only | `runs/run-20260916-041602` (Kasten, its third case, is one of the 77) |

The 2010 scores had never been reported. They are Whisper's only result outside
2017. Re-scored with the October fixes on 16 October 2026
(`findings/harmonise/run-20260918-035220/`, by `tools/rescore_harmonised.py
--run`, 15 seconds on the processor):

| Whisper | arguments | benchmark rule (leaderboard) | benchmark rule | verbatim rule |
|---|---|---|---|---|
| OT2010 | 77 | 6.77% | 6.32% | 15.76% |
| OT2017 | 61 | 6.16% | 5.71% | 14.53% |
| OT2025 trial | 8 | 6.12% | 5.67% | 14.90% |

The 2017 row reproduces the published table exactly, which is the check that
the 2010 row was scored the same way. So 2010 looks somewhat harder for Whisper,
by about 0.6 points on the benchmark rule and 1.2 verbatim. One model and one
other term - not a finding yet. The three sample cases are in
`findings/harmonise/run-20260916-041602/`; their transcripts are not in git, so
those numbers can only be remade on the 5090 laptop.

Still to do, in order:

- ~~Re-score the 2010, 2025-trial and sample runs with the October fixes~~ -
  done 16 October 2026, above. "Before" matched each run's own saved scores to
  within 0.009 points (one case, 09-571, whose reference was re-read a day after
  scoring and lost one word).
- ~~`tools/llm_format.py` and `tools/build_listening_page.py` broken~~ - fixed
  16 October 2026: both read files through the model set, as `crowd.py` does.
  A rebuild of the listening page gives the same 200 spots; only the judge
  columns of `findings/crowd/listening-bench-answers.json` are behind (the judge
  now gives primary and secondary labels and has judged 10 of the 200, not 1).
  The planned `judge_spots.py --bench` run will bring that file up to date.
- The corpus location now comes from `asr-capstone/local-paths.yaml` (not in
  git; copy `local-paths.example.yaml`). Configs say `{scotus_corpus}/runs`.
  This laptop has the file; a fresh clone on the 5090 laptop needs it made.
- ~~Sanity-check the early Whisper runs~~ - done 16 October 2026, because they
  were transcribed before the September bug fixes and before each model got its
  own settings. They hold up. Whisper's engine code has changed only twice since
  (load the model once a run; record the settings used), neither of which
  changes the words, and its settings are the same as today's. The published
  2017 Whisper figures come from the same run as the 2010 cases.
  `sanity_check_run.py` results: 2010 + 2017, 1 of 138 flagged; the 2025 trial,
  3 of 8; the three sample cases, none. Every flag is either words repeated at a
  join between two pieces of audio (`09-150`, `25-112`, `25-466`), which the
  scoring step already removes, or `25-406`, flagged as a loop at 256 words a
  minute but in fact 25 seconds of real, fast speech - the check's limit is 250.
  No re-transcribing needed.
- Item 3 above, then the three default engines (Qwen3, Whisper, Parakeet) on
  2010, so the comparison across terms rests on more than one model.
- Then everything else: twelve terms not started at all (OT2011-2016 and
  OT2018-2023), plus 61 of 62 arguments in OT2024 and 49 of 58 in OT2025 - 889
  arguments. Nothing new has to be built; it is machine time. Re-run Qwen3 and
  Canary for honest speeds while at it.

**The near target (16 October 2026): about 250 arguments with all or most
models**, run overnight and during office days on the 5090 laptop. Started the
night of 16 October: Parakeet then Qwen3 on 2010 (for the midterm), then
Parakeet, Whisper and Qwen3 on 2021, then the same on 2025. Since 17 October the
queue is a file, `pipeline/overnight-queue.csv`, run by `pipeline/overnight.ps1`
and looked after by the `asr-work` skill (`.claude/skills/asr-work/`): say "do
some ASR work" or "good night", at any hour, and Claude checks the card and starts
it, then a background supervisor agent checks the first output of each item,
restarts it after a crash, confirms progress is saved and keeps `overnight-log.md`,
while the conversation stays free. Say "stop the ASR work" or "good morning" and it
stops after the recording in progress and reports.
17 October: 2010 is done for the three default engines. Qwen3 ran at about 10x
real time, not the 4.6x in the table above, which confirms that figure was
measured while the card was paging. Both new runs pass `sanity_check_run.py`
(the one pace flag, 09-1159, is a fast speaker in Stanford v. Roche, read and
coherent). Re-scored with the October fixes (`findings/harmonise/run-scotus250-*`):

| Engine | benchmark rule, OT2017 → OT2010 | verbatim rule, OT2017 → OT2010 |
|---|---|---|
| Qwen3 | 4.44% → 5.79% | 15.55% → 17.01% |
| Whisper | 5.71% → 6.32% | 14.53% → 15.76% |
| Parakeet | 6.94% → 7.84% | 18.18% → 18.68% |

2010 is harder for all three, the order holds (Qwen3 first on the benchmark
rule, Whisper first verbatim), and every engine is still 2.4 to 2.9 times worse
as a record. Qwen3's lead over Whisper on the benchmark rule shrinks from 1.3
points to 0.5. Not yet looked at: why 2010 is harder (recording quality, more
crosstalk, the reporter's conventions that year).
**18 October: the near target is met for the three default engines.** Parakeet,
Whisper and Qwen3 now cover all four terms, 258 arguments: OT2017 (61), OT2010
(77), OT2021 (62), OT2025 (58). The queue ran from 09:59 on 17 Oct to 19:12 on
18 Oct with no restarts and no failed recordings. Whisper's 2010 is the September
run, not redone. Benchmark and verbatim rules, after the October fixes
(`findings/harmonise/`):

| Engine | OT2010 | OT2017 | OT2021 | OT2025 |
|---|---|---|---|---|
| Qwen3, benchmark | 5.79% | 4.44% | 3.95% | 4.14% |
| Whisper, benchmark | 6.32% | 5.71% | 5.51% | 5.82% |
| Parakeet, benchmark | 7.84% | 6.94% | 5.85% | 6.31% |
| Qwen3, verbatim | 17.01% | 15.55% | 15.21% | 15.47% |
| Whisper, verbatim | 15.76% | 14.53% | 14.72% | 15.07% |
| Parakeet, verbatim | 18.68% | 18.18% | 17.20% | 17.38% |

The order is the same in every term: Qwen3 first on the benchmark rule, Whisper
first verbatim, Parakeet last on both. 2010 is the hardest term for all three.
(23 October: those Parakeet rows are from before its full-stop fix. Fixed: 6.54%,
5.77%, 4.95%, 5.36% benchmark and 17.55%, 17.18%, 16.43%, 16.56% verbatim, so it is
now second on the benchmark rule in OT2021 and OT2025. `midterm/numbers-pack.md` R3.)
Canary, Voxtral, Granite and Granite Plus stay on hold in the queue file
(backfill only if a result calls for it). Both analyses re-run on all four terms
the same day: the argument-by-argument flip holds in every term (`findings/flip/`;
since 2020 Qwen3 wins every argument on the benchmark rule, Whisper about 72% of
them verbatim), and so does the error model (`findings/error-model/three-engines-by-term/`;
conditions 21-39 times the engine in every term; 60-78 times since Parakeet's full-stop fix). The seven-engine parts (the
crowd, the vote) stay OT2017 only.

**27 October: ten terms done for the three default engines.** The queue (25-27 Oct,
no failures) added OT2013 (70), OT2015 (69), OT2019 (58), OT2020 (57), OT2022 (57) and
OT2023 (60), then ran Parakeet again with the per-frame cap on its 67 piled-up
recordings (`run-*-parakeet-capped`; 18-1323 10.59% → 5.81%, 13-1339 8.25% → 7.24%,
the rest within 0.2 points). Average per argument, after harmonising, Parakeet with
the capped re-runs swapped in:

| Engine | OT2013 | OT2015 | OT2019 | OT2020 | OT2022 | OT2023 |
|---|---|---|---|---|---|---|
| Qwen3, benchmark | 6.98% | 5.58% | 4.19% | 4.08% | 4.18% | 4.27% |
| Whisper, benchmark | 7.21% | 7.20% | 5.65% | 5.73% | 5.85% | 5.90% |
| Parakeet, benchmark | 7.69% | 6.81% | 5.30% | 4.58% | 5.06% | 5.22% |
| Qwen3, verbatim | 15.81% | 14.34% | 15.03% | 13.91% | 15.44% | 15.54% |
| Whisper, verbatim | 14.23% | 14.25% | 14.76% | 15.33% | 15.25% | 15.31% |
| Parakeet, verbatim | 16.35% | 15.41% | 16.23% | 16.08% | 16.45% | 16.48% |

Qwen3 is first on the benchmark rule in every term and Whisper first verbatim in every
term but one: OT2020, argued by telephone, where the justices took turns and hardly
anyone talked over anyone, Qwen3 is first on both. That fits the crosstalk finding.
Not yet re-run on the new terms: the flip, the error model and the failure searches
(`lineup.PARTS` still lists the original four terms; adding six would about double the
cases, and the cost of judging them).

The parser used to stop 20-1530's record (West Virginia v. EPA) at a mid-argument
recess on page 64 of 151, so it held 10,001 of 22,307 words and every engine
scored about 120% on it. Fixed 17 Oct; it was the only one of 1,037 transcripts
affected. Parakeet's OT2021 benchmark average went 8.18% → 6.26%, Whisper's
7.89% → 5.94%. Old files kept in `D:/scotus-corpus/superseded/`.
Also fixed 17 Oct, before any 2025 run started: eight PDFs whose margin numbers sit
in the same piece of text as the words used to parse to an empty record. Three are
OT2025 (24-699, 24-781, 24-993); the other five are OT2019-2020, outside the study.
No record that already parsed changed.
Fixed 20 Oct: in most OT2013 and OT2014 PDFs (and three OT2015 ones) the margin
number sits 3.4 points above its words, so only the first line of each turn was read
(12-872: 1,790 words of about 9,200). `extract.py` now joins a bare number to the words
just below it; every OT2010-12 and OT2017-25 record parses identically. The OT2013
Parakeet and Whisper records were rebuilt and re-scored 21 Oct (standard-rule medians
8.8% and 7.1%); old files in `D:/scotus-corpus/superseded/2026-10-20_OT2013-records-line-numbers/`.
Still open: 12-9012 (Robers) scores about 24% for every engine against a 9,434-word
record while each engine writes about 11,000, so that record looks short for another reason.

- Proposed terms: 2010, 2017 (done), 2021 and 2025 - 258 arguments, spread
  across the span, with two terms on each side of the 2020 change. Arguments
  were about an hour each through 2019 and run 80 to 93 minutes since, so the
  recent terms cost about half again as much per argument. OT2020 (argued by
  telephone) is left out on purpose; it is its own condition, worth a later look.
- New audio to transcribe: 76 hours (2010), 87 (2021), 86 (2025).
- Machine time, from the speed column above, one model at a time:

  | models | hours |
  |---|---|
  | all seven | about 300 |
  | six, without Granite Plus | about 145 |
  | five, without either Granite | about 110 |

  Granite Plus alone is half the total: it runs at 1.6x real time, and its
  verbatim figure measures IBM's choice to drop punctuation anyway. Qwen3 and
  Canary were timed while the card was paging, so their share is probably an
  overestimate. A 12-hour night does about a twelfth of the six-model job.
- One run per model, all three new terms at once, under a fixed name so each
  night carries on where the last stopped:
  `python -m scotus_asr.cli run --config config/qwen3.yaml --term 2010 --term 2021 --term 2025 --run-id run-scotus250-qwen3`
  Whisper skips 2010 - its 2010 transcripts in `run-20260918-035220` passed the
  sanity check and used today's settings, so redoing them would only cost hours
  and electricity: `--config config/corpus.yaml --term 2021 --term 2025`. (The
  hour estimates above already leave it out.) Without `--run-id`, a command
  continues the most recent run, which is the wrong one when switching models.
- Pausing: start each run in its own PowerShell window, not inside a Claude
  session, so it survives the session closing. To pause without losing anything,
  from any other window: `python -m scotus_asr.cli stop --config <same config>
  --run-id <same name>` - it finishes the argument it is on, then ends (added
  16 October 2026; `pipeline/README.md`, "Stopping and starting again"). Ctrl+C
  stops at once but restarts the argument in progress: about 5 minutes lost for
  Whisper, 20 for Qwen3, 55 for Granite Plus on a recent 85-minute argument. To
  resume either way, run the same command. If a script runs several models in a
  row, end it on exit code 130 so a stop does not start the next model.
- Before the first night: item 3 above (the memory protection matters most when
  nobody is watching), `ollama stop`, and Windows sleep turned off while plugged
  in. Afterwards: `sanity_check_run.py` on each run, then a model set like
  `config/model-sets/scotus-seven.yaml` pointing at the new runs.

## Things deliberately not done, so they are not rediscovered as ideas

**Dropped in October 2026:** fine-tuning a model on court audio (LoRA), and
checking names against each case's briefs. Fine-tuning was dropped because
training on some Supreme Court arguments and testing on others means the same
justices, room and microphones, so it would overstate what fine-tuning does in
the real world. **Back in on 16 October** as an honest best-case test (H6 in
`heilmeier-notes.md`): if fine-tuning cannot fix crosstalk even with the same
justices, room and microphones, it will not fix it elsewhere. Gains are reported
only as a ceiling. Also not pursued: a commercial API
comparison (Gemini and the rest), and streaming models.

**Canary-Qwen-2.5B was researched and cannot run on this laptop.** No
transformers path, NeMo will not install on Python 3.14, and NVIDIA support
Windows only through WSL2. Written up in `model-usage-notes.md`.

**The two Granite models keep a residual loop rate** of 0.065% and 0.057% of
their words. Splitting the audio and re-decoding at higher temperatures were both
tried; combining them might recover some of it, for several hours of machine time.

**Seam duplication is corrected at scoring time, not in the engines.** The
transcriptions on disk are what the models produced, which is the evidence.
Every tool that reads them back must load them through
`stages._load_asr_result`, which applies the correction. Four tools did not until
October 2026, and their tables were regenerated.

## Before running anything again

```powershell
# which laptop is this, and is the card free?
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
# a loaded Ollama model sits on ~21 of the 24 GB
ollama stop
```

Then, for a model whose settings have not been checked lately:

```
python tools/check_granite_plus_conformance.py     # engine against IBM's live card
python tools/chunk_sweep.py --engine <name>        # before trusting any chunk length
python tools/sanity_check_run.py --run <run dir>   # after any run, before believing it
```

`sanity_check_run.py` is the one that earns its keep. It asks whether the output
is a coherent transcript of the recording at all, which is a cruder question than
word error rate and has to be settled first - both of the faults fixed in
September were found with it rather than by scoring.

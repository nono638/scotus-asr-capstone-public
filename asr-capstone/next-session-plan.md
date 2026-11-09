# The plan for the next session (written 18 October 2026)

Paste the block below into a new session in plan mode. It runs the next steps in
order, with subagents for research and independent work. The listening bench is left
out on purpose: that step is Noah labelling by ear, and step 4 gives it 30 new
candidates.

```
Read asr-capstone/WHERE-I-LEFT-OFF.md, asr-capstone/app-roadmap.md and
asr-capstone/midterm/numbers-pack.md first. Then plan, and after I approve, carry out
these steps in order. Use subagents for research and for independent pieces of work,
but check what each one produces yourself before building on it: re-run its numbers,
read its files. Commit after each step, and push when a step is finished. Tell me in
a few lines when each step is done before starting the next.

1. Midterm methods outline (due 28 Oct). Write asr-capstone/midterm/methods-outline.md:
   corpus and terms, the engines and their settings, the three scoring rules and the
   October fixes, the per-argument flip, the error model, EdAcc. Outlines and numbers
   only; I write the prose. Every number must trace to a file in findings/.

2. CORAAL scouting (a subagent). Size, licence, download, transcript format and its
   conventions (pauses, unintelligible stretches, redactions, overlapping speech), and
   how Koenecke et al. 2020 scored it. Write asr-capstone/datasets/coraal.md. Stop and
   ask me before downloading anything over a few GB.

3. CORAAL onboarding, once I approve the download. A corpus reader in
   pipeline/scotus_asr/corpora/ like edacc.py, with tests, plus a settings file in
   config/corpora/. Put the general part (reading time-stamped transcripts) where
   app-roadmap.md phase 1 says the reference readers go, so the next dataset reuses
   it. Try 2 recordings with --limit, then add CORAAL rows to
   pipeline/overnight-queue.csv after EdAcc dev and before the Supreme Court terms.
   No long GPU runs; the queue does those.

4. Invented-words hunt (a subagent; no GPU). Using check_silences.py and the saved
   runs, find words an engine wrote where the record has nothing and the audio is
   quiet, on the four finished terms and EdAcc. Write findings/invented-words/ with a
   README and the 30 clearest cases for the listening bench.

5. Earnings-22 scouting (a subagent), as in step 2. Write
   asr-capstone/datasets/earnings22.md. No download.

6. Make the website flashier and interactive, with a gallery you can listen to. The
   site is tools/build_site.py -> asr-capstone/site/, published privately to
   https://claude.ai/artifact/3Q9MW1VB1ZgMNPPkLsTELX (republish to that same link).
   Build it the way app-roadmap.md "One set of widgets on every page" says: shared
   widgets in web/widget/ (Listen, Compare, Chart, Table), each written once and used
   by every page, so a visitor learns them once - above all the audio ones.
   - Interactive charts: Figure 1 with one dot per argument, a switch between the
     scoring rules, a term filter, hover to see the argument and both rates, and
     click to hear that argument. Make the coverage grid and the error-model results
     interactive the same way. Load any chart library from cdnjs at a pinned version,
     or draw SVG by hand; keep the static PNG for the paper.
   - Look and feel: a more editorial, distinctive design - a strong opening that
     states the finding, the "flip" made vivid, more visual weight on the numbers.
     If a design plugin or skill is available (check /plugin and the skills list),
     load it and say which one you used; if none is, say so. Keep it readable on a
     phone and in dark mode, and keep every number traceable to findings/.
   - Gallery: each passage uses the Listen and Compare widgets. A play button, a
     choice of clip lengths (e.g. 5, 10, 20 seconds around the spot), and Qwen3's
     transcript highlighted word by word as the audio plays, with the record's words
     beside it. Make Listen from the player and clip-cutting already in
     tools/build_listening_page.py and tools/listening_page/template.html, not a
     second player; move it into web/widget/ so both the gallery and the listening
     bench load it, and check the live listening bench still builds and plays. Clips are separate audio files published with the page (the
     artifact limits are 16 MB for the page, 15 MB a file), cut only from Supreme
     Court audio, which is public domain. Check EdAcc's licence before publishing any
     EdAcc clip, and leave EdAcc out if it is unclear.
   - Pick about 12 passages: the non-crosstalk passages no engine got (as now), plus
     the clearest invented-word cases from step 4. Each card says what kind of error
     it is and that it is not yet checked by ear.
   - Add a short section for steps 4 and 5.
   - Before publishing: open the built page, play two clips at each length, and
     confirm the highlighting follows the audio. Switch the rules and filters on
     each chart and click a dot to hear it. Tell me what you checked.

Don't start the ASR queue unless I say "do some ASR work". Don't change anything
under runs/ or D:/scotus-corpus/cases.
```

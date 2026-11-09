# Midterm: what's left (written the night of 7 November 2026, for Sunday 8 November)

The draft is `midterm/draft.md`, committed and pushed. Due Sunday evening.

## Where the draft stands

| Section | State |
|---|---|
| 1. Introduction | **not written** (about 20 minutes of questions with Claude) |
| 2. Literature review | drafted: 2.1 reference is a judgment, 2.2 styles differ, 2.3 machines hear what they expect, 2.4 errors differ in weight, 2.5 Atwany et al. |
| 3. Data and methods | drafted: 3.1 data, 3.2 engines (Table 1), 3.3 scoring (Table 2, NCRA vs normaliser), 3.4 judges, 3.5 problems along the way |
| 4. Preliminary results | drafted: 4.1 how good the engines are (Table 3), 4.2 the flip (Figure 1), 4.3 errors that matter |
| 5. Limits and next steps | **not written**; Claude drafts it from the notes at the end of `draft.md` |
| References | **not compiled**; Claude builds the list from the citations in the draft |
| AI-use disclosure | **not written**; your decision what it says (course rules) |

## In order

1. **Check the spacing rule** in the syllabus or assignment. Sections 2-4 are already about
   5,600 words. If the 10-12 pages are double-spaced (about 3,000-3,300 words), about a
   third has to go. Easiest cuts: the NCRA table down to five rows; merge the normaliser
   material in 2.2 and 3.3; 3.5 to two sentences; the last paragraph of 4.3.
2. **Check whether a code walkthrough is still due with the draft.** `WHERE-I-LEFT-OFF.md`
   says "draft and code walkthrough". If it is, ask Claude for a one-page plain map of the
   pipeline.
3. **Introduction** with Claude.
4. **Section 5** and the **reference list**, Claude drafts; you read.
5. **Pick one or two figures** from `midterm/figures/candidates/` (contact sheet:
   `00-contact-sheet.png`; captions and the agent's top three in its README).
6. **Read the whole draft once, aloud if you can.** Change anything that doesn't sound like you.
7. **Read the cited passages** (list below). About 2 hours.
8. **Decide the open checks** (below).
9. Paste into your document, add the AI-use disclosure, format, submit.

## Open checks in the draft

- 2.1: open the *People v. Parris* opinion, 4 N.Y.3d 41 (2004): https://www.nycourts.gov/REPORTER/3dseries/2004/2004_09408.htm
  (it's cited from summaries; the court's site refused automated access).
- 2.3: MacKay chapter and section numbers for the noisy-channel idea (chapters 1-3).
- 2.3: your call whether to keep Jones et al. 2019 (court reporters' accuracy on African
  American English). It's published research, not reporters disagreeing, but it's sensitive.
- 3.5: the AI-use disclosure the course requires, and the repository link.
- 4.3: one figure marked ⟳ (Whisper and Qwen3 restarts and African American English
  grammar), measured before the repairs.
- End of section 3.3: the NCRA and federal-guide references to add to the list.

## The reading pack: what to read, and what the draft uses it for

Read the abstract and the passage named. Confirm it says what the draft says.

| Source | Read | The draft uses it for |
|---|---|---|
| Atwany et al. 2025 (`literature/pdfs/atwany-2025-...pdf`) | abstract; §4.1 Datasets; "Impact of Architecture and Scale"; the judge prompt in the appendix | 20+ models, ~10 data sets; "low WERs may conceal dangerous hallucinations"; encoder-only models hallucinate least; reference as "The original, accurate text"; grammar differences = "No Error" |
| Radford et al. 2023 (Whisper paper) | §2.3 (decoder); Appendix C (normaliser) | "audio-conditional language model"; normaliser built for "innocuous" differences, may overfit to Whisper's style |
| NCRA, "What is an Error?" (March 2026) (`literature/pdfs/ncra-2026-what-is-an-error-rpr.pdf`) | both pages | every row of Table 2 |
| Guide to Judiciary Policy, Vol. 6, § 520.40.10(b) | the "Editing of Speech" paragraph (URL in `literature/true-and-accurate-transcripts/report.md`) | fillers normally out unless they change meaning; grammar "transcribed as spoken" |
| Glenn et al. 2010 (LREC) | results on careful transcription | 4.1-4.5% disagreement; 95% judgment calls |
| Koenecke et al. 2024, "Careless Whisper" | abstract | about 1% invented phrases, 38% harmful, courtroom risk |
| Koenecke et al. 2020 (PNAS) | abstract; methods on normalisation | 0.35 vs 0.19 WER; "aks" to "ask", fillers removed before scoring |
| Martin & Tang 2020 | abstract | habitual "be", "I'll be" |
| McNamara et al. 2024 | the results table | OpenAI engine 6.4% clean, 13.1% verbatim on Earnings-22 |
| Gandhi et al. 2022 (ESB) | abstract | keep punctuation and casing |
| Sanabria et al. 2023 (EdAcc) | results table | best engine 19.7% on the test set |
| *People v. Parris* (2004) | the holding | reconstruction hearings |
| Warren 1970 | the one-page result | the cough in "legislatures" |

Second-hand in the draft, and said so: Fraser (via Haworth et al. 2023). Cited from a summary
until you read it: *Parris*.

---

## Overnight results (not midterm work; for after you submit)

**Login and database review** (`hosting/AUTH-REVIEW.md`). Verdict: keep what was built.
Firebase Authentication and Firestore are the standard, maintained choice; the site's forms
only call Firebase, so nothing about passwords or sessions is home-made. FirebaseUI isn't
worth switching to (v7 is beta and needs a build tool; v6 is archived). Risks to fix
before go-live: (1) every refused save shows "invited testers only", which would hide a
rules mistake and confuses people right after they confirm their email; (2) the live
"fewest ratings" counter can be inflated or jammed by one bad actor; (3) a tampered rating
could carry the wrong licence into the CSV split; (4) passwords: the form asks 8, Firebase
enforces 6, NIST's 2025 guidance says 15. Your decisions: the password minimum; live
counter or counts updated at each rebuild; when to switch on App Check (anti-abuse); the
date accounts are deleted; where CSV backups are kept. Setup about 3.5-4.5 hours. The
security rules are untested until a real Firebase project exists.

**Figures for the paper** (`midterm/figures/candidates/`, contact sheet `00-contact-sheet.png`,
captions in its README, rebuilt by `midterm/figures/make_candidates.py`). 14 charts and 3
tables. Claude's picks: **03** (the flip, one dot per argument, 190 of 258 in the shaded
corner) and **05** (the benchmark winner reverses meaning most: 146 / 121 / 80). **02** (the
two rules crown different engines) is a simpler alternative to 03. Also strong: 08 (what
surrounds a word matters more than the engine) and 12 (which engine wins depends on which
human transcript is the reference). Skip or retitle 13: it compares averages computed two
ways. The one number that didn't match the draft (Qwen3 fluent errors on CORAAL, 28% not
29%) is fixed.

**Nemotron on RunPod** (`runpod-nemotron-estimate.md`; research only, nothing rented or
spent). On an RTX PRO 6000 (96 GB, full precision, $1.69/h Community, $2.49/h Secure):
a 5-argument pilot about $3.50; the four Supreme Court terms (310 h) about $6; all four data
sets (625.5 h) about $12, range $5-28. So the pilot plus all four terms fits in $25 whatever
the speed; everything fits at the middle estimate but not at the slow end. Biggest unknown:
speed on hour-long recordings with word timings on (estimated 40-300x real time; NVIDIA's
260-410x is for short clips), so time the pilot first. Terminate the pod when done: a
stopped pod still bills its disk (~$30 a month for 150 GB). Corrections: the model is 34B
parameters (67.5 GB at full precision), and it is not listed for any 24 GB card, so the
laptop is out except an untested 4-bit build. The licence puts no limits on the outputs.
Hosted alternatives: DeepInfra $0.12 per audio hour (all four data sets about $75). Not
counted: the work of plugging it into the pipeline as an eighth engine (Claude's time, not
money). A post-midterm decision.

**Public site, ready for Cloudflare Pages** (`hosting/cloudflare-readiness.md`; go-live
checklist at the end of `hosting/SETUP.md`). All 323 checks pass locally. Main problem found
and worked around: Cloudflare Pages ignores requests for part of a file, so clips started
from 0 s instead of their place in the recording (and Safari may refuse such audio). A small
script (`_worker.js`) now serves the audio properly; only audio goes through it, so the free
plan's request limit is used only by audio. Also added: security headers, a 404 page, page
descriptions, a favicon, robots.txt, a Contact section, two colours darkened for
readability, and a privacy line saying the pages load fonts and sign-in code from Google.
Not verifiable until it's live: that Cloudflare routes only the audio through the script,
and the script's time on the free plan (`check_public.py --live <url>` checks both). Your
decisions: a contact address (not necessarily your personal email) and the date stored
emails are deleted (new step 0). Note: new Firebase projects don't allow `localhost` for
sign-in by default; add it in step 7. Ratings stay invite-only until CUNY's HRPP answers.

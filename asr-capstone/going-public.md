# Going public: licences, ratings and hosting

Researched online on 7 November 2026. These are research notes, not legal advice. I am
not a lawyer. Where a question really needs the data set's maintainers or CUNY to answer,
the note says so. "My reading" marks a judgement I made that no source states outright.
"Not verified" marks something I could not check.

## Summary

**Recommendation.** Host the pages and the audio on **Cloudflare Pages** (free) under a
domain of your own (about $11-12 a year). Keep accounts and ratings in **Firebase**
(Authentication plus Firestore, free Spark plan). The whole site today is about 1,400
files and 1.05 GB, and the largest file is 15 MB. That fits Pages' free limits (20,000
files, 25 MiB per file), so no separate audio bucket is needed yet. Firebase sends the
sign-up and password-reset emails itself and does not pause idle projects. Supabase is
the runner-up if you would rather have SQL. It needs your own email sender, and free
projects pause after a quiet week. Your own setup time is about 2-4 hours, plus a day or
two of coding for the login and rating pages. **Licences:** the Supreme Court material
is free to publish. EdAcc (CC BY-SA 4.0, checked in the licence file) and CORAAL
(CC BY-NC-SA 4.0) can go on a public site with credits. Earnings-22 should stay text
only. None of the six engines puts limits on publishing its transcripts. **Open risks:**
(1) CORAAL is non-commercial. Paying for your own hosting is fine. Ads, a paid tier, or
a paid app would not be, and a donate button is a grey area. (2) Collecting and
analysing people's ratings is probably human subjects research under CUNY's rules, so get
a CUNY HRPP decision before collecting any. A draft email is in
`midterm/drafts/email-hrpp-ratings.md`. (3) Earnings-22 audio has no licence, so only Rev
can say yes to clips.

---

## 1. Licences for a public site

The current notes (`datasets/coraal.md`, `datasets/earnings22.md`) judged private pages.
A public site is "Sharing" in the Creative Commons sense: making the material available
to the public. Every condition of the licences now applies in full.

### Supreme Court (audio and transcripts)

- **Source used:** supremecourt.gov only. The pipeline lists and downloads from
  `supremecourt.gov/oral_arguments/argument_audio/<term>` and
  `.../argument_transcript/<term>` (`pipeline/scotus_asr/corpus/listing.py`). Nothing in
  the pipeline reads Oyez. Oyez came up only in the scoping report, as a text compared
  against the official one.
- **Audio:** recorded by the Court. Works of U.S. government employees have no copyright
  (17 U.S.C. 105). The Court's audio page states no terms of use at all. It says
  recordings are posted "on the same day an argument is heard by the Court" [1].
- **Transcripts:** made by contract reporters, not by Court employees. The Court's page
  says "Heritage Reporting Corporation has provided transcripts for the Court beginning in
  October Term 2017" and Alderson before that, and that "Same-day transcripts are
  considered official but subject to final review" [2]. It states no copyright or terms.
  Section 105 covers employees, not contractors, so this is the one soft spot. Two
  things make the risk very small (my reading): the transcript is a word-for-word record
  of other people's speech in a public hearing, with little of the reporter's own
  creativity in it, and the Court gives it away free to everyone. `court-audio-access.md`
  also notes a 2009 Tenth Circuit decision that reporters do not own copyright in a
  transcript of others' words.
- **Oyez:** its copies carry Oyez's own licence. Creative Commons' 2003 write-up says Oyez
  audio is licensed with attribution, no commercial reuse, and share-alike, because Oyez
  edited it. Later Oyez transcript pages have been reported as CC BY-NC-SA 4.0 [3]. I
  could not open Oyez's current terms page (not verified). None of this applies as long
  as nothing from Oyez is used. **Do not mix Oyez audio, timings or speaker names into
  the public pages** without crediting Oyez and taking on its non-commercial terms.
- **Verdict:** publish freely. Credit the Court anyway, and say what was changed.

### EdAcc

- **Licence: CC BY-SA 4.0, confirmed.** The v1.0 item on Edinburgh DataShare
  (doi:10.7488/ds/7914, available since 15 April 2025) says "Recordings, linguistic
  backgrounds, data statement, and evaluation scripts are released on our website under
  CC-BY-SA" and ships a file `CC_BY_SA_license_text.txt`. That file is titled "Creative
  Commons Attribution-ShareAlike 4.0 International Public License" [4]. The arXiv
  abstract says the same, "CC-BY-SA" [5]. The Hugging Face card
  (`edinburghcstr/edacc`) says "Public Domain, Creative Commons Attribution-ShareAlike
  International Public License", which is muddled, but it links to BY-SA 4.0 [6].
- **One thing to know:** the first DataShare item (2023, doi:10.7488/ds/3832) was
  withdrawn "due to a change in the license for their reuse", and replaced, through
  ds/7848, by ds/7914 [4]. The pipeline downloads ds/7914 (`corpora/edacc.py`), which is
  the current one. Cite that DOI, not the 2023 one.
- **Consent:** the EdAcc site says "All contributors provided informed consent to publicly
  share their speech recordings and demographic information" (Edinburgh Informatics
  ethics approval, ref. 49776) [7]. So public clips are what the speakers agreed to.
- **What the licence asks:** credit, a link to the licence, a note of what you changed,
  and anything you adapt shared under BY-SA 4.0 as well. No limit on commercial use.
- **Verdict:** public clips and reference text are fine with the credit below.

### CORAAL

**Licence:** CC BY-NC-SA 4.0. The user guide says derivative versions "you develop and
wish to share with others must be distributed using the same license" (UG p. 16, quoted
in `datasets/coraal.md`).

**Does a public, free, non-commercial site with clips comply? Yes.** The licence lets you
"reproduce and Share the Licensed Material, in whole or in part, for NonCommercial
purposes only" (section 2(a)(1)(A)) [8]. Clips are sharing "in part". Whole recordings,
as on the explorer pages, are sharing "in whole". Precedent: the Koenecke et al.
repository has about 6,100 CORAAL clips on public GitHub, and CORAAL's own Explorer
streams whole recordings (both in `datasets/coraal.md`).

**What "NonCommercial" means.** The licence: "not primarily intended for or directed
towards commercial advantage or monetary compensation" [8]. Creative Commons adds that
it "turns on the use, not the identity of the reuser", and "it is only the primary
purpose of the reuse that needs to be considered" [9]. So being a student does not make
it non-commercial by itself; what the site does decides it.

| Plan | Commercial? | Why |
|--|--|--|
| You pay for hosting or a domain | **No** (my reading) | Money goes out, not in. Nobody pays you for the clips. |
| Free accounts to rate clips | No | No payment "in connection with the exchange". |
| Ads on CORAAL pages | **Avoid** | Their aim is money. CC's FAQ does not rule on ads, so it is uncertain at best. |
| Charging for access, a paid tier | **Yes** | CC's FAQ: "charging for access may not be permitted with NC-licensed material" [10]. |
| A donate button | **Grey area** | CC gives no ruling on donations [9] [10]. A "help pay for hosting" link is probably not the site's primary purpose, but nobody has said so. Safest: no donate button, or keep it off the CORAAL pages, or ask CORAAL. |
| A future paid app, or one sold to court-reporting firms | **Yes** | Needs a commercial licence from CORAAL, or CORAAL left out of it. The user guide says DCB, PRV, ATL and VLD can be licensed for commercial use by asking Tyler Kendall; ROC, DCA, DTA and LES were not listed (UG p. 16). |
| A free, open-source app | Probably not | Same test: no money for the material. |
| Using the site to promote your own reporting business | Avoid | It would point the use at commercial advantage (my reading). |

**What ShareAlike asks of the clips.** Cutting clips and re-encoding them is probably
*not* making Adapted Material. The licence lets you share "in part", and format changes
are covered by section 2(a)(4): "simply making modifications authorized by this Section
2(a)(4) never produces Adapted Material" [11]. But the clips are still CORAAL material
under BY-NC-SA 4.0. Each one needs the credit, the licence link and "clipped, re-encoded".
And section 2(a)(5)(C) says you may not add terms or technical locks that stop later
users from doing what the licence allows [8]. So:

- the site's terms must not forbid copying or downloading the CORAAL clips;
- a free login in front of the *rating* tools is fine, but keep the clips and their
  credits reachable as ordinary files, with no download-blocking tricks (my reading;
  CC's definition of a technical lock is about anti-circumvention law, DRM, not logins).

**What ShareAlike asks of transcripts and annotations.**

- The CORAAL reference text shown on a page is CORAAL material: same licence.
- Anything built *from* it and shared: corrected references, re-transcriptions typed by
  visitors, the reference marked up with error labels, a published file of ratings
  tied to the CORAAL text. Treat all of it as Adapted Material and publish it under
  **BY-NC-SA 4.0** only (section 3(b)(1): "a Creative Commons license with the same
  License Elements, this version or later") [8].
- **It cannot be merged with EdAcc or Earnings-22 material into one adapted work.**
  BY-SA 4.0 adaptations may only be BY-SA (or the Free Art Licence or GPLv3), and
  BY-NC-SA adaptations may only be BY-NC-SA. "Currently, no non-CC licenses have been
  designated as compatible with BY-NC-SA 4.0" [12]. Putting works side by side is fine:
  CC's FAQ allows combining any CC content in a collection "so long as you provide
  attribution" [10]. In practice: keep a separate CORAAL page and a separate CORAAL file
  in any published data set. The compare page's numbers (word error rates, counts) are
  facts, not text taken from the corpus, so they are not a problem (my reading).
- Your own write-up, charts and code are not adaptations of CORAAL and can carry your
  own licence.

**Names and places.** CORAAL bleeps them in the audio and marks them in the text. A
public page must never try to undo that, and the rating tool should not ask people to
fill them in.

**Verdict:** public site OK, as long as it stays free, with no ads or paid parts, and
everything adapted from CORAAL is shared as BY-NC-SA 4.0. Only CORAAL (Tyler Kendall)
can settle the donate-button and app questions.

### Earnings-22

- **Transcripts: CC BY-SA 4.0.** The licence file covers "the transcripts and associated
  text files that are used for alignment" (`datasets/earnings22.md`, source [15] there).
  Public display is fine with credit and the same licence.
- **Audio: no licence.** Rev never states one. The paper relies on a fair-use argument
  for its own use. The Hugging Face copies say "CC BY-SA 4.0" for everything, but they
  are not Rev's statement.
- **Safe public option:** what the site does now. Show the reference text and the
  engines' text side by side, with no audio, and link to Rev's repository so readers can
  get the calls themselves.
- **Riskier option:** a few seconds of audio as a fair-use quote, for comment and
  criticism. A U.S. court would weigh it case by case. A public site carries more risk
  than a private page did, and the companies, not Rev, may own the recordings (my
  reading). I would not do it without permission.
- **To get clips, ask Rev** (the speech-datasets maintainers) whether short clips may be
  shown with credit. Only they can say. No draft written yet; say if you want one.

### The engines' transcripts

| Engine (checkpoint used) | Licence | Limits on publishing its output? |
|--|--|--|
| Whisper large-v3 (`openai/whisper-large-v3`, run through faster-whisper) | Hugging Face card: Apache-2.0. OpenAI's GitHub code and weights: MIT | None stated |
| Qwen3-ASR 1.7B (`Qwen/Qwen3-ASR-1.7B`) | Apache-2.0 | None stated |
| Qwen3 forced aligner (`Qwen3-ForcedAligner-0.6B`), used for word times | Apache-2.0 | None stated |
| Voxtral Mini 3B (`mistralai/Voxtral-Mini-3B-2507`) | Apache-2.0 | None stated |
| Canary 1B v2 (`nvidia/canary-1b-v2`) | CC BY 4.0: "Use of this model is governed by the CC-BY-4.0 license" | None. Card says "ready for commercial/non-commercial use" |
| Parakeet TDT 0.6B v3 (`nvidia/parakeet-tdt-0.6b-v3`) | CC BY 4.0, same wording | None |
| Granite Speech 4.1 2B and 2B Plus (`ibm-granite/...`) | Apache-2.0 | None stated |

Sources: each model's Hugging Face card [13].

- None of these licences restricts what you do with the transcripts. The licences cover
  the model files, and the site does not give out the model files.
- Credit the engines anyway, with name and version. It is good practice and lets
  readers repeat the work. Canary and Parakeet are CC BY: if you ever host their
  weights, credit NVIDIA.
- **Who owns a machine transcript?** Probably nobody, as a new work. The U.S. Copyright
  Office does not register material made by a machine without human authorship (my
  reading of its AI guidance, not checked for this note). But the transcript repeats the
  speaker's words, so treat it as part of the corpus it came from: CORAAL engine text as
  BY-NC-SA 4.0, EdAcc and Earnings-22 engine text as BY-SA 4.0.

### The site's own licence

One licence cannot cover the whole site, because the inputs disagree. Use layers:

| Part | Licence |
|--|--|
| Code (`tools/`, `web/widget/`, the pipeline) | MIT (short, common). The site does not ship PyMuPDF, so its AGPL does not reach the pages. |
| Your own words, charts, scores and tables | CC BY 4.0, "except where noted". Anyone can reuse it, and CC BY material may go into BY-SA works. |
| Supreme Court audio and text | No copyright. Say so; no licence needed. |
| EdAcc clips, reference text, engine text | CC BY-SA 4.0 |
| Earnings-22 reference and engine text | CC BY-SA 4.0 |
| CORAAL clips, reference text, engine text, anything adapted from them | CC BY-NC-SA 4.0 |
| Visitors' ratings and corrections | The licence of the recording they are about (see the contributor line below) |

---

## 2. Wording to paste

TASL means Title, Author, Source, Licence (CC's own checklist), plus what was changed.
Fill the bracketed parts.

### Credits section

> **Credits and licences**
>
> Except where noted, the words, charts and numbers on this site are by Noah Collin and
> are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The code
> is under the MIT licence. Recordings and transcripts from other people keep their own
> licences, listed below. What I changed: I cut the recordings into clips, joined some
> clips into longer files, kept some recordings whole, and re-encoded them at lower
> quality. I show the reference text split by time beside the speech engines'
> transcripts. Nothing on this site is endorsed by the people who made these data sets.
>
> **Supreme Court of the United States.** Oral argument audio and transcripts,
> October Terms 2010, 2017, 2021 and 2025. Recordings by the Court; transcripts by
> Alderson Reporting Company (to 2016) and Heritage Reporting Corporation (2017 on).
> Source: [supremecourt.gov](https://www.supremecourt.gov/oral_arguments/). Works of
> the U.S. government are not under copyright, and the Court states no licence. Changes:
> clipped and re-encoded.
>
> **EdAcc, the Edinburgh International Accents of English Corpus.** Ramon Sanabria,
> Nina Markl, Andrea Carmantini, Ondrej Klejch, Peter Bell and Nikolay Bogoychev (2025),
> University of Edinburgh. Source: [Edinburgh DataShare,
> doi:10.7488/ds/7914](https://doi.org/10.7488/ds/7914). Licence:
> [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Changes: audio
> clipped and re-encoded; reference text shown beside the engines' text. The clips, the
> reference text and the engines' transcripts of this audio are shared under CC BY-SA 4.0.
>
> **CORAAL, the Corpus of Regional African American Language.** Tyler Kendall and
> Charlie Farrington (2023), version 2023.06, The Online Resources for African American
> Language Project, University of Oregon, with each component's own authors (listed
> [here / on the data page]). Source:
> [doi:10.7264/1ad5-6t35](https://doi.org/10.7264/1ad5-6t35). Licence:
> [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), for
> non-commercial use only. Changes: audio clipped or kept whole and re-encoded; reference
> text shown beside the engines' text. Names and places were bleeped by CORAAL in the
> original recordings. The clips, the reference text, the engines' transcripts of this
> audio and any labels or corrections made on it are shared under CC BY-NC-SA 4.0.
>
> **Earnings-22.** Miguel Del Rio, Peter Ha, Quinten McNamara, Corey Miller and Shipra
> Chandra (2022), Rev. Source: [revdotcom/speech-datasets on
> GitHub](https://github.com/revdotcom/speech-datasets/tree/main/earnings22). Licence of
> the transcripts: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
> Changes: reference text split by time and shown beside the engines' text, shared under
> CC BY-SA 4.0. No source states a licence for the audio, so none of it is played here.
>
> **Speech engines.** Whisper large-v3 (OpenAI, MIT / Apache-2.0), Qwen3-ASR 1.7B and
> Qwen3-ForcedAligner 0.6B (Alibaba Qwen team, Apache-2.0), Voxtral Mini 3B (Mistral AI,
> Apache-2.0), Canary 1B v2 and Parakeet TDT 0.6B v3 (NVIDIA, CC BY 4.0), Granite Speech
> 4.1 2B and 2B Plus (IBM, Apache-2.0). Their transcripts are machine output; they are
> shared under the licence of the recording they transcribe.

Check the CORAAL credit against `CREDITS` in `tools/build_site.py` before pasting; the
component citations there are the ones the CORAAL guide asks for.

### Footer line

> Text and charts © Noah Collin, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
> except where noted. Audio and transcripts keep their own licences: Supreme Court (public
> domain), EdAcc and Earnings-22 text (CC BY-SA 4.0), CORAAL (CC BY-NC-SA 4.0,
> non-commercial). [Credits and licences](#credits). A CUNY SPS student project; not
> legal advice, not an official record.

### Contributor line (on the sign-up and rating pages)

> What you submit here (ratings, labels, corrected transcripts) may be published for
> research, without your name or email. You agree it is shared under the licence of the
> recording it is about: CC BY-NC-SA 4.0 for CORAAL, CC BY-SA 4.0 for EdAcc and
> Earnings-22, and CC BY 4.0 for the Supreme Court.

---

## 3. Collecting ratings from people

### Collect as little as possible

| Keep | Why |
|--|--|
| A random user ID made by the sign-in service | Links one person's ratings together. Needed for the reliability weighting in `app-roadmap.md`. |
| An email address, held only by the sign-in service | For password reset. Never copied into the ratings table. |
| A display name the person picks (not their real name) | So they can see their own work. Say "don't use your real name". |
| For each rating: clip ID, answer, label, corrected text if any, time | The research data. |
| Optional, one question: "Which fits you best: court reporter, captioner/transcriber, linguist, other?" | Only if the analysis needs it. It is information *about the person*, which matters for CUNY review (below). |

Leave out: real names, ages, locations, IP addresses in your own tables, free-text
"about me" boxes, tracking cookies. Use the sign-in service's anonymous accounts as the
cookie fallback the roadmap mentions: people can rate without giving an email at all.

**Never store passwords yourself.** Let the sign-in service (Firebase or Supabase) take
them and keep only salted hashes. Turn on two-step login for your own admin accounts.

### What the law asks (my reading)

- **New York, the SHIELD Act.** It covers "any person or business which owns or licenses
  computerized data" with private information of New York residents, and "private
  information" includes "a user name or e-mail address in combination with a password or
  security question and answer that would permit access to an online account" [14].
  - You must keep "reasonable safeguards" (GBL 899-bb). A small business, under 50
    employees, meets that with safeguards "appropriate for the size and complexity" of
    what it does [15].
  - If those logins leak, you must tell the people affected (GBL 899-aa).
  - Using a managed sign-in service, tight database rules and no stray exports with
    emails in them is the practical way to meet this. Whether a leak of hashed
    passwords counts is not clear from the text.
- **Other U.S. states.** California's privacy-policy law (CalOPPA) is aimed at
  "commercial" websites; a free student site is probably outside it (not verified).
  Writing a short notice anyway costs nothing.
- **Children.** Say the site is for adults (18+). That also keeps CUNY review simple and
  keeps the site outside the children's privacy rules (COPPA).
- **GDPR (EU and UK visitors).** It reaches a U.S. site only if it is offering services
  to people in the EU or monitoring them there. Recital 23: the "mere accessibility" of a
  website in the EU is not enough; signs would be EU languages or currencies, or naming
  EU users [16]. An English site for U.S. court reporters is probably outside it. But a
  notice that meets its basics (who, what, why, how long, how to delete) is easy, so
  write one.

### A short privacy notice to start from

> **Privacy.** This site is run by Noah Collin, a student at the CUNY School of
> Professional Studies, for a capstone project. If you make an account, we keep your
> email address (only for signing in and password resets), a display name you choose,
> and the ratings and corrections you submit. Passwords are handled by [Google
> Firebase] and we never see them. We do not use advertising or tracking cookies. Our
> host keeps standard server logs. Ratings may be analysed and published for research
> without your name or email. Your email is never published or shared. You can ask us to
> delete your account and your ratings at any time: [contact address]. We will delete all
> email addresses when the study ends [date]. This site is for adults (18 and over).

CUNY may ask for consent wording of its own. If so, merge the two.

### Does CUNY's human research review apply?

**CUNY's rule.** CUNY HRPP or IRB review is required when all three are true: "The
investigator is conducting research or clinical investigation; The proposed research or
clinical investigation involves human subjects; CUNY is engaged in the research" [17]
[18]. CUNY is engaged when its students or staff get, for the research, data through
"intervention or interaction" with people, identifiable private information, or consent
[18]. "When researchers are not certain whether their activities constitute human
subject research, they should contact their CUNY college or school's HRPP Office" [18].

**The federal definitions CUNY uses** (45 CFR 46.102) [19]:

- Research: "a systematic investigation, including research development, testing, and
  evaluation, designed to develop or contribute to generalizable knowledge."
- Human subject: "a living individual about whom an investigator (whether professional
  or student) conducting research ... Obtains information ... through intervention or
  interaction with the individual, and uses, studies, or analyzes the information", or
  gets identifiable private information.
- "Interaction includes communication or interpersonal contact between investigator and
  subject." A web form people answer counts as communication (my reading).

**Class projects.** CUNY's School of Public Health (a different CUNY school, not SPS)
says projects done "solely to fulfill course requirements" whose findings "will not be
made generalizable" need no review [20]. Brooklyn College says much the same [21]. I
found no SPS page on class projects; the SPS HRPP page just repeats the three-part test
[17].

**Quality improvement.** CUNY's pages say nothing about it. Other universities' guidance
notes that OHRP treats intent to publish as an "insufficient criterion" either way
(UC San Diego, https://irb.ucsd.edu/_files/researchers/EBP-QA-QI-Projects.pdf; Indiana,
https://research.iu.edu/compliance/human-subjects/guidance/quality.html). This
project is not improving a CUNY service, so the QI route does not fit (my reading).

**Verdict (my reading, to be confirmed by CUNY).**

- Your own ratings, and your own listening page, are not human subjects research. You
  are the investigator, not a subject.
- Ratings from the public, analysed in the capstone paper, put on a public site, or
  published as a data set, **probably are**. It is systematic, it aims at generalizable
  knowledge (a public write-up and data set), and it studies what people tell you
  through a form, linked to an account.
  - The best argument against: people are rating *clips*, not telling you about
    themselves. Some review boards accept that for expert judgements.
  - That argument gets weaker if you weigh each person's reliability (the roadmap plans
    to) or ask their profession.
- If it is human subjects research, it would most likely be **exempt, category 2**:
  "survey procedures" where the answers are recorded so people "cannot readily be
  ascertained", or where disclosure would not harm their reputation or job (45 CFR
  46.104(d)(2)) [22]. Exempt still means CUNY decides, not you, and it must be decided
  **before** collecting anything.
- **What to do:** ask the SPS HRPP coordinator now, before building the rating page.
  Draft: `midterm/drafts/email-hrpp-ratings.md`. Talk to your professor first. CUNY's
  central page says certifications "may be required from the Faculty Advisor (for
  student investigators)", and that master's students may be the lead investigator only
  "with stipulations" [23]. Brooklyn College says a student project must list a faculty
  adviser [21].
- **Practical points.**
  - Applications now go through Cayuse Human Ethics, per CUNY's central page [23]. The
    SPS page still says IRB Manager [17], so ask which.
  - CITI training records link to the application, which suggests the training is
    expected [23]. Doing it before the email saves a round trip.
  - Hunter College says an exempt review takes about two to three weeks (from a search
    result; its FAQ page refused my request, not verified).
  - Data collected before a decision may not be usable in the paper.

---

## 4. Hosting

Size of the site today (counted 7 Nov 2026): `site/` is 558 files, 229 MB; `explorer/`
is 843 files, 820 MB. About 1,400 files and 1.05 GB in all, 654 of them audio. The
largest file is a 15 MB CSV; the largest audio is 13.6 MB.

### The static pages and audio

| Host | Free plan | Paid | Gotchas for this site |
|--|--|--|--|
| **Cloudflare Pages** (or Workers static assets, same limits) | 20,000 files, 25 MiB per file, 500 builds a month; bandwidth not limited on the limits page; "Requests to static assets are free and unlimited" (Workers) [24] [25] | Workers Paid $5/month (100,000 files) [25] | The site fits today. Upload with `wrangler`, so the audio never goes into git. A custom domain must be added to Cloudflare. |
| Cloudflare **R2** (for audio, if it outgrows Pages) | 10 GB-month storage, 1 M writes, 10 M reads a month, **egress free** [26] | $0.015 per GB-month | Not needed yet. The free `r2.dev` address "is rate-limited and should only be used for development purposes"; use your own domain [27]. |
| GitHub Pages | Site "no larger than 1 GB", 100 GB/month soft bandwidth [28] | — | **Over the 1 GB limit already.** Audio would go into git forever (against `CLAUDE.md`). Its terms say it should not handle "sensitive transactions" such as passwords [28]. |
| Netlify | 300 credits a month: 20 credits per GB of bandwidth, 15 per production deploy [29] [30] | Personal $9/month, Pro $20/month [29] | When credits run out, "all of your web projects ... are paused" until the next month [30]. That is about 15 GB of listening a month, less with deploys. A class sharing the link could use that up. |
| Vercel | Hobby: 100 GB data transfer, 1 GB Blob storage, "for personal, non-commercial use" [31] | Pro $20/month | Workable, but the audio would need its paid Blob storage or a second host, and a paid app later means Pro. |
| Firebase Hosting | 10 GB stored, **360 MB a day** of transfer [32] | $0.15/GB over that | Too small a daily allowance for audio. Fine for pages alone. |

Cloudflare's terms say video and other large files must go through its paid services
"(e.g., the Developer Platform, Images, and Stream)" rather than the plain CDN [33].
Pages, Workers and R2 are part of the Developer Platform, so short audio clips there
should be fine (my reading).

### Accounts and the ratings database

| Service | Free plan | Paid | Gotchas |
|--|--|--|--|
| **Firebase** (Authentication + Firestore) | 50,000 monthly users; Firestore 1 GiB, 50,000 reads and 20,000 writes a day [32]. Sends its own emails: 1,000 address checks and 150 password resets a day; 100 new accounts per hour per IP [34] | Blaze, pay as you go | No pausing. Emails work out of the box. A NoSQL database: getting a CSV for pandas needs a short script. If a daily quota runs out, that part stops until the next day. Blaze has budget alerts but no hard spending cap. Database rules must be written carefully, or anyone can read everyone's ratings. |
| Supabase (Postgres + Auth) | 500 MB database, 1 GB files, 5 GB egress, 50,000 monthly users, 2 projects [35] | Pro $25/month [35] | "Free projects are paused after 1 week of inactivity"; restorable "for up to 1 year" with data kept [35] [36]. The built-in email sender only sends to your own team and is "set to 2 messages per hour" [37], so real sign-ups need your own sender (Resend free: 3,000 a month, 100 a day [38]). SQL and CSV export are easy. Row-level security must be set up right. |
| PocketBase on a small VPS | Software free | Hetzner from €5.99/month listed [39]; specs not verified | One program with SQLite, auth and an admin page built in [40]. You run the server: updates, backups, HTTPS, uptime. Still version 0.x. Could also serve the audio. |
| Cloudflare D1 + Workers | 5 GB, 5 M rows read and 100,000 written a day [41] | inside Workers Paid | All on one vendor, but there is no ready-made login. You would write password handling yourself, which is the part most worth not writing yourself. |

### Recommendation

**Cloudflare Pages for the pages and audio, Firebase for accounts and ratings.**

- **Why:** nothing to pay but the domain. No server to look after. No pausing. Password
  and email handling is done by a big provider. The site fits Pages' free limits as it
  is. When audio grows past 20,000 files, move it to R2 on the same account.
- **Supabase instead** if you would rather query the ratings in SQL. Then also set up
  Resend for email, and expect the project to pause in quiet weeks. Restore takes a
  click, and the data survives.
- **Costs:** about $11-12 a year for a `.com` at Cloudflare's at-cost registrar.
  Sources disagree slightly, and Verisign raised the .com wholesale price on 1 Nov 2026
  (not verified on Cloudflare's own page). Everything else $0 at this size. The next step
  up is $5/month (Workers Paid).
- **Your own setup time** (rough estimate):

  | Step | Time |
  |--|--|
  | Cloudflare account, choose and buy a domain (needs a card) | 30-45 min |
  | Pages project, log in `wrangler`, first upload, connect the domain (DNS can take a few hours) | 30-60 min |
  | Firebase project, turn on email/password and anonymous sign-in, Firestore in a U.S. region, add the domain to the allowed list | 30-60 min |
  | A contact address for the privacy notice (Cloudflare's free email forwarding works) | 15 min |
  | **Total** | **about 2-4 hours**, spread over a day |

  Not counted: building the sign-in and rating pages and the Firestore rules (a day or
  two of coding), and waiting for CUNY's HRPP decision (weeks).

---

## Open questions, and who can answer them

| Question | Who |
|--|--|
| Is collecting and analysing public ratings human subjects research, and if so is it exempt? | CUNY SPS HRPP coordinator. Draft: `midterm/drafts/email-hrpp-ratings.md` |
| Is a donate button, or a later app, acceptable for CORAAL material? | CORAAL (Tyler Kendall, University of Oregon). No draft yet. |
| May short Earnings-22 audio clips be shown? | Rev's speech-datasets maintainers. No draft yet. |
| Oyez's current licence | oyez.org's terms page. Only matters if Oyez material is ever used. |
| Whether the contract reporters claim anything in the Supreme Court transcripts | Very unlikely to matter. No one to ask unless it comes up. |

## Sources

1. Supreme Court, argument audio: https://www.supremecourt.gov/oral_arguments/argument_audio.aspx
2. Supreme Court, availability of transcripts: https://www.supremecourt.gov/oral_arguments/availabilityoforalargumenttranscripts.aspx
3. Oyez and Creative Commons: https://creativecommons.org/2003/06/25/supremecourtaudioclassicsenterp2pzonethankstocreativecommonslicenses/ and https://wiki.creativecommons.org/wiki/Oyez (current oyez.org terms not read)
4. EdAcc v1.0 on Edinburgh DataShare: https://datashare.ed.ac.uk/handle/10283/8983 (doi:10.7488/ds/7914), its licence file https://datashare.ed.ac.uk/bitstream/handle/10283/8983/CC_BY_SA_license_text.txt; superseded items https://datashare.ed.ac.uk/handle/10283/8911 (ds/7848) and https://datashare.ed.ac.uk/handle/10283/4836 (ds/3832)
5. Sanabria et al. 2023, arXiv: https://arxiv.org/abs/2303.18110
6. EdAcc on Hugging Face: https://huggingface.co/datasets/edinburghcstr/edacc
7. EdAcc home page: https://groups.inf.ed.ac.uk/edacc/
8. CC BY-NC-SA 4.0 legal code: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en
9. CC, NonCommercial interpretation: https://wiki.creativecommons.org/wiki/NonCommercial_interpretation
10. CC FAQ: https://creativecommons.org/faq/
11. CC BY-SA 4.0 legal code: https://creativecommons.org/licenses/by-sa/4.0/legalcode.en
12. CC, compatible licences: https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/
13. Model cards: https://huggingface.co/openai/whisper-large-v3, https://huggingface.co/Qwen/Qwen3-ASR-1.7B, https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B, https://huggingface.co/mistralai/Voxtral-Mini-3B-2507, https://huggingface.co/nvidia/canary-1b-v2, https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3, https://huggingface.co/ibm-granite/granite-speech-4.1-2b, https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus
14. NY General Business Law 899-aa: https://www.nysenate.gov/legislation/laws/GBS/899-AA
15. NY General Business Law 899-bb: https://www.nysenate.gov/legislation/laws/GBS/899-BB
16. GDPR Recital 23: https://gdpr-info.eu/recitals/no-23/
17. CUNY SPS, HRPP and IRB (coordinator, three-part test): https://sps.cuny.edu/about/policies/research-compliance/hrpp-and-irb
18. CUNY, "When is CUNY HRPP or IRB Review Required?" (2019), quoted from search results and the SPH capstone page; the PDF itself returned 404: https://www.hunter.cuny.edu/irb/repository/files/forms/hrpp-irb/When%20is%20CUNY%20HRPP%20or%20IRB%20Review%20Required.pdf
19. 45 CFR 46.102: https://www.law.cornell.edu/cfr/text/45/46.102
20. CUNY SPH, class research projects: https://sph.cuny.edu/research/human-research-protection-program/for-faculty/class-research-projects/ and capstone requirements: https://sph.cuny.edu/research/human-research-protection-program/for-students/capstone-requirements/
21. Brooklyn College HRPP FAQ: https://www.brooklyn.edu/provost/compliance/irb
22. 45 CFR 46.104: https://www.law.cornell.edu/cfr/text/45/46.104
23. CUNY central HRPP page: https://www.cuny.edu/research/research-compliance/human-research-protection-program/ and policies list https://www.cuny.edu/research/research-compliance/human-research-protection-program/hrpp-policies-procedures/ (HRPP-102 on determining human subjects research would not load)
24. Cloudflare Pages limits: https://developers.cloudflare.com/pages/platform/limits/
25. Cloudflare Workers pricing and limits: https://developers.cloudflare.com/workers/platform/pricing/, https://developers.cloudflare.com/workers/platform/limits/
26. Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
27. Cloudflare R2 public buckets: https://developers.cloudflare.com/r2/buckets/public-buckets/
28. GitHub Pages limits: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
29. Netlify pricing: https://www.netlify.com/pricing/
30. Netlify, how credits work: https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/
31. Vercel pricing: https://vercel.com/pricing
32. Firebase pricing: https://firebase.google.com/pricing
33. Cloudflare service-specific terms (CDN): https://www.cloudflare.com/service-specific-terms-application-services/
34. Firebase Authentication limits: https://firebase.google.com/docs/auth/limits
35. Supabase pricing: https://supabase.com/pricing
36. Supabase, project pausing: https://supabase.com/docs/guides/platform/free-project-pausing
37. Supabase, custom SMTP: https://supabase.com/docs/guides/auth/auth-smtp
38. Resend pricing: https://resend.com/pricing
39. Hetzner Cloud: https://www.hetzner.com/cloud/
40. PocketBase FAQ: https://pocketbase.io/faq/
41. Cloudflare D1 pricing: https://developers.cloudflare.com/d1/platform/pricing/

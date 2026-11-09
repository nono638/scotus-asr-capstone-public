# Invented words

Words a speech engine wrote where nobody said anything. A stenographer can
mishear a word, but does not write words into a silence. A machine sometimes
does, and this folder lists where.

Made by `tools/find_invented_words.py` (processor only, about 15 minutes for
everything with the four terms run side by side; a few seconds once cached).
The same tool writes the real cases in the format all four failure finders
share to `findings/failures/invented/`, with a hand-picked shortlist.

## What counts

An insertion means the engine wrote a word and the alignment has no reference word
to set against it. It is counted as invented only if the audio there is quiet:

- **speech share under 0.2**: Silero VAD hears speech in less than a fifth of
  the span, and
- **at least 15 dB below the recording**: measured against the whole recording's
  level, not a fixed number, because the equipment changed between 2010 and 2025.
- **EdAcc and CORAAL**: no reference turn may overlap the span, and no stretch
  the reference leaves out of scoring either (EdAcc's read-aloud passages,
  CORAAL rows with a bleeped name or unclear speech). Their reference turns
  carry times; the Supreme Court's do not, so there the alignment alone decides
  that "the record has nothing".

The span runs from the first inserted word's start to the last one's end, in the
engine's own timings. A span shorter than 0.5 s is widened to 0.5 s around its
middle, so the level is not read off a handful of samples.

Why these numbers: of 76,106 insertions, most sit on speech (speech share above
0.5, within 10 dB of the recording). The quiet ones form a separate group at
speech share 0 and 20 to 30 dB down, with few in between. Moving the cut-offs
changes the count a little: 0.1 and 15 dB gives 811 candidates, 0.3 and 12 dB
gives 1,391. The 0.2 and 15 dB cut gave 990. (These figures are for the Supreme
Court and EdAcc test, before EdAcc dev and CORAAL were added.)

Engines and runs: Whisper large-v3, Qwen3-ASR 1.7B and Parakeet TDT 0.6b on four
Supreme Court terms (258 arguments), on CORAAL's Rochester (ROC, 19 interviews),
Princeville (PRV, 32) and Washington DC (DCB, 63), and on all 125 Earnings-22 calls;
five engines on EdAcc's test (40 conversations) and dev (36). The runs are listed in
`tools/lineup.py`.

## Counts

| Corpus | Term | Engine | Recordings | Hours | Insertions | Quiet | of which speaker labels | Quiet per hour |
|---|---|---|---|---|---|---|---|---|
| Supreme Court | OT2010 | Whisper | 77 | 76.3 | 9,695 | **593** | 489 | **7.77** |
| |  | Qwen3 | 77 | 76.3 | 11,615 | 44 | 0 | 0.58 |
| |  | Parakeet | 77 | 76.3 | 9,187 | 68 | 0 | 0.89 |
| | OT2017 | Whisper | 61 | 61.1 | 3,452 | 51 | 24 | 0.83 |
| |  | Qwen3 | 61 | 61.1 | 3,297 | 4 | 0 | 0.07 |
| |  | Parakeet | 61 | 61.1 | 3,962 | 23 | 0 | 0.38 |
| | OT2021 | Whisper | 62 | 86.7 | 4,765 | 57 | 12 | 0.66 |
| |  | Qwen3 | 62 | 86.7 | 3,281 | 8 | 0 | 0.09 |
| |  | Parakeet | 62 | 86.7 | 4,584 | 33 | 1 | 0.38 |
| | OT2025 | Whisper | 58 | 86.0 | 4,981 | 48 | 6 | 0.56 |
| |  | Qwen3 | 58 | 86.0 | 3,778 | 7 | 0 | 0.08 |
| |  | Parakeet | 58 | 86.0 | 5,580 | 37 | 0 | 0.43 |
| EdAcc | dev | Whisper | 36 | 17.4 | 1,747 | 21 | 0 | 1.21 |
| |  | Qwen3 | 36 | 17.4 | 1,782 | 33 | 0 | 1.90 |
| |  | Parakeet | 36 | 17.4 | 1,730 | 15 | 0 | 0.86 |
| |  | Canary | 36 | 17.4 | 1,504 | 5 | 0 | 0.29 |
| |  | Granite | 36 | 17.4 | 1,357 | 3 | 0 | 0.17 |
| | test | Whisper | 40 | 18.2 | 1,977 | 6 | 0 | 0.33 |
| |  | Qwen3 | 40 | 18.2 | 1,831 | 29 | 0 | 1.59 |
| |  | Parakeet | 40 | 18.2 | 1,902 | 14 | 0 | 0.77 |
| |  | Canary | 40 | 18.2 | 1,707 | 2 | 0 | 0.11 |
| |  | Granite | 40 | 18.2 | 1,569 | 4 | 0 | 0.22 |
| CORAAL | DCB | Whisper | 63 | 46.1 | 6,131 | 100 | 0 | 2.17 |
| |  | Qwen3 | 63 | 46.1 | 3,294 | 76 | 1 | 1.65 |
| |  | Parakeet | 63 | 46.1 | 5,114 | 225 | 0 | 4.89 |
| | PRV | Whisper | 32 | 14.0 | 2,002 | 28 | 0 | 2.01 |
| |  | Qwen3 | 32 | 14.0 | 1,424 | 25 | 0 | 1.79 |
| |  | Parakeet | 32 | 14.0 | 1,773 | 51 | 0 | 3.65 |
| | ROC | Whisper | 19 | 13.2 | 1,429 | 7 | 0 | 0.53 |
| |  | Qwen3 | 19 | 13.2 | 610 | 4 | 0 | 0.30 |
| |  | Parakeet | 19 | 13.2 | 981 | 19 | 0 | 1.44 |
| Earnings-22 | African | Whisper | 5 | 5.1 | 733 | 22 | 0 | 4.35 |
| |  | Qwen3 | 5 | 5.1 | 891 | 20 | 1 | 3.96 |
| |  | Parakeet | 5 | 5.1 | 885 | 15 | 0 | 2.97 |
| | Asian | Whisper | 28 | 25.3 | 3,672 | 56 | 0 | 2.21 |
| |  | Qwen3 | 28 | 25.3 | 3,865 | 123 | 7 | 4.86 |
| |  | Parakeet | 28 | 25.3 | 4,215 | 49 | 0 | 1.93 |
| | English | Whisper | 26 | 22.9 | 2,635 | 66 | 0 | 2.89 |
| |  | Qwen3 | 26 | 22.9 | 2,397 | 42 | 0 | 1.84 |
| |  | Parakeet | 26 | 22.9 | 2,772 | 46 | 1 | 2.01 |
| | Germanic | Whisper | 12 | 14.3 | 1,630 | 26 | 0 | 1.82 |
| |  | Qwen3 | 12 | 14.3 | 1,444 | 19 | 2 | 1.33 |
| |  | Parakeet | 12 | 14.3 | 1,940 | 20 | 0 | 1.40 |
| | Other Romance | Whisper | 13 | 15.8 | 2,974 | 44 | 0 | 2.79 |
| |  | Qwen3 | 13 | 15.8 | 3,072 | 65 | 1 | 4.13 |
| |  | Parakeet | 13 | 15.8 | 3,631 | 46 | 0 | 2.92 |
| | Slavic | Whisper | 10 | 7.7 | 1,096 | 15 | 0 | 1.94 |
| |  | Qwen3 | 10 | 7.7 | 1,127 | 19 | 0 | 2.46 |
| |  | Parakeet | 10 | 7.7 | 1,431 | 31 | 0 | 4.01 |
| | Spanish/Portuguese | Whisper | 31 | 28.9 | 4,359 | 119 | 2 | 4.12 |
| |  | Qwen3 | 31 | 28.9 | 4,401 | 123 | 3 | 4.26 |
| |  | Parakeet | 31 | 28.9 | 5,428 | 149 | 1 | 5.16 |

Parakeet is from its `-reread` runs (23 October, `../parakeet-stall/`). Writing back
the speech its decoder used to skip also puts a few more words in quiet stretches:
its quiet insertions went from 123 to 161 on the Supreme Court, 23 to 29 on EdAcc
and 283 to 295 on CORAAL. The other engines' rows did not change.

EdAcc test lost three rows (Whisper 8 to 6, Parakeet 12 to 11) when the test for
stretches left out of scoring was added with CORAAL: all three sat on the
read-aloud passage, two at the very start of the recording and one with no
content word, so none was among the 48 below. Nothing else changed.

Invented words are rare: under one an hour for every engine except Whisper on
OT2010. Most of the quiet ones are a single small word ("and", "the", "MR."). On
the Supreme Court and EdAcc test, only 48 hold a real word, are not at the start
or end of the recording and are not a speaker label. Of those 48, 27 were
inserted by that engine alone. Those first counts were made before Parakeet's
re-read and before CORAAL's Washington DC and Earnings-22 were added. Now
`findings/failures/invented/candidates.csv` holds 533 such cases: Supreme Court
51, EdAcc 31, CORAAL 84 and Earnings-22 367 (181 of the 533 by one engine alone).

**Earnings-22's count needs care.** Its reference has no times, so a stretch counts
as "nobody speaking" only by the voice detector, and phone audio, hold music and an
operator talking over the line make that less sure. Some calls' references also
leave speech out (4453076 is known to be cut short), so the engine's words there
look invented when the reference is what is missing: 29 of Qwen3's 208 are on
4453076 alone. Read Earnings-22 cases one by one before quoting a rate. Per hour,
leaving it aside, CORAAL has the most (Parakeet about four an hour on Washington
DC) and the Supreme Court the fewest.

**Whisper writes speaker labels.** 532 of the 990 are a name printed the way a
transcript prints it, written into the pause where one speaker hands over to
the next: "MR." (322 times), "JUSTICE KAGAN.", "GENERAL VERRILLI.", "CHIEF
JUSTICE ROBERTS.". Nobody says these out loud. Whisper wrote 489 of them in OT2010
and only 6 to 24 in each later term. It also wrote names that belong to no Supreme
Court argument: "CHAIRMAN BERNANKE." seven times, at the moment the Chief Justice
thanks counsel, and "CONSUELO MACK." once. The most likely explanation is that
Whisper's training data included transcripts formatted like these, possibly
the 2010-era Supreme Court ones, but nothing here proves that.

Whisper's word confidence does not help find them. The quiet insertions average
0.59 to 0.60, much the same as all its insertions (0.61).

## Examples

| Argument | Clock | Engine | Engine wrote [invented] | Record |
|---|---|---|---|---|
| 20-1410 (OT2021) | 0:28:27 | Parakeet | Mr. Brindley. [I've already said that.] Thank you, Mr. Chief Justice | Mr. Brindley. ^ Thank you, Mr. Chief Justice |
| 24-1063 (OT2025) | 1:32:40 | Whisper | Thank you, counsel. [Thank you, counsel.] Rebuttal, Ms. Black? | Thank you, counsel. ^ Rebuttal, Ms. Blatt. |
| 16-1435 (OT2017) | 0:54:37 | Parakeet | Would that be allowed [to be a question?] Under the statute, yes. | Would that be allowed? ^ Under the statute, yes. |
| 09-11311 (OT2010) | 0:56:41 | Whisper | not an apprentice problem. [CHAIRMAN BERNANKE.] Thank you, Counsel. | not an Apprendi problem. ^ Thank you, counsel. |
| 21-511 (OT2021) | 0:20:14 | Parakeet | any other uh discovery order? [Trevor Burrus] So the harm | any other discovery order? ^ So the harm |
| 20-826 (OT2021) | 0:44:32 | Whisper | satisfied here. [year.] You mentioned that the State | satisfied here. ^ You mentioned that the state |

The first runs over 17 seconds of quiet audio. Two patterns recur: an engine
writing the last phrase again into the silence after it ("Thank you, counsel."
eight seconds later), and Parakeet finishing a sentence the speaker had already
finished ("[to be a question?]", "[of the question?]").

## Files

- `candidates.csv`: all 1,191 quiet insertions (987 Supreme Court and EdAcc test,
  74 EdAcc dev, 130 CORAAL). `shared_with` names other engines
  that inserted words at the same reference gap or within a second of it.
  `at_edge` means before the first word that matches the record or after the
  last one (25 rows in all). `speaker_label` means a word in capitals or one ending in a colon.
- `clearest-30.csv`: thirty to listen to first. All are inside the argument and
  hold a real word. At most two come from one recording, and they are spread
  across the four terms and three engines. Ranked within each term and engine:
  not shared with another engine, not just after a reporter's dash, real words
  before speaker labels, then the most content words, least speech and quietest.
  All thirty are Supreme Court cases. No EdAcc case was clearly better (see below),
  and only the Supreme Court audio is public domain.
- `counts.csv`: the table above.
- `cache/`: what the tool measured for each recording, every insertion included,
  so the thresholds can be changed without loading the audio again. 6.4 MB. It
  can be rebuilt, so it does not need to be in git.

## Caveats

- **Nothing here has been checked by ear yet.** These are candidates.
- **The detector can miss quiet speech.** A justice speaking away from the
  microphone, or someone whispering, can read as silence. "Yes, sir." or "That's
  right." in a pause may be real speech the reporter chose not to take down. An
  insertion that several engines share is more likely to be real speech, which
  is why `shared_with` is there (335 of the 990 are shared).
- **A word the record dropped is not an invention.** The reporter leaves out
  stutters, "you know" and "I mean". The tool does not count words an engine
  wrote twice in a row, or those hedges, as content words, but it will not
  catch every one.
- **The reporter's dashes.** "the most - --" marks someone cut off. Engines
  sometimes write the words that were drowned out, and those words are real.
  These are ranked last in the clearest list but stay in `candidates.csv`.
- **Start and end of the recording.** The marshal's cry and chatter after the
  case is submitted are not in the record, so words there look invented.
  Parakeet's "The Honorable Courtney." is probably the marshal's "The Honorable, the
  Chief Justice". These rows are flagged `at_edge` and left out of the clearest list.
- **Timings are the engine's own.** Whisper's first word in a segment, and
  Qwen3's aligner when it fails, can be placed in the pause beside where the word
  was actually said. That makes a real word look like one written over silence.
  Many single small words in the list are probably this.
- **EdAcc is less clean.** Many of its quiet insertions sit in stretches 50-60 dB
  down (near digital silence between turns), and most are shared by several
  engines. That looks more like timing or reference gaps than invention, so none
  made the clearest list. EdAcc dev looks the same.
- **CORAAL's quiet is less quiet**: its quiet cases sit about 19 dB below the
  recording (Supreme Court 24, EdAcc 35-40), and its transcript has no row for
  the time between two speakers (102 minutes of 27 hours). Speech in those gaps
  is thrown out by the quiet test, but soft speech could slip through. The
  clearest CORAAL and EdAcc cases are in `findings/failures/invented/shortlist.csv`;
  this folder's clearest-30 is still Supreme Court only.

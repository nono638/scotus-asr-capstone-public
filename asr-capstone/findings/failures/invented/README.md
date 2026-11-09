# Invented words

Words an engine wrote where nobody said anything. A stenographer can mishear a
word, but does not write words into a silence. This is the shared-format copy of
`findings/invented-words/`, which has the full list and the longer write-up.

Made by `tools/find_invented_words.py` (processor only; a few seconds once its
cache is there, about 5 minutes for EdAcc and CORAAL from nothing).

## The rules

An insertion (the engine wrote a word the reference has nothing against) counts
as invented if the audio under it is quiet:

- **speech share under 0.2**: Silero VAD hears speech in less than a fifth of the span,
- **at least 15 dB below the recording** as a whole, and
- **a timed reference has nothing there** (EdAcc, CORAAL): no reference turn and no
  stretch left out of scoring (CORAAL rows with a bleeped name or `/unintelligible/`,
  EdAcc's read-aloud passages) overlaps the span. The Supreme Court reference has
  no times, so there the alignment alone decides.

The span is the engine's own word times, widened to at least 0.5 s.

`candidates.csv` keeps only the **real** cases: not a speaker label ("MR.",
"JUSTICE KAGAN."), not before the first or after the last word that matches the
reference, and with at least one content word (not "and", "the", "uh", "yeah").
The quiet ones that fail these tests are in `findings/invented-words/candidates.csv`.

Columns beyond the shared ones: `start_clock`, `content_words`, `n_content`,
`shared_with` (other engines that also inserted words within a second of it),
`speech_share`, `level_vs_recording_db`, `confidence` (Whisper only). `record` is
always empty: the reference has nothing there. `others_right` is the recording's
other engines less those in `shared_with`. Subkind `phrase` is three words or
more, `word` is fewer.

## Counts

Real cases per engine-hour of audio (every engine heard the same hours):

| Data set | Hours | Whisper | Qwen3 | Parakeet | Canary | Granite |
|---|---|---|---|---|---|---|
| Supreme Court (4 terms, 258 arguments) | 310.1 | 14 (0.05/h) | 3 (0.01/h) | 20 (0.06/h) | | |
| EdAcc (test + dev, 76 conversations) | 35.6 | 4 (0.11/h) | 14 (0.39/h) | 6 (0.17/h) | 1 (0.03/h) | 2 (0.06/h) |
| CORAAL (ROC + PRV, 51 interviews) | 27.2 | 4 (0.15/h) | 12 (0.44/h) | 13 (0.48/h) | | |

By term, split and component in `counts.csv`. `quiet_insertions` there is every
quiet insertion before the three tests above, and `alone` the real cases no
other engine shares.

Real invented words are rare everywhere: well under one an hour. They are rarer
on the Supreme Court than on the two conversation sets, by a factor of three to
ten. The reasons are probably the same ones that make those sets harder anyway:
quieter, less tidy audio with more pauses, and a reference that is timed by hand.

## What the shortlist shows

`shortlist.csv` has 23 cases: 10 Supreme Court, 4 EdAcc, 9 CORAAL, at most two
from any recording. None has been heard yet (`heard` = no). Three patterns:

- **Echo**: the engine writes the last phrase again into the silence after it.
  "Thank you, counsel." eight seconds later (Whisper, and once Qwen3), "times"
  after "sometimes".
- **Finishing the sentence**: Parakeet adds an ending the speaker never said:
  "to be a question?", "of the question?", "like that."
- **Whole new sentences**: Parakeet's "here since 1989 as he was going over to
  California." in a six-second pause in a Princeville interview, "I've already said
  that." on the Supreme Court, and Whisper's "Thank you" in near silence on EdAcc.

**EdAcc has only 4.** Most of its 27 real cases are Qwen3 rows whose word times
failed (all its words stamped at one instant, or spread evenly over a stretch), or
words that several engines wrote in the same spot, which is more likely quiet real
speech than invention. Canary and Granite have none clear enough.

## Checked from the audio

Three new spans were measured again by hand from the original files (native
sample rate, Silero with other settings):

- CORAAL PRV_se0_ag3_f_02_2 at 0:19:39, Parakeet's "here since 1989...": 20.5 dB
  below the recording, no speech found; the transcript has no row for 6.7 s.
  Confirmed quiet.
- CORAAL ROC_se0_ag2_m_01_3 at 0:05:19, Parakeet's "anyway, um you maybe start.":
  15.5 dB below, 0.05 s of speech in 1.2 s, between two rows of the same speaker.
  Confirmed quiet, though only just on level.
- EdAcc dev EDACC-C18 at 0:01:52, Qwen3's "meet her Wednesday at the train
  station.": the gap is quiet (36 dB below), but these are the last words of the
  read-aloud passage the speaker had just finished. Qwen3's word times there are
  spread evenly, half a second a word, so the words were really said a few seconds
  earlier. **Not an invention**; left out of the shortlist.

## Caveats

- **Nothing has been heard yet.** Quiet speech (someone away from the microphone,
  a mutter) can read as silence.
- **Qwen3's word times are unreliable** where its aligner fails: 12 of its 29 real
  cases have a span of zero length. These may be real words placed in the wrong spot.
- **CORAAL's transcript has gaps.** Pause rows only cover a pause inside one
  speaker's talk; the time between two speakers has no row. 102 minutes of the
  27 hours are covered by no row, 137 gaps last over 2 s (longest 21 s). An
  engine writing real speech into such a gap would look like an insertion, but
  the quiet test throws those out: of 1,840 CORAAL insertions with no reference
  turn over them, 146 were quiet. The interviewer is transcribed in the same file,
  so the interviewer's talk counts as reference.
- **CORAAL's quiet is less quiet.** Its quiet cases sit about 19 dB below the
  recording, against 24 on the Supreme Court and 35-40 on EdAcc. Home recordings
  with room noise; the 15 dB rule is closer to the edge here.
- **Words shared by several engines** are more likely real speech the reference
  left out (see `shared_with`). Only 44 of the 93 real cases are by one engine alone.

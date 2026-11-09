# Labelling guidelines for flagged spots

**Version 0.2 (pilot), 15 October 2026.** Used word for word by the listening page
(`tools/listening_page/template.html`) and the judge (`tools/judge_spots.py`). Change
the version number whenever a question or a rule changes, and log the change at the
bottom. Labels made under different versions are not pooled.

Part 1 says why the labelling is done this way. Part 2 is the codebook itself.

---

## Part 1. Why it is done this way

The flagged spots are places where the speech models and the official transcript part
ways: 9,504 of them. Simple rules sorted most of them by kind, and a language model (the
"judge", Gemma 4 31B, run locally) sorted the 819 the rules couldn't place. Those counts
can only be quoted if the sorting agrees with a careful person. Measuring that is an
*annotation study*: people and an automatic labeller label the same items, and the
agreement between them is measured. That kind of study has settled methods, and the
design below follows them.

**1. Fixed, written rules, piloted and then frozen.** Annotation work runs from a written
codebook: what the unit is, what the labeller may look at, each category with what is in
and out, and what to do in borderline cases. It is tried on a small pilot, fixed where it
proved unclear, then frozen, with every later change logged. Labels made under different
rules can't be pooled. (Krippendorff, *Content Analysis*; Pustejovsky & Stubbs, *Natural
Language Annotation for Machine Learning*, the "annotate, evaluate, revise" cycle.)

**2. The unit is the flagged words; everything else is evidence.** The page highlights a
stretch of words. That stretch is what gets labelled. Hearing three sentences, or seeing
speaker names further away, can help decide, but it doesn't widen what is being labelled.
This is what stops the same spot getting a different label depending on which clip
happened to be played.

**3. What each labeller sees is fixed, or recorded.** The information a labeller has is
part of the method. So the page holds to one listening protocol (Part 2), and records
which clips were played for each spot. That makes it possible to check afterwards whether
the longer clip changes the labels.

**4. Each spot is labelled once, by ear.** The right answer for a spot is in the audio:
whether someone talked over it, whether a word was misheard. So the person's labels come
from listening, and they are what the rules and the judge are checked against. Version
0.1 also had a reading pass first, from the text alone with the audio locked, to give
the judge (which only reads text) a like-for-like comparison and to measure what the
audio adds. It was dropped in 0.2. With one labeller who always reads first, the reading
answers pull the listening answers towards them, which weakens the labels that matter
most and makes the measured gap too small. It also doubled the work. The cost is that
when the judge disagrees with the ear, it can't be told apart whether its reasoning was
wrong or it simply couldn't hear; some questions, overlap above all, can't be answered
from text at all.

**5. Observable features, each a yes or no, instead of one "kind".** "What kind of
difference is it?" asks for a judgement about cause, and people agree less on those than
on things they can observe. It also forces a ranking when several things are true at
once. So each spot gets a short list of yes/no questions about what is there: is someone
talking over it, is there a stumble, is it a name, do the two versions sound alike, and
so on. As many can be true as are true. This is how causes of recognition errors are
usually studied - as features that occur together, not one exclusive class (Goldwater,
Jurafsky & Manning 2010, "Which words are hard to recognize?", *Speech Communication*,
which also found that words near a change of speaker and disfluencies raise error rates).

**6. Agreement is measured with the standard statistics.** For each question, Cohen's
kappa between two labellers (the agreement beyond what chance alone would give). For the
whole set of features per spot, Krippendorff's alpha with the MASI distance, which gives
partial credit when two sets partly overlap (Passonneau 2006; Artstein & Poesio 2008,
"Inter-coder agreement for computational linguistics", *Computational Linguistics*). A
second person labelling part of the sample gives the person-to-person figure that the
judge should be measured against: the judge can't be expected to agree with one person
more than two people agree with each other.

**7. Who is speaking is a separate measurement, not one of these questions.** None of the
seven models writes speaker names, and the scoring removes them. So a missing name is
never a difference here. Speaker attribution is scored separately in the field (diarization
error rate; speaker-attributed word error rate such as cpWER from the CHiME-6 challenge).
This study doesn't measure it, and says so. It is where a multichannel recorder like FTR's
would matter most.

---

## Part 2. The codebook (version 0.2)

### The unit

The **spot**: the highlighted words in the official line and the matching highlighted
words in each model's line. Either side can be empty ("nothing here"). Label the spot,
not the sentence around it.

### Listening

1. Play the **sentence** clip first.
2. Play the 10-second clip or the three-sentence clip only if the sentence clip leaves
   you unsure. The page records which clips you played.
3. Answer the questions from what you hear, then say who got it right.

### The questions

Tick every one that is true of the spot. Untick means no. They are not exclusive.

1. **Overlap or hand-over.** Someone else is speaking during the spot, or a new speaker
   starts inside the spot or on the word right next to it. A justice saying "Right" while
   counsel is still talking counts. A change of speaker further away doesn't.
2. **Stumble.** The spot is, or sits right next to, a repeated word ("I -- I think"), a
   restart ("the -- to take"), a word cut off partway, or a filler that is part of a
   stumble ("uh", "um", "well", "you know", "I mean").
3. **Name or legal term.** A person, place, case name, statute name or legal term of art
   is involved: Cronic, comity, en banc, Blackledge, AEDPA.
4. **Number or citation.** A number, date, statute, section or subsection is involved:
   "3553(e)", "III", "15 cents".
5. **Same words, written differently.** Read aloud, both sides would sound the same. Only
   spelling, spacing, hyphens, an abbreviation, punctuation or a transcript convention
   differ: "e-mails" and "emails", "all right" and "alright", "Mr." and "mister".
6. **Sound-alike.** The words differ but sound alike or nearly alike: relief and belief,
   breadth and breath, "him to" and "into". Not ticked together with 5.
7. **Small word or ending.** The difference is in a short common word (a, the, is, are,
   in, and, of, to, could, can) or a word ending (-s, -ed, -ing, 's).
8. **Words on one side only.** At least one whole word on one side has no counterpart on
   the other.

Then one of these if needed:

- **None of these.** You looked and none of the eight is true.
- **Can't tell.** The audio isn't enough to answer.

### Who got it right

- **Official** - what you hear matches the official transcript.
- **Machines** - what you hear matches what most of the models wrote. Where the models
  split, compare with Qwen3's line.
- **Both reasonable** - both are fair ways to write what was said.
- **Neither** - what you hear matches neither.
- **Can't tell** - the audio isn't clear enough.

### Borderline cases

- A speaker name missing from a model's line is not a difference. Only answer question 1
  from the speech itself.
- Doubled words the reporter keeps ("for -- for") are question 2 even when the models
  dropped them; question 8 is also true if whole words are missing.
- A wrong name that sounds like the right one is both 3 and 6.
- If you'd need to guess, leave it unticked; if the whole spot is a guess, "Can't tell".

### How the old kinds map onto the questions

For comparing with labels made before version 0.1 and with the rules:

| Old kind | Questions |
|---|---|
| speaker change or overlap | 1 |
| disfluency | 2 |
| name or legal term | 3 |
| number or citation | 4 |
| not a real difference | 5 |
| misheard word | 6 |
| small word or ending | 7 |
| words left out or added | 8 |

---

## Change log

- **0.1, 13 October 2026.** First written version, for the pilot. Replaces the single
  "kind" (12 October) and the primary/secondary kinds (13 October, four spots labelled,
  kept in `findings/crowd/bench-pilot-0/`). Next: pilot on 20 spots, fix what proved
  unclear, freeze as 1.0, then run the judge.
- **0.2, 15 October 2026.** The reading pass is dropped: each spot is labelled once, by
  ear (Part 1, point 4, says why). The questions are unchanged. Nothing on the page is
  locked any more; it still records which clips were played. Labels save to the
  collection `labels-v02`. Under 0.1 only one spot was saved, and it was blank.

# Heilmeier summary

My professor specifically mentioned the Heilmeier Catechism for the capstone
proposal. The proposal (`project-overview.md`) should answer all eight questions
clearly.

George Heilmeier ran DARPA from 1975 to 1977. He wrote these questions as a test that
any proposed research project has to pass. DARPA still uses them.

Source: <https://www.darpa.mil/about/heilmeier-catechism>

This is the short version. Raw notes, sources and half-ideas go in
`heilmeier-notes.md` first; update this file from there now and then.

Last updated: 12 October 2026.

## The eight questions (DARPA's wording)

1. What are you trying to do? Articulate your objectives using absolutely no jargon.
2. How is it done today, and what are the limits of current practice?
3. What is new in your approach and why do you think it will be successful?
4. Who cares? If you are successful, what difference will it make?
5. What are the risks?
6. How much will it cost?
7. How long will it take?
8. What are the mid-term and final "exams" to check for success?

## My answers so far

**1. What am I trying to do?** Find out whether AI transcripts of court hearings are
as good as the official ones, using the Supreme Court's own recordings and
transcripts.

**2. How is it done today?** Courts use certified human reporters. AI vendors quote
accuracy measured on clean test audio, with punctuation and filler words ignored.
Court vendors call their AI output a draft ("up to 95%" for FTR). Nobody publishes
accuracy on real court audio scored as a record.

**3. What's new?** I score each model twice, the benchmark way and as a record, against
a certified transcript. I also find where models drop speech without any sign. Every
model scored 2-4 times worse as a record. I know what a record needs because I've
been a court reporter for 15 years.

**4. Who cares?** Courts deciding whether to buy AI transcription, court reporters
and certification boards, and lawyers who depend on the record for appeals. A bill
in Congress (H.R. 7997 / S. 4154) would set up a federal task force to study exactly
this.

**5. Risks?** I have a stake in the answer. There's no human baseline yet, so the
error rates have no scale. And the scoring treats the official transcript as
correct.

**6. Cost?** Close to nothing: free public data, free open models, a laptop I own.
Hiring a reporter for a human baseline is the one real cost, still unpriced.

**7. How long?** Open - need the semester deadlines.

**8. Checkpoints?** Open - not chosen yet.

## Notes to self

- Question 1 means plain English. If someone outside data science can't follow the
  objective, rewrite it.
- The "exams" (8) should be concrete checkpoints I can point to, not "the project
  is done."

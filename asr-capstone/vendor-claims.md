# What vendors claim about accuracy

Checked online on 12 October 2026. Vendor pages change and disappear, so every quote
below says where it came from and whether I saw the page myself.

Follow-up (17 Oct 2026): stronger claims (FTR's homepage now says 98%), buyers'
documents, and how digital reporting went for courts and lawyers are in
`digital-reporting-claims.md`.

The short version: the "2-3% error" figures come from general-purpose speech models
scored on public benchmarks. The vendors selling into courtrooms claim less than that
for the AI alone, and they call its output a draft.

## General-purpose speech models

- **Google, Gemini 3.5 Transcribe: 2.6% word error rate.** The number comes from
  Artificial Analysis, an independent leaderboard that tests on about eight hours of
  audio from three public datasets. It is not courtroom audio.
- Benchmark scores like this strip punctuation, capitals and filler words before
  counting errors. See `project-overview.md` for why that matters here.

## For The Record (FTR)

One of the largest vendors of courtroom recording. Its AI product is **FTR RealTime**.

**Who owns it.** Tyler Technologies agreed in February 2026 to buy For The Record for
about $212.5 million in cash (trade press, seen myself). FTR's homepage now says: "In
April 2026, Tyler Technologies acquired For The Record."

**How it records.** The FTR Gold recorder takes up to 16 separate audio channels
(FTR Gold product sheet, July 2026, from search results). In practice courts often
group microphones: a McAllen, Texas federal courtroom spec groups its microphones into
4 channels for the FTR recorder. So a channel is often a position in the room (the
bench, a counsel table, the witness box), not one person. The Supreme Court audio in
this project is a single mixed channel.

**Does RealTime use the separate channels? Yes, by FTR's own description,** though FTR
never says how. From the RealTime page (seen myself):

- a "live speech-to-text feed synced with multi-channel audio—just seconds behind the
  spoken word," which gives the system "time to analyze and process multiple
  speakers"
- "Identifies speakers and attributes speech correctly even during overtalk"
- "Instant language detection across different talkers and audio channels"
- handles "overlapping dialogue using multi-pass processing"

Also: the 2022 trade article (seen myself) says that with FTR Smart Audio, FTR's
courtroom audio setup, RealTime "approaches speaker designation accuracy of up to
100%." The RealTime Portable Kit offers "up to eight audio channels, configurable with
custom labels for speaker attributed text" (from search results; the product sheet
returned "not found"). So the speaker labels very likely come from which channel the
voice is loudest on.

What FTR does not say: whether it runs speech recognition on each channel separately,
or on a mix with the channels used only to label speakers, or what "multi-pass" means.
Every microphone picks up everyone in the room, so running each channel separately
would transcribe the same words several times; something has to decide which channel
owns each moment.

**Human transcribers use the channels too.** FTR's Player guide (a court's copy, read
myself) says you can switch each channel on or off, which "is useful if you have
trouble understanding the speaker on one channel or if two or more people speak at the
same time on different channels."

**What speech engine it uses: not said.** The current pages say only that RealTime is
"powered by FTR Justice Cloud" and uses "multi-pass processing." The 2022 launch article
(seen myself) says FTR applied AI "from top-tier platforms—such as AWS and
Microsoft—to millions of hours of acoustically optimized legal proceedings." So it is
probably a commercial cloud engine adapted with court audio, but which one, and whether
that is still true, is not public. A Microsoft Marketplace listing for FTR's courtroom
speech-to-text says it runs on Azure Government (from search results only - the
listing blocked my request).

**The accuracy claim: "up to 95%."** From the FTR RealTime product page (seen myself):

- "Provides an instantaneous, keyword searchable draft transcript with up to 95%
  accuracy"
- "Up to 95% Real-Time Accuracy"

95% accuracy means at least 5 wrong words in every 100, and "up to" makes it the best
case. The page does not say how it was measured, on what audio, or whether punctuation
counts.

**Does FTR say a human has to check it?** Only for a certified transcript. Whether
anyone checks the draft otherwise is left to the court.

- The page for court reporters and transcribers (seen myself) says: "We understand that
  people, not machines, create certified transcripts," and that the tools are "built to
  empower transcription professionals, not replace them." It calls the AI output
  "accurate, searchable rough drafts that accelerate the transcription process."
- The FTR RealTime page (seen myself) pitches the unchecked draft for use during
  proceedings, with judges "no longer relying on certified transcripts." It says the
  recording, not the text, "remains the definitive source of truth." It never mentions
  a human reviewing the draft.
- The 2022 launch article (seen myself, dated 11 March 2022) went further: "With
  unprecedented accuracy of up to 95%, FTR RealTime eliminates the need to hire costly
  specialists for same-day transcription services," and "Lawyers will have the records
  they need to work on appeals." No review step is mentioned.

So the human step is required only when someone orders a certified transcript. For
everything else, including uses like preparing an appeal in the 2022 wording, the draft
is offered as good enough on its own. The current pages are more careful than the 2022
launch.

**FTR QuickDraft (not confirmed).** Search results describe a second product that
"bridges the gap between audio capture and certified transcript production," producing
an uncertified transcript for reporters and transcribers to work from, "up to 95%"
accurate with speakers labelled "up to 100%" accurately. The product page and its PDF
both returned "page not found" when I tried them, so I have not seen these words
myself.

## Verbit

- Claims "99% accurate" transcripts for legal work, but that figure is after human
  review. Certified court reporters and electronic reporters check the AI output.
- The AI alone: an earlier company-cited report said about 90%. A third-party profile
  says 87-95%. That profile is from an aggregator site, so weigh it lightly.

## VIQ Solutions

- Launched NetScribe Live on 9 September 2026, a real-time recording and transcription
  platform for court proceedings. No accuracy figure found. (From the September scoping
  report.)

## How this lines up with this project's numbers

On the benchmark rule, the best open model here, Qwen3-ASR, gets 4.9% of words wrong:
about FTR's "up to 95%." Scored as a record - punctuation, capitals and every spoken
word counted - the same model gets 15.9% wrong. FTR does not say which way it counts,
so the two numbers cannot be compared directly. But the gap shows how much "95%
accurate" can leave out.

## Congress is looking at this

The **Research and Oversight of AI in Courts Act of 2026** (H.R. 7997 in the House,
S. 4154 in the Senate) was introduced in March 2026 with sponsors from both parties. It
would set up a 15-member task force to study AI speech-to-text in federal courts,
including how accurate the record is. The National Court Reporters Association backs
it. As far as I could find in October 2026 it has not passed. News reports disagree
about who would sit on the task force, so check the bill text before quoting that part.

## Sources

- [FTR RealTime product page](https://fortherecord.com/our-solutions/ftr-realtime)
- [FTR, court reporters and transcribers](https://fortherecord.com/solutions/stakeholder/court-reporters-and-transcribers/)
- [FTR RealTime launch article, March 2022](https://fortherecord.com/resource/groundbreaking-speech-to-text-technology-debuted-at-legalweek/)
- [Speech Technology: For the Record Launches FTR RealTime](https://www.speechtechmag.com/Articles/News/Speech-Technology-News/For-the-Record-Launches-FTR-RealTime-156204.aspx)
- [Verbit legal transcription](https://verbit.ai/solutions-legal-transcription)
- [TechRadar Verbit review](https://www.techradar.com/reviews/verbit-review)
- [Artificial Analysis speech-to-text leaderboard](https://artificialanalysis.ai/speech-to-text)
- [H.R. 7997 bill text](https://www.govinfo.gov/content/pkg/BILLS-119hr7997ih/html/BILLS-119hr7997ih.htm)
- [Rep. Hageman press release](https://hageman.house.gov/media/press-releases/rep-hageman-introduces-bipartisan-bill-sens-wicker-welch-examine-use-ai-speech)
- [FedScoop on the bill](https://fedscoop.com/us-courts-would-study-ai-speech-to-text-under-bipartisan-bicameral-bill/)

# Can you get the audio of an FTR-recorded hearing, or only the transcript?

Researched online on 12 October 2026. Rules are set court by court and change, so
check the court's current rule before relying on any example here.

## Short answer

Usually you can get the audio, and often anyone can, not just the lawyers. But the
audio is almost never the official record. Only a certified transcript is. Limits
depend on the type of case and on the court, not mainly on whether you are a lawyer.

## Federal courts

- The Judicial Conference let judges who record digitally put the audio on PACER, at
  each judge's discretion, for $2.40 a file (approved 2010 after a two-year pilot).
  Many bankruptcy courts do this: an MP3 inside a PDF on the docket, usually within a
  day or two of the hearing.
- Otherwise you buy a copy from the clerk: $34 a disc at the Court of Federal Claims
  and the Southern District of Florida bankruptcy court; $33 a CD in the Northern
  District of Ohio bankruptcy court. Files are often in FTR's own format and need the
  free FTR Player.
- Some courts give attorneys on the case one free listen.
- The audio is a convenience copy. Northern District of New York: the official record
  is the written transcript. Montana bankruptcy: the audio can't be used to make
  official transcripts. Southern District of Florida bankruptcy: no party may have the
  audio transcribed and file that transcript.

## State courts - examples

| Where | Who can get audio | Notes |
|---|---|---|
| North Dakota | parties and their lawyers, free | unless a court order restricts it |
| Nebraska | participants and counsel, even for closed hearings | must notify the other parties, who can object within 10 days |
| Michigan, 7th Circuit Court | parties and lawyers of record, under a limited-use agreement | anyone else must file a motion; the judge decides |
| Colorado | requesters generally, $35 a disc | listening only, not the official record, not admissible. One district (12th) gives copies only for an appeal |
| Oregon | requesters generally, 5-10 business days | state law limits juvenile, adoption and protective-order cases |
| Washington (Benton/Franklin counties, FTR courtrooms) | requesters generally | "for verification of testimony only"; official transcripts only from a certified reporter or approved transcriptionist |
| Idaho (Bannock County) | on approval | granted audio "is not an official court record" |

Canada for comparison: the Federal Court gives copies to one representative of each
party and each media organisation, and the judge decides for members of the public.
Nova Scotia makes requesters promise not to broadcast without a judge's consent.

## FTR's own ordering site

FTR runs a portal (FTR Justice Cloud / Express Access) where "attorneys,
self-represented litigants, journalists, and members of the public" can order audio
and, where offered, transcripts from participating courts. Each court decides what is
released and to whom. (From FTR's pages via search results; the page itself gives no
rules.)

## So, the guess that lawyers get audio and the public doesn't

Partly right. The public can often buy the audio too. The real lines are:

- **Case type.** Juvenile, adoption, sealed and protected cases are restricted almost
  everywhere.
- **The court's own policy.** A few courts release only to parties, or only for an
  appeal, or only with a judge's approval.
- **What you may do with it.** Some courts let you listen but not publish (limited-use
  agreements, no-broadcast promises).

## Why this matters for the project

- Audio from FTR-recorded state courts, paired with a certified transcript of the
  same hearing, could be a second test set: trial-court audio, possibly with separate
  microphone channels. But the parties are private people, and use limits like
  Michigan's or Nova Scotia's would stop it being published. That would break this
  project's rule that anyone can rerun it. The Supreme Court data has no such limits.
- In these courts the transcript is usually typed from the recording afterwards, not
  taken down live in the room, which is a different kind of reference from the Supreme
  Court's.

## Getting audio and transcripts for this project (looked into 12 Oct 2026)

**What you get.** One `.trm` file per recording, with all the channels inside it, not
one file per microphone. The free FTR Player can play or mute each channel but is not
documented to save them separately. Converting `.trm` to ordinary audio needs FTR
Manager (part of the paid FTR Annotation Suite, 14-day free trial) or the court doing
it, and courts usually convert to MP3, which mixes the channels together. The PACER
audio files are MP3s, so probably mixed. How many channels a courtroom has varies (4 is
common).

**The cheap route: federal bankruptcy court.**

- Audio: $2.40 a file on PACER where the judge allows it (MP3, probably mixed), or
  about $33-34 a disc from the clerk (`.trm`, channels kept).
- Transcript: once a transcript has been filed for 90 days, anyone can download it
  from PACER for $0.10 a page, with no 30-page cap. A one-hour hearing at about 50
  pages is about $5.
- So a matched pair costs roughly $8 (mixed audio) or $40 (separate channels).
- The transcript is typed from the recording by a certified transcriber, not taken
  down live.

**The human floor, for real money.** Buy the audio of a hearing that already has a
filed transcript, and pay a certified transcriber (AAERT) to transcribe it without
seeing the filed one. Federal maximum rates (from October 2024) are $4.40 a page for
30-day delivery, so about $200-250 per hour of audio. Both transcripts would come from
the same recording, which makes it a fairer comparison than the Supreme Court one
(live reporter against someone working from audio).

**Can it be published?** Recordings made by court employees are probably public
domain as federal government work (17 U.S.C. 105) - my reading, not checked with a
lawyer. Transcripts by contract transcribers are less clear; a 2009 Tenth Circuit
decision (unpublished) said reporters don't own copyright in a transcript of others'
words. The safe path: publish the code and the docket numbers so anyone can buy the
same files, not the files themselves. Choose business Chapter 11 cases over consumer
cases, to keep private people's finances out of it.

## The $100 plan (decided 12 Oct 2026)

- **PACER is free under $30 a quarter.** PACER's pricing page: "Spend $30 or less on
  court records in a quarter and fees are WAIVED." Docket pages, transcripts and audio
  all count toward it. Browse on CourtListener (free) first, and buy only what is
  needed on PACER.
- **Step 1, free:** 3 hearings, each with its MP3 audio and its filed transcript,
  kept under $30 for the quarter.
- **Step 2, about $70:** the `.trm` file with separate channels for 2 of them, from
  the clerk.
- **The human floor, free:** I transcribe one hearing myself from the audio, before
  opening its filed transcript or any machine output. I hold an RPR; at least one
  federal bankruptcy court (N.D. Fla.) accepts an RPR to transcribe its recordings,
  as do AAERT's CET or a state credential. The write-up has to say I did it myself
  and have a stake in the answer.

How to choose hearings: a court that posts audio on PACER and records with FTR;
Chapter 11 business cases; a transcript filed more than 90 days ago; 20-60 minutes
(transcripts on PACER have no price cap); in the courtroom rather than by phone or
Zoom if the docket shows it; one contested hearing with several lawyers and one
routine one.

## Sources

- [S.D. Fla. Bankruptcy, digital audio FAQs](https://www.flsb.uscourts.gov/sites/flsb/files/documents/Digital_Audio_Recording_FAQs_%28rev.%2002.20.2025%29.pdf)
- [N.D. Ohio Bankruptcy, audio order form](https://www.ohnb.uscourts.gov/sites/default/files/file-list/audio-order-form-fillable-2025.pdf)
- [Court of Federal Claims fee schedule](https://www.cfc.uscourts.gov/sites/cfc/files/25.07.28%20UPDATED%20Fee%20Schedule.pdf)
- [Minnesota Lawyer: PACER access to be wider and cheaper (2010)](https://minnlawyer.com/2010/03/22/pacer-access-to-be-wider-and-cheaper/)
- [C.D. Ill. Bankruptcy, audio files of hearings](https://www.ilcb.uscourts.gov/audio-files-court-hearings)
- [D. Minn. Bankruptcy, audio on PACER](https://www.mnb.uscourts.gov/digital-audio-recordings-available-pacer)
- [N.D.N.Y. Bankruptcy, CourtSpeak](https://www.nynb.uscourts.gov/courtspeak-program)
- [D. Mont. Bankruptcy](https://www.mtb.uscourts.gov/node/155)
- [S.D. Ind. Bankruptcy, hearing file availability](https://www.insb.uscourts.gov/sites/insb/files/hearing-file-availability.pdf)
- [North Dakota Administrative Rule 40](https://www.courtrules.net/north_dakota/north-dakota-administrative-rules/rule-40)
- [Nebraska Judicial Branch](https://nebraskajudicial.gov/book/export/html/9169)
- [Michigan 7th Circuit Court, digital copies](https://files.7thcircuitcourt.com/departments/court_technology/cd.php)
- [Colorado Judicial Branch](https://api-ac.coloradojudicial.gov/media/273)
- [Oregon, Washington County Circuit Court audio copies](https://www.courts.oregon.gov/courts/washington/records/Pages/AudioCopies.aspx)
- [Oregon, Grant/Harney juvenile audio order](https://www.courts.oregon.gov/courts/grant/go/SiteAssets/Pages/Presiding-Judge-Orders/26-014%20JUV%20Audio%20Recordings.pdf)
- [Franklin County, WA, audio requests](https://franklincountywa.gov/233/Audio-Recordings-Request)
- [Benton County, WA, authorized transcriptionists](https://www.bentoncountywa.gov/departments/courts_and_judicial_services/superior_court/processes_procedures/b_general/authorized_transcriptionists.php)
- [Bannock County, ID, records request](https://www.bannockcounty.gov/wp-content/uploads/2025/09/Records-Request-6D-Information-Page.pdf)
- [Federal Court of Canada, DARS notice (2015)](https://www.fct-cf.ca/content/assets/pdf/base/DARS%20Notice%20feb-6-2015%20(ENG).pdf)
- [Nova Scotia audio request form](https://www.courts.ns.ca/sites/default/files/forms/audio_request_form_interactive_31-03-23.pdf)
- [FTR Express Access](https://fortherecord.com/our-solutions/ftr-express-access/)
- [FTR participating courts](https://fortherecord.com/participating-courts)

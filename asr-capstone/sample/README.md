# Verification sample — Supreme Court oral argument audio and transcripts

Six cases pulled straight from supremecourt.gov on 13 September 2026, to check by hand
that the audio and the official transcripts really are what the capstone needs. This is
also the pipeline's default `sample_dir`: running with `config/default.yaml` transcribes
the three cases that have audio, and `runs/run-20260916-041602/` is that run.

Every file is a U.S. Government work and is in the public domain.

## What is here

| Folder | Argued | Audio | Speaker labels |
|---|---|---|---|
| `OT2003_02-763_Barnhart_v_Thomas` | 14 Oct 2003 | — | `QUESTION:` (71 of 72 bench turns) |
| `OT2004_04-104_United_States_v_Booker` | 4 Oct 2004 | — | named justices (210 of 211) |
| `OT2004_03-633_Roper_v_Simmons` | 13 Oct 2004 | — | named justices (all 122) |
| `OT2010_09-834_Kasten_v_Saint_Gobain_Performance_Plasti` | 13 Oct 2010 | 55.9 min | named justices |
| `OT2024_24-316_Kennedy_Sec_of_H_HS_v_Braidwood_Mgmt_Inc` | 21 Apr 2025 | 86.2 min | named justices |
| `OT2025_24-109_Louisiana_v_Callais` | 15 Oct 2025 | 150.1 min | named justices |

The three older cases are transcript-only on purpose. The Court's own site does not host
audio before the 2010 term. They are here to pin down when the transcripts started naming
individual Justices.

The Braidwood folder also holds `case_documents/`: 12 of the 100 filings on that case's
docket, downloaded to test whether a case's own briefs could supply a vocabulary list. That
idea was later dropped.

## Files in each folder

- `<docket>_transcript.pdf` — the official transcript, exactly as the Court serves it
- `<docket>_transcript.txt` — the same thing run through `pdftotext -layout`. Kept for
  reference; the pipeline reads the PDF itself with PyMuPDF.
- `<docket>_audio.mp3` — the official recording (64 kbps mono). **Not in git** (134 MB in
  all). Fetch them with `python fetch_sample_media.py`, which reads the URLs from
  `manifest.json`.

## Two things to know before reusing this

**The audio URL cannot be built from the docket number.** Louisiana v. Callais was
reargued, so the October 2025 recording is served at `24-109_2.mp3`. Plain `24-109.mp3`
is the *first* argument, from March 2025, and pairing it with the October transcript
would silently mismatch 150 minutes of audio against the wrong record. The audio link
has to be read off the term's argument-audio index page. See `NOTE_reargument.txt` in
that folder.

**Modern transcripts end with a keyword index.** After the argument text, the PDF carries
an alphabetical index whose lines also start with digits, exactly like the numbered
transcript lines. Counting words without cutting it off inflates the total by roughly a
sixth. The pipeline's parser stops at the "(Whereupon ... was submitted.)" line.

A quick check that audio and transcript belong together is speaking rate: spoken words
divided by audio minutes. The pipeline flags anything outside 145 to 210 words a minute.

## The old transcripts (`OCR_example/`)

Before 2000 the Court's PDFs are scanned page images with an old OCR text layer on top.
This folder holds one complete 1969-term transcript (`69-13_05-04-1970.pdf`), page 6
rendered as an image (`1969_page_as_scanned.png`), and the text the PDF already carries for
that page (`1969_page_existing_OCR_layer.txt`).

The page is faded but every word is legible. The existing text layer reads, in part:

> this Court held that it could note -that the record in his case disclosed a violation of
> zhe rule of Witherspoon vs. Illinois, in -the process by which jurors hi.i. been death
> qualified

where the image says "the rule", "had been", and has no hyphens. Those are the marks of an
old OCR engine on faint ink, not of a damaged source, so the pages can be read again. The
pipeline's `ocr` stage does that. It finds the 1–25 margin line numbers by their position
on the page rather than by reading the digits, and reads the words with GLM-OCR. Results are
in `pipeline/README.md`.

This is a side quest. The pre-2010 transcripts have no matching audio on the Court's site,
so they only matter if the study is ever extended back before 2010.

The old transcripts also show three labelling eras:

| Era | Bench label | Counsel label | Format |
|---|---|---|---|
| ~1968–1970 | `Q` | `A` | scanned image + OCR text layer |
| ~1972–2003 | `QUESTION:` | `MR. SURNAME:` | scanned image + OCR text layer |
| OT2004– | `JUSTICE SURNAME:` | `MR. SURNAME:` | born-digital text |

Sampled pages from 1969 through 1999 all carry page images; 2003, 2010 and 2025 carry none
and have real embedded fonts. **The changeover to born-digital PDFs is at the 2000 term.**

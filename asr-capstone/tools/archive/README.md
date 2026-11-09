# Archived tools

Scripts for experiments that are finished. Their results are in `findings/`, and
they are kept so those results can be traced back to the code that made them.
They are not maintained and may not match the current pipeline.

| Script | What it was for | Result |
|---|---|---|
| `aligner_control.py` | Does the shared forced aligner invent silence? | `findings/aligner-control.csv` - it roughly doubles it |
| `rescore_with_seam_fix.py` | Re-score every run after the seam fix | `findings/seam-fix-before-after.csv` - the fix now lives in `stages._load_asr_result` |
| `redecode_looping_cases.py` | Re-transcribe the 11 cases with undetected loops | `findings/phase3-final-rescore.csv` |
| `parse_transcript.py` | The first transcript parser, using `pdftotext` | Replaced by `pipeline/scotus_asr/transcripts/` |
| `transcript_turns/` | What that first parser produced for the six sample cases | Nothing reads these now |
| `parakeet_stall/` | Why Parakeet leaves minutes of speech blank (23 Oct 2026): gap counts, the full-stop test, chunk lengths, the gap re-read, the random sample and the full before-and-after | `findings/parakeet-stall/`. They wrote their transcripts to a scratch folder, not kept; `parakeet_rechunk.py` and `parakeet_reread.py` make them again |

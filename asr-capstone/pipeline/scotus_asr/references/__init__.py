"""Readers for reference transcripts, whatever file they arrive in.

Phase 1 of `app-roadmap.md`: a corpus adapter (or, later, someone's own folder of
audio and transcripts) should not need its own parser for a common format. Each
module here reads one kind of file into rows and turns rows into a `Transcript`.

- `timed_table` - delimited text with one timed utterance per row (CORAAL's .txt).
- `nlp` - Rev's one-token-per-line format (Earnings-22).

STM and CTM are still in `corpora/formats.py`, where EdAcc first needed them.
"""

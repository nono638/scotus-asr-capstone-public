"""Turning an official transcript PDF into the reference text.

Three steps, kept apart because they fail differently:

    extract   PDF to numbered lines, keeping the page and line each came from
    parse     numbered lines to speaker turns
    speakers  tidy up the speaker names
"""

from .model import Line, Page, Turn, Transcript


def __getattr__(name):
    # The PDF reader needs PyMuPDF. Load it only when asked for, so code that
    # just needs the Transcript model (scoring, other corpora) never imports it.
    if name == "extract_lines":
        from .extract import extract_lines
        return extract_lines
    if name == "parse_transcript":
        from .parse import parse_transcript
        return parse_transcript
    raise AttributeError(name)


__all__ = ["Line", "Page", "Turn", "Transcript", "extract_lines", "parse_transcript"]

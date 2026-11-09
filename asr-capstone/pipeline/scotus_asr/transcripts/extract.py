"""Pulling numbered lines out of a transcript PDF.

Only the numbered lines carry spoken words. The running header, the page number,
the cover sheet, the table of contents and the appearance list are all page
furniture, and the margin numbers 1 to 25 are what separate one from the other.

Why this does not use `pdftotext`
---------------------------------
The original `parse_transcript.py` shelled out to poppler's `pdftotext -layout`.
That works, but it needs a program installed outside Python - and it is not
installed on this machine. It survives only because the `.txt` files were already
made; a new case would fail. PyMuPDF is already a dependency and needs nothing
external.

Why this groups by vertical position
------------------------------------
PyMuPDF puts the margin number and the body text in *different* blocks. On a real
page the number "5" arrives in one block and the words beside it in another, and
every fifth number turns up in a block of its own before any body text at all. So
the page is rebuilt by rounding each piece's vertical position and grouping: two
pieces at the same height are the same line, whatever block they came from.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from .model import Line, Page

#: A margin line number: one or two digits and nothing else.
_LINE_NUMBER = re.compile(r"^\d{1,2}$")

#: A margin number and the words in one piece, laid out with spaces rather than
#: placed separately: "             1             JUSTICE THOMAS: ...". Three
#: OT2025 PDFs (24-699, 24-781, 24-993) are built this way, and the strict rule
#: above read no lines from them at all. The leading spaces and the two spaces
#: after the number are what keep "5 percent of the..." from matching.
#:
#: The words must hold a letter or digit. Some OT2017 PDFs put a lone "--" (an
#: interruption carried onto its own line) in one piece with its number; those
#: lines were always dropped, and keeping them now would change five records
#: that published results were scored against, by a dash or two each.
_NUMBER_AND_WORDS = re.compile(r"^\s+(\d{1,2})(?:\s{2,}(.*[^\W_].*))?\s*$")

#: Two pieces of text within this many points of each other, vertically, belong
#: to the same line. Lines on these transcripts are about 26 points apart, so
#: there is a lot of room either side of this.
_Y_TOLERANCE = 3.0

#: In most OT2013 and OT2014 PDFs (and three OT2015 ones) the margin number on
#: every line after the first of a turn sits 3.4 points *above* its words, just
#: past the tolerance, so the number and the words came out as two rows and both
#: were dropped: only the first line of each turn survived. A row holding nothing
#: but a number is joined to an unnumbered row this close below it. Raising the
#: tolerance instead would also shift almost every OT2016-2025 record by a few
#: dozen words, and those are what published results were scored against.
_LIFTED_NUMBER_GAP = 6.0

#: Running headers and reporter footers. These sit outside the numbered lines
#: anyway, but a page where the number is missing would otherwise let them in.
_FURNITURE = re.compile(
    r"Official\s*-\s*Subject to Final Review"
    r"|Alderson Reporting"
    r"|Heritage Reporting"
    r"|www\.hrccourtreporters\.com"
    r"|1-800-FOR-DEPO",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    """Tidy one line's text without changing what was said.

    Soft hyphens are a rendering artefact of the justified layout and are not
    part of the words. Everything else - the double dashes that mark an
    interruption, the real punctuation - is left exactly as it is, because
    whether a model reproduces punctuation is one of the things being measured.
    """
    text = text.replace("\xad", "")          # soft hyphen
    text = text.replace(" ", " ")       # non-breaking space
    return " ".join(text.split())            # collapse runs of whitespace


def _page_pieces(page: pymupdf.Page) -> list[tuple[float, float, str]]:
    """Every run of text on a page, as (vertical position, left edge, text)."""
    pieces: list[tuple[float, float, str]] = []
    content = page.get_text("dict")
    for block in content.get("blocks", []):
        # Type 0 is text. Type 1 is an image, which on these pages means a scan.
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if not text.strip():
                continue
            x0, y0, _x1, _y1 = line["bbox"]
            pieces.append((y0, x0, text))
    return pieces


def _group_into_rows(
    pieces: list[tuple[float, float, str]]
) -> list[tuple[float, list[tuple[float, str]]]]:
    """Group pieces that sit at the same height into rows.

    Returns:
        One (height, row) pair per row, top to bottom. Each row holds (left edge,
        text) sorted left to right.
    """
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    current: list[tuple[float, str]] = []
    current_y: float | None = None

    for y0, x0, text in sorted(pieces, key=lambda p: (p[0], p[1])):
        if current_y is None or abs(y0 - current_y) <= _Y_TOLERANCE:
            current.append((x0, text))
            # Anchor on the first piece of the row so a gradual drift down the
            # page cannot merge two real lines into one.
            current_y = current_y if current_y is not None else y0
        else:
            rows.append((current_y, sorted(current)))
            current = [(x0, text)]
            current_y = y0

    if current:
        rows.append((current_y, sorted(current)))
    return rows


def _join_lifted_numbers(
    rows: list[tuple[float, list[tuple[float, str]]]]
) -> list[list[tuple[float, str]]]:
    """Put a number that sits just above its words back on the same row.

    See `_LIFTED_NUMBER_GAP`. A row is joined only when it is a bare number and
    the row just below has no number of its own, so ordinary pages, where the
    next row is a whole line (about 26 points) further down, are untouched.
    """
    joined: list[list[tuple[float, str]]] = []
    index = 0
    while index < len(rows):
        y, row = rows[index]
        if index + 1 < len(rows):
            next_y, next_row = rows[index + 1]
            bare_number = len(row) == 1 and _LINE_NUMBER.match(row[0][1].strip())
            if (bare_number and next_y - y <= _LIFTED_NUMBER_GAP
                    and _split_line_number(next_row)[0] is None):
                joined.append(row + next_row)
                index += 2
                continue
        joined.append(row)
        index += 1
    return joined


def _split_line_number(row: list[tuple[float, str]]) -> tuple[int | None, float, str]:
    """Separate a row's margin number from its words.

    The number is taken only from the leftmost piece, and only if that piece is
    nothing but one or two digits. That is deliberately strict: a row beginning
    with a number that is part of a sentence ("5 percent of the...") arrives as
    one piece of text, not as a bare digit in its own right, so it cannot be
    mistaken for a margin number.

    Returns:
        (line number or None, left edge of the words, the words).
    """
    if not row:
        return None, 0.0, ""

    first_x, first_text = row[0]
    stripped = first_text.strip()

    if _LINE_NUMBER.match(stripped) and len(row) >= 1:
        rest = row[1:]
        text = _clean(" ".join(piece for _x, piece in rest))
        left = rest[0][0] if rest else first_x
        return int(stripped), left, text

    joined = _NUMBER_AND_WORDS.match(first_text)
    if joined:
        words = [joined.group(2) or ""] + [piece for _x, piece in row[1:]]
        return int(joined.group(1)), first_x, _clean(" ".join(words))

    return None, first_x, _clean(" ".join(piece for _x, piece in row))


def extract_lines(pdf_path: Path | str) -> tuple[list[Page], int]:
    """Read a transcript PDF into numbered lines.

    Args:
        pdf_path: The official transcript.

    Returns:
        The pages that carry numbered lines, and the PDF's total page count.
        Pages with no numbered lines at all - the cover, the contents - come back
        with an empty list rather than being dropped, so page numbers still line
        up with the PDF.

    Raises:
        FileNotFoundError: If the PDF is not there.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"No transcript PDF at {pdf_path}")

    pages: list[Page] = []
    with pymupdf.open(pdf_path) as document:
        page_count = document.page_count
        for index, page in enumerate(document, start=1):
            lines: list[Line] = []
            for row in _join_lifted_numbers(_group_into_rows(_page_pieces(page))):
                number, left, text = _split_line_number(row)
                if number is None or not text:
                    continue
                if _FURNITURE.search(text):
                    continue
                lines.append(Line(page=index, number=number, text=text, x0=left))
            pages.append(Page(number=index, lines=lines))

    return pages, page_count


def has_page_images(pdf_path: Path | str) -> bool:
    """Is this PDF a scan rather than real text?

    Used to decide whether a case needs OCR. A born-digital transcript has no
    images at all; a scanned one is a full-page picture per page. All six sample
    transcripts are born-digital; only the 1969 example is scanned.
    """
    with pymupdf.open(Path(pdf_path)) as document:
        for page in document:
            if page.get_images():
                return True
    return False

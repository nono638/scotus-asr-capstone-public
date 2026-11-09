"""Working out a scanned page's structure from where the words sit.

This module contains the decision the whole OCR design turns on, so it is worth
setting out plainly.

Every transcript page has lines numbered 1 to 25 down the left margin. Those
numbers are what separate spoken text from page furniture - the running header,
the page number, the reporter's footer - so recovering them is not a nicety. Get
them wrong and the transcript parser has nothing to work with.

The tempting approach is to ask a vision model to transcribe the page including
the numbers. That fails in a particular and nasty way. A column of bare integers
carries almost no linguistic signal, which is exactly the situation where a
model's language prior is least constrained by what is actually in the image. Show
it a faded "7" in a run of 1 to 25 and it will produce "7" whether or not the ink
is legible - and if the digit is missing altogether it will helpfully supply the
number that ought to be there. The result looks perfect and is unverifiable.

So the numbers are never read. They are **counted**. The boxes in the left margin
are sorted top to bottom and numbered by their position in that order. Whatever
the OCR thought each digit said is kept only as a cross-check: where the rank and
the read digit disagree, that is recorded as a quality flag rather than quietly
resolved. This is immune to the misreads already visible in the existing text
layer, where line numbers come out as "z", "0", "i f" and "IS".
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Sequence

#: How wide the line-number column is, as a share of the page width. Measured
#: from the leftmost number rather than from the page edge, so it only has to
#: cover the column itself: the skew of a scan, plus the width of a second digit.
_GUTTER_BAND = 0.05

#: Fewer boxes than this in the left margin is not a column of line numbers.
#: Cover pages and dividers carry no numbered lines and should say so, rather
#: than report whatever short words happened to sit furthest left.
_MINIMUM_COLUMN = 3

#: Margin boxes closer together than this share of the line spacing are the same
#: line number, split in two by a bad reading.
_SAME_ROW = 0.3


@dataclass(frozen=True)
class TextBox:
    """One piece of text an OCR engine found, and where it sat on the page.

    Coordinates are in pixels, with the origin at the top left, which is what
    every engine here returns.
    """

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float | None = None

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class GutterLine:
    """One margin line number, identified by position rather than by reading.

    Attributes:
        rank: Position from the top, counting from 1. **This is the line number.**
        printed: What the OCR thought the digit said, kept only to check against
            `rank`. None when the engine returned nothing.
        y_center: Vertical middle of the number, used to pick out the words that
            belong to this line.
        agrees: Whether the read digit matches the rank. False is a flag for
            review, not an error to correct.
    """

    rank: int
    printed: str | None
    y_center: float
    agrees: bool


@dataclass
class PageGeometry:
    """What was worked out about the layout of one scanned page.

    Attributes:
        page: Page number, counting from 1.
        lines: The margin numbers found, in order down the page.
        body_left: Left edge of the spoken text, just right of the margin.
        body_top: Top of the first numbered line.
        body_bottom: Bottom of the last one.
        warnings: Anything that did not look right.
    """

    page: int
    lines: list[GutterLine] = field(default_factory=list)
    body_left: float = 0.0
    body_top: float = 0.0
    body_bottom: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def line_count(self) -> int:
        """How many margin numbers were actually detected."""
        return len(self.lines)

    @property
    def highest_line(self) -> int:
        """The largest line number worked out, 25 on a full page.

        Differs from `line_count` when a number was too faint to detect: the
        spacing still says which line it was, so the count of boxes is short
        while the numbering stays right.
        """
        return max((line.rank for line in self.lines), default=0)

    @property
    def missing_numbers(self) -> list[int]:
        """Line numbers the spacing implies but no box was found for.

        These are lines whose text was still read - only the number in the margin
        was missed - so this is a measure of scan quality, not of lost content.
        """
        found = {line.rank for line in self.lines}
        return [n for n in range(1, self.highest_line + 1) if n not in found]

    @property
    def disagreements(self) -> int:
        """How many read digits did not match their position.

        The honest quality measure for a page: it counts what the OCR got wrong
        about something whose right answer is known independently.
        """
        return sum(1 for line in self.lines if not line.agrees)

    @property
    def body_box(self) -> tuple[float, float, float, float] | None:
        """The area to crop for reading the words, or None if no lines were found.

        Cropping here is what makes the design safe. The margin numbers are not
        in the cropped image, so a vision model reading it cannot invent them -
        not because it was told not to, but because they are not there.
        """
        if not self.lines:
            return None
        return (self.body_left, self.body_top, float("inf"), self.body_bottom)

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        return {
            "page": self.page,
            "line_count": self.line_count,
            "disagreements": self.disagreements,
            "body_left": round(self.body_left, 1),
            "body_top": round(self.body_top, 1),
            "body_bottom": round(self.body_bottom, 1),
            "lines": [asdict(line) for line in self.lines],
            "warnings": self.warnings,
        }


def _leading_number(text: str | None) -> int | None:
    """The number a margin box starts with, ignoring anything stuck to it.

    Merging boxes that share a row sometimes picks up a short word sitting close
    to the margin, so the text arrives as "19is" or "2-" rather than "19" or "2".
    The line number is still perfectly legible at the front.

    Only the leading run of digits counts, and it must match the whole number:
    "21" does not confirm line 2. Without that, a two-digit number would appear
    to agree with the one-digit line above it.

    Returns:
        The leading number, or None if the text does not start with a digit.
    """
    if not text:
        return None
    digits = ""
    for character in text.strip():
        if not character.isdigit():
            break
        digits += character
    return int(digits) if digits else None


def _looks_like_a_number(text: str) -> bool:
    """Could this short string be a margin line number?

    Deliberately generous. Old scans misread digits as letters - "z" for 2, "IS"
    for 15, "i f" for 11 - and a strict test would reject the very lines that
    most need finding. Position decides what a box *is*; this only decides
    whether a box is the right *shape* to be a line number.
    """
    return len(text.strip()) <= 2


def _ranks_by_spacing(gutter: Sequence[TextBox]) -> list[int]:
    """Work out which line number each margin box is, from how far apart they sit.

    Simply numbering the boxes 1, 2, 3... breaks the moment the OCR misses one.
    If the number beside line 10 is too faint to detect at all, every line below
    it shifts up by one and the rest of the page is silently misnumbered - which
    is worse than a wrong digit, because nothing about the result looks wrong.

    So the spacing does the work instead. Lines on these pages are evenly spaced,
    so the usual distance between one number and the next is one line. A gap of
    about twice that means a number was missed, and the count skips accordingly.

    The typical spacing is taken as the median of the gaps rather than the mean,
    so one or two missed numbers cannot drag the estimate off.

    Args:
        gutter: Margin boxes, already sorted top to bottom.

    Returns:
        A line number for each box, starting at 1.
    """
    if len(gutter) < 2:
        return [1] * len(gutter)

    centers = [box.y_center for box in gutter]
    gaps = sorted(centers[i + 1] - centers[i] for i in range(len(centers) - 1))
    pitch = gaps[len(gaps) // 2]

    # Degenerate pages - every box at the same height - fall back to counting,
    # which is no worse than anything else when the geometry makes no sense.
    if pitch <= 0:
        return list(range(1, len(gutter) + 1))

    ranks = [1]
    for index in range(1, len(centers)):
        step = max(1, round((centers[index] - centers[index - 1]) / pitch))
        ranks.append(ranks[-1] + step)

    return _shift_to_match_digits(ranks, gutter)


def _shift_to_match_digits(ranks: list[int], gutter: Sequence[TextBox]) -> list[int]:
    """Decide where the sequence starts, using the digits that were readable.

    Spacing gets the gaps right but cannot see a gap at the very top. If the
    number beside line 1 was never detected, counting from the first box found
    calls line 2 "line 1" and the whole page is off by one. That happened on
    page 3 of the 1969 example.

    The digits settle it, but only collectively. Any single digit may be a
    misread - the same page reads 2 as "z" and 6 as "0" - so no one of them is
    trusted. Instead every readable digit votes on how far the sequence is
    shifted, and a shift is applied only when most of them agree. One stray "18"
    where an 8 should be cannot move anything.

    Spacing still decides the gaps; this only decides the starting point.

    Args:
        ranks: Line numbers from spacing alone, starting at 1.
        gutter: The margin boxes those ranks belong to.

    Returns:
        The ranks, shifted if the digits clearly say so.
    """
    votes: dict[int, int] = {}
    readable = 0

    for rank, box in zip(ranks, gutter):
        printed = _leading_number(box.text)
        if printed is None:
            continue
        readable += 1
        offset = printed - rank
        votes[offset] = votes.get(offset, 0) + 1

    if not votes:
        return ranks

    offset, agreeing = max(votes.items(), key=lambda item: item[1])

    # Needs a real majority of the readable digits, not merely the most common
    # answer among a scattering of misreads.
    if offset == 0 or agreeing < max(3, readable * 0.6):
        return ranks

    # A shift that would put line numbers at zero or below is not a shift, it is
    # a misreading of a page that has something else in its margin.
    if min(ranks) + offset < 1:
        return ranks

    return [rank + offset for rank in ranks]


def find_gutter(
    boxes: Sequence[TextBox],
    page_width: float,
    gutter_fraction: float = 0.2,
) -> tuple[list[TextBox], list[TextBox]]:
    """Split a page's boxes into margin numbers and everything else.

    The margin is found from the page's own layout rather than from a fixed
    fraction of its width. A fraction has to be tuned per document and gets it
    wrong when it is close: the 1969 scans put their line numbers between 10.2%
    and 12.6% across the page, so a 12% cutoff sliced through the middle of the
    column and took some numbers while leaving others behind.

    What actually distinguishes a line number is that it sits entirely to the
    left of the prose. So the prose defines the boundary: find where the real
    words start, and anything short and left of that is a margin number. That
    calibrates itself to each page.

    Args:
        boxes: Everything the OCR found on the page.
        page_width: Width of the page in the same units as the boxes.
        gutter_fraction: A backstop, used only when a page has no prose to
            measure against. Also caps how far right the margin may reach, so a
            page of nothing but short words cannot be read as one enormous margin.

    Returns:
        The margin boxes, sorted top to bottom, and the rest.
    """
    cap = page_width * gutter_fraction
    short = [box for box in boxes if _looks_like_a_number(box.text)]
    if not short:
        return [], list(boxes)

    # The margin numbers are the leftmost things on the page and sit in a narrow
    # column, so the left edge of that column plus a small allowance covers them
    # all and reaches nothing else. The allowance has to absorb the wobble of a
    # scan and the difference between a one-digit and a two-digit number, and
    # nothing more.
    left_edge = min(box.x0 for box in short)
    band = min(page_width * _GUTTER_BAND, cap)

    gutter = [box for box in short if box.x0 <= left_edge + band]

    # A handful of scattered short words is not a column of line numbers. Without
    # this, a cover page with no numbered lines at all would report a margin made
    # of whatever short words happened to sit furthest left.
    if len(gutter) < _MINIMUM_COLUMN:
        return [], list(boxes)
    in_gutter = {id(box) for box in gutter}
    body = [box for box in boxes if id(box) not in in_gutter]

    gutter.sort(key=lambda box: box.y_center)
    return _merge_split_numbers(gutter), body


def _merge_split_numbers(gutter: list[TextBox]) -> list[TextBox]:
    """Join margin boxes that sit at the same height into one line number.

    A faint two-digit number often comes back as two separate boxes, because the
    recognition split it down the middle. Line 11 on page 6 of the 1969 example
    arrives as `'i'` and `'f'` side by side - the misread the project's own notes
    record as "i f for 11".

    Left alone, those two boxes look like two lines, and every line below them is
    numbered one too high. So anything sharing a row is merged into a single
    entry spanning both.

    The threshold is a fraction of the distance between lines rather than a fixed
    number of pixels, so it works whatever resolution the page was rendered at.

    Args:
        gutter: Margin boxes, sorted top to bottom.

    Returns:
        One box per row, with the pieces' text joined left to right.
    """
    if len(gutter) < 2:
        return gutter

    centers = [box.y_center for box in gutter]
    gaps = sorted(centers[i + 1] - centers[i] for i in range(len(centers) - 1))
    pitch = gaps[len(gaps) // 2]
    if pitch <= 0:
        return gutter

    limit = pitch * _SAME_ROW
    merged: list[TextBox] = []
    row: list[TextBox] = [gutter[0]]

    for box in gutter[1:]:
        if box.y_center - row[-1].y_center <= limit:
            row.append(box)
        else:
            merged.append(_join(row))
            row = [box]
    merged.append(_join(row))

    return merged


def _join(row: list[TextBox]) -> TextBox:
    """Combine boxes sharing a row into one, keeping the full extent."""
    if len(row) == 1:
        return row[0]
    ordered = sorted(row, key=lambda box: box.x0)
    return TextBox(
        text="".join(box.text.strip() for box in ordered),
        x0=min(box.x0 for box in ordered),
        y0=min(box.y0 for box in ordered),
        x1=max(box.x1 for box in ordered),
        y1=max(box.y1 for box in ordered),
    )


def read_geometry(
    boxes: Sequence[TextBox],
    page: int,
    page_width: float,
    expected_lines: int = 25,
    gutter_fraction: float = 0.12,
) -> PageGeometry:
    """Work out where the numbered lines are on one scanned page.

    Args:
        boxes: Everything the OCR found.
        page: Which page this is.
        page_width: Page width, for locating the margin.
        expected_lines: How many numbered lines a full page carries.
        gutter_fraction: How far across the page the margin reaches.

    Returns:
        The page's structure, with any concerns recorded as warnings rather than
        raised. A bad page must not stop a thousand-page run; it must be findable
        afterwards.
    """
    geometry = PageGeometry(page=page)
    gutter, body = find_gutter(boxes, page_width, gutter_fraction)

    if not gutter:
        geometry.warnings.append(
            "No line numbers found in the left margin. This page may be a cover "
            "sheet, or the scan may be skewed enough to move the margin."
        )
        return geometry

    # The number comes from where the box sits, not from what the OCR read.
    for rank, box in zip(_ranks_by_spacing(gutter), gutter):
        printed = box.text.strip() or None
        geometry.lines.append(
            GutterLine(
                rank=rank,
                printed=printed,
                y_center=box.y_center,
                agrees=_leading_number(printed) == rank,
            )
        )

    geometry.body_top = min(box.y0 for box in gutter)
    geometry.body_bottom = max(box.y1 for box in gutter)

    # The words start just right of the widest margin number. Falling back to the
    # margin's right edge keeps a page with no body text from producing nonsense.
    body_in_band = [
        box for box in body
        if geometry.body_top - 5 <= box.y_center <= geometry.body_bottom + 5
    ]
    if body_in_band:
        geometry.body_left = min(box.x0 for box in body_in_band)
    else:
        geometry.body_left = max(box.x1 for box in gutter)

    if geometry.missing_numbers:
        geometry.warnings.append(
            f"No margin number was detected for line(s) "
            f"{', '.join(str(n) for n in geometry.missing_numbers)}, but the "
            f"spacing shows where they were, so the numbering is unaffected."
        )

    if geometry.highest_line != expected_lines:
        geometry.warnings.append(
            f"Numbered lines run to {geometry.highest_line}, expected "
            f"{expected_lines}. The last page of a section is often short, so "
            f"this is only a problem in the middle of a transcript."
        )

    if geometry.disagreements:
        geometry.warnings.append(
            f"{geometry.disagreements} of {geometry.line_count} line numbers were "
            f"read as something other than their position. The position is used; "
            f"this is recorded as a measure of how well the OCR read this page."
        )

    return geometry


def words_for_line(
    body: Sequence[TextBox], line: GutterLine, tolerance: float
) -> list[TextBox]:
    """The words that sit beside one margin number.

    Args:
        body: Boxes outside the margin.
        line: The numbered line to collect words for.
        tolerance: How far a word's middle may sit from the number's middle. Half
            a line's height is a sensible value - large enough for slightly
            uneven scanning, small enough not to reach the next line.

    Returns:
        The words, left to right.
    """
    matched = [
        box for box in body
        if abs(box.y_center - line.y_center) <= tolerance
    ]
    matched.sort(key=lambda box: box.x0)
    return matched

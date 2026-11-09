"""What an OCR engine has to look like, and what reading a page produces.

Two kinds of engine, doing different jobs:

**A layout engine** returns every piece of text with the box it sat in. The boxes
are what matter - they are how the margin line numbers are found by position
rather than by being read. The one used here reads them out of the PDF's own text
layer; `embedded_engine.py` says why, rather than using a model for the job.

**A text engine** reads an image and returns words. No boxes, better prose. It is
only ever shown the body of the page, cropped so the margin numbers are not in
the picture, which is what stops it inventing them.

Splitting the two is the whole design. The deterministic engine is trusted for
structure, the language model for text, and neither is asked to do the other's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .geometry import PageGeometry, TextBox


@dataclass
class PageReading:
    """One scanned page, read.

    Attributes:
        page: Page number, counting from 1.
        lines: The text of each numbered line, in order, as
            `(line number, text)`. Line numbers come from position in the
            margin, never from reading the digit.
        geometry: What was worked out about the layout.
        engine: Which engine produced the text.
        boxes: Everything the layout engine found. Kept so a page can be
            re-examined without running the OCR again, which is slow.
    """

    page: int
    lines: list[tuple[int, str]] = field(default_factory=list)
    geometry: PageGeometry | None = None
    engine: str = ""
    boxes: list[TextBox] = field(default_factory=list)
    model_text: str = ""

    @property
    def text(self) -> str:
        """The page's words, one numbered line per output line."""
        return "\n".join(text for _number, text in self.lines)

    @property
    def best_text(self) -> str:
        """The most accurate reading of this page.

        The vision model's, where there is one: it handles faded ink far better.
        Otherwise the words assembled from the boxes.
        """
        return self.model_text or self.text

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary, for writing to JSON."""
        return {
            "page": self.page,
            "engine": self.engine,
            "line_count": len(self.lines),
            # Two readings of the same page, kept apart on purpose.
            #
            # `lines` is line-accurate: each entry really is the text beside that
            # margin number, because the words were matched to it by position.
            # Its wording is whatever the boxes said, which on a scan is poor.
            #
            # `model_text` is word-accurate and has no line structure at all -
            # the model returns paragraphs, not twenty-five numbered lines.
            #
            # Merging them would mean guessing which paragraph belongs to which
            # line number, and a wrong guess there is invisible. So both are
            # kept and the choice is left to whoever reads the file.
            "lines": [{"number": n, "text": t} for n, t in self.lines],
            "model_text": self.model_text,
            "geometry": self.geometry.to_dict() if self.geometry else None,
            "boxes": [
                {
                    "text": box.text,
                    "x0": round(box.x0, 1),
                    "y0": round(box.y0, 1),
                    "x1": round(box.x1, 1),
                    "y1": round(box.y1, 1),
                    "confidence": box.confidence,
                }
                for box in self.boxes
            ],
        }


@dataclass(frozen=True)
class PageSource:
    """One page, offered in every form an engine might want.

    A recognition model wants the picture. An engine reading a PDF's existing
    text layer wants the file and the page number. Handing over both means
    neither has to reach around the other, and an engine simply ignores what it
    does not use.

    Attributes:
        pdf_path: The PDF.
        page_number: Which page, counting from 1.
        image: The rendered page, already enlarged and contrast-stretched.
        scale: Image pixels per PDF point. An engine returning coordinates in
            PDF points multiplies by this so its boxes line up with the image,
            which is what the cropping step needs.
    """

    pdf_path: Path
    page_number: int
    image: Any
    scale: float = 1.0


@runtime_checkable
class LayoutEngine(Protocol):
    """Finds text and, crucially, where it sits."""

    name: str

    def boxes(self, source: PageSource) -> list[TextBox]:
        """Return every piece of text on the page with the box it sat in.

        Coordinates must be in image pixels, so that they can be used to crop the
        image.

        Args:
            source: The page, as a file and as a picture.

        Returns:
            The boxes, in whatever order the engine produced them.
        """
        ...


@runtime_checkable
class TextEngine(Protocol):
    """Reads an image and returns words, with no claim about where they were."""

    name: str

    def read(self, image: Any) -> str:
        """Read an image of the body of a page.

        The image passed here has already had the margin cropped off, so the
        engine never sees the line numbers and cannot invent them.

        Args:
            image: A PIL image, cropped to the body text.

        Returns:
            The text, with line breaks where the page had them.
        """
        ...


#: Either kind, where a function accepts both.
OcrEngine = LayoutEngine | TextEngine

"""Reading the layout from a scanned PDF's own text layer.

The Court's scanned transcripts are page images with OCR text bolted on top,
produced when the archive was digitised. That text is poor - "zhe" for "the",
"hi.i." for "had", and margin numbers read as "z", "0" and "IS".

But its **boxes are good**. Checking page 6 of the 1969 example: every margin
number is present and correctly placed at the left edge, and the text of three of
them is wrong. Position right, characters wrong.

That is exactly the split this pipeline is built around, so the old text layer
turns out to be a perfectly good layout engine even though it is a bad reader. It
supplies the geometry; a language model supplies the words.

The practical argument for using it is stronger still. It needs nothing installed.
The obvious alternative, Surya, would have pulled in `torch 2.14` from ordinary
PyPI and silently replaced this machine's CUDA build of PyTorch with a
processor-only one - taking the GPU away from the speech models with no error
message anywhere.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from .base import PageSource
from .geometry import TextBox


class EmbeddedTextEngine:
    """Layout from the text layer already inside the PDF.

    Works on any PDF that carries text, which includes both the scanned
    transcripts (where the text is poor but positioned) and the born-digital ones
    (where it is exact). That second case is what makes the born-digital pages
    usable as a gold standard for measuring OCR quality.
    """

    #: Used in filenames and in the results tables.
    name = "embedded"

    def boxes(self, source: PageSource) -> list[TextBox]:
        """Every word on the page, with its box in image pixels.

        Args:
            source: The page. Only `pdf_path`, `page_number` and `scale` are used.

        Returns:
            The words, in the PDF's own reading order.

        Raises:
            FileNotFoundError: If the PDF is missing.
            IndexError: If the page does not exist.
        """
        pdf_path = Path(source.pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"No PDF at {pdf_path}")

        with pymupdf.open(pdf_path) as document:
            if not 1 <= source.page_number <= document.page_count:
                raise IndexError(
                    f"{pdf_path.name} has {document.page_count} pages; "
                    f"asked for page {source.page_number}."
                )
            page = document[source.page_number - 1]
            # "words" gives one entry per whitespace-separated word as
            # (x0, y0, x1, y1, text, block, line, word). Word-level rather than
            # line-level matters: a line-level box would swallow the margin
            # number into the sentence beside it, and the whole point is to keep
            # them apart.
            raw = page.get_text("words")

        scale = source.scale or 1.0
        return [
            TextBox(
                text=word[4],
                x0=word[0] * scale,
                y0=word[1] * scale,
                x1=word[2] * scale,
                y1=word[3] * scale,
            )
            for word in raw
        ]


def has_text_layer(pdf_path: Path | str, sample_pages: int = 3) -> bool:
    """Does this PDF carry text at all?

    A PDF with page images and no text layer needs a recognition model for the
    layout as well as the words, and this engine cannot help with it.

    Args:
        pdf_path: The PDF.
        sample_pages: How many pages to look at. The first page is often a cover
            sheet with little text, so a couple more are checked.

    Returns:
        Whether any of the sampled pages held text.
    """
    with pymupdf.open(Path(pdf_path)) as document:
        for index in range(min(sample_pages, document.page_count)):
            if document[index].get_text("text").strip():
                return True
    return False

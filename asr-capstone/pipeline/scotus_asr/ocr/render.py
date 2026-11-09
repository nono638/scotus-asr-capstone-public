"""Turning a scanned PDF page into an image worth reading.

The 1968-1999 transcripts are one JPEG-2000 image per page, about 1190 by 1667
pixels, which works out at roughly 150 dots per inch on a letter-size page. The
ink is faint - typewriter ribbon, photocopied, then scanned - but the layout is
about as easy as OCR gets: one column, monospaced, no handwriting.

Enlarging matters more than anything else done here. Most recognition models are
trained on images around 300 dots per inch, so a 150 dpi scan is outside what they
handle best. Making the image bigger before reading it usually helps more than
switching to a larger model, and it costs nothing but time.

The contrast step is deliberately mild. Aggressive thresholding turns faint strokes
into gaps, and a missing stroke is unrecoverable - the model has nothing left to
work from. Stretching the existing range is safe; throwing away grey is not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageOps


def render_page(
    pdf_path: Path | str,
    page_number: int,
    dpi: int = 300,
    upscale: float = 1.0,
    enhance: bool = True,
) -> Image.Image:
    """Render one page of a PDF as an image.

    Args:
        pdf_path: The PDF.
        page_number: Which page, counting from 1.
        dpi: Dots per inch to render at. Rendering above the scan's own
            resolution still helps, because it lets the enlarging happen with
            better interpolation than a plain pixel copy.
        upscale: Enlarge further after rendering. 1.0 leaves it alone.
        enhance: Convert to grey and stretch the contrast.

    Returns:
        The page as a PIL image.

    Raises:
        FileNotFoundError: If the PDF is missing.
        IndexError: If the page does not exist.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"No PDF at {pdf_path}")

    with pymupdf.open(pdf_path) as document:
        if not 1 <= page_number <= document.page_count:
            raise IndexError(
                f"{pdf_path.name} has {document.page_count} pages; "
                f"asked for page {page_number}."
            )
        page = document[page_number - 1]
        pixmap = page.get_pixmap(dpi=dpi)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    if enhance:
        # Grey first: colour carries nothing on a black-and-white scan, and
        # stretching contrast per channel can tint faint strokes.
        image = ImageOps.grayscale(image)
        # Ignore the most extreme 1% at each end, so a single speck of dirt or a
        # bright scanner edge does not set the whole page's range.
        image = ImageOps.autocontrast(image, cutoff=1)

    if upscale and upscale != 1.0:
        size = (int(image.width * upscale), int(image.height * upscale))
        # Lanczos rather than nearest or bilinear: it keeps the edges of thin
        # typewriter strokes rather than smearing them.
        image = image.resize(size, Image.LANCZOS)

    return image


def crop_body(image: Image.Image, body_left: float, body_top: float,
              body_bottom: float, padding: float = 8.0) -> Image.Image:
    """Cut the margin numbers off a page image.

    This is the step that makes it safe to hand the page to a language model. The
    numbers are not removed from the result afterwards - they are absent from the
    input, so there is nothing for the model to get wrong and nothing for it to
    helpfully supply.

    Args:
        image: The full page.
        body_left: Where the words start, from the page geometry.
        body_top: Top of the first numbered line.
        body_bottom: Bottom of the last one.
        padding: Pixels of breathing room, so characters are not clipped.

    Returns:
        The cropped image.
    """
    left = max(0, int(body_left - padding))
    top = max(0, int(body_top - padding))
    bottom = min(image.height, int(body_bottom + padding))
    return image.crop((left, top, image.width, bottom))


def page_count(pdf_path: Path | str) -> int:
    """How many pages a PDF has."""
    with pymupdf.open(Path(pdf_path)) as document:
        return document.page_count


def page_width_points(pdf_path: Path | str, page_number: int) -> float:
    """How wide a page is, in PDF points, without rendering it.

    Used when nothing needs the picture: the layout still has to know how wide
    the page is to locate the left margin, and reading that from the file is
    instant where rendering is not.
    """
    with pymupdf.open(Path(pdf_path)) as document:
        return float(document[page_number - 1].rect.width)


def is_scanned(pdf_path: Path | str) -> bool:
    """Does this PDF need OCR at all?

    A born-digital transcript has real text and no page images; a scanned one is
    a picture per page. Checking rather than assuming is what established that
    all six sample transcripts are born-digital and only the 1969 example is not.
    """
    with pymupdf.open(Path(pdf_path)) as document:
        for page in document:
            if page.get_images():
                return True
    return False

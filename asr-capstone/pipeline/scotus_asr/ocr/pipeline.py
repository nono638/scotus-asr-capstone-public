"""Reading a scanned transcript, one page at a time.

The order of operations is the argument:

1. Render the page and enlarge it.
2. Find every word and its box with a layout engine.
3. Work out the margin numbers **by position**, never by reading them.
4. Crop the image so the margin is not in it.
5. Read the cropped body with a language model, which is good at faded prose and
   is now structurally unable to invent a line number.

Each page is written to disk as it is read. A hundred-page transcript takes a
while, and a crash at page 80 should cost one page, not eighty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from ..config import OcrSettings
from .base import PageReading, PageSource
from .geometry import TextBox, read_geometry, words_for_line
from .render import crop_body, page_count, page_width_points, render_page

#: Called after each page with (page number, pages done, pages total).
PageCallback = Callable[[int, int, int], None]


def read_page(
    pdf_path: Path,
    page_number: int,
    layout: Any,
    settings: OcrSettings,
    text_engine: Any | None = None,
) -> PageReading:
    """Read one scanned page.

    Args:
        pdf_path: The scanned transcript.
        page_number: Which page, counting from 1.
        layout: An engine returning text with boxes.
        settings: Rendering and margin settings.
        text_engine: An optional second engine that re-reads the cropped body.
            When given, its text replaces the layout engine's, which is usually
            better prose. The line numbers are unaffected either way, because
            they never came from text in the first place.

    Returns:
        The page, its numbered lines, and what was worked out about its layout.
    """
    # PDF coordinates are in points, 72 to the inch. An engine reporting points
    # multiplies by this so its boxes line up with the rendered pixels, which is
    # what the cropping step works in.
    scale = (settings.render_dpi / 72.0) * (settings.upscale or 1.0)

    # Rendering is by far the slowest thing here, and only a model that reads a
    # picture actually needs one. An engine working from the PDF's own text layer
    # does not, so the image is produced only when something will look at it.
    # Across a 104-page transcript this is the difference between minutes and
    # seconds.
    image = None
    if text_engine is not None:
        image = render_page(
            pdf_path,
            page_number,
            dpi=settings.render_dpi,
            upscale=settings.upscale,
        )
        page_width = float(image.width)
    else:
        page_width = page_width_points(pdf_path, page_number) * scale

    source = PageSource(
        pdf_path=Path(pdf_path),
        page_number=page_number,
        image=image,
        scale=scale,
    )

    boxes = layout.boxes(source)
    geometry = read_geometry(
        boxes,
        page=page_number,
        page_width=page_width,
        expected_lines=settings.expected_lines_per_page,
        gutter_fraction=settings.gutter_width_fraction,
    )

    reading = PageReading(
        page=page_number,
        geometry=geometry,
        engine=getattr(layout, "name", "unknown"),
        boxes=list(boxes),
    )

    if not geometry.lines:
        # A cover sheet or a divider. Nothing to number, nothing to read.
        return reading

    # Always assembled from the boxes, because this is the reading that is
    # line-accurate: each entry is genuinely the text beside that margin number.
    reading.lines = _lines_from_boxes(boxes, geometry)

    if text_engine is not None and image is not None and geometry.body_box:
        cropped = crop_body(
            image, geometry.body_left, geometry.body_top, geometry.body_bottom
        )
        reading.engine = f"{reading.engine}+{getattr(text_engine, 'name', 'text')}"
        # Kept separately rather than folded into the lines above. The model
        # returns paragraphs, not twenty-five numbered lines, so pairing its
        # output with line numbers would mean guessing - and a wrong guess there
        # looks exactly like a right one.
        reading.model_text = text_engine.read(cropped)

    return reading


def _lines_from_boxes(boxes: Sequence[TextBox], geometry) -> list[tuple[int, str]]:
    """Assemble each numbered line from the boxes sitting beside its number."""
    body = [
        box for box in boxes
        if box.x0 > geometry.body_left - 1
    ]
    # Half the distance between lines: enough for an uneven scan, not enough to
    # reach the line above or below.
    spacing = _typical_spacing(geometry)
    lines: list[tuple[int, str]] = []

    for line in geometry.lines:
        words = words_for_line(body, line, tolerance=spacing / 2)
        lines.append((line.rank, " ".join(box.text for box in words).strip()))

    return lines


def _typical_spacing(geometry) -> float:
    """How far apart the numbered lines sit, in pixels."""
    if len(geometry.lines) < 2:
        return 40.0
    centers = [line.y_center for line in geometry.lines]
    return (centers[-1] - centers[0]) / (len(centers) - 1)


def read_document(
    pdf_path: Path,
    layout: Any,
    settings: OcrSettings,
    text_engine: Any | None = None,
    pages: Iterable[int] | None = None,
    on_page: PageCallback | None = None,
    save_page: Callable[[PageReading], None] | None = None,
) -> list[PageReading]:
    """Read a whole scanned transcript.

    Args:
        pdf_path: The transcript.
        layout: The engine that returns boxes.
        settings: Rendering and margin settings.
        text_engine: Optional second engine for the body text.
        pages: Which pages, counting from 1. All of them by default.
        on_page: Called after each page, for progress.
        save_page: Called with each page as it is finished. This is what makes a
            long run survive a crash - supply it and every page is on disk the
            moment it is read.

    Returns:
        The pages read, in order.
    """
    wanted = list(pages) if pages is not None else range(1, page_count(pdf_path) + 1)
    total = len(list(wanted)) if not isinstance(wanted, range) else len(wanted)

    readings: list[PageReading] = []
    for done, number in enumerate(wanted, start=1):
        reading = read_page(pdf_path, number, layout, settings, text_engine)
        readings.append(reading)

        if save_page is not None:
            save_page(reading)
        if on_page is not None:
            on_page(number, done, total)

    return readings

"""Reading scanned transcript pages.

Only the pre-2000 transcripts need this. Everything from the 2000 term onward is
a born-digital PDF whose text can be read exactly, and running OCR over those
would replace a perfect reference with an approximate one.

They are still worth reading, for the opposite reason: because the true text is
known, a born-digital page is a free gold standard. Measuring the OCR against it
says how much to trust the same OCR on the 1969 scans, where nothing exists to
check against.
"""

from .geometry import GutterLine, PageGeometry, TextBox, read_geometry
from .base import OcrEngine, PageReading

__all__ = [
    "GutterLine",
    "PageGeometry",
    "TextBox",
    "read_geometry",
    "OcrEngine",
    "PageReading",
]

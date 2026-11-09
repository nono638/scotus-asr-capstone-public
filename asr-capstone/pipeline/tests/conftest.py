"""Shared fixtures.

The default test run must be fast and must not need a GPU, a network connection
or a model download. Anything that does is marked, so it can be excluded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scotus_asr.transcripts.model import Line

#: The capstone folder, found by walking up from this file.
CAPSTONE_DIR = Path(__file__).resolve().parents[2]
SAMPLE_DIR = CAPSTONE_DIR / "sample"


@pytest.fixture
def sample_dir() -> Path:
    """Where the six verified cases live."""
    return SAMPLE_DIR


@pytest.fixture
def manifest_path(sample_dir: Path) -> Path:
    """The manifest, skipping the test if the sample is not present."""
    path = sample_dir / "manifest.json"
    if not path.exists():
        pytest.skip("Sample data is not present.")
    return path


def make_lines(rows: list[str], page: int = 1, start: int = 1) -> list[Line]:
    """Build numbered lines from plain strings, for tests that need no PDF.

    Line numbers are assigned in order and wrap at 25, which is how a real
    transcript page is laid out.
    """
    lines = []
    number = start
    for row in rows:
        lines.append(Line(page=page, number=number, text=row, x0=127.5))
        number = number + 1 if number < 25 else 1
    return lines

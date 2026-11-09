"""Scoring a corpus that has no PDFs must not need the PDF reader.

PyMuPDF is only for the Supreme Court's transcripts, and its licence (AGPL) is a
reason to keep it out of anything that might one day run on a public site. Each
check runs in a fresh Python, because this test session may already have loaded
it for the PDF tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "module",
    ["scotus_asr.scoring.metrics", "scotus_asr.stages", "scotus_asr.cli", "scotus_asr.corpora.edacc"],
)
def test_no_pdf_reader_without_pdfs(module):
    code = f"import sys, {module}; print('pymupdf' in sys.modules)"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=PIPELINE, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"

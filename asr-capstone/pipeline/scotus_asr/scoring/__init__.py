"""Comparing a machine transcription against the official record."""

from .normalize import NORMALIZERS, normalize_tokens
from .align import Alignment, align_words
from .omissions import OmittedSpan, find_omissions
from .metrics import ScoreRow, score_case

__all__ = [
    "NORMALIZERS",
    "normalize_tokens",
    "Alignment",
    "align_words",
    "OmittedSpan",
    "find_omissions",
    "ScoreRow",
    "score_case",
]

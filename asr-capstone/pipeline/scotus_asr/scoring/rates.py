"""Words per minute: a quick check that a transcript belongs to its recording.

Kept apart from the PDF parser so scoring a corpus that has no PDFs never needs
PyMuPDF installed.
"""

from __future__ import annotations


def check_speaking_rate(
    word_count: int, audio_minutes: float, low: float = 165.0, high: float = 197.0
) -> tuple[float, bool]:
    """Sanity-check a transcript against its recording.

    Dividing spoken words by audio minutes gives a speaking rate. Appellate
    argument runs between roughly 165 and 197 words per minute, and a figure
    outside that means one of two things went wrong: the audio and the transcript
    are different proceedings, or the keyword index is being counted as speech.
    Other corpora set their own band in their config.

    Args:
        word_count: Spoken words in the transcript.
        audio_minutes: Length of the recording.
        low: Bottom of the plausible range.
        high: Top of it.

    Returns:
        The rate, and whether it looks believable. A recording of zero length
        returns `(0.0, False)` rather than dividing by zero.
    """
    if audio_minutes <= 0:
        return 0.0, False
    rate = word_count / audio_minutes
    return rate, low <= rate <= high

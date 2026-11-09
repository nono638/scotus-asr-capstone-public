"""Measure speech recognition accuracy against official Supreme Court transcripts.

The pipeline runs in stages, and each stage writes its results to disk before the
next one starts:

    fetch        get the audio and transcript PDFs
    transcripts  pull the reference text out of the PDFs and split it into turns
    ocr          read the page images, for the scanned transcripts
    asr          run a speech recognition model over the audio
    score        align the two and work out where the model went wrong

Stages are separate because they fail for different reasons and take wildly
different amounts of time. Downloading fails because a server is down and is worth
retrying; transcription takes half an hour on the GPU and must never be repeated
unnecessarily.
"""

__version__ = "0.1.0"

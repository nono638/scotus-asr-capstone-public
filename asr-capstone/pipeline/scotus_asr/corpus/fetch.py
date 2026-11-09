"""Downloading the files that are not kept in version control.

The recordings are about 134 MB for six cases and will be far larger for the full
corpus, so they are fetched rather than stored. Every source address is recorded
in the manifest, which is kept.

Two details carried over from the existing `fetch_sample_media.py`, both of which
were learned the hard way and neither of which is optional.

The Court's website serves a short HTML error page to anything that does not look
like a browser. Without a browser-like identifier that page lands on disk named
`.mp3`, and fails to open much later in a completely unrelated part of the
pipeline.

And the file is written under a temporary name until it is complete. An
interrupted download must not leave a truncated MP3 that a resumed run mistakes
for a finished one.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable

from ..store import TEMP_SUFFIX
from .web import PoliteSession

#: The Court's site refuses anything that does not look like a browser.
HEADERS = {"User-Agent": "Mozilla/5.0 (SCOTUS ASR capstone)"}

#: Read this much at a time. Large enough to be quick, small enough to report
#: progress on a 70 MB file.
_CHUNK = 1 << 16

#: Called with (bytes so far, total bytes or 0 if the server did not say).
ProgressCallback = Callable[[int, int], None]


def download(
    url: str,
    destination: Path,
    on_progress: ProgressCallback | None = None,
    timeout: float = 120.0,
    session: "PoliteSession | None" = None,
) -> int:
    """Fetch one file, leaving it in place only once it is complete.

    Args:
        url: What to fetch.
        destination: Where it goes. Parent directories are created.
        on_progress: Called as the download proceeds.
        timeout: Seconds to wait for the server.
        session: Fetch through this instead, so a bulk download waits between
            files and backs off when the server asks. Downloading six sample
            files without one is fine; downloading a thousand is not.

    Returns:
        How many bytes were written.

    Raises:
        urllib.error.URLError: If the server could not be reached.
        OSError: If the file could not be written.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + TEMP_SUFFIX)

    opener = (
        (lambda: session.open(url))
        if session is not None
        else (lambda: urllib.request.urlopen(
            urllib.request.Request(url, headers=HEADERS), timeout=timeout
        ))
    )
    written = 0

    try:
        with opener() as response:
            total = int(response.headers.get("Content-Length") or 0)
            with open(partial, "wb") as stream:
                while True:
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    stream.write(chunk)
                    written += len(chunk)
                    if on_progress is not None:
                        on_progress(written, total)
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    return written


def missing_files(case, want_audio: bool = True, want_transcript: bool = True
                  ) -> list[tuple[str, Path]]:
    """Which of a case's files are not on disk yet.

    Args:
        case: The case to check.
        want_audio: Include the recording.
        want_transcript: Include the transcript PDF.

    Returns:
        `(url, destination)` for each missing file. A case with no recording -
        anything before the 2010 term - contributes no audio entry rather than an
        entry that cannot be fetched.
    """
    wanted: list[tuple[str, Path]] = []

    if want_audio and case.audio_url and not case.audio_path.exists():
        wanted.append((case.audio_url, case.audio_path))

    if want_transcript and case.transcript_url and not case.transcript_pdf.exists():
        wanted.append((case.transcript_url, case.transcript_pdf))

    return wanted

"""Getting a corpus onto disk: large files that resume, and archives.

The Supreme Court downloader (`corpus/fetch.py`) fetches thousands of small
files, each in one go. Speech corpora mostly arrive the other way round: one
archive of several gigabytes. A dropped connection at 90% should not mean
starting again, so this one resumes, by asking the server for the rest of the
file from where the partial copy stops (an HTTP Range request).

Both steps leave proof that they finished - the file under its real name, a
marker file beside the unpacked folder - so a second run skips them.
"""

from __future__ import annotations

import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

#: Called with (bytes so far, total bytes or 0 if unknown).
ByteProgress = Callable[[int, int], None]

_CHUNK = 1 << 20
_HEADERS = {"User-Agent": "Mozilla/5.0 (ASR capstone; corpus download)"}


def fetch(
    url: str,
    destination: Path,
    expected_bytes: int | None = None,
    on_progress: ByteProgress | None = None,
    timeout: float = 120.0,
) -> Path:
    """Download one file, carrying on from a partial copy if there is one.

    Args:
        url: What to fetch.
        destination: Where the finished file goes.
        expected_bytes: The size the source says the file is. When given, a file
            already at the destination with this size is taken as done, and a
            finished download of any other size is an error rather than a
            quietly truncated archive.
        on_progress: Called as bytes arrive.
        timeout: Seconds to wait for the server.

    Returns:
        The destination.

    Raises:
        OSError: If the finished file is not the expected size.
    """
    destination = Path(destination)
    if destination.exists() and (expected_bytes is None
                                 or destination.stat().st_size == expected_bytes):
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    # A copy left at the real name by something else (a manual download, an
    # older run) is taken as a partial one and continued.
    if destination.exists() and not partial.exists():
        destination.replace(partial)
    have = partial.stat().st_size if partial.exists() else 0

    headers = dict(_HEADERS)
    if have:
        headers["Range"] = f"bytes={have}-"
    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        # 206 means the server is sending the rest; 200 means it ignored the
        # Range header and is sending everything, so start the file again.
        if have and response.status != 206:
            have = 0
        length = int(response.headers.get("Content-Length") or 0)
        total = have + length if length else (expected_bytes or 0)
        with open(partial, "ab" if have else "wb") as stream:
            got = have
            while chunk := response.read(_CHUNK):
                stream.write(chunk)
                got += len(chunk)
                if on_progress is not None:
                    on_progress(got, total)

    size = partial.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise OSError(
            f"{destination.name} is {size} bytes, expected {expected_bytes}. "
            f"The partial copy is kept; run again to carry on."
        )
    partial.replace(destination)
    return destination


def unpack(archive: Path, into: Path) -> Path:
    """Unpack a .tar, .tar.gz or .zip into a folder, once.

    A marker file is written beside the folder only after everything is out, so
    an unpack stopped halfway is redone rather than trusted.

    Tar members are extracted with Python's "data" filter, which refuses paths
    that would land outside the folder and drops anything executable - the
    archive came from the internet.

    Returns:
        The folder.
    """
    archive, into = Path(archive), Path(into)
    marker = into.with_name(into.name + ".unpacked")
    if marker.exists():
        return into

    if into.exists():
        shutil.rmtree(into)
    into.mkdir(parents=True)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.namelist():
                if not (into / member).resolve().is_relative_to(into.resolve()):
                    raise OSError(f"{archive.name} holds a path outside the folder: {member}")
            bundle.extractall(into)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(into, filter="data")

    marker.write_text(f"unpacked from {archive.name}\n", encoding="utf-8")
    return into

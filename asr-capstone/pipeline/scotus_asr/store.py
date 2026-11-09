"""Where results go, and how they get there without being corrupted.

The rule this module enforces: **a file that exists is a file that is finished.**

Nothing is ever written directly to its final name. Content goes to a temporary
file, is flushed all the way to the disk, and only then is renamed into place.
Renaming is atomic, so a reader either sees the old file or the complete new one,
never a half-written one. If the machine dies mid-write, the leftover temporary
file is ignored and the work is simply redone.

That matters because a partly-written transcription looks exactly like a finished
one to a resumed run, and the run would skip it and score garbage.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Suffix for in-progress files. Anything wearing it is incomplete by definition.
TEMP_SUFFIX = ".tmp"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write bytes so that `path` is either absent, old, or complete.

    Args:
        path: Final destination. Parent directories are created if needed.
        data: The full contents.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create the temporary file in the destination directory, because renaming
    # across drives is a copy and is not atomic.
    handle, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=TEMP_SUFFIX
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            # Without this the bytes may still be in the operating system's cache
            # when the rename happens, and a power cut loses them.
            os.fsync(stream.fileno())
        # os.replace overwrites atomically, including on Windows.
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text atomically. See `atomic_write_bytes`."""
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path: Path, obj: Any, indent: int = 1) -> None:
    """Write an object as JSON atomically.

    `ensure_ascii` is off so transcript text keeps its real characters - curly
    quotes and dashes matter when the thing being measured is punctuation.
    """
    atomic_write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False))


def read_json(path: Path) -> Any:
    """Read a JSON file written by this module."""
    return json.loads(path.read_text(encoding="utf-8"))


def new_run_id(prefix: str = "run") -> str:
    """A run identifier that sorts chronologically, e.g. `run-20260916-143355`."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}"


class RunStore:
    """The folder holding one run's results, and the only thing that writes to it.

    Layout::

        runs/<run_id>/
            reference/<docket>.json
            asr/<docket>.<engine>.json
            ocr/<docket>/page_0001.json
            scores/<docket>.<engine>.json
            results/*.csv
            ledger.jsonl
            run.log
            config_used.yaml

    Every artifact path is worked out from the task that produces it, so asking
    "has this been done" is the same question as "does this file exist".
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # --- locating things ---------------------------------------------------

    def path(self, *parts: str) -> Path:
        """A path inside the run folder."""
        return self.root.joinpath(*parts)

    def reference_path(self, docket: str) -> Path:
        """Where the transcript pulled out of the PDF goes."""
        return self.path("reference", f"{docket}.json")

    def asr_path(self, docket: str, engine: str) -> Path:
        """Where one model's transcription of one case goes."""
        return self.path("asr", f"{docket}.{engine}.json")

    def ocr_page_path(self, docket: str, page: int) -> Path:
        """Where one scanned page's reading goes. Zero-padded so pages sort."""
        return self.path("ocr", docket, f"page_{page:04d}.json")

    def score_path(self, docket: str, engine: str) -> Path:
        """Where the alignment and metrics for one case and model go."""
        return self.path("scores", f"{docket}.{engine}.json")

    def results_path(self, name: str) -> Path:
        """Where a results table goes."""
        return self.path("results", name)

    # --- writing -----------------------------------------------------------

    def write_json(self, path: Path, obj: Any) -> None:
        """Write an artifact atomically."""
        atomic_write_json(path, obj)

    def has(self, path: Path) -> bool:
        """Is this artifact present and complete?

        A zero-length file counts as absent. That can happen if a disk filled up
        at exactly the wrong moment, and treating it as done would hide the
        failure behind an empty result.
        """
        return path.exists() and path.stat().st_size > 0

    def append_csv_row(
        self,
        path: Path,
        row: dict[str, Any],
        fieldnames: Sequence[str] | None = None,
        flush: bool = True,
    ) -> None:
        """Add one row to a CSV, writing the header if the file is new.

        Rows are appended as they are produced rather than collected and written
        at the end. A run killed at case 40 of 50 still leaves 39 usable rows.

        This is the one place that does not write atomically, and deliberately:
        appending a single line is effectively atomic on its own, and rewriting
        the whole table for every row would get slow. The per-case JSON files are
        the real record; the CSV is a convenience that can be rebuilt from them.

        Args:
            path: The table.
            row: Column name to value.
            fieldnames: Column order. Defaults to the order of `row`.
            flush: Push to disk immediately. Leave on for unattended runs.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = list(fieldnames) if fieldnames else list(row)
        is_new = not path.exists() or path.stat().st_size == 0

        with open(path, "a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            if is_new:
                writer.writeheader()
            writer.writerow(row)
            if flush:
                stream.flush()
                os.fsync(stream.fileno())

    def append_csv_rows(
        self,
        path: Path,
        rows: Iterable[dict[str, Any]],
        fieldnames: Sequence[str] | None = None,
    ) -> int:
        """Add several rows. Returns how many were written."""
        count = 0
        for row in rows:
            self.append_csv_row(path, row, fieldnames=fieldnames)
            count += 1
        return count

    def remove_csv_rows(self, path: Path, column: str, value: str) -> int:
        """Drop a case's existing rows from a results table.

        Called before a task writes its rows. Without it, redoing a case appends
        a second set and the table silently double-counts - which happened while
        the OCR stage was being developed: 778 rows describing 671 pages.

        Done once, at the start, rather than by rewriting the table at the end.
        That keeps the property that matters: rows still reach the disk as they
        are produced, so a run killed halfway still leaves usable results.

        Args:
            path: The table.
            column: Which column identifies the case, usually `docket`.
            value: The case being redone.

        Returns:
            How many rows were dropped.
        """
        if not path.exists() or path.stat().st_size == 0:
            return 0

        with open(path, "r", newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        kept = [row for row in rows if row.get(column) != value]
        removed = len(rows) - len(kept)

        if not removed:
            return 0

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept)
        atomic_write_text(path, buffer.getvalue())
        return removed

    def clean_temp_files(self) -> int:
        """Delete leftover temporary files from a previous crash.

        A file that cannot be deleted is skipped rather than allowed to raise.
        The usual reason is that another run is writing to it right now - on
        Windows an open file cannot be removed - and that was enough to bring
        down a whole run before this was handled. Tidying up is housekeeping; it
        must never be able to stop the work.

        Returns:
            How many were actually removed. Worth logging after an unclean
            shutdown, where it says how much was left half-written.
        """
        removed = 0
        for leftover in self.root.rglob(f"*{TEMP_SUFFIX}"):
            try:
                leftover.unlink()
                removed += 1
            except OSError:
                # In use, already gone, or not ours to delete. All fine: an
                # unfinished file is ignored anyway, and a later run will get it.
                continue
        return removed

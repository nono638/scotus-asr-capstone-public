"""Making the CUDA libraries findable on Windows.

The problem this solves, because it took a while to diagnose and the error
message points the wrong way.

CTranslate2 - the runtime under faster-whisper - needs `cublas64_12.dll`, one of
NVIDIA's maths libraries. It is already on this machine: PyTorch ships its own
copy inside `site-packages/torch/lib`. But CTranslate2 loads it by bare name, and
Windows looks for a bare name on the PATH. PyTorch's folder is not on the PATH,
so the load fails with:

    RuntimeError: Library cublas64_12.dll is not found or cannot be loaded

which reads like a missing installation and is nothing of the sort.

`os.add_dll_directory` does not fix it. That list is consulted for some load
styles and not for the one CTranslate2 uses. Putting the folder on the PATH does
work, and that is what this module does.

Doing it here rather than in a batch file matters: an unattended overnight run
should not depend on somebody having set an environment variable first.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

#: The library whose absence stops transcription.
_REQUIRED = "cublas64_12.dll"

#: Folders inside the environment that hold NVIDIA libraries. PyTorch's own
#: folder comes first because installing the CUDA build of PyTorch is already a
#: requirement, so it is the copy most likely to be present and to match.
_CANDIDATES = (
    Path("torch") / "lib",
    Path("nvidia") / "cublas" / "bin",
    Path("nvidia") / "cudnn" / "bin",
)

_done = False


def _site_packages() -> Path:
    """Where packages are installed in the running environment."""
    return Path(sys.prefix) / "Lib" / "site-packages"


def find_cuda_library_dirs() -> list[Path]:
    """Folders in this environment that hold NVIDIA runtime libraries."""
    base = _site_packages()
    return [base / candidate for candidate in _CANDIDATES if (base / candidate).is_dir()]


def cuda_libraries_ready() -> bool:
    """Is the library CTranslate2 needs somewhere the loader will look?"""
    for folder in find_cuda_library_dirs():
        if (folder / _REQUIRED).exists():
            return True
    return False


def ensure_cuda_libraries() -> list[Path]:
    """Put the NVIDIA library folders on the PATH, once.

    Safe to call as often as you like; it does its work the first time and
    returns the same answer afterwards. Safe on a machine with no GPU too, where
    it simply finds nothing and changes nothing.

    Returns:
        The folders added, empty if there were none to add.
    """
    global _done
    folders = find_cuda_library_dirs()
    if _done or not folders:
        return folders

    current = os.environ.get("PATH", "")
    known = {part.lower() for part in current.split(os.pathsep) if part}

    added = [folder for folder in folders if str(folder).lower() not in known]
    if added:
        os.environ["PATH"] = os.pathsep.join(
            [str(folder) for folder in added] + ([current] if current else [])
        )
        logger.info(
            "Added %d folder(s) to PATH so CUDA libraries can be found: %s",
            len(added),
            ", ".join(folder.name for folder in added),
        )

    # Registered as well. It is not what makes CTranslate2 work, but other
    # libraries do use this list, and it costs nothing.
    for folder in folders:
        try:
            os.add_dll_directory(str(folder))
        except (AttributeError, OSError):
            # Not Windows, or the folder vanished. Neither is worth stopping for.
            pass

    _done = True
    return added


def describe_gpu() -> str:
    """A short line about the GPU, for the log at the start of a run.

    Returns a plain sentence rather than raising when there is no GPU, because
    running on the processor is a supported situation - it is what happens on the
    laptop without an NVIDIA card.
    """
    try:
        import torch
    except ImportError:
        return "PyTorch is not installed, so no GPU is available."

    if not torch.cuda.is_available():
        return "No GPU available; work will run on the processor."

    name = torch.cuda.get_device_name(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    free = torch.cuda.mem_get_info()[0] / 1024**3
    return f"{name}, {free:.1f} GB free of {total:.1f} GB."


def device_index(device: str = "cuda") -> int:
    """Which card a device string means: `cuda` is the first, `cuda:1` the second."""
    _, _, number = device.partition(":")
    return int(number) if number.isdigit() else 0


def enough_memory(needed_gb: float, device: str = "cuda") -> tuple[bool, str]:
    """Is there room on the GPU for a model of roughly this size?

    Worth checking before a long job rather than discovering it an hour in. The
    usual cause of a shortfall on this machine is Ollama holding a model
    resident, which can occupy most of the card until it is told to let go.
    Measured against *free* memory, not the card's size, so it works the same
    on any NVIDIA card and counts whatever else is running.

    Args:
        needed_gb: Roughly how much the model wants.
        device: Which card, e.g. `cuda` or `cuda:1`.

    Returns:
        Whether there is room, and a sentence explaining if there is not.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return False, "No GPU available."
        free, total = torch.cuda.mem_get_info(device_index(device))
        free, total = free / 1024**3, total / 1024**3
    except Exception as error:  # noqa: BLE001 - a check must not itself fail a run
        return True, f"Could not check GPU memory ({error}); carrying on."

    if free >= needed_gb:
        return True, f"{free:.1f} GB free."

    if total < needed_gb:
        return False, (
            f"This card has {total:.1f} GB in all and the model needs about "
            f"{needed_gb:.1f} GB, so it cannot run here. Pick a smaller engine."
        )
    return False, (
        f"Only {free:.1f} GB free on the GPU and about {needed_gb:.1f} GB is "
        f"needed. Another program is holding the rest - if Ollama is running, "
        f"'ollama stop' will give the memory back."
    )


def prepare_gpu(
    device: str,
    needed_gb: float,
    label: str,
    *,
    cap: bool = True,
    bfloat16: bool = False,
) -> None:
    """The checks every engine makes before it loads a model.

    One function so that every engine gets the same protection. Until October
    2026 Voxtral and the two Granites had these checks and the other four did
    not, which was fine on one laptop watched by its owner and is not fine
    for somebody else's machine left running overnight.

    In order:

    1. A run set to use the card must actually see one. The dangerous case is
       the processor-only build of PyTorch: it imports without complaint and
       reports no card, and the engine would fail later with an error about
       CUDA that does not name the cause.
    2. The card must have room for this model now (`enough_memory`).
    3. The ceiling (`cap_memory`), so running short raises an error instead
       of Windows quietly paging GPU memory out to system RAM.
    4. A warning if the model wants bfloat16 and the card predates it (NVIDIA
       cards before the RTX 30 series). It still runs, but slowly.

    Does nothing for a run set to the processor. Nothing here is specific to
    one card: every figure is read from the card in use.

    Args:
        device: The engine's device setting, e.g. `cuda`, `cuda:1` or `cpu`.
        needed_gb: Roughly what the model needs at its peak, weights and
            working memory together. Each engine keeps its own measured figure.
        label: What is being loaded, for the messages.
        cap: False for engines whose memory PyTorch does not manage
            (faster-whisper runs on CTranslate2), where a cap would do nothing.
        bfloat16: Whether the model runs in bfloat16.

    Raises:
        RuntimeError: No usable card, or not enough room on it.
    """
    if not device.startswith("cuda"):
        return
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return  # nothing to check with; the engine will say what is missing

    if not torch.cuda.is_available():
        raise RuntimeError(
            f"{label} is set to run on an NVIDIA card (device: {device}), but "
            f"PyTorch cannot see one. Either there is no NVIDIA card, or the "
            f"processor-only build of PyTorch is installed - run setup.ps1 to "
            f"get the right one. To run on the processor instead, set "
            f"'device: cpu'."
        )
    index = device_index(device)
    if index >= torch.cuda.device_count():
        raise RuntimeError(
            f"{label} is set to use {device}, but this machine has "
            f"{torch.cuda.device_count()} NVIDIA card(s), numbered from 0."
        )

    room, reason = enough_memory(needed_gb, device)
    if not room:
        raise RuntimeError(f"Not enough video memory to run {label}. {reason}")

    if cap:
        cap_memory(device=device)

    if bfloat16:
        with torch.cuda.device(index):
            if not torch.cuda.is_bf16_supported(including_emulation=False):
                logger.warning(
                    "%s runs in bfloat16, which %s does not support natively. "
                    "It will run, but expect it to be much slower.",
                    label,
                    torch.cuda.get_device_name(index),
                )


# ---------------------------------------------------------------------------
# Watching the card while a run is going, so a crash leaves evidence behind.
#
# Written after a run died on 21 September 2026. The machine took a kernel
# bugcheck - VIDEO_SCHEDULER_INTERNAL_ERROR, the graphics scheduler faulting
# inside Windows itself - and rebooted. The run log was no help. It showed one
# chunk taking eleven minutes where the same work had taken two minutes an hour
# earlier, and then it simply stopped. Nothing recorded how much video memory
# was in use, so the obvious suspect could be neither confirmed nor cleared.
#
# The failure this guards against is the quiet one. When more is asked of the
# card than it has, Windows does not refuse. It moves GPU memory out to system
# RAM and carries on, perhaps fifty times slower, reporting no error at any
# point. The note in `aligner.py` records this project running into it once
# already. A run that is merely slow looks exactly like a run that is working.
#
# The point of the numbers below is that a slowdown can be read afterwards as
# either "the card was full" or "the card was fine and something else was
# wrong". That is the question that could not be answered on 21 September.
# ---------------------------------------------------------------------------

import json
import threading
from datetime import datetime, timezone


def memory_snapshot() -> dict:
    """How much video memory is in use right now.

    Two different measurements, and the gap between them is the interesting
    part:

    - `free_gb` and `used_gb` come from the driver and cover the whole card,
      including other programs. Ollama holding a model shows up here.
    - `torch_allocated_gb` is what this process's tensors actually occupy, and
      `torch_reserved_gb` is what PyTorch has claimed from the driver in order
      to hand it out. Reserved is always the larger, because PyTorch keeps
      blocks it has finished with rather than returning them.

    So a card reading nearly full while `torch_allocated_gb` is small means
    something else is holding the memory. Both large means we are.

    Returns:
        Plain numbers, safe to write to JSON. Empty when there is no GPU - a
        missing reading must never stop a run.
    """
    try:
        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            return {}
        free, total = torch.cuda.mem_get_info()
        return {
            "free_gb": round(free / 1024**3, 2),
            "used_gb": round((total - free) / 1024**3, 2),
            "total_gb": round(total / 1024**3, 2),
            "torch_allocated_gb": round(torch.cuda.memory_allocated() / 1024**3, 2),
            "torch_reserved_gb": round(torch.cuda.memory_reserved() / 1024**3, 2),
        }
    except Exception as error:  # noqa: BLE001 - a reading must never fail a run
        return {"error": str(error)}


def log_memory(label: str) -> None:
    """Put one memory reading in the ordinary run log.

    For the handful of moments worth seeing without opening another file: a
    model finishing loading, a case starting, a case ending.
    """
    reading = memory_snapshot()
    if not reading or "error" in reading:
        return
    logger.info(
        "GPU after %s: %.1f GB free of %.1f, this process holds %.1f GB "
        "(%.1f GB reserved)",
        label,
        reading["free_gb"],
        reading["total_gb"],
        reading["torch_allocated_gb"],
        reading["torch_reserved_gb"],
    )


def release_memory() -> None:
    """Hand PyTorch's spare blocks back to the driver.

    PyTorch holds on to memory it has finished with, because reusing a block is
    far faster than asking the driver for a new one. Normally that is the right
    trade. It is the wrong one here, and the measurements say so plainly.

    Transcribing 16-285 with Voxtral, chunk by chunk, with nothing else on the
    card:

        loaded, idle      allocated 12.1 GB     reserved 12.2 GB
        chunk 0           allocated 12.6 GB     reserved 17.1 GB
        chunk 1           allocated 12.6 GB     reserved 21.2 GB

    What is actually in use never moves. What PyTorch has taken from the driver
    climbs about 4 GB a chunk. Each chunk decodes a different number of tokens,
    so the cache it needs is a slightly different size every time, and a block
    of the wrong size cannot be reused - the allocator asks the driver for a
    new one and keeps the old. By chunk 1 there are 8.6 GB of blocks held and
    unused, and 1.3 GB left on a 24 GB card. Chunk 2 would want more than the
    card has.

    Windows does not refuse at that point. It moves GPU memory out to system
    RAM and carries on many times slower, raising nothing. That is how the run
    of 21 September died.

    **The usual fix is not available here.** `expandable_segments:True` in
    `PYTORCH_CUDA_ALLOC_CONF` is what PyTorch's own documentation recommends
    for reserved memory far exceeding allocated, and it is exactly this shape
    of problem. Setting it on this machine produces:

        expandable_segments not supported on this platform

    It needs CUDA's virtual memory calls, which PyTorch does not wire up on
    Windows. So the blunt instrument is the only instrument.

    **And it is cheap.** Measured at 69 milliseconds with 4 GB cached, against
    chunks that take 60 to 120 seconds. A tenth of one percent, to keep the
    card from filling. Called after every chunk, not just between recordings.
    """
    try:
        import gc  # noqa: PLC0415
        import torch  # noqa: PLC0415

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as error:  # noqa: BLE001 - tidying must not fail a run
        logger.debug("Could not release GPU memory: %s", error)


class MemoryRecorder:
    """Writes a video memory reading to its own file every few seconds.

    **Why a separate file, and why forced to disk.** A kernel crash takes
    Windows down without unwinding anything, and whatever the operating system
    was still holding in its write buffers is lost. A log flushed only by
    Python looks written and is not there after the reboot. So every line here
    is flushed and then `fsync`ed, which does not return until the disk says it
    has the data. That costs one small write every few seconds and buys a file
    whose last line is genuinely the last thing that happened.

    The readings go to `gpu-memory.jsonl` rather than into `run.log` because one
    every five seconds would bury the run log, and because a file of one JSON
    object per line reads straight into a table afterwards.

    Runs on a daemon thread, so it never keeps the program alive and never
    blocks an exit.

    Args:
        path: Where to write.
        every_seconds: Gap between readings. Five is often enough to catch a
            card filling up over a minute, and rare enough to cost nothing.
    """

    def __init__(self, path: Path, every_seconds: float = 5.0) -> None:
        self.path = Path(path)
        self.every_seconds = every_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._note = "starting"
        self._lock = threading.Lock()

    def note(self, text: str) -> None:
        """Say what the run is doing, so a reading can be placed in the run.

        A number on its own says the card was full. A number with
        "16-285 chunk 3" against it says which piece of work filled it.
        """
        with self._lock:
            self._note = text

    def start(self) -> None:
        """Begin recording."""
        if self._thread is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(
            target=self._loop, name="gpu-memory-recorder", daemon=True
        )
        self._thread.start()
        logger.info(
            "Recording GPU memory to %s every %.0f seconds.",
            self.path.name,
            self.every_seconds,
        )

    def stop(self) -> None:
        """Stop recording and wait briefly for the last line to land."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.every_seconds + 2.0)
            self._thread = None

    def sample(self, note: str | None = None) -> None:
        """Write one reading immediately, outside the usual rhythm.

        Used at the moments that matter most - either side of a chunk - so the
        file holds an exact before and after rather than whatever the timer
        happened to catch.
        """
        if note is not None:
            self.note(note)
        self._write(self._read())

    def _read(self) -> dict:
        with self._lock:
            note = self._note
        row = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": note,
        }
        row.update(memory_snapshot())
        return row

    def _write(self, row: dict) -> None:
        """Append one line and make sure the disk really has it."""
        try:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            logger.debug("Could not write a GPU memory reading: %s", error)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._write(self._read())
            self._stop.wait(self.every_seconds)


#: The one recorder for the current run.
#:
#: A module-level object rather than something threaded through every call.
#: The engines are several layers below the command line that creates it, and
#: passing a recorder down through the runner, the task list and every engine
#: would touch a lot of code to deliver one optional diagnostic.
_recorder: MemoryRecorder | None = None


def start_recording(path: Path, every_seconds: float = 5.0) -> MemoryRecorder:
    """Start the run's recorder and make it findable from anywhere."""
    global _recorder
    _recorder = MemoryRecorder(path, every_seconds)
    _recorder.start()
    return _recorder


def stop_recording() -> None:
    """Stop the run's recorder, if one was started."""
    global _recorder
    if _recorder is not None:
        _recorder.stop()
        _recorder = None


def mark(note: str, *, sample: bool = False) -> None:
    """Say what is happening now, for whoever reads the file afterwards.

    Does nothing when no recorder is running, so engines can call it freely -
    in a test, or from a one-off script, there is simply nothing to record.

    Args:
        note: What the run is doing, e.g. "16-285 chunk 3".
        sample: Write a reading immediately as well as setting the note. Worth
            it either side of a chunk; not worth it more often than that.
    """
    if _recorder is None:
        return
    if sample:
        _recorder.sample(note)
    else:
        _recorder.note(note)


#: How much of the card a run leaves for everything else: 8% of it, and never
#: less than 1.5 GB.
#:
#: Until October 2026 this was a fixed 92% of the card, worked out for the RTX
#: 5090 Laptop: 23.89 GB, of which the Windows desktop holds about 1.3. A
#: fixed share does not travel. On an 8 GB card 8% is 0.6 GB, less than a
#: desktop needs. So the share has a floor. On the 5090 the rule gives the same
#: 22.0 GB as before, so nothing measured there changes.
RESERVE_FRACTION = 0.08
RESERVE_MIN_GB = 1.5

#: Kept clear of whatever other programs held when the run started.
OTHERS_MARGIN_GB = 0.5


def cap_fraction(device: str = "cuda") -> float:
    """The share of this card a run may take, worked out from the card itself.

    The smaller of two limits:

    - the card less its reserve for the desktop (`RESERVE_FRACTION`); and
    - the card less what other programs hold right now, less a margin. With
      Ollama holding 10 GB of a 24 GB card, a cap of 22 GB would allow the very
      paging the cap exists to prevent.

    Returns 1.0 (no cap) if the card cannot be read.
    """
    try:
        import torch  # noqa: PLC0415

        index = device_index(device)
        free, total = torch.cuda.mem_get_info(index)
        free, total = free / 1024**3, total / 1024**3
        mine = torch.cuda.memory_reserved(index) / 1024**3
    except Exception:  # noqa: BLE001 - a limit must not fail a run
        return 1.0
    return share_for(total, others_gb=max(total - free - mine, 0.0))


def share_for(total_gb: float, others_gb: float = 0.0) -> float:
    """The rule in `cap_fraction`, on plain numbers so it can be tested anywhere.

    Args:
        total_gb: The card's size.
        others_gb: What other programs hold on it.
    """
    reserve = max(total_gb * RESERVE_FRACTION, RESERVE_MIN_GB)
    allowed = min(total_gb - reserve, total_gb - others_gb - OTHERS_MARGIN_GB)
    return max(min(allowed / total_gb, 1.0), 0.05)


def cap_memory(fraction: float | None = None, device: str = "cuda") -> None:
    """Stop this process from asking the card for more than it has.

    **Why a cap is worth having at all.** Out of memory on Windows is not an
    error. Ask for more than the card holds and the driver moves GPU memory out
    to system RAM and carries on, many times slower, raising nothing. Run that
    hard enough and the graphics scheduler misses a deadline and takes Windows
    down with it, which is what happened on 21 September 2026.

    A cap converts that into an ordinary exception. PyTorch refuses the
    allocation, the engine raises, the runner records the case as failed and
    moves to the next one. One case missing from a table is a far better
    outcome than a machine that reboots and loses the other sixty.

    This is a backstop, not the fix. The fix is `release_memory` after every
    chunk, which keeps the ceiling from being approached at all. This is here
    for the chunk that is denser than any chunk measured so far.

    **What it does not cover.** The cap is set once, at load. A program that
    starts using the card afterwards is not counted. `cap_fraction` does count
    what other programs held at the start.

    Args:
        fraction: Share of the card's total memory this process may reserve.
            Left out, it is worked out from the card (`cap_fraction`).
        device: Which card, e.g. `cuda` or `cuda:1`.
    """
    try:
        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            return
        index = device_index(device)
        if fraction is None:
            fraction = cap_fraction(device)
        torch.cuda.set_per_process_memory_fraction(fraction, index)
        total = torch.cuda.get_device_properties(index).total_memory / 1024**3
        logger.info(
            "Capped this process at %.0f%% of the card, %.1f GB of %.1f. Past "
            "that PyTorch will raise rather than let Windows page GPU memory "
            "out to system RAM.",
            fraction * 100,
            total * fraction,
            total,
        )
    except Exception as error:  # noqa: BLE001 - a backstop must not fail a run
        logger.warning("Could not cap GPU memory: %s", error)

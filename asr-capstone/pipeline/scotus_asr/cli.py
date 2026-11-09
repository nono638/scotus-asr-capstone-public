"""The command line.

    python -m scotus_asr.cli run --all
    python -m scotus_asr.cli asr --case 09-834
    python -m scotus_asr.cli report
    python -m scotus_asr.cli stop --run-id run-scotus250-qwen3

A run keeps its results in its own folder, and by default a new command carries on
in the most recent one. That is what makes resuming work: run the same command
again after a crash and it picks up where it stopped. Use `--new-run` to start
somewhere clean, which is what you want after changing a setting that would make
old results incomparable.

`stop`, from any other window, asks a run to finish the recording it is on and
then end, so a morning pause loses nothing. Ctrl+C in the run's own window stops
at once and loses the recording in progress.

This module is deliberately thin. It parses arguments, decides which tasks to
build, prints progress and gets out of the way. Everything it calls can be used
just as easily from a notebook or a window.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from . import stages
from .config import Config, load_config
from .corpora.registry import build_corpus
from .corpus.manifest import select
from .events import Event, EventBus, EventKind, log_listener
from .gpu import describe_gpu, start_recording, stop_recording
from .ledger import Ledger
from .runner import STOP_FILE, Runner
from .store import RunStore, new_run_id


def _latest_run(runs_dir: Path) -> Path | None:
    """The most recent run folder, or None if there are no runs yet.

    Run identifiers carry a timestamp and sort chronologically, so the newest is
    simply the last by name.
    """
    if not runs_dir.exists():
        return None
    folders = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    return folders[-1] if folders else None


def resolve_run_dir(config: Config, run_id: str | None, start_new: bool) -> Path:
    """Decide which run folder to work in.

    Args:
        config: Supplies where runs live.
        run_id: A specific run to continue.
        start_new: Force a fresh folder.

    Returns:
        The folder to use, created if necessary.
    """
    runs_dir = config.paths.runs_dir

    if run_id:
        return runs_dir / run_id
    if start_new:
        return runs_dir / new_run_id()

    existing = _latest_run(runs_dir)
    return existing if existing else runs_dir / new_run_id()


def _write_config(run_dir: Path, config: Config, engine=None) -> None:
    """Record the settings a run used, so a result can be traced back to them.

    Called twice per run. The first time is before any engine exists, so a run
    that fails while building its tasks still leaves a record of what it was
    asked to do. The second is once one does, and that is the one worth having:
    most of the speech-recognition section belongs to Whisper, and a Parakeet run
    recorded a beam size it never used while omitting the chunk length it
    depended on.

    Args:
        run_dir: The run's folder.
        config: The settings as loaded.
        engine: The engine about to run, if there is one. Given one, it is asked
            what it will actually use.
    """
    (run_dir / "config_used.yaml").write_text(
        yaml.safe_dump(config.to_dict(engine), sort_keys=False), encoding="utf-8"
    )


def _setup_logging(run_dir: Path, verbose: bool) -> None:
    """Send log messages to `run.log` and to the screen.

    The file is the point. An unattended run is read the next morning, and a
    message that only ever went to a closed terminal is a message that was never
    written.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(run_dir / "run.log", encoding="utf-8")]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )


def _printing_listener(event: Event) -> None:
    """Show progress on screen, without flooding it.

    Repeated progress messages overwrite one line rather than scrolling, so a
    150-minute transcription reports continuously without producing thousands of
    lines of output.
    """
    if event.kind is EventKind.TASK_PROGRESS:
        bar = f"{event.fraction * 100:5.1f}%" if event.fraction is not None else "     "
        print(f"\r  {bar}  {event.message}", end="", flush=True)
        return

    marks = {
        EventKind.TASK_STARTED: "->",
        EventKind.TASK_SKIPPED: "--",
        EventKind.TASK_FINISHED: "ok",
        EventKind.TASK_FAILED: "!!",
        EventKind.TASK_RETRYING: "..",
        EventKind.WARNING: " !",
    }
    mark = marks.get(event.kind, "  ")
    where = f"{event.task_id}: " if event.task_id else ""
    # Clear whatever the progress line left behind.
    print(f"\r{mark} {where}{event.message}".ljust(100))


def _dockets(args: argparse.Namespace, config: Config) -> list[str] | None:
    """The recordings asked for: `--case`, else the settings' `corpus.recordings`, else all."""
    if getattr(args, "case", None):
        return args.case
    return list(config.corpus.recordings) or None


def _choose_recordings(args: argparse.Namespace, config: Config, prepare: bool):
    """The corpus, and the recordings in it that the filters leave.

    Args:
        prepare: Download and unpack the corpus first if it is not on disk yet.
            Only the commands that do work ask for this; listing never downloads.

    Returns:
        (corpus, all recordings, chosen recordings)
    """
    corpus = build_corpus(config)
    if prepare and not corpus.fetches_per_recording:
        print(f"Preparing {corpus.name} in {corpus.root}")
        corpus.prepare(progress=lambda note: print(f"\r  {note}".ljust(100), end="", flush=True))
        print()
    try:
        cases = corpus.recordings()
    except FileNotFoundError as missing:
        raise SystemExit(f"{corpus.name} is not prepared yet ({missing}). "
                         f"Run the fetch command first.") from None

    dockets = _dockets(args, config)
    terms = args.term if getattr(args, "term", None) else None
    chosen = select(cases, dockets=dockets, terms=terms)
    if getattr(args, "limit", None):
        chosen = chosen[: args.limit]
    return corpus, cases, chosen


def _build_tasks(
    args: argparse.Namespace, config: Config, store: RunStore, events: EventBus
) -> list:
    """Work out which tasks the chosen command needs."""
    corpus, cases, chosen = _choose_recordings(
        args, config, prepare=args.command in ("fetch", "run"))
    dockets = _dockets(args, config)
    terms = args.term if getattr(args, "term", None) else None

    if terms and not chosen:
        known = sorted({case.term for case in cases if case.term})
        raise SystemExit(
            f"No cases in term(s) {', '.join(terms)}. Available: {', '.join(known)}"
        )

    if dockets:
        missing = set(dockets) - {case.docket for case in chosen}
        if missing:
            raise SystemExit(
                f"No such case(s): {', '.join(sorted(missing))}. "
                f"Available: {', '.join(c.docket for c in cases)}"
            )

    wanted = args.command
    tasks = []

    if wanted in ("fetch", "run") and corpus.fetches_per_recording:
        tasks += stages.build_fetch_tasks(chosen, store, events)
    if wanted in ("transcripts", "run"):
        tasks += stages.build_transcript_tasks(chosen, store, corpus)
    if wanted == "ocr":
        if corpus.name != "scotus":
            raise SystemExit("ocr reads Supreme Court transcript PDFs; it has nothing to do here.")
        tasks += stages.build_ocr_tasks(
            chosen, config, store, events,
            read_text=args.read_text,
            pages=_parse_pages(args.pages),
        )
    if wanted in ("asr", "run"):
        tasks += stages.build_asr_tasks(chosen, config, store, events)
    if wanted in ("score", "run"):
        tasks += stages.build_score_tasks(chosen, config, store)

    return tasks


def _parse_pages(text: str | None) -> list[int] | None:
    """Turn `1-5` or `3,7,11` into page numbers.

    Args:
        text: What the user typed, or None for every page.

    Returns:
        The pages in order with duplicates removed, or None for all of them.

    Raises:
        SystemExit: If the range cannot be read, with the two forms spelled out.
    """
    if not text:
        return None

    pages: set[int] = set()
    try:
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                first, last = part.split("-", 1)
                pages.update(range(int(first), int(last) + 1))
            elif part:
                pages.add(int(part))
    except ValueError:
        raise SystemExit(
            f"Could not read --pages {text!r}. Use a range like 1-5, "
            f"a list like 3,7,11, or both: 1-5,20"
        ) from None

    return sorted(pages)


def _command_cases(config: Config, args) -> int:
    """List the cases the manifest knows about.

    Honours the same `--case` and `--term` filters the working commands use.
    Listing everything regardless of them would be worse than useless: you would
    check what a run is about to cover, see the whole corpus, and have no way to
    tell the filter was ignored rather than empty.
    """
    corpus, _, cases = _choose_recordings(args, config, prepare=False)

    if not cases:
        print("No cases match.")
        return 1

    if corpus.name != "scotus":
        minutes = sum(c.audio_minutes or 0 for c in cases)
        print(f"{len(cases)} recording(s) in {corpus.name}, {minutes / 60:.1f} hours\n")
        print(f"{'recording':28} {'split':6} {'minutes':>8}  on disk")
        for case in cases:
            print(f"{case.id:28} {case.split:6} {case.audio_minutes or 0:8.1f}  "
                  f"{'yes' if case.audio_path.exists() else 'no'}")
        return 0

    print(f"{len(cases)} case(s)\n")
    print(f"{'case':16} {'term':6} {'argued':12} {'minutes':>8}  files")
    for case in cases:
        audio = "audio+transcript" if case.has_audio else "transcript only"
        on_disk = []
        if case.transcript_pdf.exists():
            on_disk.append("pdf")
        if case.audio_path.exists():
            on_disk.append("mp3")
        minutes = f"{case.audio_minutes:.0f}" if case.audio_minutes else "-"
        print(
            f"{case.docket:16} {case.term:6} {case.argued:12} {minutes:>8}  "
            f"{audio:17} on disk: {','.join(on_disk) or 'nothing'}"
        )
    return 0


def _command_report(store: RunStore) -> int:
    """Show what a run has produced so far."""
    results = store.results_path("cases.csv")
    if not results.exists():
        print(f"No results yet in {store.root}")
        return 1

    print(f"Results in {store.root}\n")
    print(results.read_text(encoding="utf-8"))

    for table, what in (
        ("omissions.csv", "omitted span(s) - 25+ words missing from the transcript"),
        ("silences.csv", "silence(s) over 10s - audio with no words at all"),
    ):
        path = store.results_path(table)
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            print(f"\n{len(lines) - 1} {what}, in {path.name}")
    return 0


def _command_stop(config: Config, run_id: str | None) -> int:
    """Ask a run to stop once the recording it is on has finished.

    It only leaves a `STOP` file in the run folder; the run notices it before its
    next task. The run has to be named. "The most recent run" is the last folder
    by name, and a fixed name like `run-scotus250-qwen3` sorts after every dated
    one, so guessing could leave the request in a run that is not running while
    the real one carries on.
    """
    if not run_id:
        print("Say which run to stop: --run-id <name>. The name is on the run's "
              "first line, 'Run folder: ...'.")
        return 2

    run_dir = resolve_run_dir(config, run_id, start_new=False)
    if not run_dir.is_dir():
        print(f"No run folder at {run_dir}. A full path works too: "
              "--run-id <path to the run folder>")
        return 1

    stop_file = run_dir / STOP_FILE
    stop_file.write_text("Stop once the recording in progress has finished.\n", encoding="utf-8")
    print(f"Asked {run_dir.name} to stop after the recording it is on.")
    print("It ends when that one is saved; run the same command again to carry on.")
    print(f"To take the request back before then, delete {stop_file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the command line. Returns the exit code."""
    parser = argparse.ArgumentParser(
        prog="scotus_asr",
        description="Measure speech recognition against reference transcripts: the "
                    "Supreme Court's by default, or another corpus named in the settings.",
    )
    parser.add_argument(
        "command",
        choices=["fetch", "transcripts", "ocr", "asr", "score", "run", "report", "cases",
                 "stop"],
        help=(
            "What to do. 'run' does fetch, transcripts, asr and score in order. "
            "'ocr' is separate because it measures how well the pages read rather "
            "than feeding the speech comparison, and takes a while. 'stop' asks the "
            "run named by --run-id to end after the recording it is on."
        ),
    )
    parser.add_argument(
        "--case", action="append", metavar="DOCKET",
        help="Limit to one case. Repeat for several. Default is every case.",
    )
    parser.add_argument(
        "--term", action="append", metavar="YEAR",
        help="Limit to one October Term, e.g. 2017. Repeat for several. A whole "
             "term is the natural unit for a run: one reporting contractor, one "
             "transcript format.",
    )
    parser.add_argument("--all", action="store_true", help="Every case (the default).")
    parser.add_argument(
        "--limit", type=int, metavar="N",
        help="Only the first N recordings after the other filters - for trying a "
             "new corpus or engine on a few before committing to all of them.",
    )
    parser.add_argument(
        "--config", type=Path, action="append",
        help="A settings file. Give it twice to combine a model's file with a "
             "corpus's, e.g. --config config/qwen3.yaml --config config/corpora/edacc.yaml; "
             "the later file wins where both set something.",
    )
    parser.add_argument("--run-id", help="Continue this run rather than the most recent.")
    parser.add_argument(
        "--new-run", action="store_true",
        help="Start a fresh run folder instead of continuing the most recent one.",
    )
    parser.add_argument(
        "--max-attempts", type=int,
        help="How many times to try a failing task before moving on.",
    )
    parser.add_argument("--verbose", action="store_true", help="Also log to the screen.")
    parser.add_argument(
        "--read-text", action="store_true",
        help=(
            "ocr only: also read the words with the vision model, not just the "
            "line numbers. About fifteen seconds a page, so it is off by default."
        ),
    )
    parser.add_argument(
        "--pages", metavar="RANGE",
        help="ocr only: which pages, e.g. 1-5 or 3,7,11. Default is all of them.",
    )

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "cases":
        return _command_cases(config, args)
    if args.command == "stop":
        return _command_stop(config, args.run_id)

    run_dir = resolve_run_dir(config, args.run_id, args.new_run)
    store = RunStore(run_dir)

    if args.command == "report":
        return _command_report(store)

    _setup_logging(run_dir, args.verbose)

    events = EventBus()
    events.subscribe(log_listener)
    events.subscribe(_printing_listener)

    # Written twice, on purpose. This first pass records what the run was asked
    # to do, so a run that dies while building its tasks still leaves a record.
    # It is rewritten below once an engine exists and can say what it will
    # actually use - see `_write_config`.
    _write_config(run_dir, config)

    ledger = Ledger(run_dir / "ledger.jsonl")
    runner = Runner(
        store,
        ledger,
        events,
        max_attempts=args.max_attempts or config.run.max_attempts,
        backoff_seconds=config.run.retry_backoff_seconds,
    )

    print(f"Run folder: {run_dir}")
    if args.command in ("asr", "run"):
        # Said once at the start, because "which machine am I on and is the card
        # free" is the first question when a run turns out slow. Logged as well
        # as printed: on 21 September this line went to a terminal that the
        # reboot took with it, and the run folder held no record of it.
        description = describe_gpu()
        print(f"GPU: {description}")
        logging.getLogger(__name__).info("GPU at the start of the run: %s", description)

        # A reading every five seconds, forced to disk, for the whole run. The
        # cost is a few hundred kilobytes; the value is that the next crash is
        # diagnosable instead of a guess.
        start_recording(run_dir / "gpu-memory.jsonl")

    tasks = _build_tasks(args, config, store, events)
    if not tasks:
        print("Nothing to do.")
        return 0

    # Now that task-building has succeeded, an engine can be built and asked what
    # it will run with. Only the commands that use one: fetch, transcripts and
    # ocr never touch an engine, and asking for one would fail a run that has no
    # business needing it.
    if args.command in ("asr", "score", "run"):
        from .asr.registry import build_engine  # noqa: PLC0415 - avoids a cycle

        _write_config(run_dir, config, build_engine(config.asr))

    print(f"{len(tasks)} task(s).\n")

    try:
        summary = runner.run(tasks)
    except KeyboardInterrupt:
        print("\nStopped. Finished work is saved - run the same command again to carry on.")
        return 130
    finally:
        # Stopped here rather than left to the daemon thread, so the file has a
        # tidy last line when the run ends normally. A file that stops mid-run
        # then means the run stopped mid-run.
        stop_recording()

    print(f"\n{summary.describe()}")
    if summary.failures:
        print("\nFailed:")
        for task_id, message in summary.failures:
            print(f"  {task_id}: {message}")
        print(f"\nFull tracebacks are in {ledger.path}")
        return 1

    if summary.stopped:
        # The same code as Ctrl+C, so a script running several models in a row
        # can tell "you stopped it" from "it finished" and not start the next one.
        print("Finished work is saved - run the same command again to carry on.")
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

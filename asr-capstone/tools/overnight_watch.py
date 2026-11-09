"""Wait while the overnight queue runs, and come back when something needs a look.

`pipeline/overnight.ps1` runs the queue in its own window. This waits beside it
and ends - printing what it saw - at the first of:

    ended          the queue finished, was stopped, or ended on an unexpected code
    died           its process is gone but it never said it ended
                   (window closed, process killed, laptop restarted)
    first result   the item in progress saved its first new transcript - worth
                   a look before trusting the rest of the night to it
    no heartbeat   the GPU memory file stopped growing, so the run's process is
                   frozen or gone
    quiet          no recording saved and no chunk started for too long: hung
    routine        nothing wrong; a progress report every so often

The supervisor agent of the asr-work skill (.claude/skills/asr-work/supervisor.md)
runs this again and again, dealing with whatever it reports in between. It only
reads files; it never stops or starts anything itself. Everything it judges by is
read from the files, not remembered, so a watcher started a minute ago sees a hang
that began an hour ago.

Usage:
    python tools/overnight_watch.py
    python tools/overnight_watch.py --quiet-minutes 120     # for Granite Plus
    python tools/overnight_watch.py --mark-checked          # first result looked at
    python tools/overnight_watch.py --status                # report now, do not wait
    python tools/overnight_watch.py --peek                  # newest transcript beside the record
    python tools/overnight_watch.py --queue                 # every row, its progress, time left
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.config import local_path  # noqa: E402

#: The memory recorder writes every 5 seconds. A file this stale means the
#: process writing it is frozen or gone.
HEARTBEAT_MINUTES = 5.0

#: How long after an item starts before a missing heartbeat counts. Listing the
#: work and loading a model come before the recorder's first line.
GRACE_MINUTES = 5.0


def read_jsonl(path: Path) -> list[dict]:
    """Every line of a JSON-lines file. A half-written last line is skipped."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def read_state(path: Path) -> dict | None:
    """The queue's state file. PowerShell 5.1 writes it with a byte-order mark."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def is_alive(pid: int) -> bool:
    """Whether a Windows process with this number is still running."""
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
        capture_output=True, text=True,
    ).stdout
    return f'"{pid}"' in out


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text)


def item_key(item: dict) -> str:
    """One queue item on one start. A restarted item gets a new key."""
    return f"{item['run']} | {item['terms']} | {item['started']}"


def saved_since(ledger: list[dict], since: datetime) -> tuple[list[dict], list[dict]]:
    """Transcripts saved, and tasks failed, since a moment."""
    recent = [r for r in ledger if parse_time(r["finished_at"]) >= since]
    saved = [r for r in recent if r["status"] == "ok" and "/asr/" in r["task_id"]]
    failed = [r for r in recent if r["status"] == "failed"]
    return saved, failed


def progress_at(item_started: datetime, ledger_path: Path, gpu: list[dict]) -> datetime:
    """When the item last moved: started, saved a task, or began a new chunk.

    Read from the files rather than remembered, so a watcher started a minute ago
    still knows the run has been stuck for an hour. A new chunk shows as a new
    note in the memory file; the note's first line says when that chunk began.
    """
    times = [item_started]
    if ledger_path.exists():
        times.append(datetime.fromtimestamp(ledger_path.stat().st_mtime, timezone.utc))
    if gpu:
        current = gpu[-1].get("note")
        since = gpu[-1]["at"]
        for row in reversed(gpu):
            if row.get("note") != current:
                break
            since = row["at"]
        times.append(parse_time(since))
    return max(times)


def decide(
    state: dict | None,
    alive: bool,
    first_unchecked: bool,
    item_minutes: float,
    heartbeat_minutes: float | None,
    quiet_minutes: float,
    quiet_limit: float,
    routine_due: bool,
) -> str | None:
    """Which event, if any, to return with. Most serious first."""
    if state is None:
        return "no queue: there is no state file, so the queue has not been started"
    if state["state"] != "running":
        return f"ended: the queue {state['state']} (exit code {state['exit_code']})"
    if not alive:
        return "died: the queue's process is gone but it never said it ended"
    if first_unchecked:
        return "first result: the item in progress saved its first new transcript"
    if (
        heartbeat_minutes is not None
        and item_minutes > GRACE_MINUTES
        and heartbeat_minutes > HEARTBEAT_MINUTES
    ):
        return f"no heartbeat: the GPU memory file is {heartbeat_minutes:.0f} minutes old"
    if quiet_minutes > quiet_limit:
        return f"quiet: nothing saved and no new chunk for {quiet_minutes:.0f} minutes"
    if routine_due:
        return "routine: nothing wrong"
    return None


def configs_of(entry: dict) -> list[Path]:
    """The settings files a queue row (or the item in progress) runs with.

    A row may name several, separated by spaces - an engine's file and then a
    corpus's, e.g. `config/qwen3.yaml config/corpora/edacc.yaml` - exactly as a
    run takes `--config` twice.
    """
    return [CAPSTONE / "pipeline" / c for c in entry.get("config", "").split()]


_RUNS_DIRS: dict[str, Path] = {}


def run_dir_for(entry: dict, runs: Path) -> Path:
    """Where this row's run lives. Each corpus keeps its runs in its own folder
    (EdAcc's beside the corpus, not among the Supreme Court's), so it comes from
    the row's settings; `runs` is the fallback for an entry that names none."""
    key = entry.get("config", "")
    if not key:
        return runs / entry["run"]
    if key not in _RUNS_DIRS:
        from scotus_asr.config import load_config
        _RUNS_DIRS[key] = Path(load_config(configs_of(entry)).paths.runs_dir)
    return _RUNS_DIRS[key] / entry["run"]


def row_label(row: dict) -> str:
    """The engine, plus the corpus when it is not the Supreme Court."""
    configs = row["config"].split()
    # corpus.yaml is Whisper's settings file; the others are named for their engine.
    engine = Path(configs[0]).stem.replace("corpus", "whisper")
    # A file in config/reruns/ names a few recordings to run again, not a corpus.
    names = [Path(c).stem for c in configs[1:] if "reruns" not in c]
    rerun = " re-run" if any("reruns" in c for c in configs) else ""
    return f"{engine}{rerun} ({names[0]})" if names else f"{engine}{rerun}"


def local(text: str) -> str:
    return parse_time(text).astimezone().strftime("%a %H:%M")


def describe(state: dict | None, runs: Path) -> str:
    """What the queue has done and is doing, in a few lines."""
    if state is None:
        return "No queue state."
    lines = [f"Queue: {state['state']}, started {local(state['started'])}, process {state['pid']}."]
    for done in state.get("items") or []:
        lines.append(
            f"  finished: {done['run']} {done['terms']}, exit {done['exit_code']}, "
            f"{local(done['started'])} to {local(done['ended'])}"
        )
    item = state.get("item")
    if item:
        run_dir = run_dir_for(item, runs)
        saved, failed = saved_since(read_jsonl(run_dir / "ledger.jsonl"), parse_time(item["started"]))
        lines.append(
            f"Now: {item['run']} {item['terms']} since {local(item['started'])} - "
            f"{len(saved)} transcript(s) saved, {len(failed)} failure(s)."
        )
        for row in saved[-3:]:
            lines.append(f"  {row['task_id'].split('/')[0]}: {row['summary']}")
        for row in failed[-3:]:
            lines.append(f"  FAILED {row['task_id']}: {row['error'][:200]}")
        gpu = read_jsonl(run_dir / "gpu-memory.jsonl")
        if gpu:
            last = gpu[-1]
            lines.append(
                f"GPU: {last.get('note')} - {last.get('torch_reserved_gb')} GB reserved, "
                f"{last.get('free_gb')} GB free, at {local(last['at'])}."
            )
    queue = CAPSTONE / "pipeline" / "overnight-queue.csv"
    todo = [l for l in queue.read_text(encoding="utf-8").splitlines() if l.startswith("todo,")]
    lines.append(f"Rows still marked todo: {len(todo)}.")
    return "\n".join(lines)


#: Speed in times real time, by config, for rows whose run has not measured its own
#: yet. Measured on the 5090 laptop; the table in supervisor.md says where from.
SPEEDS = {
    "parakeet.yaml": 47, "corpus.yaml": 19, "qwen3.yaml": 10, "canary.yaml": 35,
    "voxtral.yaml": 7, "granite.yaml": 8, "granite-plus.yaml": 1.6,
}


def queue_rows() -> list[dict]:
    """The queue file's rows, in order."""
    import csv
    path = CAPSTONE / "pipeline" / "overnight-queue.csv"
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def usual_minutes(case) -> float:
    """A recording's length before any transcript says: its own, where the listing
    has it (EdAcc does), else about an hour for an argument through 2019 and 85
    minutes since."""
    if getattr(case, "audio_minutes", None):
        return case.audio_minutes
    term = str(getattr(case, "term", "") or "")
    return (60 if int(term) < 2020 else 85) if term.isdigit() else 30


def row_progress(row: dict, runs: Path) -> dict:
    """How far one row has got, counted from its run's ledger, never stored.

    The arguments in a row come from the same listing and term filter a run uses,
    so "9 of 62" knows the 62. Hours left are the audio not yet transcribed over
    the speed this run has measured, or the usual speed for its engine.
    """
    from scotus_asr.config import load_config
    from scotus_asr.corpora.registry import build_corpus
    from scotus_asr.corpus.manifest import select

    config = load_config(configs_of(row))
    # No terms (a corpus that is not the Supreme Court) means no filter, not "none of them".
    cases = select(build_corpus(config).recordings(), terms=row["terms"].split() or None,
                   dockets=list(config.corpus.recordings) or None)
    run_dir = run_dir_for(row, runs)
    ledger = read_jsonl(run_dir / "ledger.jsonl")
    ok = [r for r in ledger if r["status"] == "ok"]
    transcribed = {r["task_id"].split("/")[0] for r in ok if "/asr/" in r["task_id"]}
    scored = {r["task_id"].split("/")[0] for r in ok if "/score/" in r["task_id"]}
    dockets = {c.docket for c in cases}

    speeds = []
    for r in ok:
        if "/asr/" in r["task_id"] and "times_realtime" in r.get("summary", ""):
            speeds.append(float(r["summary"].split(", ")[-1].split()[0]))
    speed = sorted(speeds)[len(speeds) // 2] if len(speeds) >= 3 else SPEEDS.get(Path(row["config"].split()[0]).name)

    # The case listing leaves audio_minutes empty, so the length of an argument
    # comes from up to ten transcripts this run already saved for these terms -
    # or, before there are any, about an hour through 2019 and 85 minutes since.
    lengths = []
    for docket in sorted(dockets & transcribed)[:10]:
        found = next((run_dir / "asr").glob(f"{docket}.*.json"), None)
        if found:
            lengths.append(json.loads(found.read_text(encoding="utf-8"))["audio_seconds"] / 60)
    left = [c for c in cases if c.docket not in transcribed]
    if lengths:
        left_minutes = len(left) * sum(lengths) / len(lengths)
    else:
        left_minutes = sum(usual_minutes(c) for c in left)
    return {
        "total": len(dockets),
        "transcribed": len(dockets & transcribed),
        "scored": len(dockets & scored),
        "hours_left": left_minutes / 60 / speed if speed else None,
        "speed": speed,
        "measured": len(speeds) >= 3,
    }


def queue_view(runs: Path) -> str:
    """Every row of the queue with how far it has got, and the time left."""
    lines = []
    total_left = 0.0
    for row in queue_rows():
        engine = row_label(row)
        what = row["terms"] or "all"
        if row["status"] == "hold":
            lines.append(f"hold  {engine:18} {what:15} {row['note']}")
            continue
        p = row_progress(row, runs)
        left = ""
        if row["status"] == "todo" and p["hours_left"] is not None:
            total_left += p["hours_left"]
            how = "measured" if p["measured"] else "usual"
            left = f"about {p['hours_left']:.1f} h left at {p['speed']:g}x ({how})"
        lines.append(
            f"{row['status']:5} {engine:18} {what:15} "
            f"{p['transcribed']:>3}/{p['total']:<3} transcribed, {p['scored']:>3} scored   {left}"
        )
    lines.append(f"\nLeft in the todo rows: about {total_left:.0f} hours of GPU time.")
    return "\n".join(lines)


def peek(state: dict | None, runs: Path, n: int = 60) -> str:
    """The start and end of the newest transcript, beside the start of the record.

    Enough to see at a glance whether the words are the right recording, in
    order, without loops or gaps - the things a score alone can hide.
    """
    item = (state or {}).get("item") or ((state or {}).get("items") or [None])[-1]
    if not item:
        return "No item to peek at."
    run_dir = run_dir_for(item, runs)
    saved = [r for r in read_jsonl(run_dir / "ledger.jsonl")
             if r["status"] == "ok" and "/asr/" in r["task_id"]]
    if not saved:
        return f"{item['run']} has no saved transcript yet."
    docket = saved[-1]["task_id"].split("/")[0]
    asr_file = next((run_dir / "asr").glob(f"{docket}.*.json"))
    result = json.loads(asr_file.read_text(encoding="utf-8"))
    words = " ".join(s["text"].strip() for s in result["segments"]).split()
    ref = json.loads((run_dir / "reference" / f"{docket}.json").read_text(encoding="utf-8"))
    ref_words = " ".join(t["text"] for t in ref["turns"]).split()
    return "\n".join([
        f"{asr_file.name}: {result['word_count']} words, {result['audio_seconds'] / 60:.0f} min of audio, "
        f"{result['speed_x_realtime']:.1f}x real time; the record has {len(ref_words)} words.",
        f"\nTRANSCRIPT, first {n} words:\n{' '.join(words[:n])}",
        f"\nRECORD, first {n} words:\n{' '.join(ref_words[:n])}",
        f"\nTRANSCRIPT, last 30 words:\n{' '.join(words[-30:])}",
        f"\nRECORD, last 30 words:\n{' '.join(ref_words[-30:])}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet-minutes", type=float, default=45.0,
                        help="how long without progress counts as hung (default 45)")
    parser.add_argument("--every-minutes", type=float, default=60.0,
                        help="how often to come back with a routine report (default 60)")
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--mark-checked", action="store_true",
                        help="record that the current item's first result was looked at")
    parser.add_argument("--status", action="store_true", help="report now and return")
    parser.add_argument("--peek", action="store_true",
                        help="newest transcript of the current item beside the record")
    parser.add_argument("--queue", action="store_true",
                        help="every row of the queue, how far it has got, and the time left")
    args = parser.parse_args()

    runs = local_path("scotus_corpus") / "runs"
    state_file = runs / "overnight-state.json"
    checked_file = runs / "overnight-checked.txt"

    if args.mark_checked:
        state = read_state(state_file)
        if not state or not state.get("item"):
            print("No item in progress to mark.")
            return 1
        with checked_file.open("a", encoding="utf-8") as f:
            f.write(item_key(state["item"]) + "\n")
        print(f"Marked as checked: {item_key(state['item'])}")
        return 0

    if args.status:
        print(describe(read_state(state_file), runs))
        return 0

    if args.peek:
        print(peek(read_state(state_file), runs))
        return 0

    if args.queue:
        print(queue_view(runs))
        return 0

    watch_started = time.monotonic()

    while True:
        state = read_state(state_file)
        item = (state or {}).get("item")
        alive = bool(state) and is_alive(int(state["pid"]))
        now = datetime.now(timezone.utc)

        first_unchecked = False
        item_minutes = 0.0
        quiet = 0.0
        heartbeat = None
        if item:
            run_dir = run_dir_for(item, runs)
            started = parse_time(item["started"])
            item_minutes = (now - started).total_seconds() / 60
            ledger = read_jsonl(run_dir / "ledger.jsonl")
            saved, _ = saved_since(ledger, started)
            checked = checked_file.read_text(encoding="utf-8").splitlines() if checked_file.exists() else []
            first_unchecked = bool(saved) and item_key(item) not in checked

            gpu_file = run_dir / "gpu-memory.jsonl"
            if gpu_file.exists():
                heartbeat = (time.time() - gpu_file.stat().st_mtime) / 60
            moved = progress_at(started, run_dir / "ledger.jsonl", read_jsonl(gpu_file))
            quiet = (now - moved).total_seconds() / 60

        event = decide(
            state,
            alive,
            first_unchecked,
            item_minutes,
            heartbeat,
            quiet_minutes=quiet,
            quiet_limit=args.quiet_minutes,
            routine_due=(time.monotonic() - watch_started) / 60 >= args.every_minutes,
        )
        if event:
            print(f"EVENT {event}\n")
            print(describe(state, runs))
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())

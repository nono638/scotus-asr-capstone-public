"""Download the files a manifest points at, into one folder per case.

Resumable: a file already on disk is skipped, and an interrupted download leaves
a temporary file that is removed rather than a truncated one that a later run
would mistake for finished. So a stopped download is restarted by running the
same command again.

Goes through the polite client, so a bulk download waits between files and backs
off if the server asks it to.

Usage:
    python tools/fetch_corpus.py --limit 12                 # a subset, newest first
    python tools/fetch_corpus.py --terms 2024,2025
    python tools/fetch_corpus.py --dockets 24-316,09-834
    python tools/fetch_corpus.py                            # everything in the manifest
    python tools/fetch_corpus.py --transcripts-only         # skip the audio
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.corpus.fetch import download  # noqa: E402
from scotus_asr.corpus.web import PoliteSession  # noqa: E402
from scotus_asr.config import local_path  # noqa: E402


def human(count: int) -> str:
    """Bytes as something readable."""
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        help="default: <scotus_corpus>/cases/manifest.json, from local-paths.yaml")
    parser.add_argument("--cases-dir", type=Path,
                        help="default: <scotus_corpus>/cases, from local-paths.yaml")
    parser.add_argument("--terms", help="Only these terms, e.g. 2024,2025")
    parser.add_argument("--dockets", help="Only these cases, e.g. 24-316,09-834")
    parser.add_argument("--limit", type=int, help="Stop after this many cases.")
    parser.add_argument("--transcripts-only", action="store_true")
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--with-audio-only", action="store_true",
        help="Skip cases the Court hosts no recording for.",
    )
    args = parser.parse_args()
    if args.manifest is None:
        args.manifest = local_path("scotus_corpus") / "cases" / "manifest.json"
    if args.cases_dir is None:
        args.cases_dir = local_path("scotus_corpus") / "cases"

    if not args.manifest.exists():
        print(f"No manifest at {args.manifest}. Run tools/build_manifest.py first.")
        return 1

    entries = json.loads(args.manifest.read_text(encoding="utf-8"))

    if args.terms:
        wanted = {int(t.strip()) for t in args.terms.split(",") if t.strip()}
        entries = [e for e in entries if e.get("term") in wanted]
    if args.dockets:
        wanted_dockets = {d.strip() for d in args.dockets.split(",") if d.strip()}
        entries = [e for e in entries if e["docket"] in wanted_dockets]
    if args.with_audio_only:
        entries = [e for e in entries if e.get("audio_url")]

    # Newest first, so a subset is drawn from the terms with the cleanest
    # born-digital transcripts rather than whatever happens to sort first.
    entries.sort(key=lambda e: (e.get("argued") or ""), reverse=True)
    if args.limit:
        entries = entries[: args.limit]

    if not entries:
        print("Nothing selected.")
        return 1

    session = PoliteSession(min_interval=args.interval)
    total_bytes = 0
    downloaded = skipped = failed = 0
    started = time.monotonic()

    print(f"{len(entries)} case(s) -> {args.cases_dir}\n")

    for index, entry in enumerate(entries, start=1):
        docket = entry["docket"]
        folder = args.cases_dir / entry["folder"]

        jobs: list[tuple[str, str, Path]] = []
        if not args.audio_only and entry.get("transcript_url"):
            jobs.append(("transcript", entry["transcript_url"],
                         folder / f"{docket}_transcript.pdf"))
        if not args.transcripts_only and entry.get("audio_url"):
            jobs.append(("audio", entry["audio_url"], folder / f"{docket}_audio.mp3"))

        for kind, url, destination in jobs:
            if destination.exists():
                skipped += 1
                continue
            try:
                written = download(url, destination, session=session)
                total_bytes += written
                downloaded += 1
                print(f"[{index}/{len(entries)}] {docket} {kind}: {human(written)}")
            except Exception as error:
                failed += 1
                print(f"[{index}/{len(entries)}] {docket} {kind}: FAILED "
                      f"{type(error).__name__}: {error}")

    elapsed = time.monotonic() - started
    print(f"\n{downloaded} downloaded ({human(total_bytes)}), "
          f"{skipped} already had, {failed} failed, in {elapsed / 60:.1f} min.")
    print(f"{session.requests_made} requests made.")
    return 1 if failed and not downloaded else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Re-download the sample audio that the repository does not carry.

The MP3s are about 134 MB, so they are kept out of git and fetched again when
needed. Every source URL is recorded in manifest.json, which is committed, so
this restores a fresh clone to a complete sample folder.

    python fetch_sample_media.py             # get whatever is missing
    python fetch_sample_media.py --check     # just say what is missing
    python fetch_sample_media.py --force     # download again even if present

All of these files are U.S. Government works in the public domain.

One thing to be careful about: the audio URL is read from the manifest, never
built from the docket number. Louisiana v. Callais was reargued and its October
recording is served as 24-109_2.mp3, so guessing the URL would quietly pair the
wrong audio with the transcript.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"

# The Court's site returns a short HTML error page to requests without a
# browser-like user agent, which then lands on disk named .mp3 and fails to
# open much later, somewhere confusing.
HEADERS = {"User-Agent": "Mozilla/5.0 (capstone sample fetcher)"}


def wanted(entry):
    """The files this entry should have, as (url, path) pairs."""
    folder = HERE / entry["folder"]
    docket = entry["docket"]
    out = []
    if entry.get("audio_url"):
        out.append((entry["audio_url"], folder / f"{docket}_audio.mp3"))
    if entry.get("transcript_url"):
        out.append((entry["transcript_url"], folder / f"{docket}_transcript.pdf"))
    return out


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as response:
        total = int(response.headers.get("Content-Length") or 0)
        got = 0
        with open(partial, "wb") as handle:
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                handle.write(chunk)
                got += len(chunk)
                if total:
                    pct = 100 * got / total
                    print(f"\r    {got/1e6:6.1f} MB of {total/1e6:.1f} MB ({pct:3.0f}%)",
                          end="", flush=True)
        print()

    # Only put the real filename in place once the whole file arrived, so an
    # interrupted run never leaves a truncated MP3 that looks complete.
    partial.replace(path)
    return got


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="list what is missing and stop")
    parser.add_argument("--force", action="store_true",
                        help="download even if the file is already there")
    args = parser.parse_args()

    if not MANIFEST.exists():
        sys.exit(f"No manifest at {MANIFEST}")

    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))

    jobs = []
    for entry in entries:
        for url, path in wanted(entry):
            if args.force or not path.exists():
                jobs.append((url, path))

    if not jobs:
        print("Nothing missing. The sample folder is complete.")
        return

    print(f"{len(jobs)} file(s) to fetch:")
    for _, path in jobs:
        print(f"  {path.relative_to(HERE)}")

    if args.check:
        return

    failures = []
    for i, (url, path) in enumerate(jobs, 1):
        print(f"\n[{i}/{len(jobs)}] {path.name}")
        print(f"    from {url}")
        try:
            size = download(url, path)
            print(f"    saved {size/1e6:.1f} MB")
        except Exception as exc:
            print(f"    FAILED: {exc}")
            failures.append((url, path, exc))

    print()
    if failures:
        print(f"{len(failures)} of {len(jobs)} failed:")
        for url, path, exc in failures:
            print(f"  {path.name}: {exc}")
        sys.exit(1)
    print(f"All {len(jobs)} file(s) downloaded.")


if __name__ == "__main__":
    main()

"""Ask the Court's site what exists, and write it down as a manifest.

Reads the per-term listing pages and records, for every argument, where its
transcript and recording actually live. Downloads nothing - this is the index
that `fetch_corpus.py` then works from.

Every address is read off a listing page rather than built from a docket number.
See `corpus/listing.py` for why that is not optional.

Usage:
    python tools/build_manifest.py --terms 2010-2025
    python tools/build_manifest.py --terms 2024,2025 --out <scotus_corpus>/manifest.json
    python tools/build_manifest.py --terms 2024 --no-resolve-mp3   # faster, no second hop
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.corpus.listing import assign_case_ids, build_term  # noqa: E402
from scotus_asr.corpus.web import PoliteSession  # noqa: E402

def default_out() -> Path:
    """Where the manifest goes unless --out says otherwise.

    It sits beside the case folders, the way `sample/manifest.json` does,
    because the pipeline finds it at `sample_dir / "manifest.json"`. A
    function rather than a constant, so --help works without local-paths.yaml.
    """
    return local_path("scotus_corpus") / "cases" / "manifest.json"


def parse_terms(text: str) -> list[int]:
    """Read `2010-2025`, `2024,2025`, or a mix of both.

    Args:
        text: The terms as typed.

    Returns:
        Every term named, in order, without duplicates.
    """
    terms: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            first, last = part.split("-", 1)
            terms.extend(range(int(first), int(last) + 1))
        elif part:
            terms.append(int(part))
    return sorted(set(terms))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terms", required=True, help="e.g. 2010-2025 or 2024,2025")
    parser.add_argument("--out", type=Path,
                        help="default: <scotus_corpus>/cases/manifest.json, from local-paths.yaml")
    parser.add_argument(
        "--no-resolve-mp3",
        action="store_true",
        help="Skip the second hop to each recording. One request per case cheaper, "
             "but the manifest then holds landing pages rather than recordings.",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Seconds between requests. Default 1.0.",
    )
    parser.add_argument(
        "--merge", action="store_true",
        help="Update only the terms named, keeping every other term already in "
             "the file. Rebuilding one term costs about seventy requests; "
             "rebuilding all sixteen costs a thousand, so repairing one term "
             "should not mean re-asking the Court for the other fifteen.",
    )
    args = parser.parse_args()
    if args.out is None:
        args.out = default_out()

    terms = parse_terms(args.terms)
    session = PoliteSession(min_interval=args.interval)

    entries: list[dict] = []
    warnings: list[str] = []

    for term in terms:
        try:
            found, said = build_term(session, term, resolve_mp3=not args.no_resolve_mp3)
        except Exception as error:
            print(f"OT{term}: FAILED - {type(error).__name__}: {error}")
            warnings.append(f"OT{term} could not be read: {error}")
            continue

        with_audio = sum(1 for entry in found if entry["audio_url"])
        print(f"OT{term}: {len(found):3} arguments, {with_audio:3} with audio")
        for warning in said:
            print(f"    WARN {warning}")
        entries.extend(found)
        warnings.extend(said)

    if not entries:
        print("Nothing found. Manifest not written.")
        return 1

    if args.merge and args.out.exists():
        existing = json.loads(args.out.read_text(encoding="utf-8"))
        rebuilt = set(terms)
        kept = [entry for entry in existing if entry.get("term") not in rebuilt]
        print(f"\nMerging: {len(entries)} rebuilt, {len(kept)} kept from "
              f"{len(existing)} already in the file.")
        # Identifiers are assigned across the whole manifest, so the kept
        # entries have to be present before that runs or a cross-term duplicate
        # would not be seen.
        entries = sorted(kept + entries, key=lambda e: (e.get("term", 0), e.get("argued", "")))

    renamed = assign_case_ids(entries)
    if renamed:
        note = (f"{len(renamed)} case(s) argued in more than one term, so the term is "
                f"part of their identifier: {', '.join(renamed)}")
        print(f"    NOTE {note}")
        warnings.append(note)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    total_audio = sum(1 for entry in entries if entry["audio_url"])
    print(f"\n{len(entries)} arguments, {total_audio} with audio -> {args.out}")
    print(f"{session.requests_made} requests made.")

    if warnings:
        report = args.out.with_name(args.out.stem + "_warnings.txt")
        report.write_text("\n".join(warnings), encoding="utf-8")
        print(f"{len(warnings)} warnings -> {report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

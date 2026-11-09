"""Read a run's transcriptions and ask whether they are coherent at all.

Scoring answers "how close to the reference". This answers a cruder question
that has to be settled first: does this output look like a transcript of this
recording? A run can score plausibly while being quietly broken - the wrong
half of a chunk kept, timings that drift, a mode that silently fell back to
something else - and word error rate alone hides all three.

Nine checks, each one a failure this project has actually had or come close to:

    coverage        do the words span the recording, or stop partway
    monotonic       do word times ever run backwards
    in bounds       does any word sit past the end of the audio
    pace            is any chunk running at a speed that is not speech
    seams           do chunks overlap or leave holes after trimming
    length          is the word count near the official transcript's
    duplication     do the same words appear twice at a seam
    silence         how much of the recording carries no word
    mode            is the output shaped the way the prompt asked for

Usage:
    python tools/sanity_check_run.py --run <scotus_corpus>/runs/run-20260924-164308
    python tools/sanity_check_run.py --run ... --verbose
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

#: Real Supreme Court argument runs between these, measured across this corpus.
#: Outside them a chunk is either a repetition loop or a chunk that gave up.
SLOWEST_REAL_SPEECH = 90.0
FASTEST_REAL_SPEECH = 250.0

#: A word may end a little past the audio - the last timestamp is the model's
#: estimate, not a measurement - but not by much.
GRACE_SECONDS = 3.0

#: How far a transcription's word count may sit from the official transcript's
#: before it is worth looking at. The official record includes speaker names and
#: procedural lines a model never says, so some gap is normal and one-sided.
WORD_COUNT_TOLERANCE = 0.35


def load_reference_words(path: Path) -> int:
    """How many words the official transcript holds."""
    data = json.loads(path.read_text(encoding="utf-8"))
    turns = data.get("turns") or data.get("segments") or []
    return sum(len((t.get("text") or "").split()) for t in turns)


def check(result: dict, reference_words: int | None, verbose: bool) -> list[str]:
    """Everything wrong with one case, as plain sentences."""
    problems: list[str] = []
    notes: list[str] = []

    segments = result.get("segments") or []
    audio_seconds = result.get("audio_seconds") or 0.0
    if not segments:
        return ["no segments at all"]

    words = [w for s in segments for w in (s.get("words") or [])]
    if not words:
        return ["segments exist but carry no timed words - the timings are missing"]

    # --- coverage: do the words reach the end of the recording --------------
    first_word = words[0]["start"]
    last_word = words[-1]["end"]
    covered = (last_word - first_word) / audio_seconds if audio_seconds else 0
    if covered < 0.9:
        problems.append(
            f"words only span {covered:.0%} of the recording "
            f"({first_word:.0f}s to {last_word:.0f}s of {audio_seconds:.0f}s) - "
            f"transcription stopped early or chunks were dropped"
        )
    else:
        notes.append(f"covers {covered:.0%} of the recording")

    # --- monotonic: time only moves forward ---------------------------------
    backwards = sum(1 for a, b in zip(words, words[1:]) if b["start"] < a["start"])
    if backwards:
        problems.append(
            f"{backwards} words start before the word before them - the "
            f"timestamps are not in order"
        )

    # --- in bounds ----------------------------------------------------------
    past_end = [w for w in words if w["end"] > audio_seconds + GRACE_SECONDS]
    if past_end:
        worst = max(w["end"] for w in past_end)
        problems.append(
            f"{len(past_end)} words sit past the end of the audio, the furthest "
            f"at {worst:.0f}s of {audio_seconds:.0f}s - the rollover unwrapping "
            f"is adding too much"
        )

    # --- pace ---------------------------------------------------------------
    fast, slow = [], []
    for s in segments:
        span = s["end"] - s["start"]
        if span < 20:
            continue
        rate = len(s["text"].split()) / (span / 60)
        if rate > FASTEST_REAL_SPEECH:
            fast.append((s["index"], rate))
        elif rate < SLOWEST_REAL_SPEECH:
            slow.append((s["index"], rate))
    if fast:
        problems.append(
            f"{len(fast)} chunks faster than speech, worst "
            f"{max(r for _, r in fast):.0f} words a minute at chunk "
            f"{max(fast, key=lambda x: x[1])[0]} - a repetition loop got through"
        )
    if slow:
        notes.append(
            f"{len(slow)} chunks under {SLOWEST_REAL_SPEECH:.0f} wpm "
            f"(quiet stretches, or a chunk that gave up early)"
        )

    # --- seams: overlaps and holes after trimming ---------------------------
    overlaps, holes = 0, 0
    for a, b in zip(segments, segments[1:]):
        if b["start"] < a["end"] - 0.5:
            overlaps += 1
        elif b["start"] - a["end"] > 20.0:
            holes += 1
    if overlaps:
        problems.append(
            f"{overlaps} chunk pairs overlap in time - the midpoint trim is "
            f"keeping the same words twice"
        )
    if holes:
        notes.append(f"{holes} gaps over 20s between chunks")

    # --- length against the official transcript -----------------------------
    said = sum(len(s["text"].split()) for s in segments)
    if reference_words:
        drift = (said - reference_words) / reference_words
        if abs(drift) > WORD_COUNT_TOLERANCE:
            problems.append(
                f"{said:,} words against the official {reference_words:,} "
                f"({drift:+.0%}) - too far off to be the same argument"
            )
        else:
            notes.append(f"{said:,} words vs official {reference_words:,} ({drift:+.0%})")
    else:
        notes.append(f"{said:,} words")

    # --- duplication at seams ----------------------------------------------
    doubled = 0
    for a, b in zip(segments, segments[1:]):
        tail = a["text"].split()[-8:]
        head = b["text"].split()[:8]
        if len(tail) == 8 and tail == head:
            doubled += 1
    if doubled:
        problems.append(f"{doubled} seams repeat the same eight words twice")

    # --- silence ------------------------------------------------------------
    spoken = sum(w["end"] - w["start"] for w in words)
    quiet = 1 - (spoken / audio_seconds) if audio_seconds else 0
    notes.append(f"{quiet:.0%} of the recording carries no word")

    # --- mode: is this timestamp-mode output --------------------------------
    text = " ".join(s["text"] for s in segments)
    if "[T:" in text:
        problems.append("timestamp tags leaked into the transcript text")
    capitals = sum(1 for c in text if c.isupper())
    # Only Granite Plus is meant to write no capitals; every other model does.
    if "plus" in result.get("engine", "").lower() and capitals > len(text) * 0.005:
        notes.append(
            f"{capitals} capital letters - unexpected for this model, which IBM "
            f"say omits capitalisation"
        )

    if verbose:
        for note in notes:
            print(f"        - {note}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--verbose", action="store_true",
                        help="Print the figures behind each case, not just faults.")
    args = parser.parse_args(argv)

    files = sorted((args.run / "asr").glob("*.json"))
    if not files:
        print(f"No finished transcriptions in {args.run / 'asr'}")
        return 1

    print(f"{args.run.name}: {len(files)} cases finished\n")

    all_problems: dict[str, list[str]] = {}
    coverage, quiet_share, wer_like = [], [], []

    for path in files:
        result = json.loads(path.read_text(encoding="utf-8"))
        docket = result.get("docket") or path.stem.split(".")[0]
        ref_path = args.run / "reference" / f"{docket}.json"
        if not ref_path.exists():
            matches = list((args.run / "reference").glob(f"{docket}*.json"))
            ref_path = matches[0] if matches else None
        reference_words = load_reference_words(ref_path) if ref_path else None

        print(f"  {docket}")
        problems = check(result, reference_words, args.verbose)
        if problems:
            all_problems[docket] = problems
            for p in problems:
                print(f"        PROBLEM: {p}")
        elif not args.verbose:
            print("        looks coherent")

        segments = result.get("segments") or []
        words = [w for s in segments for w in (s.get("words") or [])]
        if words and result.get("audio_seconds"):
            coverage.append((words[-1]["end"] - words[0]["start"])
                            / result["audio_seconds"])
            spoken = sum(w["end"] - w["start"] for w in words)
            quiet_share.append(1 - spoken / result["audio_seconds"])
        if reference_words:
            said = sum(len(s["text"].split()) for s in segments)
            wer_like.append(said / reference_words)

    print("\n" + "=" * 70)
    if coverage:
        print(f"coverage of the recording: median {statistics.median(coverage):.1%}, "
              f"worst {min(coverage):.1%}")
    if quiet_share:
        print(f"share with no word:        median {statistics.median(quiet_share):.1%}, "
              f"worst {max(quiet_share):.1%}")
    if wer_like:
        print(f"words vs official:         median {statistics.median(wer_like):.2f}x, "
              f"range {min(wer_like):.2f}-{max(wer_like):.2f}x")
    print("=" * 70)

    if all_problems:
        print(f"\n{len(all_problems)} of {len(files)} cases have something worth "
              f"looking at:")
        for docket, problems in all_problems.items():
            print(f"  {docket}: {'; '.join(problems)}")
        return 1
    print(f"\nAll {len(files)} cases are coherent on every check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

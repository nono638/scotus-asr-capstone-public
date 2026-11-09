"""Saying what kind of difference each difference is.

A word error rate says how much the two texts disagree. It does not say whether
the machine misheard a party's name or merely put a comma where the reporter put
a full stop, and for a court record those are not remotely the same failure.

This is the idea behind `fstalign`'s entity classes and `asr-evaluation`'s
confusion tables, done in plain Python over the comparison `pairs.py` writes.
Rev's tool is the better one and is worth adopting properly later - it is C++ in
a Docker image, which is a heavier dependency than this project needs today.

The categories are deliberately coarse. A category that needs argument to apply
is one that will be applied inconsistently, and the point of the breakdown is to
show where the gap between benchmark scoring and verbatim scoring comes from.
That gap is the thesis, so it matters that its parts are countable rather than
merely arguable.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

#: The order matters: the first category that fits wins, so the narrow and
#: uninteresting explanations are tested before the broad ones.
#:
#: `casing` may also involve punctuation - `law. That` against `law, that` moved
#: both - so it means "the letters match once case is ignored", not "only the
#: capitals changed". Naming it `casing_only` would be a lie about 900-odd rows.
CATEGORIES = [
    "variant",
    "punctuation",
    "casing",
    "contraction",
    "number_format",
    "citation",
    "proper_noun",
    "disfluency",
    "wording",
]

#: Forms that mean the same thing and should not be scored as errors. This is
#: `fstalign`'s `--syn` idea: you declare the equivalences rather than argue
#: about them afterwards. Deliberately short - every entry is a decision about
#: what counts as a correct record, so the list belongs in the write-up, not
#: buried in a helper.
VARIANTS: dict[str, str] = {
    "versus": "v",
    "v": "v",
    "vs": "v",
    "united states": "us",
    "u s": "us",
    "percent": "%",
    "section": "§",
}

#: Interruption and false-start marks. These are the reporter's notation for
#: broken speech, not sounds anybody made, so a machine cannot produce them and
#: should not really be charged for their absence. Counting them separately is
#: the only way to see how much of the verbatim penalty is this.
DASHES = re.compile(r"^[‐-―+-]+$")

#: Words a verbatim record keeps and a readable transcript throws away.
FILLERS = frozenset({
    "uh", "um", "er", "ah", "hm", "hmm", "mm", "mhm", "uh-huh", "huh",
    "well", "so", "okay", "yeah", "yes", "no", "right",
})

#: The shapes a legal citation takes in argument.
CITATION = re.compile(
    r"(\bv\.?\b|\bversus\b|\bU\.?S\.?C\.?\b|\bF\.?\s?\d?d\b|\bSection\b|\bsection\b|\§|\(\w\)|\d+\(\w\))"
)

_PUNCT = re.compile(r"[^\w\s]")
_DIGIT = re.compile(r"\d")


def _bare(text: str) -> str:
    """Letters and digits only, lowercased. Two texts equal here differ only in
    punctuation, spacing and case."""
    return _PUNCT.sub("", text).replace(" ", "").lower()


def _expand(text: str) -> str:
    """Undo the common contractions, so `we'll` and `we will` compare equal."""
    out = text.lower()
    for long, short in (
        ("will", "'ll"), ("not", "n't"), ("are", "'re"),
        ("is", "'s"), ("have", "'ve"), ("would", "'d"), ("am", "'m"),
    ):
        out = out.replace(short, long)
    return _PUNCT.sub("", out).replace(" ", "")


def _as_variant(text: str) -> str:
    """Fold the declared equivalent forms together, so `v.` and `versus` match."""
    cleaned = _PUNCT.sub(" ", text.lower())
    cleaned = " ".join(cleaned.split())
    if cleaned in VARIANTS:
        return VARIANTS[cleaned]
    return "".join(VARIANTS.get(word, word) for word in cleaned.split())


def classify(reference_text: str, asr_text: str, kind: str) -> str:
    """Name the kind of difference between one pair of stretches.

    Args:
        reference_text: What the official record has. Empty for an insertion.
        asr_text: What the machine produced. Empty for a deletion.
        kind: The alignment's own label - equal, substitute, delete or insert.

    Returns:
        One of `CATEGORIES`. An `equal` chunk is not a difference and returns
        `equal`.
    """
    if kind == "equal":
        return "equal"

    # A deletion has no machine text and an insertion has no reference text. Read
    # back from CSV by pandas those empty cells arrive as NaN, a float, and NaN
    # is truthy - so `value or ""` does not catch it and every caller would need
    # its own guard. Coercing here is the one place that fixes all of them.
    reference = reference_text.strip() if isinstance(reference_text, str) else ""
    machine = asr_text.strip() if isinstance(asr_text, str) else ""
    both = f"{reference} {machine}".strip()

    # Notation for broken speech, on either side.
    if reference and all(DASHES.match(word) for word in reference.split()):
        return "disfluency"
    if machine and all(DASHES.match(word) for word in machine.split()):
        return "disfluency"

    if reference and machine:
        if _bare(reference) == _bare(machine):
            # Same letters and digits, so only the marks or the capitals moved.
            # Case preserved here: if these still match, the capitals did not.
            kept_case_ref = _PUNCT.sub("", reference).replace(" ", "")
            kept_case_asr = _PUNCT.sub("", machine).replace(" ", "")
            return "punctuation" if kept_case_ref == kept_case_asr else "casing"
        if _expand(reference) == _expand(machine):
            return "contraction"
        if _as_variant(reference) == _as_variant(machine):
            return "variant"

    words = (reference or machine).split()
    if any(_DIGIT.search(word) for word in words):
        # A number written differently on each side, e.g. `202` against `two-oh-two`.
        if reference and machine and _DIGIT.search(reference) != _DIGIT.search(machine):
            return "number_format"
        if CITATION.search(both):
            return "citation"
        return "number_format"

    if CITATION.search(both):
        return "citation"

    if all(word.lower().strip(".,;:?!") in FILLERS for word in words if word):
        return "disfluency"

    # A capital in the middle of a turn is a name: a party, counsel, a justice,
    # a statute. These are the errors that matter most in a record and the ones
    # benchmark scoring is least likely to surface.
    if any(word[:1].isupper() for word in words[1:]) or (
        words and words[0][:1].isupper() and len(words) == 1
    ):
        return "proper_noun"

    # Plain mishearing: `was` for `is`, or a dropped `the`. The largest group,
    # and the only one that is a straightforward speech-recognition error.
    return "wording"


@dataclass(frozen=True)
class Breakdown:
    """How a case's differences divide up.

    Attributes:
        counts: How many differences of each category.
        reference_words: Official words involved, per category.
        confusions: The most common `(official, machine)` pairs.
    """

    counts: Counter
    reference_words: Counter
    confusions: Counter

    def share(self) -> dict[str, float]:
        """Each category as a percentage of all differences."""
        total = sum(self.counts.values())
        if not total:
            return {}
        return {name: round(100 * n / total, 1) for name, n in self.counts.most_common()}


def summarize(rows: Iterable, top_confusions: int = 25) -> Breakdown:
    """Count the categories across a set of comparison rows.

    Args:
        rows: Anything with `kind`, `reference_text`, `asr_text` and
            `reference_words` - the `WordPair`s `pairs.py` produces, or the same
            columns read back from its CSV.
        top_confusions: How many substitution pairs to keep.

    Returns:
        The breakdown.
    """
    counts: Counter = Counter()
    words: Counter = Counter()
    confusions: Counter = Counter()

    for row in rows:
        kind = _get(row, "kind")
        if kind == "equal":
            continue

        reference = _get(row, "reference_text") or ""
        machine = _get(row, "asr_text") or ""
        category = classify(reference, machine, kind)

        counts[category] += 1
        words[category] += int(_get(row, "reference_words") or 0)

        # Case is kept. Lowercasing here would turn the single most common
        # verbatim difference - `Court` heard as `court` - into a pair of
        # identical strings, which reads as a bug in the table rather than as
        # the finding it actually is.
        if kind == "substitute" and reference and machine:
            confusions[(reference, machine)] += 1

    return Breakdown(
        counts=counts,
        reference_words=words,
        confusions=Counter(dict(confusions.most_common(top_confusions))),
    )


def _get(row, field: str):
    """Read a field from a dataclass or from a dict read out of CSV."""
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def add_categories(rows: Sequence[dict]) -> Sequence[dict]:
    """Label rows read back from CSV, in place, with a `category` column."""
    for row in rows:
        row["category"] = classify(
            row.get("reference_text", ""), row.get("asr_text", ""), row.get("kind", "")
        )
    return rows

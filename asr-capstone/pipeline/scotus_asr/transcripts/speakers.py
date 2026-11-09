"""Tidying speaker labels.

Court reporters are human, and the labels in an official transcript are not
perfectly consistent. The 2024 Braidwood transcript calls the same advocate both
`MR. MOOPPAN` and `MR. MOOPAN`; the 2004 Booker transcript contains a
`CHIEF JUSTICE STEVENS` who did not exist, alongside the real `JUSTICE STEVENS`
and `CHIEF JUSTICE REHNQUIST`. Left alone, each typo becomes an extra speaker and
inflates any count of who was in the room.

What this module will and will not do
-------------------------------------
It fixes only what it can fix **without guessing**:

* spacing, stray punctuation and casing, which are unambiguous
* a justice who appears both with and without the word CHIEF, where the surname
  settles it

It deliberately does **not** merge labels just because they look similar. In the
2010 Kasten transcript, `MR. KASTEN` and `MR. KASTER` differ by one letter, and
whether they are one person or two is a question about that argument, not about
spelling. Merging on similarity would quietly decide it. Instead, near-duplicates
are reported as warnings so a person can look, and an explicit alias list in the
settings applies any decision they reach.

Silently merging speakers in a study whose subject is speaker attribution would
be a bad trade: it makes the numbers tidier and less true.
"""

from __future__ import annotations

import re
from collections import Counter

#: Two labels at most this far apart in edit distance are worth a second look.
_SIMILAR_ENOUGH = 2

#: `CHIEF JUSTICE ROBERTS` -> the surname `ROBERTS`.
_JUSTICE = re.compile(r"^(?:CHIEF\s+)?JUSTICE\s+(?P<surname>[A-Z][A-Z'\- ]*)$")


def normalize_label(label: str) -> str:
    """Tidy one label in ways that cannot be wrong.

    Collapses whitespace, uppercases, and drops a trailing colon or full stop
    that sometimes survives extraction. Does not touch spelling.

    >>> normalize_label("  justice  kagan :")
    'JUSTICE KAGAN'
    """
    cleaned = " ".join(label.split()).upper()
    return cleaned.rstrip(":. ").strip()


def _edit_distance(a: str, b: str) -> int:
    """How many single-character edits turn one string into the other.

    A small implementation rather than a dependency: the strings here are short
    speaker labels, so the obvious algorithm is quick enough and one fewer
    package is one fewer thing to install on the other laptop.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,          # delete
                    current[j - 1] + 1,       # insert
                    previous[j - 1] + (char_a != char_b),  # substitute
                )
            )
        previous = current
    return previous[-1]


def _unify_justice_titles(counts: Counter[str]) -> dict[str, str]:
    """Settle `CHIEF JUSTICE X` against `JUSTICE X`.

    Only one justice is the Chief, and no justice is elevated partway through an
    argument. So if the same surname appears both with and without the title, one
    of them is a slip, and the form used more often is the real one.

    Returns:
        A mapping from the wrong form to the right one, empty if nothing clashed.
    """
    by_surname: dict[str, list[str]] = {}
    for label in counts:
        match = _JUSTICE.match(label)
        if match:
            by_surname.setdefault(match.group("surname").strip(), []).append(label)

    aliases: dict[str, str] = {}
    for surname, labels in by_surname.items():
        if len(labels) < 2:
            continue
        # Most frequent wins; ties broken by the shorter label, since an
        # erroneous CHIEF is an addition rather than an omission.
        best = max(labels, key=lambda name: (counts[name], -len(name)))
        for label in labels:
            if label != best:
                aliases[label] = best
    return aliases


def find_near_duplicates(labels: list[str]) -> list[tuple[str, str, int]]:
    """Spot labels similar enough that one may be a typo of the other.

    Args:
        labels: Distinct labels from one transcript.

    Returns:
        `(rarer, commoner, edit distance)` for each suspicious pair. Reported,
        never applied - see this module's note on why.
    """
    found: list[tuple[str, str, int]] = []
    ordered = sorted(set(labels))
    for i, first in enumerate(ordered):
        for second in ordered[i + 1 :]:
            # Only compare labels of the same kind. MR. SMITH and JUSTICE SMITH
            # are not plausible typos of one another.
            if first.split()[0] != second.split()[0]:
                continue
            distance = _edit_distance(first, second)
            if 0 < distance <= _SIMILAR_ENOUGH:
                found.append((first, second, distance))
    return found


def resolve_speakers(
    labels: list[str], aliases: dict[str, str] | None = None
) -> tuple[dict[str, str], list[str]]:
    """Work out the tidied form of every label in one transcript.

    Args:
        labels: Every speaker label, in the order spoken, repeats included. The
            repetition matters: frequency is what decides which of two clashing
            forms is the real one.
        aliases: Decisions already made by a person, applied last so they
            override everything worked out automatically.

    Returns:
        A mapping from each original label to its tidied form, and a list of
        warnings about anything that looked wrong but was not changed.
    """
    tidied = [normalize_label(label) for label in labels]
    counts = Counter(tidied)
    warnings: list[str] = []

    mapping: dict[str, str] = {label: label for label in counts}
    mapping.update(_unify_justice_titles(counts))

    for wrong, right in mapping.items():
        if wrong != right:
            warnings.append(
                f"Speaker {wrong!r} appeared {counts[wrong]} time(s) alongside "
                f"{right!r} ({counts[right]} time(s)); treating them as the same person."
            )

    for rarer, commoner, distance in find_near_duplicates(list(counts)):
        # Report in the order that reads naturally: the rarer one is the suspect.
        if counts[rarer] > counts[commoner]:
            rarer, commoner = commoner, rarer
        if mapping.get(rarer) == mapping.get(commoner):
            continue  # already settled above
        warnings.append(
            f"Speakers {rarer!r} ({counts[rarer]}) and {commoner!r} "
            f"({counts[commoner]}) differ by {distance} character(s). "
            f"Left as two people - set an alias in the settings if they are one."
        )

    if aliases:
        for wrong, right in aliases.items():
            mapping[normalize_label(wrong)] = normalize_label(right)

    # Re-apply the original spellings so callers can look up what they have.
    full = {original: mapping.get(normalize_label(original), normalize_label(original))
            for original in labels}
    return full, warnings

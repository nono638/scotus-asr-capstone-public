"""Deciding what counts as a difference before anything is scored.

This module is where the project's central argument lives, so it is worth being
explicit about it.

Published word error rates - the 2.6% and 5.63% figures you see quoted - are
computed after stripping punctuation, capitalisation and speaker attribution, and
after deleting filler words and expanding contractions. A verbatim legal record is
*defined* by those things. So a single number cannot answer the question; you have
to score the same pair of texts more than once and report the difference.

Three ways of comparing, each isolating something different:

`standard`
    The normalizer from the Whisper paper. Lower-cases, removes punctuation,
    deletes fillers such as "uh" and "um", expands contractions, standardises
    numbers. Use this and only this when comparing against published benchmark
    numbers, because it is what those numbers were computed with.

`lowercase_nopunct`
    Lower-cases and drops punctuation, and does nothing else. Fillers stay,
    contractions stay as spoken. The gap between this and `standard` is the cost
    of the Whisper normalizer's *extra* tidying, which is otherwise invisible.

`verbatim`
    Collapses runs of whitespace. Nothing else. Punctuation, capitalisation and
    every "uh" are scored as words in their own right. This is the one that
    reflects what a certified transcript is judged against.

Reporting all three, and treating the distance between them as a finding rather
than an inconvenience, is the point.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

#: Everything that is not a letter, a digit, an apostrophe or whitespace.
_PUNCTUATION = re.compile(r"[^\w\s']", flags=re.UNICODE)

#: Cached because building Whisper's normalizer loads a spelling table.
_whisper_normalizer: Callable[[str], str] | None = None


def _standard(text: str) -> str:
    """Apply the normalizer from the Whisper paper.

    Imported and built lazily: it loads a spelling-mapping file, and the verbatim
    comparison must not pay that cost.
    """
    global _whisper_normalizer
    if _whisper_normalizer is None:
        from whisper_normalizer.english import EnglishTextNormalizer

        _whisper_normalizer = EnglishTextNormalizer()
    return _whisper_normalizer(text)


def _lowercase_nopunct(text: str) -> str:
    """Lower-case and remove punctuation, changing nothing else."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCTUATION.sub(" ", text)
    return " ".join(text.split())


def _verbatim(text: str) -> str:
    """Collapse whitespace and leave everything else exactly as it is."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


#: The comparisons to run, by name. Scoring walks this, so adding a fourth way of
#: comparing means adding one entry here and nothing else.
NORMALIZERS: dict[str, Callable[[str], str]] = {
    "standard": _standard,
    "lowercase_nopunct": _lowercase_nopunct,
    "verbatim": _verbatim,
}


@dataclass(frozen=True)
class TokenizedText:
    """Normalized tokens, and where each came from.

    Normalizing can change how many words there are - "I'd" becomes "I would",
    and "(Laughter.)" disappears altogether. So a token's position is not its
    original word's position, and anything that wants to map a scoring result
    back to a timestamp needs the link between them.

    That link is what turns "forty words are missing" into "forty seconds are
    missing starting at 1:12:30", which is the number a court reporter cares
    about.

    Attributes:
        tokens: The tokens actually compared.
        source_index: For each token, which original word it came from. Several
            tokens can share one source word.
    """

    tokens: list[str]
    source_index: list[int]

    def __len__(self) -> int:
        return len(self.tokens)

    @property
    def text(self) -> str:
        """The tokens joined back into a string."""
        return " ".join(self.tokens)


def normalize_tokens(
    words: list[str], normalizer: str = "standard", harmonise: bool = False
) -> TokenizedText:
    """Normalize a list of words, keeping track of where each token came from.

    Each word is normalized on its own rather than the whole text at once. That
    is slightly slower, and it is what makes the mapping back to timestamps
    possible: normalizing everything in one go would lose which token came from
    which word.

    Args:
        words: The words, as spoken or as transcribed.
        normalizer: Which comparison to use. See this module's introduction.
        harmonise: Apply the fixes in `harmonise` first, so that differences
            nobody could hear - "3553(e)" against "3553E", "Vogt's" against
            "votes" - are not counted. Off by default, so the original figures
            can still be reproduced exactly.

    Returns:
        The tokens and their source word positions. A word that normalizes away
        to nothing - a stage direction, a filler under `standard` - contributes
        no tokens, which is correct: it is not being compared.

    Raises:
        KeyError: If the normalizer name is not one of `NORMALIZERS`.
    """
    try:
        transform = NORMALIZERS[normalizer]
    except KeyError:
        raise KeyError(
            f"No normalizer called {normalizer!r}. "
            f"Available: {', '.join(sorted(NORMALIZERS))}."
        ) from None

    tokens: list[str] = []
    source_index: list[int] = []

    if harmonise:
        from .harmonise import fix_words, fix_words_verbatim

        fixed = fix_words_verbatim(words) if normalizer == "verbatim" else fix_words(words)
    else:
        fixed = [[word] for word in words]

    for position, pieces in enumerate(fixed):
        for piece in pieces:
            for token in transform(piece).split():
                tokens.append(token)
                source_index.append(position)

    return TokenizedText(tokens=tokens, source_index=source_index)

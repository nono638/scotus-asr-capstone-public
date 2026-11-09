"""Lining the official record up against what the machine heard.

`jiwer` does the actual work. It uses RapidFuzz underneath, which computes edit
distance with a bit-parallel algorithm in C++, so aligning twenty-odd thousand
words against twenty-odd thousand more takes well under a second. The naive
approach would be four hundred million cells of dynamic programming in Python,
which is why this wraps a library rather than implementing it.

What this adds on top is the bookkeeping: jiwer reports positions in its own token
stream, and those positions have to lead back to real words with real timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import jiwer

from .normalize import TokenizedText, normalize_tokens

#: What jiwer calls each kind of alignment chunk.
ChunkType = Literal["equal", "substitute", "delete", "insert"]


@dataclass(frozen=True)
class Chunk:
    """One stretch where the two texts agree, or one specific way they differ.

    `delete` means words in the official record that the machine never produced -
    the raw material of an omitted span. `insert` means the machine produced words
    that were never said, which is where invented names show up.

    Attributes:
        kind: equal, substitute, delete or insert.
        ref_start: First reference token, counting from zero.
        ref_end: One past the last reference token.
        hyp_start: First machine token.
        hyp_end: One past the last machine token.
    """

    kind: ChunkType
    ref_start: int
    ref_end: int
    hyp_start: int
    hyp_end: int

    @property
    def ref_length(self) -> int:
        """How many reference tokens this covers."""
        return self.ref_end - self.ref_start

    @property
    def hyp_length(self) -> int:
        """How many machine tokens this covers."""
        return self.hyp_end - self.hyp_start


@dataclass
class Alignment:
    """The full comparison of one reference against one machine transcription.

    Attributes:
        normalizer: Which way of comparing produced this. The same pair of texts
            scored three ways gives three different alignments, and mixing them
            up would be an easy and invisible mistake.
        chunks: The alignment, in order.
        reference: Normalized reference tokens, with their source positions.
        hypothesis: Normalized machine tokens, with theirs.
        wer: Word error rate.
        hits, substitutions, deletions, insertions: The counts behind it.
    """

    normalizer: str
    chunks: list[Chunk] = field(default_factory=list)
    reference: TokenizedText | None = None
    hypothesis: TokenizedText | None = None
    wer: float = 0.0
    hits: int = 0
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0

    @property
    def reference_length(self) -> int:
        """Reference tokens compared. The denominator of the word error rate."""
        return len(self.reference) if self.reference else 0

    @property
    def deletion_rate(self) -> float:
        """Share of the record the machine simply did not produce."""
        if not self.reference_length:
            return 0.0
        return self.deletions / self.reference_length

    def summary(self) -> dict[str, float | int | str]:
        """The headline numbers, ready for a results row."""
        return {
            "normalizer": self.normalizer,
            "wer": round(self.wer, 6),
            "hits": self.hits,
            "substitutions": self.substitutions,
            "deletions": self.deletions,
            "insertions": self.insertions,
            "reference_tokens": self.reference_length,
            "hypothesis_tokens": len(self.hypothesis) if self.hypothesis else 0,
            "deletion_rate": round(self.deletion_rate, 6),
        }


def align_words(
    reference_words: list[str],
    hypothesis_words: list[str],
    normalizer: str = "standard",
    harmonise: bool = False,
    vocabulary: set[str] | None = None,
) -> Alignment:
    """Compare the official record against a machine transcription.

    Args:
        reference_words: The official transcript, as words. Speaker labels must
            already be gone - nobody says "JUSTICE KAGAN" out loud, so counting
            it as a missed word would penalise the model for being right.
        hypothesis_words: What the machine produced, as words. Keeping this as a
            list rather than a string is what lets a result be traced back to a
            timestamp later.
        normalizer: Which way of comparing. See `normalize`.
        harmonise: Stop the comparison inventing differences nobody could hear.
            See `harmonise`. Off by default, so old figures can be reproduced.
        vocabulary: The words that decide which neighbouring tokens are joined
            ("e mails" -> "emails"). Defaults to the words of these two texts.
            Pass a shared one when several machine texts are compared against
            the same reference, so the reference is joined the same way each time.

    Returns:
        The alignment and its counts. An empty reference gives an alignment with
        a word error rate of zero rather than a division by zero; the caller
        should notice the empty reference through `reference_length`.
    """
    reference = normalize_tokens(reference_words, normalizer, harmonise)
    hypothesis = normalize_tokens(hypothesis_words, normalizer, harmonise)

    if harmonise:
        # "e mails" and "emails": join on both sides the same way, so a word
        # written open, hyphenated or closed counts as one word.
        from .harmonise import join_compounds

        if vocabulary is None:
            vocabulary = set(reference.tokens) | set(hypothesis.tokens)
        reference = TokenizedText(*join_compounds(reference.tokens, reference.source_index, vocabulary))
        hypothesis = TokenizedText(*join_compounds(hypothesis.tokens, hypothesis.source_index, vocabulary))

    if not reference.tokens:
        return Alignment(
            normalizer=normalizer,
            reference=reference,
            hypothesis=hypothesis,
            insertions=len(hypothesis.tokens),
        )

    # jiwer takes strings, and splits them on whitespace by default. The tokens
    # are already whitespace-free, so joining and letting it split back gives
    # exactly the token stream that was put in.
    output = jiwer.process_words(reference.text, hypothesis.text)

    chunks = [
        Chunk(
            kind=chunk.type,
            ref_start=chunk.ref_start_idx,
            ref_end=chunk.ref_end_idx,
            hyp_start=chunk.hyp_start_idx,
            hyp_end=chunk.hyp_end_idx,
        )
        for chunk in output.alignments[0]
    ]

    return Alignment(
        normalizer=normalizer,
        chunks=chunks,
        reference=reference,
        hypothesis=hypothesis,
        wer=output.wer,
        hits=output.hits,
        substitutions=output.substitutions,
        deletions=output.deletions,
        insertions=output.insertions,
    )

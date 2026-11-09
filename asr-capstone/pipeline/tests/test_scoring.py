"""Tests for normalizing, aligning, and finding the passages that went missing.

The omitted-span tests matter most. That measurement is the project's own
contribution, so there is no reference implementation to check against - only
these.
"""

from __future__ import annotations

import pytest

from scotus_asr.asr.base import Word
from scotus_asr.scoring.align import align_words
from scotus_asr.scoring.normalize import NORMALIZERS, normalize_tokens
from scotus_asr.scoring.omissions import find_omissions, summarize_omissions


class TestNormalizers:
    """Three ways of comparing, each hiding something different."""

    def test_verbatim_keeps_punctuation_and_case(self):
        tokens = normalize_tokens(["Mr.", "Chief", "Justice,"], "verbatim")
        assert tokens.tokens == ["Mr.", "Chief", "Justice,"]

    def test_lowercase_nopunct_removes_typography_only(self):
        tokens = normalize_tokens(["Mr.", "Chief", "Justice,"], "lowercase_nopunct")
        assert tokens.tokens == ["mr", "chief", "justice"]

    def test_lowercase_nopunct_keeps_filler_words(self):
        """A model that drops ten seconds of hesitation still dropped them."""
        tokens = normalize_tokens(["uh,", "I", "think"], "lowercase_nopunct")
        assert "uh" in tokens.tokens

    def test_the_standard_normalizer_deletes_fillers(self):
        """Which is exactly why it cannot be the only number reported."""
        tokens = normalize_tokens(["uh", "I", "think"], "standard")
        assert "uh" not in tokens.tokens

    def test_a_word_that_normalizes_away_contributes_no_tokens(self):
        tokens = normalize_tokens(["(Laughter.)"], "lowercase_nopunct")
        assert tokens.tokens == ["laughter"]
        assert normalize_tokens(["--"], "lowercase_nopunct").tokens == []

    def test_every_token_can_be_traced_to_its_source_word(self):
        """One word can become several tokens: "I'd" becomes "i would".

        Without this mapping there is no way back from a scoring position to a
        timestamp, and no way to say when an omission happened.
        """
        tokens = normalize_tokens(["I'd", "go"], "standard")
        assert len(tokens.tokens) == len(tokens.source_index)
        assert tokens.source_index[-1] == 1

    def test_an_unknown_normalizer_says_what_is_available(self):
        with pytest.raises(KeyError, match="verbatim"):
            normalize_tokens(["word"], "nonsense")

    def test_all_three_are_registered(self):
        assert set(NORMALIZERS) == {"standard", "lowercase_nopunct", "verbatim"}


class TestAlignment:
    def test_identical_text_scores_zero(self):
        words = "the court will hear argument".split()
        alignment = align_words(words, words, "lowercase_nopunct")
        assert alignment.wer == 0.0
        assert alignment.deletions == 0

    def test_missing_words_count_as_deletions(self):
        reference = "the court will hear argument this morning".split()
        hypothesis = "the court will morning".split()
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")
        assert alignment.deletions == 3

    def test_invented_words_count_as_insertions(self):
        alignment = align_words("the court".split(), "the supreme court".split(),
                                "lowercase_nopunct")
        assert alignment.insertions == 1

    def test_an_empty_reference_does_not_divide_by_zero(self):
        alignment = align_words([], "something".split(), "lowercase_nopunct")
        assert alignment.wer == 0.0
        assert alignment.reference_length == 0

    def test_punctuation_only_shows_up_under_verbatim(self):
        """The project's central point, as a test.

        The same pair of texts differ only in punctuation. Scored the benchmark
        way they are identical; scored the way a certified record is judged, they
        are not.
        """
        reference = "the court will hear argument".split()
        hypothesis = "The court, will hear argument.".split()

        assert align_words(reference, hypothesis, "lowercase_nopunct").wer == 0.0
        assert align_words(reference, hypothesis, "verbatim").wer > 0.0


def timed_words(texts, start=0.0, gap_at=None, gap_length=0.0):
    """Build machine words that run back to back, with one silence in the middle.

    Each word lasts exactly one second and begins where the last one ended, so
    the only gap anywhere in the timeline is the one put there on purpose. That
    makes the expected duration in each test the plain value of `gap_length`,
    with no arithmetic to get wrong.

    Args:
        texts: The words.
        start: When the first word begins.
        gap_at: Index to insert a silence before, standing in for skipped speech.
        gap_length: How long that silence lasts, in seconds.
    """
    words = []
    clock = start
    for index, text in enumerate(texts):
        if gap_at is not None and index == gap_at:
            clock += gap_length
        words.append(Word(text=text, start=clock, end=clock + 1.0))
        clock += 1.0
    return words


class TestOmissions:
    def test_a_long_dropped_run_is_found(self):
        reference = ["word"] * 10 + [f"missing{i}" for i in range(40)] + ["word"] * 10
        hypothesis = ["word"] * 20
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        spans = find_omissions(alignment, min_words=25)

        assert len(spans) == 1
        assert spans[0].word_count == 40

    def test_short_gaps_are_not_reported(self):
        """Ordinary scattered errors are not omissions."""
        reference = ["word"] * 10 + ["gone"] * 5 + ["word"] * 10
        hypothesis = ["word"] * 20
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        assert find_omissions(alignment, min_words=25) == []

    def test_one_accidental_word_does_not_split_a_span(self):
        """The merge rule, and the reason it exists.

        A dropped passage usually contains a word or two the model emitted
        anyway. Without merging, one stray match turns a single 60-word omission
        into two 30-word ones, both of which fall under the threshold and vanish
        from the results entirely.
        """
        reference = (
            ["start"] * 5
            + [f"a{i}" for i in range(30)]
            + ["the"]
            + [f"b{i}" for i in range(30)]
            + ["end"] * 5
        )
        hypothesis = ["start"] * 5 + ["the"] + ["end"] * 5
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        merged = find_omissions(alignment, min_words=25, merge_gap=2)
        assert len(merged) == 1
        assert merged[0].word_count == 61

        split = find_omissions(alignment, min_words=25, merge_gap=0)
        assert len(split) == 2

    def test_the_silence_in_the_machine_timeline_gives_the_duration(self):
        """A skipped passage leaves a hole between two timestamps.

        That hole is measured directly from the model's own output, with no
        second alignment model involved.
        """
        reference = ["word"] * 5 + [f"missing{i}" for i in range(30)] + ["word"] * 5
        hypothesis = ["word"] * 10
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        spans = find_omissions(
            alignment,
            hypothesis_timings=timed_words(hypothesis, gap_at=5, gap_length=12.0),
            min_words=25,
        )

        assert len(spans) == 1
        assert spans[0].gap_seconds == pytest.approx(12.0, abs=0.01)

    def test_a_span_at_the_very_start_is_flagged(self):
        """There is no earlier word to measure from."""
        reference = [f"missing{i}" for i in range(30)] + ["word"] * 5
        hypothesis = ["word"] * 5
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        spans = find_omissions(alignment, hypothesis_timings=timed_words(hypothesis),
                               min_words=25)
        assert spans[0].at_start
        assert spans[0].gap_seconds is None

    def test_spans_come_back_worst_first(self):
        reference = (
            [f"a{i}" for i in range(30)]
            + ["kept"] * 10
            + [f"b{i}" for i in range(60)]
            + ["kept"] * 10
        )
        hypothesis = ["kept"] * 20
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        spans = find_omissions(alignment, min_words=25)
        assert [span.word_count for span in spans] == [60, 30]

    def test_timings_that_disagree_with_the_word_count_are_flagged(self):
        """Forty words cannot fit in one second, so something is wrong."""
        reference = ["word"] * 5 + [f"missing{i}" for i in range(40)] + ["word"] * 5
        hypothesis = ["word"] * 10
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")

        spans = find_omissions(
            alignment,
            hypothesis_timings=timed_words(hypothesis, gap_at=5, gap_length=1.0),
            min_words=25,
        )
        assert spans[0].timing_disagrees

    def test_a_perfect_transcription_has_nothing_to_report(self):
        words = ["word"] * 50
        alignment = align_words(words, words, "lowercase_nopunct")
        assert find_omissions(alignment, min_words=25) == []

    def test_the_summary_leads_with_seconds_lost(self):
        reference = ["word"] * 5 + [f"missing{i}" for i in range(30)] + ["word"] * 5
        hypothesis = ["word"] * 10
        alignment = align_words(reference, hypothesis, "lowercase_nopunct")
        spans = find_omissions(
            alignment,
            hypothesis_timings=timed_words(hypothesis, gap_at=5, gap_length=10.0),
            min_words=25,
        )

        summary = summarize_omissions(spans)
        assert summary["omitted_spans"] == 1
        assert summary["omitted_words"] == 30
        assert summary["seconds_lost"] == pytest.approx(10.0, abs=0.1)

    def test_the_summary_of_nothing_is_all_zeros(self):
        summary = summarize_omissions([])
        assert summary["omitted_spans"] == 0
        assert summary["seconds_lost"] == 0.0


def test_written_words_joins_whisper_pieces_only():
    from scotus_asr.scoring.metrics import written_words

    assert written_words([" a", " dope", "-themed", " party."]) == ["a", "dope-themed", "party."]
    # Engines that give whole words come back as they were, even with a stray space.
    assert written_words(["a", "dope-themed", " party."]) == ["a", "dope-themed", " party."]
    assert written_words([]) == []
    # Numbers split the same way, and a word at a chunk seam stays its own word.
    assert written_words([" up", " 2", ".5", "%", " in", "Next", " year"]) == ["up", "2.5%", "in", "Next", "year"]


def test_verbatim_counts_a_split_word_once():
    from scotus_asr.scoring.align import align_words
    from scotus_asr.scoring.metrics import written_words

    reference = ["a", "dope-themed", "party."]
    pieces = [" a", " dope", "-themed", " party."]
    assert align_words(reference, pieces, "verbatim").wer > 0
    assert align_words(reference, written_words(pieces), "verbatim").wer == 0


def test_leaderboard_rate_reads_the_whole_text():
    from scotus_asr.scoring.align import align_words
    from scotus_asr.scoring.metrics import leaderboard_error_rate

    reference, hypothesis = ["twenty", "five", "dollars"], ["25", "dollars"]
    assert leaderboard_error_rate(reference, hypothesis) == 0
    assert align_words(reference, hypothesis, "standard").wer > 0

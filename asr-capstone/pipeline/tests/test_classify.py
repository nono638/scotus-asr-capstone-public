"""Tests for sorting differences into kinds.

The breakdown these produce is an argument, not a convenience: it claims that a
third of the verbatim penalty is marks and capitals rather than mishearing. A
category that quietly drifts changes that claim without anything looking wrong,
so each one is pinned to an example here.
"""

from __future__ import annotations

from scotus_asr.scoring.classify import classify, summarize


def test_an_agreeing_stretch_is_not_a_difference():
    assert classify("we will hear argument", "we will hear argument", "equal") == "equal"


def test_only_the_marks_moved():
    assert classify("so,", "so", "substitute") == "punctuation"


def test_only_the_capitals_moved():
    assert classify("Court", "court", "substitute") == "casing"


def test_marks_and_capitals_together_count_as_casing():
    """`casing` means the letters match once case is ignored, not that marks held.

    Naming this `casing_only` would misdescribe most of the rows that land here.
    """
    assert classify("law. That", "law, that", "substitute") == "casing"


def test_a_contraction_is_not_a_mishearing():
    assert classify("We will", "We'll", "substitute") == "contraction"
    assert classify("do not", "don't", "substitute") == "contraction"


def test_declared_equivalents_are_not_errors():
    """The `--syn` idea: say which forms mean the same thing, once, on purpose."""
    assert classify("v.", "versus", "substitute") == "variant"


def test_interruption_marks_are_disfluency_whichever_dash_is_used():
    """The reporter writes `--`; the model writes an em dash. Same notation."""
    assert classify("--", "—", "substitute") == "disfluency"
    assert classify("--", "", "delete") == "disfluency"


def test_a_filler_word_is_disfluency():
    assert classify("uh", "", "delete") == "disfluency"


def test_a_name_is_a_proper_noun():
    assert classify("Saint-Gobain", "St. Gobain", "substitute") == "proper_noun"


def test_a_plain_mishearing_is_wording():
    assert classify("was", "is", "substitute") == "wording"
    assert classify("the", "", "delete") == "wording"


def test_an_empty_side_does_not_crash():
    """Read back from CSV by pandas, a missing cell arrives as NaN, not "".

    NaN is truthy, so the usual `value or ""` guard does not catch it. Every
    notebook would need its own check if this were not handled here.
    """
    assert classify("something", float("nan"), "delete") == "wording"
    assert classify(float("nan"), "something", "insert") == "wording"


def test_the_breakdown_counts_categories_and_keeps_case_in_the_confusions():
    rows = [
        {"kind": "substitute", "reference_text": "Court", "asr_text": "court",
         "reference_words": 1},
        {"kind": "substitute", "reference_text": "Court", "asr_text": "court",
         "reference_words": 1},
        {"kind": "delete", "reference_text": "the", "asr_text": "", "reference_words": 1},
        {"kind": "equal", "reference_text": "we will", "asr_text": "we will",
         "reference_words": 2},
    ]

    breakdown = summarize(rows)

    assert breakdown.counts["casing"] == 2
    assert breakdown.counts["wording"] == 1
    assert "equal" not in breakdown.counts
    # Lowercasing here would make the commonest verbatim difference look like
    # two identical strings.
    assert breakdown.confusions[("Court", "court")] == 2

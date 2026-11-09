"""Tests for tidying speaker labels.

The line this module walks: fix what is certainly a slip, report what might be,
and never quietly decide a question about who was in the room. In a study whose
subject includes speaker attribution, merging two speakers on a guess would make
the numbers tidier and less true.
"""

from __future__ import annotations

from scotus_asr.transcripts.speakers import (
    find_near_duplicates,
    normalize_label,
    resolve_speakers,
)


class TestTidyingOneLabel:
    def test_spacing_and_case_are_fixed(self):
        assert normalize_label("  justice  kagan ") == "JUSTICE KAGAN"

    def test_a_trailing_colon_is_dropped(self):
        assert normalize_label("MR. GREIM:") == "MR. GREIM"

    def test_spelling_is_left_alone(self):
        """Tidying is not correcting."""
        assert normalize_label("MR. MOOPAN") == "MR. MOOPAN"

    def test_an_accented_surname_survives(self):
        assert normalize_label("general aguiñaga") == "GENERAL AGUIÑAGA"


class TestJusticeTitles:
    def test_a_stray_chief_is_settled_by_the_surname(self):
        """The 2004 Booker transcript contains a Chief Justice Stevens who did
        not exist, alongside the real Justice Stevens.

        Only one justice is the Chief and nobody is promoted mid-argument, so the
        form used more often is the right one. This is safe to decide.
        """
        labels = ["JUSTICE STEVENS"] * 39 + ["CHIEF JUSTICE STEVENS"]
        mapping, warnings = resolve_speakers(labels)

        assert mapping["CHIEF JUSTICE STEVENS"] == "JUSTICE STEVENS"
        assert any("STEVENS" in warning for warning in warnings)

    def test_a_real_chief_justice_is_left_alone(self):
        labels = ["CHIEF JUSTICE REHNQUIST"] * 20 + ["JUSTICE STEVENS"] * 10
        mapping, _warnings = resolve_speakers(labels)

        assert mapping["CHIEF JUSTICE REHNQUIST"] == "CHIEF JUSTICE REHNQUIST"
        assert mapping["JUSTICE STEVENS"] == "JUSTICE STEVENS"

    def test_a_chief_who_is_the_only_form_is_not_changed(self):
        labels = ["CHIEF JUSTICE ROBERTS"] * 47
        mapping, _warnings = resolve_speakers(labels)
        assert mapping["CHIEF JUSTICE ROBERTS"] == "CHIEF JUSTICE ROBERTS"


class TestNearDuplicates:
    def test_a_likely_typo_is_reported(self):
        """Braidwood spells the same advocate MOOPPAN 88 times and MOOPAN twice."""
        labels = ["MR. MOOPPAN"] * 88 + ["MR. MOOPAN"] * 2
        _mapping, warnings = resolve_speakers(labels)

        assert any("MOOPAN" in warning and "MOOPPAN" in warning for warning in warnings)

    def test_a_likely_typo_is_not_merged(self):
        """Reported, not decided. The point of the module.

        In the 2010 Kasten transcript, MR. KASTEN and MR. KASTER differ by one
        letter and whether they are one person is a question about that argument,
        not about spelling. A rule that merges on similarity would answer it
        wrongly and silently.
        """
        labels = ["MR. KASTER"] * 38 + ["MR. KASTEN"] * 4
        mapping, _warnings = resolve_speakers(labels)

        assert mapping["MR. KASTEN"] == "MR. KASTEN"
        assert mapping["MR. KASTER"] == "MR. KASTER"

    def test_different_titles_are_never_compared(self):
        """MR. SMITH and JUSTICE SMITH are not plausible typos of each other."""
        assert find_near_duplicates(["MR. SMITH", "JUSTICE SMITH"]) == []

    def test_clearly_different_names_are_not_reported(self):
        assert find_near_duplicates(["MR. GREIM", "MR. MOOPPAN"]) == []

    def test_an_ordinary_transcript_produces_no_warnings(self):
        labels = (
            ["CHIEF JUSTICE ROBERTS"] * 47
            + ["JUSTICE KAGAN"] * 24
            + ["MS. NELSON"] * 73
        )
        _mapping, warnings = resolve_speakers(labels)
        assert warnings == []


class TestExplicitDecisions:
    def test_an_alias_overrides_everything_worked_out_automatically(self):
        """Once a person has looked and decided, the decision is applied."""
        labels = ["MR. KASTER"] * 38 + ["MR. KASTEN"] * 4
        mapping, _warnings = resolve_speakers(
            labels, aliases={"MR. KASTEN": "MR. KASTER"}
        )
        assert mapping["MR. KASTEN"] == "MR. KASTER"

    def test_an_alias_is_tidied_before_being_applied(self):
        labels = ["MR. KASTER"] * 5 + ["MR. KASTEN"]
        mapping, _warnings = resolve_speakers(
            labels, aliases={" mr. kasten ": "mr. kaster"}
        )
        assert mapping["MR. KASTEN"] == "MR. KASTER"


def test_every_label_gets_an_answer():
    """Nothing may fall through: a missing entry would drop a turn's speaker."""
    labels = ["JUSTICE KAGAN", "MR. GREIM", "QUESTION", "THE COURT"]
    mapping, _warnings = resolve_speakers(labels)
    assert set(mapping) == set(labels)

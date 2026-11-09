"""Tests for turning numbered lines into speaker turns.

Most of these are about defects found in the original `parse_transcript.py`, so
they are as much a record of what went wrong as a check that it stays fixed.
"""

from __future__ import annotations

import json

import pytest

from conftest import make_lines
from scotus_asr.corpus.manifest import load_cases
from scotus_asr.transcripts.parse import check_speaking_rate, parse_lines, parse_transcript


def test_a_label_starts_a_new_turn():
    lines = make_lines([
        "CHIEF JUSTICE ROBERTS: We'll hear argument first",
        "this morning in Case 24-109.",
        "MS. NELSON: Thank you, Mr. Chief Justice.",
    ])
    transcript = parse_lines(lines, docket="test")

    assert [t.speaker for t in transcript.turns] == ["CHIEF JUSTICE ROBERTS", "MS. NELSON"]
    assert transcript.turns[0].text == "We'll hear argument first this morning in Case 24-109."


def test_section_headings_are_not_spoken():
    """The printed heading must not become part of what the Chief Justice said.

    This is the defect that affected the first turn of every sample transcript.
    """
    lines = make_lines([
        "CHIEF JUSTICE ROBERTS: Ms. Nelson.",
        "ORAL ARGUMENT OF JANAI NELSON",
        "ON BEHALF OF APPELLANTS PRESS ROBINSON, ET AL.",
        "MS. NELSON: Thank you.",
    ])
    transcript = parse_lines(lines, docket="test")

    assert transcript.turns[0].text == "Ms. Nelson."
    assert "ORAL ARGUMENT" not in transcript.full_text()
    assert "PRESS ROBINSON" not in transcript.full_text()


def test_rebuttal_headings_are_also_dropped():
    lines = make_lines([
        "CHIEF JUSTICE ROBERTS: Mr. Greim, rebuttal?",
        "REBUTTAL ARGUMENT OF EDWARD D. GREIM",
        "ON BEHALF OF THE APPELLEES",
        "MR. GREIM: Thank you.",
    ])
    transcript = parse_lines(lines, docket="test")
    assert transcript.turns[0].text == "Mr. Greim, rebuttal?"
    assert len(transcript.turns) == 2


def test_parsing_stops_at_the_keyword_index():
    """Everything after the argument is an alphabetical index, not speech.

    Its lines also begin with digits, so without this the word count comes out
    roughly a sixth too high.
    """
    lines = make_lines([
        "MS. NELSON: I welcome your questions.",
        "(Whereupon, at 12:35 p.m., the case was submitted.)",
        "affirm [1] 83:8 acceptable [3] 35:19",
        "aimed [2] 31:8,9 addressed [1] 14:2",
    ])
    transcript = parse_lines(lines, docket="test")

    assert len(transcript.turns) == 1
    assert "affirm" not in transcript.full_text()
    assert transcript.index_started_on_page == 1


def test_a_recess_is_not_the_end_of_the_argument():
    """20-1530's record stopped at its recess on page 64 of 151."""
    lines = make_lines([
        "CHIEF JUSTICE ROBERTS: Why don't we take a five-minute break.",
        "(Whereupon, a brief recess was taken.)",
        "CHIEF JUSTICE ROBERTS: Mr. Hungar.",
        "(Whereupon, at 12:06 p.m., the case",
        "was submitted.)",
        "affirm [1] 83:8 acceptable [3] 35:19",
    ])
    transcript = parse_lines(lines, docket="test")

    assert len(transcript.turns) == 2
    assert transcript.turns[0].events[0].kind == "recess"
    assert transcript.turns[1].text == "Mr. Hungar."
    assert "affirm" not in transcript.full_text()


def test_stage_directions_are_kept_but_not_counted_as_speech():
    """`(Laughter.)` is recorded against the turn rather than thrown away.

    Whether a model reproduces these or silently tidies them is one of the things
    being measured, so they cannot be discarded at this stage.
    """
    lines = make_lines([
        "JUSTICE KAGAN: That is a bold position.",
        "(Laughter.)",
        "And yet here we are.",
    ])
    transcript = parse_lines(lines, docket="test")

    turn = transcript.turns[0]
    assert turn.text == "That is a bold position. And yet here we are."
    assert [e.text for e in turn.events] == ["(Laughter.)"]
    assert turn.events[0].kind == "laughter"
    assert turn.events[0].line == 2
    # Five words were spoken before it, so that is where it belongs. A line
    # number alone cannot place a notation inside a turn that resumes after it.
    assert turn.events[0].after_word == 5


def test_reference_json_written_before_events_had_pages_still_loads():
    """Every transcript on disk was written as `[line_number, text]` pairs.

    Rejecting that shape would mean every run's reference JSON had to be rebuilt
    before anything could read it. The missing fields stay at zero, which is
    honest: those files genuinely do not know the page or the word offset.
    """
    from scotus_asr.transcripts.model import Turn

    turn = Turn.from_dict({
        "speaker": "JUSTICE KAGAN",
        "text": "That is a bold position.",
        "events": [[23, "(Laughter.)"]],
    })

    assert len(turn.events) == 1
    assert turn.events[0].text == "(Laughter.)"
    assert turn.events[0].line == 23
    assert turn.events[0].kind == "laughter"
    assert turn.events[0].page == 0
    assert turn.events[0].after_word == 0


def test_an_event_survives_being_written_and_read_back():
    from scotus_asr.transcripts.model import Turn

    before = parse_lines(
        make_lines([
            "JUSTICE KAGAN: That is a bold position.",
            "(Laughter.)",
        ]),
        docket="test",
    ).turns[0]

    after = Turn.from_dict(before.to_dict())

    assert after.events == before.events


def test_a_notation_nobody_thought_of_is_still_a_notation():
    """The old rule was a four-word list, and only one of the four ever fired.

    Anything else the reporter wrote went into the text and was scored as
    speech. The rule is the shape of the line now, so an unfamiliar notation is
    recorded rather than counted as something somebody said.
    """
    lines = make_lines([
        "JUSTICE KAGAN: Let us take a short break.",
        "(Off the record.)",
        "We are back.",
    ])
    transcript = parse_lines(lines, docket="test")

    turn = transcript.turns[0]
    assert "Off the record" not in turn.text
    assert [e.text for e in turn.events] == ["(Off the record.)"]
    assert turn.events[0].kind == "other"


def test_a_statutory_citation_is_speech_and_stays_in_the_text():
    """`(b)` and `(2)` are read aloud. Widening the rule must not swallow them."""
    lines = make_lines([
        "MR. SMITH: The exception appears at subsection",
        "(b)",
        "and again at",
        "(2)",
    ])
    transcript = parse_lines(lines, docket="test")

    turn = transcript.turns[0]
    assert turn.events == []
    assert "(b)" in turn.text and "(2)" in turn.text


def test_a_brace_from_the_pdf_extractor_is_still_a_parenthesis():
    """PyMuPDF rendered one opening parenthesis as a brace, after which the
    stage direction was counted as two words somebody said."""
    lines = make_lines([
        "JUSTICE KAGAN: That is a bold position.",
        "{Laughter.)",
    ])
    transcript = parse_lines(lines, docket="test")

    assert "Laughter" not in transcript.turns[0].text
    assert transcript.turns[0].events[0].kind == "laughter"


def test_the_closing_notation_is_recorded_rather_than_only_stopping_the_parse():
    """Until now only its page survived - the words appeared nowhere at all."""
    lines = make_lines([
        "JUSTICE KAGAN: We will hear argument.",
        "MR. SMITH: Thank you, Your Honor.",
        "(Whereupon the case was submitted.)",
    ])
    transcript = parse_lines(lines, docket="test")

    closing = [e for turn in transcript.turns for e in turn.events if e.kind == "end"]
    assert len(closing) == 1
    assert "submitted" in closing[0].text
    # It still ends the parse, which is what keeps the keyword index out.
    assert transcript.index_started_on_page == 1


def test_nothing_before_the_first_speaker_is_counted():
    """The cover page, the contents and the appearance list are not speech."""
    lines = make_lines([
        "IN THE SUPREME COURT OF THE UNITED STATES",
        "PETITIONER, v. RESPONDENT",
        "APPEARANCES:",
        "JUSTICE THOMAS: Counsel?",
    ])
    transcript = parse_lines(lines, docket="test")

    assert len(transcript.turns) == 1
    assert transcript.full_text() == "Counsel?"


def test_accented_surnames_are_recognised():
    """Louisiana's Solicitor General is Aguinaga, spelled with an N-tilde.

    An A-Z-only pattern silently loses all 48 of his turns, which is what
    happened before this was fixed.
    """
    lines = make_lines([
        "GENERAL AGUIÑAGA: Mr. Chief Justice, and may it please the Court.",
        "The district court erred.",
    ])
    transcript = parse_lines(lines, docket="test")

    assert len(transcript.turns) == 1
    assert transcript.turns[0].speaker == "GENERAL AGUIÑAGA"


def test_a_mid_sentence_colon_does_not_start_a_turn():
    lines = make_lines([
        "MS. NELSON: The statute says: no person shall be denied.",
        "It said: that is enough.",
    ])
    transcript = parse_lines(lines, docket="test")

    assert len(transcript.turns) == 1


def test_where_each_turn_sits_is_recorded():
    """Provenance is what turns a score into evidence you can go and check."""
    lines = [
        *make_lines(["JUSTICE ALITO: A question spanning"], page=12, start=23),
        *make_lines(["two pages of the transcript."], page=13, start=1),
    ]
    transcript = parse_lines(lines, docket="test")

    turn = transcript.turns[0]
    assert (turn.start_page, turn.start_line) == (12, 23)
    assert (turn.end_page, turn.end_line) == (13, 1)


def test_full_text_can_include_or_exclude_speakers():
    lines = make_lines([
        "JUSTICE KAGAN: Why?",
        "MR. GREIM: Because.",
    ])
    transcript = parse_lines(lines, docket="test")

    assert transcript.full_text() == "Why? Because."
    assert "JUSTICE KAGAN:" in transcript.full_text(include_speakers=True)


class TestSpeakingRate:
    """The check that catches audio paired with the wrong transcript."""

    def test_a_normal_rate_passes(self):
        rate, ok = check_speaking_rate(word_count=9891, audio_minutes=55.9)
        assert ok
        assert 165 <= rate <= 197

    def test_too_few_words_for_the_length_fails(self):
        _rate, ok = check_speaking_rate(word_count=2000, audio_minutes=55.9)
        assert not ok

    def test_counting_the_index_as_speech_shows_up(self):
        """A sixth too many words pushes the rate above the plausible band."""
        _rate, ok = check_speaking_rate(word_count=int(9891 * 1.17), audio_minutes=55.9)
        assert not ok

    def test_zero_length_audio_does_not_divide_by_zero(self):
        rate, ok = check_speaking_rate(word_count=100, audio_minutes=0)
        assert rate == 0.0
        assert not ok


@pytest.mark.needs_data
class TestAgainstTheRealTranscripts:
    """The regression check: the six verified cases must not drift."""

    def test_turn_counts_match_the_verified_sample(self, manifest_path, sample_dir):
        """Turn counts were established by hand when the sample was built."""
        for case in load_cases(manifest_path, sample_dir):
            if not case.transcript_pdf.exists():
                pytest.skip(f"{case.transcript_pdf.name} is not present.")
            transcript = parse_transcript(case.transcript_pdf, case.docket)
            assert len(transcript.turns) == case.expected_turns, (
                f"{case.docket}: got {len(transcript.turns)} turns, "
                f"expected {case.expected_turns}"
            )

    def test_word_counts_are_close_to_the_verified_sample(self, manifest_path, sample_dir):
        """Within 1%.

        Not exact, and deliberately so. This parser drops the printed
        `ORAL ARGUMENT OF ...` headings that the original wrongly counted as
        speech, and recovers a few lines the original lost, so the totals differ
        by a few dozen words. A gap of more than 1% would mean something else
        changed.
        """
        for case in load_cases(manifest_path, sample_dir):
            if not case.transcript_pdf.exists():
                pytest.skip(f"{case.transcript_pdf.name} is not present.")
            transcript = parse_transcript(case.transcript_pdf, case.docket)
            expected = case.expected_words or 0
            drift = abs(transcript.word_count - expected) / expected
            assert drift < 0.01, (
                f"{case.docket}: {transcript.word_count} words against "
                f"{expected} expected, a {drift:.1%} difference"
            )

    def test_the_index_is_always_found(self, manifest_path, sample_dir):
        """Failing to find it silently inflates the word count."""
        for case in load_cases(manifest_path, sample_dir):
            if not case.transcript_pdf.exists():
                pytest.skip(f"{case.transcript_pdf.name} is not present.")
            transcript = parse_transcript(case.transcript_pdf, case.docket)
            assert transcript.index_started_on_page is not None, case.docket

    def test_the_accented_surname_survives_a_real_parse(self, manifest_path, sample_dir):
        """Callais has an advocate whose name the old pipeline mangled.

        `pdftotext` dropped the N-tilde, so the old transcript_turns.json (now in tools/archive/)
        records him as MR. AGUIAGA. Reading the PDF directly keeps it.
        """
        cases = {c.docket: c for c in load_cases(manifest_path, sample_dir)}
        callais = cases.get("24-109")
        if callais is None or not callais.transcript_pdf.exists():
            pytest.skip("Callais is not present.")

        transcript = parse_transcript(callais.transcript_pdf, "24-109")
        assert any("AGUIÑAGA" in speaker for speaker in transcript.speakers)

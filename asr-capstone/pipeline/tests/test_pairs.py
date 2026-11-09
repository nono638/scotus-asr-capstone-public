"""Tests for the word-by-word comparison.

The point of this table is that a difference can be traced back to a speaker, a
page and a moment in the audio. If that mapping slips by one turn the file still
looks perfectly reasonable and quietly attributes words to the wrong justice, so
the positions matter more here than the counts do.
"""

from __future__ import annotations

import csv

from scotus_asr.asr.base import Word
from scotus_asr.scoring.align import align_words
from scotus_asr.scoring.pairs import word_pairs, write_pairs
from scotus_asr.transcripts.model import Transcript, Turn


def _words(text: str, start: float = 0.0) -> list[Word]:
    """A machine transcription with one second per word."""
    return [
        Word(text=word, start=start + i, end=start + i + 1, probability=0.9)
        for i, word in enumerate(text.split())
    ]


def _transcript() -> Transcript:
    """Two speakers, so a mis-mapped position shows up as the wrong name."""
    return Transcript(
        docket="00-001",
        turns=[
            Turn(speaker="CHIEF JUSTICE ROBERTS", text="we will hear argument now",
                 start_page=3, start_line=3),
            Turn(speaker="MR. SMITH", text="thank you your honor",
                 start_page=4, start_line=11),
        ],
    )


def test_a_perfect_transcription_is_one_matching_stretch():
    rows = word_pairs(
        _transcript(),
        _words("we will hear argument now thank you your honor"),
        docket="00-001",
        engine="test",
    )

    assert [row.kind for row in rows] == ["equal"]
    assert rows[0].reference_words == 9


def test_a_difference_carries_the_speaker_page_and_line_it_came_from():
    """The second turn's words must not be attributed to the first speaker."""
    rows = word_pairs(
        _transcript(),
        _words("we will hear argument now thank you your lordship"),
        docket="00-001",
        engine="test",
    )

    changed = [row for row in rows if row.kind == "substitute"]
    assert len(changed) == 1
    assert changed[0].reference_text == "honor"
    assert changed[0].asr_text == "lordship"
    assert changed[0].speaker == "MR. SMITH"
    assert changed[0].page == 4
    assert changed[0].line == 11


def test_a_dropped_run_borrows_the_time_of_the_next_word_produced():
    """A deletion has no time of its own, and a blank time cannot be listened to."""
    rows = word_pairs(
        _transcript(),
        _words("we will hear argument now thank you"),
        docket="00-001",
        engine="test",
    )

    dropped = [row for row in rows if row.kind == "delete"]
    assert len(dropped) == 1
    assert dropped[0].reference_text == "your honor"
    assert dropped[0].asr_text == ""
    # Nothing follows the drop here, so there is no later word to borrow from.
    assert dropped[0].start_seconds is None


def test_words_the_machine_invented_are_marked_as_insertions():
    rows = word_pairs(
        _transcript(),
        _words("we will hear oral argument now thank you your honor"),
        docket="00-001",
        engine="test",
    )

    added = [row for row in rows if row.kind == "insert"]
    assert len(added) == 1
    assert added[0].asr_text == "oral"
    assert added[0].reference_text == ""


def test_the_chunk_totals_add_back_up_to_the_scores():
    """The table must not disagree with the numbers already published from it."""
    transcript = _transcript()
    spoken = transcript.full_text().split()
    heard = _words("we will hear oral argument now thanks you your lordship")

    alignment = align_words(spoken, [w.text for w in heard], normalizer="verbatim")
    rows = word_pairs(transcript, heard, docket="00-001", engine="test",
                      normalizer="verbatim", alignment=alignment)

    counted = {
        "substitute": sum(r.reference_words for r in rows if r.kind == "substitute"),
        "delete": sum(r.reference_words for r in rows if r.kind == "delete"),
        "insert": sum(r.asr_words for r in rows if r.kind == "insert"),
    }
    assert counted["substitute"] == alignment.substitutions
    assert counted["delete"] == alignment.deletions
    assert counted["insert"] == alignment.insertions


def test_writing_it_out_keeps_every_column(tmp_path):
    rows = word_pairs(
        _transcript(),
        _words("we will hear argument now thank you your lordship"),
        docket="00-001",
        engine="test",
    )
    path = tmp_path / "pairs.csv"

    assert write_pairs(rows, path) == len(rows)

    written = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(written) == len(rows)
    assert written[0]["docket"] == "00-001"
    assert "confidence" in written[0]

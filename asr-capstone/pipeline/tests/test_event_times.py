"""Tests for placing a reporter's notation at a moment in the audio.

A notation sits at a position on the page; a silence sits at a moment in the
recording. Only the machine transcription carries times, so the notation has to
be routed through it, and every step of that route can fail quietly.

The point of placing them is to stop charging a model for silence it was right
about. Where the reporter wrote `(Laughter.)` there is a sound but no speech, and
a model that writes nothing there is behaving correctly.
"""

from __future__ import annotations

from scotus_asr.asr.base import Word
from scotus_asr.scoring.pairs import event_times
from scotus_asr.transcripts.model import Event, Transcript, Turn


def _words(text: str, start: float = 0.0, each: float = 1.0) -> list[Word]:
    """One machine word per second, so a time is easy to reason about."""
    return [
        Word(text=f" {word}", start=start + i * each, end=start + (i + 1) * each)
        for i, word in enumerate(text.split())
    ]


def _transcript(events_after: int) -> Transcript:
    """Two turns, with a notation placed inside the first."""
    return Transcript(
        docket="00-001",
        turns=[
            Turn(
                speaker="JUSTICE KAGAN",
                text="that is a bold position and yet here we are",
                events=[Event(text="(Laughter.)", line=5, after_word=events_after,
                              kind="laughter")],
            ),
            Turn(speaker="MR. SMITH", text="we would say otherwise"),
        ],
    )


def test_a_notation_lands_near_the_words_it_follows():
    """Five words in, at a word a second, is about five seconds in."""
    transcript = _transcript(events_after=5)
    heard = _words("that is a bold position and yet here we are we would say otherwise")

    placed = event_times(transcript, heard)

    assert len(placed) == 1
    event, when = placed[0]
    assert event.kind == "laughter"
    assert 4.0 <= when <= 6.0


def test_moving_the_notation_later_moves_its_time_later():
    heard = _words("that is a bold position and yet here we are we would say otherwise")

    early = event_times(_transcript(events_after=1), heard)[0][1]
    late = event_times(_transcript(events_after=9), heard)[0][1]

    assert late > early


def test_a_transcript_with_no_notations_places_nothing():
    plain = Transcript(
        docket="00-001",
        turns=[Turn(speaker="JUSTICE KAGAN", text="that is a bold position")],
    )

    assert event_times(plain, _words("that is a bold position")) == []


def test_nothing_is_placed_when_the_machine_produced_nothing():
    """No times to route through, so no guess is offered."""
    assert event_times(_transcript(events_after=5), []) == []


def test_a_notation_after_a_stretch_the_model_missed_still_gets_placed():
    """The alignment has no machine word against a deleted stretch, so the
    lookup walks forward to the next word it does have rather than giving up."""
    transcript = _transcript(events_after=5)
    # The middle of the turn is missing from what the machine produced.
    heard = _words("that is a bold we would say otherwise")

    placed = event_times(transcript, heard)

    assert len(placed) == 1
    assert placed[0][1] >= 0.0


def test_placements_come_back_in_order():
    transcript = Transcript(
        docket="00-001",
        turns=[
            Turn(speaker="A", text="one two three four five",
                 events=[Event(text="(Laughter.)", after_word=4, kind="laughter")]),
            Turn(speaker="B", text="six seven eight nine ten",
                 events=[Event(text="(Laughter.)", after_word=1, kind="laughter")]),
        ],
    )
    heard = _words("one two three four five six seven eight nine ten")

    placed = event_times(transcript, heard)

    assert len(placed) == 2
    assert placed[0][1] <= placed[1][1]

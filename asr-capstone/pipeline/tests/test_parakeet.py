"""Tests for the Parakeet engine's pieces of real logic.

None needs a GPU or a model. All decide whether words survive, which is the
thing this project measures, so an error in any would show up as the model
dropping speech when it was the harness that dropped it - or, for the gap
re-read, as the harness hiding a drop the model made.
"""

from __future__ import annotations

from scotus_asr.asr.base import Segment, Word
from scotus_asr.asr.parakeet_engine import (
    CHUNK_SECONDS,
    OVERLAP_SECONDS,
    ParakeetEngine,
    _place,
    _to_words,
    fill_gaps,
    frame_step,
    keep_window,
)
from scotus_asr.config import AsrSettings


def _steps(pieces, cap=10):
    """Run frame_step over a list of (blank, duration) steps; the frames moved."""
    import torch

    held, moved = torch.zeros(1, dtype=torch.long), []
    for blank, duration in pieces:
        step, held = frame_step(torch.tensor([blank]), torch.tensor([duration]), held, cap)
        moved.append(int(step))
    return moved


def test_a_piece_stuck_on_one_frame_is_moved_on_after_ten():
    # 18-1323: the same frame, piece after piece, duration zero every time.
    moved = _steps([(False, 0)] * 25)
    assert moved == ([0] * 9 + [1]) * 2 + [0] * 5


def test_ordinary_steps_are_left_alone():
    steps = [(False, 2), (False, 0), (False, 1), (True, 3), (False, 0), (False, 4)]
    assert _steps(steps) == [2, 0, 1, 3, 0, 4]


def test_a_blank_always_moves_on_at_least_one_frame():
    assert _steps([(True, 0)]) == [1]


def test_moving_on_starts_the_count_again():
    # Nine on one frame, a move, then nine more: no piece is forced.
    steps = [(False, 0)] * 9 + [(False, 1)] + [(False, 0)] * 9
    assert _steps(steps) == [0] * 9 + [1] + [0] * 9


def test_sub_word_pieces_are_joined_into_words():
    """Parakeet emits `sol` then `d`; the pipeline expects `sold`.

    A new word is the piece that starts with a space.
    """
    tokens = [
        {"token": "Or", "start": 0.56, "end": 0.72},
        {"token": " that", "start": 0.72, "end": 0.96},
        {"token": " sol", "start": 1.28, "end": 1.52},
        {"token": "d", "start": 1.52, "end": 1.68},
    ]

    words = _to_words(tokens, offset=0.0)

    assert [w.text for w in words] == ["Or", " that", " sold"]
    # The joined word runs from the first piece to the last.
    assert words[-1].start == 1.28
    assert words[-1].end == 1.68


def test_word_times_are_shifted_to_their_place_in_the_recording():
    """Timestamps come back relative to the chunk, not the recording."""
    tokens = [{"token": " word", "start": 5.0, "end": 5.4}]

    words = _to_words(tokens, offset=600.0)

    assert words[0].start == 605.0
    assert words[0].end == 605.4


def test_empty_pieces_are_skipped_without_breaking_the_word_being_built():
    words = _to_words(
        [
            {"token": " par", "start": 1.0, "end": 1.2},
            {"token": "", "start": 1.2, "end": 1.2},
            {"token": "ty", "start": 1.2, "end": 1.4},
        ],
        offset=0.0,
    )

    assert [w.text for w in words] == [" party"]


def test_the_first_chunk_keeps_everything_up_to_the_shared_midpoint():
    """Nothing precedes the first chunk, so its start must not be trimmed."""
    keep_from, keep_until = keep_window(offset=0.0, index=0, total_seconds=3600.0)

    assert keep_from == 0.0
    assert keep_until == CHUNK_SECONDS - OVERLAP_SECONDS / 2


def test_the_last_chunk_keeps_everything_to_the_end():
    """Nothing follows it, so trimming its tail would drop real speech."""
    offset = 1200.0
    keep_from, keep_until = keep_window(offset, index=2, total_seconds=1500.0)

    assert keep_from == offset + OVERLAP_SECONDS / 2
    assert keep_until >= 1500.0


def test_neighbouring_chunks_meet_exactly_once():
    """The seam is a point, not a gap and not an overlap.

    Where one chunk stops keeping words is exactly where the next starts, so a
    word is kept once however its timestamp falls.
    """
    step = CHUNK_SECONDS - OVERLAP_SECONDS
    total = 4000.0

    _, first_until = keep_window(0.0, 0, total)
    second_from, _ = keep_window(step, 1, total)

    assert first_until == second_from


def test_every_second_of_a_long_recording_is_covered_exactly_once():
    """Walk the whole thing and check the windows tile it without holes."""
    total = 3000.0
    step = CHUNK_SECONDS - OVERLAP_SECONDS

    windows = []
    offset, index = 0.0, 0
    while offset < total:
        windows.append(keep_window(offset, index, total))
        offset += step
        index += 1

    assert windows[0][0] == 0.0
    assert windows[-1][1] >= total
    for (_, ends), (starts, _) in zip(windows, windows[1:]):
        assert ends == starts, "a gap or an overlap between chunks"


def test_the_keep_window_follows_a_chunk_length_changed_at_run_time(monkeypatch):
    """A chunk-length test changes CHUNK_SECONDS after import.

    The window used to take it as a default argument, which is fixed when the
    module loads, so it went on trimming at 300 seconds while the chunks were cut
    at the new length - and nothing said so.
    """
    from scotus_asr.asr import parakeet_engine

    monkeypatch.setattr(parakeet_engine, "CHUNK_SECONDS", 120.0)

    _, keep_until = parakeet_engine.keep_window(0.0, 0, 3600.0)

    assert keep_until == 120.0 - OVERLAP_SECONDS / 2


# The full-stop stall: every blank stretch is decoded again on its own. These use
# a fake decoder that "hears" a word every second wherever it is asked to look,
# so they need no model.

def _word(text, start):
    return Word(f" {text}", start, start + 0.5)


def _fake_decoder(heard_every=1.0, calls=None):
    def decode(start, end):
        if calls is not None:
            calls.append((start, end))
        t, words = start, []
        while t < end:
            words.append(_word("w", t))
            t += heard_every
        return words
    return decode


def test_a_blank_stretch_of_four_seconds_or_more_is_read_again():
    words = [_word("Online", 10.0), _word("grow.", 11.0), _word("And", 30.0)]
    calls = []

    added = fill_gaps(_fake_decoder(calls=calls), words, 10.0, 30.5)

    assert calls[0] == (11.5, 30.0), "the gap is from one word's end to the next's start"
    assert added and all(11.5 <= w.start < 30.0 for w in added)


def test_a_short_pause_is_left_alone():
    words = [_word("a", 0.0), _word("b", 3.0)]  # 2.5 s between them
    calls = []

    assert fill_gaps(_fake_decoder(calls=calls), words, 0.0, 3.5) == []
    assert calls == []


def test_the_start_and_end_of_the_recording_are_read_again_too():
    """A stall can begin before the first word or run past the last."""
    calls = []

    fill_gaps(_fake_decoder(calls=calls), [_word("middle", 20.0)], 0.0, 40.0)

    assert (0.0, 20.0) in calls and (20.5, 40.0) in calls


def test_words_a_re_read_puts_outside_its_stretch_are_not_kept():
    """A re-read must only fill its own gap, never double a word beside it."""
    def decode(start, end):
        return [_word("before", start - 1), _word("inside", start + 1), _word("after", end)]

    # One 4.5 s gap; what is left after "inside" is too short to read again.
    added = fill_gaps(decode, [_word("a", 0.0), _word("b", 5.0)], 0.0, 5.5)

    assert [w.text for w in added] == [" inside"]


def test_a_gap_inside_a_re_read_is_read_again_three_levels_deep_at_most():
    """Each re-read here stalls straight away, leaving a gap inside the gap."""
    calls = []

    def decode(start, end):
        calls.append((start, end))
        return [_word("first", start)]  # one word, then nothing

    fill_gaps(decode, [_word("a", 0.0), _word("b", 100.0)], 0.0, 100.5)

    assert len(calls) == 3


def test_a_re_read_that_finds_nothing_is_not_tried_again():
    """Same audio, same decoder, same answer: a second try only costs time."""
    calls = []

    fill_gaps(lambda s, e: calls.append((s, e)) or [], [_word("a", 0.0), _word("b", 60.0)], 0.0, 60.5)

    assert calls == [(0.5, 60.0)]


def test_restored_words_go_into_the_chunk_they_fall_in():
    """One segment per chunk, as the seam clean-up expects."""
    segments = [
        Segment(0, 0.0, 290.0, "x", [_word("one.", 0.0), _word("two", 289.5)]),
        Segment(1, 296.0, 590.0, "y", [_word("three", 296.0), _word("four", 589.5)]),
    ]

    _place(segments, [_word("lost", 150.0), _word("found", 400.0)])

    assert [w.text for w in segments[0].words] == [" one.", " lost", " two"]
    assert [w.text for w in segments[1].words] == [" three", " found", " four"]
    assert segments[0].text == "one. lost two"


def test_the_engine_restores_words_with_a_space_before_the_first():
    """A decode's first word has no leading space; joined, it read "grow.uh"."""
    import numpy as np

    engine = ParakeetEngine(AsrSettings(engine="parakeet", model="parakeet-tdt-0.6b-v3"))
    engine._decode_piece = lambda piece, offset: [Word("uh", offset, offset + 0.3),
                                                  Word(" the", offset + 0.5, offset + 0.8)]
    # 5 s long: one 4.5 s gap, and what the re-read leaves (3.7 s) is too short to read again.
    segments = [Segment(0, 0.0, 5.0, "grow.", [_word("grow.", 0.0)])]

    restored = engine.reread_gaps(np.zeros(5 * 16_000, dtype=np.float32), segments, 5.0)

    assert restored == 2
    assert segments[0].text == "grow. uh the"
    assert engine.words_restored == 2 and engine.gap_rereads >= 1

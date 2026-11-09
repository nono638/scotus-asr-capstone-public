"""Tests for the forced aligner shared by the engines that produce no timings.

Nothing here loads the real model - a fake stands in for it, returning the shape
the real one returns: one entry per word, punctuation stripped, capitals kept.

That stripping is what these tests are about. Two of the four models in the study
have no timings of their own and are routed through here, and if their
punctuation is lost on the way they are scored as though they never wrote any.
The strictest of the three scoring rules counts punctuation as part of the
record, so the loss does not look like a bug in this file. It looks like those
models tidying away the record, which is the project's central claim - arrived at
by accident.
"""

from __future__ import annotations

from scotus_asr.asr.aligner import ForcedAligner


class _FakeProcessor:
    """Stands in for the aligner's processor, stripping marks as the real one does."""

    def __init__(self, drop: int = 0) -> None:
        #: How many words to lose, to test the mismatch path.
        self.drop = drop
        self.seen: list[str] = []

    def prepare_forced_aligner_inputs(self, audio, transcript, language, return_tensors):
        self.seen.append(transcript)
        return _FakeInputs(), [transcript.split()]

    def decode_forced_alignment(self, logits, input_ids, word_lists, timestamp_token_id):
        bare = [
            "".join(c for c in word if c.isalnum() or c == "'")
            for word in word_lists[0]
        ]
        if self.drop:
            bare = bare[: -self.drop]
        return [
            [{"text": word, "start_time": i * 0.5, "end_time": i * 0.5 + 0.4}
             for i, word in enumerate(bare)]
        ]


class _FakeInputs(dict):
    """The real processor returns a BatchFeature; only these two bits are used."""

    def __init__(self) -> None:
        super().__init__(input_ids=[[1, 2, 3]])

    def to(self, device, dtype=None):
        return self


class _FakeLogits:
    logits = None


class _FakeModel:
    class config:
        timestamp_token_id = 7

    def __call__(self, **kwargs):
        return _FakeLogits()


def _aligner(drop: int = 0) -> ForcedAligner:
    """An aligner with the model already in place, so `load` does nothing."""
    made = ForcedAligner(device="cpu", compute_type="float32")
    made._processor = _FakeProcessor(drop=drop)
    made._model = _FakeModel()
    return made


SPOKEN = "Mr. Chief Justice, and may it please the Court: this is it."


def test_the_punctuation_survives_alignment():
    """The whole point. The aligner returns `Mr`; the record says `Mr.`"""
    words = _aligner().align([], SPOKEN)

    assert "".join(w.text for w in words).strip() == SPOKEN


def test_every_word_of_the_text_comes_back():
    words = _aligner().align([], SPOKEN)

    assert len(words) == len(SPOKEN.split())


def test_the_words_carry_the_aligners_times_not_the_texts_order():
    """The text supplies the spelling; the aligner supplies the seconds."""
    words = _aligner().align([], SPOKEN)

    assert words[0].start == 0.0
    assert words[1].start == 0.5
    assert all(later.start > earlier.start
               for earlier, later in zip(words, words[1:]))


def test_an_offset_moves_the_words_onto_the_recordings_clock():
    """A chunk is aligned against itself and has to be placed in the whole."""
    words = _aligner().align([], SPOKEN, offset=120.0)

    assert words[0].start == 120.0


def test_a_leading_space_matches_what_the_other_engines_produce():
    """So scoring sees one shape of word list whatever model made it."""
    words = _aligner().align([], SPOKEN)

    assert all(w.text.startswith(" ") for w in words)


def test_empty_text_places_nothing():
    assert _aligner().align([], "   ") == []


def test_a_count_mismatch_keeps_the_words_without_misdating_them():
    """Pairing a short list against a long one would misdate words, and the times are
    what the silence measure is built on. So the two are lined up by their letters: each
    word the aligner returned keeps its own time, and the punctuation stays."""
    full = _aligner().align([], SPOKEN)
    words = _aligner(drop=2).align([], SPOKEN)

    assert [w.text for w in words] == [w.text for w in full]
    kept = len(SPOKEN.split()) - 2
    assert [w.start for w in words[:kept]] == [w.start for w in full[:kept]]
    assert "," in "".join(w.text for w in words)


def test_the_repository_is_reported_for_the_run_record():
    assert "ForcedAligner" in _aligner().repo_id


def test_aligner_precision_follows_the_old_rule_unless_set():
    """Unset, it reproduces the published runs: float16 engines got a float16
    aligner, everything else float32."""
    from scotus_asr.asr.aligner import aligner_compute_type
    from scotus_asr.config import AsrSettings

    assert aligner_compute_type(AsrSettings(compute_type="float16")) == "float16"
    assert aligner_compute_type(AsrSettings(compute_type="bfloat16")) == "float32"
    pinned = AsrSettings(compute_type="float16",
                         engine_options={"aligner_compute_type": "float32"})
    assert aligner_compute_type(pinned) == "float32"


def _stamped(*words):
    return [{"text": w, "start_time": float(i), "end_time": i + 0.5} for i, w in enumerate(words)]


def test_a_token_of_marks_alone_keeps_the_chunks_punctuation():
    from scotus_asr.asr.aligner import with_marks

    got = with_marks("Well, I -- I think so.", _stamped("Well", "I", "I", "think", "so"))
    assert [g[0] for g in got] == ["Well,", "I", "--", "I", "think", "so."]
    assert got[2][1:] == (1.5, 1.5)   # the dash sits where the word before it ended
    assert got[3][1:] == (2.0, 2.5)   # and the next word keeps its own time


def test_marks_first_take_the_first_words_time():
    from scotus_asr.asr.aligner import with_marks

    got = with_marks("-- Yes.", _stamped("Yes"))
    assert got[0] == ("--", 0.0, 0.0) and got[1] == ("Yes.", 0.0, 0.5)


def test_counts_that_differ_line_up_by_letters():
    from scotus_asr.asr.aligner import with_marks

    # The aligner splits one token in two: the words either side keep their own times.
    got = with_marks("One, ice-cream two.", _stamped("One", "ice", "cream", "two"))
    assert [g[0] for g in got] == ["One,", "ice-cream", "two."]
    assert got[0][1] == 0.0 and got[2][1] == 3.0


def test_nothing_in_common_keeps_the_aligners_words():
    from scotus_asr.asr.aligner import with_marks

    assert [g[0] for g in with_marks("--", _stamped("a"))] == ["a"]

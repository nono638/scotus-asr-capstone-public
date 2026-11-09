"""Separating the margin line number from the words on a row."""

from scotus_asr.transcripts.extract import _group_into_rows, _join_lifted_numbers, _split_line_number


def test_a_number_in_its_own_piece_is_the_line_number():
    number, _left, text = _split_line_number([(119.0, "1   "), (154.0, "of this law is")])
    assert number == 1
    assert text == "of this law is"


def test_a_number_laid_out_with_spaces_in_the_same_piece():
    """24-993's layout: number and words arrive as one piece."""
    row = [(29.0, "             1             JUSTICE THOMAS:  Mr. Ho.")]
    number, _left, text = _split_line_number(row)
    assert number == 1
    assert text == "JUSTICE THOMAS: Mr. Ho."


def test_a_blank_numbered_line_in_that_layout_has_no_words():
    number, _left, text = _split_line_number([(29.0, "            25   ")])
    assert number == 25
    assert text == ""


def test_a_lone_dash_in_that_layout_stays_dropped_as_it_always_was():
    """Keeping it would change OT2017 records the published results used."""
    number, _left, _text = _split_line_number([(29.0, "            12   --")])
    assert number is None


def test_a_sentence_that_starts_with_a_number_is_not_a_line_number():
    number, _left, text = _split_line_number([(150.0, "5 percent of the cases")])
    assert number is None
    assert text == "5 percent of the cases"


def test_a_number_lifted_just_above_its_words_is_joined_to_them():
    """12-872's layout: each number sits 3.4 points above the words beside it."""
    pieces = [(88.53, 104.3, "2 "), (91.92, 133.0, "question. Everybody agrees"),
              (114.21, 104.3, "3 "), (117.60, 133.0, "immunity, that there")]
    rows = _join_lifted_numbers(_group_into_rows(pieces))
    assert [_split_line_number(row)[:3:2] for row in rows] == [
        (2, "question. Everybody agrees"), (3, "immunity, that there")]


def test_a_blank_numbered_line_is_not_joined_to_the_next_line():
    """The next numbered line is a whole line (about 26 points) further down."""
    pieces = [(88.0, 104.3, "2 "), (114.0, 104.3, "3 "), (114.0, 133.0, "the words")]
    rows = _join_lifted_numbers(_group_into_rows(pieces))
    assert [_split_line_number(row)[:3:2] for row in rows] == [(2, ""), (3, "the words")]

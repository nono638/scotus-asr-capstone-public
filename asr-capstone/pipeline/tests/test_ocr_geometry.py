"""Tests for reading a scanned page's structure from where the words sit.

These test the decision the OCR design rests on: line numbers are assigned by
counting down the margin, never by reading the digit. The tests below are mostly
about what happens when the digit is unreadable, because that is the case the
design exists for.
"""

from __future__ import annotations

from scotus_asr.ocr.geometry import (
    TextBox,
    find_gutter,
    read_geometry,
    words_for_line,
)

#: A 1969 transcript page, rendered at 150 dots per inch.
PAGE_WIDTH = 1190.0

#: Lines sit about 60 pixels apart at that resolution.
LINE_SPACING = 60.0


def page_boxes(numbers, body_text="some words here", first_y=100.0):
    """Build a page of boxes: a margin number and a line of words for each entry.

    Args:
        numbers: What the OCR read in the margin, one per line. Use "" for a
            number it could not read at all.
        body_text: Words to put beside each number.
        first_y: Top of the first line.
    """
    boxes = []
    for index, printed in enumerate(numbers):
        top = first_y + index * LINE_SPACING
        boxes.append(TextBox(text=printed, x0=90, y0=top, x1=120, y1=top + 30))
        boxes.append(
            TextBox(text=body_text, x0=170, y0=top, x1=900, y1=top + 30)
        )
    return boxes


class TestFindingTheMargin:
    def test_the_leftmost_short_boxes_are_the_margin(self):
        boxes = page_boxes(["1", "2", "3"])
        gutter, body = find_gutter(boxes, PAGE_WIDTH)

        assert len(gutter) == 3
        assert len(body) == 3

    def test_the_margin_comes_back_top_to_bottom(self):
        """Order is the whole mechanism, so it cannot be left to chance."""
        boxes = page_boxes(["1", "2", "3"])
        gutter, _ = find_gutter(list(reversed(boxes)), PAGE_WIDTH)

        assert [box.y0 for box in gutter] == sorted(box.y0 for box in gutter)

    def test_a_long_word_in_the_margin_is_not_a_line_number(self):
        """The reporter's footer sits at the left edge too."""
        boxes = page_boxes([str(n) for n in range(1, 26)])
        boxes.append(TextBox(text="ALDERSON", x0=95, y0=1700, x1=300, y1=1730))

        gutter, _ = find_gutter(boxes, PAGE_WIDTH)
        assert len(gutter) == 25

    def test_a_short_word_out_in_the_page_is_not_a_line_number(self):
        """A page reference in the body looks exactly like a line number."""
        boxes = page_boxes([str(n) for n in range(1, 26)])
        boxes.append(TextBox(text="14", x0=600, y0=1700, x1=630, y1=1730))

        gutter, _ = find_gutter(boxes, PAGE_WIDTH)
        assert len(gutter) == 25

    def test_a_handful_of_short_words_is_not_a_column(self):
        """A cover page has no numbered lines and must say so.

        Without this, the leftmost few short words on a title page would be
        reported as a margin, and the page would appear to have line numbers it
        does not have.
        """
        boxes = [
            TextBox(text="IN", x0=90, y0=400, x1=120, y1=430),
            TextBox(text="OF", x0=92, y0=500, x1=122, y1=530),
        ]
        gutter, body = find_gutter(boxes, PAGE_WIDTH)

        assert gutter == []
        assert len(body) == 2

    def test_a_number_split_into_two_pieces_is_one_line(self):
        """The 1969 scan reads 11 as two boxes, "i" and "f", side by side.

        Counted as two lines, every line below would be numbered one too high.
        """
        boxes = page_boxes([str(n) for n in range(1, 26)])
        # Replace the box for 11 with the two pieces the scan actually produces.
        boxes = [b for b in boxes if not (b.x0 == 90 and b.text == "11")]
        y = 100.0 + 10 * LINE_SPACING
        boxes.append(TextBox(text="i", x0=88, y0=y, x1=100, y1=y + 30))
        boxes.append(TextBox(text="f", x0=104, y0=y + 1, x1=118, y1=y + 31))

        gutter, _ = find_gutter(boxes, PAGE_WIDTH)
        assert len(gutter) == 25


class TestNumberingByPosition:
    def test_line_numbers_come_from_position(self):
        geometry = read_geometry(page_boxes([str(n) for n in range(1, 26)]),
                                 page=6, page_width=PAGE_WIDTH)

        assert geometry.line_count == 25
        assert [line.rank for line in geometry.lines] == list(range(1, 26))
        assert geometry.disagreements == 0

    def test_misread_digits_do_not_change_the_numbering(self):
        """The real misreads from the 1969 scan: z for 2, 0 for 6, IS for 15.

        This is the case the whole design exists for. The digits are wrong and
        the line numbers still come out right, because the digits were never
        consulted.
        """
        printed = [str(n) for n in range(1, 26)]
        printed[1] = "z"     # 2 misread
        printed[5] = "0"     # 6 misread
        printed[14] = "IS"   # 15 misread

        geometry = read_geometry(page_boxes(printed), page=6, page_width=PAGE_WIDTH)

        assert [line.rank for line in geometry.lines] == list(range(1, 26))
        assert geometry.disagreements == 3

    def test_an_empty_box_still_gets_its_line(self):
        """Some engines return a box with no text where the ink was too faint."""
        printed = [str(n) for n in range(1, 26)]
        printed[9] = ""

        geometry = read_geometry(page_boxes(printed), page=6, page_width=PAGE_WIDTH)

        assert geometry.line_count == 25
        assert geometry.lines[9].rank == 10
        assert geometry.lines[9].printed is None
        assert not geometry.lines[9].agrees

    def test_a_number_missed_entirely_does_not_shift_the_rest(self):
        """The failure that would otherwise be invisible.

        If the OCR finds nothing at all where line 10's number was, counting the
        boxes 1, 2, 3... makes line 11 into line 10 and every line below it
        wrong. Nothing about the output would look wrong. Numbering by spacing
        instead leaves a gap where the gap really is.
        """
        boxes = page_boxes([str(n) for n in range(1, 26)])
        # Drop the margin box for line 10, keeping its words.
        boxes = [b for b in boxes if not (b.x0 == 90 and b.text == "10")]

        geometry = read_geometry(boxes, page=6, page_width=PAGE_WIDTH)

        assert geometry.line_count == 24        # one number not found
        assert geometry.highest_line == 25      # numbering still reaches 25
        assert geometry.missing_numbers == [10]
        # Every number that was found still reads correctly.
        assert all(line.agrees for line in geometry.lines)

    def test_two_numbers_missed_in_a_row_still_keep_the_count(self):
        boxes = page_boxes([str(n) for n in range(1, 26)])
        boxes = [b for b in boxes if not (b.x0 == 90 and b.text in ("10", "11"))]

        geometry = read_geometry(boxes, page=6, page_width=PAGE_WIDTH)

        assert geometry.highest_line == 25
        assert geometry.missing_numbers == [10, 11]

    def test_a_word_stuck_to_the_number_is_not_a_misread(self):
        """Merging a row sometimes picks up a short word next to the margin.

        The text arrives as "19is" instead of "19". The line number is perfectly
        legible at the front, and counting that as a misreading would overstate
        how badly the page read.
        """
        boxes = page_boxes([str(n) for n in range(1, 26)])
        # A two-letter body word close enough to the margin to be picked up and
        # merged into the number beside it, which is how "19is" arises.
        y = 100.0 + 18 * LINE_SPACING
        boxes.append(TextBox(text="is", x0=124, y0=y, x1=150, y1=y + 30))

        geometry = read_geometry(boxes, page=4, page_width=PAGE_WIDTH)

        assert geometry.line_count == 25
        assert geometry.lines[18].rank == 19
        assert geometry.lines[18].printed == "19is"
        assert geometry.disagreements == 0

    def test_a_two_digit_number_does_not_confirm_a_one_digit_line(self):
        """"21" must not be accepted as agreeing with line 2."""
        printed = [str(n) for n in range(1, 26)]
        printed[1] = "21"

        geometry = read_geometry(page_boxes(printed), page=4, page_width=PAGE_WIDTH)
        assert not geometry.lines[1].agrees

    def test_disagreements_are_recorded_rather_than_corrected(self):
        """The count is an honest quality measure for the page.

        The right answer is known independently, so this says how well the OCR
        read a page without anyone having to check it by hand.
        """
        printed = [str(n) for n in range(1, 26)]
        printed[0] = "l"

        geometry = read_geometry(page_boxes(printed), page=1, page_width=PAGE_WIDTH)

        assert geometry.lines[0].rank == 1
        assert geometry.lines[0].printed == "l"
        assert geometry.disagreements == 1
        assert any("line numbers were read as" in w for w in geometry.warnings)


class TestPageLevelChecks:
    def test_a_page_with_no_margin_says_so_rather_than_failing(self):
        """A cover sheet has no numbered lines. That is normal, not an error."""
        boxes = [TextBox(text="SUPREME COURT OF THE UNITED STATES",
                         x0=300, y0=400, x1=900, y1=440)]
        geometry = read_geometry(boxes, page=1, page_width=PAGE_WIDTH)

        assert geometry.line_count == 0
        assert geometry.body_box is None
        assert any("No line numbers" in w for w in geometry.warnings)

    def test_a_short_page_is_flagged_but_still_read(self):
        geometry = read_geometry(page_boxes(["1", "2", "3"]), page=104,
                                 page_width=PAGE_WIDTH)

        assert geometry.line_count == 3
        assert any("expected 25" in w for w in geometry.warnings)

    def test_the_body_starts_to_the_right_of_the_margin(self):
        geometry = read_geometry(page_boxes([str(n) for n in range(1, 26)]),
                                 page=6, page_width=PAGE_WIDTH)

        assert geometry.body_left == 170
        assert geometry.body_left > 120  # past the widest margin number

    def test_the_crop_excludes_the_margin_entirely(self):
        """The reason a language model cannot invent line numbers here."""
        geometry = read_geometry(page_boxes([str(n) for n in range(1, 26)]),
                                 page=6, page_width=PAGE_WIDTH)

        left, top, _right, bottom = geometry.body_box
        assert left >= 120
        assert top <= 100
        assert bottom >= 100 + 24 * LINE_SPACING

    def test_a_header_above_the_numbered_lines_is_outside_the_crop(self):
        """Page furniture falls outside the band the numbers define, for free."""
        boxes = page_boxes([str(n) for n in range(1, 26)])
        boxes.append(TextBox(text="Official - Subject to Final Review",
                             x0=300, y0=30, x1=900, y1=60))

        geometry = read_geometry(boxes, page=6, page_width=PAGE_WIDTH)
        _left, top, _right, _bottom = geometry.body_box
        assert top > 60


class TestMatchingWordsToLines:
    def test_words_are_matched_to_the_number_beside_them(self):
        boxes = page_boxes(["1", "2", "3"])
        geometry = read_geometry(boxes, page=6, page_width=PAGE_WIDTH)
        _gutter, body = find_gutter(boxes, PAGE_WIDTH)

        words = words_for_line(body, geometry.lines[1], tolerance=LINE_SPACING / 2)
        assert len(words) == 1

    def test_words_come_back_left_to_right(self):
        boxes = page_boxes([str(n) for n in range(1, 26)], body_text="filler")
        # Put three words on the first line, deliberately out of order.
        boxes += [
            TextBox(text="third", x0=500, y0=100, x1=600, y1=130),
            TextBox(text="first", x0=170, y0=100, x1=250, y1=130),
            TextBox(text="second", x0=300, y0=100, x1=400, y1=130),
        ]
        geometry = read_geometry(boxes, page=6, page_width=PAGE_WIDTH)
        _gutter, body = find_gutter(boxes, PAGE_WIDTH)

        words = words_for_line(body, geometry.lines[0], tolerance=30)
        assert [box.text for box in words][:4] == ["filler", "first", "second", "third"]

    def test_a_slightly_uneven_scan_still_matches(self):
        """Scans are never perfectly square, so exact alignment cannot be required."""
        boxes = page_boxes([str(n) for n in range(1, 26)], body_text="filler")
        boxes.append(TextBox(text="drifted", x0=950, y0=108, x1=1100, y1=138))

        geometry = read_geometry(boxes, page=6, page_width=PAGE_WIDTH)
        _gutter, body = find_gutter(boxes, PAGE_WIDTH)

        words = words_for_line(body, geometry.lines[0], tolerance=LINE_SPACING / 2)
        assert "drifted" in [box.text for box in words]

"""One badly timed word must not hold the reference's clock at its time."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))


def test_one_late_word_does_not_freeze_the_rest():
    from lineup import longest_forward_run

    times = [1.0, 2.0, 500.0, 3.0, 4.0, 5.0]
    assert longest_forward_run(times) == {0, 1, 3, 4, 5}


def test_words_with_no_time_are_left_out_and_ties_stay():
    from lineup import longest_forward_run

    assert longest_forward_run([None, 1.0, None, 1.0, 2.0]) == {1, 3, 4}
    assert longest_forward_run([None, None]) == set()

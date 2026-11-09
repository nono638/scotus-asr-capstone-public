"""The fixes that stop the comparison inventing differences.

Every case here is a real spot from the hand review of 157 flagged rows
(`flagged-spots-review.md`).
"""

import pytest

from scotus_asr.scoring.align import align_words


def errors(reference: str, hypothesis: str, rule: str, harmonise: bool = True) -> int:
    a = align_words(reference.split(), hypothesis.split(), rule, harmonise=harmonise)
    return a.substitutions + a.deletions + a.insertions


SAME_WORDS = [
    ("granted under 3553(e). And that", "granted under 3553E. And that"),
    ("One is 1252(b)(9), which", "One is 1252 B9, which"),
    ("28 U.S.C. 2254(d)", "28 USC 2254 d"),
    ("their e-mails in storage", "their emails in storage"),
    ("adopted Respondents' view", "adopted respondent's view"),
    ("there's been no change", "there has been no change"),
    ("All right. Suppose", "Alright. Suppose"),
    ("non-Article III judge", "non-Article 3 judge"),
    ("So $10 times 200", "So 10 dollars times 200"),
    ("the Mt. Healthy framework", "the Mount Healthy framework"),
    ("Uh-huh. So", "Mm-hmm. So"),
    # The engines' word timings split some words at punctuation.
    ("while U.S. Government officials", "while U .S. government officials"),
    ("paid $5,000 for", "paid $5 ,000 for"),
    ("Justice O'Connor, says", "Justice O 'Connor, says"),
]


def test_a_stammer_is_not_joined_into_a_roman_numeral():
    # "ii" is in the vocabulary (Title II), but "I -- I" is two words.
    a = align_words("Now, I -- I think".split(), "now i think".split(), "standard",
                    harmonise=True, vocabulary={"ii", "now", "i", "think"})
    assert a.reference.tokens == ["now", "i", "i", "think"]
    assert a.deletions == 1


def test_a_leading_space_on_a_machine_word_does_not_hide_it():
    # Whisper stores " arm's" with a space in front.
    a = align_words(["the", "arm's", "length"], ["the", " arm's", "length"], "standard", harmonise=True)
    assert a.substitutions + a.deletions + a.insertions == 0


@pytest.mark.parametrize("rule", ["standard", "lowercase_nopunct"])
@pytest.mark.parametrize("reference,hypothesis", SAME_WORDS)
def test_differences_nobody_could_hear_are_not_counted(reference, hypothesis, rule):
    assert errors(reference, hypothesis, rule) == 0


@pytest.mark.parametrize("rule", ["standard", "lowercase_nopunct", "verbatim"])
def test_real_differences_still_count(rule):
    # Words really left out. The benchmark rule expands "it's" to "it is", so
    # there it is three words, not two.
    assert errors("it's a basic question", "basic question", rule) == (3 if rule == "standard" else 2)
    # A real mishearing.
    assert errors("the breadth or", "the breath or", rule) == 1


def test_verbatim_forgives_only_how_a_compound_is_written():
    assert errors("in rule-making, of course", "in rule making, of course", "verbatim") == 0
    assert errors("their e-mails in storage", "their emails in storage", "verbatim") == 0
    # Style is part of a record, so these still count under verbatim.
    assert errors("non-Article III judge", "non-Article 3 judge", "verbatim") == 1
    assert errors("adopted Respondents' view", "adopted respondent's view", "verbatim") == 1


def test_off_by_default_so_old_figures_reproduce():
    assert errors("granted under 3553(e). And that", "granted under 3553E. And that",
                  "standard", harmonise=False) == 1

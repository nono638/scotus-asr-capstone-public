"""Rev's NLP reference format (Earnings-22)."""

import pytest

from scotus_asr.references.nlp import nlp_to_transcript, read_nlp

# The start of 4485192.nlp, then a cut-off word, tags and a second speaker.
NLP = (
    "token|speaker|ts|endTs|punctuation|prepunctuation|case|tags\n"
    "Good|0|||||UC|[]\n"
    "morning|0|||,||LC|[]\n"
    "Year|0|||||UC|[]\n"
    "2022|0|||||N/A|['0:YEAR']\n"
    "Call|0|||.||UC|[]\n"
    "<crosstalk>|0|||||N/A|[]\n"
    "question-|1|||||LC|['171:FALLBACK']\n"
    "<unk>|1|||,||N/A|[]\n"
    "um|1|||,||LC|[]\n"
    "right|1|||.|\"|LC|[]\n"
)


@pytest.fixture
def nlp(tmp_path):
    path = tmp_path / "4485192.nlp"
    path.write_text(NLP, encoding="utf-8")
    return path


def test_words_carry_their_punctuation_and_tags_are_dropped(nlp):
    transcript = nlp_to_transcript("4485192", read_nlp(nlp))
    assert [(t.speaker, t.text) for t in transcript.turns] == [
        ("0", "Good morning, Year 2022 Call."),
        ("1", "question- um, \"right."),
    ]
    assert transcript.turns[0].start is None


def test_columns_are_found_by_name(tmp_path):
    path = tmp_path / "x.nlp"
    path.write_text("speaker|token|punctuation\n0|Hello|.\n", encoding="utf-8")
    assert read_nlp(path)[0].word == "Hello."


def test_a_missing_column_is_named(tmp_path):
    path = tmp_path / "x.nlp"
    path.write_text("word|speaker\nHello|0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="token"):
        read_nlp(path)

"""Tests for corpora other than the Supreme Court, and the formats they share.

No network and no real corpus: the EdAcc and CORAAL tests build a small copy of
each release's layout in a temporary folder, with a second of silence for audio.
"""

from __future__ import annotations

import tarfile

import numpy as np
import pytest
import soundfile

from scotus_asr.asr.base import AsrResult, Segment, Word
from scotus_asr.config import ScoringSettings, load_config
from scotus_asr.corpora.base import Recording, read_index, write_index
from scotus_asr.corpora.coraal import CoraalCorpus
from scotus_asr.corpora.coraal import clean as coraal_clean
from scotus_asr.corpora.download import unpack
from scotus_asr.corpora.edacc import EdaccCorpus, clean
from scotus_asr.corpora.earnings22 import Earnings22Corpus, lfs_size
from scotus_asr.corpora.formats import (
    IGNORE, read_ctm, read_stm, stm_to_transcript, write_ctm, write_stm,
)
from scotus_asr.corpora.registry import build_corpus
from scotus_asr.scoring.metrics import drop_ignored, score_case
from scotus_asr.transcripts.model import Transcript, Turn

STM = f""";; a comment line
REC-1 1 REC-1-B 5.22 6.25 <male,l1> YEAH I'VE GOT A <LAUGH> NOTIFICATION
REC-1 1 REC-1-A 0.00 5.33 <male,l1> OKAY I THINK IT'S RECORDING
REC-1 1 REC-1-A 7.00 9.00 <male,l1> {IGNORE}
REC-1 1 REC-1-B 9.50 10.00 <male,l1> <NO-SPEECH>
REC-2 1 REC-2-A 0.00 1.00 <female,l2> HELLO
"""


@pytest.fixture
def stm_file(tmp_path):
    path = tmp_path / "stm"
    path.write_text(STM, encoding="utf-8")
    return path


class TestStm:
    def test_reads_every_field_and_skips_comments(self, stm_file):
        lines = read_stm(stm_file)
        assert len(lines) == 5
        first = lines[0]
        assert (first.file, first.speaker, first.start, first.end) == ("REC-1", "REC-1-B", 5.22, 6.25)
        assert first.labels == "male,l1"
        assert first.text == "YEAH I'VE GOT A <LAUGH> NOTIFICATION"

    def test_a_short_line_is_an_error_not_a_lost_turn(self, tmp_path):
        bad = tmp_path / "bad.stm"
        bad.write_text("REC-1 1 A 0.0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="line 1"):
            read_stm(bad)

    def test_turns_come_out_in_time_order_with_ignored_stretches_apart(self, stm_file):
        lines = [l for l in read_stm(stm_file) if l.file == "REC-1"]
        transcript = stm_to_transcript("REC-1", lines, clean=clean)
        assert [t.speaker for t in transcript.turns] == ["REC-1-A", "REC-1-B"]
        assert transcript.turns[0].start == 0.0 and transcript.turns[0].end == 5.33
        assert transcript.turns[1].text == "YEAH I'VE GOT A NOTIFICATION"
        assert transcript.ignore == [(7.0, 9.0)]

    def test_a_line_that_cleans_to_nothing_is_dropped(self, stm_file):
        lines = [l for l in read_stm(stm_file) if l.file == "REC-1"]
        transcript = stm_to_transcript("REC-1", lines, clean=clean)
        assert all(turn.text for turn in transcript.turns)
        assert len(transcript.turns) == 2

    def test_writing_and_reading_back_keeps_the_turns(self, stm_file, tmp_path):
        lines = [l for l in read_stm(stm_file) if l.file == "REC-1"]
        transcript = stm_to_transcript("REC-1", lines, clean=clean)
        out = tmp_path / "out.stm"
        write_stm(transcript, out)
        again = stm_to_transcript("REC-1", read_stm(out))
        assert [t.text for t in again.turns] == [t.text for t in transcript.turns]
        assert again.ignore == transcript.ignore


class TestCtm:
    def test_round_trip(self, tmp_path):
        words = [Word("hello", 1.0, 1.4), Word("there", 1.5, 1.9), Word(" ", 2.0, 2.0)]
        path = tmp_path / "x.ctm"
        write_ctm("REC-1", words, path)
        back = read_ctm(path)["REC-1"]
        assert [w.text for w in back] == ["hello", "there"]
        assert back[1].start == pytest.approx(1.5) and back[1].end == pytest.approx(1.9)

    def test_reads_confidence_when_given(self, tmp_path):
        path = tmp_path / "c.ctm"
        path.write_text("REC 1 2.0 0.5 YES 0.9\nREC 1 1.0 0.5 NO\n", encoding="utf-8")
        words = read_ctm(path)["REC"]
        assert [w.text for w in words] == ["NO", "YES"]   # sorted by time
        assert words[1].probability == 0.9


class TestTranscriptTimes:
    def test_times_and_ignored_stretches_survive_saving(self):
        transcript = Transcript(
            docket="REC-1",
            turns=[Turn(speaker="A", text="hello", start=1.0, end=2.0)],
            ignore=[(3.0, 4.0)],
        )
        again = Transcript.from_dict(transcript.to_dict())
        assert again.turns[0].start == 1.0 and again.turns[0].end == 2.0
        assert again.ignore == [(3.0, 4.0)]

    def test_a_reference_saved_before_times_existed_still_loads(self):
        old = {"docket": "16-1144", "turns": [{"speaker": "JUSTICE KAGAN", "text": "well"}]}
        transcript = Transcript.from_dict(old)
        assert transcript.turns[0].start is None
        assert transcript.ignore == []


def _result(words: list[Word]) -> AsrResult:
    return AsrResult(
        docket="REC-1", engine="test", model="test",
        segments=[Segment(index=0, start=words[0].start, end=words[-1].end,
                          text=" ".join(w.text for w in words), words=words)],
        audio_seconds=60.0,
    )


class TestIgnoredStretches:
    def test_a_word_goes_by_its_midpoint(self):
        words = [Word("in", 6.5, 7.4), Word("out", 6.0, 7.2), Word("edge", 8.9, 9.2)]
        kept = drop_ignored(words, [(7.0, 9.0)])
        # "in" has its midpoint at 6.95, "out" at 6.6, "edge" at 9.05: all outside.
        assert [w.text for w in kept] == ["in", "out", "edge"]
        assert drop_ignored([Word("inside", 7.5, 8.5)], [(7.0, 9.0)]) == []

    def test_nothing_ignored_keeps_everything(self):
        words = [Word("a", 0.0, 1.0)]
        assert drop_ignored(words, []) == words

    def test_words_read_aloud_are_not_charged_as_insertions(self):
        reference = Transcript(
            docket="REC-1",
            turns=[Turn(speaker="A", text="okay let us talk", start=0.0, end=2.0)],
            ignore=[(3.0, 10.0)],
        )
        said = [Word("okay", 0.0, 0.4), Word("let", 0.5, 0.7), Word("us", 0.8, 1.0),
                Word("talk", 1.1, 1.5), Word("the", 4.0, 4.2), Word("rainbow", 4.3, 4.8)]
        score = score_case(reference, _result(said), ScoringSettings(), audio_minutes=1.0)
        standard = next(r for r in score.rows if r.normalizer == "standard")
        assert standard.insertions == 0 and standard.wer == 0.0


def _fake_release(root):
    """Two recordings in EdAcc's layout: one in test, one in dev."""
    release = root / "unpacked" / "edacc_v1.0"
    (release / "data").mkdir(parents=True)
    for split, name in (("test", "REC-1"), ("dev", "REC-2")):
        (release / split).mkdir()
        (release / split / "conv.list").write_text(name + "\n", encoding="utf-8")
        (release / split / "stm").write_text(
            "".join(l + "\n" for l in STM.splitlines() if l.startswith(name)), encoding="utf-8")
        soundfile.write(str(release / "data" / f"{name}.wav"), np.zeros(32000), 32000)
    return release


class TestEdacc:
    def test_clean_removes_tags_and_spaces(self):
        assert clean("YEAH <LAUGH>  I  <OVERLAP> SEE") == "YEAH I SEE"
        assert clean("<NO-SPEECH>") == ""

    def test_index_lists_each_split_with_length_and_speakers(self, tmp_path):
        _fake_release(tmp_path)
        corpus = EdaccCorpus(tmp_path, split="test")
        write_index(corpus.index, corpus._build_index())
        [recording] = corpus.recordings()
        assert recording.id == "REC-1" and recording.split == "test"
        assert recording.audio_minutes == pytest.approx(1 / 60)
        assert recording.sampling_rate == 32000
        assert recording.extra["speakers"] == {"REC-1-A": "male,l1", "REC-1-B": "male,l1"}
        assert recording.extra["ignored_seconds"] == 2.0
        assert len(EdaccCorpus(tmp_path).recordings()) == 2   # no split: both

    def test_reference_is_the_cleaned_stm(self, tmp_path):
        _fake_release(tmp_path)
        corpus = EdaccCorpus(tmp_path, split="test")
        write_index(corpus.index, corpus._build_index())
        transcript = corpus.reference(corpus.recordings()[0])
        assert transcript.full_text() == "OKAY I THINK IT'S RECORDING YEAH I'VE GOT A NOTIFICATION"
        assert transcript.ignore == [(7.0, 9.0)]

    def test_listing_before_preparing_says_so(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            EdaccCorpus(tmp_path).recordings()


CORAAL_TXT = (
    "Line\tSpkr\tStTime\tContent\tEnTime\n"
    "1\tROC_int_01\t0.5\tSo where did you grow up?\t2.0\n"
    "2\tROC_se0_ag1_f_01\t2.1\tUm, on the [east side.]\t3.4\n"
    "3\tROC_int_01\t3.0\t[Okay.]\t3.5\n"
    "4\tROC_se0_ag1_f_01\t3.5\t(pause 0.40)\t3.9\n"
    "5\tROC_se0_ag1_f_01\t3.9\tBy /RD-SCHOOL-3/, you know.\t5.2\n"
    "6\tROC_se0_ag1_f_01\t5.3\tIt- it w- it was nice <laugh> (laughing)\t7.0\n"
)


def _fake_coraal(root):
    """One Rochester recording, its audio and transcript in separate unpacked parts."""
    audio = root / "unpacked" / "ROC_audio_part01_2020.05"
    text = root / "unpacked" / "ROC_textfiles_2020.05"
    audio.mkdir(parents=True)
    text.mkdir(parents=True)
    soundfile.write(str(audio / "ROC_se0_ag1_f_01_1.wav"), np.zeros(16000), 16000)
    soundfile.write(str(audio / "ROC_se0_ag1_f_02_1.wav"), np.zeros(16000), 16000)  # no transcript
    (text / "ROC_se0_ag1_f_01_1.txt").write_text(CORAAL_TXT, encoding="utf-8")


class TestCoraal:
    def test_clean_follows_the_user_guide(self):
        assert coraal_clean("(pause 0.52)") == ""
        assert coraal_clean("on Seventh and /RD-ADDRESS-3/ all the kids") is None
        assert coraal_clean("I can appreciate that /unintelligible/") is None
        assert coraal_clean("Christopher /Folumbus/ I mean Columbus.") is None
        assert coraal_clean("Or is he [retired? No?]") == "Or is he retired? No?"
        assert coraal_clean("Well we're all different. <laugh>") == "Well we're all different."
        assert coraal_clean("what up dog (atypical pronunciation)") == "what up dog"
        assert coraal_clean("it- it- it w- it used to be") == "it it it w it used to be"

    def test_index_needs_audio_and_transcript(self, tmp_path):
        _fake_coraal(tmp_path)
        corpus = CoraalCorpus(tmp_path)
        write_index(corpus.index, corpus._build_index())
        [recording] = corpus.recordings()
        assert recording.id == "ROC_se0_ag1_f_01_1" and recording.split == "ROC"
        assert recording.audio_minutes == pytest.approx(1 / 60)
        assert recording.extra["speakers"] == ["ROC_int_01", "ROC_se0_ag1_f_01"]
        assert CoraalCorpus(tmp_path, split="roc").recordings() == [recording]
        assert CoraalCorpus(tmp_path, split="PRV").recordings() == []

    def test_reference_drops_pauses_and_ignores_redactions(self, tmp_path):
        _fake_coraal(tmp_path)
        corpus = CoraalCorpus(tmp_path)
        write_index(corpus.index, corpus._build_index())
        transcript = corpus.reference(corpus.recordings()[0])
        assert transcript.full_text(include_speakers=False) == (
            "So where did you grow up? Um, on the east side. Okay. It it w it was nice")
        assert transcript.ignore == [(3.9, 5.2)]

    def test_an_unknown_component_is_refused(self, tmp_path):
        with pytest.raises(SystemExit, match="ROC"):
            CoraalCorpus(tmp_path, split="XYZ").recordings()


class TestIndexAndUnpack:
    def test_index_round_trip(self, tmp_path):
        recording = Recording(id="R", audio_path=tmp_path / "r.wav", audio_minutes=2.5,
                              corpus="c", split="test", sampling_rate=16000, extra={"k": 1})
        write_index(tmp_path / "i.jsonl", [recording])
        [back] = read_index(tmp_path / "i.jsonl")
        assert back == recording and back.extra == {"k": 1}

    def test_unpack_once_then_skip(self, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_text("hi", encoding="utf-8")
        archive = tmp_path / "a.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(source / "a.txt", arcname="top/a.txt")
        into = unpack(archive, tmp_path / "out")
        assert (into / "top" / "a.txt").read_text(encoding="utf-8") == "hi"
        (into / "top" / "a.txt").write_text("changed", encoding="utf-8")
        unpack(archive, tmp_path / "out")   # the marker says it is done
        assert (into / "top" / "a.txt").read_text(encoding="utf-8") == "changed"


class TestChoosingACorpus:
    def test_the_supreme_court_is_the_default(self):
        assert build_corpus(load_config()).name == "scotus"

    def test_another_corpus_needs_a_root(self, tmp_path):
        settings = tmp_path / "s.yaml"
        settings.write_text("corpus:\n  name: edacc\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="root"):
            build_corpus(load_config(settings))

    def test_an_unknown_name_lists_the_known_ones(self, tmp_path):
        settings = tmp_path / "s.yaml"
        settings.write_text("corpus:\n  name: nope\n  root: x\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="edacc"):
            build_corpus(load_config(settings))

    def test_a_model_file_and_a_corpus_file_combine(self, tmp_path):
        model = tmp_path / "model.yaml"
        model.write_text("asr:\n  engine: qwen3-asr\npaths:\n  runs_dir: D:/a\n", encoding="utf-8")
        corpus = tmp_path / "corpus.yaml"
        corpus.write_text("corpus:\n  name: edacc\n  root: D:/c\npaths:\n  runs_dir: D:/b\n",
                          encoding="utf-8")
        config = load_config([model, corpus])
        assert config.asr.engine == "qwen3-asr"        # kept from the first
        assert config.corpus.name == "edacc"           # added by the second
        assert config.paths.runs_dir.as_posix() == "D:/b"   # the later file wins


def test_edacc_takes_recordings_from_the_stm_not_conv_list(tmp_path):
    """In the real dev split conv.list names a recording with no audio."""
    release = _fake_release(tmp_path)
    (release / "test" / "conv.list").write_text("REC-1\nREC-GHOST\n", encoding="utf-8")
    corpus = EdaccCorpus(tmp_path, split="test")
    recordings = corpus._build_index()
    assert [r.id for r in recordings if r.split == "test"] == ["REC-1"]
    assert any("REC-GHOST" in note for note in corpus.notes)


def _fake_earnings22(root):
    """Two calls: one in Subset 10, one not, with metadata and references."""
    (root / "media").mkdir(parents=True)
    (root / "references").mkdir()
    (root / "metadata.csv").write_text(
        "File ID,Ticker Symbol,Country by Ticker,UN Defined,Major Dialect Family,"
        "Language Family + Area Based,File Length (seconds),Sampling Rate (Hz)\n"
        "4485192,EPC,United States,Northern America,English,English,3720,16000\n"
        "4468919,LOMA,Argentina,Latin America and Caribbean,Other,Spanish/Portuguese,1214,22050\n",
        encoding="utf-8")
    for call in ("4485192", "4468919"):
        soundfile.write(str(root / "media" / f"{call}.mp3"), np.zeros(16000), 16000, format="MP3")
        (root / "references" / f"{call}.nlp").write_text(
            "token|speaker|ts|endTs|punctuation|prepunctuation|case|tags\n"
            "Good|0|||||UC|[]\nmorning|0|||.||LC|[]\n", encoding="utf-8")


class TestEarnings22:
    def test_lfs_pointer_gives_the_real_size(self, tmp_path):
        pointer = tmp_path / "p.txt"
        pointer.write_text("version https://git-lfs.github.com/spec/v1\n"
                           "oid sha256:352f\nsize 14770322\n", encoding="utf-8")
        assert lfs_size(pointer) == 14_770_322

    def test_splits_are_regions_or_subset10(self, tmp_path):
        _fake_earnings22(tmp_path)
        corpus = Earnings22Corpus(tmp_path)
        write_index(corpus.index, corpus._build_index())
        assert [r.split for r in corpus.recordings()] == ["English", "Spanish/Portuguese"]
        assert [r.id for r in Earnings22Corpus(tmp_path, split="subset10").recordings()] == ["4485192"]
        assert [r.id for r in Earnings22Corpus(tmp_path, split="spanish/portuguese").recordings()] == ["4468919"]
        with pytest.raises(SystemExit, match="English"):
            Earnings22Corpus(tmp_path, split="Martian").recordings()

    def test_reference_is_read_from_the_nlp_file(self, tmp_path):
        _fake_earnings22(tmp_path)
        corpus = Earnings22Corpus(tmp_path)
        write_index(corpus.index, corpus._build_index())
        transcript = corpus.reference(corpus.recordings()[0])
        assert transcript.full_text() == "Good morning."

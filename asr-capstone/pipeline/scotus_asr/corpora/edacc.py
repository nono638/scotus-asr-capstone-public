"""EdAcc, the Edinburgh International Accents of English Corpus.

About 40 hours of video calls between pairs of friends, many of them speaking
English as a second language - the nearest public stand-in for a remote
deposition. Version 1.0 is one tar file from the University of Edinburgh's
DataShare (DOI 10.7488/ds/7914), CC BY-SA, no account needed.

**What arrives.** The release follows the Kaldi and NIST conventions, so almost
nothing here is EdAcc's own:

    edacc_v1.0/
      data/<recording>.wav        whole conversations, one file each
      dev/  test/                 the two splits; there is no training set
        conv.list                 the recordings in the split - not used: in dev it
                                  disagrees with the stm and the audio
        stm                       the reference, one timed turn per line
        segments, text, utt2spk   the same turns as Kaldi files
        company.ctm               a commercial engine's output, anonymised
        stm.filt                  not used: a processed copy with damaged words
      linguistic_background.csv   each speaker's first language and history

**The reference** is upper case, unpunctuated, with numbers spelt out ("C
FOURTEEN DASH P ONE"). So only the benchmark rule (`standard`) compares like
with like here. The lowercase rule still counts "14" against "fourteen", and the
verbatim rule charges every capital letter and comma - its number means nothing
on this corpus.

Noise is written as tags - `<LAUGH>`, `<OVERLAP>`, `<DTMF>` (a tone), `<FOREIGN>`
and a few rarer ones - which are removed here. Hesitations are written as words
("UM", "UH") and kept; the benchmark rule removes them, as it does for the
Supreme Court. The passages each speaker reads aloud at the start are marked
IGNORE_TIME_SEGMENT_IN_SCORING and left out of scoring.

Each line's speaker carries a label like `<male,l2>` (sex, and English as first
or second language). The README warns these "may not be entirely reliable", so
they are kept with each recording for later analysis, not used to report.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import soundfile

from ..transcripts.model import Transcript
from .base import Corpus, Progress, Recording, read_index, write_index
from .download import fetch, unpack
from .formats import StmLine, read_stm, stm_to_transcript

#: DataShare's own address for the file; the item page's links serve a web app.
URL = ("https://datashare.ed.ac.uk/server/api/core/bitstreams/"
       "819f726e-1a65-4b3c-88d2-efdf0a7021ce/content")
ARCHIVE = "edacc_v1.0.tar.gz"
ARCHIVE_BYTES = 5_916_732_170
SPLITS = ("dev", "test")

_TAG = re.compile(r"<[^>]*>")


def clean(text: str) -> str:
    """A line of EdAcc reference with its noise tags removed."""
    return " ".join(_TAG.sub(" ", text).split())


class EdaccCorpus(Corpus):
    name = "edacc"

    @property
    def release(self) -> Path:
        return self.root / "unpacked" / "edacc_v1.0"

    @property
    def index(self) -> Path:
        return self.root / "recordings.jsonl"

    def prepare(self, progress: Progress = lambda note: None) -> None:
        archive = self.root / "downloads" / ARCHIVE
        last = [0]

        def report(got: int, total: int) -> None:
            if got - last[0] >= 50_000_000 or got == total:
                last[0] = got
                progress(f"downloading {ARCHIVE}: {got / 1e9:.2f} of {total / 1e9:.2f} GB")

        fetch(URL, archive, expected_bytes=ARCHIVE_BYTES, on_progress=report)
        if not (self.root / "unpacked.unpacked").exists():
            progress(f"unpacking {ARCHIVE} (a few minutes)")
        unpack(archive, self.root / "unpacked")
        notes = ""
        if not self.index.exists():
            progress("measuring every recording")
            write_index(self.index, self._build_index())
            notes = " - note: " + "; ".join(self.notes) if self.notes else ""
        progress("ready" + notes)

    def _build_index(self) -> list[Recording]:
        """Every recording in both splits, with its length and its speakers.

        **The recordings are the ones the STM names, not `conv.list`.** The two
        disagree in dev: `conv.list` lists EDACC-C33_P2, which has no audio in
        the release, and EDACC-C46, whose audio and reference are split into
        C46_P1 and C46_P2. The STM matches the audio exactly, and it is what gets
        scored. A recording with no audio would be left out and noted.
        """
        recordings = []
        self.notes: list[str] = []
        for split in SPLITS:
            lines = self._stm(split)
            names = list(dict.fromkeys(line.file for line in lines))
            listed = (self.release / split / "conv.list").read_text(encoding="utf-8").split()
            if set(listed) != set(names):
                self.notes.append(
                    f"{split}: conv.list and stm disagree (only in conv.list: "
                    f"{', '.join(sorted(set(listed) - set(names))) or 'none'}; only in stm: "
                    f"{', '.join(sorted(set(names) - set(listed))) or 'none'}); used stm")
            for name in names:
                audio = self.release / "data" / f"{name}.wav"
                if not audio.exists():
                    self.notes.append(f"{split}: no audio for {name}; left out")
                    continue
                info = soundfile.info(str(audio))
                mine = [line for line in lines if line.file == name]
                speakers = {line.speaker: line.labels for line in mine}
                ignored = sum(line.end - line.start for line in mine if line.ignored)
                recordings.append(Recording(
                    id=name, audio_path=audio, audio_minutes=info.duration / 60,
                    corpus=self.name, split=split, sampling_rate=info.samplerate,
                    extra={"speakers": speakers, "ignored_seconds": round(ignored, 2)},
                ))
        return recordings

    def recordings(self) -> list[Recording]:
        if not self.index.exists():
            raise FileNotFoundError(self.index)
        everything = read_index(self.index)
        return [r for r in everything if not self.split or r.split == self.split]

    def reference(self, recording: Recording) -> Transcript:
        lines = [line for line in self._stm(recording.split) if line.file == recording.id]
        if not lines:
            raise ValueError(f"No reference lines for {recording.id} in {recording.split}/stm")
        return stm_to_transcript(recording.id, lines, clean=clean,
                                 source=f"edacc_v1.0/{recording.split}/stm")

    def _stm(self, split: str) -> list[StmLine]:
        return _read_stm_cached(self.release / split / "stm")


@lru_cache(maxsize=4)
def _read_stm_cached(path: Path) -> list[StmLine]:
    """Each split's STM is read once per process, not once per recording."""
    return read_stm(path)

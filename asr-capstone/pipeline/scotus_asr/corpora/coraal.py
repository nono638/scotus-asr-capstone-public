"""CORAAL, the Corpus of Regional African American Language (University of Oregon).

Sociolinguistic interviews, mostly one interviewer and one speaker, recorded in
several cities and decades. Koenecke et al. (2020, PNAS) used it to show that
commercial speech recognition made twice as many errors for Black speakers as
for white ones, and the capstone proposal promised it. Release 2023.06, licensed
CC BY-NC-SA 4.0: free to use for research, credit required. Notes from scouting
it are in `asr-capstone/datasets/coraal.md`.

**What arrives.** Each component (a site and year, e.g. ROC = Rochester 2016) is
a handful of files on lingtools.uoregon.edu:

    <COMP>_metadata_<version>.txt          one row per recording, speaker details
    <COMP>_audio_partNN_<version>.tar.gz   WAV, 44.1 kHz mono, split for download
    <COMP>_textfiles_<version>.tar.gz      one tab-separated transcript per WAV

Each part unpacks into a folder of its own; a recording is found by name across
all of them. The transcript rows are `Line Spkr StTime Content EnTime`, read by
`references.timed_table`, which keeps this module down to CORAAL's own markup.

**The markup** (CORAAL User Guide, pp. 19-26), and what is done with it:

- `(pause 0.52)` rows - silent stretches; dropped.
- `/RD-NAME-2/` and the like - a name or address bleeped out of the audio; the
  engines hear a tone. `/unintelligible/`, `/inaudible/`, `/??/` - talk nobody
  could make out. `/word/` - a best guess, or a mispronounced word written as
  said; the two cannot be told apart. A row holding any of these cannot be scored
  fairly, so its time is ignored in scoring, as EdAcc's read-aloud passages are.
- `<laugh>`, `<cough>` and other sounds, and line notes like `(whispered)` -
  removed.
- `[ ]` around overlapping speech - the brackets go, the words stay.
- A cut-off word or restart, `it- it- it w-` - the hyphen goes, the word stays,
  as Koenecke et al. did. Engines seldom write the fragments, so they count as
  missed words.

Leaving out a whole row for one bleeped name is cautious. In Princeville it sets
aside 2,380 of 44,313 rows, 71 minutes and 10% of the words (counted 19 Oct
2026). Koenecke et al. instead deleted only the marked words and kept the rest
of the row, which charges an engine for anything it writes over the beep.

Fillers ("uh", "um") stay in the reference; the benchmark rule removes them on
both sides. The reference has normal punctuation and capitals but follows its own
conventions (numbers spelt out, "gonna"), so the benchmark rule is the main one.

Rochester, Princeville and Washington DC (DCB, added 21 Oct 2026) came first:
the three sites Koenecke et al. used. Atlanta, Washington DC 1968 (DCA),
Detroit 1966 (DTA), Lower East Side and Valdosta were added on 23 Oct 2026, so
all eight are listed. To add a site, add a line to COMPONENTS with the byte
sizes the server gives; the index is rebuilt to include it.
"""

from __future__ import annotations

import re
from pathlib import Path

import soundfile

from ..references.timed_table import read_timed_table, rows_to_transcript
from ..transcripts.model import Transcript
from .base import Corpus, Progress, Recording, read_index, write_index
from .download import fetch, unpack

BASE = "https://lingtools.uoregon.edu/coraal"

#: Each component: its version, then {file kind: bytes}, sizes from the server.
COMPONENTS = {
    "ROC": ("2020.05", {
        "metadata": 9_748, "textfiles": 801_537,
        "audio_part01": 601_718_376, "audio_part02": 617_531_670, "audio_part03": 797_355_036,
        "audio_part04": 549_776_743, "audio_part05": 312_347_159,
    }),
    "PRV": ("2018.10.06", {
        "metadata": 20_393, "textfiles": 894_006,
        "audio_part01": 797_045_351, "audio_part02": 919_479_624, "audio_part03": 982_116_581,
        "audio_part04": 565_637_234,
    }),
    "DCB": ("2018.10.06", {
        "metadata": 43_302, "textfiles": 2_816_920,
        "audio_part01": 807_328_059, "audio_part02": 646_803_359, "audio_part03": 471_156_371,
        "audio_part04": 478_496_612, "audio_part05": 904_081_541, "audio_part06": 670_401_934,
        "audio_part07": 594_417_668, "audio_part08": 633_462_590, "audio_part09": 664_400_237,
        "audio_part10": 530_685_203, "audio_part11": 468_514_884, "audio_part12": 521_037_029,
        "audio_part13": 564_766_923, "audio_part14": 128_184_960,
    }),
    # The other five, added 23 Oct 2026 to complete the corpus. DCA and DTA are
    # 1960s reel-to-reel tape, the noisiest audio in the study.
    "ATL": ("2020.05", {
        "metadata": 6_603, "textfiles": 512_506,
        "audio_part01": 471_181_856, "audio_part02": 394_142_433, "audio_part03": 386_630_794,
        "audio_part04": 462_114_530,
    }),
    "DCA": ("2018.10.06", {
        "metadata": 44_081, "textfiles": 1_971_578,
        "audio_part01": 721_501_810, "audio_part02": 625_840_650, "audio_part03": 768_177_376,
        "audio_part04": 631_928_677, "audio_part05": 699_329_572, "audio_part06": 962_982_155,
        "audio_part07": 625_858_241, "audio_part08": 764_114_779, "audio_part09": 838_786_355,
        "audio_part10": 869_237_834,
    }),
    "DTA": ("2023.06", {
        "metadata": 31_226, "textfiles": 1_428_948,
        "audio_part01": 466_988_785, "audio_part02": 542_634_532, "audio_part03": 308_039_403,
        "audio_part04": 495_756_211, "audio_part05": 644_922_715, "audio_part06": 609_017_557,
        "audio_part07": 400_027_751, "audio_part08": 633_244_891, "audio_part09": 532_734_651,
        "audio_part10": 522_685_486,
    }),
    "LES": ("2021.07", {
        "metadata": 7_957, "textfiles": 546_430,
        "audio_part01": 511_759_806, "audio_part02": 557_989_800, "audio_part03": 716_158_028,
    }),
    "VLD": ("2021.07", {
        "metadata": 7_476, "textfiles": 667_292,
        "audio_part01": 581_271_031, "audio_part02": 353_884_408, "audio_part03": 574_591_219,
        "audio_part04": 688_030_585,
    }),
}

_PAUSE = re.compile(r"^\(pause\s+[\d.]+\)$")
_UNSCORABLE = re.compile(r"/[^/]*/")
_TAG = re.compile(r"<[^>]*>")
_NOTE = re.compile(r"\([^)]*\)")


def clean(text: str) -> str | None:
    """A CORAAL row's words to score: "" for a pause, None if it cannot be scored."""
    text = text.strip()
    if _PAUSE.match(text):
        return ""
    if _UNSCORABLE.search(text):
        return None
    text = _NOTE.sub(" ", _TAG.sub(" ", text)).replace("[", " ").replace("]", " ")
    words = [w[:-1] if w.endswith("-") and len(w) > 1 else w for w in text.split()]
    return " ".join(w for w in words if w)


def file_name(component: str, kind: str) -> str:
    version = COMPONENTS[component][0]
    return f"{component}_{kind}_{version}.{'txt' if kind == 'metadata' else 'tar.gz'}"


class CoraalCorpus(Corpus):
    """`split` is a component code ("ROC"), or empty for every listed component."""

    name = "coraal"

    @property
    def index(self) -> Path:
        return self.root / "recordings.jsonl"

    def components(self) -> list[str]:
        if not self.split:
            return list(COMPONENTS)
        wanted = self.split.upper()
        if wanted not in COMPONENTS:
            raise SystemExit(f"No CORAAL component {self.split!r} here. Listed: {', '.join(COMPONENTS)}")
        return [wanted]

    def prepare(self, progress: Progress = lambda note: None) -> None:
        # Every listed component is fetched and indexed, whichever split a run
        # asks for, so the index is the same file for all of them.
        for component in COMPONENTS:
            version, files = COMPONENTS[component]
            for kind, size in files.items():
                name = file_name(component, kind)
                target = self.root / "downloads" / name
                if not target.exists():
                    progress(f"downloading {name} ({size / 1e9:.2f} GB)")
                fetch(f"{BASE}/{component.lower()}/{version}/{name}", target, expected_bytes=size)
                if kind != "metadata":
                    unpack(target, self.root / "unpacked" / name.removesuffix(".tar.gz"))
        indexed = {r.split for r in read_index(self.index)} if self.index.exists() else set()
        if not set(COMPONENTS) <= indexed:
            progress("measuring every recording")
            write_index(self.index, self._build_index())
        progress("ready")

    def _build_index(self) -> list[Recording]:
        """Every recording with both a WAV and a transcript, with its length.

        The archives were made on a Mac and carry a hidden "._" copy of every
        file (resource forks, not audio or text); those are skipped.
        """
        unpacked = self.root / "unpacked"
        texts = {p.stem: p for p in unpacked.rglob("*.txt") if not p.name.startswith("._")}
        recordings = []
        for component in COMPONENTS:
            for audio in sorted(unpacked.rglob(f"{component}_*.wav")):
                if audio.stem not in texts:
                    continue
                info = soundfile.info(str(audio))
                rows = read_timed_table(texts[audio.stem], speaker="Spkr", start="StTime",
                                        end="EnTime", text="Content")
                speakers = sorted({r.speaker for r in rows})
                recordings.append(Recording(
                    id=audio.stem, audio_path=audio, audio_minutes=info.duration / 60,
                    corpus=self.name, split=component, sampling_rate=info.samplerate,
                    extra={"speakers": speakers, "transcript": str(texts[audio.stem])},
                ))
        return recordings

    def recordings(self) -> list[Recording]:
        wanted = set(self.components())
        if not self.index.exists():
            raise FileNotFoundError(self.index)
        return [r for r in read_index(self.index) if r.split in wanted]

    def reference(self, recording: Recording) -> Transcript:
        path = Path(recording.extra["transcript"])
        rows = read_timed_table(path, speaker="Spkr", start="StTime", end="EnTime", text="Content")
        return rows_to_transcript(recording.id, rows, clean=clean, source=f"CORAAL {path.name}")

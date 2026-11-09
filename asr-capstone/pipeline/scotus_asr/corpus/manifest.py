"""Reading the list of cases.

`sample/manifest.json` records, for each case, where its files came from and what
the earlier hand-verification found in them. The pipeline treats it as the index
of what exists.

One rule carried over from that verification, and it is not a detail: **the audio
address is read from the manifest, never built from the docket number.** Louisiana
v. Callais was argued twice, so its October recording is served as `24-109_2.mp3`.
Guessing `24-109.mp3` fetches the March argument instead and pairs 150 minutes of
the wrong audio with the transcript, with nothing anywhere reporting an error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Case:
    """One oral argument, and where its files are.

    Attributes:
        docket: The Court's docket number, e.g. `09-834`. Used as the identifier
            throughout the pipeline because it is short, unique and appears in
            every filename.
        folder: The case's directory inside `sample/`.
        argued: Date of argument, `YYYY-MM-DD`.
        transcript_url: Where the official transcript PDF came from.
        audio_url: Where the recording came from, or None for the cases the Court
            does not host audio for (anything before the 2010 term).
        audio_minutes: Length of the recording, from the earlier verification.
        expected_turns: Speaker turns found when the sample was checked by hand.
        expected_words: Spoken words found at the same time. Both are used as a
            regression check - if the parser starts producing different numbers,
            something changed that should not have.
    """

    docket: str
    folder: Path
    argued: str
    transcript_url: str | None
    audio_url: str | None
    audio_minutes: float | None
    expected_turns: int | None
    expected_words: int | None
    #: Where the transcript actually is, when it is not named after the docket.
    #: The sample's one scanned example is filed under its argument date rather
    #: than the usual pattern.
    transcript_file: Path | None = None

    @property
    def has_audio(self) -> bool:
        """Can this case be transcribed? Transcript-only cases cannot."""
        return self.audio_url is not None

    @property
    def id(self) -> str:
        """The name every corpus's recordings share for their identifier."""
        return self.docket

    #: What the downloaded files are named after - always the bare docket number,
    #: because that is what `fetch_corpus.py` wrote. `docket` above is the
    #: pipeline's *identifier*, which carries a term or a date for the twelve
    #: arguments whose docket number alone is not unique. Keeping them apart is
    #: what stops Johnson v. United States, argued twice in OT2014, writing both
    #: of its results to one file.
    file_stem: str = ""

    @property
    def transcript_pdf(self) -> Path:
        """The official transcript, as the Court serves it."""
        if self.transcript_file is not None:
            return self.transcript_file
        return self.folder / f"{self.file_stem or self.docket}_transcript.pdf"

    @property
    def audio_path(self) -> Path:
        """The recording. May not exist - it is kept out of version control."""
        return self.folder / f"{self.file_stem or self.docket}_audio.mp3"

    @property
    def term(self) -> str:
        """The October Term this case belongs to, taken from the folder name.

        Folders are named like `OT2010_09-834_Kasten_v_...`, so the term is the
        first four digits. Returns an empty string if the name does not follow
        that pattern.
        """
        name = self.folder.name
        if name.startswith("OT") and name[2:6].isdigit():
            return name[2:6]
        return ""


def load_cases(manifest_path: Path, sample_dir: Path | None = None) -> list[Case]:
    """Read every case out of a manifest file.

    Args:
        manifest_path: The `manifest.json` to read.
        sample_dir: Where the case folders live. Defaults to the manifest's own
            directory, which is how the sample is laid out.

    Returns:
        Cases in the order the manifest lists them.

    Raises:
        FileNotFoundError: If the manifest is missing.
        ValueError: If it is not a list, or an entry has no docket number.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest at {manifest_path}")

    base = Path(sample_dir) if sample_dir else manifest_path.parent
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"{manifest_path} should hold a list of cases.")

    return [_to_case(entry, base, index) for index, entry in enumerate(entries)]


def _to_case(entry: dict[str, Any], base: Path, index: int) -> Case:
    """Turn one manifest entry into a `Case`."""
    docket = entry.get("docket")
    if not docket:
        raise ValueError(f"Case {index} in the manifest has no docket number.")

    folder_name = entry.get("folder")
    if not folder_name:
        raise ValueError(f"Case {docket} has no folder.")

    return Case(
        # The manifest carries `case_id` where a docket number covers more than
        # one argument. Falling back to the bare docket keeps the six-case sample
        # manifest, which predates that field, working unchanged.
        docket=str(entry.get("case_id") or docket),
        file_stem=str(docket),
        folder=base / folder_name,
        argued=entry.get("argued", ""),
        transcript_url=entry.get("transcript_url"),
        audio_url=entry.get("audio_url"),
        audio_minutes=entry.get("audio_minutes"),
        expected_turns=entry.get("turns"),
        expected_words=entry.get("spoken_words"),
    )


def select(cases: Iterable[Case], dockets: Iterable[str] | None = None,
           with_audio_only: bool = False,
           terms: Iterable[str | int] | None = None) -> list[Case]:
    """Narrow a list of cases.

    Args:
        cases: What to choose from.
        dockets: Keep only these docket numbers. None keeps all of them.
        with_audio_only: Drop cases that have no recording. Use this for stages
            that need audio, so a transcript-only case is quietly left out rather
            than failing later with a confusing missing-file error.
        terms: Keep only these October Terms. Whole terms are the natural unit
            for a run - they share a reporting contractor and a transcript
            format, so a term that behaves oddly is a finding rather than noise.

    Returns:
        The cases that survived, in their original order.
    """
    chosen = list(cases)
    if dockets is not None:
        wanted = {d.strip() for d in dockets}
        chosen = [c for c in chosen if c.docket in wanted]
    if terms is not None:
        years = {str(t).strip() for t in terms}
        chosen = [c for c in chosen if c.term in years]
    if with_audio_only:
        chosen = [c for c in chosen if c.has_audio]
    return chosen

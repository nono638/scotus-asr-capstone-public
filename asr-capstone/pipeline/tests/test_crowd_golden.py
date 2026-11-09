"""tools/crowd.py's tables, frozen on a small made-up case.

crowd.py's labelling rules are moving into the package. This test pins down
what they write today so the move can be checked to change nothing: the same
four models on the same two recordings must give the same tables, byte for byte.

The case is court-shaped on purpose - mixed case, speaker turns, the reporter's
dash, a name, legal terms, a citation, fillers - so every rule has something to
fire on. To accept a deliberate change, rerun with UPDATE_GOLDEN=1 and say why
in the commit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scotus_asr.transcripts.model import Transcript, Turn

CAPSTONE = Path(__file__).resolve().parents[2]
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "crowd-golden"

TURNS = [
    ("CHIEF JUSTICE ROBERTS", "We'll hear argument this morning in Case 17-1234, "
     "Smith v. Jones. Mr. Garre."),
    ("MR. GARRE", "Mr. Chief Justice, and may it please the Court: The Chevron "
     "doctrine -- the question here is whether certiorari should --"),
    ("JUSTICE KAGAN", "Well, Mr. Garre, isn't 28 U.S.C. 1291 enough? I mean, the "
     "statute says final decisions, and that's all."),
    ("MR. GARRE", "Yes, Your Honor. Uh-huh. The text is clear, and Garcia agrees."),
]

SAID = {
    # Nearly right: the one the others are measured against.
    "Alpha": "we'll hear argument this morning in case seventeen twelve thirty four smith "
             "versus jones mister garre mister chief justice and may it please the court "
             "the chevron doctrine the question here is whether certiorari should well "
             "mister garre isn't twenty eight usc twelve ninety one enough i mean the "
             "statute says final decisions and that's all yes your honor uh huh the text "
             "is clear and garcia agrees",
    # The other three share most mistakes (a name, a legal term, an ending, the
    # dropped "well" and "uh huh"), so three of four agree against the record.
    # The last three words each get wrong in their own way: a hard passage.
    "Bravo": "we'll hear argument this morning in case seventeen twelve thirty four smith "
             "v jones mr gary mr chief justice and may it please the court the shevron "
             "doctrine the question here is whether certiorari should mr gary isn't "
             "twenty eight usc twelve ninety one enough i mean the statute says final "
             "decision and that's all yes your honor the text is clear an garza agreed",
    "Charlie": "we'll hear the argument this morning in case seventeen twelve thirty four "
               "smith v jones mr gary mr chief justice may it please the court the shevron "
               "doctrine the the question here is whether should mr gary is not twenty "
               "eight usc twelve ninety one enough um the statute says final decision and "
               "that's all yeah your honor the text is clear in gracia agree",
    "Delta": "we'll hear argument this morning in case seventeen twelve thirty four smith "
             "v jones mr gary chief justice and may it please the court the shevron "
             "doctrine the question here is whether certiorari should mr gary isn't twenty "
             "eight usc twelve ninety one enough i mean statute says final decision and "
             "that's all yes your honor the text is clear on garcias greece",
}

# Tables that depend only on the words. runs-used.csv names the temporary run
# folders, so it differs every time and is left out.
TABLES = ["heard-by.csv", "models-and-vote.csv", "shared-misses.csv",
          "hard-passages.csv", "against-the-record.csv", "interruptions.csv"]


def _make_run(runs: Path, name: str, text: str, recording: str) -> Path:
    folder = runs / f"run-{name.lower()}"
    (folder / "asr").mkdir(parents=True, exist_ok=True)
    (folder / "reference").mkdir(exist_ok=True)
    turns = [Turn(speaker=who, text=said, start=i * 10.0, end=i * 10.0 + 10.0)
             for i, (who, said) in enumerate(TURNS)]
    (folder / "reference" / f"{recording}.json").write_text(
        json.dumps(Transcript(docket=recording, turns=turns).to_dict()), encoding="utf-8")
    words = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.3}
             for i, w in enumerate(text.split())]
    (folder / "asr" / f"{recording}.engine-{name.lower()}.json").write_text(json.dumps({
        "docket": recording, "engine": f"engine-{name.lower()}", "model": name,
        "audio_seconds": 40.0,
        "segments": [{"index": 0, "start": 0.0, "end": 40.0, "text": text, "words": words}],
    }), encoding="utf-8")
    return folder


def test_crowd_tables_match_the_frozen_copy(tmp_path):
    runs = tmp_path / "runs"
    paths = {}
    for name, text in SAID.items():
        for recording in ("17-1234", "18-5678"):
            paths[name] = _make_run(runs, name, text, recording)
    out = tmp_path / "out"
    command = [sys.executable, str(CAPSTONE / "tools" / "crowd.py"), "--out", str(out)]
    for name, path in paths.items():
        command += ["--model", f"{name}={path}"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.mkdir(parents=True, exist_ok=True)
        for table in TABLES:
            (GOLDEN / table).write_bytes((out / table).read_bytes())
        pytest.skip("golden tables rewritten")

    # Line endings aside: git may turn the frozen copies' into Windows ones on checkout.
    def text(path: Path) -> bytes:
        return path.read_bytes().replace(b"\r\n", b"\n")

    for table in TABLES:
        assert text(out / table) == text(GOLDEN / table), table

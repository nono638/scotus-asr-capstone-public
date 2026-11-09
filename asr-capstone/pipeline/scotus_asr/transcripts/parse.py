"""Turning numbered lines into speaker turns.

The shape of the job, carried over from the earlier `parse_transcript.py`: walk the
numbered lines in order, start a new turn whenever a line begins with a speaker
label, and otherwise add the line to whoever is currently speaking.

Three things are done differently here, and each fixes a real defect.

**Section headings are no longer swallowed.** A transcript announces each
advocate with a heading like `ORAL ARGUMENT OF JANAI NELSON ON BEHALF OF
APPELLANTS`. Those sit on numbered lines, so the old parser added them to
whoever spoke last. Every sample transcript's first turn ends with one - the Chief
Justice appears to say "Ms. Nelson. ORAL ARGUMENT OF JANAI NELSON ON BEHALF OF
APPELLANTS PRESS ROBINSON, ET AL." He said the first two words. The rest is a
printed heading nobody spoke aloud, and scoring a model for failing to say it
would be scoring it for getting the answer right.

**Stage directions are kept.** `(Laughter.)` used to be dropped silently. Whether
a system reproduces these or quietly tidies them away is one of the things being
measured, so they are recorded against the turn they interrupt.

**Where every turn sits is recorded.** Page and line, start and end. When scoring
reports a missing span, this is what lets you open the PDF at the right page.
"""

from __future__ import annotations

import re
from pathlib import Path

from .extract import extract_lines
from .model import Event, Line, Transcript, Turn, classify_event
from .speakers import resolve_speakers
from ..scoring.rates import check_speaking_rate  # noqa: F401  (moved; kept importable here)

#: A line that begins a new turn. Anchored at the start of the line, after the
#: margin number has been removed, and restricted to the titles that actually
#: appear, so a mid-sentence colon ("It said:", "may it please the Court:") does
#: not start a spurious turn.
#:
#: The surname range runs past plain A-Z on purpose. Louisiana's Solicitor
#: General is J. Benjamin Aguinaga, spelled with an N-tilde, and the official
#: transcript spells it correctly 52 times. An A-Z-only pattern silently loses
#: all 48 of his turns - which is how this was found.
#:
#: À-Þ is the accented upper-case range of Latin-1, which covers the
#: names that actually turn up in these transcripts.
_LABEL = re.compile(
    r"^((?:CHIEF JUSTICE|JUSTICE|QUESTION|THE COURT|MR|MRS|MS|GENERAL|DEAN|PROF)"
    r"[A-ZÀ-Þ .'\-]{0,30}?):\s*(.*)$"
)

#: The printed heading that introduces each advocate. Not spoken.
_HEADING = re.compile(
    r"^(?:ORAL|REBUTTAL|CLOSING|SURREBUTTAL)\s+ARGUMENT\s+OF\b", re.IGNORECASE
)

#: The second half of a heading, when it runs onto the next line.
_HEADING_CONTINUES = re.compile(r"^(?:ON BEHALF OF|,?\s*ESQ\.?\b)", re.IGNORECASE)

#: A stage direction: something that happened rather than something said.
#:
#: This was a four-word list - Laughter, Pause, Recess, Applause - and across 138
#: transcripts it fired 408 times, of which 404 were `(Laughter.)`. The other
#: three never fired once. Anything the reporter wrote that was not on the list
#: went into the text as ordinary words and was scored as speech.
#:
#: So the rule is now shape rather than vocabulary: a whole line that is one
#: parenthesised phrase. The four words survive as a label in `classify_event`.
#:
#: Two details. The content must start with a letter and run to at least three
#: characters, which keeps statutory citations out - `(b)` and `(2)` are spoken
#: aloud and belong in the text. And a brace is accepted alongside a bracket,
#: because PyMuPDF rendered the opening parenthesis of one `(Laughter.)` as `{`,
#: after which it was counted as two words somebody said.
_EVENT = re.compile(r"^[({]\s*[A-Za-z][^)}]{2,79}[)}]\s*\.?\s*$")

#: Where the argument stops and the alphabetical keyword index begins. The index
#: lines also start with digits, so without this they are counted as speech and
#: the word total comes out roughly a sixth too high.
#:
#: A recess is the one "(Whereupon" that is not the end. In 20-1530 (West Virginia
#: v. EPA) the Court took "(Whereupon, a brief recess was taken.)" on page 64 of
#: 151, and stopping there threw away more than half the argument. It is the only
#: one of 1,037 transcripts with speech after a "(Whereupon" line.
_END = re.compile(r"\(Whereupon(?![^)]*recess)|was submitted\.\)|WAS SUBMITTED\.?\)")


def _is_heading(text: str, previous_was_heading: bool) -> bool:
    """Is this line part of a printed heading rather than speech?

    A heading may run onto a second line. The continuation is recognised by
    starting with "ON BEHALF OF", or by being entirely upper case immediately
    after a heading - transcript prose is mixed case, so all-capitals following a
    heading is the rest of that heading.
    """
    if _HEADING.match(text):
        return True
    if not previous_was_heading:
        return False
    if _HEADING_CONTINUES.match(text):
        return True
    # All capitals, and long enough that a shouted single word is not caught.
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(letters) > 3


def parse_lines(lines: list[Line], docket: str = "") -> Transcript:
    """Build a transcript from already-extracted numbered lines.

    Kept separate from reading the PDF so it can be tested on a handful of made-up
    lines without needing a file.

    Args:
        lines: Numbered lines, in reading order.
        docket: The case, recorded on the result.

    Returns:
        A `Transcript`. Turns with no words are dropped - a heading on its own
        does not make a turn.
    """
    transcript = Transcript(docket=docket)
    turns: list[Turn] = []
    current: Turn | None = None
    raw_labels: list[str] = []
    started = False          # has anyone spoken yet?
    in_heading = False

    for line in lines:
        text = line.text

        if _END.search(text):
            transcript.index_started_on_page = line.page
            # Recorded before stopping. `(Whereupon the case was submitted.)` is
            # a notation like any other, and until now only its page survived -
            # the words themselves appeared nowhere, neither as speech nor as an
            # event. It marks the end of the audio as well as the end of the
            # page, which is exactly where a model's last silence tends to fall.
            if current is not None:
                current.events.append(
                    Event(
                        text=text,
                        page=line.page,
                        line=line.number,
                        after_word=len(current.text.split()),
                        kind="end",
                    )
                )
            break

        if _is_heading(text, in_heading):
            in_heading = True
            continue
        in_heading = False

        match = _LABEL.match(text)
        if match:
            speaker, remainder = match.group(1).strip(), match.group(2).strip()
            current = Turn(
                speaker=speaker,
                text=remainder,
                start_page=line.page,
                start_line=line.number,
                end_page=line.page,
                end_line=line.number,
            )
            turns.append(current)
            raw_labels.append(speaker)
            started = True
            continue

        # Nothing before the first speaker counts. This is what keeps the cover
        # page, the appearance list and the table of contents out.
        if not started or current is None:
            continue

        if _EVENT.match(text):
            current.events.append(
                Event(
                    text=text,
                    page=line.page,
                    line=line.number,
                    # Where in this turn the notation falls. A line number alone
                    # cannot say: a turn interrupted by laughter and then resumed
                    # puts the event in the middle, and placing it at the end
                    # would put it after words that were spoken before it.
                    after_word=len(current.text.split()),
                    kind=classify_event(text),
                )
            )
            continue

        current.text = f"{current.text} {text}".strip() if current.text else text
        current.end_page = line.page
        current.end_line = line.number

    transcript.turns = [turn for turn in turns if turn.text]

    if raw_labels:
        mapping, warnings = resolve_speakers(raw_labels)
        for turn in transcript.turns:
            turn.speaker_normalized = mapping.get(turn.speaker, turn.speaker)
        transcript.warnings.extend(warnings)

    return transcript


def parse_transcript(pdf_path: Path | str, docket: str = "") -> Transcript:
    """Read a transcript PDF into speaker turns.

    Args:
        pdf_path: The official transcript.
        docket: The case. Taken from the filename if not given.

    Returns:
        A `Transcript` with turns, provenance and any warnings.

    Raises:
        FileNotFoundError: If the PDF is not there.
        ValueError: If no numbered lines were found at all, which means the PDF
            is a scan and needs the OCR path instead.
    """
    pdf_path = Path(pdf_path)
    if not docket:
        # Files are named like `09-834_transcript.pdf`.
        docket = pdf_path.stem.split("_")[0]

    pages, page_count = extract_lines(pdf_path)
    lines = [line for page in pages for line in page.lines]

    if not lines:
        raise ValueError(
            f"{pdf_path.name} has no numbered lines. It is probably a scan "
            f"rather than a text PDF, so it needs the OCR path."
        )

    transcript = parse_lines(lines, docket=docket)
    transcript.source_pdf = str(pdf_path)
    transcript.page_count = page_count

    if transcript.index_started_on_page is None:
        transcript.warnings.append(
            "Never found the end of the argument, so the alphabetical index may "
            "have been counted as speech. Expect the word count to be too high."
        )

    return transcript

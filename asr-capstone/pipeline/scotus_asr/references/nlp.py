"""Rev's NLP format: one token per line, with its speaker and punctuation.

Rev ships its own datasets this way (Earnings-21, Earnings-22) and its scorer,
fstalign, reads it. A header row names the columns, split by `|`:

    token|speaker|ts|endTs|punctuation|prepunctuation|case|tags
    Good|0|||||UC|[]
    morning|0|||||LC|[]
    Call|0|||.||UC|[]

Rev's README documents a slightly different set of columns from the files that
are actually published (`prepunctuation` is there, `wer_tags` is not), so the
columns are found by name. The token already carries its capitals; a word as
written is the prepunctuation, the token and the punctuation joined. Times are
empty in the plain references, so the turns here have none - scored whole, the
way the Supreme Court arguments are.

**Tags.** Tokens in angle brackets - `<inaudible>`, `<crosstalk>`, `<unk>`,
`<foreign>`, `<laugh>`, `<affirmative>`, `<silence>` - stand for something that
is not a word to score, and are dropped. With no times there is no stretch to
leave out, so whatever an engine writes over an `<inaudible>` counts as an extra
word. fstalign lets any word match `<unk>`; that is not copied here. A handful
per call, against about 10,000 words.

Cut-off words (`question-`) keep their hyphen, as the reference writes them; the
benchmark rule's normaliser decides what to do with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..transcripts.model import Transcript, Turn


@dataclass(frozen=True)
class NlpToken:
    """One token: the word as written (with its punctuation), and who said it."""

    speaker: str
    word: str

    @property
    def is_tag(self) -> bool:
        return self.word.strip(".,?!…:;\"'").startswith("<")


def read_nlp(path: Path, encoding: str = "utf-8") -> list[NlpToken]:
    """Every token of an NLP file, in order.

    Raises:
        ValueError: If the token or speaker column is missing, naming the ones
            there are.
    """
    path = Path(path)
    lines = path.read_text(encoding=encoding).splitlines()
    header = lines[0].split("|") if lines else []
    if "token" not in header or "speaker" not in header:
        raise ValueError(f"{path}: needs token and speaker columns; the header has {header}")
    at = {name: header.index(name) for name in header}

    def field(fields: list[str], name: str) -> str:
        return fields[at[name]] if name in at and at[name] < len(fields) else ""

    tokens = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("|")
        word = field(fields, "prepunctuation") + field(fields, "token") + field(fields, "punctuation")
        tokens.append(NlpToken(speaker=field(fields, "speaker"), word=word))
    return tokens


def nlp_to_transcript(recording_id: str, tokens: Iterable[NlpToken], source: str = "") -> Transcript:
    """Join each speaker's run of tokens into a turn, leaving out the tags."""
    transcript = Transcript(docket=recording_id, source_pdf=source)
    speaker, words = None, []

    def close() -> None:
        if words:
            transcript.turns.append(Turn(speaker=speaker, text=" ".join(words),
                                         speaker_normalized=speaker))

    for token in tokens:
        if token.is_tag:
            continue
        if token.speaker != speaker:
            close()
            speaker, words = token.speaker, []
        words.append(token.word)
    close()
    return transcript

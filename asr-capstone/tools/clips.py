"""Cutting short audio clips from the Supreme Court recordings, for any page that plays them.

The listening bench, the website's gallery and Figure 1's dots all play short clips
with the words highlighted as they are spoken. They cut them the same way, here:
read only the stretch needed from the argument's MP3, average it to mono and write
it as an MP3 beside the page.

Only Supreme Court audio is cut here: it is public domain, so the clips can go on a
page. Other corpora have their own licences.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import soundfile as sf

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.config import local_path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lineup import SCOTUS_RUNS  # noqa: E402


#: The run each default engine's words come from, by term (see tools/lineup.py).
RUNS = SCOTUS_RUNS


def run_for(engine: str, term: str):
    """The ModelRun holding `engine`'s transcripts for `term`."""
    from scotus_asr.model_sets import _model
    runs = RUNS[engine]
    return _model(engine, runs.get(term, runs["*"]), runs_dir())


def file_name(run, docket: str, term: str) -> str:
    """Most dockets are files of their own; a re-argued one carries its term."""
    docket = docket.split("_")[0]
    return docket if run.asr_file(docket).exists() else f"{docket}_{term}"


def runs_dir() -> Path:
    """The Supreme Court runs, wherever local-paths.yaml says the corpus is."""
    return local_path("scotus_corpus") / "runs"


def cases_dir() -> Path:
    """The case folders (audio and transcripts), from local-paths.yaml."""
    return local_path("scotus_corpus") / "cases"


def case_folder(docket: str, term: str) -> Path:
    """The folder of one argument. A re-argued case ("15-1204_OT2017") has one per term."""
    docket = docket.split("_")[0]
    return sorted(cases_dir().glob(f"{term}_{docket}_*"))[0]


def audio_for(docket: str, term: str) -> Path:
    return next(case_folder(docket, term).glob("*_audio.mp3"))


def case_name(docket: str, term: str) -> str:
    return case_folder(docket, term).name.split("_", 2)[2].replace("_", " ")


def cut_clip(audio: Path, start: float, end: float, out: Path) -> None:
    """Write `start`..`end` seconds of `audio` to `out` as a mono MP3.

    Constant bit rate (about 48 kbps), so a browser jumps to the right word when
    a page seeks inside the clip; a 30-second clip comes to about 200 KB.
    """
    rate = sf.info(audio).samplerate
    data, sr = sf.read(audio, start=int(max(0.0, start) * rate), stop=int(end * rate), always_2d=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, data.mean(axis=1), sr, format="MP3", compression_level=0.95, bitrate_mode="CONSTANT")


#: The two lengths every card offers, in seconds, and how far each edge may move
#: to land between two sentences instead of in the middle of one.
SHORT, LONG, SLACK = 15.0, 30.0, 5.0
#: A pause this long counts as a break between sentences, for speech an engine
#: did not punctuate.
PAUSE = 0.7


def sentence_breaks(word_lists) -> list[tuple[float, float, bool]]:
    """Places to cut between sentences, as (end of one sentence, start of the next, full stop?).

    A break comes after a word ending in . ? or ! (a full stop: True), or at a
    pause of PAUSE seconds (False), in any of the engines' timed word lists given.
    """
    out = []
    for words in word_lists:
        timed = [w for w in words if w.start is not None and w.end is not None and w.text.strip()]
        for w, nxt in zip(timed, timed[1:]):
            stop = w.text.strip().endswith((".", "?", "!"))
            if stop or nxt.start - w.end >= PAUSE:
                out.append((w.end, nxt.start, stop))
    return sorted(out)


def snap_window(start: float, end: float, length: float, breaks, duration: float) -> tuple[float, float]:
    """A window of about `length` seconds around start..end that begins and ends
    between sentences where it can.

    Each edge may move up to SLACK seconds. When there is a break both inside and
    outside an edge, the outside one wins, so the clip runs a little longer rather
    than cutting a sentence short. A full stop beats a pause. The case itself
    always stays inside, with a second and a half to spare.
    """
    middle = (start + end) / 2
    a = min(middle - length / 2, start - 1.5)
    b = max(middle + length / 2, end + 1.5)
    # Start just before the next sentence's first word; end just after the last word.
    lefts = [(max(prev, nxt - 0.3), stop) for prev, nxt, stop in breaks]
    rights = [(min(nxt, prev + 0.4), stop) for prev, nxt, stop in breaks]

    def pick(edge: float, options: list[tuple[float, bool]], outside) -> float:
        if not options:
            return edge
        options = [x for x, stop in options if stop] or [x for x, _ in options]
        pool = [o for o in options if outside(o)] or options
        return min(pool, key=lambda o: abs(o - edge))

    a = pick(a, [(x, f) for x, f in lefts if a - SLACK <= x <= min(a + SLACK, start - 1.0)], lambda x: x <= a)
    b = pick(b, [(x, f) for x, f in rights if max(b - SLACK, end + 1.0) <= x <= b + SLACK], lambda x: x >= b)
    return max(0.0, a), min(duration, b)


def timed_words(words, start: float, end: float, wrong: set[int] | None = None) -> list[list]:
    """An engine's words that start inside a clip, as [text, start, end] in clip time.

    `wrong` holds the indexes of words that differ from the record; those get a
    fourth item, 1, so the page can mark them.
    """
    out = []
    for i, w in enumerate(words):
        if w.start is None or w.end is None or not (start <= w.start < end):
            continue
        item = [w.text.strip(), round(w.start - start, 2), round(w.end - start, 2)]
        if wrong is not None and i in wrong:
            item.append(1)
        if item[0]:
            out.append(item)
    return out


def join_hyphen_pieces(items: list[list]) -> list[list]:
    """Whisper's timed words with a split hyphen joined back: ["dope", ...] and
    ["-themed", ...] become one word, "dope-themed", lasting from the first's
    start to the second's end, marked wrong if either piece was."""
    out = []
    for item in items:
        if out and re.match(r"-[\w$]", item[0]) and re.search(r"[\w%$]$", out[-1][0]):
            prev = out[-1]
            prev[0] += item[0]
            prev[2] = item[2]
            if len(item) > 3 and item[3] and len(prev) == 3:
                prev.append(item[3])
        else:
            out.append(list(item))
    return out


def timed_reference(words: list[str], times: list[float], start: float, end: float,
                    marked: set[int]) -> list[list]:
    """The record's words inside a clip, timed like an engine's.

    The record has no times of its own; `times` are the ones borrowed from the
    engines (lineup.reference_times), and each word lasts until the next begins.
    Words in `marked` (the passage the card is about) get a fourth item, 2.
    """
    out = []
    for i, (word, t) in enumerate(zip(words, times)):
        if not (start <= t < end):
            continue
        nxt = times[i + 1] if i + 1 < len(times) and times[i + 1] > t else t + 0.4
        item = [word, round(t - start, 2), round(min(nxt, t + 1.5) - start, 2)]
        if i in marked:
            item.append(2)
        out.append(item)
    return out

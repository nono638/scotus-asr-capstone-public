"""Audio clips for the most serious rows of the website's data page.

Which rows: Sonnet called the meaning opposite, or gave severity 3 or 4, in a data
set whose audio may be published (not Earnings-22, which has no stated licence).

Each clip runs about 15 seconds and ends between sentences where it can, the same way
as the cards (clips.snap_window). The host allows 511 files a page, so the clips are
not separate files: they are joined into Ogg Opus files under its 15 MB limit, half a
second of silence between them, and the page jumps to the right place in one of those.

    python tools/build_data.py              # first: site/data/errors.csv
    python tools/build_row_clips.py         # writes the two below
    python tools/build_site.py

Writes site/clips/rows/<data set>-NN.ogg and site/data/row-clips.json, which gives
each case its file and where its clip starts and ends. Needs the corpora and the runs,
so the 5090 laptop, but only the processor, not the card.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pandas as pd
import soundfile as sf

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clips  # noqa: E402
import lineup  # noqa: E402

SITE = CAPSTONE / "site"
OUT = SITE / "clips" / "rows"
INDEX = SITE / "data" / "row-clips.json"

PUBLISHABLE = ("scotus", "edacc", "coraal")
#: 24 kbps is about the same quality for speech as the cards' 48 kbps MP3, at half the size.
KBPS = 24
RATE = 24000
#: A file holds this much audio: about 13.5 MB at 24 kbps, under the host's 15 MB.
MAX_SECONDS = 4500
GAP = 0.5
#: A row longer than this, in seconds, has no real time. The longest real one is under 25.
MAX_SPAN = 120


def serious_rows(limit: int | None) -> pd.DataFrame:
    e = pd.read_csv(SITE / "data" / "errors.csv", dtype=str, keep_default_na=False)
    severity = pd.to_numeric(e.sonnet_severity, errors="coerce")
    rows = e[e.corpus.isin(PUBLISHABLE) & ((e.sonnet_meaning == "opposite") | (severity >= 3))]
    # A case gone after the repair is no longer in the transcript the page shows.
    rows = rows[~rows.not_counted.str.startswith("gone")]
    # Rows whose place the search lost have no time in errors.csv (build_data.py), and a
    # few "edits" rows run from 0 to far into the recording: nobody knows where to cut.
    # Better no clip than the wrong one.
    span = pd.to_numeric(rows.end, errors="coerce") - pd.to_numeric(rows.start, errors="coerce")
    unknown = rows[span.isna() | (span > MAX_SPAN)]
    if len(unknown):
        print(f"No clip, as their times are not real: {', '.join(unknown.case)}", flush=True)
    rows = rows[span.notna() & (span <= MAX_SPAN)]
    return rows.sample(limit, random_state=2027) if limit else rows


def row_windows(rows: pd.DataFrame, job: dict) -> list[tuple[str, float, float]]:
    """(case, start, end) of each row's clip in this recording, snapped like a card's."""
    lined = lineup.load(job)
    duration = sf.info(job["audio"]).duration
    breaks: dict[tuple, list] = {}
    out = []
    for r in rows.itertuples():
        start, end = float(r.start), float(r.end)
        right = [x for x in r.others_right.split() if x in lined and x != r.engine]
        other = right[:1] or [x for x in ("Qwen3", "Whisper", "Parakeet") if x in lined and x != r.engine][:1]
        shown = tuple(x for x in [r.engine, *other] if x in lined)
        if shown not in breaks:
            breaks[shown] = clips.sentence_breaks([lined[x][3] for x in shown])
        a, b = clips.snap_window(start, end, clips.SHORT, breaks[shown], duration)
        out.append((r.case, a, b))
    return out


def merged(windows: list[tuple[str, float, float]]) -> list[tuple[float, float, list]]:
    """Overlapping clips share one stretch of audio: (start, end, the clips in it)."""
    spans: list[tuple[float, float, list]] = []
    for w in sorted(windows, key=lambda x: x[1]):
        if spans and w[1] <= spans[-1][1]:
            a, b, inside = spans[-1]
            spans[-1] = (a, max(b, w[2]), inside + [w])
        else:
            spans.append((w[1], w[2], [w]))
    return spans


class AudioFile:
    """One Ogg Opus file that stretches of audio are added to, end to end."""

    def __init__(self, path: Path):
        self.path = path
        self.part = path.with_suffix(".part.ogg")
        self.out = av.open(str(self.part), "w", format="ogg")
        self.stream = self.out.add_stream("libopus", rate=RATE)
        self.stream.bit_rate = KBPS * 1000
        self.stream.layout = "mono"
        self.samples = 0

    @property
    def seconds(self) -> float:
        return self.samples / RATE

    def _write(self, piece) -> None:
        piece.pts = self.samples
        piece.time_base = Fraction(1, RATE)
        self.samples += piece.samples
        for packet in self.stream.encode(piece):
            self.out.mux(packet)

    def add(self, data: np.ndarray, rate: int) -> None:
        """Add mono audio. A new resampler each time, as sources differ in rate."""
        frame = av.AudioFrame.from_ndarray(data.astype(np.float32)[np.newaxis, :], format="fltp", layout="mono")
        frame.sample_rate = rate
        resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        for piece in resampler.resample(frame):
            self._write(piece)
        for piece in resampler.resample(None):
            self._write(piece)

    def add_silence(self, seconds: float) -> None:
        self.add(np.zeros(int(seconds * RATE), dtype=np.float32), RATE)

    def close(self) -> None:
        for packet in self.stream.encode(None):
            self.out.mux(packet)
        self.out.close()
        self.part.replace(self.path)


def build(limit: int | None) -> tuple[dict, list]:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.ogg"):    # a smaller build must not leave files from a bigger one
        old.unlink()
    rows = serious_rows(limit)
    print(f"{len(rows)} rows get a clip: {rows.groupby('corpus').size().to_dict()}", flush=True)
    files: list[str] = []
    index: dict[str, list] = {}
    placed: list[tuple] = []     # for the check afterwards

    for corpus in PUBLISHABLE:
        jobs = {(j["term"], j["docket"]): j for j in lineup.recordings(corpus)}
        current, number = None, 0
        groups = list(rows[rows.corpus == corpus].groupby(["part", "recording"]))
        for done, (key, group) in enumerate(groups, 1):
            job = jobs.get(key)
            if job is None:
                print(f"  {corpus} {key} not found: {len(group)} rows left without a clip", flush=True)
                continue
            rate = sf.info(job["audio"]).samplerate
            for a, b, inside in merged(row_windows(group, job)):
                if current is None or current.seconds >= MAX_SECONDS:
                    if current:
                        current.close()
                    number += 1
                    name = f"{corpus}-{number:02d}.ogg"
                    current = AudioFile(OUT / name)
                    files.append(f"clips/rows/{name}")
                data, _ = sf.read(job["audio"], start=int(a * rate), stop=int(b * rate), always_2d=True)
                at = current.seconds
                current.add(data.mean(axis=1), rate)
                current.add_silence(GAP)
                for case, x, y in inside:
                    index[case] = [len(files) - 1, round(at + x - a, 2), round(at + y - a, 2)]
                    placed.append((case, job["audio"], x, y))
            if done % 25 == 0 or done == len(groups):
                print(f"  {corpus}: {done} of {len(groups)} recordings, file {number}", flush=True)
        if current:
            current.close()

    INDEX.write_text(json.dumps({"kbps": KBPS, "files": files, "rows": index}, separators=(",", ":")), encoding="utf-8")
    return {"files": files, "rows": index}, placed


def decoded(path: Path) -> np.ndarray:
    with av.open(str(path)) as f:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=RATE)
        parts = [p.to_ndarray().ravel() for frame in f.decode(audio=0) for p in resampler.resample(frame)]
    return np.concatenate(parts)


def check_clips(built: dict, placed: list, how_many: int = 40) -> int:
    """Does each sampled clip's place in the file really hold that moment of the recording?

    Compares the file's audio with the source's, so a wrong offset can't pass. Silence
    has nothing to compare, so quiet clips are skipped rather than counted as a pass.
    """
    files = {i: decoded(SITE / f) for i, f in enumerate(built["files"])}
    failed, compared = 0, 0
    for case, audio, a, b in random.Random(2027).sample(placed, min(how_many, len(placed))):
        f, x, y = built["rows"][case]
        rate = sf.info(audio).samplerate
        source, _ = sf.read(audio, start=int(a * rate), stop=int(b * rate), always_2d=True)
        source = source.mean(axis=1)
        # Both at RATE, by picking samples: rough, but enough to line two signals up.
        source = source[np.linspace(0, len(source) - 1, int((b - a) * RATE)).astype(int)]
        clip = files[f][int(x * RATE):int(x * RATE) + len(source)]
        n = min(len(source), len(clip))
        if n < RATE or source[:n].std() < 1e-3:
            continue
        compared += 1
        corr = np.correlate(np.abs(clip[:n:8]) - np.abs(clip[:n:8]).mean(),
                            np.abs(source[:n:8]) - np.abs(source[:n:8]).mean(), "same")
        lag = (int(corr.argmax()) - len(corr) // 2) * 8 / RATE
        if abs(lag) > 0.1:
            failed += 1
            print(f"  FAIL {case}: its clip is {lag:+.2f} s off", flush=True)
    print(f"Checked {compared} clips against the source audio: {failed} off by more than 0.1 s", flush=True)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only this many rows, picked at random: for a trial")
    args = parser.parse_args()
    built, placed = build(args.limit)
    sizes = [(SITE / f).stat().st_size for f in built["files"]]
    print(f"{len(built['rows'])} rows, {len(sizes)} files, {sum(sizes) / 1e6:.1f} MB; "
          f"largest file {max(sizes) / 1e6:.1f} MB", flush=True)
    lengths = [y - x for _, x, y in built["rows"].values()]
    print(f"Clip length: median {np.median(lengths):.1f} s, longest {max(lengths):.1f} s", flush=True)
    return 1 if check_clips(built, placed) or max(sizes) >= 15e6 else 0


if __name__ == "__main__":
    raise SystemExit(main())

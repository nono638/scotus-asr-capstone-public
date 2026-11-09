"""Build the whole-recording pages: every recording of a data set, start to finish.

The website (tools/build_site.py) shows the clearest failures. These pages show
everything behind them, one data set to a page: pick any recording, then read the
reference and every engine's transcript side by side, 30 seconds at a time, with
every case the failure searches found highlighted before you reach it. Where the
recording's audio is on the page, the words light up as it plays, and the player
can step from one highlighted error to the next.

Writes asr-capstone/explorer/<data set>/ (ignored by git apart from index.html):

    index.html            the page: a picker and a recording view
    catalog.json          one row per recording, for the picker
    rec/<shard>.txt       the transcripts, three recordings to a file (gzip, as base64)
    audio/<id>.ogg        full audio, Opus at 14 kbps, for as many recordings as fit
    local-audio.json      where each recording's audio is on this laptop; read by
                          tools/explore_local.py, never published

Why one page per data set: a published page may hold 256 MB and 511 files. At
about 6.5 MB an hour, Opus fits roughly 30 hours beside the Supreme Court's
transcripts, 35 beside CORAAL's and all 36 of EdAcc's; one page for everything
would hold a quarter of that. Which recordings get their audio: the ones the
website's cards come from first, then the ones with the most errors the judges
called serious, one from each part before a second from any.

Why three recordings to a file and times as gaps between words: the file limit,
and small numbers compress far better (about 130 KB a recorded hour).

The audio licences decide what is published: Supreme Court audio is public
domain, EdAcc's is CC BY-SA 4.0 and CORAAL's CC BY-NC-SA 4.0 (credited on the
page); Earnings-22's audio has no stated licence, so its page is text only.
Run tools/build_data.py first: the error rates come from site/data/recordings.csv.

    python tools/build_explorer.py scotus      # one data set (or several)
    python tools/build_explorer.py             # all four
    python tools/build_explorer.py --no-audio  # skip encoding the audio
"""

from __future__ import annotations

import argparse
import base64
import functools
import bisect
import gzip
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lineup  # noqa: E402

CAPSTONE = lineup.CAPSTONE
FINDINGS = CAPSTONE / "findings"
EXPLORER = CAPSTONE / "explorer"
PAGE = CAPSTONE / "tools" / "explorer_page"
WIDGETS = CAPSTONE / "web" / "widget"
SITE_PAGE = CAPSTONE / "tools" / "site_page"

NAMES = {"scotus": "Supreme Court", "edacc": "EdAcc", "coraal": "CORAAL", "earnings22": "Earnings-22"}
PART_LABELS = {"test": "Test", "dev": "Dev", "ROC": "Rochester", "PRV": "Princeville",
               "DCB": "Washington DC", "DCA": "Washington DC 1968", "DTA": "Detroit",
               "ATL": "Atlanta", "VLD": "Valdosta", "LES": "Lower East Side"}
#: Audio that may be published, by data set (see the licences above).
PUBLISHABLE = {"scotus", "edacc", "coraal"}
#: Megabytes of audio and transcripts on one page; the host takes 256.
BUDGET_MB = 245
OPUS_KBPS = 14
PER_SHARD = 3
KINDS = ["meaning", "invented", "edits", "skips"]


# --- scores and failure cases ----------------------------------------------------

def scores(corpus: str) -> dict:
    """{recording: {engine: {benchmark, swapped, dropped, added}}}, all in percent,
    from site/data/recordings.csv (tools/build_data.py)."""
    t = pd.read_csv(CAPSTONE / "site" / "data" / "recordings.csv", dtype={"recording": str})
    t = t[t.corpus == corpus]
    out: dict = {}
    for r in t.itertuples():
        n = r.reference_words or 1
        out.setdefault(r.recording, {})[r.engine] = {
            "benchmark": r.error_rate, "swapped": round(100 * r.substituted / n, 2),
            "dropped": round(100 * r.dropped / n, 2), "added": round(100 * r.added / n, 2)}
    return out


def section(kind: str, subkind: str, sonnet: str, severity: float) -> str:
    """Which of the website's sections a case belongs to; "minor" for a plain
    mishearing, which is highlighted more quietly."""
    if kind != "meaning":
        return kind
    if sonnet:
        if sonnet == "opposite":
            return "opposite"
        return "fact" if sonnet == "changed" and severity >= 3 else "minor"
    return {"negation": "opposite", "number": "fact"}.get(subkind, "minor")


def failure_cases(corpus: str) -> dict:
    """{(part, recording): [case, ...]}: every case the four failure searches found,
    with what the judges said about it."""
    import build_site
    t = build_site.judged()
    # A case gone after the repair has no place left in the transcript to mark.
    t = t[(t.corpus == corpus) & (t.source == "candidates") & ~t.not_counted.str.startswith("gone")]
    notes = {}
    for kind in KINDS:
        short = pd.read_csv(FINDINGS / "failures" / kind / "shortlist.csv", dtype=str, keep_default_na=False)
        for r in short[short.corpus == corpus].itertuples():
            notes[(r.recording, r.engine, round(float(r.start), 2))] = r.explanation
    out: dict = {}
    for r in t.itertuples():
        severity = r.s_severity if pd.notna(r.s_severity) else -1
        case = {"kind": r.kind, "sub": r.subkind, "engine": r.engine, "s": round(float(r.start), 2),
                "e": round(float(r.end), 2), "record": r.record, "wrote": r.engine_wrote, "why": r.evidence,
                "sec": section(r.kind, r.subkind, r.s_meaning, severity)}
        if r.s_meaning:
            case["judge"] = f"Sonnet: {r.s_meaning}, severity {int(severity)} of 4" + (f"; Qwen: {r.q_meaning}" if r.q_meaning else "")
        elif r.q_meaning:
            case["judge"] = f"Qwen: {r.q_meaning}"
        note = notes.get((r.recording, r.engine, round(float(r.start), 2)))
        if note:
            case["note"] = note
        out.setdefault((r.part, r.recording), []).append(case)
    return out


def mark_reference(cases: list[dict], ref_words: list[str], ref_time: list[float]) -> None:
    """Give each case the reference words it is about ("ri": [first, last + 1]),
    found by their text near the case's time, as the website's cards find them."""
    from build_site import plain
    flat = [plain(w) for w in ref_words]
    for c in cases:
        want = [plain(w) for w in str(c["record"]).split() if plain(w)]
        if not want:
            continue
        lo = bisect.bisect_left(ref_time, c["s"] - 30)
        hi = bisect.bisect_right(ref_time, c["e"] + 30)
        hits = [i for i in range(lo, max(lo, hi - len(want) + 1)) if flat[i:i + len(want)] == want]
        if hits:
            best = min(hits, key=lambda i: abs(ref_time[i] - c["s"]))
            c["ri"] = [best, best + len(want)]


# --- one recording -------------------------------------------------------------

def gaps(values: list[int]) -> list[int]:
    out, last = [], 0
    for v in values:
        out.append(v - last)
        last = v
    return out


def one_word(text: str) -> str:
    """A word as one token: the page splits each line on spaces, so any space
    inside a word becomes a no-break space, and an empty word a middle dot."""
    return re.sub(r"\s+", " ", text.strip()) or "·"


def transcripts(job: dict) -> tuple[dict, list[str], list[float]]:
    """The reference and every engine's words, lined up, in the page's compact form,
    and the reference's words with their times (for marking the cases).

    Engine words carry their own times. The reference's words borrow theirs
    (lineup.reference_times): the Supreme Court's record has no times of its own.
    """
    lined = lineup.load(job)
    names = list(lined)
    transcript, ref_words, _, _ = lined[names[0]]
    n = len(ref_words)
    ref_time = lineup.reference_times(lined)
    missed = [0] * n
    engines = {}
    for name in names:
        _, _, al, words = lined[name]
        rs, hs = al.reference.source_index, al.hypothesis.source_index
        off = [0] * len(words)
        got = set()
        # A word the scoring drops ("um", a stage direction) is not compared, so
        # no engine can have missed it.
        scored = set(rs)
        for c in al.chunks:
            if c.kind == "equal":
                for i in range(c.ref_start, c.ref_end):
                    got.add(rs[i])
            else:
                for j in range(c.hyp_start, c.hyp_end):
                    off[hs[j]] = 1
        for k in scored - got:
            missed[k] += 1
        starts = [round((w.start or 0) * 100) for w in words]
        engines[name] = {
            "t": " ".join(one_word(w.text) for w in words),
            "s": gaps(starts),
            "d": [max(0, round((w.end or 0) * 100) - s) for w, s in zip(words, starts)],
            "off": "".join(map(str, off)),
        }
    turn_of = lineup.word_turns(transcript)
    data = {
        "ref": {"t": " ".join(one_word(w) for w in ref_words), "s": gaps([round(x * 100) for x in ref_time]),
                # [word, turn] wherever a new turn starts, so a turn with no
                # words in it does not shift the speaker names after it.
                "turns": [[i, turn_of[i]] for i in range(len(turn_of)) if i == 0 or turn_of[i] != turn_of[i - 1]],
                "speakers": [t.speaker for t in transcript.turns],
                "missed": "".join(map(str, missed))},
        "engines": engines,
    }
    return data, ref_words, ref_time


def files_of(job: dict, entry: dict | None) -> list[dict]:
    """Every file behind one recording: where it is on the 5090 laptop, and links."""
    out = [{"what": "Audio", "path": str(job["audio"]), "audio": True}]
    first = job["models"][0]
    if job["corpus"] == "scotus" and entry:
        pdf = job["audio"].parent / f"{entry['docket']}_transcript.pdf"
        out.append({"what": "The Court's transcript (PDF)", "path": str(pdf), "url": entry["transcript_url"]})
        out.append({"what": "The Court's audio (MP3)", "url": entry["audio_url"]})
    elif entry and entry.get("extra", {}).get("transcript"):
        out.append({"what": "The corpus's own transcript", "path": entry["extra"]["transcript"]})
    out.append({"what": "The reference, as read by the pipeline", "path": str(first.reference_file(job["docket"]))})
    for m in job["models"]:
        out.append({"what": f"{m.name}: its transcript", "path": str(m.asr_file(job["docket"])), "engine": m.name})
        out.append({"what": f"{m.name}: the run's scores", "path": str(m.run_dir / "results" / "scores.csv"),
                    "engine": m.name})
    return out


def describe(path: Path) -> str:
    """The line a README in the same folder (or the one above) gives this file."""
    for readme in [path.parent / "README.md", path.parent.parent / "README.md"]:
        if not readme.exists():
            continue
        name = re.escape(path.name)
        rel = re.escape(path.relative_to(readme.parent).as_posix())
        for line in readme.read_text(encoding="utf-8").splitlines():
            m = (re.match(rf"\|\s*`(?:{name}|{rel})`\s*\|\s*(.+?)\s*\|", line)
                 or re.match(rf"\s*[-*]\s*`(?:{name}|{rel})`\s*[-:–]+\s*(.+)", line))
            if m:
                return re.sub(r"`", "", m.group(1)).strip()
    return ""


# --- audio --------------------------------------------------------------------------

def encode(source: Path, out: Path) -> None:
    """The whole recording as 16 kHz mono Opus at OPUS_KBPS: clear speech, about 6.5 MB an hour."""
    import av
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part.ogg")
    with av.open(str(source)) as src, av.open(str(part), "w", format="ogg") as dst:
        stream = dst.add_stream("libopus", rate=16000)
        stream.bit_rate = OPUS_KBPS * 1000
        stream.layout = "mono"
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in src.decode(audio=0):
            for piece in resampler.resample(frame):
                for packet in stream.encode(piece):
                    dst.mux(packet)
        for piece in resampler.resample(None):
            for packet in stream.encode(piece):
                dst.mux(packet)
        for packet in stream.encode(None):
            dst.mux(packet)
    part.replace(out)


def card_recordings(corpus: str) -> dict[str, int]:
    """How many of the website's cards come from each recording of a data set: the ones on
    its page, since the file of cut clips also holds cards that have since been retired."""
    import build_site
    path = CAPSTONE / "site" / build_site.DATASETS[corpus]["file"]
    got: dict[str, int] = {}
    if path.exists():
        html = path.read_text(encoding="utf-8")
        data = json.JSONDecoder().raw_decode(html, html.index("const D = ") + len("const D = "))[0]
        for section in data["failures"]:
            for c in section["cards"]:
                got[str(c["recording"])] = got.get(str(c["recording"]), 0) + 1
    return got


def pick_audio(rows: list[dict], room_mb: float, cards: dict[str, int]) -> list[dict]:
    """The recordings whose audio goes on the page, until room_mb is used: the
    website's card recordings first, then the most serious errors, a part at a time."""
    def size(r):
        return r["min"] * 60 * OPUS_KBPS * 1000 / 8 / 1e6 * 1.03

    order = sorted(rows, key=lambda r: (-cards.get(r["id"], 0), -r["serious"], r["min"]))
    first = [r for r in order if cards.get(r["id"])]
    by_part: dict[str, list] = {}
    for r in order:
        if not cards.get(r["id"]):
            by_part.setdefault(r["p"], []).append(r)
    turns = []
    while any(by_part.values()):
        for part in by_part:
            if by_part[part]:
                turns.append(by_part[part].pop(0))
    chosen, used = [], 0.0
    for r in first + turns:
        if used + size(r) <= room_mb:
            chosen.append(r)
            used += size(r)
    return chosen


# --- the page --------------------------------------------------------------------------

def page(data: dict) -> str:
    html = (PAGE / "explorer.html").read_text(encoding="utf-8")
    for name in ["table", "credits"]:
        html = html.replace(f"/*{name.upper()}*/", (WIDGETS / f"{name}.js").read_text(encoding="utf-8"))
    return (html.replace("/*TOKENS*/", (WIDGETS / "tokens.css").read_text(encoding="utf-8"))
                .replace("/*TITLE*/", f"{NAMES[data['corpus']]} Recordings")
                .replace("/*SITECSS*/", (SITE_PAGE / "site.css").read_text(encoding="utf-8"))
                .replace("/*EXPLORERCSS*/", (PAGE / "explorer.css").read_text(encoding="utf-8"))
                .replace("/*EXPLORERJS*/", (PAGE / "explorer.js").read_text(encoding="utf-8"))
                .replace("/*DATA*/{}", json.dumps(data, ensure_ascii=False)))


def build(corpus: str, no_audio: bool) -> None:
    import build_site
    out = EXPLORER / corpus
    table = scores(corpus)
    cases = failure_cases(corpus)
    cards = card_recordings(corpus)
    manifest = {e["case_id"]: e for e in json.loads(
        (lineup.scotus_root() / "cases" / "manifest.json").read_text(encoding="utf-8"))} if corpus == "scotus" else {}
    index = {}
    if corpus != "scotus":
        for line in (lineup.corpus_root(corpus) / "recordings.jsonl").read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            index[e["id"]] = e

    if (out / "rec").exists():
        shutil.rmtree(out / "rec")
    (out / "rec").mkdir(parents=True)
    catalog, local_audio, shard, shard_name = [], {}, {}, ""
    jobs = lineup.recordings(corpus)
    for number, job in enumerate(jobs):
        if number % PER_SHARD == 0:
            if shard:
                write_shard(out / shard_name, shard)
            shard_name, shard = f"rec/{number // PER_SHARD + 1:03d}.txt", {}
        rid = job["docket"]
        entry = manifest.get(rid) if corpus == "scotus" else index.get(rid)
        found = cases.get((job["term"], rid), [])
        data, ref_words, ref_time = transcripts(job)
        mark_reference(found, ref_words, ref_time)
        seconds = (sf.info(job["audio"]).duration if corpus == "scotus" else float(entry["duration"]))
        data["cases"] = found
        data["files"] = files_of(job, entry)
        shard[rid] = data
        local_audio[rid] = str(job["audio"])
        row = {"id": rid, "c": corpus, "p": job["term"], "title": title(corpus, rid, entry),
               "sub": subtitle(corpus, entry), "min": round(seconds / 60, 1),
               "sc": table.get(rid, {}), "engines": [m.name for m in job["models"]],
               "k": {k: sum(1 for c in found if c["kind"] == k) for k in KINDS},
               "serious": sum(1 for c in found if c["sec"] in ("opposite", "fact") and "judge" in c),
               "cards": cards.get(rid, 0), "shard": shard_name}
        if corpus == "scotus" and entry:
            row["ext"] = {"audio": entry["audio_url"], "pdf": entry["transcript_url"]}
        catalog.append(row)
        if (number + 1) % 25 == 0:
            print(f"{corpus} [{number + 1}/{len(jobs)}] {rid}", flush=True)
    if shard:
        write_shard(out / shard_name, shard)

    text_mb = sum(p.stat().st_size for p in (out / "rec").iterdir()) / 1e6
    chosen = pick_audio(catalog, BUDGET_MB - text_mb - 2, cards) if corpus in PUBLISHABLE else []
    keep = {f"{r['id']}.ogg" for r in chosen}
    if (out / "audio").exists():
        for old in (out / "audio").iterdir():
            if old.name not in keep:
                old.unlink()
    for n, r in enumerate(chosen, 1):
        path = out / "audio" / f"{r['id']}.ogg"
        if not no_audio and not path.exists():
            print(f"encoding {corpus}/{r['id']} ({r['min']} min, {n} of {len(chosen)})", flush=True)
            encode(Path(local_audio[r["id"]]), path)
        if path.exists():
            r["audio"] = path.relative_to(out).as_posix()

    (out / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / "local-audio.json").write_text(json.dumps(local_audio, indent=0), encoding="utf-8")
    from datetime import date
    meta = {"built": date.today().isoformat(), "corpus": corpus, "names": NAMES, "parts": PART_LABELS,
            "kinds": KINDS, "siteUrl": "https://claude.ai/artifact/3Q9MW1VB1ZgMNPPkLsTELX",
            "explorers": build_site.EXPLORER_URLS,
            "pages": {c: d["file"] for c, d in build_site.DATASETS.items()},
            "speakers": speaker_names(corpus), "interviewer": interviewers(corpus),
            "home": build_site.SOURCES[corpus]["home"], "credits": [build_site.CREDITS[corpus]],
            "sections": [[k, t] for k, t, _ in build_site.SECTIONS]}
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (out / "index.html").write_text(page(meta), encoding="utf-8")
    audio = list((out / "audio").glob("*.ogg")) if (out / "audio").exists() else []
    hours = sum(r["min"] for r in catalog if r.get("audio")) / 60
    files = sum(1 for p in out.rglob("*") if p.is_file() and p.name not in ("local-audio.json", "meta.json"))
    print(f"explorer/{corpus}: {len(catalog)} recordings, {sum(1 for r in catalog if r.get('audio'))} with audio "
          f"({hours:.1f} h); {files} files to publish; transcripts {text_mb:.1f} MB, "
          f"audio {sum(p.stat().st_size for p in audio) / 1e6:.1f} MB", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpora", nargs="*", help="scotus, edacc, coraal, earnings22 (default: all)")
    parser.add_argument("--no-audio", action="store_true", help="skip encoding the audio")
    parser.add_argument("--page-only", action="store_true", help="rebuild index.html from meta.json")
    args = parser.parse_args()
    for corpus in args.corpora or list(NAMES):
        if corpus not in NAMES:
            parser.error(f"no data set called {corpus}")
        if args.page_only:
            import build_site
            meta = json.loads((EXPLORER / corpus / "meta.json").read_text(encoding="utf-8"))
            meta.update(explorers=build_site.EXPLORER_URLS,
                        pages={c: d["file"] for c, d in build_site.DATASETS.items()},
                        speakers=speaker_names(corpus), credits=[build_site.CREDITS[corpus]],
                        interviewer=interviewers(corpus))
            (EXPLORER / corpus / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            entries = {}
            if corpus == "coraal":
                for line in (lineup.corpus_root(corpus) / "recordings.jsonl").read_text(encoding="utf-8").splitlines():
                    e = json.loads(line)
                    entries[e["id"]] = e
            if entries:
                path = EXPLORER / corpus / "catalog.json"
                catalog = json.loads(path.read_text(encoding="utf-8"))
                for r in catalog:
                    r["sub"] = subtitle(corpus, entries.get(r["id"]))
                path.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            (EXPLORER / corpus / "index.html").write_text(page(meta), encoding="utf-8")
            print(f"explorer/{corpus}/index.html rebuilt")
        else:
            build(corpus, args.no_audio)
    return 0


def write_shard(path: Path, shard: dict) -> None:
    """Gzipped, then written as base64 text: the website serves only a fixed list of
    file types, which has .txt and no compressed archive, and plain JSON would be
    about 240 MB against 90 this way. The page decodes and unzips it."""
    raw = json.dumps(shard, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(base64.b64encode(gzip.compress(raw, 9)))


def title(corpus: str, rid: str, entry: dict | None) -> str:
    if corpus == "scotus":
        return entry["case_name"] if entry else rid
    if corpus == "edacc":
        return f"Video call {rid}"
    if corpus == "coraal":
        place = PART_LABELS.get(rid.split("_")[0], rid.split("_")[0])
        return f"{place} interview {rid}"
    extra = (entry or {}).get("extra", {})
    return f"{extra.get('ticker', '')} earnings call ({extra.get('country', '')})".strip()


@functools.cache
def interviewers(corpus: str) -> dict:
    """{code: [recordings]}: where someone interviewed elsewhere asks the questions."""
    if corpus != "coraal":
        return {}
    root = lineup.corpus_root("coraal") / "downloads"
    meta = pd.concat([pd.read_csv(f, sep="\t", dtype=str) for f in sorted(root.glob("*_metadata_*.txt"))])
    interviewed = set(meta["CORAAL.Spkr"])
    both = meta[meta["Interviewer.Code"].isin(interviewed)]
    return {code: sorted(set(g["CORAAL.File"])) for code, g in both.groupby("Interviewer.Code")}


def speaker_names(corpus: str) -> dict:
    """Plain names for the speaker codes in the transcripts: {code: [name, about]}.

    The transcripts name speakers by code (CORAAL's ROC_se0_ag1_f_01, EdAcc's
    EDACC-C01-A). CORAAL's metadata (one file per component) and EdAcc's
    background survey say who each one is. Earnings-22's speakers are numbers,
    named on the page itself."""
    import pandas as pd
    out = {}
    if corpus == "coraal":
        root = lineup.corpus_root("coraal") / "downloads"
        meta = pd.concat([pd.read_csv(f, sep="\t", dtype=str) for f in sorted(root.glob("*_metadata_*.txt"))])
        sex = {"Female": "woman", "Male": "man"}
        for _, r in meta.iterrows():
            primary = r.get("Primary.Spkr") != "no"
            about = ", ".join(x for x in [sex.get(r["Gender"], ""), r["Age"] if isinstance(r["Age"], str) else ""] if x)
            out[r["CORAAL.Spkr"]] = ["Interviewee" if primary else "Other speaker", about]
            code = r["Interviewer.Code"]
            if isinstance(code, str) and code not in out:
                out[code] = ["Interviewer", ", ".join(x for x in [sex.get(r["Interviewer.Gender"], ""),
                             f"aged {r['Interviewer.Age']}" if isinstance(r["Interviewer.Age"], str) else ""] if x)]
        # An interviewer is interviewed in their own recordings, which came first above if
        # the row did; where they ask the questions, the page says so (META.interviewer).
        # CORAAL's "misc" tier: anyone besides the interviewer and the people interviewed.
        out["misc"] = out["Misc"] = ["Someone else", "anyone else who speaks (CORAAL's misc tier)"]
        # Interviewers the metadata never names (PRV_int_03, PRV_int_04, and ATL_Int_01 with
        # a capital I): the code itself says what they are.
        for path in sorted((lineup.corpus_root("coraal") / "unpacked").rglob("*.txt")):
            if "_metadata_" in path.name:
                continue
            for code in set(re.findall(r"\b[A-Z]{3}_[Ii]nt_\d+\b", path.read_text(encoding="utf-8", errors="replace"))):
                if code not in out:
                    out[code] = out.get(code.replace("_Int_", "_int_"), ["Interviewer", ""])
    elif corpus == "edacc":
        path = lineup.corpus_root("edacc") / "unpacked" / "edacc_v1.0" / "linguistic_background.csv"
        survey = pd.read_csv(path, dtype=str, encoding="cp1252")
        def fix(v: str) -> str:
            # The survey is mostly Windows text, but a few answers were saved as UTF-8.
            try:
                return v.encode("cp1252").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                return v
        survey = survey.map(lambda v: fix(v) if isinstance(v, str) else v)
        col = lambda start: next(c for c in survey.columns if c.strip().startswith(start))
        first, accent, sex = col("What is/are your first language"), col("How would you describe your accent"), col("What is your gender")
        for _, r in survey.iterrows():
            bits = [{"male": "man", "female": "woman"}.get(str(r[sex]).strip().lower(), ""),
                    f"first language {r[first].strip()}" if isinstance(r[first], str) else "",
                    f"calls their accent “{r[accent].strip()}”" if isinstance(r[accent], str) else ""]
            out[r["PARTICIPANT_ID"]] = [f"Speaker {r['PARTICIPANT_ID'].rsplit('-', 1)[-1]}",
                                        ", ".join(b for b in bits if b)]
    return out


def subtitle(corpus: str, entry: dict | None) -> str:
    if not entry:
        return ""
    if corpus == "scotus":
        return f"No. {entry['docket']}, argued {entry['argued']}"
    extra = entry.get("extra", {})
    if corpus == "edacc":
        who = extra.get("speakers", {})
        l2 = sum(1 for v in who.values() if v.endswith("l2"))
        return f"{len(who)} speakers, {l2} speaking English as a second language"
    if corpus == "coraal":
        # The person interviewed, from CORAAL's metadata (the file name less its
        # file number); the code alone only gives an age group.
        about = speaker_names("coraal").get(entry["id"].rsplit("_", 1)[0], ["", ""])[1]
        return f"Interview with a {about}" if about else ""
    return f"Call {entry['id']}"


if __name__ == "__main__":
    raise SystemExit(main())

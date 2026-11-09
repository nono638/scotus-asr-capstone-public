"""Every recording of every data set, and each engine lined up against its reference.

The tools that look for particular kinds of error (invented words, meaning changes,
edits, skips) all start the same way: find the recordings, find which run holds
each engine's transcript, and line each transcript up against the reference word
by word. That is done here, once, so the data sets are treated alike.

A data set is split into parts: a Supreme Court term ("OT2017"), an EdAcc split
("test", "dev"), a CORAAL component ("ROC", "PRV", "DCB", "ATL", ...) or an Earnings-22
region ("Asian"). A job is one recording:

    {"corpus": "coraal", "term": "PRV", "docket": "PRV_se0_ag2_f_01_1",
     "audio": Path(...), "models": [ModelRun, ...]}

("term" and "docket" are the Supreme Court names for the part and the recording;
they are kept for every data set so the older tools read the same keys.)

Lining up is the way tools/crowd.py does it: seam duplicates removed, stretches
the reference leaves out of scoring dropped, the `standard` rule with the
harmonise fixes, one shared vocabulary for every engine.
"""

from __future__ import annotations

import bisect
import json
import os
import re
import sys
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.model_sets import ModelRun, engines_in  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.metrics import drop_ignored  # noqa: E402
from scotus_asr.scoring.normalize import normalize_tokens  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402

#: The run each default engine's Supreme Court transcripts are in, by term ("*" for
#: every other term). OT2017 is the seven-model study's runs; the rest the queue's.
#: Parakeet's are the -reread runs: the old ones with every blank stretch decoded
#: again, because its decoder can stall after a full stop (findings/parakeet-stall/).
#: Qwen3's, and the other engines' below, are the -reread runs too: the chunks the
#: aligner stripped of punctuation or the engine gave up on, decoded again
#: (tools/redecode_chunks.py, 6-7 November 2026).
SCOTUS_RUNS = {
    "Qwen3": {"OT2017": "run-20260921-051927-reread", "*": "run-scotus250-qwen3-reread"},
    "Whisper": {"OT2010": "run-20260918-035220", "OT2017": "run-20260918-035220",
                "*": "run-scotus250-whisper"},
    "Parakeet": {"OT2017": "run-20260924-064733-reread", "*": "run-scotus250-parakeet-reread"},
}

#: The other data sets: one run per engine covers every part.
OTHER_RUNS = {
    "edacc": {"Whisper": "run-edacc-whisper", "Qwen3": "run-edacc-qwen3-reread",
              "Parakeet": "run-edacc-parakeet-reread", "Canary": "run-edacc-canary-reread",
              "Granite": "run-edacc-granite-reread"},
    "coraal": {"Whisper": "run-coraal-whisper", "Qwen3": "run-coraal-qwen3-reread",
               "Parakeet": "run-coraal-parakeet-reread"},
    "earnings22": {"Whisper": "run-earnings22-whisper", "Qwen3": "run-earnings22-qwen3-reread",
                   "Parakeet": "run-earnings22-parakeet-reread"},
}

#: Parakeet run again on the recordings where its decoder piled words on one moment
#: of audio, with the per-frame cap (3392e30, 26-27 Oct 2026). Each holds only those
#: recordings (67 in all), so it stands in for the run above recording by recording.
CAPPED_RUNS = {"scotus": "run-scotus250-parakeet-capped", "edacc": "run-edacc-parakeet-capped",
               "coraal": "run-coraal-parakeet-capped",
               "earnings22": "run-earnings22-parakeet-capped"}

#: The parts of each data set that are finished for every engine above. Earnings-22's
#: parts are the regions in its metadata; while one engine is still part way
#: through, recordings() keeps to the calls every engine has done.
PARTS = {
    "scotus": ["OT2010", "OT2017", "OT2021", "OT2025"],
    "edacc": ["test", "dev"],
    "coraal": ["ROC", "PRV", "DCB", "ATL", "DCA", "DTA", "LES", "VLD"],
    "earnings22": ["English", "Spanish/Portuguese", "Asian", "Other Romance", "Germanic",
                   "Slavic", "African"],
}


def scotus_root() -> Path:
    return local_path("scotus_corpus")


def corpus_root(corpus: str) -> Path:
    """Where a data set other than the Supreme Court lives, from local-paths.yaml."""
    return local_path("asr_corpora") / corpus


def model_run(name: str, run_dir: Path) -> ModelRun:
    engines = engines_in(run_dir)
    if len(engines) != 1:
        raise ValueError(f"{run_dir} holds {len(engines)} engines, expected one")
    return ModelRun(name, run_dir, next(iter(engines)))


def scotus_models(term: str) -> list[ModelRun]:
    runs = scotus_root() / "runs"
    return [model_run(engine, runs / by_term.get(term, by_term["*"]))
            for engine, by_term in SCOTUS_RUNS.items()]


def recordings(corpus: str, parts: list[str] | None = None, use_capped: bool = True) -> list[dict]:
    """Every recording in these parts of a data set that every engine has done.

    use_capped=False keeps Parakeet's -reread runs everywhere, for the judge samples
    drawn before the capped re-runs. Such a job, on a recording that has a re-run,
    has "not_cached" set: the saved line-up is the re-run's, so load() would be wrong.
    """
    parts = parts or PARTS[corpus]
    jobs = []
    root = scotus_root() if corpus == "scotus" else corpus_root(corpus)
    capped = model_run("Parakeet", root / "runs" / CAPPED_RUNS[corpus])
    capped_has = capped.recordings()

    def with_capped(models: list[ModelRun], docket: str) -> list[ModelRun]:
        if docket not in capped_has or not use_capped:
            return models
        return [capped if m.name == "Parakeet" else m for m in models]

    if corpus == "scotus":
        root = scotus_root()
        manifest = json.loads((root / "cases" / "manifest.json").read_text(encoding="utf-8"))
        for term in parts:
            models = scotus_models(term)
            have = set.intersection(*(m.recordings() for m in models))
            # The runs mix terms, so the term comes from the manifest. Its case_id
            # is the recording name the runs use ("15-1204_OT2017" for a re-argument).
            for entry in sorted(manifest, key=lambda e: e["case_id"]):
                if f"OT{entry['term']}" != term or entry["case_id"] not in have:
                    continue
                audio = root / "cases" / entry["folder"] / f"{entry['docket']}_audio.mp3"
                jobs.append({"corpus": corpus, "term": term, "docket": entry["case_id"],
                             "audio": audio, "models": with_capped(models, entry["case_id"]),
                             "not_cached": not use_capped and entry["case_id"] in capped_has})
        return jobs

    models = [model_run(name, root / "runs" / run) for name, run in OTHER_RUNS[corpus].items()]
    have = set.intersection(*(m.recordings() for m in models))
    for line in (root / "recordings.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["split"] in parts and entry["id"] in have:
            jobs.append({"corpus": corpus, "term": entry["split"], "docket": entry["id"],
                         "audio": Path(entry["path"]), "models": with_capped(models, entry["id"]),
                         "not_cached": not use_capped and entry["id"] in capped_has})
    return jobs


def line_up(models: list[ModelRun], docket: str) -> dict:
    """Each engine against the reference, for one recording.

    Returns {engine: (transcript, reference_words, alignment, words)}, where
    `words` is the engine's own timed word list (seam repeats and ignored
    stretches removed) and `alignment.hypothesis.source_index` leads from an
    aligned token back to it. Every engine sees the same reference tokens.
    """
    loaded = {}
    for run in models:
        transcript = Transcript.from_dict(
            json.loads(run.reference_file(docket).read_text(encoding="utf-8")))
        words = drop_ignored(_load_asr_result(run.asr_file(docket)).words, transcript.ignore)
        loaded[run.name] = (transcript, words)

    first = loaded[models[0].name][0]
    vocabulary = set(normalize_tokens(first.full_text().split(), "standard", harmonise=True).tokens)
    for transcript, words in loaded.values():
        vocabulary |= set(normalize_tokens([w.text for w in words], "standard", harmonise=True).tokens)

    lined = {}
    reference_tokens = None
    for name, (transcript, words) in loaded.items():
        reference_words = transcript.full_text().split()
        alignment = align_words(reference_words, [w.text for w in words], "standard",
                                harmonise=True, vocabulary=vocabulary)
        if reference_tokens is None:
            reference_tokens = alignment.reference.tokens
        elif alignment.reference.tokens != reference_tokens:
            raise ValueError(f"{docket}: {name}'s copy of the reference differs")
        lined[name] = (transcript, reference_words, alignment, words)
    return lined


#: Whisper's word timings split a hyphenated word in two: "dope-themed" comes out
#: as "dope" and "-themed", so joined with spaces it reads "dope -themed". Only
#: Whisper does it (24,647 times across the four data sets; Qwen3's two are real
#: minus signs). The line-ups here use the benchmark rule, which forgives hyphens;
#: the verbatim rule does not, so scoring joins them first (metrics.written_words).
_MARK_ON_PIECE = re.compile(r"(?<!\S)([^\s\[\]]+) (\[+)-(?=[\w$])")
_SPLIT = re.compile(r"(?<=[\w%$]) -(?=[\w$])")


def join_split_hyphens(text: str) -> str:
    """Whisper text with its split hyphens joined back: "dope -themed" becomes
    "dope-themed", and a mark on the second piece, "dope [-themed]", moves to the
    whole word, "[dope-themed]". Brackets of any depth ([ or [[) are kept."""
    # Join first, so "year -on [-year]" becomes "year-on [-year]", then "[year-on-year]".
    return _MARK_ON_PIECE.sub(r"\2\1-", _SPLIT.sub("-", text))


def word_turns(transcript: Transcript) -> list[int]:
    """For each word of transcript.full_text().split(), the index of its turn.

    Lets a finder tell whether a stretch of the record crosses from one speaker
    to the next (overlapping talk) or stays inside one turn.
    """
    out = []
    for i, turn in enumerate(transcript.turns):
        out += [i] * len(turn.text.split())
    return out


def reference_times(lined: dict) -> list[float]:
    """A time in seconds for each reference word, from a line_up() result.

    The Supreme Court's record has no times of its own, so each word borrows the
    start of the engine word it lines up with (the first engine that has one),
    and a word no engine got takes the time of the word before it. Borrowed from
    different engines the times can step back a little; they are made to only go
    forward, so a word can be found by time. Used by the explorer and the judge.

    Going forward means keeping the longest run of times that never steps back, and
    treating the rest as having none. Simply never stepping back let one badly timed word
    hold every word after it at its time, up to two minutes (bug-audit-2026-11-05.md).
    """
    names = list(lined)
    times: list[float | None] = [None] * len(lined[names[0]][1])
    for name in names:
        _, _, alignment, words = lined[name]
        rs, hs = alignment.reference.source_index, alignment.hypothesis.source_index
        for c in alignment.chunks:
            if c.kind != "equal":
                continue
            for i, j in zip(range(c.ref_start, c.ref_end), range(c.hyp_start, c.hyp_end)):
                w = words[hs[j]]
                if times[rs[i]] is None and w.start is not None:
                    times[rs[i]] = w.start
    keep = longest_forward_run(times)
    out, last = [], 0.0
    for i, t in enumerate(times):
        if i in keep:
            last = t
        out.append(last)
    return out


def longest_forward_run(times: list[float | None]) -> set[int]:
    """Which positions form the longest run of times that never steps back."""
    tails: list[float] = []       # the smallest last time of a run of each length
    at: list[int] = []            # and where it is
    before = [-1] * len(times)
    for i, t in enumerate(times):
        if t is None:
            continue
        n = bisect.bisect_right(tails, t)
        before[i] = at[n - 1] if n else -1
        if n == len(tails):
            tails.append(t)
            at.append(i)
        else:
            tails[n], at[n] = t, i
    keep, i = set(), at[-1] if at else -1
    while i >= 0:
        keep.add(i)
        i = before[i]
    return keep


#: Lined-up recordings, saved so each finder does not align everything again
#: (about 6 seconds a recording to align, a twentieth of that to read back).
#: Ignored by git. A saved one is used only while it is newer than every
#: transcript and reference it was made from, so a recording transcribed again,
#: or a run swapped for another (as Parakeet's were on 23 Oct 2026), is lined up
#: again without anyone remembering to delete anything.
CACHE = CAPSTONE / "findings" / "failures" / "cache"


def fresh(path: Path, job: dict) -> bool:
    """Whether the saved line-up at path is newer than everything it came from."""
    if not path.exists():
        return False
    sources = [f for m in job["models"]
               for f in (m.asr_file(job["docket"]), m.reference_file(job["docket"]))]
    return path.stat().st_mtime > max(f.stat().st_mtime for f in sources)


def load(job: dict) -> dict:
    """line_up() for one job, read from the cache when it is there and fresh."""
    import gzip
    import pickle
    if job.get("not_cached"):
        return line_up(job["models"], job["docket"])
    path = CACHE / job["corpus"] / job["term"] / f"{job['docket']}.pkl.gz"
    if fresh(path, job):
        return pickle.loads(gzip.decompress(path.read_bytes()))
    lined = line_up(job["models"], job["docket"])
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written beside it and renamed, so a finder running at the same time never
    # reads half a file.
    part = path.with_suffix(f".{os.getpid()}.part")
    part.write_bytes(gzip.compress(pickle.dumps(lined), 3))
    os.replace(part, path)
    return lined


if __name__ == "__main__":
    # python tools/lineup.py [corpus ...]: fill the cache, so the finders start fast.
    import time
    started = time.monotonic()
    for corpus in sys.argv[1:] or list(PARTS):
        jobs = recordings(corpus)
        for number, job in enumerate(jobs, 1):
            load(job)
            print(f"{corpus} [{number}/{len(jobs)}] {job['term']} {job['docket']} "
                  f"{(time.monotonic() - started) / 60:.1f} min", flush=True)

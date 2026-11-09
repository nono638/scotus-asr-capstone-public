"""One benchmark rule on every data set: error rates by engine and part, with the October fixes.

findings/<data set>/engines.csv pools what each run saved when it was scored, and a run
saves its benchmark column without the October fixes, so those tables read about half a
point higher than the Supreme Court's, and than recordings.csv. This table is the one to
quote and the one the website shows.

    python tools/benchmark_tables.py                  # after tools/build_data.py

Writes findings/<data set>/benchmark.csv, for EdAcc, CORAAL and Earnings-22:

    part          a part of the data set, or "all"
    engine        short name
    recordings    how many recordings
    words         reference words on the benchmark rule
    benchmark     errors over words, in percent, pooled (from findings/recordings.csv)
    verbatim      the same on the verbatim rule; blank on EdAcc, whose reference has no
                  capitals or punctuation, so the rule means nothing there

EdAcc also gets the commercial engine's transcript that ships with its test split
(company.ctm), scored the same way, on the test split only.
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "tools"))
sys.path.insert(0, str(CAPSTONE / "pipeline"))

import lineup  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.metrics import drop_ignored, written_words  # noqa: E402

FINDINGS = CAPSTONE / "findings"
CORPORA = ["edacc", "coraal", "earnings22"]


def verbatim_one(job: dict) -> list[dict]:
    """Verbatim errors and words for each engine on one recording."""
    rows = []
    for engine, (_, reference, _, words) in lineup.load(job).items():
        a = align_words(reference, written_words([w.text for w in words]), "verbatim", harmonise=True)
        rows.append({"recording": job["docket"], "engine": engine,
                     "v_errors": a.substitutions + a.deletions + a.insertions, "v_words": len(a.reference.tokens)})
    return rows


def company_rows() -> pd.DataFrame:
    """EdAcc's commercial transcript on the benchmark rule, recording by recording."""
    from scotus_asr.corpora.formats import read_ctm
    ctm = read_ctm(lineup.corpus_root("edacc") / "unpacked" / "edacc_v1.0" / "test" / "company.ctm")
    rows = []
    for job in lineup.recordings("edacc"):
        if job["term"] != "test":
            continue
        transcript, reference, *_ = next(iter(lineup.load(job).values()))
        # As for an engine: words inside a stretch the reference leaves out don't count.
        hypothesis = [w.text for w in drop_ignored(ctm.get(job["docket"], []), transcript.ignore)]
        a = align_words(reference, hypothesis, "standard", harmonise=True)
        rows.append({"corpus": "edacc", "part": "test", "recording": job["docket"], "engine": "Commercial",
                     "reference_words": len(a.reference.tokens),
                     "errors": a.substitutions + a.deletions + a.insertions})
    return pd.DataFrame(rows)


def pooled(t: pd.DataFrame, part: str) -> pd.DataFrame:
    got = t.groupby("engine", sort=False).agg(recordings=("recording", "nunique"), words=("reference_words", "sum"),
                                              errors=("errors", "sum"), v_errors=("v_errors", "sum"),
                                              v_words=("v_words", "sum")).reset_index()
    got.insert(0, "part", part)
    got["benchmark"] = (100 * got.errors / got.words).round(2)
    got["verbatim"] = (100 * got.v_errors / got.v_words).round(2).where(got.v_words > 0)
    return got[["part", "engine", "recordings", "words", "benchmark", "verbatim"]]


def main() -> int:
    table = pd.read_csv(FINDINGS / "recordings.csv", dtype={"recording": str})
    table["errors"] = table.substituted + table.dropped + table.added
    for corpus in CORPORA:
        t = table[table.corpus == corpus].copy()
        if corpus == "edacc":
            # The verbatim rule means nothing without capitals or punctuation in the record.
            t["v_errors"], t["v_words"] = 0, 0
        else:
            with ProcessPoolExecutor() as pool:
                rows = [r for got in pool.map(verbatim_one, lineup.recordings(corpus), chunksize=4) for r in got]
            t = t.merge(pd.DataFrame(rows), on=["recording", "engine"], validate="one_to_one")
        keep = ["part", "recording", "engine", "reference_words", "errors", "v_errors", "v_words"]
        t = t[keep]
        frames = [pooled(t[t.part == part], part) for part in dict.fromkeys(t.part)]
        if corpus == "edacc":
            company = company_rows().assign(v_errors=0, v_words=0)[keep]
            frames = [pooled(pd.concat([t[t.part == "test"], company]), "test")
                      if f.part.iloc[0] == "test" else f for f in frames]
        frames.append(pooled(t, "all"))
        out = pd.concat(frames, ignore_index=True)
        out.to_csv(FINDINGS / corpus / "benchmark.csv", index=False)
        print(f"\n{corpus}\n" + out[out.part.isin(["all", "test"])].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

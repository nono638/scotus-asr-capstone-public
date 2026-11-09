"""One table of every engine's error rate and speed, from a folder of runs.

Each run already scores itself (`results/scores.csv`, `results/cases.csv`, one
row per recording). This pools them: the errors added up over every recording
and divided by every reference word, which weights a long conversation more
than a short one - the same way `crowd.py` and the benchmark papers count.

    python tools/summarise_runs.py --runs-dir <asr_corpora>/edacc/runs --out findings/edacc

writes

  engines.csv        one row per engine: error rate under each rule, the share
                     of words swapped, dropped and added (benchmark rule), hours
                     of audio, hours taken, and speed (times faster than real time)
  per-recording.csv  one row per engine and recording, the same numbers

A transcript made somewhere else can be scored alongside, if it is a NIST CTM
file (one timed word per line, the usual format for this). EdAcc ships one from
a commercial engine. It is scored through the pipeline's own scoring, against
the corpus the settings files name:

    python tools/summarise_runs.py --runs-dir <asr_corpora>/edacc/runs --out findings/edacc \\
        --ctm company=<asr_corpora>/edacc/unpacked/edacc_v1.0/test/company.ctm \\
        --config pipeline/config/corpora/edacc.yaml

Its speed is left blank: nobody timed it.

A corpus in parts (EdAcc's test and dev splits, CORAAL's components) can be
summarised part by part too. `--index` names the corpus's recordings.jsonl, whose
`split` gives each recording's part; that adds engines-by-part.csv. `--parts`
keeps engines.csv and per-recording.csv to the parts named, so a new part run
later does not change a table already quoted:

    python tools/summarise_runs.py --runs-dir <asr_corpora>/edacc/runs --out findings/edacc \
        --index <asr_corpora>/edacc/recordings.jsonl --parts test ...

While one engine is still part way through a corpus, `--shared-only` keeps every
table to the recordings all the engines have done, so they are compared on the
same audio.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.model_sets import discover  # noqa: E402

RULES = ["standard", "lowercase_nopunct", "verbatim"]


def run_rows(runs_dir: Path) -> pd.DataFrame:
    """Per-recording numbers for every engine, each from its most complete run."""
    frames = []
    for run in discover(runs_dir):
        results = run.run_dir / "results"
        table = pd.DataFrame(columns=["docket"])
        if (results / "scores.csv").exists():
            scores = pd.read_csv(results / "scores.csv")
            cases = pd.read_csv(results / "cases.csv")
            scores = scores[scores.engine == run.engine]
            cases = cases[cases.engine == run.engine]
            wide = scores.pivot_table(index="docket", columns="normalizer",
                                      values=["substitutions", "deletions", "insertions",
                                              "reference_tokens"], aggfunc="sum")
            wide.columns = [f"{rule}_{what}" for what, rule in wide.columns]
            table = cases[["docket", "audio_minutes", "runtime_seconds"]].merge(
                wide.reset_index(), on="docket")
            table.insert(0, "engine", run.engine)
            table["run"] = run.run_dir.name
        unscored = sorted(run.recordings() - set(table.docket))
        if unscored:
            print(f"{run.run_dir.name}: scoring {len(unscored)} transcript(s) the run has "
                  f"not scored yet, in memory")
            table = pd.concat([table, unscored_rows(run, unscored)], ignore_index=True)
        frames.append(table)
    return pd.concat(frames, ignore_index=True)


def unscored_rows(run, dockets: list[str]) -> pd.DataFrame:
    """Per-recording numbers for transcripts a run has not scored yet.

    A run scores everything at the end, so one stopped part way through has
    transcripts and no scores. They are scored here the way the scoring stage
    does it (stages.py), with the run's own settings, and nothing is written
    into the run folder.
    """
    import yaml
    from scotus_asr.config import ScoringSettings
    from scotus_asr.scoring.metrics import score_case
    from scotus_asr.stages import _load_asr_result
    from scotus_asr.transcripts.model import Transcript

    # Only the scoring section: the saved settings carry fields load_config
    # does not take back (the engine's resolved name, for one).
    used = yaml.safe_load((run.run_dir / "config_used.yaml").read_text(encoding="utf-8"))
    scoring = ScoringSettings(**used.get("scoring", {}))
    rows = []
    for docket in dockets:
        transcript = Transcript.from_dict(json.loads(run.reference_file(docket).read_text(encoding="utf-8")))
        result = _load_asr_result(run.asr_file(docket))
        score = score_case(transcript, result, scoring, audio_minutes=result.audio_seconds / 60)
        row = {"engine": run.engine, "docket": docket, "audio_minutes": result.audio_seconds / 60,
               "runtime_seconds": result.runtime_seconds}
        for r in score.rows:
            for what in ("substitutions", "deletions", "insertions"):
                row[f"{r.normalizer}_{what}"] = getattr(r, what)
            row[f"{r.normalizer}_reference_tokens"] = r.reference_tokens
        row["run"] = run.run_dir.name
        rows.append(row)
    return pd.DataFrame(rows)


def ctm_rows(name: str, ctm: Path, config_files: list[Path]) -> pd.DataFrame:
    """Per-recording numbers for a CTM file, scored like an engine's output."""
    from scotus_asr.asr.base import AsrResult, Segment, Word
    from scotus_asr.config import load_config
    from scotus_asr.corpora.formats import read_ctm
    from scotus_asr.corpora.registry import build_corpus
    from scotus_asr.scoring.metrics import score_case

    config = load_config(config_files)
    corpus = build_corpus(config)
    words_by_file = read_ctm(ctm)
    rows = []
    for recording in corpus.recordings():
        words = [Word(w.text, w.start, w.end, w.probability)
                 for w in words_by_file.get(recording.id, [])]
        seconds = recording.audio_minutes * 60
        result = AsrResult(recording.id, name, ctm.name,
                           [Segment(0, 0.0, seconds, " ".join(w.text for w in words), words)],
                           seconds)
        score = score_case(corpus.reference(recording), result, config.scoring,
                           recording.audio_minutes)
        row = {"engine": name, "docket": recording.id,
               "audio_minutes": recording.audio_minutes, "runtime_seconds": None}
        for r in score.rows:
            for what in ("substitutions", "deletions", "insertions"):
                row[f"{r.normalizer}_{what}"] = getattr(r, what)
            row[f"{r.normalizer}_reference_tokens"] = r.reference_tokens
        row["run"] = str(ctm)
        rows.append(row)
    return pd.DataFrame(rows)


def add_rates(table: pd.DataFrame) -> pd.DataFrame:
    """Error rates (percent) from the counts, for one row or a pooled one."""
    out = table.copy()
    for rule in RULES:
        errors = sum(out[f"{rule}_{w}"] for w in ("substitutions", "deletions", "insertions"))
        out[f"wer_{rule}"] = (100 * errors / out[f"{rule}_reference_tokens"]).round(2)
    for what, label in (("substitutions", "swapped"), ("deletions", "dropped"),
                        ("insertions", "added")):
        out[f"{label}_pct"] = (100 * out[f"standard_{what}"]
                               / out["standard_reference_tokens"]).round(2)
    out["speed_x_realtime"] = (out.audio_minutes * 60 / out.runtime_seconds).round(1)
    return out


def summarise(rows: pd.DataFrame, by: list[str] = ["engine"]) -> pd.DataFrame:
    counts = [c for c in rows.columns if c.endswith(("_substitutions", "_deletions",
                                                     "_insertions", "_reference_tokens"))]
    pooled = rows.groupby(by, sort=False).agg(
        recordings=("docket", "count"), audio_minutes=("audio_minutes", "sum"),
        runtime_seconds=("runtime_seconds", lambda s: s.sum(min_count=1)),
        run=("run", "first"), **{c: (c, "sum") for c in counts})
    pooled = add_rates(pooled.reset_index())
    pooled["audio_hours"] = (pooled.audio_minutes / 60).round(2)
    pooled["hours_taken"] = (pooled.runtime_seconds / 3600).round(2)
    keep = by + ["recordings", "wer_standard", "wer_lowercase_nopunct", "wer_verbatim",
            "swapped_pct", "dropped_pct", "added_pct", "audio_hours", "hours_taken",
            "speed_x_realtime", "standard_reference_tokens", "run"]
    return pooled[keep].sort_values(by[:-1] + ["wer_standard"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ctm", action="append", default=[], metavar="NAME=PATH",
                        help="a CTM file to score alongside the runs (repeatable)")
    parser.add_argument("--config", action="append", type=Path, default=[],
                        help="settings files naming the corpus, needed with --ctm")
    parser.add_argument("--index", type=Path,
                        help="the corpus's recordings.jsonl, to summarise part by part")
    parser.add_argument("--parts", nargs="+",
                        help="keep engines.csv and per-recording.csv to these parts (needs --index)")
    parser.add_argument("--shared-only", action="store_true",
                        help="keep to the recordings every engine has done")
    args = parser.parse_args()
    if args.parts and not args.index:
        parser.error("--parts needs --index, to know which part each recording is in")
    if args.ctm and not args.config:
        parser.error("--ctm needs --config, to know which corpus to score against")

    rows = run_rows(args.runs_dir)
    for pair in args.ctm:
        name, _, path = pair.partition("=")
        rows = pd.concat([rows, ctm_rows(name, Path(path), args.config)], ignore_index=True)
    if args.shared_only:
        engines = rows.engine.nunique()
        shared = rows.groupby("docket").engine.nunique()
        rows = rows[rows.docket.isin(shared[shared == engines].index)]

    args.out.mkdir(parents=True, exist_ok=True)
    if args.index:
        part = {e["id"]: e["split"] for e in map(json.loads,
                args.index.read_text(encoding="utf-8").splitlines())}
        rows.insert(1, "part", rows.docket.map(part))
        summarise(rows, ["part", "engine"]).to_csv(args.out / "engines-by-part.csv", index=False)
        if args.parts:
            rows = rows[rows.part.isin(args.parts)]
    engines = summarise(rows)
    engines.to_csv(args.out / "engines.csv", index=False)
    per = add_rates(rows)[["engine"] + (["part"] if args.index else []) + ["docket", "audio_minutes", "runtime_seconds",
                           "speed_x_realtime", "wer_standard", "wer_lowercase_nopunct",
                           "wer_verbatim", "swapped_pct", "dropped_pct", "added_pct"]]
    per.to_csv(args.out / "per-recording.csv", index=False)
    with pd.option_context("display.width", 200):
        print(engines.drop(columns=["run"]).to_string(index=False))
    print(f"\nWritten to {args.out}")


if __name__ == "__main__":
    main()

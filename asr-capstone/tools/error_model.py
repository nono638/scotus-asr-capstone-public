"""Which conditions make a word likely to be wrong, and does the engine matter more? (H2)

Reads the word tables from tools/word_table.py and fits a logistic regression of
"this engine got this word wrong" on:

    engine           which model (the best one is the baseline)
    word_type        number, legal term, name, filler, small function word (content words baseline)
    turn             distance to a change of speaker: 0, 1-3, 4-10 words, or further (baseline)
    near_dash        a reporter's dash within two words: someone was interrupted
    disfluency_near  a filler or a repeated word within two words
    rate             local words per second, in half-second steps
    role             justice or advocate (Supreme Court only)
    recording        one term per recording, so a hard recording cannot pass for a hard condition

The predictors are all categories or binned, so the words are first collapsed into
counts per combination; a binomial model on those counts gives exactly the same
estimates as one row per word, in seconds rather than hours. Standard errors are
clustered by recording, since words from one recording are not independent.

To say whether the engine matters more than the conditions, three versions are
fitted - engine only, conditions only, both - and compared by McFadden's pseudo
R-squared against a model that knows only the recording: the share of that
model's log-likelihood each one recovers. It is computed word by word (not from
the collapsed counts, whose deviance would flatter every model), so it is the
same number one row per word would give.

Writes, for each corpus, into --out:

    odds-ratios-<corpus>.csv     every term's odds ratio with a 95% interval
    error-rates-<corpus>.csv     the plain error rate in each condition, for reading alongside
    variance-explained.csv       engine only / conditions only / both, per corpus

    python tools/error_model.py --table scotus=<scotus_corpus>/word-table.csv.gz \\
        --table edacc=<asr_corpora>/edacc/word-table.csv.gz --out findings/error-model
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm

RATE_STEP = 0.5
RATE_CAP = 8.0
MIN_WORDS = 100   # a word type rarer than this is folded into "content"


def long_form(table: pd.DataFrame) -> pd.DataFrame:
    """One row per word per engine, with the conditions coded for the model."""
    engines = [c for c in table.columns if c.startswith("ok_")]
    words = table.copy()
    # An odds ratio from a handful of words is noise, and the benchmark rule
    # deletes most fillers before scoring, so on the Supreme Court almost none
    # are left. Rare types join the baseline rather than get a term of their own.
    counts = words.word_type.value_counts()
    rare = counts[counts < MIN_WORDS].index
    words.loc[words.word_type.isin(rare), "word_type"] = "content"
    words["turn"] = pd.cut(words.words_to_turn, [-1, 0, 3, 10, np.inf],
                           labels=["0", "1-3", "4-10", "far"]).astype(str)
    rate = words.local_rate.fillna(words.local_rate.median()).clip(upper=RATE_CAP)
    words["rate"] = (rate / RATE_STEP).round() * RATE_STEP
    keep = ["recording", "word_type", "turn", "near_dash", "disfluency_near", "rate", "role"]
    long = words.melt(id_vars=keep, value_vars=engines, var_name="engine", value_name="ok")
    long["engine"] = long.engine.str.removeprefix("ok_")
    return long


def collapse(long: pd.DataFrame) -> pd.DataFrame:
    keys = [c for c in long.columns if c != "ok"]
    grouped = long.groupby(keys, observed=True).ok.agg(["sum", "count"]).reset_index()
    grouped["wrong"] = grouped["count"] - grouped["sum"]
    return grouped.rename(columns={"sum": "right"})


def formula_terms(data: pd.DataFrame, baseline: str, which: str) -> str:
    engine = f"C(engine, Treatment('{baseline}'))"
    conditions = ["C(word_type, Treatment('content'))", "C(turn, Treatment('far'))",
                  "disfluency_near", "rate"]
    if data.near_dash.nunique() > 1:
        conditions.append("near_dash")
    if data.role.nunique() > 1:
        conditions.append("C(role, Treatment('advocate'))")
    parts = {"engine": [engine], "conditions": conditions, "both": [engine] + conditions}[which]
    return " + ".join(parts + ["C(recording)"])


def fit(data: pd.DataFrame, terms: str):
    exog = patsy.dmatrix(terms, data, return_type="dataframe")
    endog = data[["wrong", "right"]].to_numpy()
    groups = pd.factorize(data.recording)[0]
    model = sm.GLM(endog, exog, family=sm.families.Binomial())
    return model.fit(cov_type="cluster", cov_kwds={"groups": groups})


def word_loglike(result, data: pd.DataFrame) -> float:
    """Log-likelihood summed over individual words, from the fitted probabilities."""
    p = np.clip(result.fittedvalues.to_numpy(), 1e-12, 1 - 1e-12)
    return float((data.wrong * np.log(p) + data.right * np.log(1 - p)).sum())


def tidy(result) -> pd.DataFrame:
    ci = result.conf_int()
    table = pd.DataFrame({
        "term": result.params.index,
        "odds_ratio": np.exp(result.params.values),
        "ci_low": np.exp(ci[0].values),
        "ci_high": np.exp(ci[1].values),
        "p_value": result.pvalues.values,
    })
    table = table[~table.term.str.startswith(("C(recording)", "Intercept"))]
    table["term"] = (table.term.str.replace(r"C\((\w+), Treatment\('[^']*'\)\)\[T\.", r"\1=", regex=True)
                     .str.rstrip("]"))
    return table.round({"odds_ratio": 3, "ci_low": 3, "ci_high": 3, "p_value": 4})


def plain_rates(long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in ["engine", "word_type", "turn", "near_dash", "disfluency_near", "role"]:
        for value, group in long.groupby(column):
            rows.append({"condition": column, "value": value, "words": len(group),
                         "error_pct": round(100 * (1 - group.ok.mean()), 2)})
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", action="append", required=True, metavar="CORPUS=PATH",
                        help="a word table from word_table.py. Repeat for each corpus.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    explained = []
    for spec in args.table:
        corpus, path = spec.split("=", 1)
        long = long_form(pd.read_csv(path))
        data = collapse(long)
        baseline = (long.groupby("engine").ok.mean()).idxmax()
        print(f"{corpus}: {len(long):,} word-engine pairs in {len(data):,} combinations; "
              f"baseline engine {baseline}")

        floor = word_loglike(fit(data, "C(recording)"), data)
        results = {which: fit(data, formula_terms(data, baseline, which))
                   for which in ("engine", "conditions", "both")}
        for which, result in results.items():
            r2 = 1 - word_loglike(result, data) / floor
            explained.append({"corpus": corpus, "model": which,
                              "mcfadden_r2_beyond_recording": round(r2, 4)})
            print(f"  {which:10s} McFadden R2 beyond the recording: {r2:.3f}")

        tidy(results["both"]).to_csv(args.out / f"odds-ratios-{corpus}.csv", index=False)
        plain_rates(long).to_csv(args.out / f"error-rates-{corpus}.csv", index=False)

    pd.DataFrame(explained).to_csv(args.out / "variance-explained.csv", index=False)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

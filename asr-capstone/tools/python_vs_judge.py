"""How much of Sonnet's verdict can features with no understanding of meaning predict?

A first look (27 October 2026) at whether finding serious ASR errors needs an LLM, or
whether the Python rules' own facts about a case (which rule flagged it, the data set,
how many other engines got it right, how alike the two spellings are, a "not" on one
side only) already tell. Trained and scored with 5-fold cross-validation on the
judge's answers; the judge is the yardstick, not the truth.

    python tools/python_vs_judge.py                       # Sonnet on full-v1
    python tools/python_vs_judge.py --answers answers-qwen3.8-27b-full-v1.csv
"""
import argparse
import difflib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict
from sklearn.tree import DecisionTreeClassifier, export_text

JUDGE = Path(__file__).resolve().parent.parent / "findings" / "judge"
parser = argparse.ArgumentParser()
parser.add_argument("--answers", default="answers-claude-sonnet-5-5-full-v1.csv")
parser.add_argument("--sample", default="full-v1.csv")
args = parser.parse_args()

d = pd.read_csv(JUDGE / args.answers)
d = d[(d.ask == "meaning") & (d.variant == "minute") & (d.valid.astype(str) == "True")]
a = pd.DataFrame(list(d.answer.map(json.loads)))
a["case"] = d.case.values
s = pd.read_csv(JUDGE / args.sample).set_index("case")
a = a.join(s[["corpus", "engine", "kind", "subkind", "source", "record", "engine_wrote", "others_right"]], on="case")

NEG = re.compile(r"\b(not|no|never|n't|ain't|cannot|nothing|nobody|none)\b|n't\b", re.I)
rec = a.record.fillna("").astype(str)
eng = a.engine_wrote.fillna("").astype(str)
X = pd.DataFrame({
    "others_right": a.others_right.fillna("").astype(str).str.split().map(len),
    "all_agree": (a.source == "all-agree").astype(int),
    "similarity": [difflib.SequenceMatcher(None, r.lower(), e.lower()).ratio() for r, e in zip(rec, eng)],
    "neg_one_side": [int(bool(NEG.search(r)) != bool(NEG.search(e))) for r, e in zip(rec, eng)],
    "digit_one_side": [int(any(c.isdigit() for c in r) != any(c.isdigit() for c in e)) for r, e in zip(rec, eng)],
    "rec_words": rec.str.split().map(len),
    "eng_words": eng.str.split().map(len),
})
X = X.join(pd.get_dummies(a[["subkind", "corpus", "engine", "kind"]], dtype=int))

targets = {
    "matters (changed or opposite)": a.meaning.isin(["changed", "opposite"]),
    "harmless (same or reworded)": a.meaning.isin(["same", "reworded"]),
    "opposite": a.meaning == "opposite",
    "serious (opposite or severity 3+)": (a.meaning == "opposite") | (a.severity >= 3),
    "human probably wrong (doubt = yes)": a.reference_doubt == "yes",
}
for name, y in targets.items():
    y = y.astype(int).values
    base = max(y.mean(), 1 - y.mean())
    lr = cross_val_predict(LogisticRegression(max_iter=2000, class_weight="balanced"), X, y, cv=5, method="predict_proba")[:, 1]
    tree = cross_val_predict(DecisionTreeClassifier(max_depth=4, min_samples_leaf=20), X, y, cv=5, method="predict_proba")[:, 1]
    acc = ((tree > 0.5) == y).mean()
    print(f"{name}: {y.sum()} of {len(y)}; always-guess-the-majority {base:.0%}; "
          f"tree accuracy {acc:.0%}; ranking quality (AUC) logistic {roc_auc_score(y, lr):.2f}, tree {roc_auc_score(y, tree):.2f}")
    # How many of the true cases are in the top N by the logistic score (finding needles).
    top = np.argsort(-lr)[: y.sum()]
    print(f"   of the {y.sum()} true cases, {y[top].sum()} are in the top {y.sum()} by the Python score")

# The simplest rule for inversions: the negation finder flagged it.
neg = a.subkind.isin(["negation", "aint"])
opp = a.meaning == "opposite"
print(f"rule 'negation finder flagged it': {neg.sum()} cases, {(neg & opp).sum()} opposite "
      f"({(neg & opp).sum() / neg.sum():.0%}); catches {(neg & opp).sum()} of {opp.sum()} opposites")
print(export_text(DecisionTreeClassifier(max_depth=3, min_samples_leaf=20).fit(X, opp.astype(int)), feature_names=list(X.columns)))

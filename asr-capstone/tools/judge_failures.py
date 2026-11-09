"""Ask a local language model about the failure cases the Python searches found.

The four searches in findings/failures/ (meaning changes, invented words, edits,
skips) decide everything with rules: a "not" on one side only, a different
number, a different content word, a dialect feature rewritten, words over
silence, speech left out. Rules can't say whether the meaning really changed or
how much it matters, and the biggest pile is the least checked: about 15,500 of
the 18,500 meaning candidates are "a different content word", many of them names
or sound-alikes that change nothing. So a model reads each case and answers.

This is the second judge. tools/judge_spots.py (Gemma 4 31B) labels what *kind*
of difference a flagged spot is and is never asked who is right. This one asks
about consequences, on the failure cases, in five kinds of request:

    labelled  the reference and the engine's text, the spot marked. Did the
              meaning change or flip, how serious is it, would a reader notice,
              a question for the case's kind, and could it mislead someone
              relying on the text. The rule's verdict is not shown: with it,
              the judge repeated it even over two identical texts (PROMPT).
              Asked at three sizes of
              context, since how much context a judge needs is the open question:
                line    the few words either side the search saved
                minute  30 s either side, speaker names included
                whole   the full reference first, then the minute
    rule      the minute, then the rule's label and evidence: is the rule right?
              The judge copies both texts at the spot first, so it has read them.
    blind    two versions identical except at the spot, one the reference and
              one with the engine's words, without saying which is which: which
              is more likely what was said? Asked in both orders, which also
              shows whether the judge favours whichever comes first.
    rank      every engine's version of the spot, names hidden and shuffled:
              which keeps the meaning best?
    misses    a minute of reference and engine text with nothing marked: list
              every difference that matters. Matched afterwards against what the
              rules found in that minute, to see what the rules miss.

The cases are a fixed sample (findings/judge/sample-v1.csv, --make-sample), so a
later model, local or frontier, answers exactly the same questions on exactly the
same text. Nothing here has been heard: the shortlist cases were picked and
explained by Claude in earlier sessions, so agreement with them is two models
agreeing, not a measure of truth. The four controls are the only cases with a
known right answer.

How it talks to Ollama is copied from judge_spots.py: JSON answers (here held to
a schema, https://docs.ollama.com/capabilities/structured-outputs), temperature 0
and a fixed seed so a rerun gives the same answer, thinking off unless --think,
each answer saved as it comes so a stopped run carries on, and the card given
back at the end. The context window (num_ctx) is fixed per phase, because Ollama
reloads the model whenever it changes (llm_format.py found the same): every
short request first, then the whole-transcript ones at one larger size, in
recording order so cases from one recording share the transcript at the start of
the prompt and Ollama need not read it again.

GPU: gemma4:26b needs about 17 GB at the short size. Stops if Ollama already has
another model loaded.

    python tools/judge_failures.py --make-sample            # write sample-v1.csv
    python tools/judge_failures.py --dry-run s01            # print every prompt for one case
    python tools/judge_failures.py --source control         # the four controls only
    python tools/judge_failures.py                          # everything not yet answered
    python tools/judge_failures.py --ask blind,rank --model gemma4:31b
    python tools/judge_failures.py --prompt 0.3 --model claude-haiku-5-5 --think --batch   # half price
    python tools/judge_failures.py --summary                # the tables for the README
    python tools/judge_failures.py --sample full-v1 --make-combo combo-v1   # 300 cases for prompt combinations
    python tools/judge_failures.py --prompt 0.5 --sample full-v1 --subset combo-v1 --sizes minute \\
        --model claude-sonnet-5-5 --think --batch           # every kind of question on them
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lineup  # noqa: E402
from scotus_asr.scoring.normalize import normalize_tokens  # noqa: E402

CAPSTONE = lineup.CAPSTONE
FAILURES = CAPSTONE / "findings" / "failures"
OUT = CAPSTONE / "findings" / "judge"
SAMPLE = OUT / "sample-v1.csv"
#: Samples drawn and judged before Parakeet's capped re-runs (27 Oct 2026). They keep
#: its -reread transcripts, so a judge run on them later reads the same text.
BEFORE_CAPPED = {"sample-v1", "sample-v2", "sample-v3"}
#: Added to the answers, request log and batch file names for any sample but the
#: first, so a bigger sample's answers never mix into sample-v1's tables.
SUFFIX = ""
OLLAMA = "http://localhost:11434"
MODEL = "gemma4:26b"
#: Written into every row; change a request's version whenever its wording changes.
#: 0.2 (23 Oct 2026): the labelled request no longer shows the rule's verdict. With
#: it, Gemma 4 26B called both "same" controls changed or reversed, repeating the
#: rule's evidence over two identical texts; the rule now has its own request.
PROMPT = {"labelled": "0.2", "rule": "0.2", "blind": "0.1", "rank": "0.1", "misses": "0.1"}
OPTIONS = {"temperature": 0, "seed": 1, "num_predict": 1500}
SHORT_CTX = 8192
#: With thinking on, the thinking counts toward num_predict, so the answer needs
#: far more room, and the window has to hold it as well as the prompt.
#: Gemma 4's thinking is only on or off. Most requests ran 300-1,200 tokens, but
#: one "misses" request ran 7,612 (it lists the whole minute), so 16k. Qwen 3.8's card allows up to 262k tokens of reasoning
#: (huggingface.co/Qwen/Qwen3.8-27B, Best Practices) and Ollama offers it at
#: low / medium / xhigh, so it gets 32k at Ollama's default, medium.
THINK_PREDICT = {"qwen": 32768, "*": 16384}
THINK_LEVEL = {"qwen": "medium", "*": True}
LONGEST_SHORT_PROMPT = 1500   # tokens; the longest line/minute prompt measured was 1,223


#: Claude through Anthropic's API, for any model named claude-... (24 Oct 2026: Haiku 5.5).
#: The key is read from a git-ignored file, or ANTHROPIC_API_KEY, and goes only into
#: the request header: never printed, logged or written to the answer files.
CLAUDE_API = "https://api.anthropic.com/v1/messages"
KEY_FILE = Path(__file__).resolve().parents[1] / "API keys" / "Claude API.txt"
#: Haiku 5.5 takes no temperature and no thinking budget: thinking is off, or
#: "adaptive" at an effort level (medium, as Qwen 3.8 runs).
CLAUDE_EFFORT = "medium"
#: Batch prices per million tokens, in / out (Anthropic's price list, 26 Oct 2026);
#: asked directly, twice these.
BATCH_PRICES = {"claude-haiku-5-5": (0.05, 0.25), "claude-sonnet-5-5": (1.0, 5.0)}
#: Average tokens a meaning request (prompt 0.4, a minute either side) reads and, per
#: model with thinking allowed at medium, writes: sample-v3's 400 rows. For the estimate
#: printed before sending; other asks are longer or shorter.
TOKENS_IN = 2210
TOKENS_OUT = {"claude-haiku-5-5": 482, "claude-sonnet-5-5": 130}


def per_model(table: dict, model: str):
    return next((v for k, v in table.items() if k != "*" and model.startswith(k)), table["*"])


def window(tokens: int) -> int:
    """A context window that holds this many tokens, in steps of 8k."""
    return -(-tokens // 8192) * 8192
KINDS = ["meaning", "invented", "edits", "skips"]
ASKS = ["labelled", "rule", "blind", "rank", "misses"]
WINDOW = 30.0       # seconds either side of a case, for "minute"
RANK_WORDS = 12     # reference words either side of the spot, for "rank"


# ---------------------------------------------------------------------------
# What the reference is, and who would rely on the text, per data set
# ---------------------------------------------------------------------------

RECORDING = {
    "scotus": "a U.S. Supreme Court oral argument",
    "edacc": "a recorded video call between two people (the EdAcc accent data set)",
    "coraal": "a recorded sociolinguistic interview (CORAAL, the Corpus of Regional African American Language)",
    "earnings22": "a company earnings call (the Earnings-22 data set)",
}
REFERENCE = {
    "scotus": "the official transcript made by the Court's reporter: a careful word-for-word "
              "record with speaker names; \"--\" marks where someone breaks off or is cut off",
    "edacc": "a hand transcript made for the data set, in capitals with little punctuation",
    "coraal": "a hand transcript made for the corpus, which keeps the speaker's own grammar "
              "(African American English) word for word",
    "earnings22": "a hand transcript made for the data set; its transcribers sometimes left "
                  "stretches out, so it can lack words that were said",
}
READER = {
    "scotus": "a lawyer or judge relying on the court record",
    "edacc": "someone relying on a written record of the call",
    "coraal": "a researcher quoting the interview",
    "earnings22": "an investor or analyst relying on the transcript of the call",
}

#: What each search's label means, in words a reader with no background follows.
SUBKIND = {
    ("meaning", "negation"): "a \"not\" or other negative word on one side only",
    ("meaning", "number"): "a number that differs",
    ("meaning", "word"): "a different content word",
    ("meaning", "dropped"): "a single word that carries meaning (only, never, all...) left out",
    ("meaning", "added"): "a single word that carries meaning (only, never, all...) put in",
    ("invented", "word"): "a word written where the audio is silent or nearly so, with nothing in the reference",
    ("invented", "phrase"): "words written where the audio is silent or nearly so, with nothing in the reference",
    ("skips", "short"): "a stretch of clear speech left out",
    ("skips", "long"): "a long stretch of clear speech left out",
    ("skips", "whole-turn"): "a speaker's whole turn left out",
}
FEATURES = {
    "habitual-be": "habitual \"be\" (\"he be working\" means he usually works)",
    "zero-copula": "no \"is\" or \"are\" (\"she nice\")",
    "aint": "\"ain't\"",
    "third-person-s": "a verb without -s (\"she teach\")",
    "was-levelling": "\"was\" with a plural (\"they was\")",
    "negative-concord": "a double negative (\"I don't get no\")",
    "existential-it": "\"it\" for \"there\" (\"it's a store on the corner\")",
    "completive-done": "\"done\" for something finished (\"I done told you\")",
    "finna": "\"finna\" for \"about to\"",
}


def subkind_text(kind: str, subkind: str) -> str:
    if kind == "edits" and subkind == "restart":
        return ("a restart or repeated word (\"I -- I think\", \"the the\") cleaned up into "
                "smooth speech")
    if kind == "edits":
        return ("the speaker's African American English grammar rewritten into standard "
                f"English: {FEATURES.get(subkind, subkind)}")
    return SUBKIND.get((kind, subkind), f"{kind}, {subkind}")


#: The follow-up question for each kind, and the answers allowed.
FOLLOW = {
    "meaning": ("What is the engine's word at the spot?", {
        "changes meaning": "a different real word that changes what is said",
        "same thing": "a name, spelling or form of the same word; a reader would still understand",
        "garble": "a misheard word that makes nonsense",
        "cant tell": "the text is not enough to say"}),
    "number": ("Is the engine's number a different quantity?", {
        "different quantity": "a different amount, date, count or figure",
        "same quantity": "the same quantity written another way",
        "not a number": "no real number is involved"}),
    "negation": ("Is a negation really lost or added?", {
        "negation lost": "the reference has a negative the engine's text lacks",
        "negation added": "the engine's text has a negative the reference lacks",
        "no change": "both say yes, or both say no"}),
    "edits": ("Is that grammar really in the reference, and does the engine's version say "
              "something different? (\"he be working\" means he usually works; \"he's working\" "
              "means right now.)", {
                  "meaning changed": "the feature is there and the engine's version means something else",
                  "meaning kept": "the feature is there and the engine's version means the same",
                  "not there": "the reference doesn't really have that feature here"}),
    "restart": ("Does cleaning up the restart change what the record shows?", {
        "meaning changed": "the cleaned-up version says something different",
        "only the stumble lost": "the same words and meaning, only the stumble is gone",
        "not a restart": "the reference has no restart or repeat here"}),
    "invented": ("Where do the extra words seem to come from?", {
        "continues the talk": "they fit what is being said, as if the speaker went on",
        "stock phrase": "a set phrase from nowhere (\"thank you\", \"I've already said that\")",
        "unrelated": "words that don't fit anything around them",
        "cant tell": "the text is not enough to say"}),
    "skips": ("What does leaving it out do?", {
        "content lost, gap hidden": "the left-out words carry content and the engine's text reads on as if nothing is missing",
        "content lost, gap shows": "the left-out words carry content and the engine's text shows a break",
        "little lost": "the left-out words carry little content"}),
}


def follow_key(case: dict) -> str:
    if case["kind"] == "meaning" and case["subkind"] in ("number", "negation"):
        return case["subkind"]
    if case["kind"] == "edits" and case["subkind"] == "restart":
        return "restart"
    return case["kind"]


MEANING = {
    "same": "the same words, or the same words written differently",
    "reworded": "different words, the same meaning",
    "changed": "a different meaning",
    "opposite": "the meaning is reversed (yes/no, can/can't, is/isn't, more/less)",
    "garbled": "not sensible English; a reader can't tell what was meant",
}
SEVERITY = {
    0: "nothing a reader would care about",
    1: "a slip a reader would read past",
    2: "a wrong detail",
    3: "a wrong fact: a number, a party, who did what",
    4: "reverses or loses the point being made",
}
THREE = ["yes", "maybe", "no"]


# ---------------------------------------------------------------------------
# The sample
# ---------------------------------------------------------------------------

SHARED = ["corpus", "part", "recording", "engine", "kind", "subkind", "start", "end", "record",
          "engine_wrote", "record_context", "engine_context", "others_right", "evidence"]


def spread(rows: pd.DataFrame, n: int, rng: random.Random) -> list[int]:
    """n row labels taken in turn from each data set and engine, best first."""
    groups: dict = {}
    for label, row in rows.iterrows():
        groups.setdefault((row.corpus, row.engine), []).append(label)
    order = list(groups)
    rng.shuffle(order)
    picked: list[int] = []
    corpora: dict = {}
    while len(picked) < n and any(groups.values()):
        for key in order:
            # At most two from one data set until every data set has had a turn.
            if groups[key] and len(picked) < n and corpora.get(key[0], 0) < max(2, n // 2):
                picked.append(groups[key].pop(0))
                corpora[key[0]] = corpora.get(key[0], 0) + 1
        if all(not g or corpora.get(k[0], 0) >= max(2, n // 2) for k, g in groups.items()):
            break
    return picked


def make_sample(seed: int = 2026) -> pd.DataFrame:
    rng = random.Random(seed)
    parts = []
    for kind in KINDS:
        short = pd.read_csv(FAILURES / kind / "shortlist.csv", dtype=str, keep_default_na=False)
        short["source"] = "shortlist"
        short["_rank"] = -(short.interest.astype(int) * 10 + short.clarity.astype(int))
        short = short.sample(frac=1, random_state=seed).sort_values("_rank", kind="stable")
        parts.append(short.loc[spread(short, 5, rng)])

    taken = {(r.corpus, r.recording, r.engine, r.start) for p in parts for r in p.itertuples()}
    draws = [("meaning", "word", 6), ("meaning", "number", 2), ("meaning", "negation", 2),
             ("edits", None, 2), ("invented", None, 2), ("skips", None, 2)]
    for kind, subkind, n in draws:
        cand = pd.read_csv(FAILURES / kind / "candidates.csv", dtype=str, keep_default_na=False)
        if subkind:
            cand = cand[cand.subkind == subkind]
        cand = cand[[(r.corpus, r.recording, r.engine, r.start) not in taken for r in cand.itertuples()]]
        cand = cand.sample(frac=1, random_state=seed)
        cand["source"] = "random"
        parts.append(cand.loc[spread(cand, n, rng)])

    sample = pd.concat(parts, ignore_index=True)
    keep = SHARED + ["source", "interest", "clarity", "explanation"]
    sample = sample.reindex(columns=keep).fillna("")
    sample = pd.concat([sample, pd.DataFrame(controls(sample, rng))], ignore_index=True).fillna("")
    sample.insert(0, "case", [f"s{i + 1:02d}" for i in range(len(sample))])
    sample["expect"] = sample.get("expect", "")
    return sample


def make_random_sample(n: int, seed: int, also_taken: pd.DataFrame | None = None,
                       first_number: int = 1) -> pd.DataFrame:
    """n rows drawn at random from every search's candidates, each kind in proportion
    to its share of all the rows (the first sample over-weighted the small kinds and
    the hand-picked cases, so its scores don't carry over to the rows as a whole).
    Rows in sample-v1 and in also_taken are never drawn."""
    every = {kind: pd.read_csv(FAILURES / kind / "candidates.csv", dtype=str, keep_default_na=False)
             for kind in KINDS}
    total = sum(len(t) for t in every.values())
    # Each kind's share of n, rounded so they add up to n (largest remainders first).
    exact = {kind: n * len(t) / total for kind, t in every.items()}
    counts = {kind: int(x) for kind, x in exact.items()}
    for kind in sorted(exact, key=lambda k: exact[k] - counts[k], reverse=True)[:n - sum(counts.values())]:
        counts[kind] += 1
    first = pd.concat([pd.read_csv(OUT / "sample-v1.csv", dtype=str, keep_default_na=False), also_taken])
    taken = {(r.corpus, r.recording, r.engine, r.start) for r in first.itertuples()}
    parts = []
    for kind, table in every.items():
        table = table[[(r.corpus, r.recording, r.engine, r.start) not in taken for r in table.itertuples()]]
        parts.append(table.sample(n=counts[kind], random_state=seed))
    sample = pd.concat(parts, ignore_index=True)
    sample = sample.sample(frac=1, random_state=seed).reset_index(drop=True)   # kinds mixed, not in blocks
    sample = sample.reindex(columns=SHARED).fillna("")
    sample["source"] = "random"
    sample.insert(0, "case", [f"r{i + first_number:03d}" for i in range(len(sample))])
    for column in ("interest", "clarity", "explanation", "expect"):
        sample[column] = ""
    return sample


def make_full_sample(seed: int) -> pd.DataFrame:
    """Every row: all four searches' candidates and the all-agree spots, in a random
    order, so the first rows of a run sent in parts are a fair cross-section rather
    than one data set. Ids f00001, f00002, ... follow that order."""
    tables = [pd.read_csv(FAILURES / kind / "candidates.csv", dtype=str, keep_default_na=False).assign(source="candidates")
              for kind in KINDS]
    tables.append(pd.read_csv(FAILURES / "meaning" / "all-agree.csv", dtype=str,
                              keep_default_na=False).assign(source="all-agree"))
    every = pd.concat(tables, ignore_index=True)
    every = every.sample(frac=1, random_state=seed).reset_index(drop=True)
    sample = every.reindex(columns=SHARED + ["source"]).fillna("")
    sample.insert(0, "case", [f"f{i + 1:05d}" for i in range(len(sample))])
    for column in ("interest", "clarity", "explanation", "expect"):
        sample[column] = ""
    return sample


#: How many cases of each group the prompt-combination subset takes from each data
#: set: 75 each, so the Supreme Court is not swamped by CORAAL. The rarer groups,
#: likelier to hold an interesting case, get more than their share; ordinary word
#: swaps stay in as the counterweight. Only CORAAL has dialect edits.
COMBO = {"negation": 20, "number": 10, "all-agree": 12, "invented": 6, "skips": 7, "word/other": 20}
COMBO_CORAAL = {**COMBO, "negation": 18, "number": 8, "all-agree": 10, "edits": 10, "word/other": 16}


def group_of(row) -> str:
    if row["source"] == "all-agree":
        return "all-agree"
    if row["kind"] != "meaning":
        return row["kind"]
    if row["subkind"] in ("negation", "aint"):
        return "negation"
    return "number" if row["subkind"] == "number" else "word/other"


def make_combo_sample(full: pd.DataFrame) -> pd.DataFrame:
    """The cases for testing which combination of prompts finds the interesting
    ones (future-work-llm-judge.md). A full sample's order is random, so the lowest
    case ids in each group are a random draw; they are also the cases the first
    part of a run in parts answered already, so those answers carry over. Ids and
    rows are the full sample's own: answers go to its answer files."""
    full = full.assign(group=full.apply(group_of, axis=1))
    parts = []
    for corpus, rows in full.groupby("corpus"):
        for group, n in (COMBO_CORAAL if corpus == "coraal" else COMBO).items():
            parts.append(rows[rows.group == group].sort_values("case").head(n))
    return pd.concat(parts).sort_values("case")


def add_agree_sample(base: str, n: int, seed: int) -> pd.DataFrame:
    """A sample plus n spots drawn at random where every engine wrote the same thing
    against the reference (meaning/all-agree.csv). The random rows hardly ever hold
    one, because the meaning search sets them apart, but they are where a slip the
    reference tidied up is likely: the test for 0.4's misspoke question."""
    first = pd.read_csv(OUT / f"{base}.csv", dtype=str, keep_default_na=False)
    agree = pd.read_csv(FAILURES / "meaning" / "all-agree.csv", dtype=str, keep_default_na=False)
    extra = agree.sample(n=n, random_state=seed).reset_index(drop=True).reindex(columns=SHARED).fillna("")
    extra["source"] = "all-agree"
    extra.insert(0, "case", [f"a{i + 1:03d}" for i in range(n)])
    for column in ("interest", "clarity", "explanation", "expect"):
        extra[column] = ""
    return pd.concat([first, extra], ignore_index=True)


def controls(sample: pd.DataFrame, rng: random.Random) -> list[dict]:
    """Four cases with a known answer, on real Supreme Court sentences.

    Two "same": a real meaning case whose engine side is replaced by the
    reference's own words (expected: meaning same, severity 0, and the rule's
    evidence, which still describes the old difference, judged wrong). Two
    "opposite": "is" made "is not" and "can" made "can't" in the middle of a
    real turn (expected: meaning opposite, severity 3 or 4).
    """
    out = []
    scotus = sample[(sample.corpus == "scotus") & (sample.kind == "meaning")]
    for _, row in scotus.head(2).iterrows():
        out.append({**{k: row[k] for k in SHARED}, "engine": "Control", "engine_wrote": row.record,
                    "engine_context": row.record_context, "source": "control", "expect": "same"})
    jobs = [j for j in lineup.recordings("scotus", ["OT2021"])]
    rng.shuffle(jobs)
    for word, flipped in [("is", "is not"), ("can", "can't")]:
        for job in jobs:
            lined = lineup.load(job)
            transcript, ref_words, _, _ = lined[next(iter(lined))]
            times = lineup.reference_times(lined)
            turn_of = lineup.word_turns(transcript)
            spots = [k for k in range(15, len(ref_words) - 15)
                     if ref_words[k] == word and ref_words[k + 1].isalpha() and ref_words[k + 1].islower()
                     and turn_of[k - 12] == turn_of[k + 12] and "--" not in " ".join(ref_words[k - 6:k + 7])]
            if not spots:
                continue
            k = rng.choice(spots)
            before, after = " ".join(ref_words[k - 6:k]), " ".join(ref_words[k + 1:k + 7])
            out.append({"corpus": "scotus", "part": job["term"], "recording": job["docket"],
                        "engine": "Control", "kind": "meaning", "subkind": "negation",
                        "start": f"{times[k]:.2f}", "end": f"{times[k + 1]:.2f}",
                        "record": word, "engine_wrote": flipped,
                        "record_context": f"{before} [{word}] {after}",
                        "engine_context": f"{before} [{flipped}] {after}", "others_right": "",
                        "evidence": f"negation: record '{word}', engine '{flipped}'",
                        "source": "control", "expect": "opposite"})
            break
    return out


# ---------------------------------------------------------------------------
# Finding a case in the full transcripts
# ---------------------------------------------------------------------------

def norm(word: str) -> str:
    return re.sub(r"[^\w']", "", word.lower()).strip("'")


def tokens(text: str) -> list[str]:
    return [n for n in (norm(w) for w in text.split()) if n]


def split_context(context: str) -> tuple[list[str], list[str]]:
    """The words before and after the bracketed spot ("^" marks an empty one)."""
    if "[" in context and "]" in context:
        before, rest = context.split("[", 1)
        return tokens(before), tokens(rest.split("]", 1)[1])
    if "^" in context:
        before, after = context.split("^", 1)
        return tokens(before), tokens(after)
    return tokens(context), []


def locate(words: list[str], times: list[float], before: list[str], inside: list[str],
           after: list[str], t0: float, reach: float) -> tuple[int, int, float]:
    """Where a saved snippet sits in a full word list: (first, end, share matched).

    The searches saved their context in slightly different forms (raw words,
    or lower-cased with numbers spelled out), so this counts matching words
    rather than demanding all of them, and among equal matches takes the one
    nearest the case's time.
    """
    index = [i for i, w in enumerate(words) if norm(w)]
    seq = [norm(words[i]) for i in index]
    if not any(abs(times[i] - t0) <= reach for i in index):
        # Nothing within reach (an engine that went quiet for a long stretch):
        # look further out rather than give up.
        reach = min((abs(times[i] - t0) for i in index), default=0) + reach
    best = (-1, 0.0, 0)
    for p in range(len(seq) + 1):
        t = times[index[p]] if p < len(seq) else times[-1]
        if abs(t - t0) > reach:
            continue
        score = sum(p + k < len(seq) and seq[p + k] == w for k, w in enumerate(inside))
        score += sum(p - 1 - k >= 0 and seq[p - 1 - k] == w for k, w in enumerate(reversed(before)))
        tail = p + len(inside)
        score += sum(tail + k < len(seq) and seq[tail + k] == w for k, w in enumerate(after))
        if score > best[0] or (score == best[0] and abs(t - t0) < best[1]):
            best = (score, abs(t - t0), p)
    p = best[2]
    first = index[p] if p < len(seq) else len(words)
    end = index[p + len(inside) - 1] + 1 if inside and p + len(inside) - 1 < len(seq) else first
    total = len(before) + len(inside) + len(after)
    return first, end, round(best[0] / total, 2) if total else 1.0


def speaker_names(corpus: str, transcript) -> list[str]:
    """A readable name for each turn. Supreme Court names are kept, since who is
    asking (a Justice) and who is answering (counsel) carries meaning."""
    if corpus == "scotus":
        return [t.speaker for t in transcript.turns]
    seen: dict = {}
    out = []
    for t in transcript.turns:
        if corpus == "coraal" and "_int_" in t.speaker:
            out.append("Interviewer")
            continue
        if t.speaker not in seen:
            seen[t.speaker] = f"Speaker {'ABCDEFGHIJ'[len(seen)] if corpus == 'edacc' else len(seen) + 1}"
        out.append(seen[t.speaker])
    return out


class Case:
    """One sample row with the full transcripts it came from."""

    def __init__(self, row: dict, cache: dict):
        self.row = row
        key = (row["corpus"], row["part"], row["recording"])
        if key not in cache:
            jobs = lineup.recordings(row["corpus"], [row["part"]], use_capped=SAMPLE.stem not in BEFORE_CAPPED)
            job = next(j for j in jobs if j["docket"] == row["recording"])
            lined = lineup.load(job)
            cache.clear()   # one recording at a time is plenty; the sample is in recording order
            cache[key] = (job, lined, lineup.reference_times(lined))
        self.job, self.lined, self.ref_time = cache[key]
        self.transcript, self.ref_words, _, _ = self.lined[next(iter(self.lined))]
        self.turn_of = lineup.word_turns(self.transcript)
        self.names = speaker_names(row["corpus"], self.transcript)
        start, end = float(row["start"]), float(row["end"])
        self.start, self.end = start, end

        before, after = split_context(row["record_context"])
        self.r0, self.r1, self.ref_match = locate(self.ref_words, self.ref_time, before,
                                                  tokens(row["record"]), after, start, 90)
        if row["engine"] == "Control":
            # The engine side is the reference with the spot replaced.
            self.eng_words = (self.ref_words[:self.r0] + row["engine_wrote"].split() + self.ref_words[self.r1:])
            n = len(row["engine_wrote"].split())
            spot_time = [self.ref_time[min(self.r0, len(self.ref_time) - 1)]] * n
            self.eng_time = self.ref_time[:self.r0] + spot_time + self.ref_time[self.r1:]
            self.e0, self.e1, self.eng_match = self.r0, self.r0 + n, 1.0
        else:
            words = self.lined[row["engine"]][3]
            self.eng_words = [w.text.strip() for w in words]
            self.eng_time = [w.start if w.start is not None else 0.0 for w in words]
            before, after = split_context(row["engine_context"])
            self.e0, self.e1, self.eng_match = locate(self.eng_words, self.eng_time, before,
                                                      tokens(row["engine_wrote"]), after, start, 20)

    # --- text blocks ---------------------------------------------------------

    def new_speaker(self, i: int) -> bool:
        """Whether word i starts a new speaker (CORAAL and EdAcc split one
        speaker's talk into many short turns; one name per stretch is enough)."""
        return self.names[self.turn_of[i]] != self.names[self.turn_of[i - 1]]

    def window(self) -> tuple[int, int, int, int]:
        """Reference and engine word ranges for 30 s either side of the case."""
        lo_t, hi_t = self.start - WINDOW, self.end + WINDOW
        rlo = next((i for i, t in enumerate(self.ref_time) if t >= lo_t), 0)
        rhi = next((i for i, t in enumerate(self.ref_time) if t > hi_t), len(self.ref_words))
        rlo, rhi = min(rlo, max(0, self.r0 - 5)), max(rhi, min(len(self.ref_words), self.r1 + 5))
        elo = next((i for i, t in enumerate(self.eng_time) if t >= lo_t), 0)
        ehi = next((i for i, t in enumerate(self.eng_time) if t > hi_t), len(self.eng_words))
        elo, ehi = min(elo, max(0, self.e0 - 5)), max(ehi, min(len(self.eng_words), self.e1 + 5))
        return rlo, rhi, elo, ehi

    def reference_block(self, lo: int, hi: int, mark: bool = True) -> str:
        parts: list[str] = []
        for i in range(lo, hi):
            if i == lo or self.new_speaker(i):
                parts.append(("\n" if parts else "") + self.names[self.turn_of[i]] + ":")
            if mark and i == self.r0:
                parts.append("[[" if self.r1 > self.r0 else "[[]]")
            parts.append(self.ref_words[i])
            if mark and self.r1 > self.r0 and i == self.r1 - 1:
                parts.append("]]")
        if mark and self.r0 >= hi:
            parts.append("[[]]")
        return glue(parts)

    def engine_block(self, lo: int, hi: int, mark: bool = True) -> str:
        parts: list[str] = []
        for i in range(lo, hi):
            if mark and i == self.e0:
                parts.append("[[" if self.e1 > self.e0 else "[[]]")
            parts.append(self.eng_words[i])
            if mark and self.e1 > self.e0 and i == self.e1 - 1:
                parts.append("]]")
        if mark and self.e0 >= hi:
            parts.append("[[]]")
        return self.whole_words(glue(parts))

    def whole_words(self, text: str) -> str:
        """Whisper splits a hyphenated word in two ("dope -themed"); a judge reads
        the stray hyphen as the engine's own mistake, so it is joined back."""
        return lineup.join_split_hyphens(text) if self.row["engine"] == "Whisper" else text

    def wrote(self) -> str:
        """What the engine wrote at the spot, as a whole word ("dope-themed", not "-themed")."""
        wrote = self.row["engine_wrote"]
        if self.row["engine"] == "Whisper" and re.match(r"-[\w$]", wrote):
            whole = re.search(r"\[\[(.*?)\]\]", self.whole_words(brackets(self.row["engine_context"])))
            return whole.group(1) if whole else wrote
        return self.whole_words(wrote)

    def context(self, size: str) -> str:
        if size == "line":
            return (f"Reference:\n{brackets(self.row['record_context'])}\n\n"
                    f"Speech recognition engine:\n{self.whole_words(brackets(self.row['engine_context']))}")
        rlo, rhi, elo, ehi = self.window()
        minute = (f"Reference, about a minute around the spot:\n{self.reference_block(rlo, rhi)}\n\n"
                  f"Speech recognition engine, the same minute (it writes no speaker names):\n"
                  f"{self.engine_block(elo, ehi)}")
        if size == "minute":
            return minute
        return f"{minute}\n\nThe spot is at {clock(self.start)} into the recording."

    def whole_reference(self) -> str:
        return self.reference_block(0, len(self.ref_words), mark=False)

    def blind_versions(self) -> tuple[str, str]:
        """(reference version, engine version): the reference minute, lower-cased
        without punctuation, with either the reference's or the engine's words
        at the spot. Only the spot differs, so style is no clue."""
        rlo, rhi, _, _ = self.window()

        def version(spot: list[str]) -> str:
            parts: list[str] = []
            for i in range(rlo, rhi):
                if i == rlo or self.new_speaker(i):
                    parts.append(("\n" if parts else "") + self.names[self.turn_of[i]] + ":")
                if i == self.r0:
                    parts.append("[[" + " ".join(spot) + "]]")
                if self.r0 <= i < self.r1:
                    continue
                parts.append(" ".join(tokens(self.ref_words[i])))
            if self.r0 >= rhi:
                parts.append("[[" + " ".join(spot) + "]]")
            return glue(parts)

        return version(tokens(self.row["record"])), version(tokens(self.row["engine_wrote"]))

    def engine_versions(self, either_side: int = RANK_WORDS) -> dict:
        """Each engine's words over the reference's spot and a few words either
        side, the spot in [[ ]], from its alignment with the reference."""
        out = {}
        for name, (_, _, alignment, words) in self.lined.items():
            text = aligned_text(alignment, [w.text.strip() for w in words], max(0, self.r0 - either_side),
                                min(len(self.ref_words), self.r1 + either_side), self.r0, self.r1)
            out[name] = text
        return out


def glue(parts: list[str]) -> str:
    text = " ".join(p for p in parts if p)
    return text.replace("[[ ", "[[").replace(" ]]", "]]").replace("\n ", "\n")


def brackets(context: str) -> str:
    if "[" in context:
        return context.replace("[", "[[").replace("]", "]]")
    return context.replace("^", "[[]]")


def clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def aligned_text(alignment, hyp_words: list[str], lo: int, hi: int, r0: int, r1: int) -> str:
    """The engine words lined up with reference words lo..hi (raw indices), with
    the part lined up with r0..r1 in [[ ]]. A word the engine put in between two
    reference words sits before the second; it belongs to an empty spot (an
    invented word) when it sits exactly there."""
    rs, hs = alignment.reference.source_index, alignment.hypothesis.source_index
    end_of_reference = (rs[-1] + 1) if rs else 0
    picked: dict = {}   # hyp raw index -> (where in the reference, in the spot)
    for c in alignment.chunks:
        if c.kind == "insert":
            at = rs[c.ref_start] if c.ref_start < len(rs) else end_of_reference
            if lo <= at <= hi:
                # Words put in right beside a spot are part of what went wrong there.
                spot = r0 <= at <= r1
                for j in range(c.hyp_start, c.hyp_end):
                    picked.setdefault(hs[j], (at - 0.5, spot))
            continue
        if c.ref_end - c.ref_start == c.hyp_end - c.hyp_start:
            # Word for word (always so for "equal"): each engine word goes with its own.
            pairs = [([rs[i]], hs[j]) for i, j in zip(range(c.ref_start, c.ref_end), range(c.hyp_start, c.hyp_end))]
        else:
            refs = [rs[i] for i in range(c.ref_start, c.ref_end)]
            pairs = [(refs, hs[j]) for j in range(c.hyp_start, c.hyp_end)]
        for refs, j in pairs:
            if refs and lo <= min(refs) < hi:
                picked.setdefault(j, (min(refs), any(r0 <= r < r1 for r in refs)))
    parts: list[str] = []
    inside = marked = False
    for j in sorted(picked):
        where, spot = picked[j]
        if not marked and not spot and where >= r0 and not any(s for _, s in picked.values()):
            parts.append("[[]]")      # the engine wrote nothing at the spot
            marked = True
        if spot and not inside:
            parts.append("[[")
            inside = marked = True
        if not spot and inside:
            parts.append("]]")
            inside = False
        parts.append(hyp_words[j])
    if inside:
        parts.append("]]")
    if not marked:
        parts.append("[[]]")
    return glue(parts)


# ---------------------------------------------------------------------------
# The prompts
# ---------------------------------------------------------------------------

def system_labelled(corpus: str) -> str:
    # The same for every case of a data set, so a run of cases from one recording
    # starts every prompt with the same words.
    return (
        f"You compare two transcripts of {RECORDING[corpus]}. The reference is {REFERENCE[corpus]}. "
        "The other was written by a speech recognition engine. The spot to judge is marked "
        "[[ ]] in both (an empty [[]] means one side has nothing there). Treat the reference as "
        "what was said. You read text only; you cannot hear the audio. Judge the spot, not other "
        "differences around it. Answer with JSON only.")


def labelled_message(case: Case, size: str) -> str:
    row = case.row
    question, answers = FOLLOW[follow_key(row)]
    head = (f"Full reference transcript of the recording, for background:\n{case.whole_reference()}\n\n"
            "----\n\n") if size == "whole" else ""
    return head + "\n".join([
        case.context(size), "",
        f"At the spot the reference has: \"{row['record']}\"",
        f"At the spot the engine wrote: \"{row['engine_wrote']}\"", "",
        "Answer:",
        "- meaning: what the engine's text at the spot does to the meaning, compared with the reference. One of:",
        *[f"    {k}: {v}" for k, v in MEANING.items()],
        "- severity: how much it matters, 0 to 4:",
        *[f"    {k}: {v}" for k, v in SEVERITY.items()],
        "- noticeable: reading only the engine's text, would a careful reader notice something "
        "is wrong here? yes, maybe or no.",
        f"- follow_up: {question} One of:",
        *[f"    {k}: {v}" for k, v in answers.items()],
        f"- stakes: if {READER[row['corpus']]} used the engine's text, could this error mislead "
        "them? yes, maybe or no.",
        "- stakes_how: one sentence on how, or why not.",
        "- reason: one plain sentence, for a reader with no background, on what went wrong at the spot.",
    ])


def labelled_schema(case: Case) -> dict:
    answers = list(FOLLOW[follow_key(case.row)][1])
    return obj({"meaning": enum(list(MEANING)), "severity": {"type": "integer", "minimum": 0, "maximum": 4},
                "noticeable": enum(THREE), "follow_up": enum(answers),
                "stakes": enum(THREE), "stakes_how": STR, "reason": STR})


def rule_message(case: Case) -> str:
    """The rule's claim, asked about on its own, after the text."""
    row = case.row
    return "\n".join([
        case.context("minute"), "",
        f"A rule-based checker flagged the marked spot as {subkind_text(row['kind'], row['subkind'])}. "
        f"Its evidence: {row['evidence']}", "",
        "The checker can be wrong. Read both texts at the spot yourself before deciding.", "",
        "Answer:",
        "- reference_has: the reference's words at the spot, copied exactly.",
        "- engine_has: the engine's words at the spot, copied exactly.",
        "- rule_right: from the two texts, is the checker's label and evidence right? yes, partly or no.",
        "- rule_reason: one sentence on why.",
    ])


def system_blind(corpus: str) -> str:
    return (
        f"You read two versions of the same stretch of {RECORDING[corpus]}. They are word for word "
        "the same except at the spot marked [[ ]]; an empty [[]] means that version has nothing "
        "there. One version is wrong at the spot. The text is lower-cased without punctuation, so "
        "spelling and style are no clue. From the sense, the grammar, what the speakers are talking "
        "about and how people talk in this setting, which version is more likely what the speaker "
        "actually said? Answer with JSON only.")


def blind_message(first: str, second: str) -> str:
    return "\n".join([
        f"Version A:\n{first}", "", f"Version B:\n{second}", "",
        "Answer:",
        "- pick: A, B, or cant tell.",
        "- sure: 1 (a guess), 2 (fairly sure) or 3 (sure).",
        "- reason: one sentence.",
    ])


BLIND_SCHEMA = None  # set below, after the helpers


def system_rank(corpus: str) -> str:
    return (
        f"You compare transcripts of {RECORDING[corpus]}. The reference is {REFERENCE[corpus]}; "
        "treat it as what was said. Several speech recognition engines wrote the same stretch; "
        "their names are hidden. Rank them on how well each keeps the meaning of the reference at "
        "the spot marked [[ ]], not on spelling, punctuation or small slips that change nothing. "
        "Answer with JSON only.")


def rank_message(case: Case, shown: list[tuple[str, str]]) -> str:
    rlo, rhi, _, _ = case.window()
    lines = [f"Reference, about a minute around the spot:\n{case.reference_block(rlo, rhi)}", "",
             "What each engine wrote around the spot (an empty [[]] means it wrote nothing there):"]
    lines += [f"- {label}: {text}" for label, text in shown]
    lines += ["", "Answer:",
              "- ranks: for each engine, its rank, 1 for the best at keeping the meaning. Engines "
              "that keep it equally well get the same rank.",
              "- reason: one sentence."]
    return "\n".join(lines)


def rank_schema(labels: list[str]) -> dict:
    ranks = obj({label: {"type": "integer", "minimum": 1, "maximum": len(labels)} for label in labels})
    return obj({"ranks": ranks, "reason": STR})


def system_misses(corpus: str) -> str:
    return (
        f"You compare two transcripts of {RECORDING[corpus]}. The reference is {REFERENCE[corpus]}; "
        "treat it as what was said. The other was written by a speech recognition engine, which "
        "writes no speaker names. Answer with JSON only.")


def misses_message(case: Case) -> str:
    rlo, rhi, elo, ehi = case.window()
    return "\n".join([
        f"Reference, about a minute:\n{case.reference_block(rlo, rhi, mark=False)}", "",
        f"Speech recognition engine, the same minute:\n{case.engine_block(elo, ehi, mark=False)}", "",
        "List every place where the engine's text says something different from the reference: "
        "a changed or reversed meaning, a wrong word that matters, a different number, words that "
        "carry content left out or added. Leave out spelling, punctuation, capitals, \"uh\" and "
        "\"um\", repeated words, and names spelled differently. The two may start and end at "
        "slightly different words; ignore the edges. If there are none, give an empty list.",
        "For each: reference (its words there, or empty), engine (its words there, or empty), "
        "severity 0 to 4 (0 nothing a reader would care about, 4 reverses or loses the point), "
        "what (a few words on what changed).",
    ])


STR = {"type": "string"}


def enum(values: list) -> dict:
    return {"type": "string", "enum": values}


def obj(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties)}


BLIND_SCHEMA = obj({"pick": enum(["A", "B", "cant tell"]), "sure": {"type": "integer", "minimum": 1, "maximum": 3},
                    "reason": STR})
RULE_SCHEMA = obj({"reference_has": STR, "engine_has": STR, "rule_right": enum(["yes", "partly", "no"]),
                   "rule_reason": STR})
MISSES_SCHEMA = obj({"differences": {"type": "array", "items": obj({
    "reference": STR, "engine": STR, "severity": {"type": "integer", "minimum": 0, "maximum": 4}, "what": STR})}})


# ---------------------------------------------------------------------------
# Prompt 0.3 (24 Oct 2026): the same cases, asked the way the research on
# judges of this size suggests (findings/judge/prompting-research.md):
#   - the spot in HTML's <mark> tag, not [[ ]] (which is wiki-link markup);
#     "(nothing)" written out where one side has no words;
#   - fewer questions a request: meaning, stakes and the cold read apart;
#   - the reason first in every answer, so the verdict follows the reasoning;
#   - the severity scale anchored with worked examples, and a rule for
#     left-out words (0.2's skips came out 3-4 almost every time);
#   - "would a reader notice" asked as a cold read of the engine's text alone;
#   - room to say the reference itself looks wrong;
#   - rank shows 3 words either side, not 12; misses at most 5, worst first.
# ---------------------------------------------------------------------------

ASKS_V3 = ["meaning", "stakes", "cold", "rule", "blind", "rank", "misses"]
SPOT_WORDS = 3

SEVERITY_GUIDE = "\n".join([
    "Severity, 0 to 4, with examples:",
    '  0  nothing a reader would care about. "I I think" -> "I think"; "gonna" -> "going to"',
    '  1  a slip a reader would read past. "we went to the store and then home" -> "we went to the store then home"',
    '  2  a wrong detail. "she moved here in the spring" -> "she moved here in the fall"',
    '  3  a wrong fact: a number, a party, who did what. "revenue grew 15 percent" -> "revenue grew 50 percent"',
    '  4  reverses or loses the point. "we did not approve the merger" -> "we did approve the merger"',
    'Words left out or added: rate them by what they carried. A lost "yeah, right" is 0 or 1; '
    "a lost clause with a fact in it is 3; a lost answer that changes what the speaker meant is 4.",
])

AAE_NOTE = (
    "The reference keeps African American English grammar. Written as standard English, it changes "
    "the meaning only when the feature carries meaning: habitual \"be\" does (\"he be working\" means "
    "he usually works; \"he's working\" means right now); a verb without -s is present tense (\"he "
    "work there\" means he works there now; \"he worked there\" puts it in the past); a dropped "
    "\"is\" or \"are\" does not (\"they not ready\" means \"they're not ready\").")


def tagged(text: str) -> str:
    """0.2's [[ ]] marks as <mark> tags, with an empty side written out."""
    text = text.replace("[[]]", "<mark>(nothing)</mark>")
    return re.sub(r"\[\[(.*?)\]\]", r"<mark>\1</mark>", text, flags=re.S)


def said(words: str) -> str:
    return f'"{words}"' if words.strip() else "(nothing)"


def system_v3(corpus: str, marked: bool = True) -> str:
    return (
        f"You check a speech recognition engine's transcript of {RECORDING[corpus]} against a reference "
        f"transcript. The reference is {REFERENCE[corpus]}. It is usually right, but people make "
        "mistakes too. You read text only; you cannot hear the audio. "
        + ("The place to judge is marked with <mark> and </mark>; <mark>(nothing)</mark> means that "
           "text has no words there. " if marked else "")
        + "Answer in JSON.")


def at_the_spot(case: Case) -> str:
    row = case.row
    return f"At the marked place the reference has {said(row['record'])}; the engine has {said(case.wrote())}."


def meaning_message_v3(case: Case, size: str) -> str:
    row = case.row
    question, answers = FOLLOW[follow_key(row)]
    head = (f"The full reference transcript, for background:\n{case.whole_reference()}\n\n----\n\n"
            if size == "whole" else "")
    return head + "\n".join([
        tagged(case.context(size)), "", at_the_spot(case), "", SEVERITY_GUIDE, "",
        *([AAE_NOTE, ""] if row["corpus"] == "coraal" else []),
        "Answer these, in this order:",
        "- reason: one or two plain sentences on what the engine's text does at the marked place, "
        "compared with the reference. Judge only the marked place.",
        "- meaning: one of",
        *[f"    {k}: {v}" for k, v in MEANING.items()],
        "- severity: 0 to 4, as above.",
        f"- follow_up: {question} One of",
        *[f"    {k}: {v}" for k, v in answers.items()],
        "- reference_doubt: does the reference itself look wrong at the marked place, with the engine's "
        "words making more sense? yes, maybe or no.",
    ])


def meaning_schema_v3(case: Case) -> dict:
    return obj({"reason": STR, "meaning": enum(list(MEANING)),
                "severity": {"type": "integer", "minimum": 0, "maximum": 4},
                "follow_up": enum(list(FOLLOW[follow_key(case.row)][1])),
                "reference_doubt": enum(THREE)})


def stakes_message_v3(case: Case) -> str:
    return "\n".join([
        tagged(case.context("minute")), "", at_the_spot(case), "",
        f"If {READER[case.row['corpus']]} relied on the engine's text here, could the difference at the "
        "marked place mislead them?",
        "Answer, in this order:",
        "- reason: one sentence on how it could mislead them, or why it would not.",
        "- stakes: yes, maybe or no.",
    ])


STAKES_SCHEMA = obj({"reason": STR, "stakes": enum(THREE)})


def system_cold(corpus: str) -> str:
    return (
        f"You read a speech recognition engine's transcript of {RECORDING[corpus]}. Speech recognition "
        "makes mistakes: wrong words, words left out, and words that were never said. You have no other "
        "transcript and no audio. Answer in JSON.")


def cold_message(case: Case) -> str:
    _, _, elo, ehi = case.window()
    return "\n".join([
        f"The engine's transcript, about a minute (it writes no speaker names):\n"
        f"{case.engine_block(elo, ehi, mark=False)}", "",
        "Point out up to 3 places that look wrong to you: words that make no sense here, a sentence "
        "that seems to be missing something, or words that don't fit what is being said. Copy the "
        "words exactly. If nothing looks wrong, give an empty list.",
        "For each, in this order: why (a few words), words (copied exactly).",
    ])


COLD_SCHEMA = obj({"places": {"type": "array", "maxItems": 3, "items": obj({"why": STR, "words": STR})}})


def rule_message_v3(case: Case) -> str:
    row = case.row
    return "\n".join([
        tagged(case.context("minute")), "",
        f"A rule-based checker flagged the marked place as {subkind_text(row['kind'], row['subkind'])}. "
        f"Its evidence: {row['evidence']}",
        "(\"N of N others right\" counts the other engines that wrote what the reference has.)", "",
        "The checker can be wrong. Read both texts at the marked place yourself first.", "",
        "Answer, in this order:",
        "- reference_has: the reference's words at the marked place, copied exactly.",
        "- engine_has: the engine's words at the marked place, copied exactly.",
        "- rule_reason: one sentence: does the evidence match the two texts?",
        "- rule_right: is the checker's label and evidence right? yes, partly or no.",
    ])


RULE_SCHEMA_V3 = obj({"reference_has": STR, "engine_has": STR, "rule_reason": STR,
                      "rule_right": enum(["yes", "partly", "no"])})


def system_blind_v3(corpus: str) -> str:
    return (
        f"You read two versions of the same stretch of {RECORDING[corpus]}. They are word for word the "
        "same except at the place marked with <mark> and </mark>; <mark>(nothing)</mark> means that "
        "version has no words there. One version is wrong at that place. The text is lower-cased without "
        "punctuation, so spelling and style are no clue. Which version is more likely what the speaker "
        "actually said? Judge by the sense, the grammar, what the speakers are talking about and how "
        "people talk in this setting. Answer in JSON.")


def blind_message_v3(first: str, second: str) -> str:
    return "\n".join([
        f"Version A:\n{tagged(first)}", "", f"Version B:\n{tagged(second)}", "",
        "Answer, in this order:",
        "- reason: one or two sentences comparing the two marked places.",
        "- pick: A, B, or cant tell.",
        "- sure: 1 (a guess), 2 (fairly sure) or 3 (sure).",
    ])


BLIND_SCHEMA_V3 = obj({"reason": STR, "pick": enum(["A", "B", "cant tell"]),
                       "sure": {"type": "integer", "minimum": 1, "maximum": 3}})


def rank_message_v3(case: Case, shown: list[tuple[str, str]]) -> str:
    rlo, rhi, _, _ = case.window()
    return "\n".join([
        f"Reference, about a minute:\n{tagged(case.reference_block(rlo, rhi))}", "",
        f"What each engine wrote at the marked place, with {SPOT_WORDS} words either side for context:",
        *[f"- {label}: {tagged(text)}" for label, text in shown], "",
        "Rank the engines on how well the words inside <mark> keep the reference's meaning. The words "
        "outside <mark> are only there to show where it is; ignore their differences. Ignore spelling, "
        "punctuation and capitals.",
        "Answer, in this order:",
        "- reason: one sentence.",
        "- ranks: for each engine, its rank, 1 for the best. Engines that keep the meaning equally well "
        "get the same rank.",
    ])


def rank_schema_v3(labels: list[str]) -> dict:
    ranks = obj({label: {"type": "integer", "minimum": 1, "maximum": len(labels)} for label in labels})
    return obj({"reason": STR, "ranks": ranks})


def misses_message_v3(case: Case) -> str:
    rlo, rhi, elo, ehi = case.window()
    return "\n".join([
        f"Reference, about a minute:\n{case.reference_block(rlo, rhi, mark=False)}", "",
        f"Speech recognition engine, the same minute (it writes no speaker names):\n"
        f"{case.engine_block(elo, ehi, mark=False)}", "",
        SEVERITY_GUIDE, "",
        *([AAE_NOTE, ""] if case.row["corpus"] == "coraal" else []),
        "List the places where the engine's text changes the meaning: a changed or reversed meaning, a "
        "wrong word that matters, a different number, or words that carry content left out or added. "
        "At most 5, worst first. Leave out spelling, punctuation, capitals, fillers (\"uh\", \"um\", "
        "\"like\"), repeated words, names spelled differently, and anything at the very start or end "
        "where the two simply begin or stop at different words. If nothing changes the meaning, give "
        "an empty list.",
        "For each, in this order: what (a few words on what changed), reference (its words there, or "
        "empty), engine (its words there, or empty), severity (0 to 4).",
    ])


MISSES_SCHEMA_V3 = obj({"differences": {"type": "array", "maxItems": 5, "items": obj({
    "what": STR, "reference": STR, "engine": STR, "severity": {"type": "integer", "minimum": 0, "maximum": 4}})}})


def requests_v3(case: Case, asks: list[str], sizes: list[str]) -> list[tuple]:
    """(ask, variant, system, user, schema, extra) for one case, prompt 0.3."""
    row, corpus = case.row, case.row["corpus"]
    out = []
    if "meaning" in asks:
        for size in sizes:
            out.append(("meaning", size, system_v3(corpus), meaning_message_v3(case, size),
                        meaning_schema_v3(case), {}))
    if "stakes" in asks:
        out.append(("stakes", "minute", system_v3(corpus), stakes_message_v3(case), STAKES_SCHEMA, {}))
    if "cold" in asks:
        out.append(("cold", "minute", system_cold(corpus), cold_message(case), COLD_SCHEMA, {}))
    if "rule" in asks:
        out.append(("rule", "minute", system_v3(corpus), rule_message_v3(case), RULE_SCHEMA_V3, {}))
    if "blind" in asks:
        ref, eng = case.blind_versions()
        first_ref = random.Random(row["case"]).random() < 0.5
        for order, ref_first in [("order1", first_ref), ("order2", not first_ref)]:
            a, b = (ref, eng) if ref_first else (eng, ref)
            out.append(("blind", order, system_blind_v3(corpus), blind_message_v3(a, b), BLIND_SCHEMA_V3,
                        {"reference_is": "A" if ref_first else "B"}))
    if "rank" in asks and row["engine"] != "Control":
        versions = list(case.engine_versions(SPOT_WORDS).items())
        random.Random(row["case"]).shuffle(versions)
        shown = [(f"Engine {i + 1}", text) for i, (_, text) in enumerate(versions)]
        key = {f"Engine {i + 1}": name for i, (name, _) in enumerate(versions)}
        out.append(("rank", "minute", system_v3(corpus), rank_message_v3(case, shown),
                    rank_schema_v3([label for label, _ in shown]), {"engines": key}))
    if "misses" in asks:
        out.append(("misses", "minute", system_v3(corpus, marked=False), misses_message_v3(case),
                    MISSES_SCHEMA_V3, {}))
    return out


# ---------------------------------------------------------------------------
# Prompt 0.4 (26 Oct 2026): only the meaning request changes. What the
# reviewers of sample-v2 ran into, and the user's question about slips:
#   - the follow-up had no answer for a word swap that keeps the meaning;
#   - a new question: did the speaker misspeak, and the reference put it right?
#   - for that, how many of the other engines wrote what the reference has and
#     how many wrote what this engine has: a text-only judge's one clue to what
#     was said aloud.
# ---------------------------------------------------------------------------

FOLLOW_V4 = {**FOLLOW, "meaning": ("What is the engine's word at the spot?", {
    "changes meaning": "a different real word that changes what is said",
    "same meaning, other words": "a different word or words that say the same thing",
    "same thing": "a name, spelling or form of the same word; a reader would still understand",
    "garble": "a misheard word that makes nonsense",
    "cant tell": "the text is not enough to say"})}


def other_engines(case: Case) -> str:
    row = case.row
    if row["engine"] == "Control":
        return ""
    # Compared as the searches compare them, on the benchmark rule with the fixes:
    # "$5" is "5 dollars", and "e mails" is "emails". Raw words said fewer engines agreed
    # than the search had counted on one meaning case in nine (bug-audit-2026-11-05.md).
    same_form = lambda text: "".join(normalize_tokens(text.split(), "standard", harmonise=True).tokens)
    ref, mine = same_form(row["record"]), same_form(row["engine_wrote"])
    spots = [same_form(re.search(r"\[\[(.*?)\]\]", text, re.S).group(1))
             for name, text in case.engine_versions(0).items() if name != row["engine"]]
    as_ref, as_mine = sum(s == ref for s in spots), sum(s == mine for s in spots)
    rest = len(spots) - as_ref - as_mine
    return (f"The other {len(spots)} speech recognition engines at the marked place: {as_ref} wrote what the "
            f"reference has, {as_mine} wrote the same as this engine"
            + (f", {rest} wrote something else." if rest else "."))


def meaning_message_v4(case: Case, size: str) -> str:
    row = case.row
    question, answers = FOLLOW_V4[follow_key(row)]
    head = (f"The full reference transcript, for background:\n{case.whole_reference()}\n\n----\n\n"
            if size == "whole" else "")
    others = other_engines(case)
    return head + "\n".join([
        tagged(case.context(size)), "", at_the_spot(case), *([others] if others else []), "",
        SEVERITY_GUIDE, "",
        *([AAE_NOTE, ""] if row["corpus"] == "coraal" else []),
        "Answer these, in this order:",
        "- reason: one or two plain sentences on what the engine's text does at the marked place, "
        "compared with the reference. Judge only the marked place.",
        "- meaning: one of",
        *[f"    {k}: {v}" for k, v in MEANING.items()],
        "- severity: 0 to 4, as above.",
        f"- follow_up: {question} One of",
        *[f"    {k}: {v}" for k, v in answers.items()],
        "- reference_doubt: does the reference itself look wrong at the marked place, with the engine's "
        "words making more sense? yes, maybe or no.",
        "- misspoke: did the speaker probably say the engine's words aloud by mistake (a slip of the "
        "tongue, a wrong word, name or number), with the reference writing what they meant instead? "
        "When the other engines all wrote the same as this engine, the words were probably said aloud. "
        "Answer no for a mishearing, a spelling or nonsense. yes, maybe or no.",
    ])


def meaning_schema_v4(case: Case) -> dict:
    return obj({"reason": STR, "meaning": enum(list(MEANING)),
                "severity": {"type": "integer", "minimum": 0, "maximum": 4},
                "follow_up": enum(list(FOLLOW_V4[follow_key(case.row)][1])),
                "reference_doubt": enum(THREE), "misspoke": enum(THREE)})


def requests_v4(case: Case, asks: list[str], sizes: list[str]) -> list[tuple]:
    """Prompt 0.4: the new meaning request; every other request as in 0.3."""
    out = [("meaning", size, system_v3(case.row["corpus"]), meaning_message_v4(case, size),
            meaning_schema_v4(case), {}) for size in sizes] if "meaning" in asks else []
    return out + requests_v3(case, [a for a in asks if a != "meaning"], sizes)


# ---------------------------------------------------------------------------
# Prompt 0.5 (28 Oct 2026): 0.4 plus one new request, "story". The plan is
# several narrow questions as features, combined by a small model trained on
# labels made by ear, rather than one killer prompt. This one asks straight out
# how good an example the case is, by the criteria in future-work-llm-judge.md.
# ---------------------------------------------------------------------------

ASKS_V5 = ASKS_V3 + ["story"]

STORY = {
    0: "not an error worth showing anyone",
    1: "an ordinary error, the kind every transcript has",
    2: "a good example: it changes what was said, in a way worth showing",
    3: "a striking example: a reader would be misled about something that matters, and would not notice",
}


def story_message(case: Case) -> str:
    row = case.row
    others = other_engines(case)
    return "\n".join([
        tagged(case.context("minute")), "", at_the_spot(case), *([others] if others else []), "",
        *([AAE_NOTE, ""] if row["corpus"] == "coraal" else []),
        "This is for a study of how speech recognition can mislead someone who reads only the machine's "
        "transcript. The best examples change what was said (a reversed meaning, a wrong number, party or "
        f"fact), read naturally so a reader would not suspect them, matter to {READER[row['corpus']]}, and "
        "follow a pattern with a name (\"is an\" heard as \"isn't\"). A case where the reference is wrong "
        "and the engine right is also worth showing.",
        "Answer, in this order:",
        "- reason: one sentence on what would make this case worth showing, or not.",
        "- reads_naturally: would the engine's words at the marked place look normal to someone with only "
        "the engine's text? yes, maybe or no.",
        "- pattern: the kind of mistake in a few words, e.g. \"negation dropped\", \"sound-alike word\", "
        "\"number misheard\", \"words left out\", \"reference wrong\".",
        "- example: 0 to 3",
        *[f"    {k}  {v}" for k, v in STORY.items()],
    ])


STORY_SCHEMA = obj({"reason": STR, "reads_naturally": enum(THREE), "pattern": STR,
                    "example": {"type": "integer", "minimum": 0, "maximum": 3}})


def requests_v5(case: Case, asks: list[str], sizes: list[str]) -> list[tuple]:
    """Prompt 0.5: every request as in 0.4, plus story."""
    out = requests_v4(case, [a for a in asks if a != "story"], sizes)
    if "story" in asks:
        out.append(("story", "minute", system_v3(case.row["corpus"]), story_message(case), STORY_SCHEMA, {}))
    return out


#: Which version each kind of request is at, in each prompt set. 0.2's blind,
#: rank and misses requests kept their 0.1 wording; 0.4 changed only meaning;
#: 0.5 only adds story, so answers to the others carry over from 0.4.
PROMPT_SETS = {"0.2": PROMPT, "0.3": {a: "0.3" for a in ASKS_V3},
               "0.4": {**{a: "0.3" for a in ASKS_V3}, "meaning": "0.4"}}
PROMPT_SETS["0.5"] = {**PROMPT_SETS["0.4"], "story": "0.5"}


# ---------------------------------------------------------------------------
# Prompt 0.6 (31 Oct 2026): 0.5 plus five new requests, for the cases Sonnet
# called reversed or serious (the AAE one only for CORAAL's):
#   - repair: the engine's text alone, the spot marked. What was really said?
#     Can a careful editor put it right without the audio?
#   - cause: why the engine most likely went wrong, and whether the text can
#     settle which version is right or it takes listening;
#   - aae: which African American English feature, if any, is at the spot;
#   - qa_question, then qa_answer: a question written from the reference alone,
#     then answered from each version alone. A second measure of a meaning
#     change, one that asks for no label. qa_answer needs qa_question's answers
#     first, so it is a second run.
# ---------------------------------------------------------------------------

NEW_V6 = ["repair", "cause", "aae", "qa_question", "qa_answer"]
ASKS_V6 = ASKS_V5 + NEW_V6
#: qa_question's answers, by case, read from the answers file before qa_answer is built.
QUESTIONS: dict = {}

CAUSE = {
    "sound-alike": "words that sound like what was said (\"is an\" heard as \"isn't\")",
    "short word": "a short word lost or added (not, no, a, the, and)",
    "usual phrase": "a more usual word or phrase written in place of the one said",
    "dialect or accent": "the speaker's dialect or accent, e.g. a grammar feature written as standard English",
    "number or name": "a number, name or technical term misheard",
    "left out": "a stretch of speech left out",
    "made up": "words with nothing behind them (\"thank you\", a repeated phrase)",
    "reference wrong": "the reference is probably the one in error",
    "other": "none of these",
}
SETTLE = {
    "text": "a careful reader could tell from the text which version is right",
    "audio": "only listening could settle it",
}
AAE_FEATURES = {
    "ain't": "ain't for isn't, aren't, hasn't, haven't or didn't",
    "double negative": "two or more negatives for one (\"I don't know nothing\")",
    "no is/are": "is or are left out (\"they not ready\")",
    "habitual be": "be for something that happens usually (\"he be working\")",
    "no -s": "a present-tense verb without -s, including \"he don't\"",
    "past form": "a past tense without -ed or in another form (\"he come yesterday\")",
    "done or been": "done for finished, or stressed been for long ago",
    "other": "another African American English feature",
    "none": "no dialect feature at the marked place",
}


def system_alone(corpus: str, whose: str) -> str:
    return (f"You read {whose} of {RECORDING[corpus]}. You have no other transcript and no audio. "
            "The place to look at is marked with <mark> and </mark>; <mark>(nothing)</mark> means the "
            "text has no words there. Answer in JSON.")


def repair_message(case: Case) -> str:
    _, _, elo, ehi = case.window()
    return "\n".join([
        f"The engine's transcript, about a minute (it writes no speaker names):\n{tagged(case.engine_block(elo, ehi))}", "",
        "Speech recognition makes mistakes: wrong words, words left out, and words that were never said. "
        "The marked place may have one, or may be right.",
        "Answer, in this order:",
        "- reason: one or two sentences on whether the marked words fit what is being said.",
        "- looks_wrong: do the marked words look like a mistake? yes, maybe or no.",
        "- guess: what the speaker most likely said at the marked place, as a careful editor would write it "
        "without the audio. Copy the marked words unchanged if they look right. Write (nothing) if the "
        "words there look like they were never said.",
        "- sure: 1 (a guess), 2 (fairly sure) or 3 (sure).",
    ])


REPAIR_SCHEMA = obj({"reason": STR, "looks_wrong": enum(THREE), "guess": STR,
                     "sure": {"type": "integer", "minimum": 1, "maximum": 3}})


def cause_message(case: Case) -> str:
    others = other_engines(case)
    return "\n".join([
        tagged(case.context("minute")), "", at_the_spot(case), *([others] if others else []), "",
        *([AAE_NOTE, ""] if case.row["corpus"] == "coraal" else []),
        "Answer, in this order:",
        "- reason: one or two sentences on how the engine most likely came to write what it did.",
        "- cause: the most likely one of",
        *[f"    {k}: {v}" for k, v in CAUSE.items()],
        "- settle: one of",
        *[f"    {k}: {v}" for k, v in SETTLE.items()],
    ])


CAUSE_SCHEMA = obj({"reason": STR, "cause": enum(list(CAUSE)), "settle": enum(list(SETTLE))})


def aae_message(case: Case) -> str:
    others = other_engines(case)
    return "\n".join([
        tagged(case.context("minute")), "", at_the_spot(case), *([others] if others else []), "",
        AAE_NOTE, "",
        "Answer, in this order:",
        "- reason: one or two sentences on any African American English grammar at the marked place, in "
        "either version.",
        "- feature: the main one, one of",
        *[f"    {k}: {v}" for k, v in AAE_FEATURES.items()],
        "- feature_side: which version has the African American English form? reference, engine, both or neither.",
        "- feature_lost: does the engine's version lose or change what that feature meant? yes, maybe or no.",
    ])


AAE_SCHEMA = obj({"reason": STR, "feature": enum(list(AAE_FEATURES)),
                  "feature_side": enum(["reference", "engine", "both", "neither"]), "feature_lost": enum(THREE)})


def qa_question_message(case: Case) -> str:
    rlo, rhi, _, _ = case.window()
    return "\n".join([
        f"The transcript, about a minute:\n{tagged(case.reference_block(rlo, rhi))}", "",
        "Write one short question that a reader of this passage could answer, and whose answer depends on "
        "the marked words: whether something is so, what happened, a number, who did what. Do not quote the "
        "marked words, and do not put the answer in the question. A yes/no question is best when it fits.",
        "Answer, in this order:",
        "- question: the question, or empty if the marked words carry nothing a question could ask about.",
        "- kind: yes/no, fact, or none (when the question is empty).",
        "- answer: the answer from this passage: yes or no for a yes/no question, a few words for a fact, "
        "empty for none.",
    ])


QA_QUESTION_SCHEMA = obj({"question": STR, "kind": enum(["yes/no", "fact", "none"]), "answer": STR})


def qa_answer_message(passage: str, question: dict) -> str:
    form = "yes, no, or not stated" if question["kind"] == "yes/no" else "a few words, or not stated"
    return "\n".join([
        f"The transcript, about a minute:\n{tagged(passage)}", "",
        f"Question: {question['question']}", "",
        "Answer from what this passage says, as it is written; do not guess at what the speaker might have "
        "meant instead. The marked place is where the answer should be.",
        "Answer, in this order:",
        "- reason: one sentence.",
        f"- answer: {form}.",
    ])


def qa_answer_schema(question: dict) -> dict:
    answer = enum(["yes", "no", "not stated"]) if question["kind"] == "yes/no" else STR
    return obj({"reason": STR, "answer": answer})


def requests_v6(case: Case, asks: list[str], sizes: list[str]) -> list[tuple]:
    """Prompt 0.6: every request as in 0.5, plus the five new ones."""
    row, corpus = case.row, case.row["corpus"]
    out = requests_v5(case, [a for a in asks if a not in NEW_V6], sizes)
    rlo, rhi, elo, ehi = case.window()
    if "repair" in asks:
        out.append(("repair", "minute", system_alone(corpus, "a speech recognition engine's transcript"),
                    repair_message(case), REPAIR_SCHEMA, {}))
    if "cause" in asks:
        out.append(("cause", "minute", system_v3(corpus), cause_message(case), CAUSE_SCHEMA, {}))
    if "aae" in asks and corpus == "coraal":
        out.append(("aae", "minute", system_v3(corpus), aae_message(case), AAE_SCHEMA, {}))
    if "qa_question" in asks:
        out.append(("qa_question", "minute", system_alone(corpus, "a transcript"), qa_question_message(case),
                    QA_QUESTION_SCHEMA, {}))
    question = QUESTIONS.get(row["case"])
    if "qa_answer" in asks and question and question["kind"] != "none" and question["question"].strip():
        # The same question, answered once from each version, neither told which it is.
        for variant, passage in [("engine", case.engine_block(elo, ehi)), ("reference", case.reference_block(rlo, rhi))]:
            out.append(("qa_answer", variant, system_alone(corpus, "a transcript"), qa_answer_message(passage, question),
                        qa_answer_schema(question), {"question": question["question"]}))
    return out


PROMPT_SETS["0.6"] = {**PROMPT_SETS["0.5"], **{a: "0.6" for a in NEW_V6}}


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def post(path: str, body: dict, timeout: int = 900) -> dict:
    request = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_claude(model: str) -> bool:
    return model.startswith("claude-")


_key: list[str] = []


def api_key() -> str:
    if not _key:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key and KEY_FILE.exists():
            key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
        if not key:
            raise SystemExit(f"No Claude API key: set ANTHROPIC_API_KEY or put it in {KEY_FILE}")
        _key.append(key)
    return _key[0]


def claude_schema(schema):
    """The same schema as Claude's structured output takes it: no minimum, maximum
    or maxItems, and no extra keys on objects. check() still holds answers to the bounds."""
    if isinstance(schema, list):
        return [claude_schema(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: (claude_schema(v) if k != "properties" else {p: claude_schema(s) for p, s in v.items()})
           for k, v in schema.items() if k not in ("minimum", "maximum", "maxItems")}
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def claude_call(url: str, body: dict | None = None) -> str:
    """GET, or POST a body, to the Claude API. The key goes in the header only."""
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                     headers={"x-api-key": api_key(), "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            # Rate limit, overloaded or a server hiccup: wait and ask again.
            if error.code in (429, 500, 502, 503, 529) and attempt < 4:
                time.sleep(int(error.headers.get("retry-after") or 15 * (attempt + 1)))
                continue
            raise
    raise RuntimeError("unreachable")


def claude_body(model: str, system: str, user: str, schema: dict, think: bool) -> dict:
    return {"model": model, "max_tokens": THINK_PREDICT["*"], "system": system,
            "messages": [{"role": "user", "content": user}],
            "thinking": {"type": "adaptive"} if think else {"type": "disabled"},
            "output_config": {"format": {"type": "json_schema", "schema": claude_schema(schema)},
                              **({"effort": CLAUDE_EFFORT} if think else {})}}


def read_claude(reply: dict, think: bool, seconds: float) -> tuple[dict | None, dict]:
    """The answer and its bookkeeping from one Claude reply (asked directly or in a batch)."""
    usage, blocks = reply.get("usage", {}), reply.get("content", [])
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    meta = {"tokens_in": usage.get("input_tokens", 0), "tokens_out": usage.get("output_tokens", 0),
            "seconds": seconds,
            "done": {"max_tokens": "length", "end_turn": "stop"}.get(reply.get("stop_reason"), reply.get("stop_reason", "")),
            "think_level": CLAUDE_EFFORT if think else "off", "num_predict": THINK_PREDICT["*"],
            "thinking_tokens": (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0),
            "thinking": "".join(b.get("thinking", "") for b in blocks if b.get("type") == "thinking")}
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        return None, {**meta, "raw": text[:500]}
    return (answer if isinstance(answer, dict) else None), meta


def ask_claude(model: str, system: str, user: str, schema: dict, think: bool) -> tuple[dict | None, dict]:
    started = time.time()
    reply = json.loads(claude_call(CLAUDE_API, claude_body(model, system, user, schema, think)))
    return read_claude(reply, think, round(time.time() - started, 2))


def loaded_models() -> dict:
    """{name: context window} for each model Ollama has loaded."""
    with urllib.request.urlopen(OLLAMA + "/api/ps", timeout=30) as response:
        return {m["name"]: m.get("context_length") for m in json.loads(response.read().decode("utf-8")).get("models", [])}


def ask(model: str, system: str, user: str, schema: dict, num_ctx: int, think: bool) -> tuple[dict | None, dict]:
    options = {**OPTIONS, "num_ctx": num_ctx}
    if think:
        options["num_predict"] = per_model(THINK_PREDICT, model)
        think = per_model(THINK_LEVEL, model)
    body = {"model": model, "stream": False, "think": think, "format": schema, "keep_alive": "10m",
            "options": options,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    started = time.time()
    try:
        if is_claude(model):
            return ask_claude(model, system, user, schema, think)
        reply = post("/api/chat", body, timeout=3600)
    except urllib.error.HTTPError as error:
        # 24 Oct 2026: Ollama gave a 500 after 7,800 tokens of one cold read and
        # took the rest of the run with it. Saved as invalid; --redo-invalid asks again.
        return None, {"tokens_in": 0, "tokens_out": 0, "seconds": round(time.time() - started, 2),
                      "done": "error", "raw": f"HTTP {error.code}: {error.read()[:300]!r}"}
    ns = 1e9
    meta = {"tokens_in": reply.get("prompt_eval_count", 0), "tokens_out": reply.get("eval_count", 0),
            "seconds": round(time.time() - started, 2), "done": reply.get("done_reason", ""),
            "think_level": str(think), "num_predict": options["num_predict"],
            # Ollama's own timings, for speed per model: loading, reading the
            # prompt, writing the reply (thinking included).
            "load_s": round(reply.get("load_duration", 0) / ns, 2),
            "read_s": round(reply.get("prompt_eval_duration", 0) / ns, 2),
            "write_s": round(reply.get("eval_duration", 0) / ns, 2),
            "thinking": reply.get("message", {}).get("thinking", "") or ""}
    try:
        answer = json.loads(reply["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return None, {**meta, "raw": reply.get("message", {}).get("content", "")[:500]}
    return (answer if isinstance(answer, dict) else None), meta


def card() -> dict:
    """Memory in use and temperature, from nvidia-smi (llm_format.py's reading)."""
    import llm_format
    try:
        reading = llm_format.card_reading()
    except Exception:
        # nvidia-smi can fail to start for a moment (23 Oct 2026: it took a whole
        # run down); a missing reading is not worth losing the run for.
        return {}
    return {"memory_mib": reading["memory_used_mib"], "spill_mib": reading["spill_mib"],
            "temperature_c": reading["temperature_c"]}


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def tag(model: str) -> str:
    return re.sub(r"[^\w.-]+", "-", model).strip("-")


FIELDS = ["case", "ask", "variant", "model", "prompt", "think", "num_ctx", "answer", "valid",
          "tokens_in", "tokens_out", "seconds", "memory_mib", "spill_mib", "temperature_c"]


def check(ask_name: str, answer: dict | None, schema: dict) -> bool:
    """Whether an answer has every field and only allowed values."""
    if not answer:
        return False
    for key, rule in schema["properties"].items():
        if key not in answer:
            return False
        value = answer[key]
        if "enum" in rule and value not in rule["enum"]:
            return False
        if rule.get("type") == "integer" and not (isinstance(value, int) and rule["minimum"] <= value <= rule["maximum"]):
            return False
        if rule.get("type") == "object" and not check(ask_name, value, rule):
            return False
        if rule.get("type") == "array" and len(value) > rule.get("maxItems", len(value)):
            return False
    return True


def requests_for(case: Case, asks: list[str], sizes: list[str]) -> list[tuple]:
    """(ask, variant, system, user, schema, extra) for one case."""
    row, corpus = case.row, case.row["corpus"]
    out = []
    if "labelled" in asks:
        for size in sizes:
            out.append(("labelled", size, system_labelled(corpus), labelled_message(case, size),
                        labelled_schema(case), {}))
    if "rule" in asks:
        out.append(("rule", "minute", system_labelled(corpus), rule_message(case), RULE_SCHEMA, {}))
    if "blind" in asks:
        ref, eng = case.blind_versions()
        # Which side is the reference is decided per case, then swapped.
        first_ref = random.Random(row["case"]).random() < 0.5
        for order, ref_first in [("order1", first_ref), ("order2", not first_ref)]:
            a, b = (ref, eng) if ref_first else (eng, ref)
            out.append(("blind", order, system_blind(corpus), blind_message(a, b), BLIND_SCHEMA,
                        {"reference_is": "A" if ref_first else "B"}))
    if "rank" in asks and row["engine"] != "Control":
        versions = list(case.engine_versions().items())
        random.Random(row["case"]).shuffle(versions)
        shown = [(f"Engine {i + 1}", text) for i, (_, text) in enumerate(versions)]
        key = {f"Engine {i + 1}": name for i, (name, _) in enumerate(versions)}
        out.append(("rank", "minute", system_rank(corpus), rank_message(case, shown),
                    rank_schema([label for label, _ in shown]), {"engines": key}))
    if "misses" in asks:
        out.append(("misses", "minute", system_misses(corpus), misses_message(case), MISSES_SCHEMA, {}))
    return out


def save_answer(writer, f, log, keys: dict, answer: dict | None, meta: dict, schema: dict,
                extra: dict, reading: dict) -> bool:
    """One answer to the CSV and its timings (and thinking) to the request log. Returns valid."""
    valid = check(keys["ask"], answer, schema) and meta["done"] != "length"
    log.write(json.dumps({**keys, "valid": valid, **{k: v for k, v in meta.items() if k != "raw"},
                          **reading}, ensure_ascii=False) + "\n")
    log.flush()
    record = {**(answer or {"raw": meta.get("raw", "")}), **extra}
    writer.writerow({**keys, "answer": json.dumps(record, ensure_ascii=False), "valid": valid,
                     **{k: meta[k] for k in ("tokens_in", "tokens_out", "seconds")}, **reading})
    f.flush()
    return valid


# ---------------------------------------------------------------------------
# Claude's Batch API: half the price, answers within 24 hours (usually much less).
# The batch ids and what each request was are kept in batch-<model>.json as soon
# as they are sent, so a stopped script collects them on the next run instead of
# paying for them twice.
# ---------------------------------------------------------------------------

CLAUDE_BATCHES = CLAUDE_API + "/batches"
BATCH_MAX_REQUESTS = 10_000
BATCH_MAX_BYTES = 100_000_000   # the API takes up to 256 MB; kept well under
BATCH_CHECK_SECONDS = 60


def stem(model: str) -> str:
    return tag(model) + SUFFIX


def batch_file(model: str) -> Path:
    return OUT / f"batch-{stem(model)}.json"


def run_batch(args, jobs: list, prompt_of: dict, think: str, out_file: Path) -> int:
    if not is_claude(args.model):
        raise SystemExit("--batch is for Claude models only (Ollama has no batches)")
    path = batch_file(args.model)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if state and not state["collected"]:
        print(f"A batch sent {state['sent']} hasn't been collected: collecting it, sending nothing new.", flush=True)
    else:
        if not jobs:
            print("Nothing to send: every request already has an answer.")
            return 0
        state = {"model": args.model, "think": think, "sent": time.strftime("%Y-%m-%d %H:%M"),
                 "collected": False, "batches": [], "requests": {}}
        part, size = [], 0
        for n, (case_id, (ask_name, variant, system, user, schema, extra)) in enumerate(jobs):
            custom_id = f"r{n:06d}"
            request = {"custom_id": custom_id, "params": claude_body(args.model, system, user, schema, args.think)}
            state["requests"][custom_id] = {"case": case_id, "ask": ask_name, "variant": variant,
                                            "prompt": prompt_of[ask_name], "schema": schema, "extra": extra}
            part.append(request)
            size += len(json.dumps(request))
            if len(part) == BATCH_MAX_REQUESTS or size > BATCH_MAX_BYTES or n == len(jobs) - 1:
                reply = json.loads(claude_call(CLAUDE_BATCHES, {"requests": part}))
                state["batches"].append({"id": reply["id"], "requests": len(part), "collected": False})
                path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                print(f"Sent batch {reply['id']}: {len(part)} requests", flush=True)
                part, size = [], 0

    with out_file.open("a", encoding="utf-8", newline="") as f, \
            (OUT / f"requests-{stem(args.model)}.jsonl").open("a", encoding="utf-8") as log:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if f.tell() == 0:
            writer.writeheader()
        for batch in state["batches"]:
            if batch["collected"]:
                continue
            while True:
                status = json.loads(claude_call(f"{CLAUDE_BATCHES}/{batch['id']}"))
                counts = status["request_counts"]
                print(f"  {time.strftime('%H:%M')} {batch['id']}: {status['processing_status']}, "
                      + ", ".join(f"{k} {v}" for k, v in counts.items() if v), flush=True)
                if status["processing_status"] == "ended":
                    break
                time.sleep(BATCH_CHECK_SECONDS)
            invalid = 0
            for line in claude_call(status["results_url"]).splitlines():
                if not line.strip():
                    continue
                result = json.loads(line)
                job = state["requests"][result["custom_id"]]
                if result["result"]["type"] == "succeeded":
                    answer, meta = read_claude(result["result"]["message"], args.think, 0)
                else:
                    # errored, canceled or expired: saved as invalid; --redo-invalid asks again.
                    answer, meta = None, {"tokens_in": 0, "tokens_out": 0, "seconds": 0, "done": "error",
                                          "raw": json.dumps(result["result"])[:300]}
                keys = {"case": job["case"], "ask": job["ask"], "variant": job["variant"], "model": args.model,
                        "prompt": job["prompt"], "think": state["think"], "num_ctx": 0}
                valid = save_answer(writer, f, log, keys, answer, {**meta, "batch": batch["id"]},
                                    job["schema"], job["extra"], {})
                invalid += not valid
            batch["collected"] = True
            path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            print(f"Collected {batch['id']}: {batch['requests']} answers, {invalid} invalid", flush=True)
    state["collected"] = True
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return 0


def run(args) -> int:
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    if "not_counted" in sample:   # a case gone after a repair is not there to read
        sample = sample[~sample.not_counted.str.startswith("gone")]
    if args.source:
        sample = sample[sample.source.isin(args.source.split(","))]
    if args.subkind:
        sample = sample[sample.subkind.isin(args.subkind.split(","))]
    if args.cases:
        sample = sample[sample.case.isin(args.cases.split(","))]
    if args.subset:
        sample = sample[sample.case.isin(pd.read_csv(OUT / f"{args.subset}.csv", dtype=str).case)]
    default = {"0.2": ASKS, "0.5": ASKS_V5, "0.6": [a for a in ASKS_V6 if a != "qa_answer"]}.get(args.prompt, ASKS_V3)
    asks = (args.ask or ",".join(default)).split(",")
    prompt_of = PROMPT_SETS[args.prompt]
    build = {"0.2": requests_for, "0.3": requests_v3, "0.4": requests_v4, "0.5": requests_v5,
             "0.6": requests_v6}[args.prompt]
    sizes = args.sizes.split(",")
    sample = sample.sort_values(["corpus", "part", "recording", "case"])

    cache: dict = {}
    if args.dry_run:
        for row in sample.to_dict("records"):
            case = Case(row, cache)
            print(f"===== {row['case']} {row['corpus']} {row['recording']} {row['engine']} "
                  f"{row['kind']}/{row['subkind']}  located: reference {case.ref_match}, engine {case.eng_match}")
            for ask_name, variant, system, user, _, extra in build(case, asks, sizes):
                shown = user if variant != "whole" else user[:600] + "\n[... whole reference ...]\n" + user[-2500:]
                print(f"--- {ask_name} / {variant} {extra}\nSYSTEM: {system}\nUSER:\n{shown}\n")
        return 0

    local = not is_claude(args.model)
    loaded = loaded_models() if local else {}
    others = [m for m in loaded if m != args.model]
    if others:
        raise SystemExit(f"STOP: Ollama already has {', '.join(others)} loaded. Run 'ollama stop <name>' first.")
    # The same model loaded at another window size means another program is
    # using it (23 Oct 2026: a proofreading job at 32k). Taking turns would
    # reload the model on every request and slow both to a crawl.
    budget = per_model(THINK_PREDICT, args.model) if args.think else 2000
    short_ctx = window(LONGEST_SHORT_PROMPT + budget) if args.think else SHORT_CTX
    if loaded.get(args.model) not in (None, short_ctx):
        raise SystemExit(f"STOP: {args.model} is loaded with a {loaded[args.model]}-token window, so another "
                         "program is probably using it. Wait for it to finish, or 'ollama stop' it.")

    OUT.mkdir(parents=True, exist_ok=True)
    out_file = OUT / f"answers-{stem(args.model)}.csv"
    done = set()
    if out_file.exists():
        done = {(r["case"], r["ask"], r["variant"], r["prompt"], r["think"])
                for r in csv.DictReader(out_file.open(encoding="utf-8"))
                if not (args.redo_invalid and r["valid"] != "True")}
    if "qa_answer" in asks and out_file.exists():
        for r in csv.DictReader(out_file.open(encoding="utf-8")):
            if r["ask"] == "qa_question" and r["valid"] == "True":
                QUESTIONS[r["case"]] = json.loads(r["answer"])
    think = "yes" if args.think else "no"
    if args.max_new:
        # One part of a big run: the first N cases by id (a random order in a full
        # sample) with no answer yet. The same command without it sends the rest.
        answered = {d[0] for d in done if d[1] in asks and d[4] == think}
        todo = sorted(c for c in sample.case if c not in answered)[:args.max_new]
        sample = sample[sample.case.isin(todo)]

    # Short requests first at one window size, then the whole-transcript ones at
    # another: a change of size reloads the model.
    jobs_short, jobs_whole = [], []
    for row in sample.to_dict("records"):
        case = Case(row, cache)
        for request in build(case, asks, sizes):
            if (row["case"], request[0], request[1], prompt_of[request[0]], think) in done:
                continue
            (jobs_whole if request[1] == "whole" else jobs_short).append((row["case"], request))
    whole_ctx = short_ctx
    if jobs_whole:
        longest = max(len(r[3]) + len(r[2]) for _, r in jobs_whole)
        # About 3.5 characters a token in this text, room for the answer, in steps of 8k.
        whole_ctx = window(int(longest / 3.5) + budget)
    print(f"{args.model}, thinking {per_model(THINK_LEVEL, args.model) if args.think else 'off'} "
          f"(up to {budget} tokens out):{len(jobs_short)} short requests (num_ctx {short_ctx}), "
          f"{len(jobs_whole)} whole (num_ctx {whole_ctx}); {len(done)} already answered", flush=True)
    if is_claude(args.model) and args.model in TOKENS_OUT:
        jobs = len(jobs_short) + len(jobs_whole)
        price_in, price_out = BATCH_PRICES[args.model] if args.batch else [2 * x for x in BATCH_PRICES[args.model]]
        cost = jobs * (TOKENS_IN * price_in + TOKENS_OUT[args.model] * price_out) / 1e6
        print(f"Estimated cost: about ${cost:.2f} for {jobs} requests"
              f"{' at batch prices' if args.batch else ''} (from the averages on sample-v3)", flush=True)
    if args.estimate_only:
        return 0
    if args.batch:
        return run_batch(args, jobs_short + jobs_whole, prompt_of, think, out_file)
    if is_claude(args.model) and batch_file(args.model).exists() and \
            not json.loads(batch_file(args.model).read_text(encoding="utf-8"))["collected"]:
        raise SystemExit(f"STOP: a batch for {args.model} hasn't been collected yet. "
                         "Run the same command with --batch to collect it first.")
    # Every request's timings and its thinking, beside the answers (the CSV's
    # columns are kept as they were, so older files still read).
    log = (OUT / f"requests-{stem(args.model)}.jsonl").open("a", encoding="utf-8")
    started_all = time.time()
    errors_in_a_row = 0

    with out_file.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if f.tell() == 0:
            writer.writeheader()
        try:
            for n, (case_id, (ask_name, variant, system, user, schema, extra)) in enumerate(
                    jobs_short + jobs_whole, 1):
                num_ctx = whole_ctx if variant == "whole" else short_ctx
                answer, meta = ask(args.model, system, user, schema, num_ctx, args.think)
                # Each reading starts PowerShell (for the spill figure), a second or
                # two, so every 10th request and every whole-transcript one.
                reading = card() if local and (variant == "whole" or n % 10 == 1) else {}
                valid = save_answer(writer, f, log, {"case": case_id, "ask": ask_name, "variant": variant,
                                                     "model": args.model, "prompt": prompt_of[ask_name],
                                                     "think": think, "num_ctx": num_ctx},
                                    answer, meta, schema, extra, reading)
                print(f"  [{n}/{len(jobs_short) + len(jobs_whole)}] {case_id} {ask_name}/{variant} "
                      f"{meta['seconds']:.1f}s in {meta['tokens_in']} out {meta['tokens_out']}"
                      f"{'' if valid else '  INVALID'}{'  CUT OFF' if meta['done'] == 'length' else ''}"
                      f"{'  SERVER ERROR' if meta['done'] == 'error' else ''} "
                      f"{reading.get('memory_mib', '')} MiB, {(time.time() - started_all) / 60:.0f} min so far",
                      flush=True)
                errors_in_a_row = errors_in_a_row + 1 if meta["done"] == "error" else 0
                if errors_in_a_row >= 3:
                    print(f"  STOP: three server errors in a row ({meta['raw']})", flush=True)
                    break
                if reading.get("temperature_c", 0) >= 87:
                    print("  card at 87 C or more: two minutes to cool", flush=True)
                    time.sleep(120)
        finally:
            log.close()
            print(f"{args.model}: {(time.time() - started_all) / 60:.1f} min in all", flush=True)
            # Give the card back, unless someone else had the model loaded already.
            if local and args.model not in loaded:
                post("/api/generate", {"model": args.model, "keep_alive": 0})
    return 0


# ---------------------------------------------------------------------------

def diff_words(a: str, b: str) -> set[str]:
    """Words on one side only; all the words if the two sides hold the same ones."""
    x, y = set(tokens(a)), set(tokens(b))
    return (x ^ y) or (x | y)


def misses_table(sample: pd.DataFrame, answers: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Match each difference the judge listed in a minute against the rules' cases there.

    A judge item and a rule case match when they are in the same recording, engine
    and minute and the words that differ overlap. Rough on purpose: the items it
    can't match are printed, to be read one by one.
    """
    found = pd.concat([pd.read_csv(FAILURES / k / "candidates.csv", dtype=str, keep_default_na=False,
                                   usecols=SHARED) for k in KINDS])
    found["start"] = found.start.astype(float)
    rows, unmatched = [], []
    for _, a in answers[answers.ask == "misses"].iterrows():
        case = sample.loc[a.case]
        if case.engine == "Control":
            continue
        t0, t1 = float(case.start) - WINDOW, float(case.end) + WINDOW
        near = found[(found.recording == case.recording) & (found.engine == case.engine)
                     & (found.start >= t0) & (found.start <= t1)]
        near_words = [diff_words(r.record, r.engine_wrote) for r in near.itertuples()]
        items = a.answer.get("differences", [])
        hit = set()
        for item in items:
            words = diff_words(item["reference"], item["engine"])
            match = [i for i, w in enumerate(near_words) if w & words]
            hit.update(match)
            if not match:
                unmatched.append(f"{a.case} {case.corpus} {case.engine}: \"{item['reference']}\" -> "
                                 f"\"{item['engine']}\" (severity {item['severity']}; {item['what']})")
        rows.append({"case": a.case, "judge_items": len(items),
                     "matched": len(items) - sum(1 for u in unmatched if u.startswith(a.case + " ")),
                     "rule_cases": len(near), "rule_cases_mentioned": len(hit),
                     "case_itself_mentioned": any(diff_words(case.record, case.engine_wrote)
                                                  & diff_words(i["reference"], i["engine"]) for i in items)})
    return pd.DataFrame(rows), unmatched


def summary(model: str) -> int:
    """The tables for findings/judge/README.md, from the latest prompt of each request."""
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False).set_index("case", drop=False)
    answers = pd.read_csv(OUT / f"answers-{tag(model)}.csv", dtype=str, keep_default_na=False)
    answers = answers[answers.prompt == answers.ask.map(PROMPT)]
    answers = answers.drop_duplicates(["case", "ask", "variant"], keep="last").copy()
    answers["answer"] = answers.answer.map(json.loads)
    for col in ("seconds", "tokens_in"):
        answers[col] = pd.to_numeric(answers[col])
    answers = answers.join(sample[["kind", "subkind", "source", "expect", "engine", "interest"]], on="case")
    print(f"{model}: {answers.case.nunique()} cases, {len(answers)} answers, "
          f"{(answers.valid != 'True').sum()} invalid\n")

    labelled = answers[answers.ask == "labelled"].copy()
    for field in ("meaning", "severity", "noticeable", "follow_up", "stakes"):
        labelled[field] = labelled.answer.map(lambda a, f=field: a.get(f))
    wide = labelled.pivot(index="case", columns="variant", values="meaning")
    sev = labelled.pivot(index="case", columns="variant", values="severity")

    print("== Controls (expected answer)")
    for case in sample[sample.source == "control"].case:
        expect = sample.loc[case, "expect"]
        got = wide.loc[case].tolist() if case in wide.index else []
        print(f"  {case} expect {expect}: labelled {got}")
    print()

    real = labelled[labelled.source != "control"]
    print("== Meaning verdict by context size (36 cases)")
    print(pd.crosstab(real.meaning, real.variant).to_string(), "\n")
    sizes = [s for s in ("line", "minute", "whole") if s in wide]
    w = wide.loc[[c for c in wide.index if sample.loc[c, "source"] != "control"], sizes]
    print(f"Same verdict at all three sizes: {(w.nunique(axis=1) == 1).sum()} of {len(w)}")
    for a, b in [("line", "minute"), ("minute", "whole"), ("line", "whole")]:
        print(f"  {a} vs {b}: verdict differs in {(w[a] != w[b]).sum()}; "
              f"severity differs in {(sev.loc[w.index, a] != sev.loc[w.index, b]).sum()}")
    print()

    minute = real[real.variant == "minute"]
    print("== At the minute: verdict by kind")
    print(pd.crosstab([minute.kind, minute.subkind], minute.meaning).to_string(), "\n")
    print("Severity (minute) by kind:", minute.groupby("kind").severity.mean().round(1).to_dict())
    print("Fluent but wrong (not noticeable, severity 2+):",
          ", ".join(minute[(minute.noticeable == "no") & (minute.severity >= 2)].case))
    print("Could mislead (stakes yes):", (minute.stakes == "yes").sum(), "of", len(minute))
    print("Follow-up answers:\n", pd.crosstab(minute.kind, minute.follow_up).to_string(), "\n")
    scored = minute[minute.interest != ""]
    print("Shortlist interest (Claude's, earlier) against judge severity (minute), model against model:")
    print(pd.crosstab(scored.interest, scored.severity).to_string(), "\n")

    rule = answers[(answers.ask == "rule") & (answers.source != "control")].copy()
    rule["rule_right"] = rule.answer.map(lambda a: a.get("rule_right"))
    print("== Was the rule right? (from the text, minute)")
    print(pd.crosstab([rule.kind, rule.subkind], rule.rule_right).to_string(), "\n")

    blind = answers[(answers.ask == "blind") & (answers.source != "control")].copy()
    blind["got"] = blind.answer.map(lambda a: "cant tell" if a["pick"] == "cant tell"
                                    else "reference" if a["pick"] == a["reference_is"] else "engine")
    blind["first"] = blind.answer.map(lambda a: a["pick"] == "A")
    both = blind.pivot(index="case", columns="variant", values="got")
    both["kind"] = sample.loc[both.index, "kind"]
    print("== Blind: which was said? (both orders)")
    print(pd.crosstab(both.kind, both.order1 + " / " + both.order2).to_string())
    picked = blind[blind.got != "cant tell"]
    print(f"Picked version A in {picked['first'].sum()} of {len(picked)} picks (half would be no order bias)\n")

    rank = answers[answers.ask == "rank"].copy()
    rows = []
    for _, r in rank.iterrows():
        engines, ranks = r.answer["engines"], r.answer["ranks"]
        mine = next(label for label, name in engines.items() if name == r.engine)
        rows.append({"case": r.case, "kind": r.kind, "failing_rank": ranks[mine],
                     "worst": ranks[mine] == max(ranks.values()),
                     "alone_worst": list(ranks.values()).count(max(ranks.values())) == 1 and ranks[mine] == max(ranks.values())})
    rank_t = pd.DataFrame(rows)
    print("== Rank: is the engine the rules caught ranked last?")
    print(rank_t.groupby("kind")[["worst", "alone_worst"]].sum().assign(cases=rank_t.groupby("kind").size()).to_string(), "\n")

    table, unmatched = misses_table(sample, answers)
    print("== Misses: the judge's list for the minute, against the rules' cases there")
    print(table[["judge_items", "matched", "rule_cases", "rule_cases_mentioned"]].sum().to_string())
    print(f"The case itself in the judge's list: {table.case_itself_mentioned.sum()} of {len(table)}")
    print("Judge items no rule case matched:")
    for line in unmatched:
        print("  " + line)
    print()

    print("== Speed")
    print(answers.groupby(["ask", "variant"])[["seconds", "tokens_in"]].median().round(1).to_string())
    memory = pd.to_numeric(pd.read_csv(OUT / f"answers-{tag(model)}.csv").memory_mib, errors="coerce")
    print(f"Peak memory read: {memory.max():.0f} MiB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--make-sample", action="store_true", help="write sample-v1.csv (once; it is kept fixed)")
    parser.add_argument("--dry-run", nargs="?", const="", metavar="CASES",
                        help="print the prompts instead of asking (optionally for these cases, comma-separated)")
    parser.add_argument("--cases", help="only these cases, comma-separated (s01,s02)")
    parser.add_argument("--source", help="only cases from: shortlist, random, control (comma-separated)")
    parser.add_argument("--subkind", help="only cases the finders gave this subkind: negation, aint, number, ... (comma-separated)")
    parser.add_argument("--ask", help="which kinds of request (default all of the prompt set's)")
    parser.add_argument("--prompt", default="0.2", choices=list(PROMPT_SETS),
                        help="which prompt set: 0.2, or 0.3 (research-informed; see prompting-research.md)")
    parser.add_argument("--sizes", default="line,minute,whole", help="context sizes for the labelled request")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--think", action="store_true", help="let the model think first (slower)")
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                        help="Claude with --think only: the effort level (default medium). Any other level "
                             "gets its own answers file, e.g. answers-claude-sonnet-5-5-high-sample-v3.csv")
    parser.add_argument("--batch", action="store_true",
                        help="Claude only: send everything as one batch at half price and wait for it "
                             "(answers within 24 hours); run again to collect if stopped while waiting")
    parser.add_argument("--redo-invalid", action="store_true",
                        help="ask again where the saved answer is invalid or was cut off (the newer answer counts)")
    parser.add_argument("--summary", action="store_true", help="print the tables for the README")
    parser.add_argument("--sample", default="sample-v1",
                        help="which sample in findings/judge/ (default sample-v1, the fixed 40); any other "
                             "gets its own answers-<model>-<sample>.csv")
    parser.add_argument("--make-random-sample", type=int, metavar="N",
                        help="write --sample (not sample-v1) as N rows drawn at random, each kind in proportion")
    parser.add_argument("--seed", type=int, default=2027, help="seed for --make-random-sample and --add-agree")
    parser.add_argument("--add-agree", type=int, metavar="N",
                        help="write --sample as --base plus N spots where every engine agrees against the reference")
    parser.add_argument("--base", default="sample-v2", help="the sample --add-agree starts from")
    parser.add_argument("--make-full-sample", action="store_true",
                        help="write --sample as every row of the four searches plus the all-agree spots, shuffled")
    parser.add_argument("--estimate-only", action="store_true",
                        help="count the requests and print the estimated cost, then stop without sending")
    parser.add_argument("--max-new", type=int, metavar="N",
                        help="send only the first N cases (by case id) with no answer yet: a big run in parts")
    parser.add_argument("--add-random", type=int, metavar="N",
                        help="add N more random rows to --sample (never one already in it or in sample-v1)")
    parser.add_argument("--make-combo", metavar="NAME",
                        help="write NAME.csv: 75 cases per data set from --sample, for testing prompt combinations")
    parser.add_argument("--subset", metavar="NAME",
                        help="only the cases listed in NAME.csv (from --make-combo); answers go to --sample's files")
    args = parser.parse_args()

    global SAMPLE, SUFFIX, CLAUDE_EFFORT
    if args.sample != "sample-v1":
        SAMPLE = OUT / f"{args.sample}.csv"
        SUFFIX = f"-{args.sample}"
    if args.effort != "medium":
        # Medium is what every earlier file used, so only the others say so in the name.
        CLAUDE_EFFORT = args.effort
        SUFFIX = f"-{args.effort}{SUFFIX}"
    if args.make_random_sample:
        if args.sample == "sample-v1" or SAMPLE.exists():
            raise SystemExit(f"Give a new --sample name; {SAMPLE.name} is kept fixed once drawn.")
        sample = make_random_sample(args.make_random_sample, args.seed)
        sample.to_csv(SAMPLE, index=False)
        print(sample.groupby(["kind", "corpus"]).size().unstack(fill_value=0).to_string())
        return 0
    if args.make_full_sample:
        if args.sample == "sample-v1" or SAMPLE.exists():
            raise SystemExit(f"Give a new --sample name; {SAMPLE.name} is kept fixed once drawn.")
        sample = make_full_sample(args.seed)
        sample.to_csv(SAMPLE, index=False)
        print(sample.groupby(["source", "corpus"]).size().unstack(fill_value=0).to_string())
        return 0
    if args.add_agree:
        if args.sample == "sample-v1" or SAMPLE.exists():
            raise SystemExit(f"Give a new --sample name; {SAMPLE.name} is kept fixed once drawn.")
        sample = add_agree_sample(args.base, args.add_agree, args.seed)
        sample.to_csv(SAMPLE, index=False)
        print(sample.groupby(["source", "corpus"]).size().unstack(fill_value=0).to_string())
        return 0
    if args.make_combo:
        if (OUT / f"{args.make_combo}.csv").exists():
            raise SystemExit(f"{args.make_combo}.csv exists; it is kept fixed once drawn.")
        combo = make_combo_sample(pd.read_csv(SAMPLE, dtype=str, keep_default_na=False))
        combo.to_csv(OUT / f"{args.make_combo}.csv", index=False)
        print(pd.crosstab(combo.group, combo.corpus, margins=True).to_string())
        return 0
    if args.add_random:
        # Growing a sample keeps every row already in it, so answers given so far still count.
        sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
        numbers = sample.case[sample.case.str.startswith("r")].str[1:].astype(int)
        more = make_random_sample(args.add_random, args.seed, sample, int(numbers.max()) + 1)
        sample = pd.concat([sample, more], ignore_index=True)
        sample.to_csv(SAMPLE, index=False)
        print(more.groupby(["kind", "corpus"]).size().unstack(fill_value=0).to_string())
        return 0

    if args.make_sample:
        if SAMPLE.exists():
            raise SystemExit(f"{SAMPLE} exists; the sample is kept fixed so models can be compared. "
                             "Delete it by hand to draw a new one.")
        sample = make_sample()
        OUT.mkdir(parents=True, exist_ok=True)
        sample.to_csv(SAMPLE, index=False)
        print(sample.groupby(["source", "kind"]).size().to_string())
        return 0
    if args.summary:
        return summary(args.model)
    if args.dry_run is not None:
        if args.dry_run:
            args.cases = args.dry_run
        args.dry_run = True
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

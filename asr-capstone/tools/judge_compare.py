"""Compare the local judge models on the fixed sample: how good, how fast.

Every answers-<model>.csv in findings/judge/ is read, split by thinking on/off,
and scored against what is known:

- the four controls (s37, s38 same; s39, s40 opposite; the rule wrong on s37, s38);
- Claude's own answers in claude-review/, written from the text before Claude saw
  any model's answers. Claude isn't ground truth either; it is one careful reading;
- whether a blind pick survives swapping the order of the two versions.

Speed comes from the answers' own seconds and, for runs since 23 Oct 2026, the
requests-<model>.jsonl beside them (Ollama's own timings, the thinking, memory).

    python tools/judge_compare.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_failures as J  # noqa: E402

CONTROLS = {"s37": "same", "s38": "same", "s39": "opposite", "s40": "opposite"}
#: Cases where Claude's review thought the reference, not the engine, may be wrong.
SUSPECT_REFERENCE = ["s05", "s21", "s30", "s34"]


def spot_found(row: pd.Series, places: list[dict]) -> bool:
    """Whether a cold-read answer points at the case's spot: one of its quotes
    shares a word with what the engine wrote there, or, where the engine wrote
    nothing, with the engine's words right beside the gap."""
    before, after = J.split_context(row["engine_context"])
    spot = set(J.tokens(row["engine_wrote"])) or set(before[-2:] + after[:2])
    return any(spot & set(J.tokens(p.get("words", ""))) for p in places)


def claude_answers() -> pd.DataFrame:
    rows = []
    for path in sorted((J.OUT / "claude-review").glob("s*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"case": d["case"], **{f"c_{k}": d["own"].get(k) for k in ("meaning", "severity", "noticeable", "stakes")}})
    return pd.DataFrame(rows).set_index("case")


def load() -> pd.DataFrame:
    frames = []
    for path in sorted(J.OUT.glob("answers-*.csv")):
        if "-sample-" in path.stem:   # the bigger samples are scored by judge_sample_v2.py
            continue
        a = pd.read_csv(path, dtype=str, keep_default_na=False)
        frames.append(a)
    a = pd.concat(frames)
    # Which prompt set a row belongs to. 0.2's blind, rank and misses kept their
    # 0.1 wording; 0.1's own labelled answers were replaced, so they drop out.
    v02 = a.prompt == a.ask.map(J.PROMPT_SETS["0.2"])
    a["prompt_set"] = v02.map({True: "0.2", False: ""})
    a.loc[a.prompt == "0.3", "prompt_set"] = "0.3"
    a = a[a.prompt_set != ""]
    a = a.drop_duplicates(["model", "think", "prompt_set", "case", "ask", "variant"], keep="last")
    a["answer"] = a.answer.map(json.loads)
    a["seconds"] = pd.to_numeric(a.seconds)
    a["tokens_out"] = pd.to_numeric(a.tokens_out)
    a["setup"] = a.model + a.think.map({"yes": " think"}).fillna("") + " p" + a.prompt_set
    return a


def score(a: pd.DataFrame, claude: pd.DataFrame) -> dict:
    out = {"answers": len(a), "invalid": int((a.valid != "True").sum())}
    every, a = a, a[a.valid == "True"]   # answers cut off or malformed say nothing
    lab = a[a.ask.isin(["labelled", "meaning"])].copy()
    lab["meaning"] = lab.answer.map(lambda x: x.get("meaning"))
    lab["severity"] = pd.to_numeric(lab.answer.map(lambda x: x.get("severity")), errors="coerce")
    lab["noticeable"] = lab.answer.map(lambda x: x.get("noticeable"))
    ctl = lab[lab.case.isin(list(CONTROLS))]
    out["controls right"] = f"{(ctl.meaning == ctl.case.map(CONTROLS)).sum()}/{len(ctl)}"
    rule = a[(a.ask == "rule") & a.case.isin(list(CONTROLS))]
    want = {"s37": "no", "s38": "no", "s39": "yes", "s40": "yes"}
    out["rule controls"] = f"{sum(r.answer.get('rule_right') == want[r.case] for r in rule.itertuples())}/{len(rule)}"

    real = lab[~lab.case.isin(list(CONTROLS))].join(claude, on="case")
    for size in ("line", "minute", "whole"):
        s = real[real.variant == size]
        if len(s):
            out[f"meaning = Claude ({size})"] = f"{(s.meaning == s.c_meaning).sum()}/{len(s)}"
    m = real[real.variant == "minute"]
    if len(m):
        gap = m.severity - pd.to_numeric(m.c_severity)
        out["severity minus Claude (minute)"] = round(gap.mean(), 2)
        out["severity off by 2+"] = int((gap.abs() >= 2).sum())
        if m.noticeable.notna().any():
            out["noticeable = Claude"] = f"{(m.noticeable == m.c_noticeable).sum()}/{len(m)}"
    sample = pd.read_csv(J.SAMPLE, dtype=str, keep_default_na=False).set_index("case")
    cold = a[(a.ask == "cold") & ~a.case.isin(list(CONTROLS))]
    if len(cold):
        # 0.3 asks "would a reader notice" as a cold read of the engine's text
        # alone: did it point at the spot? Compared with Claude's yes / no.
        found = cold.set_index("case").answer.map(lambda x: x.get("places", []))
        hits = {c: spot_found(sample.loc[c], places) for c, places in found.items()}
        verdict = claude.c_noticeable.reindex(list(hits))
        agree = sum((hits[c] and verdict[c] == "yes") or (not hits[c] and verdict[c] == "no")
                    or verdict[c] == "maybe" for c in hits)
        out["cold read finds the spot"] = f"{sum(hits.values())}/{len(hits)}"
        out["noticeable = Claude"] = f"{agree}/{len(hits)} (maybe counts either way)"
    stakes = a[(a.ask.isin(["stakes", "labelled"])) & ~a.case.isin(list(CONTROLS))
               & ((a.ask == "stakes") | (a.variant == "minute"))]
    if len(stakes):
        mine = stakes.set_index("case").answer.map(lambda x: x.get("stakes"))
        out["stakes = Claude"] = f"{sum(mine[c] == claude.c_stakes.get(c) for c in mine.index)}/{len(mine)}"
    doubt = lab[(lab.variant == "minute") & lab.case.isin(SUSPECT_REFERENCE)]
    if len(doubt) and doubt.answer.map(lambda x: "reference_doubt" in x).any():
        out["reference doubted (s05 s21 s30 s34)"] = ", ".join(
            f"{r.case} {r.answer['reference_doubt']}" for r in doubt.sort_values("case").itertuples())
    misses_all = a[(a.ask == "misses") & ~a.case.isin(list(CONTROLS))]
    if len(misses_all):
        own = sum(any(J.diff_words(sample.loc[r.case, "record"], sample.loc[r.case, "engine_wrote"])
                      & J.diff_words(i["reference"], i["engine"]) for i in r.answer.get("differences", []))
                  for r in misses_all.itertuples())
        out["misses list includes the case"] = f"{own}/{len(misses_all)}"
    sizes = real.pivot_table(index="case", columns="variant", values="meaning", aggfunc="first")
    if {"line", "minute", "whole"} <= set(sizes):
        out["same verdict at all 3 sizes"] = f"{(sizes[['line', 'minute', 'whole']].nunique(axis=1) == 1).sum()}/{len(sizes)}"

    blind = a[a.ask == "blind"].copy()
    blind["got"] = blind.answer.map(lambda x: "cant" if x["pick"] == "cant tell"
                                    else "ref" if x["pick"] == x["reference_is"] else "eng")
    pairs = blind.pivot_table(index="case", columns="variant", values="got", aggfunc="first").dropna()
    if len(pairs) and {"order1", "order2"} <= set(pairs):
        out["blind: same answer both orders"] = f"{(pairs.order1 == pairs.order2).sum()}/{len(pairs)}"
        out["blind: reference both orders"] = f"{((pairs.order1 == 'ref') & (pairs.order2 == 'ref')).sum()}/{len(pairs)}"
        picks = blind[blind.got != "cant"]
        out["blind: share picking A"] = f"{(picks.answer.map(lambda x: x['pick']) == 'A').mean():.0%}"

    rank = a[a.ask == "rank"]
    if len(rank):
        sample = pd.read_csv(J.SAMPLE, dtype=str, keep_default_na=False).set_index("case")
        worst = 0
        for r in rank.itertuples():
            ranks, engines = r.answer["ranks"], r.answer["engines"]
            mine = next(k for k, v in engines.items() if v == sample.loc[r.case, "engine"])
            worst += ranks[mine] == max(ranks.values())
        out["rank: caught engine last"] = f"{worst}/{len(rank)}"

    misses = a[(a.ask == "misses") & ~a.case.isin(list(CONTROLS))]
    if len(misses):
        out["misses: items per minute"] = round(misses.answer.map(lambda x: len(x.get("differences", []))).mean(), 1)

    a = every
    out["minutes in all"] = round(a.seconds.sum() / 60, 1)
    for ask in ("labelled", "rule", "blind", "rank", "misses"):
        s = a[(a.ask == ask) & (a.variant != "whole")]
        if len(s):
            out[f"median s: {ask}"] = round(s.seconds.median(), 1)
    w = a[a.variant == "whole"]
    if len(w):
        out["median s: labelled whole"] = round(w.seconds.median(), 1)
    out["median tokens written"] = int(a.tokens_out.median())
    out["max tokens written"] = int(a.tokens_out.max())
    return out


def speed_log(model: str, think: str, prompt_set: str) -> dict:
    # The full logs (thinking text and all) stay out of git; a gzipped copy is
    # committed, so the other laptop reads that.
    path = J.OUT / f"requests-{J.tag(model)}.jsonl"
    if path.exists():
        text = path.read_text(encoding="utf-8")
    elif path.with_suffix(".jsonl.gz").exists():
        text = gzip.decompress(path.with_suffix(".jsonl.gz").read_bytes()).decode("utf-8")
    else:
        return {}
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    rows = [r for r in rows if r.get("think") == think and (r.get("prompt") == "0.3") == (prompt_set == "0.3")]
    if not rows:
        return {}
    r = pd.DataFrame(rows)
    if J.is_claude(model):
        # The API gives no writing time or card memory: tokens over the whole
        # request's seconds (reading the prompt and the network included).
        # Batched answers have no time of their own (0 s), so they are left out.
        return {"tokens/s writing (median)": round((r.tokens_out / r.seconds.replace(0, pd.NA)).median(), 1),
                "cut off at the length limit": int((r.done == "length").sum()),
                "thinking tokens (median)": int(r.get("thinking_tokens", pd.Series([0])).median()),
                "tokens in / out (thousands)": f"{r.tokens_in.sum() / 1000:.0f} / {r.tokens_out.sum() / 1000:.0f}"}
    write = r.write_s.replace(0, pd.NA)
    return {"tokens/s writing (median)": round((r.tokens_out / write).median(), 1),
            "cut off at the length limit": int((r.done == "length").sum()),
            "thinking chars (median)": int(r.thinking.str.len().median()),
            "peak memory MiB": int(pd.to_numeric(r.memory_mib, errors="coerce").max()),
            "spilled to system memory MiB": int(pd.to_numeric(r.spill_mib, errors="coerce").max())}


def main() -> int:
    claude = claude_answers()
    a = load()
    table = {}
    for setup, part in a.groupby("setup"):
        table[setup] = {**score(part, claude),
                        **speed_log(part.model.iloc[0], part.think.iloc[0], part.prompt_set.iloc[0])}
    print(pd.DataFrame(table).fillna("").to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

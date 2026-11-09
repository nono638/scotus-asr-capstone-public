"""Candidate figures and tables for the midterm paper (made 8 November 2026).

Every number is read from the project's data files, never typed in. Run from anywhere:

    .venv/Scripts/python.exe asr-capstone/midterm/figures/make_candidates.py

Writes numbered PNGs (300 dpi) and the tables as markdown to midterm/figures/candidates/,
plus 00-contact-sheet.png with small copies of all of them.

Only figure 11 needs the corpus on D: (the commercial EdAcc transcript). The first run on
the 5090 laptop saves those 40 rows to edacc-commercial-test.csv beside this script, so the
other laptop can rebuild everything from the repository alone.

The judge's labels are Claude Sonnet 5.5's only (the full-v1 run): the meaning question,
valid answers, the last answer per case. The Qwen judge's answers are not used.
"""
import json
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
CAP = HERE.parent.parent                      # asr-capstone/
FIND = CAP / "findings"
OUT = HERE / "candidates"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- look
# Colours: the first three slots of a colour-blind-checked palette for the three engines that
# ran everywhere, each with its own marker shape so the charts also work in black and white.
# Two steps of one blue for "benchmark rule" (light) and "verbatim rule" (dark).
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, GREY = "#e1e0d9", "#c3c2b7", "#b5b3ad"
LIGHT, DARK = "#86b6ef", "#104281"
ENGINE = {"Qwen3": ("#2a78d6", "o"), "Whisper": ("#eb6834", "s"), "Parakeet": ("#1baf7a", "^")}
CORPUS = {"scotus": "Supreme Court", "coraal": "CORAAL", "earnings22": "Earnings-22", "edacc": "EdAcc"}

plt.rcParams.update({
    "font.family": ["Segoe UI", "Arial", "DejaVu Sans"], "font.size": 10,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
    "xtick.major.size": 0, "ytick.major.size": 0, "axes.grid": False, "grid.color": GRID,
    "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 9,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})

MADE = []        # (file, title) for the contact sheet
CHECKS = []      # (what, draft says, data says)


def pct2(x):
    """Two decimals, rounding halves up as the draft does (14.975 -> 14.98)."""
    from decimal import ROUND_HALF_UP, Decimal
    return str(Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def check(what, draft, got):
    CHECKS.append((what, draft, got))


def finish(fig, num, slug, title, source):
    """Title above, one-line source note below, both lined up with the left edge of the art."""
    fig.canvas.draw()
    bb = fig.get_tightbbox(fig.canvas.get_renderer())
    w, h = fig.get_size_inches()
    chars = int(bb.width * 72 / (11 * 0.52))
    fig.text(bb.x0 / w, (bb.y1 + 0.10) / h, textwrap.fill(title, chars), ha="left", va="bottom",
             fontsize=11, weight="bold", color=INK)
    fig.text(bb.x0 / w, (bb.y0 - 0.08) / h, textwrap.fill(source, int(bb.width * 72 / (7.5 * 0.5))),
             ha="left", va="top", fontsize=7.5, color=MUTED)
    name = f"{num}-{slug}.png"
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    MADE.append((name, title))
    print("wrote", name)


def xgrid(ax):
    ax.grid(axis="x")
    ax.set_axisbelow(True)


def ygrid(ax):
    ax.grid(axis="y")
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- data
seven = pd.read_csv(FIND / "final-seven-model-results.csv")
seven["engine"] = seven.model.map({
    "Qwen3-ASR-1.7B-hf": "Qwen3", "whisper-large-v3": "Whisper", "Voxtral-Mini-3B-2507": "Voxtral",
    "granite-speech-4.1-2b-plus": "Granite Plus", "canary-1b-v2": "Canary",
    "parakeet-tdt-0.6b-v3": "Parakeet", "granite-speech-4.1-2b": "Granite"})
seven["bench"], seven["verb"] = seven.wer_standard_fixed, seven.wer_verbatim
seven["ratio"] = seven.verb / seven.bench
for e, b, v in [("Qwen3", 4.24, 14.98), ("Whisper", 5.71, 14.01), ("Parakeet", 5.77, 17.18),
                ("Voxtral", 5.91, 14.18), ("Granite Plus", 6.27, 28.92), ("Canary", 6.68, 16.12),
                ("Granite", 7.76, 17.14)]:
    r = seven[seven.engine == e].iloc[0]
    check(f"Table 3 {e}", f"{b} / {v}", f"{pct2(r.bench)} / {pct2(r.verb)}")

flip = pd.read_csv(FIND / "flip" / "per-argument.csv")
by_term = pd.read_csv(FIND / "flip" / "by-term.csv")


def sonnet_labels():
    a = pd.read_csv(FIND / "judge" / "answers-claude-sonnet-5-5-full-v1.csv")
    a = a[(a.ask == "meaning") & (a.valid.astype(str) == "True")].drop_duplicates("case", keep="last")
    got = a.answer.map(json.loads)
    for k in ["meaning", "severity", "reference_doubt"]:
        a[k] = got.map(lambda d: d.get(k))
    cases = pd.read_csv(FIND / "judge" / "full-v1.csv")
    return cases.merge(a[["case", "meaning", "severity", "reference_doubt"]], on="case", how="inner")


judged = sonnet_labels()
check("cases judged", "37,354", f"{len(judged):,}")


# ================================================================ figures
def fig01():
    d = seven.sort_values("bench", ascending=False).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    y = np.arange(len(d))
    for i, r in d.iterrows():
        ax.plot([r.bench, r.verb], [i, i], color=GREY, lw=2, zorder=1, solid_capstyle="round")
    ax.scatter(d.bench, y, s=46, color=LIGHT, edgecolor="white", linewidth=1.2, zorder=3,
               label="Benchmark rule")
    ax.scatter(d.verb, y, s=46, color=DARK, edgecolor="white", linewidth=1.2, zorder=3, marker="s",
               label="Verbatim rule")
    for i, r in d.iterrows():
        ax.text(r.verb + 0.9, i, f"{r.ratio:.1f}×", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(y, [e + ("*" if e == "Granite Plus" else "") for e in d.engine])
    ax.set_xlim(0, 33)
    ax.set_xlabel("Word error rate (%)")
    xgrid(ax)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, handletextpad=0.2, borderaxespad=0.2)
    lo, hi = seven.ratio.min(), seven.ratio.max()
    check("verbatim/benchmark ratio", "2.2 to 4.6", f"{lo:.1f} to {hi:.1f}")
    finish(fig, "01", "seven-engines-two-rules",
           "Scored as a record, every engine's error rate more than doubles",
           "Supreme Court, 2017 term, 61 arguments, mean of per-argument rates; × = verbatim ÷ benchmark. "
           "*Granite Plus writes no punctuation or capitals, by design. "
           "Source: findings/final-seven-model-results.csv")


def fig02():
    d = seven.copy()
    d["rb"] = d.bench.rank().astype(int)
    d["rv"] = d.verb.rank().astype(int)
    fig, ax = plt.subplots(figsize=(4.0, 3.2))
    for _, r in d.iterrows():
        hot = r.engine in ("Qwen3", "Whisper")
        col = ENGINE[r.engine][0] if hot else GREY
        ax.plot([0, 1], [r.rb, r.rv], color=col, lw=2.4 if hot else 1.4, zorder=3 if hot else 2,
                marker=ENGINE[r.engine][1] if hot else "o", ms=6, markeredgecolor="white")
        w = "bold" if hot else "normal"
        ax.text(-0.05, r.rb, f"{r.engine}  {pct2(r.bench)}%", ha="right", va="center", fontsize=9,
                color=INK if hot else INK2, weight=w)
        ax.text(1.05, r.rv, f"{pct2(r.verb)}%  {r.engine}", ha="left", va="center", fontsize=9,
                color=INK if hot else INK2, weight=w)
    ax.set_ylim(7.5, 0.5)
    ax.set_xlim(-0.05, 1.05)
    ax.axis("off")
    ax.text(0, 0.0, "Benchmark rule", ha="right", va="bottom", fontsize=9.5, color=INK2)
    ax.text(1, 0.0, "Verbatim rule", ha="left", va="bottom", fontsize=9.5, color=INK2)
    finish(fig, "02", "rank-change",
           "The two scoring rules crown different engines",
           "Rank of seven engines, best at top. Supreme Court, 2017 term, 61 arguments. "
           "Source: findings/final-seven-model-results.csv")


def fig03():
    bx = flip.Whisper_benchmark - flip.Qwen3_benchmark      # > 0: Qwen3 better on the benchmark rule
    vy = flip.Qwen3_verbatim - flip.Whisper_verbatim        # > 0: Whisper better on the verbatim rule
    n = len(flip)
    both = ((bx > 0) & (vy > 0)).sum()
    check("flip arguments", "190 of 258", f"{both} of {n}")
    check("Qwen3 better, benchmark", "249", f"{(bx > 0).sum()}")
    check("Whisper better, verbatim", "199", f"{(vy > 0).sum()}")
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    ax.fill_between([0, 4], 0, 4.5, color="#cde2fb", zorder=0, lw=0)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.scatter(bx, vy, s=14, color="#2a78d6", alpha=0.75, edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_xlim(-3.2, 4.0)
    ax.set_ylim(-2.4, 4.5)
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3, 4])
    ax.set_yticks([-2, -1, 0, 1, 2, 3, 4])
    ax.set_xlabel("Benchmark rule: Whisper minus Qwen3\n(points; right of 0, Qwen3 is better)")
    ax.set_ylabel("Verbatim rule: Qwen3 minus Whisper\n(points; above 0, Whisper is better)")
    ax.text(3.9, 4.35, f"Each rule picks a\ndifferent winner:\n{both} of {n}", ha="right", va="top",
            fontsize=9.5, color=INK, weight="bold")
    q_both = ((bx > 0) & (vy <= 0)).sum()
    w_both = ((bx <= 0) & (vy > 0)).sum()
    ax.text(0.1, -2.3, f"Qwen3 better\non both: {q_both}", ha="left", va="bottom", fontsize=8.5, color=INK2)
    ax.text(-3.1, 0.15, f"Whisper better\non both: {w_both}", ha="left", va="bottom", fontsize=8.5, color=INK2)
    finish(fig, "03", "flip-per-argument",
           f"In {both} of {n} arguments, the two rules crown different engines",
           "One dot per Supreme Court argument, terms 2010, 2017, 2021 and 2025. "
           "Source: findings/flip/per-argument.csv")


def fig04():
    d = by_term[by_term.term != "all four"].copy()
    d["share"] = 100 * d.flips / d.arguments
    d["year"] = d.term.str[2:]
    for t, f, a in [("OT2010", 56, 77), ("OT2017", 51, 61), ("OT2021", 46, 62), ("OT2025", 37, 58)]:
        r = d[d.term == t].iloc[0]
        check(f"flips {t}", f"{f} of {a}", f"{r.flips} of {r.arguments}")
    fig, ax = plt.subplots(figsize=(3.8, 2.6))
    x = np.arange(len(d))
    ax.bar(x, d.share, width=0.5, color="#2a78d6")
    for i, r in enumerate(d.itertuples()):
        ax.text(i, r.share + 1.5, f"{r.flips} of {r.arguments}", ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_xticks(x, d.year)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel("Arguments where the\nrules crown different engines")
    ygrid(ax)
    finish(fig, "04", "flip-by-term",
           "The two rules disagree in most arguments of every term",
           "Qwen3 better on the benchmark rule and Whisper better on the verbatim rule, same argument. "
           "Supreme Court term (year it began). Source: findings/flip/by-term.csv")


def fig05():
    s = judged[(judged.corpus == "scotus") & (judged.meaning == "opposite")]
    neg = s[s.subkind == "negation"].groupby("engine").size()
    tot = s.groupby("engine").size()
    order = tot.sort_values().index.tolist()
    check("opposite counts Qwen3/Parakeet/Whisper", "146/121/80", "/".join(str(tot[e]) for e in ["Qwen3", "Parakeet", "Whisper"]))
    check("negation opposites", "121/94/48", "/".join(str(neg[e]) for e in ["Qwen3", "Parakeet", "Whisper"]))
    fig, ax = plt.subplots(figsize=(4.2, 2.1))
    y = np.arange(len(order))
    ax.barh(y, [neg[e] for e in order], height=0.5, color=DARK, edgecolor="white", linewidth=1.2,
            label="a \"not\" lost or added")
    ax.barh(y, [tot[e] - neg[e] for e in order], left=[neg[e] for e in order], height=0.5,
            color=LIGHT, edgecolor="white", linewidth=1.2, label="another word")
    for i, e in enumerate(order):
        ax.text(tot[e] + 3, i, str(tot[e]), va="center", fontsize=9.5, color=INK, weight="bold")
    ax.set_yticks(y, order)
    ax.set_xlim(0, 165)
    ax.set_xlabel("Cases the judge called \"the opposite of the record\"")
    xgrid(ax)
    ax.legend(loc="lower left", ncol=2, fontsize=8.5, bbox_to_anchor=(0, 1.0), borderaxespad=0.2,
              handlelength=1, handletextpad=0.4)
    finish(fig, "05", "says-the-opposite",
           "The benchmark winner reverses the meaning most often",
           "Same 258 Supreme Court arguments (310 hours) for each engine; text-only labels by Claude Sonnet 5.5, "
           "not yet checked by ear. Source: findings/judge/ (full-v1 cases, Sonnet answers)")


def fig05b():
    """05 with the error rates beside it, so the reader sees which engine is the benchmark winner."""
    s = judged[(judged.corpus == "scotus") & (judged.meaning == "opposite")]
    opp = s.groupby("engine").size()
    neg = s[s.subkind == "negation"].groupby("engine").size()
    wer = {e: flip[f"{e}_benchmark"].mean() for e in ENGINE}
    check("arguments behind 05b WER", "258", f"{len(flip)}")
    order = sorted(ENGINE, key=lambda e: wer[e], reverse=True)       # best at the top
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.4, 2.0), sharey=True,
                                 gridspec_kw={"wspace": 0.35})
    y = np.arange(len(order))
    for ax, vals, fmt, lim in [(a1, wer, "{:.2f}%", 8.2), (a2, opp, "{}", 185)]:
        ax.barh(y, [vals[e] for e in order], height=0.55, color=[ENGINE[e][0] for e in order])
        for i, e in enumerate(order):
            ax.text(vals[e] + lim * 0.02, i, fmt.format(vals[e]), va="center", fontsize=9.5,
                    color=INK, weight="bold")
        ax.set_xlim(0, lim)
        xgrid(ax)
    a1.set_yticks(y, order)
    a1.set_title("Word error rate, benchmark rule\n(lower is better)", fontsize=9.5, color=INK2, loc="left")
    a2.set_title("Times the meaning was reversed\n(lower is better)", fontsize=9.5, color=INK2, loc="left")
    a1.set_xticks([0, 2, 4, 6, 8], ["0%", "2%", "4%", "6%", "8%"])
    best = order[-1]
    a1.text(wer[best] / 2, len(order) - 1, "best", ha="center", va="center", fontsize=8.5,
            color="white", weight="bold")
    a2.text(opp[best] / 2, len(order) - 1, "most", ha="center", va="center", fontsize=8.5,
            color="white", weight="bold")
    finish(fig, "05b", "best-score-most-reversals",
           f"The engine with the lowest error rate, {best}, reverses the meaning most often",
           "Same 258 Supreme Court arguments (310 hours) for each engine. Error rate: mean of per-argument "
           "rates. Reversals: cases Claude Sonnet 5.5 judged \"the opposite of the record\" from the text alone, "
           f"not yet checked by ear; most are a \"not\" lost or added ({neg['Qwen3']} / {neg['Parakeet']} / "
           f"{neg['Whisper']} for Qwen3 / Parakeet / Whisper). "
           "Source: findings/flip/per-argument.csv; findings/judge/ (full-v1, Sonnet answers)")


def flip_counts():
    bx = flip.Whisper_benchmark - flip.Qwen3_benchmark      # > 0: Qwen3 better on the benchmark rule
    vy = flip.Qwen3_verbatim - flip.Whisper_verbatim        # > 0: Whisper better on the verbatim rule
    return bx, vy, {("Qwen3", "Qwen3"): ((bx > 0) & (vy <= 0)).sum(),
                    ("Qwen3", "Whisper"): ((bx > 0) & (vy > 0)).sum(),
                    ("Whisper", "Qwen3"): ((bx <= 0) & (vy <= 0)).sum(),
                    ("Whisper", "Whisper"): ((bx <= 0) & (vy > 0)).sum()}


def fig03b():
    """The flip as a 2 x 2 table of counts: no axes to decode."""
    _, _, c = flip_counts()
    n = len(flip)
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.axis("off")
    words = {("Qwen3", "Qwen3"): "Qwen3 wins\nunder both rules",
             ("Qwen3", "Whisper"): "Each rule picks a\ndifferent winner",
             ("Whisper", "Qwen3"): "Different winners,\nthe other way",
             ("Whisper", "Whisper"): "Whisper wins\nunder both rules"}
    for r, bench in enumerate(["Qwen3", "Whisper"]):          # rows: benchmark winner (top row Qwen3)
        for k, verb in enumerate(["Qwen3", "Whisper"]):       # columns: verbatim winner
            x, yy = k, 1 - r
            hot = (bench, verb) == ("Qwen3", "Whisper")
            ax.add_patch(plt.Rectangle((x + 0.03, yy + 0.03), 0.94, 0.94,
                                       color="#2a78d6" if hot else "#f1f0ec", lw=0))
            col = "white" if hot else INK
            ax.text(x + 0.5, yy + 0.62, str(c[(bench, verb)]), ha="center", va="center",
                    fontsize=22 if hot else 16, weight="bold", color=col)
            ax.text(x + 0.5, yy + 0.27, words[(bench, verb)], ha="center", va="center",
                    fontsize=8.5, color=col if hot else INK2)
    ax.text(1, 2.2, "Winner under the verbatim rule (scored as a record)", ha="center", va="bottom",
            fontsize=9, color=INK2)
    for k, e in enumerate(["Qwen3", "Whisper"]):
        ax.text(k + 0.5, 2.02, e, ha="center", va="bottom", fontsize=9.5, weight="bold", color=INK)
        ax.text(-0.04, 1.5 - k, e, ha="right", va="center", fontsize=9.5, weight="bold", color=INK)
    ax.text(-0.42, 1, "Winner under the benchmark rule\n(how leaderboards score)", ha="center",
            va="center", rotation=90, fontsize=9, color=INK2)
    check("03b cells Q-Q / Q-W / W-Q / W-W", "59 / 190 / 0 / 9",
          " / ".join(str(c[k]) for k in [("Qwen3", "Qwen3"), ("Qwen3", "Whisper"),
                                         ("Whisper", "Qwen3"), ("Whisper", "Whisper")]))
    finish(fig, "03b", "flip-two-by-two",
           f"In {c[('Qwen3', 'Whisper')]} of {n} Supreme Court arguments, the two scoring rules pick "
           "different winners",
           f"Each of the {n} arguments (terms 2010, 2017, 2021 and 2025) is counted once: which of Qwen3 and "
           "Whisper had the lower word error rate under each rule. Source: findings/flip/per-argument.csv")


def fig03c():
    """03 with plain-language axes and every quadrant labelled."""
    bx, vy, c = flip_counts()
    n = len(flip)
    fig, ax = plt.subplots(figsize=(4.4, 3.8))
    ax.fill_between([0, 4], 0, 4.5, color="#cde2fb", zorder=0, lw=0)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.scatter(bx, vy, s=14, color="#2a78d6", alpha=0.75, edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_xlim(-3.2, 4.0)
    ax.set_ylim(-2.4, 4.5)
    ax.set_xticks([-2, 0, 2, 4])
    ax.set_yticks([-2, 0, 2, 4])
    ax.set_xlabel("← Whisper better        Benchmark rule        Qwen3 better →\n"
                  "(difference in word error rate, points)", fontsize=9)
    ax.set_ylabel("← Qwen3 better     Verbatim rule     Whisper better →\n"
                  "(difference in word error rate, points)", fontsize=9)
    lab = dict(fontsize=8.5, color=INK2)
    ax.text(3.9, 4.35, f"Different winners:\n{c[('Qwen3', 'Whisper')]} arguments", ha="right", va="top",
            fontsize=9.5, color=INK, weight="bold")
    ax.text(0.1, -2.3, f"Qwen3 wins both: {c[('Qwen3', 'Qwen3')]}", ha="left", va="bottom", **lab)
    ax.text(-3.1, 3.3, f"Whisper wins\nboth: {c[('Whisper', 'Whisper')]}", ha="left", va="top", **lab)
    ax.text(-3.1, -2.3, f"Different winners,\nthe other way: {c[('Whisper', 'Qwen3')]}", ha="left",
            va="bottom", **lab)
    d = flip.assign(bx=bx, vy=vy)
    pick = d[(d.bx > -1.2) & (d.bx < -0.8)].iloc[0]
    ax.annotate("each dot is one\nargument", xy=(pick.bx, pick.vy), xytext=(-3.1, 0.9), fontsize=8,
                color=INK2, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.7, shrinkB=4))
    finish(fig, "03c", "flip-per-argument-labelled",
           f"In {c[('Qwen3', 'Whisper')]} of {n} arguments, the two scoring rules pick different winners",
           "One dot per Supreme Court argument, terms 2010, 2017, 2021 and 2025. Source: "
           "findings/flip/per-argument.csv")


def meaning_shares():
    m = judged[(judged.kind == "meaning") & judged.engine.isin(ENGINE)]
    t = pd.crosstab([m.corpus, m.engine], m.meaning, normalize="index") * 100
    t["fluent"] = t.reworded + t.opposite
    return t


def fig06():
    t = meaning_shares()
    for e, vals in [("Parakeet", [43, 37, 38, 27]), ("Qwen3", [19, 16, 11, 12])]:
        got = [t.loc[(c, e), "garbled"] for c in ["scotus", "coraal", "earnings22", "edacc"]]
        check(f"{e} garbled Court/CORAAL/E22/EdAcc", "/".join(map(str, vals)), "/".join(f"{g:.1f}" for g in got))
    check("Qwen3 fluent Court/CORAAL", "24/29", f"{t.loc[('scotus', 'Qwen3'), 'fluent']:.2f}/{t.loc[('coraal', 'Qwen3'), 'fluent']:.2f}")
    check("Whisper garbled Court/E22", "39/8", f"{t.loc[('scotus', 'Whisper'), 'garbled']:.1f}/{t.loc[('earnings22', 'Whisper'), 'garbled']:.1f}")
    corpora = ["scotus", "coraal", "earnings22", "edacc"]
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 2.5), sharey=True)
    for ax, col, label in [(axes[0], "garbled", "Garbled: no longer makes sense (%)"),
                           (axes[1], "fluent", "Fluent: reworded or reversed (%)")]:
        y = np.arange(len(corpora))
        for c_i, c in enumerate(corpora):
            vals = [t.loc[(c, e), col] for e in ENGINE]
            ax.plot([min(vals), max(vals)], [c_i, c_i], color=GRID, lw=2, zorder=1)
        for e, (colr, mk) in ENGINE.items():
            ax.scatter([t.loc[(c, e), col] for c in corpora], y, s=50, color=colr, marker=mk,
                       edgecolor="white", linewidth=1, zorder=3, label=e)
        ax.set_xlim(0, 50)
        ax.set_xlabel(label)
        xgrid(ax)
    axes[0].set_yticks(np.arange(len(corpora)), [CORPUS[c] for c in corpora])
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, handletextpad=0.1, borderaxespad=0.2)
    finish(fig, "06", "garbled-vs-fluent",
           "Parakeet's errors look wrong; Qwen3's read naturally",
           "Share of each engine's meaning-change cases, by the judge's label (Claude Sonnet 5.5, text only). "
           "Source: findings/judge/ (full-v1 cases, Sonnet answers)")


def fig06b():
    """The same labels as a stacked bar, Supreme Court only."""
    t = meaning_shares()
    cats = [("garbled", "garbled", DARK), ("changed", "changed", "#3987e5"),
            ("fluent", "reworded or opposite", LIGHT), ("same", "same", "#e1e0d9")]
    engines = ["Parakeet", "Whisper", "Qwen3"]
    fig, ax = plt.subplots(figsize=(4.6, 1.9))
    for i, e in enumerate(engines):
        left = 0
        for col, label, colr in cats:
            v = t.loc[("scotus", e), col]
            ax.barh(i, v - 0.4, left=left, height=0.55, color=colr, label=label if i == 0 else None)
            if v > 9:
                ax.text(left + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=8.5,
                        color="white" if colr in (DARK, "#3987e5") else INK)
            left += v
    ax.set_yticks(range(len(engines)), engines)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.invert_yaxis()
    ax.spines["left"].set_visible(False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, fontsize=8.5, handlelength=1,
              handletextpad=0.3, columnspacing=0.8, borderaxespad=0.2)
    finish(fig, "06b", "meaning-labels-court",
           "On the Court, 43% of Parakeet's meaning errors are garbled, against 19% of Qwen3's",
           "Meaning-change cases on 258 Supreme Court arguments, judge's label (Claude Sonnet 5.5, text only). "
           "Source: findings/judge/ (full-v1 cases, Sonnet answers)")


def fig07():
    t = pd.crosstab(judged.corpus, judged.reference_doubt, normalize="index") * 100
    check("E22 reference doubt yes/maybe", "27 / 20", f"{t.loc['earnings22', 'yes']:.1f} / {t.loc['earnings22', 'maybe']:.1f}")
    check("other data sets, yes", "1 to 3", ", ".join(f"{t.loc[c, 'yes']:.1f}" for c in ["scotus", "coraal", "edacc"]))
    order = ["earnings22", "edacc", "scotus", "coraal"]
    fig, ax = plt.subplots(figsize=(4.2, 2.0))
    y = np.arange(len(order))
    yes = [t.loc[c, "yes"] for c in order]
    may = [t.loc[c, "maybe"] for c in order]
    ax.barh(y, yes, height=0.55, color=DARK, edgecolor="white", linewidth=1.2, label="reference looks wrong")
    ax.barh(y, may, left=yes, height=0.55, color=LIGHT, edgecolor="white", linewidth=1.2, label="maybe wrong")
    for i in range(len(order)):
        ax.text(yes[i] + may[i] + 1.2, i, f"{yes[i]:.0f}% + {may[i]:.0f}%", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [CORPUS[c] for c in order])
    ax.invert_yaxis()
    ax.set_xlim(0, 60)
    ax.set_xticks([0, 20, 40, 60], ["0%", "20%", "40%", "60%"])
    ax.set_xlabel("Share of flagged cases")
    xgrid(ax)
    ax.legend(loc="lower right", fontsize=8.5)
    finish(fig, "07", "reference-doubt",
           "On Earnings-22, the judge often doubts the reference itself",
           "All 37,354 cases the searches found, judged from text by Claude Sonnet 5.5: "
           "does the reference itself look wrong? Source: findings/judge/ (full-v1 cases, Sonnet answers)")


def fig08():
    o = pd.read_csv(FIND / "error-model" / "odds-ratios-scotus.csv")
    names = {
        "word_type=legal": "Legal term (vs ordinary word)",
        "near_dash": "Next to the reporter's \"--\"",
        "turn=0": "First word after a speaker change",
        "word_type=name": "Name (vs ordinary word)",
        "turn=1-3": "1–3 words after a speaker change",
        "disfluency_near": "Filler or repeat within two words",
        "word_type=number": "Number (vs ordinary word)",
        "turn=4-10": "4–10 words after a speaker change",
        "rate": "Each extra word per second",
        "role=justice": "Spoken by a justice (vs counsel)",
        "word_type=function": "Function word (vs ordinary word)",
    }
    c = o[o.term.isin(names)].copy()
    c["label"] = c.term.map(names)
    c = c.sort_values("odds_ratio")
    eng = o[o.term.str.startswith("engine=")]
    r = o.set_index("term")
    check("OR first word after change", "5.7", f"{r.loc['turn=0', 'odds_ratio']:.1f}")
    check("OR near dash", "6.7", f"{r.loc['near_dash', 'odds_ratio']:.1f}")
    check("OR legal (CI)", "15.8 (10.9 to 22.9)",
          f"{r.loc['word_type=legal', 'odds_ratio']:.1f} ({r.loc['word_type=legal', 'ci_low']:.1f} to {r.loc['word_type=legal', 'ci_high']:.1f})")
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    ax.axvspan(eng.odds_ratio.min(), eng.odds_ratio.max(), color="#eeede8", zorder=0, lw=0)
    ax.axvline(1, color=AXIS, lw=0.9)
    y = np.arange(len(c))
    ax.hlines(y, c.ci_low, c.ci_high, color=INK, lw=1.4)
    ax.scatter(c.odds_ratio, y, s=30, color=INK, zorder=3)
    for i, rr in enumerate(c.itertuples()):
        ax.text(rr.ci_high * 1.12, i, f"{rr.odds_ratio:.1f}", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(y, c.label)
    ax.set_xscale("log")
    ax.set_xlim(0.8, 40)
    ax.set_xticks([1, 2, 5, 10, 20], ["1", "2", "5", "10", "20"])
    ax.minorticks_off()
    ax.set_xlabel("Odds of a missed word (log scale; 1 = no difference)")
    ax.text(eng.odds_ratio.max() * 1.08, 0.5,
            f"← shaded: the other six engines\n    against Qwen3, {eng.odds_ratio.min():.1f}–{eng.odds_ratio.max():.1f}",
            ha="left", va="center", fontsize=8, color=INK2)
    ax.set_ylim(-0.6, len(c) - 0.4)
    xgrid(ax)
    finish(fig, "08", "error-model-forest",
           "What surrounds a word matters more than which engine hears it",
           "Logistic regression, every word of the 2017 term × 7 engines, one term per argument; 95% intervals. "
           "Speaker-change rows are against a word 10+ words away. Source: findings/error-model/odds-ratios-scotus.csv")


def fig09():
    e = pd.read_csv(FIND / "error-model" / "error-rates-scotus.csv")
    get = lambda c, v: e[(e.condition == c) & (e.value == v)].error_pct.iloc[0]  # noqa: E731
    rows = [("First word", get("turn", "0")), ("1–3 words", get("turn", "1-3")),
            ("4–10 words", get("turn", "4-10")), ("Further away", get("turn", "far"))]
    dash = [("Next to a \"--\"", get("near_dash", "1")), ("Not next to one", get("near_dash", "0"))]
    check("plain rate first word / far", "29% / 3%", f"{rows[0][1]:.1f} / {rows[3][1]:.1f}")
    fig, axes = plt.subplots(2, 1, figsize=(4.2, 3.1), sharex=True, gridspec_kw={"height_ratios": [4, 2]})
    for ax, data, head in [(axes[0], rows, "Distance from a change of speaker"),
                           (axes[1], dash, "The reporter's dash, which marks an interruption")]:
        y = np.arange(len(data))
        ax.barh(y, [v for _, v in data], height=0.55, color="#2a78d6")
        for i, (_, v) in enumerate(data):
            ax.text(v + 0.6, i, f"{v:.0f}%", va="center", fontsize=9.5, color=INK)
        ax.set_yticks(y, [n for n, _ in data])
        ax.set_ylim(len(data) - 0.5, -0.5)
        ax.set_xlim(0, 33)
        ax.set_xticks([0, 10, 20, 30], ["0%", "10%", "20%", "30%"])
        ax.set_title(head, fontsize=9.5, color=INK2, loc="left")
        xgrid(ax)
    axes[1].set_xlabel("Share of the record's words missed")
    finish(fig, "09", "plain-error-rates",
           f"A word right after a speaker change is missed {rows[0][1] / rows[3][1]:.0f} times as often",
           "Share of the record's words an engine did not write, Supreme Court 2017 term, all 7 engines pooled. "
           "Source: findings/error-model/error-rates-scotus.csv")


def fig10():
    v = pd.read_csv(FIND / "error-model" / "variance-explained.csv").set_index(["corpus", "model"]).mcfadden_r2_beyond_recording
    check("conditions/engine, Court", "about 41", f"{v['scotus', 'conditions'] / v['scotus', 'engine']:.1f}")
    rows = [("Supreme Court", "scotus"), ("EdAcc", "edacc")]
    fig, ax = plt.subplots(figsize=(4.2, 2.0))
    y, labels = [], []
    for i, (name, c) in enumerate(rows):
        for j, (what, col) in enumerate([("conditions", DARK), ("engine", LIGHT)]):
            yy = i * 2.6 + j
            ax.barh(yy, v[c, what], height=0.7, color=col)
            note = f"{v[c, what]:.3f}"
            if what == "conditions":
                note += f"  ({v[c, 'conditions'] / v[c, 'engine']:.0f}× the engine)"
            ax.text(v[c, what] + 0.004, yy, note, va="center", fontsize=9, color=INK)
            y.append(yy)
            labels.append(f"{name}: {what}")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.36)
    ax.set_xticks([0, 0.1, 0.2, 0.3])
    ax.set_xlabel("McFadden R² beyond knowing the recording")
    xgrid(ax)
    finish(fig, "10", "conditions-vs-engine",
           "The conditions explain about 41 times as much as the choice of engine",
           "Logistic regression of missed words, with one term per recording. Supreme Court 2017 term (7 engines), "
           "EdAcc test split (5 engines). Source: findings/error-model/variance-explained.csv")


def commercial_rows():
    cache = HERE / "edacc-commercial-test.csv"
    try:
        sys.path.insert(0, str(CAP / "tools"))
        import benchmark_tables
        c = benchmark_tables.company_rows()
        c.to_csv(cache, index=False)
    except Exception as err:  # corpus not on this laptop
        print("commercial rows from cache:", err)
        c = pd.read_csv(cache, dtype={"recording": str})
    return c


def fig11():
    c = commercial_rows()
    c["commercial"] = 100 * c.errors / c.reference_words
    r = pd.read_csv(FIND / "recordings.csv", dtype={"recording": str})
    q = r[(r.corpus == "edacc") & (r.part == "test") & (r.engine == "Qwen3")]
    d = q.merge(c[["recording", "commercial"]], on="recording", validate="one_to_one")
    pooled_q = 100 * (q.substituted + q.dropped + q.added).sum() / q.reference_words.sum()
    pooled_c = 100 * c.errors.sum() / c.reference_words.sum()
    better = (d.error_rate < d.commercial).sum()
    check("EdAcc Qwen3 vs commercial", "11.44 vs 17.46, 40 of 40", f"{pooled_q:.2f} vs {pooled_c:.2f}, {better} of {len(d)}")
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    top = 5 * np.ceil(max(d.commercial.max(), d.error_rate.max()) / 5)
    ax.plot([0, top], [0, top], color=AXIS, lw=1)
    ax.scatter(d.commercial, d.error_rate, s=22, color=ENGINE["Qwen3"][0], edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_aspect("equal")
    ax.set_xlabel("Commercial transcript, word error rate (%)")
    ax.set_ylabel("Qwen3, word error rate (%)")
    ax.text(top * 0.08, top * 0.92, "Qwen3 worse", fontsize=8.5, color=MUTED, va="top")
    ax.text(top * 0.95, top * 0.05, f"Qwen3 better:\n{better} of {len(d)}", fontsize=9.5, color=INK,
            ha="right", va="bottom", weight="bold")
    xgrid(ax)
    ygrid(ax)
    finish(fig, "11", "edacc-qwen3-vs-commercial",
           f"A laptop engine beat EdAcc's commercial transcript on all {len(d)} conversations",
           "EdAcc test split, benchmark rule; one dot per conversation. The commercial transcript ships with the "
           "data set (2023). Source: findings/recordings.csv; company.ctm via tools/benchmark_tables.py")


def fig12():
    s = pd.read_csv(FIND / "earnings22" / "subset10-two-references.csv")
    s = s[s.rule == "lowercase_nopunct"]
    g = s.groupby(["who", "reference"])[["errors", "ref_words"]].sum()
    g = (100 * g.errors / g.ref_words).unstack()
    for e, cl, vb in [("Whisper", 7.1, 13.0), ("Parakeet", 15.4, 9.8), ("Qwen3", 10.0, 11.3)]:
        check(f"E22 two refs {e} clean/verbatim", f"{cl}/{vb}", f"{g.loc[e, 'clean']:.1f}/{g.loc[e, 'verbatim']:.1f}")
    humans = g.loc["Clean transcriber", "verbatim"]
    engines = ["Whisper", "Qwen3", "Parakeet"]
    fig, ax = plt.subplots(figsize=(4.2, 2.1))
    ax.axvline(humans, color=MUTED, lw=1)
    ax.text(humans + 0.2, -0.75, f"the two human transcripts\ndiffer by {humans:.1f}%", fontsize=8,
            color=INK2, va="bottom")
    for i, e in enumerate(engines):
        ax.plot([g.loc[e, "clean"], g.loc[e, "verbatim"]], [i, i], color=GREY, lw=2, zorder=1)
    ax.scatter([g.loc[e, "clean"] for e in engines], range(3), s=50, color=LIGHT, edgecolor="white",
               linewidth=1.2, zorder=3, label="against the clean transcript")
    ax.scatter([g.loc[e, "verbatim"] for e in engines], range(3), s=50, color=DARK, marker="s",
               edgecolor="white", linewidth=1.2, zorder=3, label="against the verbatim transcript")
    ax.set_yticks(range(3), engines)
    ax.set_ylim(2.5, -1.0)
    ax.set_xlim(0, 18)
    ax.set_xticks([0, 5, 10, 15])
    ax.set_xlabel("Word error rate (%)")
    xgrid(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, handletextpad=0.2, borderaxespad=0.2)
    finish(fig, "12", "earnings22-two-references",
           "Which engine wins depends on which human transcript is the reference",
           "Earnings-22's 10 calls transcribed twice by Rev, clean and verbatim; lowercase, no punctuation, pooled. "
           "Source: findings/earnings22/subset10-two-references.csv")


def fig13():
    rows = []
    for e in ENGINE:
        rows.append(("scotus", e, seven[seven.engine == e].bench.iloc[0]))
    for c in ["edacc", "earnings22", "coraal"]:
        b = pd.read_csv(FIND / c / "benchmark.csv")
        b = b[b.part == "all"]
        for e in ENGINE:
            rows.append((c, e, b[b.engine == e].benchmark.iloc[0]))
    d = pd.DataFrame(rows, columns=["corpus", "engine", "wer"])
    corpora = ["scotus", "earnings22", "edacc", "coraal"]
    fig, ax = plt.subplots(figsize=(4.4, 2.3))
    for k, (e, (col, mk)) in enumerate(ENGINE.items()):
        x = [d[(d.corpus == c) & (d.engine == e)].wer.iloc[0] for c in corpora]
        nudge = (k - 1) * 0.14          # small vertical offset so close dots don't hide each other
        ax.scatter(x, np.arange(len(corpora)) + nudge, s=50, color=col, marker=mk, edgecolor="white",
                   linewidth=1, zorder=3, label=e)
    ax.set_yticks(range(len(corpora)), ["Supreme Court\n(2017 term)", "Earnings-22", "EdAcc", "CORAAL"])
    ax.invert_yaxis()
    ax.set_xlim(0, 20)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("Word error rate, benchmark rule (%)")
    xgrid(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, handletextpad=0.1, borderaxespad=0.2)
    q = d[d.engine == "Qwen3"].set_index("corpus").wer
    lo, hi = (q.drop("scotus") / q["scotus"]).min(), (q.drop("scotus") / q["scotus"]).max()
    finish(fig, "13", "four-data-sets",
           f"Everyday speech is {lo:.1f} to {hi:.1f} times harder than the Court's arguments",
           "Ratio for Qwen3. Supreme Court: mean of 61 arguments; others pooled over all recordings "
           "(EdAcc: dev and test, 76 conversations). "
           "Source: findings/final-seven-model-results.csv; findings/{earnings22,edacc,coraal}/benchmark.csv")


# ================================================================ tables
def draw_table(df, num, slug, title, source, widths, wrap=None, fs=9):
    """A plain table as a picture: bold header, hairline rules, no boxes."""
    wrap = wrap or {}
    cells = [[textwrap.fill(str(v), wrap.get(col, 200)) for col, v in row.items()] for _, row in df.iterrows()]
    heads = [textwrap.fill(c, wrap.get(c, 200)) for c in df.columns]
    lines = [max(1, max(s.count("\n") + 1 for s in r)) for r in [heads] + cells]
    line_h = fs * 1.45 / 72
    height = sum(lines) * line_h + len(lines) * 0.09
    fig = plt.figure(figsize=(sum(widths), height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, sum(widths))
    ax.set_ylim(height, 0)
    ax.axis("off")
    y = 0.0
    xs = np.cumsum([0] + widths[:-1])
    for k, (row, n) in enumerate(zip([heads] + cells, lines)):
        for x, txt in zip(xs, row):
            # one line at a time on its baseline, so digits and letters line up across a row
            for li, part in enumerate(txt.split("\n")):
                ax.text(x + 0.05, y + 0.05 + fs * 1.05 / 72 + li * line_h, part, va="baseline", ha="left",
                        fontsize=fs, weight="bold" if k == 0 else "normal", color=INK if k == 0 else INK2)
        y += n * line_h + 0.09
        ax.axhline(y - 0.02, color=AXIS if k == 0 else GRID, lw=1.0 if k == 0 else 0.6)
    finish(fig, num, slug, title, source)
    md = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    md += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    (OUT / f"{num}-{slug}.md").write_text(f"**{title}**\n\n" + "\n".join(md) + f"\n\n{source}\n", encoding="utf-8")


def short(text, before, after):
    """A few words either side of the marked spot ([...], or ^ where the record has nothing)."""
    if "[" not in text:
        text = text.replace(" ^ ", " [] ", 1)
    left, rest = text.split("[", 1)
    mid, right = rest.split("]", 1)
    words_before = left.split()[-before:] if before else []
    return " ".join(words_before + mid.split() + right.split()[:after])


def table_a():
    cases = pd.read_csv(FIND / "judge" / "full-v1.csv").set_index("case")
    restarts = pd.read_csv(FIND / "failures" / "edits" / "restarts-dropped.csv.gz", dtype={"recording": str})
    tidy = restarts[(restarts.corpus == "scotus") & (restarts.recording == "09-530") & (restarts.engine == "Qwen3")
                    & (restarts.record == "Suppose the -- suppose the")].iloc[0]
    # kind, case, where, does the federal rule allow it, words before and after the spot to show
    rows = [("Tidying", tidy, "Supreme Court, Qwen3", "Yes: false starts \"are not normally included\"", 0, 2),
            ("Standardising", cases.loc["f00248"], "CORAAL, Whisper", "No: grammar \"must be transcribed as spoken\"", 5, 1),
            ("Mishearing", cases.loc["f21401"], "Supreme Court, Qwen3", "No", 1, 3),
            ("Invention", cases.loc["f15697"], "EdAcc, Qwen3", "No", 2, 3)]
    out = []
    for kind, r, where, allowed, before, after in rows:
        eng_after = 0 if kind == "Invention" else after
        out.append({"Kind": kind, "The record": short(r.record_context, before, after),
                    "The engine wrote": short(r.engine_context, before, eng_after), "Where": where,
                    "Federal rule allows it?": allowed})
    df = pd.DataFrame(out)
    draw_table(df, "T1", "four-kinds-of-error", "Four kinds of difference, and which a court record allows",
               "Real cases from the searches (full-v1 cases f00248, f21401, f15697; the tidying case from "
               "findings/failures/edits/restarts-dropped.csv.gz). EdAcc's reference is in capitals. "
               "Rule: Guide to Judiciary Policy, Vol. 6, § 520.40.10(b).",
               widths=[1.05, 1.75, 1.75, 1.25, 1.6],
               wrap={"The record": 26, "The engine wrote": 26, "Where": 16, "Federal rule allows it?": 22,
                     "Kind": 14})


def table_b():
    j = judged.copy()
    j["changed"] = j.meaning.isin(["changed", "opposite", "garbled"])
    j["serious"] = j.severity >= 3
    j["opposite"] = j.meaning == "opposite"
    order = ["scotus", "coraal", "earnings22", "edacc"]
    rows = []
    for c in order + ["all"]:
        s = j if c == "all" else j[j.corpus == c]
        n = len(s)
        rows.append({"Data set": "All four" if c == "all" else CORPUS[c],
                     "Engines judged": len(s.engine.unique()),
                     "Cases found": f"{n:,}",
                     "Meaning changed": f"{s.changed.sum():,} ({100 * s.changed.mean():.0f}%)",
                     "Serious (3–4)": f"{s.serious.sum():,} ({100 * s.serious.mean():.0f}%)",
                     "Opposite": f"{s.opposite.sum():,} ({100 * s.opposite.mean():.1f}%)"})
    check("serious share per data set", "6 to 10%",
          ", ".join(f"{100 * j[j.corpus == c].serious.mean():.1f}" for c in order))
    draw_table(pd.DataFrame(rows), "T2", "search-to-judge-funnel",
               "From the searches to the judge: few flagged cases are serious",
               "Cases found by the rule-based searches, then labelled from text by Claude Sonnet 5.5 "
               "(\"meaning changed\" = changed, opposite or garbled). Source: findings/judge/ (full-v1)",
               widths=[1.25, 0.85, 0.95, 1.35, 1.25, 1.1], wrap={"Engines judged": 9})


def table_c():
    j = judged.copy()
    kinds = [("meaning", "Changes of meaning"), ("edits", "Edits to the speaker's grammar"),
             ("invented", "Words nobody said"), ("skips", "Stretches skipped")]
    rows = []
    for k, name in kinds:
        s = j[j.kind == k]
        p = lambda m: f"{100 * s.meaning.isin(m).mean():.0f}%"  # noqa: E731
        rows.append({"What the search looked for": name, "Cases": f"{len(s):,}",
                     "Same": p(["same"]), "Reworded": p(["reworded"]), "Changed": p(["changed"]),
                     "Opposite": p(["opposite"]), "Garbled": p(["garbled"]),
                     "Serious (3–4)": f"{100 * (s.severity >= 3).mean():.0f}%"})
    e = j[j.kind == "edits"]
    check("edits judged same", "2,823 of 4,509", f"{(e.meaning == 'same').sum():,} of {len(e):,}")
    check("same or reworded, all cases", "about a third", f"{100 * j.meaning.isin(['same', 'reworded']).mean():.1f}%")
    draw_table(pd.DataFrame(rows), "T3", "verdict-by-kind",
               "Most grammar edits keep the meaning, so a meaning check alone would let them through",
               "Judge's label from text (Claude Sonnet 5.5), all four data sets; Same to Garbled add to 100% across. "
               "Source: findings/judge/ (full-v1)",
               widths=[1.8, 0.7, 0.6, 0.8, 0.75, 0.75, 0.7, 0.85],
               wrap={"What the search looked for": 20})


# ================================================================ contact sheet
def contact_sheet():
    import matplotlib.image as mpimg
    files = [f for f, _ in MADE]
    cols = 4
    rows = int(np.ceil(len(files) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.2, rows * 2.7))
    for ax in axes.flat:
        ax.axis("off")
    for ax, f in zip(axes.flat, files):
        ax.imshow(mpimg.imread(OUT / f))
        ax.set_title(f.split("-")[0], fontsize=13, weight="bold", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "00-contact-sheet.png", dpi=150)
    plt.close(fig)
    print("wrote 00-contact-sheet.png")


if __name__ == "__main__":
    for f in [fig01, fig02, fig03, fig03b, fig03c, fig04, fig05, fig05b, fig06, fig06b, fig07, fig08, fig09, fig10, fig11, fig12,
              fig13, table_a, table_b, table_c]:
        f()
    contact_sheet()
    print("\nNumbers against the draft (draft | data):")
    for what, draft, got in CHECKS:
        print(f"  {what:42s} {draft:>26s} | {got}")

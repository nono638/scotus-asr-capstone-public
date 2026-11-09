"""Does the winner change with the scoring rule, argument by argument, in every term?

On the benchmark rule (capitals and punctuation ignored) Qwen3 beat Whisper on
nearly every OT2017 argument; on the verbatim rule Whisper beat Qwen3 on most of
them. This counts the same thing for each term the three default engines cover,
from the harmonised re-scores (the "after" columns, i.e. with the October fixes).

    python tools/flip.py

Writes findings/flip/:

    by-term.csv        per term: arguments, who wins on each rule, and how many
                       arguments flip (Qwen3 ahead on one rule, Whisper on the other)
    per-argument.csv   every argument's three engines on both rules, for a chart
    figure-1.png       Qwen3 against Whisper, one dot per argument, one panel per rule

OT2017 comes from findings/harmonise/per-case.csv (the seven-model study), the other
terms from findings/harmonise/<run>/per-case.csv.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
HARMONISE = CAPSTONE / "findings" / "harmonise"
OUT = CAPSTONE / "findings" / "flip"

#: Where each term's scores are, for each engine.
SOURCES = {
    # Qwen3: the -reread run, damaged chunks decoded again (tools/redecode_chunks.py).
    "Qwen3": ["per-case.csv", "run-scotus250-qwen3-reread/per-case.csv"],
    "Whisper": ["per-case.csv", "run-20260918-035220/per-case.csv",
                "run-scotus250-whisper/per-case.csv"],
    # Parakeet: the -reread runs, gaps decoded again (findings/parakeet-stall/).
    "Parakeet": ["run-20260924-064733-reread/per-case.csv", "run-scotus250-parakeet-reread/per-case.csv"],
}
TERMS = ["OT2010", "OT2017", "OT2021", "OT2025"]
RULES = {"benchmark": "standard_after_wer", "verbatim": "verbatim_after_wer"}


def short_name(model: str) -> str:
    for name in SOURCES:
        if model.lower().startswith(name.lower()):
            return name
    return model


def load() -> pd.DataFrame:
    """One row per engine per argument, with its term and both rates."""
    frames = []
    for engine, files in SOURCES.items():
        for file in files:
            table = pd.read_csv(HARMONISE / file)
            table["engine"] = table.model.map(short_name)
            table = table[table.engine == engine].copy()
            if "term" not in table.columns:
                # The seven-model file is OT2017 only.
                table["term"] = "OT2017"
            # A re-argued case carries its term in its name ("15-1204_OT2017"). The
            # OT2017 ones are named without it here, from whichever file they come
            # (24-109_OT2025 keeps its name, as it always has).
            table["docket"] = table.docket.str.replace("_OT2017", "", regex=False)
            frames.append(table[["engine", "term", "docket"] + list(RULES.values())])
    scores = pd.concat(frames)
    scores = scores[scores.term.isin(TERMS)]
    # Whisper's September run also scored OT2017; the seven-model file is the one
    # the published figures used, so keep the first copy of each.
    scores = scores.drop_duplicates(["engine", "term", "docket"], keep="first")
    return scores.rename(columns={v: k for k, v in RULES.items()})


def plot(wide: pd.DataFrame, path: Path) -> None:
    """Figure 1: one dot per argument, Whisper across, Qwen3 up, one panel per rule.

    Below the diagonal Qwen3 made fewer errors on that argument, above it Whisper did.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {"OT2010": "#1b9e77", "OT2017": "#d95f02", "OT2021": "#7570b3", "OT2025": "#e7298a"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.2))
    for ax, rule, title in zip(axes, RULES, ["Benchmark rule (capitals and punctuation ignored)",
                                             "Verbatim rule (every word as the record writes it)"]):
        x, y = wide[f"Whisper_{rule}"], wide[f"Qwen3_{rule}"]
        for term, colour in colours.items():
            mine = wide.term == term
            ax.scatter(x[mine], y[mine], s=14, alpha=0.75, color=colour, label=term.replace("OT", "Term "))
        low, high = min(x.min(), y.min()) - 0.5, max(x.max(), y.max()) + 0.5
        ax.plot([low, high], [low, high], color="grey", linewidth=1)
        ax.set_xlim(low, high)
        ax.set_ylim(low, high)
        ax.set_aspect("equal")
        # Counted each way, so an exact tie counts for neither.
        ax.text(0.97, 0.04, f"Qwen3 better: {int((y < x).sum())} of {len(wide)}",
                transform=ax.transAxes, ha="right", va="bottom")
        ax.text(0.03, 0.96, f"Whisper better: {int((x < y).sum())} of {len(wide)}",
                transform=ax.transAxes, ha="left", va="top")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("Whisper error rate (%)")
        ax.set_ylabel("Qwen3 error rate (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False)
    fig.suptitle("Which engine is better depends on how you score it: "
                 f"{len(wide)} Supreme Court arguments, one dot each")
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    scores = load()
    wide = scores.pivot_table(index=["term", "docket"], columns="engine",
                              values=list(RULES)).dropna()
    wide.columns = [f"{engine}_{rule}" for rule, engine in wide.columns]
    wide = wide.reset_index()

    rows = []
    for term, group in wide.groupby("term"):
        qwen_bench = group.Qwen3_benchmark < group.Whisper_benchmark
        whisper_verb = group.Whisper_verbatim < group.Qwen3_verbatim
        rows.append({
            "term": term,
            "arguments": len(group),
            "qwen3_beats_whisper_benchmark": int(qwen_bench.sum()),
            "whisper_beats_qwen3_verbatim": int(whisper_verb.sum()),
            "flips": int((qwen_bench & whisper_verb).sum()),
            "parakeet_last_benchmark": int((group.Parakeet_benchmark > group[["Qwen3_benchmark", "Whisper_benchmark"]].max(axis=1)).sum()),
            "parakeet_last_verbatim": int((group.Parakeet_verbatim > group[["Qwen3_verbatim", "Whisper_verbatim"]].max(axis=1)).sum()),
        })
    by_term = pd.DataFrame(rows)
    total = by_term.drop(columns="term").sum()
    by_term = pd.concat([by_term, pd.DataFrame([{"term": "all four", **total.to_dict()}])])

    OUT.mkdir(parents=True, exist_ok=True)
    by_term.to_csv(OUT / "by-term.csv", index=False)
    wide.round(3).to_csv(OUT / "per-argument.csv", index=False)
    plot(wide, OUT / "figure-1.png")
    print(by_term.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

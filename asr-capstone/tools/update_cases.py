"""Bring the judges' case list up to date after the searches are run again, keeping its ids.

findings/judge/full-v1.csv is the list both judges answer. When transcripts are repaired and
the searches run again, most cases are the same case with a corrected time or some punctuation
back. This matches them up, so their ids and answers carry over:

- a case found again keeps its id, with its times and text updated;
- a case no longer found stays in the list, marked "gone" in `not_counted`, so nothing vanishes;
- a case found for the first time joins the end of the list with a new id.

`not_counted` also marks two kinds of case that stay visible but don't count in any rate:
a skip at a chunk seam, where the fault may be how the audio was cut and not the engine; and an
edits case on the same spot as a meaning case, which is one error, not two.

Cases match on what they say, ignoring capitals and punctuation, since a repaired chunk has
its punctuation back.

    python tools/update_cases.py --dry-run
    python tools/update_cases.py
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
FINDINGS = CAPSTONE / "findings"
PATH = FINDINGS / "judge" / "full-v1.csv"
KINDS = ["meaning", "invented", "edits", "skips"]
GONE = "gone after the repair"
SEAM = "skip at a chunk seam"
SAME_SPOT = "same spot as a meaning case"


def plain(text: str) -> str:
    return re.sub(r"[^\w]", "", str(text).lower())


def key(r) -> tuple:
    return (r["corpus"], r["part"], r["recording"], r["engine"], r["kind"], r["subkind"],
            plain(r["record"]), plain(r["engine_wrote"]), plain(r["record_context"]))


def found_now() -> pd.DataFrame:
    frames = []
    for kind in KINDS:
        t = pd.read_csv(FINDINGS / "failures" / kind / "candidates.csv", dtype=str, keep_default_na=False)
        frames.append(t.assign(kind=kind, source="candidates"))
    agreed = pd.read_csv(FINDINGS / "failures" / "meaning" / "all-agree.csv", dtype=str, keep_default_na=False)
    frames.append(agreed.assign(kind="meaning", source="all-agree"))
    return pd.concat(frames, ignore_index=True).fillna("")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="Say what would change, and write nothing.")
    args = parser.parse_args()

    old = pd.read_csv(PATH, dtype=str, keep_default_na=False)
    if "not_counted" not in old:
        old["not_counted"] = ""
    now = found_now()

    waiting = defaultdict(list)
    for i, row in now.iterrows():
        waiting[key(row)].append(i)

    update = ["subkind", "start", "end", "record", "engine_wrote", "record_context", "engine_context", "others_right",
              "evidence", "source"]
    taken, changed, gone = set(), 0, 0
    # Times first: where one case is listed twice, each takes the copy nearest its own time.
    for at, row in old.iterrows():
        candidates = waiting.get(key(row), [])
        if not candidates:
            if not row["not_counted"].startswith(GONE):
                old.at[at, "not_counted"] = GONE
                gone += 1
            continue
        best = min(candidates, key=lambda i: abs(float(now.at[i, "start"]) - float(row["start"])))
        candidates.remove(best)
        taken.add(best)
        old.at[at, "not_counted"] = ""
        for column in update:
            if column in now and old.at[at, column] != now.at[best, column]:
                old.at[at, column] = now.at[best, column]
                changed += 1

    seams = now[(now.kind == "skips") & (now.get("at_seam", "") == "True")]
    seam_keys = {key(r) for _, r in seams.iterrows()}

    fresh = now.drop(index=list(taken))
    next_id = old.case.str[1:].astype(int).max() + 1
    added = []
    for _, row in fresh.sort_values(["corpus", "part", "recording", "start", "engine", "kind"]).iterrows():
        added.append({**{c: row.get(c, "") for c in old.columns}, "case": f"f{next_id:05d}", "not_counted": ""})
        next_id += 1
    table = pd.concat([old, pd.DataFrame(added, columns=old.columns)], ignore_index=True).fillna("")

    # Counted once, and not where the cut may be to blame. Neither applies to a case that's gone.
    live = ~table.not_counted.str.startswith(GONE)
    table.loc[live & table.not_counted.isin([SEAM, SAME_SPOT]), "not_counted"] = ""
    at_seam = table.apply(lambda r: key(r) in seam_keys, axis=1)
    table.loc[live & at_seam, "not_counted"] = SEAM
    spot = ["recording", "engine", "start", "end", "record_context", "source"]
    meaning_spots = set(map(tuple, table[live & (table.kind == "meaning")][spot].values))
    same = table.apply(lambda r: r["kind"] == "edits" and tuple(r[c] for c in spot) in meaning_spots, axis=1)
    table.loc[live & same, "not_counted"] = SAME_SPOT

    print(f"{len(old):,} cases before: {gone:,} newly gone, {changed:,} fields updated; {len(added):,} new; {len(table):,} now")
    print(table.not_counted.replace("", "counted").value_counts().to_string())
    new_rows = pd.DataFrame(added)
    if len(new_rows):
        print(new_rows.groupby(["corpus", "engine", "kind"]).size().to_string())
    lost = table[table.not_counted.str.startswith(GONE)]
    if len(lost):
        print("gone, by engine:", lost.groupby(["corpus", "engine"]).size().to_dict())
    if not args.dry_run:
        table.to_csv(PATH, index=False, lineterminator="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

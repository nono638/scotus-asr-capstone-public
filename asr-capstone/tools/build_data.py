"""Build the website's data: two big tables of all the ASR work, and the smaller ones.

    python tools/build_data.py

Writes into site/data/ (not in git; rebuilt from findings/ and the saved line-ups):

- recordings.csv: one row per recording and engine, every data set, the current
  runs only (tools/lineup.py). Error rate on the benchmark rule, counted from the
  same line-up the failure searches use, and how many cases of each kind the
  searches found there.
- errors.csv: one row per case the failure searches list (meaning changes,
  invented words, edits, skips, breakdowns, and the spots where every engine
  disagrees with the reference), with what the AI judge said about it. The
  restarts an engine tidied away (about 80,000) are counted, not listed. Qwen's
  answers are left out while its run is unfinished (build_site.SHOW_QWEN).
- tables-<group>.json: the other CSVs in findings/, a few bundles of them (the
  host allows 511 files a page), each with the line its folder's README gives it.
  Older tables a later run replaced are left out.

The data page (site/data.html, from tools/site_page/data.html) loads these.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
FINDINGS = CAPSTONE / "findings"
OUT = CAPSTONE / "site" / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))

#: The bundles of smaller tables: a plain name, and the folders under findings/ in it.
GROUPS = [
    ("rates", "Error rates", ["corpus", "edacc", "coraal", "earnings22", "harmonise", "flip"]),
    ("failures", "The failure searches", ["failures"]),
    ("judge", "The machine judges", ["judge"]),
    ("engines", "Engines compared word by word", ["crowd"]),
    ("experiments", "Experiments and checks", ["error-model", "parakeet-stall", "experiment-conditioning", ""]),
    ("seven", "The seven-engine study (2017 term)", ["run-"]),
]
#: Left out of the bundles: already in errors.csv or recordings.csv, scored before
#: later fixes, or made by an older search a newer one replaced.
LEAVE_OUT = ["failures/meaning/candidates.csv", "failures/edits/candidates.csv", "failures/skips/candidates.csv",
             "failures/invented/candidates.csv", "failures/breakdown/candidates.csv", "failures/meaning/all-agree.csv",
             "judge/full-v1.csv", "judge/answers-claude-sonnet-5-5-full-v1.csv", "judge/answers-qwen3.8-27b-full-v1.csv",
             # Answers set aside when a case's text changed, and Qwen's while it runs.
             "-superseded.csv", "judge/answers-qwen3.8-27b-full-v1-",
             "harmonise/run-scotus250-parakeet/", "llm-format/", "invented-words/", "/cache/"]
#: Bigger than this goes into a bundle only as its first rows.
MOST_ROWS = 5000


def error_counts(alignment) -> tuple[int, int, int, int]:
    """(substituted, dropped, added, reference words) from one engine's line-up."""
    s = d = i = 0
    for c in alignment.chunks:
        if c.kind == "equal":
            continue
        r, h = c.ref_end - c.ref_start, c.hyp_end - c.hyp_start
        s += min(r, h)
        d += max(0, r - h)
        i += max(0, h - r)
    return s, d, i, len(alignment.reference.tokens)


def recordings_table(cases: pd.DataFrame) -> pd.DataFrame:
    import lineup
    # A spot where every engine differs from the record is kept once, under whichever
    # engine came first (find_meaning_changes.py), so it says nothing about that engine.
    cases = cases[cases.found_by != "every engine differs"]
    # Double-counted spots, skips at a chunk seam, and cases gone after the repair stay on
    # the data page with their reason, and out of the counts (tools/update_cases.py).
    cases = cases[cases.not_counted == ""]
    found = cases.groupby(["corpus", "recording", "engine", "kind"]).size().unstack(fill_value=0)
    judged = cases[cases.sonnet_meaning == "opposite"].groupby(["corpus", "recording", "engine"]).size()
    rows = []
    for corpus in lineup.PARTS:
        index = {}
        if corpus != "scotus":
            for line in (lineup.corpus_root(corpus) / "recordings.jsonl").read_text(encoding="utf-8").splitlines():
                e = json.loads(line)
                index[e["id"]] = e["duration"]
        jobs = lineup.recordings(corpus)
        for n, job in enumerate(jobs, 1):
            lined = lineup.load(job)
            runs = {m.name: m.run_dir.name for m in job["models"]}
            for engine, (_, _, alignment, words) in lined.items():
                s, d, i, words_in_ref = error_counts(alignment)
                seconds = index.get(job["docket"]) or max((w.end or 0) for w in words)
                key = (corpus, job["docket"], engine)
                row = {"corpus": corpus, "part": job["term"], "recording": job["docket"], "engine": engine,
                       "run": runs.get(engine, ""), "minutes": round(seconds / 60, 1),
                       "reference_words": words_in_ref, "error_rate": round(100 * (s + d + i) / words_in_ref, 2),
                       "substituted": s, "dropped": d, "added": i}
                for kind in ["meaning", "invented", "edits", "skips", "breakdown"]:
                    row[f"found_{kind}"] = int(found.loc[key, kind]) if key in found.index and kind in found.columns else 0
                row["judged_opposite"] = int(judged.get(key, 0))
                rows.append(row)
            if n % 50 == 0:
                print(f"  {corpus}: {n} of {len(jobs)}", flush=True)
    return pd.DataFrame(rows)


#: The site takes text files up to 16 MB. With every case judged, Sonnet's reasons
#: alone were 8.4 MB, so errors.csv keeps the first sentence of each (the whole
#: answer is in findings/judge/answers-claude-sonnet-5-5-full-v1.csv), and drops
#: the rule's evidence, which repeats record, engine_wrote and others_right.
REASON_MOST = 140
#: An edit spanning more than this many seconds has lost its place (the longest real one is a few seconds).
LOST_SPAN = 120


def first_sentence(text: str) -> str:
    end = re.search(r"[.!?](\s|$)", text)
    short = text[:end.end()].strip() if end else text
    return short if len(short) <= REASON_MOST else short[:REASON_MOST - 1].rstrip() + "…"


def errors_table() -> pd.DataFrame:
    import build_site
    t = build_site.judged().copy()
    breakdown = pd.read_csv(FINDINGS / "failures" / "breakdown" / "candidates.csv", dtype=str, keep_default_na=False)
    breakdown = breakdown[[c for c in t.columns if c in breakdown.columns]].copy()
    breakdown["case"] = [f"b{n:05d}" for n in range(1, len(breakdown) + 1)]
    breakdown["source"] = "breakdown"
    breakdown["start"] = breakdown.start.astype(float).round(2)
    t = pd.concat([t, breakdown], ignore_index=True)
    out = pd.DataFrame({
        "case": t.case, "corpus": t.corpus, "part": t.part, "recording": t.recording, "engine": t.engine,
        "kind": t.kind, "subkind": t.subkind, "start": t.start, "end": t.end,
        "record": t.record, "engine_wrote": t.engine_wrote,
        "record_context": t.record_context, "engine_context": t.engine_context,
        "others_right": t.others_right,
        "found_by": t.source.replace({"candidates": "failure search", "all-agree": "every engine differs"}),
        "not_counted": t.get("not_counted", pd.Series("", index=t.index)),
        "sonnet_meaning": t.get("s_meaning"), "sonnet_severity": t.get("s_severity"),
        "sonnet_reference_doubt": t.get("s_reference_doubt"),
        "sonnet_reason": t.get("s_reason", pd.Series(dtype=str)).fillna("").map(first_sentence),
        "qwen_meaning": t.get("q_meaning"), "qwen_severity": t.get("q_severity"),
        "sonnet_story_score": t.get("story_example"),
    })
    # A case whose place the search lost (both times 0, or an edit running from the
    # start of the recording to far into it) has no real time: shown as unknown,
    # with no clip and no link to a moment that isn't it.
    span = pd.to_numeric(out.end, errors="coerce") - out.start
    lost = (out.kind != "breakdown") & (((out.start == 0) & (span == 0)) | ((out.kind == "edits") & (span > LOST_SPAN)))
    out.loc[lost, "start"] = float("nan")
    out.loc[lost, "end"] = ""
    print(f"  {int(lost.sum())} rows have no real time: {', '.join(out.case[lost])}", flush=True)
    if not build_site.SHOW_QWEN:
        out = out.drop(columns=["qwen_meaning", "qwen_severity"])
    out["sonnet_severity"] = pd.to_numeric(out.sonnet_severity, errors="coerce").astype("Int64")
    if "qwen_severity" in out:
        out["qwen_severity"] = pd.to_numeric(out.qwen_severity, errors="coerce").astype("Int64")
    out["sonnet_story_score"] = pd.to_numeric(out.sonnet_story_score, errors="coerce").astype("Int64")
    text = [c for c in out.columns if c not in ("sonnet_severity", "qwen_severity", "sonnet_story_score", "start")]
    out[text] = out[text].fillna("")
    return out


def group_of(rel: str) -> str | None:
    if any(x in f"/{rel}" for x in LEAVE_OUT if x.startswith(("/", "-"))) or any(rel.startswith(x) for x in LEAVE_OUT):
        return None
    if "/crowd/" in f"/{rel}":
        return "engines"
    top = rel.split("/")[0] if "/" in rel else ""
    for key, _, folders in GROUPS:
        for f in folders:
            if (f == "" and top == "") or (f and (top == f or (f.endswith("-") and top.startswith(f)))):
                return key
    if top in ("edacc",):
        return "rates"
    return "experiments"


def bundles() -> dict[str, dict]:
    import build_explorer
    out = {key: {"title": title, "tables": []} for key, title, _ in GROUPS}
    for path in sorted(FINDINGS.rglob("*.csv")):
        rel = path.relative_to(FINDINGS).as_posix()
        group = group_of(rel)
        if group is None:
            continue
        try:
            table = pd.read_csv(path, dtype=str, keep_default_na=False)
        except Exception:
            continue
        rows = len(table)
        if rows > MOST_ROWS:
            table = table.head(MOST_ROWS)
        out[group]["tables"].append({"path": rel, "rows": rows, "shown": len(table),
                                     "desc": build_explorer.describe(path),
                                     "csv": table.to_csv(index=False)})
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors = errors_table()
    # Some engines wrote broken characters when they broke down; the host refuses
    # a file holding the replacement character, so it becomes a plain "?".
    # newline="\n": on Windows the default doubles the line endings (\r\r\n), and a
    # browser then reads every row's first column with a line break in front of it.
    (OUT / "errors.csv").write_text(errors.to_csv(index=False, lineterminator="\n").replace("�", "?"),
                                    encoding="utf-8", newline="\n")
    print(f"site/data/errors.csv: {len(errors)} rows, {(OUT / 'errors.csv').stat().st_size / 1e6:.1f} MB", flush=True)
    recordings = recordings_table(errors)
    recordings.to_csv(OUT / "recordings.csv", index=False)
    # A copy in findings/ (small, in git), so the findings notebook can read it on
    # a laptop without the runs.
    recordings.to_csv(FINDINGS / "recordings.csv", index=False)
    print(f"site/data/recordings.csv: {len(recordings)} rows, {(OUT / 'recordings.csv').stat().st_size / 1e6:.1f} MB")
    index = []
    for key, bundle in bundles().items():
        if not bundle["tables"]:
            continue
        path = OUT / f"tables-{key}.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False).replace("�", "?"), encoding="utf-8")
        size = path.stat().st_size / 1e6
        index.append({"key": key, "title": bundle["title"], "file": path.name, "mb": round(size, 1),
                      "tables": [{"path": t["path"], "rows": t["rows"], "shown": t["shown"], "desc": t["desc"]}
                                 for t in bundle["tables"]]})
        print(f"site/data/{path.name}: {len(bundle['tables'])} tables, {size:.1f} MB")
        if size > 15:
            print("  over 15 MB: the host takes at most 16 MB a file")
    (OUT / "tables.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

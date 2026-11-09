"""Ask a local language model what kind of difference each leftover spot is.

`crowd.py` sorts every flagged spot with simple checks. The spots no check
claims are labelled "other". This sends each of those to a model running in
Ollama, with the official words around it and what the machines wrote, and asks
which kinds of difference it is, with a one-sentence reason.

The judge is held to the same terms as a person on the listening page: the same
nine kinds with the same descriptions, and any number of them marked primary
and any number secondary, as many as fit (13 October 2026; before that it had
to pick exactly one). It judges from the text only, never the audio, and is
never asked who is right; that needs the audio, and is the listener's job.

Before trusting it, its answers are compared with labels made by ear
(`flagged-spots-review.md`, step 5).

GPU: Gemma 4 31B needs about 21 GB of the card's 24. The script stops if Ollama
already has a model loaded, and unloads its own when it finishes.

Writes findings/crowd/judge.csv, one row per spot, saved as it goes, so a
stopped run picks up where it left off.

Bench mode (`--bench`, from 13 October 2026) is the comparison that matters for
checking the judge: it labels the listening page's 200 spots with the eight
yes/no questions of labelling-guidelines.md, given the official sentence and
each model's line as the page shows them (speaker names included). Results go to
findings/crowd/judge-bench.csv. Run it once the guidelines are frozen.

Usage:
    python tools/judge_spots.py --pilot 20     # try the first 20, print them
    python tools/judge_spots.py                # all the leftovers
    python tools/judge_spots.py --redo all     # start judge.csv over
    python tools/judge_spots.py --bench <listening.html> --dry-run   # show two prompts
    python tools/judge_spots.py --bench <listening.html>             # judge the bench spots
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
CROWD = CAPSTONE / "findings" / "crowd"
OUT = CROWD / "judge.csv"
OLLAMA = "http://localhost:11434"
LLM = "gemma4:31b"
OPTIONS = {"temperature": 0, "seed": 1, "num_ctx": 4096, "num_predict": 300}
#: The seven models, as named in the columns of hard-passages.csv.
MODELS = ["Whisper", "Qwen3", "Voxtral", "Canary", "Parakeet", "Granite", "Granite Plus"]

#: Word for word the descriptions on the listening page
#: (tools/listening_page/template.html), except "can't tell", since the judge
#: has only the text.
KINDS = {
    "speaker change or overlap": "Two people talking at once, one cutting in on another, or words right where one speaker hands over to the next. Example: a justice says \"Right\" while counsel is still talking.",
    "disfluency": "A stumble in how someone speaks: a repeated word (\"I -- I think\"), a restart (\"the -- to take\"), a word cut off partway, or a filler such as \"well\" or \"you know\". A verbatim record keeps these; machines often drop them.",
    "name or legal term": "A person, place, case name or legal term written differently. Example: Cronic written \"chronic\", comity written \"comedy\", en banc written \"on banc\".",
    "number or citation": "A number, date, statute or subsection written differently. Example: \"3553(e)\" against \"3553 e\", or \"III\" against \"3\".",
    "small word or ending": "A short common word swapped (a/the, is/are, could/can, in/and), or the same word with a different ending (statute/statutes, understand/understood).",
    "not a real difference": "The same words, written another way: spelling, spacing, hyphens, an abbreviation or a writing convention. Example: \"e-mails\" against \"emails\", \"all right\" against \"alright\".",
    "misheard word": "A different word that sounds alike, in clear speech. Example: breadth written \"breath\", relief written \"belief\".",
    "words left out or added": "Whole words on one side only, for none of the reasons above. Example: \"and so forth\" in the record, nothing from the machines.",
    "can't tell": "The text alone isn't enough to say which kind this is.",
}

SYSTEM = (
    "You compare an official Supreme Court transcript with what speech recognition "
    "models wrote, at one spot where they differ. Say what KINDS of difference it is, "
    "the way a careful court reporter would label it. Do not say who is right.\n\n"
    "Mark every kind that fits, and only those. A primary kind is one that describes "
    "this spot; a secondary kind plays a smaller part in it. A spot may have one primary "
    "kind and nothing else, or several of each. Do not add a kind just to have more.\n\n"
    "The kinds:\n"
    + "\n".join(f"- {k}: {v}" for k, v in KINDS.items())
    + '\n\nAnswer with JSON only: {"primary": ["<kind>", ...], "secondary": ["<kind>", ...], '
    '"reason": "<one short sentence>"}'
)


# ---------------------------------------------------------------------------
# Bench mode: the codebook's eight questions on the listening page's spots
# ---------------------------------------------------------------------------

#: labelling-guidelines.md, version 0.2, as the listening page words it.
GUIDE = "0.2"
QUESTIONS = {
    "overlap": ("Overlap or hand-over", "Someone else is speaking during the spot, or a new speaker starts inside the spot or on the word right next to it. A justice saying \"Right\" while counsel is still talking counts; a change of speaker further away doesn't. Judge from the speaker names and the reporter's dashes."),
    "stumble": ("Stumble", "The spot is, or sits right next to, a repeated word (\"I -- I think\"), a restart (\"the -- to take\"), a word cut off partway, or a filler that is part of a stumble (uh, um, well, you know, I mean)."),
    "name": ("Name or legal term", "A person, place, case name, statute name or legal term of art is involved: Cronic, comity, en banc, Blackledge, AEDPA."),
    "number": ("Number or citation", "A number, date, statute, section or subsection is involved: \"3553(e)\", \"III\", \"15 cents\"."),
    "written": ("Same words, written differently", "Read aloud, both sides would sound the same; only spelling, spacing, hyphens, an abbreviation, punctuation or a transcript convention differ: \"e-mails\" and \"emails\", \"all right\" and \"alright\"."),
    "soundalike": ("Sound-alike", "The words differ but sound alike or nearly alike: relief and belief, breadth and breath, \"him to\" and \"into\". Not ticked together with \"written\"."),
    "small": ("Small word or ending", "The difference is in a short common word (a, the, is, are, in, and, of, to, could, can) or a word ending (-s, -ed, -ing, 's)."),
    "oneside": ("Words on one side only", "At least one whole word on one side has no counterpart on the other."),
}
EXTRAS = {
    "none": ("None of these", "You looked, and none of the eight is true."),
    "cant": ("Can't tell", "The text isn't enough to answer."),
}
BENCH_SYSTEM = (
    "You label one spot where an official Supreme Court transcript and seven speech "
    "recognition models differ, the way a careful court reporter would, from the text "
    "alone. The spot is the words in [[double brackets]]; label the spot, not the "
    "sentence around it. Speaker names (in capitals, before a turn) appear only in the "
    "official transcript; no model writes them, so a missing name is never a difference.\n\n"
    "Answer each question about the spot, and list every one that is true. They are not "
    "exclusive; list as many as are true and no more.\n"
    + "\n".join(f"- {k} ({name}): {about}" for k, (name, about) in QUESTIONS.items())
    + "\n\nIf none of them is true, answer only \"none\". If the text isn't enough to "
    "answer, answer only \"cant\". Do not say who is right.\n\n"
    "Borderline cases: doubled words the reporter keeps are \"stumble\" even when the "
    "models dropped them, and also \"oneside\" if whole words are missing. A wrong name "
    "that sounds like the right one is both \"name\" and \"soundalike\". If you would "
    "need to guess, leave it out.\n\n"
    'Answer with JSON only: {"ticks": ["<key>", ...], "reason": "<one short sentence>"}'
)


def page_spots(page: Path) -> list[dict]:
    """The spots built into a listening page (the SPOTS line of its HTML)."""
    for text_line in page.read_text(encoding="utf-8").splitlines():
        if text_line.startswith("const SPOTS = "):
            return json.loads(text_line[len("const SPOTS = "):].rstrip().rstrip(";"))
    raise SystemExit(f"no SPOTS in {page}")


def sentence_text(segments: list[dict]) -> str:
    """The sentence with the spot, as the page shows it: speaker names
    where a turn starts, the spot in [[double brackets]], the context sentences left out."""
    parts = []
    for i, seg in enumerate(segments):
        if seg["r"] == "who":
            following = next((x for x in segments[i + 1:] if x["r"] != "who"), None)
            if following and following["r"] in ("sent", "spot"):
                parts.append(seg["t"].strip())
        elif seg["r"] == "spot":
            parts.append(f"[[{' '.join(seg['t'].split()) or '(nothing)'}]]")
        elif seg["r"] == "sent":
            parts.append(" ".join(seg["t"].split()))
    return " ".join(p for p in parts if p)


def bench_message(spot: dict) -> str:
    models = {"Qwen3": spot["qwen"], **spot["others"]}
    lines = "\n".join(f"- {m}: {sentence_text(segs)}" for m, segs in models.items())
    return (f"Official transcript:\n{sentence_text(spot['official'])}\n\n"
            f"What each model wrote over the same sentence:\n{lines}")


def ask_bench(text: str) -> dict:
    reply = post("/api/chat", {
        "model": LLM, "stream": False, "think": False, "format": "json",
        "keep_alive": "10m", "options": OPTIONS,
        "messages": [{"role": "system", "content": BENCH_SYSTEM}, {"role": "user", "content": text}],
    })
    try:
        answer = json.loads(reply["message"]["content"])
    except json.JSONDecodeError:
        return {"ticks": ["cant"], "reason": "the model did not answer in JSON"}
    if not isinstance(answer, dict):
        answer = {}
    given = answer.get("ticks") or []
    given = [given] if isinstance(given, str) else given
    names = list(dict.fromkeys(str(k).strip().lower() for k in given))
    reason = str(answer.get("reason", "")).strip()
    unknown = [k for k in names if k not in QUESTIONS and k not in EXTRAS]
    if unknown:
        reason += f" [unknown answers dropped: {', '.join(unknown)}]"
    ticks = [k for k in names if k in QUESTIONS]
    # Same rule as the page: a question ticked clears "none" and "can't tell".
    if not ticks:
        ticks = ["cant"] if "cant" in names else ["none"] if "none" in names else []
    if not ticks:
        return {"ticks": ["cant"], "reason": reason + " [no answer given]"}
    return {"ticks": ticks, "reason": reason}


def run_bench(page: Path, dry_run: bool) -> int:
    out = CROWD / "judge-bench.csv"
    spots = page_spots(page)
    if dry_run:
        for spot in spots[:2]:
            print(f"--- {spot['id']}\n{bench_message(spot)}\n")
        return 0
    loaded = json.loads(urllib.request.urlopen(OLLAMA + "/api/ps").read()).get("models")
    if loaded:
        raise SystemExit("STOP: Ollama already has a model loaded. Run 'ollama stop <name>' first.")
    done = set()
    if out.exists():
        done = {r["spot"] for r in csv.DictReader(out.open(encoding="utf-8")) if r["guide"] == GUIDE}
    fields = ["spot", "docket", "clock", "guide", "judge_ticks", "judge_reason"]
    print(f"{len(spots)} bench spots, {len(done)} already judged under version {GUIDE}")
    with out.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if f.tell() == 0:
            writer.writeheader()
        try:
            for spot in spots:
                if spot["id"] in done:
                    continue
                answer = ask_bench(bench_message(spot))
                writer.writerow({"spot": spot["id"], "docket": spot["docket"], "clock": spot["clock"],
                                 "guide": GUIDE, "judge_ticks": "; ".join(answer["ticks"]),
                                 "judge_reason": answer["reason"]})
                f.flush()
        finally:
            post("/api/generate", {"model": LLM, "keep_alive": 0})  # give the card back
    return 0


def leftovers() -> pd.DataFrame:
    """Every spot the checks left as "other", from both lists."""
    against = pd.read_csv(CROWD / "against-the-record.csv", keep_default_na=False)
    hard = pd.read_csv(CROWD / "hard-passages.csv", keep_default_na=False)
    against["list"] = "against"
    hard["list"] = "hard"
    # The models split on these, so the judge sees every model's version.
    # `machines_wrote` stays Qwen3's, as the key the other tools join on.
    hard["machines_wrote"] = hard["Qwen3"]
    hard["versions"] = hard.apply(
        lambda r: "\n".join(f"- {m}: {r[m] or '(nothing)'}" for m in MODELS), axis=1)
    against["versions"] = ""
    columns = ["list", "docket", "clock", "record", "machines_wrote", "versions",
               "context_before", "context_after", "what_happened"]
    both = pd.concat([against[columns], hard[columns]], ignore_index=True)
    return both[both["what_happened"] == "other"].reset_index(drop=True)


def message(row) -> str:
    official = f"{row.context_before} [[{row.record}]] {row.context_after}".strip()
    if row.versions:
        return (f"Official transcript, the spot in [[double brackets]]:\n{official}\n\n"
                f"The models disagree here. What each wrote at the spot:\n{row.versions}")
    machines = row.machines_wrote or "(nothing)"
    return (f"Official transcript, the spot in [[double brackets]]:\n{official}\n\n"
            f"What the machines wrote at the spot:\n{machines}")


def post(path: str, body: dict) -> dict:
    request = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def ask(text: str) -> dict:
    reply = post("/api/chat", {
        "model": LLM, "stream": False, "think": False, "format": "json",
        "keep_alive": "10m", "options": OPTIONS,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
    })
    try:
        answer = json.loads(reply["message"]["content"])
    except json.JSONDecodeError:
        return {"primary": ["can't tell"], "secondary": [], "reason": "the model did not answer in JSON"}
    if not isinstance(answer, dict):
        answer = {}
    reason = str(answer.get("reason", "")).strip()

    def kinds(field: str) -> tuple[list[str], list[str]]:
        given = answer.get(field) or []
        given = [given] if isinstance(given, str) else given
        names = [str(k).strip().lower() for k in given]
        return [k for k in dict.fromkeys(names) if k in KINDS], [k for k in names if k not in KINDS]

    primary, unknown_p = kinds("primary")
    secondary, unknown_s = kinds("secondary")
    secondary = [k for k in secondary if k not in primary]
    unknown = unknown_p + unknown_s
    if unknown:
        reason += f" [unknown kinds dropped: {', '.join(unknown)}]"
    if not primary:
        return {"primary": ["can't tell"], "secondary": secondary,
                "reason": reason + " [no primary kind given]"}
    return {"primary": primary, "secondary": secondary, "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=int, help="judge only the first N and print them")
    parser.add_argument("--redo", choices=["against", "hard", "all"],
                        help="drop that list's answers (or all of them) from judge.csv and judge again")
    parser.add_argument("--bench", type=Path,
                        help="a built listening page: judge its spots with the codebook's questions, "
                             "into judge-bench.csv")
    parser.add_argument("--dry-run", action="store_true", help="with --bench, print two prompts and stop")
    args = parser.parse_args()
    if args.bench:
        return run_bench(args.bench, args.dry_run)

    loaded = json.loads(urllib.request.urlopen(OLLAMA + "/api/ps").read()).get("models")
    if loaded:
        raise SystemExit("STOP: Ollama already has a model loaded. Run 'ollama stop <name>' first.")

    rows = leftovers()
    if args.pilot:
        rows = rows.head(args.pilot)
    if args.redo == "all" and OUT.exists() and not args.pilot:
        OUT.unlink()
    elif args.redo and OUT.exists() and not args.pilot:
        kept = pd.read_csv(OUT, keep_default_na=False)
        kept[kept["list"] != args.redo].to_csv(OUT, index=False)
    done = set()
    if OUT.exists() and not args.pilot:
        done = {(r["docket"], r["clock"], r["record"], r["machines_wrote"])
                for r in csv.DictReader(OUT.open(encoding="utf-8"))}
    print(f"{len(rows)} leftover spots, {len(done)} already judged")

    # Several kinds go in one cell, separated by "; ".
    fields = ["list", "docket", "clock", "record", "machines_wrote",
              "judge_primary", "judge_secondary", "judge_reason"]
    target = OUT if not args.pilot else OUT.with_name("judge-pilot.csv")
    new_file = not target.exists() or args.pilot
    started = time.time()
    with target.open("w" if args.pilot else "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        try:
            for n, row in enumerate(rows.itertuples(), 1):
                key = (row.docket, row.clock, row.record, row.machines_wrote)
                if key in done:
                    continue
                answer = ask(message(row))
                writer.writerow({"list": row.list, "docket": row.docket, "clock": row.clock,
                                 "record": row.record, "machines_wrote": row.machines_wrote,
                                 "judge_primary": "; ".join(answer["primary"]),
                                 "judge_secondary": "; ".join(answer["secondary"]),
                                 "judge_reason": answer["reason"]})
                f.flush()
                if args.pilot:
                    also = f" | secondary: {', '.join(answer['secondary'])}" if answer["secondary"] else ""
                    print(f"[{row.record}] -> [{row.machines_wrote}]\n"
                          f"    primary: {', '.join(answer['primary'])}{also}\n    {answer['reason']}")
                elif n % 50 == 0:
                    rate = (time.time() - started) / n
                    print(f"  {n}/{len(rows)}  {rate:.1f} s each", flush=True)
        finally:
            post("/api/generate", {"model": LLM, "keep_alive": 0})  # give the card back
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

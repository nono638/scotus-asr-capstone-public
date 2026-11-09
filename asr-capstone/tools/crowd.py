"""Several sets of ears on the same audio: where they agree, where they all miss,
and whether a vote among them beats the best one.

Any two or more models, on any corpus the pipeline has run over. The Supreme
Court study used seven, and they are the default; any other combination is a
model-set file, a runs folder, or a list given by hand (see "Choosing the
models" below).

For every word of the reference, this asks each model whether it wrote that
word. That gives three things:

  1. How many of the models heard each word. A word nobody heard is a floor:
     no way of combining these models can recover it.
  2. Whether the models make the same mistakes. If they do, seven models are
     fewer than seven independent listeners.
  3. A vote. The models are lined up against each other - not against the
     reference, which would be cheating - and each position takes the most
     common word. The voted transcript is then scored like a model.

It also writes two lists for a person to listen to:

  hard-passages.csv       stretches nobody heard, or the models split over
  against-the-record.csv  stretches where all but one model wrote the same thing
                          and the reference says something else, in both
                          directions: words the reference has that the machines
                          agree are not there, and words the machines agree on
                          that the reference does not have

Each spot in both lists gets two labels (see `flagged-spots-review.md`):

  what_happened  overlap, disfluency, name or legal term, number or citation,
                 small word or ending, not a real difference, or other - every
                 check runs, all tags are kept in `tags`, and the main label is
                 picked in the order of PRIORITY
  machines       how the models behaved: most have it, a few have it, all wrote
                 the same other thing, and so on (`models_right` is the count)

The thresholds are written in terms of the number of models, n, and give the
study's numbers when n is 7: "against" means all but one agree (6 of 7, and
never fewer than 2); "most" means a majority (4 of 7); "nobody" means at most
one got it (none, with fewer than four models).

Some checks lean on how a court transcript is written. A "name" is a capitalised
word the reference never writes in lower case, so it is skipped for a reference
with no lower case at all (EdAcc is all capitals). The reporter's dash marks one
speaker cutting in on another; `interruptions.csv` is written only when the
references contain dashes. The legal-terms list is harmless elsewhere.

Everything is compared under the `standard` rule (the benchmark one: no
punctuation or case) with the harmonise fixes on, so the lists do not fill up
with differences nobody could hear - "3553(e)" against "3553E", "Vogt's"
against "votes". The question here is whether a model heard the word. Granite
Plus cannot punctuate at all, so the verbatim rule would count it wrong on
every comma.

Choosing the models (scotus_asr/model_sets.py):

    python tools/crowd.py                          # the Supreme Court's seven
    python tools/crowd.py --set my-models.yaml     # a model-set file
    python tools/crowd.py --runs-dir <asr_corpora>/edacc/runs
                                                   # every engine found there
    python tools/crowd.py --runs-dir <asr_corpora>/edacc/runs --models qwen3,whisper
    python tools/crowd.py --model Qwen3=<runs>/run-a --model Whisper=<runs>/run-b

Only recordings every chosen model transcribed are compared. `runs-used.csv` in
the output folder records exactly which runs went in.

No GPU. Writes small CSVs - by default to findings/crowd/ for the seven, or
beside the runs folder for one found by --runs-dir. Takes a few minutes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jiwer
import pandas as pd
import yaml

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

from scotus_asr.model_sets import ModelRun, ModelSet, discover, from_pair, load_set  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.metrics import drop_ignored  # noqa: E402
from scotus_asr.scoring.normalize import normalize_tokens  # noqa: E402
from scotus_asr.scoring.pairs import _clock, _turn_at, _turn_lookup  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402

#: The Supreme Court study's seven models and the runs its published figures
#: come from (findings/README.md). The default set.
DEFAULT_SET = CAPSTONE / "pipeline" / "config" / "model-sets" / "scotus-seven.yaml"

# Kept for the tools that import them (build_listening_page.py, llm_format.py),
# which work on the seven. Read from the file without touching the runs, so
# importing this module costs nothing.
_SEVEN = yaml.safe_load(DEFAULT_SET.read_text(encoding="utf-8"))
RUNS: dict[str, str] = dict(_SEVEN["models"])
MODELS = list(RUNS)
PIVOT = _SEVEN["pivot"]


def seven(runs_dir: Path | None = None) -> ModelSet:
    """The Supreme Court's seven, optionally from another copy of the runs."""
    chosen = load_set(DEFAULT_SET)
    if runs_dir is not None:
        chosen = ModelSet([ModelRun(m.name, Path(runs_dir) / m.run_dir.name, m.engine)
                           for m in chosen.models], pivot=chosen.pivot, out=chosen.out,
                          description=chosen.description)
    return chosen


NUMBER_NAMES = "zero one two three four five six seven eight nine ten eleven twelve".split()


def thresholds(n: int) -> tuple[int, int, int]:
    """(majority, against, nobody) for n models; (4, 6, 1) for seven."""
    return n // 2 + 1, max(2, n - 1), 1 if n >= 4 else 0


NOTHING = ""  # what a model "wrote" where it left a word out

FILLERS = {"uh", "um", "mm", "hmm", "mhm", "oh", "ah", "er", "huh"}
#: Short replies a second speaker makes over the first - "right", "yeah".
REPLIES = {"yeah", "yes", "right", "okay", "all", "well", "no", "sure", "so", "i", "see", "mhm"}
#: Capitalised words that are not names.
NOT_NAMES = {"I", "I'm", "I'll", "I've", "I'd", "Mr.", "Ms.", "Justice", "Chief", "Court", "Your", "Honor"}
NUMBER_WORDS = set(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty "
    "sixty seventy eighty ninety hundred thousand million billion first second third "
    "fourth fifth sixth seventh eighth ninth tenth oh point percent".split()
)


# ---------------------------------------------------------------------------
# Loading and lining up
# ---------------------------------------------------------------------------

def what_each_wrote(alignment) -> list[str]:
    """For each official token, the token this model wrote there.

    The official token itself where the model got it right, the model's own
    token where it wrote something else, and NOTHING where it wrote nothing.
    Words the model added that were never said have no official position, so
    they are not in this list (they are counted separately).
    """
    ref = alignment.reference.tokens
    hyp = alignment.hypothesis.tokens
    wrote = [NOTHING] * len(ref)
    for chunk in alignment.chunks:
        if chunk.kind == "equal":
            for i in range(chunk.ref_start, chunk.ref_end):
                wrote[i] = ref[i]
        elif chunk.kind == "substitute":
            # jiwer substitutions are always one for one.
            for k, i in enumerate(range(chunk.ref_start, chunk.ref_end)):
                wrote[i] = hyp[chunk.hyp_start + k]
    return wrote


def token_times(alignment, words) -> list[float | None]:
    """A time in the audio for each official token, from this model's timings.

    Tokens the model left out get the time of the last token before them that
    it did write, which is where to start listening.
    """
    ref_len = len(alignment.reference.tokens)
    hyp_source = alignment.hypothesis.source_index
    times: list[float | None] = [None] * ref_len
    for chunk in alignment.chunks:
        if chunk.kind in ("equal", "substitute"):
            for k, i in enumerate(range(chunk.ref_start, chunk.ref_end)):
                times[i] = words[hyp_source[chunk.hyp_start + k]].start
    last = None
    for i in range(ref_len):
        if times[i] is None:
            times[i] = last
        else:
            last = times[i]
    return times


def load_case(runs_dir: Path | None, docket: str, models: ModelSet | None = None) -> dict:
    """Line every model up against the reference for one recording.

    Args:
        runs_dir: Where the seven Supreme Court runs are, when `models` is not
            given - the form the older tools call it in.
        docket: The recording.
        models: The models to line up. The seven when not given.
    """
    models = models or seven(runs_dir)
    names = models.names
    case: dict = {"docket": docket, "wrote": {}, "hyp_tokens": {}, "counts": {}, "added": {}}
    reference_tokens = None

    # Read everything first. The harmonise fixes join "e mails" into "emails"
    # when either form is used, and the reference has to be joined the same way
    # for every model, so the word list that decides it is shared.
    loaded = {}
    for run in models.models:
        ref_file = run.reference_file(docket)
        transcript = Transcript.from_dict(json.loads(ref_file.read_text(encoding="utf-8")))
        # Words inside a stretch the reference leaves out of scoring (EdAcc's
        # read-aloud passages) are dropped, exactly as the scoring stage does;
        # kept, they would all count as words the models added.
        words = drop_ignored(_load_asr_result(run.asr_file(docket)).words, transcript.ignore)
        loaded[run.name] = (transcript, words)
    first_transcript = loaded[names[0]][0]
    vocabulary = set(normalize_tokens(first_transcript.full_text(include_speakers=False).split(),
                                      "standard", harmonise=True).tokens)
    for model in names:
        vocabulary |= set(normalize_tokens([w.text for w in loaded[model][1]],
                                           "standard", harmonise=True).tokens)

    for model in names:
        # Each run keeps its own copy of the parsed reference. They should be
        # identical; checking costs nothing and a mismatch would void the table.
        transcript, words = loaded[model]
        reference_words = transcript.full_text(include_speakers=False).split()
        alignment = align_words(reference_words, [w.text for w in words], "standard",
                                harmonise=True, vocabulary=vocabulary)

        if reference_tokens is None:
            reference_tokens = alignment.reference.tokens
            case["reference_words"] = reference_words
            case["ref_source"] = alignment.reference.source_index
            case["turns"] = _turn_lookup(transcript)
        elif alignment.reference.tokens != reference_tokens:
            raise ValueError(f"{docket}: {model}'s copy of the reference differs")

        case["wrote"][model] = what_each_wrote(alignment)
        # Words this model wrote that have no official word against them, keyed
        # by the gap they fall in (the official token they come just before).
        case["added"][model] = {
            chunk.ref_start: " ".join(alignment.hypothesis.tokens[chunk.hyp_start:chunk.hyp_end])
            for chunk in alignment.chunks if chunk.kind == "insert"
        }
        case["hyp_tokens"][model] = alignment.hypothesis.tokens
        case["counts"][model] = (alignment.substitutions, alignment.deletions, alignment.insertions)
        if model == models.pivot:
            case["times"] = token_times(alignment, words)

    case["reference"] = reference_tokens
    case["vocabulary"] = vocabulary
    return case


# ---------------------------------------------------------------------------
# The vote
# ---------------------------------------------------------------------------

def vote(hyp_tokens: dict[str, list[str]], pivot: str) -> list[str]:
    """Combine the models' transcripts without looking at the reference.

    Every model is aligned against the pivot model's words. At each of the
    pivot's positions the most common word wins, and a tie keeps the pivot's.
    A word the pivot left out is added only if a majority of all models wrote
    the same thing in that gap. This is a cut-down ROVER, the usual way of
    combining recognisers.
    """
    base = hyp_tokens[pivot]
    others = [m for m in hyp_tokens if m != pivot]
    majority = len(hyp_tokens) // 2 + 1

    # candidates[i] = what each model wrote at pivot position i
    candidates = [[token] for token in base]
    # gaps[i] = what each model added just before pivot position i
    gaps: list[Counter] = [Counter() for _ in range(len(base) + 1)]

    for model in others:
        out = jiwer.process_words(" ".join(base), " ".join(hyp_tokens[model]) or "<empty>")
        theirs = hyp_tokens[model]
        written = [NOTHING] * len(base)
        for chunk in out.alignments[0]:
            if chunk.type in ("equal", "substitute"):
                for k in range(chunk.ref_end_idx - chunk.ref_start_idx):
                    written[chunk.ref_start_idx + k] = theirs[chunk.hyp_start_idx + k]
            elif chunk.type == "insert":
                added = " ".join(theirs[chunk.hyp_start_idx:chunk.hyp_end_idx])
                gaps[chunk.ref_start_idx][added] += 1
        for i, token in enumerate(written):
            candidates[i].append(token)

    voted: list[str] = []
    for i in range(len(base) + 1):
        if gaps[i]:
            added, count = gaps[i].most_common(1)[0]
            if count >= majority:
                voted.extend(added.split())
        if i == len(base):
            break
        tally = Counter(candidates[i])
        best = max(tally.values())
        winners = [t for t, c in tally.items() if c == best]
        winner = base[i] if base[i] in winners else winners[0]
        if winner != NOTHING:
            voted.append(winner)
    return voted


def score_tokens(reference: list[str], hypothesis: list[str]) -> tuple[int, int, int, int]:
    """Substitutions, deletions, insertions and reference length."""
    out = jiwer.process_words(" ".join(reference), " ".join(hypothesis) or "<empty>")
    return out.substitutions, out.deletions, out.insertions, len(reference)


# ---------------------------------------------------------------------------
# Sorting the hard passages
# ---------------------------------------------------------------------------

def kind_of_position(wrote_here: list[str], right: str) -> str:
    """What kind of position this is, from what the models wrote there.

    With n models (the numbers in brackets are for seven):

    against  all but one wrote the same wrong thing, or all left it out (6+)
    nobody   at most one got it right, and they did not agree on an
             alternative (0-1; just 0 with fewer than four models)
    split    some got it right, but fewer than a majority (2-3)
    easy     a majority got it right (4+)
    """
    majority, against, nobody = thresholds(len(wrote_here))
    heard = sum(1 for w in wrote_here if w == right)
    wrong = Counter(w for w in wrote_here if w != right)
    if wrong and wrong.most_common(1)[0][1] >= against:
        return "against"
    if heard <= nobody:
        return "nobody"
    if heard < majority:
        return "split"
    return "easy"


def stretches(kinds: list[str], wanted: set[str]) -> list[tuple[int, int]]:
    """Runs of consecutive positions whose kind is in `wanted`, as (start, end)."""
    runs, start = [], None
    for i, kind in enumerate(kinds + ["easy"]):
        if kind in wanted and start is None:
            start = i
        elif kind not in wanted and start is not None:
            runs.append((start, i))
            start = None
    return runs


def strip_ending(word: str) -> str:
    """The word without a plural or tense ending, for comparing two forms."""
    for ending in ("ing", "es", "ed", "s", "d"):
        if word.endswith(ending) and len(word) > len(ending) + 2:
            return word[: -len(ending)]
    return word


def can_spot_names(reference_words: list[str]) -> bool:
    """Whether the reference is written in ordinary case, so a capital means something.

    The name check asks whether a capitalised word is ever written in lower case.
    An all-capitals reference (EdAcc) cannot answer that - and one stray lower-case
    word in it (a Vietnamese place name in EdAcc's C60) must not switch the check on
    and turn every word into a "name". So most words have to have lower case in them.
    """
    if not reference_words:
        return False
    with_lower = sum(1 for w in reference_words if any(c.islower() for c in w))
    return with_lower / len(reference_words) >= 0.2


def looks_like_a_name(original: str, lower_words: set[str]) -> bool:
    """Whether the record's text has a capitalised word that never appears in
    lower case anywhere else in the same argument - "Printz", not "No"."""
    for word in original.split():
        bare = word.strip(".,?!;:-'\"")
        if bare[:1].isupper() and bare not in NOT_NAMES and bare.lower() not in lower_words:
            return True
    return False


#: Legal terms and case names the models are known to mishear (see the review).
LEGAL_TERMS = set(
    "en banc certiorari cert amicus amici habeas mens rea novo curiam res judicata voir "
    "dire sua sponte qui tam rem personam nunc tunc stare decisis vires ex parte facto "
    "prima facie mandamus estoppel laches comity tolled tolling vacatur preemption "
    "printz chevron auer cronic schor".split()
)
#: Short, common words. A difference made only of these is a "small word".
FUNCTION_WORDS = set(
    "a an the and or but in on at to of for with by from as is are was were be been "
    "being have has had do does did can could will would shall should may might must "
    "that this these those it its i you he she we they me him her us them my your our "
    "their not no so if then there here what which who when where why how just also "
    "very too all any some one".split()
)
#: Words people say to hold the floor or react, rather than to say something.
DISCOURSE = set("well so now okay right yeah yes oh see all sure no".split())
#: Backchannels after the harmonise fixes ("uh-huh", "mm-hmm" and so on).
BACKCHANNELS = {"uhhuh", "mmmm", "uhuh"}

#: The order a spot's main label is picked in. Every check runs on every spot and
#: all the tags are kept; this only decides which one names the spot.
PRIORITY = [
    "not a real difference",
    "speaker change or overlap",
    "disfluency",
    "name or legal term",
    "number or citation",
    "small word or ending",
]


def same_word_new_ending(a: str, b: str) -> bool:
    """"friend"/"friends", "define"/"defined", "jurisdiction"/"jurisdictional"."""
    short, long = sorted((a, b), key=len)
    return len(short) >= 3 and long.startswith(short) and 0 < len(long) - len(short) <= 3


def what_happened(record: list[str], machines: list[str], before: list[str], after: list[str],
                  original: str, lower_words: set[str], turn_nearby: bool,
                  turn_crossed: bool, dash_after: bool) -> tuple[str, list[str]]:
    """What kind of difference this is, judged from the text.

    Returns the main label and every tag that applied. `record` and `machines`
    are the two sides' tokens (one may be empty). `before` and `after` are the
    official tokens either side. `turn_nearby` says the official transcript
    changes speaker within three words; `turn_crossed` says it changes speaker
    inside the stretch. `dash_after` says the official text has a dash right
    after the stretch, which is how a restart is written.
    """
    tags = []
    present = record or machines
    one_side = not record or not machines

    # 1. The same letters, only spaced differently, or "quote" said aloud where
    #    the record has quotation marks: nothing that changes what was said.
    if record and machines and re.sub(r"[^a-z0-9]", "", "".join(record)) == \
            re.sub(r"[^a-z0-9]", "", "".join(machines)):
        tags.append("not a real difference")
    if one_side and set(present) <= {"quote", "unquote", "end"} and set(present) & {"quote", "unquote"}:
        tags.append("not a real difference")

    # 2. Two people at once, or the edge of a turn. A word written differently
    #    near a speaker change is usually just misheard, so with words on both
    #    sides the stretch has to cross the change itself.
    if (one_side and turn_nearby) or turn_crossed or set(present) <= BACKCHANNELS:
        tags.append("speaker change or overlap")

    # 3. Disfluency: a repeat, a cut-off word, a restart, a filler-like word.
    n = len(present)
    repeat = one_side and (present == after[:n] or present == before[-n:])
    cut_off = (len(present) == 1 and after and after[0] != present[0]
               and after[0].startswith(present[0]))
    restart = one_side and dash_after and n <= 4
    discourse = one_side and set(present) <= DISCOURSE
    if repeat or cut_off or restart or discourse:
        tags.append("disfluency")

    # 4. A name or a legal term.
    if (record and looks_like_a_name(original, lower_words)) or (set(record + machines) & LEGAL_TERMS):
        tags.append("name or legal term")

    # 5. Numbers, citations and subsection letters.
    both = record + machines
    if any(ch.isdigit() for ch in "".join(both)) or (set(both) & NUMBER_WORDS) \
            or any(len(w) == 1 and w not in ("a", "i") for w in both):
        tags.append("number or citation")

    # 6. Only small common words, or the same word with a different ending.
    small = (len(record) == len(machines) == 1
             and (same_word_new_ending(record[0], machines[0])
                  or (record[0] in FUNCTION_WORDS and machines[0] in FUNCTION_WORDS)))
    if small or (one_side and set(present) <= FUNCTION_WORDS):
        tags.append("small word or ending")

    main = next((label for label in PRIORITY if label in tags), "other")
    return main, tags


def what_the_machines_did(right: int, agree: int, n: int = 7) -> str:
    """How the n models behaved at a spot.

    `right` is how many matched the reference. `agree` is how many wrote the
    same other thing (leaving the words out counts as a thing).
    """
    majority = thresholds(n)[0]
    if right >= majority:
        return "most models have it"
    if right >= 1:
        return "a few models have it"
    if agree == n:
        everyone = "both" if n == 2 else f"all {NUMBER_NAMES[n] if n < len(NUMBER_NAMES) else n}"
        return f"{everyone} wrote the same other thing"
    if agree >= majority:
        return "most agree on something else"
    return "no model has it, and they disagree"


def near_interruption(reference_words: list[str], word_index: int) -> bool:
    """Whether a dash - the reporter's mark for one speaker cutting in on
    another - sits within two words of this one."""
    lo, hi = max(0, word_index - 2), min(len(reference_words), word_index + 3)
    return any(w in ("-", "--") or w.endswith("--") or w.startswith("--")
               for w in reference_words[lo:hi])


# ---------------------------------------------------------------------------

def choose_models(args: argparse.Namespace) -> ModelSet:
    """The model set the command line asks for, most specific first."""
    if args.model:
        runs = [from_pair(text) for text in args.model]
        return ModelSet(runs, pivot=args.pivot or "", description="models given by hand")
    if args.runs_dir:
        names = [n.strip() for n in args.models.split(",")] if args.models else None
        return ModelSet(discover(args.runs_dir, names), pivot=args.pivot or "",
                        out=args.runs_dir.parent / "crowd",
                        description=f"every engine found in {args.runs_dir}")
    chosen = load_set(args.set or DEFAULT_SET)
    if args.pivot:
        chosen.pivot = args.pivot
        chosen.__post_init__()
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", type=Path,
                        help="a model-set file (default: the Supreme Court's seven)")
    parser.add_argument("--runs-dir", type=Path,
                        help="use every engine found in this runs folder instead")
    parser.add_argument("--models", help="with --runs-dir: only these engines, comma-separated "
                                         "(a prefix is enough: qwen3,whisper)")
    parser.add_argument("--model", action="append", metavar="NAME=RUN",
                        help="a model by hand: its name and its run folder. Repeat.")
    parser.add_argument("--pivot", help="the model the vote lines the others up against "
                                        "(default: the set's, or the first model)")
    parser.add_argument("--out", type=Path, help="where to write the tables")
    args = parser.parse_args()

    chosen = choose_models(args)
    names = chosen.names
    n = len(names)
    majority, against_count, _ = thresholds(n)
    out = args.out or chosen.out
    if out is None:
        raise SystemExit("Say where the tables go with --out.")
    out.mkdir(parents=True, exist_ok=True)

    recordings, missing = chosen.shared_recordings()
    print(f"{chosen.description or 'Comparing'}: {', '.join(names)} (pivot {chosen.pivot})")
    if missing:
        left_out = set().union(*missing.values())
        counts = ", ".join(f"{m.name} {len(m.recordings())}" for m in chosen.models)
        print(f"  {len(left_out)} recording(s) left out because not every model has them "
              f"(recordings per model: {counts})")
    if not recordings:
        raise SystemExit("No recording was transcribed by every model.")
    pd.DataFrame([
        {"model": m.name, "engine": m.engine, "run": str(m.run_dir),
         "recordings_in_run": len(m.recordings()), "recordings_compared": len(recordings),
         "pivot": m.name == chosen.pivot}
        for m in chosen.models
    ]).to_csv(out / "runs-used.csv", index=False)

    heard_by = Counter()                 # how many models heard each word
    misses = {m: 0 for m in names}       # reference words each model got wrong
    lone_right = {m: 0 for m in names}   # right where fewer than a majority were
    both_miss = Counter()                # (a, b) -> words both got wrong
    totals = {m: [0, 0, 0] for m in names}
    vote_totals = {m: [0, 0, 0] for m in names}  # one vote per choice of pivot
    reference_total = 0
    hard_rows, against_rows = [], []
    near_dash = Counter()   # kind of position -> how many sit near a dash
    kind_total = Counter()
    dashes_seen = False

    for docket in recordings:
        case = load_case(None, docket, chosen)
        reference = case["reference"]
        reference_total += len(reference)

        lower_words = {w.strip(".,?!;:-'\"") for w in case["reference_words"] if w.islower()}
        names_possible = can_spot_names(case["reference_words"])
        dashes_seen = dashes_seen or any(
            w in ("-", "--") or w.endswith("--") or w.startswith("--")
            for w in case["reference_words"])
        turn_starts = {start for start, *_ in case["turns"] if start > 0}

        def crosses_turn(first_word: int, last_word: int) -> bool:
            return any(first_word <= t <= last_word for t in turn_starts)

        kinds = []
        for i, right in enumerate(reference):
            wrote_here = [case["wrote"][m][i] for m in names]
            got = [w == right for w in wrote_here]
            heard_by[sum(got)] += 1
            if sum(got) < majority:
                for m, ok in zip(names, got):
                    if ok:
                        lone_right[m] += 1
            for a, ok_a in zip(names, got):
                if not ok_a:
                    misses[a] += 1
                    for b, ok_b in zip(names, got):
                        if b != a and not ok_b:
                            both_miss[(a, b)] += 1
            kind = kind_of_position(wrote_here, right)
            kinds.append(kind)
            kind_total[kind] += 1
            if near_interruption(case["reference_words"], case["ref_source"][i]):
                near_dash[kind] += 1

        for m in names:
            for k in range(3):
                totals[m][k] += case["counts"][m][k]

        for pivot in names:
            s, d, ins, _ = score_tokens(reference, vote(case["hyp_tokens"], pivot))
            vote_totals[pivot][0] += s
            vote_totals[pivot][1] += d
            vote_totals[pivot][2] += ins

        def where(start: int) -> dict:
            source = case["ref_source"][start]
            speaker, page, line = _turn_at(case["turns"], source)
            return {
                "docket": docket,
                "clock": _clock(case["times"][start]),
                "speaker": speaker,
                "turn_starts_page": page,
                "turn_starts_line": line,
            }

        def record_words(start: int, end: int) -> str:
            first, last = case["ref_source"][start], case["ref_source"][end - 1]
            return " ".join(case["reference_words"][first:last + 1])

        rw = case["reference_words"]

        def labels(start: int, end: int, record: list[str], machines: list[str],
                   right: int, agree: int) -> dict:
            """The two labels for a spot: what happened, and what the machines did."""
            first = case["ref_source"][min(start, len(reference) - 1)]
            last = case["ref_source"][end - 1] if end > start else first
            turn_nearby = any(first - 3 <= t <= last + 3 for t in turn_starts)
            turn_crossed = end > start and any(first < t <= last for t in turn_starts)
            following = rw[last + 1] if end > start and last + 1 < len(rw) else ""
            dash_after = end > start and (rw[last].endswith("-") or following.startswith("-"))
            main, tags = what_happened(
                record, machines, reference[max(0, start - 4):start], reference[end:end + 4],
                record_words(start, end) if end > start and names_possible else "",
                lower_words, turn_nearby, turn_crossed, dash_after,
            )
            # Ten reference words either side, so a spot can be read (or judged)
            # without loading the whole recording again.
            after_from = last + 1 if end > start else first
            return {"what_happened": main, "tags": "; ".join(tags), "models_right": right,
                    "machines": what_the_machines_did(right, agree, n),
                    "context_before": " ".join(rw[max(0, first - 10):first]),
                    "context_after": " ".join(rw[after_from:after_from + 10])}

        def right_and_agree(start: int, end: int) -> tuple[int, int, list[str]]:
            """How many models got the stretch, how many agree on one other
            version of it, and that version."""
            versions = [tuple(case["wrote"][m][start:end]) for m in names]
            right = sum(1 for v in versions if list(v) == reference[start:end])
            wrong = Counter(v for v in versions if list(v) != reference[start:end])
            if not wrong:
                return right, 0, []
            version, agree = wrong.most_common(1)[0]
            return right, agree, [w for w in version if w]

        for start, end in stretches(kinds, {"nobody", "split"}):
            if end - start < 3:
                continue
            row = where(start)
            row["words"] = end - start
            row["kind"] = "nobody" if "nobody" in kinds[start:end] else "split"
            row["near_interruption"] = any(
                near_interruption(case["reference_words"], case["ref_source"][i])
                for i in range(start, end)
            )
            row["record"] = record_words(start, end)
            right, agree, version = right_and_agree(start, end)
            row.update(labels(start, end, reference[start:end], version, right, agree))
            for m in names:
                row[m] = " ".join(w for w in case["wrote"][m][start:end] if w)
            hard_rows.append(row)

        for start, end in stretches(kinds, {"against"}):
            machines = []
            for i in range(start, end):
                wrote_here = [case["wrote"][m][i] for m in names]
                common = Counter(w for w in wrote_here if w != reference[i]).most_common(1)[0][0]
                machines.append(common)
            row = where(start)
            row["words"] = end - start
            row["record"] = record_words(start, end)
            row["record_normalised"] = " ".join(reference[start:end])
            row["machines_wrote"] = " ".join(w for w in machines if w)
            row["direction"] = "record has it, machines do not"
            first, last = case["ref_source"][start], case["ref_source"][end - 1]
            row["crosses_turn"] = crosses_turn(first, last)
            row["near_interruption"] = any(
                near_interruption(case["reference_words"], case["ref_source"][i])
                for i in range(start, end)
            )
            right, agree, _ = right_and_agree(start, end)
            row.update(labels(start, end, reference[start:end],
                              row["machines_wrote"].split(), right, agree))
            against_rows.append(row)

        # The other direction: all but one model wrote the same words in the
        # same gap of the reference. Gaps are matched exactly, so a model that
        # placed the words one token over is not counted - a lower bound.
        gaps = Counter()
        for m in names:
            for gap, text in case["added"][m].items():
                gaps[(gap, text)] += 1
        for (gap, text), count in sorted(gaps.items()):
            if count < against_count:
                continue
            row = where(min(gap, len(reference) - 1))
            row["words"] = len(text.split())
            row["record"] = ""
            row["record_normalised"] = ""
            row["machines_wrote"] = text
            row["direction"] = "machines agree, record does not have it"
            row["crosses_turn"] = False
            row["near_interruption"] = near_interruption(
                case["reference_words"], case["ref_source"][min(gap, len(reference) - 1)]
            )
            # Here "right" means a model that did not add the words.
            row.update(labels(gap, gap, [], text.split(), n - count, count))
            against_rows.append(row)

        print(f"  {docket}: {len(reference)} words")

    # --- 1. how many heard each word -------------------------------------
    heard = pd.DataFrame(
        {"heard_by": range(n + 1), "words": [heard_by[k] for k in range(n + 1)]}
    )
    heard["share"] = (heard.words / reference_total).round(5)
    heard.to_csv(out / "heard-by.csv", index=False)

    # --- each model alone, and the vote with each pivot ------------------
    rows = []
    for m in names:
        s, d, ins = totals[m]
        vs, vd, vi = vote_totals[m]
        rows.append({
            "model": m,
            "missed_words_pct": round(100 * misses[m] / reference_total, 3),
            "wer_pct": round(100 * (s + d + ins) / reference_total, 3),
            "substitutions": s, "deletions": d, "insertions": ins,
            "right_against_the_majority": lone_right[m],
            "vote_with_this_pivot_wer_pct": round(100 * (vs + vd + vi) / reference_total, 3),
            "vote_substitutions": vs, "vote_deletions": vd, "vote_insertions": vi,
        })
    models = pd.DataFrame(rows)
    models.to_csv(out / "models-and-vote.csv", index=False)

    # --- 2. do they miss the same words? ----------------------------------
    # P(B misses | A misses), next to how often B misses overall. If the first
    # is far above the second, A and B are not independent listeners.
    shared = pd.DataFrame(index=names, columns=names, dtype=float)
    for a in names:
        for b in names:
            shared.loc[a, b] = 1.0 if a == b else (
                round(both_miss[(a, b)] / misses[a], 3) if misses[a] else float("nan"))
    shared.index.name = "when_this_model_misses"
    shared.to_csv(out / "shared-misses.csv")

    # --- lists to listen to ------------------------------------------------
    pd.DataFrame(hard_rows).to_csv(out / "hard-passages.csv", index=False)
    against = pd.DataFrame(against_rows)
    against.to_csv(out / "against-the-record.csv", index=False)

    interruptions = pd.DataFrame({
        "kind": list(kind_total),
        "words": [kind_total[k] for k in kind_total],
        "share_near_a_dash": [round(near_dash[k] / kind_total[k], 4) for k in kind_total],
    })
    if dashes_seen:
        interruptions.to_csv(out / "interruptions.csv", index=False)

    print(f"\n{reference_total:,} reference words across {len(recordings)} recordings\n")
    print(heard.to_string(index=False))
    print(f"\nNo model heard {100 * heard_by[0] / reference_total:.2f}% of the words.\n")
    print(models.to_string(index=False))
    if dashes_seen:
        print("\nHow often each kind of position sits within two words of a dash:")
        print(interruptions.to_string(index=False))
    else:
        print("\nThe references have no dashes, so interruptions.csv is not written.")
    print(f"\n{len(hard_rows)} hard passages, {len(against_rows)} against-the-record stretches")
    if against_rows:
        print(against.groupby(["direction", "what_happened"]).size().to_string())
    if hard_rows:
        print(pd.DataFrame(hard_rows).groupby(["kind", "what_happened"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

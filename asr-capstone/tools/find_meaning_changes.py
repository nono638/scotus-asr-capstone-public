"""Places where an engine wrote something fluent that means something else.

A "meaning change" is a short stretch where the engine's text reads fine but
says something different from what was said: a "not" dropped or added ("can"
for "can't"), a different number, or a different real word ("acquitted" for
"convicted"). Nothing on the page tells a reader it is wrong, which is what
makes these worse than garbled text.

Every recording comes from tools/lineup.py, with each engine already lined up
against the reference word by word (and cached). In each engine's line-up, every
run of differences next to each other is one "edit". Only short edits are looked
at, up to three tokens on each side. Each one is sorted into:

  negation  a "not", "never", "no", "nothing" ... on one side and not the other.
            The standard rule splits "can't" into "can not", so "can" for
            "can't" shows up as a missing "not".
  number    numbers on both sides that are not the same value however they are
            read ("twenty five" and "25" are the same; "15" and "50" are not).
  word      a content word swapped for a different real word.
  dropped / added
            one word that changes the sense ("only", "all", "again", "before")
            left out or put in.

and then thrown out if it is something this list is not about:

  - a name (a capitalised word the reference never writes in lower case);
  - a spelling variant or a new ending ("friend"/"friends"), another form of the
    same verb ("feel"/"felt"), or a word that means the same ("film"/"movie");
  - the same letters spaced differently ("any way"/"anyway");
  - a word the engine wrote that appears nowhere in that data set's references
    (so probably not a real word, or a name);
  - overlapping talk: a stretch that crosses from one speaker's turn to the
    next, or sits within two words of a reporter's dash (Supreme Court), or on
    EdAcc and CORAAL overlaps in time with another speaker's turn;
  - "no" against "know", "no" said as a reply, and "whether or not";
  - a word said twice or a restart ("I don't I don't remember"), where one
    copy still carries it;
  - two negatives that make one ("didn't never"): the sentence is still negative;
  - "isn't settled" for "is unsettled": the "not" moved into the word;
  - a number written another way: a case's docket number, a fraction sign, an
    ID read out letter by letter, "'08" for 2008;
  - every other engine wrote the same thing as this one. Then the reference is
    the odd one out, which is a different list.

For a `word`, `dropped` or `added` edit at least half the other engines must have
written the reference's version, so the audio there is clear enough. For a
`negation` or `number` at least one must have.

Usage:
    python tools/find_meaning_changes.py                 # every data set
    python tools/find_meaning_changes.py --corpus coraal edacc
    python tools/find_meaning_changes.py --corpus edacc --limit 3

Writes findings/failures/meaning/candidates.csv and counts.csv. The shortlist
(shortlist.csv) is picked by hand from candidates ranked by `rank_for_reading`;
`--to-read N` writes the top N per data set to read-these.csv to help with that.
Processor only; the whole of all three data sets takes a few minutes once the
line-up cache is full.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import zlib
import gzip
from pathlib import Path

import pandas as pd
import soundfile
from rapidfuzz.distance import Levenshtein

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowd  # noqa: E402
import lineup  # noqa: E402

OUT = crowd.CAPSTONE / "findings" / "failures" / "meaning"

#: Edits longer than this on either side are left alone: a long run of
#: differences is a garbled or overlapped stretch, not one word changing sense.
MAX_TOKENS = 3

#: How many tokens either side are checked for the same word said again.
NEAR = 4

#: Words either side shown in the context columns.
CONTEXT = 6

#: Words that turn a sentence round. n't words do not appear here: the standard
#: rule splits them ("didn't" -> "did not"). "ain't" stays one token, "aint".
NEGATORS = {"not", "never", "no", "nothing", "nobody", "none", "neither", "nor",
            "cannot", "aint"}

#: Single words that change the sense of a sentence when dropped or added.
SENSE_WORDS = {"only", "all", "every", "always", "again", "before", "after", "already",
               "still", "ever", "even", "almost", "both", "more", "less", "most",
               "least", "many", "few", "much", "also", "just", "too", "any", "some",
               "first", "last", "yet", "once", "anymore", "really", "very"}
#: Of those, the ones whose loss changes what is claimed, not just its strength.
#: They rank higher when picking what to read.
STRONG_SENSE = {"only", "all", "every", "always", "again", "before", "after", "already",
                "still", "ever", "both", "more", "less", "most", "least", "few",
                "first", "last", "yet", "once", "anymore", "any"}

#: Not content: fillers, small words, replies, number words.
NOT_CONTENT = (crowd.FILLERS | crowd.FUNCTION_WORDS | crowd.DISCOURSE | crowd.REPLIES
               | crowd.BACKCHANNELS | crowd.NUMBER_WORDS | NEGATORS)

#: Pairs that sound the same: one written for the other is a homophone slip, not
#: a change a reader would take at face value.
SOUND_ALIKE = [{"no", "know"}, {"not", "knot"}, {"nor", "or"}, {"none", "nun"}]

#: Forms of the same verb that the ending rules cannot see. "I feel" for "I felt"
#: is a change of tense, not of what happened, and on CORAAL it is often the
#: speaker's own grammar ("when the hurricane come"), which the edits finder covers.
VERB_FORMS = [set(f.split()) for f in [
    "be is am are was were been being", "come came coming comes", "feel felt feels feeling",
    "know knew known knows", "say said says saying", "go goes went gone going",
    "get got gets gotten getting", "think thought thinks",
    "make made makes", "take took taken taking takes", "see saw seen sees", "tell told tells", "give gave given gives",
    "run ran runs", "sit sat sits", "stand stood stands", "keep kept keeps",
    "leave left leaves", "bring brought brings", "buy bought buys", "find found finds",
    "have has had having", "do does did done doing", "hear heard hears", "mean meant means",
    "begin began begun begins", "grow grew grown grows", "win won wins", "lose lost loses",
    "pay paid pays", "teach taught teaches", "catch caught catches", "write wrote written writes",
    "drive drove driven drives", "eat ate eaten eats", "fall fell fallen falls",
    "speak spoke spoken speaks", "break broke broken breaks", "choose chose chosen chooses",
    "hold held holds", "lead led leads", "send sent sends", "spend spent spends",
    "build built builds", "meet met meets", "sell sold sells", "sleep slept sleeps",
    "wear wore worn wears", "become became becomes", "rise rose risen rises", "draw drew drawn",
    "throw threw thrown", "fly flew flown", "forget forgot forgotten", "understand understood",
    # and spoken short forms
    "gonna going", "wanna want", "kinda kind", "cause because"]]

#: Words that say the same thing. Canary in particular writes the American word
#: for a British one ("film" -> "movie", "loads" -> "a lot", "reckon" -> "think");
#: that rewrites the speaker but does not change what they said, so it is left out.
SYNONYMS = [set(f.split()) for f in [
    "film movie movies films", "sort kind", "loads lot lots many much", "pick choose",
    "enjoy like love", "reckon think guess suppose feel", "perhaps maybe", "near close",
    "great big good", "continue keep", "trust believe", "stuff things thing",
    "tall high", "fall autumn", "mum mom mother mama momma", "folks people", "kids children",
    "little small young", "say tell told said mention mentioned", "start begin",
    "got became came get become come", "route way", "okay alright", "yes yeah",
    "because due since", "fine okay", "buy get", "shop shopping", "wanted want",
    "dad daddy father", "grandma grandmother grandmas grandmothers grandmama",
    "grandpa grandfather granddaddy"]]

#: Titles said before a name ("Justice Kagan" written "Mrs. Kagan"): part of how
#: a speaker is named, not of what is said.
TITLES = {"justice", "chief", "mr", "mrs", "ms", "miss", "general", "counsel", "counselor",
          "judge", "doctor", "dr", "sir", "madam", "professor", "captain", "president"}

#: A speaker label the way a transcript prints one ("MR.", "BICKETT.").
LABEL = re.compile(r"^[A-Z]{2,}[.:]$")

COLUMNS = ["corpus", "part", "recording", "engine", "kind", "subkind", "start", "end",
           "record", "engine_wrote", "record_context", "engine_context", "others_right",
           "evidence", "record_tokens", "engine_tokens", "n_others", "n_others_right",
           "difference"]


# ---------------------------------------------------------------------------
# Small word tests
# ---------------------------------------------------------------------------

def is_content(token: str) -> bool:
    return len(token) > 1 and not any(ch.isdigit() for ch in token) and token not in NOT_CONTENT


#: Ordinals the standard rule leaves as words.
ORDINALS = {w: str(i) for i, w in enumerate(
    "zeroth first second third fourth fifth sixth seventh eighth ninth tenth".split())}


def is_number(token: str) -> bool:
    return (bool(re.fullmatch(r"\d+(st|nd|rd|th|s)?", token))
            or token in {"one", "half"} or token in ORDINALS)


def number_run(tokens: list[str], before: list[str], after: list[str]) -> list[str]:
    """The number tokens of an edit, with any number tokens right beside it, so a
    number split across the edge is read whole ("2 1000" + "and 8" = 2008)."""
    joins = {"and", "oh", "point"}
    head = []
    for t in reversed(before):
        if not (is_number(t) or t in joins):
            break
        head.insert(0, t)
    tail = []
    for t in after:
        if not (is_number(t) or t in joins):
            break
        tail.append(t)
    return [t for t in head + tokens + tail if is_number(t)]


def number_readings(tokens: list[str]) -> set:
    """The ways a run of number tokens can be read, so "20 5" and "25" match,
    "19 90" and "1990" match, and "2 1000" and "2000" match."""
    values = []
    for t in tokens:
        if t == "one":
            values.append("1")
        elif t in ORDINALS:
            values.append(ORDINALS[t])
        elif t == "half":
            values.append("0.5")
        elif is_number(t):
            values.append(re.sub(r"(st|nd|rd|th|s)$", "", t))
    if not values:
        return set()
    readings = {" ".join(values), "".join(values)}
    try:
        numbers = [float(v) for v in values]
        # Tens and units said together, then read side by side, the way years
        # and clock times are said: "19 80 8" -> "1988", "12 50 5" -> "1255".
        groups = []
        for n in numbers:
            if groups and groups[-1] % 10 == 0 and 20 <= groups[-1] <= 90 and n < 10:
                groups[-1] += n
            else:
                groups.append(n)
        readings.add("".join(str(int(g)) if g == int(g) else str(g) for g in groups))
        readings.add(str(sum(numbers)))
        total, current = 0.0, 0.0
        for n in numbers:          # English order: "2 1000 5" -> 2005
            if n in (100, 1000, 1e6) and current:
                current *= n
                if n >= 1000:
                    total, current = total + current, 0.0
            else:
                current += n
        readings.add(str(total + current))
        # "seven five hundred" for 7,500: the digits before a hundred side by side.
        if len(numbers) > 2 and numbers[-1] in (100, 1000):
            head = "".join(str(int(n)) for n in numbers[:-1])
            readings.add(str(float(int(head) * numbers[-1])))
    except ValueError:
        pass
    return readings


def same_number(a: set, b: set) -> bool:
    """Whether two sets of readings share one, counting "15" and "2015" (a year
    said short) and "0" (an engine writing "10 000" with a space) as the same."""
    if a & b:
        return True
    plain = lambda r: {x for x in r if " " not in x}
    for x in plain(a):
        for y in plain(b):
            short, long = sorted((x, y), key=len)
            # A year said short: "fifteen" or "'08" for 2015 or 2008.
            if (len(long) == 4 and long.isdigit() and long[:2] in ("19", "20") and len(short) <= 2
                    and short.isdigit() and int(long[2:]) == int(short)):
                return True
    return {"0"} in (plain(a), plain(b)) or "0" in a or "0" in b


def letters(tokens: list[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", "".join(tokens))


def sound_alike(a: str, b: str) -> bool:
    return any({a, b} == pair for pair in SOUND_ALIKE)


def is_variant(a: str, b: str) -> bool:
    """A spelling variant, a new ending, another form of the same verb, a word
    that says the same thing, or a near-miss of one letter on a long word."""
    a, b = (re.sub(r"ies$", "y", w) for w in (a, b))
    if crowd.same_word_new_ending(a, b) or crowd.strip_ending(a) == crowd.strip_ending(b):
        return True
    if any(a in forms and b in forms for forms in VERB_FORMS + SYNONYMS):
        return True
    # The same long start, a different end: "necessarily"/"necessary", "youngest"/"younger".
    same_start = len(os.path.commonprefix([a, b]))
    if same_start >= 5 and abs(len(a) - len(b)) <= 3 and same_start >= min(len(a), len(b)) - 3:
        return True
    return min(len(a), len(b)) >= 6 and Levenshtein.distance(a, b) <= 1


def capitalised_mid_sentence(words, i: int, lower_words: set | None) -> bool:
    """An engine word with a capital that does not start a sentence: likely a
    name, unless the reference writes it in lower case somewhere ("Court")."""
    text = words[i].text.strip().strip("\"'(").rstrip(".,?!;:")
    if not text[:1].isupper() or text in crowd.NOT_NAMES or text.startswith("I'"):
        return False
    if lower_words is not None and text.lower() in lower_words:
        return False
    before = words[i - 1].text.strip() if i > 0 else "."
    return not before.endswith((".", "?", "!", ":"))


# ---------------------------------------------------------------------------
# One recording
# ---------------------------------------------------------------------------

def engine_view(alignment) -> dict:
    """What one engine wrote at each reference position.

    wrote[i]       the token it wrote for reference token i ("" if it dropped it)
    added[g]       tokens it wrote just before reference token g that the
                   reference does not have
    hyp_of[i]      the engine's token index matched to reference token i (or None)
    ref_of[k]      the reference token index matched to engine token k (or None)
    """
    n_ref = len(alignment.reference.tokens)
    hyp = alignment.hypothesis.tokens
    wrote, hyp_of = [""] * n_ref, [None] * n_ref
    ref_of = [None] * len(hyp)
    added = {}
    for c in alignment.chunks:
        if c.kind in ("equal", "substitute"):
            for k, i in enumerate(range(c.ref_start, c.ref_end)):
                wrote[i] = hyp[c.hyp_start + k]
                hyp_of[i] = c.hyp_start + k
                ref_of[c.hyp_start + k] = i
        elif c.kind == "insert":
            added[c.ref_start] = hyp[c.hyp_start:c.hyp_end]
    return {"wrote": wrote, "added": added, "hyp_of": hyp_of, "ref_of": ref_of}


def other_version(view: dict, rs: int, re_: int) -> list[str]:
    """What another engine wrote over reference tokens rs..re_ (an empty span is
    the gap before rs)."""
    if rs == re_:
        return list(view["added"].get(rs, []))
    out = []
    for i in range(rs, re_):
        if i > rs:
            out += view["added"].get(i, [])
        if view["wrote"][i]:
            out.append(view["wrote"][i])
    return out


def edits(alignment) -> list[tuple[int, int, int, int]]:
    """Each run of non-equal chunks next to each other, as (ref_start, ref_end,
    hyp_start, hyp_end), if it is short enough."""
    out, run = [], None
    for c in alignment.chunks:
        if c.kind == "equal":
            if run:
                out.append(run)
            run = None
        elif run is None:
            run = [c.ref_start, c.ref_end, c.hyp_start, c.hyp_end]
        else:
            run[1], run[3] = c.ref_end, c.hyp_end
    if run:
        out.append(run)
    return [tuple(r) for r in out
            if r[1] - r[0] <= MAX_TOKENS and r[3] - r[2] <= MAX_TOKENS]


def classify(ref: list[str], hyp: list[str], near: dict) -> str | None:
    """Which kind of meaning change an edit is, or None.

    ref, hyp are the two sides' tokens; near["ref"] and near["hyp"] the tokens
    just before and after the edit on each side, to tell a word said twice (a
    restart: "I don't I don't remember") from a real one.
    """
    if letters(ref) == letters(hyp):
        return None
    neg_ref = [t for t in ref if t in NEGATORS]
    neg_hyp = [t for t in hyp if t in NEGATORS]
    if len(neg_ref) != len(neg_hyp):
        extra = neg_ref if len(neg_ref) > len(neg_hyp) else neg_hyp
        other = hyp if extra is neg_ref else ref
        before, after = near["ref"] if extra is neg_ref else near["hyp"]
        beside = before + after
        side = ref if extra is neg_ref else hyp
        # "whether or not" says the same as "whether".
        if [t for t in side if t not in other] == ["or", "not"]:
            return None
        # A restart the reporter left out: "I [don't. I] mean", "we're [not we're] just".
        if not other and before and side[-1] == before[-1]:
            return None
        # The "not" moved into the word: "isn't settled" for "is unsettled".
        for word in other:
            for prefix in ("un", "in", "im", "ir", "il", "non", "dis"):
                if word.startswith(prefix) and word[len(prefix):] in side:
                    return None
        # "no" for "know", and a negator that is only repeated ("not not").
        if any(sound_alike(a, b) for a in extra for b in other):
            return None
        if all(t in beside or extra.count(t) > 1 for t in extra):
            return None
        # Two negatives that make one ("didn't never", "ain't never"): if the
        # other side still has a negator in or right beside the edit, the
        # sentence is still negative. Common on CORAAL, where it is the
        # speaker's grammar, and the edits finder's business.
        o_before, o_after = near["hyp"] if extra is neg_ref else near["ref"]
        if any(t in NEGATORS for t in o_before[-2:] + other + o_after[:2]):
            return None
        # "no" counts only before a word that means something ("no snow");
        # on its own it is a reply or a way of holding the floor.
        if set(extra) == {"no"}:
            follows = (side + after)[side.index("no") + 1:][:1]
            if not follows or not is_content(follows[0]):
                return None
        return "negation"
    nums_ref = [t for t in ref if is_number(t)]
    nums_hyp = [t for t in hyp if is_number(t)]
    if nums_ref and nums_hyp:
        # A code read out letter by letter ("F C two six P two") is an ID, not an amount.
        if any(len(t) == 1 and t.isalpha() and t not in ("a", "i") for t in ref + hyp):
            return None
        if same_number(number_readings(nums_ref), number_readings(nums_hyp)):
            return None
        whole_ref = number_run(ref, *near["ref"])
        whole_hyp = number_run(hyp, *near["hyp"])
        if same_number(number_readings(whole_ref), number_readings(whole_hyp)):
            return None
        return "number"
    if not ref or not hyp:
        word = (ref or hyp)
        beside = sum(near["ref"] if ref else near["hyp"], [])
        if len(word) == 1 and word[0] in SENSE_WORDS and word[0] not in beside:
            return "dropped" if ref else "added"
        return None
    # Content words of three letters or more: CORAAL writes cut-off words as
    # they were said ("gr", "re"), and those are not words the engine replaced.
    new_ref = [t for t in ref if is_content(t) and len(t) >= 3 and t not in hyp]
    new_hyp = [t for t in hyp if is_content(t) and len(t) >= 3 and t not in ref]
    if new_ref and new_hyp:
        if set(new_ref + new_hyp) & TITLES:
            return None
        if any(is_variant(a, b) for a in new_ref for b in new_hyp):
            return None
        return "word"
    return None


def is_reply(text: str) -> bool:
    return bool(re.fullmatch(r"[Nn]o[.,!?]+", text.strip()))


def starts_turn(turns: list[int], w: int) -> bool:
    return w == 0 or (w < len(turns) and turns[w - 1] != turns[w])


def speaker_overlap(transcript, turn_index: int, start: float, end: float) -> bool:
    """Whether another speaker's timed turn overlaps start..end."""
    mine = transcript.turns[turn_index].speaker
    for turn in transcript.turns:
        if turn.start is None or turn.speaker == mine:
            continue
        if turn.start < end and turn.end > start:
            return True
    return False


def find(job: dict, lined: dict) -> list[dict]:
    """Every meaning-change candidate in one recording, every engine."""
    names = list(lined)
    views = {n: engine_view(lined[n][2]) for n in names}
    rows = []
    for name in names:
        transcript, reference_words, alignment, words = lined[name]
        ref_tok = alignment.reference.tokens
        hyp_tok = alignment.hypothesis.tokens
        ref_src = alignment.reference.source_index
        hyp_src = alignment.hypothesis.source_index
        turns = lineup.word_turns(transcript)
        lower_words = {w.strip(".,?!;:-'\"") for w in reference_words
                       if w[:1].islower()} if crowd.can_spot_names(reference_words) else None
        view = views[name]

        for rs, re_, hs, he in edits(alignment):
            ref, hyp = ref_tok[rs:re_], hyp_tok[hs:he]
            near = {"ref": (ref_tok[max(0, rs - NEAR):rs], ref_tok[re_:re_ + NEAR]),
                    "hyp": (hyp_tok[max(0, hs - NEAR):hs], hyp_tok[he:he + NEAR])}
            subkind = classify(ref, hyp, near)
            if not subkind:
                continue

            # The whole words on each side: "can't" is two tokens, "can not".
            ref_tokens = set(range(rs, re_))
            hyp_tokens = set(range(hs, he))
            for _ in range(2):
                words_r = {ref_src[i] for i in ref_tokens}
                ref_tokens |= {i for i in range(max(0, rs - 3), min(len(ref_tok), re_ + 3))
                               if ref_src[i] in words_r}
                hyp_tokens |= {view["hyp_of"][i] for i in ref_tokens if view["hyp_of"][i] is not None}
                words_h = {hyp_src[k] for k in hyp_tokens}
                hyp_tokens |= {k for k in range(max(0, hs - 3), min(len(hyp_tok), he + 3))
                               if hyp_src[k] in words_h}
                ref_tokens |= {view["ref_of"][k] for k in hyp_tokens if view["ref_of"][k] is not None}
            ref_words = sorted({ref_src[i] for i in ref_tokens})
            hyp_words = sorted({hyp_src[k] for k in hyp_tokens})
            at = ref_src[rs] if rs < len(ref_src) else len(reference_words)
            if ref_words:
                w0, w1 = ref_words[0], ref_words[-1] + 1
            else:
                w0 = w1 = at

            # Times from the engine's own words; a pure deletion sits between
            # the engine words either side.
            if hyp_words:
                start = words[hyp_words[0]].start
                end = words[hyp_words[-1]].end
            else:
                before = words[hyp_src[hs - 1]] if hs > 0 else None
                after = words[hyp_src[hs]] if hs < len(hyp_src) else None
                start = before.end if before else (after.start if after else 0.0)
                end = after.start if after else start
                start, end = min(start, end), max(start, end)

            # Overlapping talk. An insertion is checked on the words either side of it.
            span = range(w0, w1) if w1 > w0 else range(max(0, w0 - 1), min(len(turns), w0 + 1))
            span_turns = {turns[w] for w in span if w < len(turns)}
            if len(span_turns) > 1:
                continue
            if job["corpus"] == "scotus":
                if any(crowd.near_interruption(reference_words, w)
                       for w in range(max(0, w0 - 1), min(len(reference_words), w1 + 1))):
                    continue
            elif span_turns and speaker_overlap(transcript, next(iter(span_turns)), start, end):
                continue

            # "No" said as a reply: "No," or "No." on its own, or first in a turn.
            record_text = " ".join(reference_words[w0:w1])
            # Every word from the first to the last, as engine_context brackets them: a
            # word inside the spot that lined up with nothing ("$2 .5 billion,") is still
            # the engine's. (Before 7 November only the lined-up words were kept.)
            engine_display = " ".join(words[k].text.strip()
                                      for k in range(hyp_words[0], hyp_words[-1] + 1)) if hyp_words else ""
            if subkind == "negation" and (is_reply(record_text) or is_reply(engine_display)
                                          or (record_text.lower() == "no" and starts_turn(turns, w0))):
                continue

            # A case called by its docket number ("Case 16-111"), and a fraction
            # written as a sign ("6 1/2"): how a number is written, not which.
            if subkind == "number" and (re.search(r"\d\d-\d{2,}", record_text)
                                        or re.search("[\u2044\u00bd/]", engine_display)):
                continue

            # The same text once the whole words are shown (a token split oddly).
            if letters(record_text.lower().split()) == letters(engine_display.lower().split()):
                continue

            # Names.
            if lower_words is not None and crowd.looks_like_a_name(record_text, lower_words):
                continue
            if any(capitalised_mid_sentence(words, k, lower_words)
                   for k in {hyp_src[j] for j in range(hs, he)}):
                continue
            if any(LABEL.match(words[k].text.strip()) for k in hyp_words) and lower_words is not None:
                continue

            # The other engines: who wrote the reference's version, who wrote this one's.
            others = [n for n in names if n != name]
            right, same = [], []
            for other in others:
                version = other_version(views[other], rs, re_)
                if version == ref:
                    # The reference's own words written as they are; for a word
                    # this engine added, the words either side of the gap.
                    check = range(rs, re_) if re_ > rs else range(max(0, rs - 1), min(len(ref_tok), rs + 1))
                    if all(views[other]["wrote"][i] == ref_tok[i] for i in check):
                        right.append(other)
                if version == hyp:
                    same.append(other)
            # Every engine wrote the same thing against the reference: most likely
            # the reference's own choice (a slip the reporter tidied up, a name,
            # a reference error), not a mishearing. Kept apart, in all-agree.csv.
            all_agree = len(same) == len(others)
            need = 1 if subkind in ("negation", "number") else (len(others) + 1) // 2
            if len(right) < need and not all_agree:
                continue

            rows.append({
                "corpus": job["corpus"], "part": job["term"], "recording": job["docket"],
                "engine": name, "kind": "meaning", "subkind": subkind,
                "start": round(start, 2), "end": round(end, 2),
                "record": record_text, "engine_wrote": engine_display,
                "record_context": " ".join(reference_words[max(0, w0 - CONTEXT):w0] + ["["]
                                           + reference_words[w0:w1] + ["]"]
                                           + reference_words[w1:w1 + CONTEXT]).replace("[ ", "[").replace(" ]", "]"),
                "engine_context": engine_context(words, hyp_words, hyp_src, hs),
                "others_right": " ".join(right),
                "evidence": f"{subkind}: record '{record_text}', engine '{engine_display}'; "
                            f"{len(right)} of {len(others)} others right",
                "record_tokens": " ".join(ref), "engine_tokens": " ".join(hyp),
                "n_others": len(others), "n_others_right": len(right),
                "difference": difference(ref, hyp),
                "all_agree": all_agree,
            })
    return rows


def engine_context(words, hyp_words: list[int], hyp_src: list[int], hs: int) -> str:
    if hyp_words:
        k0, k1 = hyp_words[0], hyp_words[-1] + 1
    else:
        k0 = k1 = hyp_src[hs] if hs < len(hyp_src) else len(words)
    text = ([w.text.strip() for w in words[max(0, k0 - CONTEXT):k0]] + ["["]
            + [w.text.strip() for w in words[k0:k1]] + ["]"]
            + [w.text.strip() for w in words[k1:k1 + CONTEXT]])
    return " ".join(text).replace("[ ", "[").replace(" ]", "]")


def difference(ref: list[str], hyp: list[str]) -> float:
    """How unlike the two sides' changed words look, 0 (same letters) to 1.

    A rough stand-in for "how different in meaning": words that look alike are
    usually the engine hearing nearly the right sounds ("into"/"in to"), words
    that look nothing alike are more often a different idea altogether.
    """
    a = " ".join(t for t in ref if t not in hyp)
    b = " ".join(t for t in hyp if t not in ref)
    if not a or not b:
        return 1.0
    return round(Levenshtein.normalized_distance(a, b), 2)


# ---------------------------------------------------------------------------
# Every recording
# ---------------------------------------------------------------------------

def load(job: dict) -> dict:
    """lineup.load(), waiting a little if the cache file is still being written."""
    for attempt in range(10):
        try:
            return lineup.load(job)
        except (EOFError, gzip.BadGzipFile, zlib.error):
            time.sleep(30)
    return lineup.load(job)


def rank_for_reading(table: pd.DataFrame) -> pd.DataFrame:
    """Candidates in the order to read them: negation, then number, then word
    swaps that look least alike, then dropped or added sense words. Within each,
    more of the other engines right first."""
    order = {"negation": 0, "number": 1, "word": 2, "dropped": 3, "added": 3}
    ranked = table.copy()
    ranked["_kind"] = ranked["subkind"].map(order)
    ranked["_share"] = ranked["n_others_right"] / ranked["n_others"]
    # A dropped or added "really" or "just" is weaker than a dropped "only".
    words = (ranked["record_tokens"].fillna("") + " " + ranked["engine_tokens"].fillna("")).str.split()
    ranked["_weak"] = ranked["subkind"].isin(["dropped", "added"]) & ~words.apply(
        lambda t: bool(set(t) & STRONG_SENSE))
    return ranked.sort_values(["_kind", "_weak", "_share", "difference"],
                              ascending=[True, True, False, False]).drop(columns=["_kind", "_share", "_weak"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", nargs="+", choices=list(lineup.PARTS),
                        default=list(lineup.PARTS), help="data sets (default: all three)")
    parser.add_argument("--limit", type=int, help="only the first N recordings of each part, to try it out")
    parser.add_argument("--to-read", type=int, default=0, metavar="N",
                        help="also write the top N candidates per data set to read-these.csv")
    args = parser.parse_args()

    started = time.monotonic()
    rows, hours, vocabulary = [], [], {}
    for corpus in args.corpus:
        jobs = lineup.recordings(corpus)
        if args.limit:
            seen = {}
            jobs = [j for j in jobs if seen.setdefault(j["term"], []).append(j) or
                    len(seen[j["term"]]) <= args.limit]
        vocabulary[corpus] = set()
        for number, job in enumerate(jobs, 1):
            lined = load(job)
            found = find(job, lined)
            rows += found
            first = next(iter(lined.values()))
            vocabulary[corpus] |= set(first[2].reference.tokens)
            seconds = soundfile.info(str(job["audio"])).duration
            for engine in lined:
                hours.append({"corpus": corpus, "part": job["term"], "engine": engine,
                              "recording": job["docket"], "hours": seconds / 3600})
            print(f"{corpus} [{number}/{len(jobs)}] {job['term']} {job['docket']}: "
                  f"{len(found)} candidates {(time.monotonic() - started) / 60:.1f} min", flush=True)

    agreed = pd.DataFrame([r for r in rows if r["all_agree"]], columns=COLUMNS)
    table = pd.DataFrame([r for r in rows if not r["all_agree"]], columns=COLUMNS)

    # The engine's new content words must be real words: ones the references of
    # that data set use somewhere.
    def real(row) -> bool:
        if row["subkind"] not in ("word", "added"):
            return True
        ref = row["record_tokens"].split()
        new = [t for t in row["engine_tokens"].split() if is_content(t) and t not in ref]
        return all(t in vocabulary[row["corpus"]] for t in new)
    table = table[table.apply(real, axis=1)] if len(table) else table
    table = table.sort_values(["corpus", "part", "recording", "start", "engine"])

    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "candidates.csv", index=False)

    # One row per spot: every engine wrote the same there, so which one is shown
    # doesn't matter.
    agreed = agreed[agreed.apply(real, axis=1)] if len(agreed) else agreed
    agreed = agreed.drop_duplicates(["corpus", "part", "recording", "record_context"])
    agreed.sort_values(["corpus", "part", "recording", "start"]).to_csv(OUT / "all-agree.csv", index=False)
    print(f"{len(agreed):,} spots where every engine agrees against the reference -> all-agree.csv")

    keys = ["corpus", "part", "engine"]
    counts = pd.DataFrame(hours).groupby(keys).agg(recordings=("recording", "nunique"),
                                                   hours=("hours", "sum"))
    by_kind = table.pivot_table(index=keys, columns="subkind", values="start",
                                aggfunc="count", fill_value=0)
    counts = counts.join(by_kind).fillna(0)
    kinds = [k for k in ["negation", "number", "word", "dropped", "added"] if k in counts]
    counts[kinds] = counts[kinds].astype(int)
    counts["candidates"] = counts[kinds].sum(axis=1)
    counts["candidates_per_hour"] = (counts["candidates"] / counts["hours"]).round(2)
    for kind in kinds:
        counts[f"{kind}_per_hour"] = (counts[kind] / counts["hours"]).round(2)
    counts["hours"] = counts["hours"].round(1)
    counts.reset_index().to_csv(OUT / "counts.csv", index=False)

    if args.to_read:
        ranked = rank_for_reading(table)
        ranked.groupby("corpus").head(args.to_read).to_csv(OUT / "read-these.csv", index=False)

    print(f"\n{len(table):,} candidates")
    print(counts.to_string())
    print(f"\nin {(time.monotonic() - started) / 60:.1f} min -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

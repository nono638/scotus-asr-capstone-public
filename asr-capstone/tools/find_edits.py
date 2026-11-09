"""Where a speech engine rewrites how the person spoke, rather than mishearing them.

Two kinds of rewrite:

1. **Dialect grammar written as standard English (CORAAL).** CORAAL's transcribers
   write down what the speaker said, grammar and all: "he be working", "they
   was", "it ain't no jobs". An engine trained mostly on standard written English
   tends to write the standard form instead: "he's working", "they were", "there
   are no jobs". This finds each place the reference has one of the African
   American English features below and asks, for each engine, whether it kept
   the speaker's form, standardised it, or did something else there.

       habitual-be        "they be working"       invariant be, not after a modal or "to"
       zero-copula        "they working"          no is/are before -ing, a place or an adjective
       aint               "it ain't right"        ain't for isn't/haven't/didn't
       third-person-s     "she go", "he don't"    no -s on the verb after he/she/it
       was-levelling      "they was", "we was"    was with a plural subject
       negative-concord   "didn't do nothing"     two negatives in one clause
       existential-it     "it's a lot of people"  it for there
       completive-done    "I done told you"       done before a past-tense verb
       finna              "I'm finna go"          about to

   Each rule is written to be sure rather than to catch everything: a feature
   counts only where nothing else could explain the words (see the README).

2. **Restarts and repeated words cleaned up (every data set).** Where the
   reference keeps a repeated word or phrase ("I -- I think", "the the", "it was
   it was") and the engine wrote it only once.

Everything is read off the lined-up transcripts in tools/lineup.py (the
`standard` rule, so contractions are already spelt out: "he's" is "he is",
"don't" is "do not", "ain't" is "aint"). For each reference token, an engine
either wrote the same token, wrote a different one, or wrote nothing; words it
added sit in the gaps between reference tokens. A feature is a short stretch of
reference tokens; what the engine wrote over that stretch, including words it
added inside it, is compared with it.

Usage:
    python tools/find_edits.py                      # CORAAL, Earnings-22, EdAcc and the Supreme Court
    python tools/find_edits.py --corpus coraal --limit 3
    python tools/find_edits.py --show habitual-be   # print every instance of one feature

Writes findings/failures/edits/: candidates.csv (every dialect feature an
engine standardised or left out), restarts-dropped.csv.gz (every restart an
engine wrote once; the same columns, compressed because there are tens of
thousands), dialect-instances.csv (every dialect feature found, with each
engine's outcome), dialect-rates.csv, restart-rates.csv and counts.csv.
The shortlist is picked by hand from candidates.csv. Processor only; about a
minute for everything once the alignment cache is full.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crowd  # noqa: E402
import lineup  # noqa: E402

OUT = crowd.CAPSTONE / "findings" / "failures" / "edits"
CONTEXT = 6

SHARED = ["corpus", "part", "recording", "engine", "kind", "subkind", "start", "end",
          "record", "engine_wrote", "record_context", "engine_context", "others_right",
          "evidence"]

# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

MODALS = {"will", "would", "shall", "should", "can", "could", "may", "might", "must"}
FINITE_BE = {"is", "are", "am", "was", "were"}
AUX = FINITE_BE | MODALS | {"do", "does", "did", "has", "have", "had"}
#: Short words that can sit between a subject and its verb without changing anything.
ADVERBS = {"just", "always", "never", "still", "also", "really", "usually", "sometimes",
           "even", "ever", "only", "probably", "already", "mostly", "normally", "all",
           "both", "constantly", "steady", "actually"}
#: Words that start a clause, after which "you" is the subject and not an object.
CLAUSE_START = {"how", "what", "where", "why", "when", "who", "and", "but", "so", "if",
                "cause", "because", "like", "now", "well", "yeah", "oh", "then", "that",
                "while", "since", "until", "or", "unless", "whether", "okay", "see", "say",
                "think", "know", "mean", "said", "guess", "bet", "hope", "when"}
#: Words after which "it" is an object ("let it go", "make it work").
OBJECT_BEFORE = {"make", "made", "makes", "let", "lets", "have", "has", "had", "help", "helped",
                 "see", "saw", "seen", "watch", "watched", "hear", "heard", "feel", "felt",
                 "get", "got", "to", "not", "do", "does", "did"} | MODALS | FINITE_BE

#: -ing words that are not verbs.
NOT_VERB_ING = {"nothing", "something", "anything", "everything", "thing", "things", "morning",
                "evening", "during", "ceiling", "wedding", "king", "ring", "sing", "bring",
                "spring", "string", "swing", "wing", "sibling", "siblings", "darling",
                "pudding", "according", "including", "building", "buildings", "clothing",
                "lightning", "feeling", "feelings", "meeting", "meetings", "beginning",
                "ending", "earring", "earrings", "stuffing", "icing", "awning", "viking",
                "pending", "sterling", "bling", "fling", "sling", "sting", "thing"}
PLACE = {"at", "in", "on", "outside", "inside", "home", "here", "there", "from", "over",
         "downtown", "upstairs", "downstairs", "not"}
ADJECTIVES = {"good", "bad", "fine", "nice", "big", "little", "old", "young", "cool", "crazy",
              "sick", "tired", "happy", "mad", "scared", "ready", "smart", "rich", "broke",
              "grown", "married", "gone", "right", "wrong", "sure", "cute", "funny", "lazy",
              "busy", "nasty", "alright", "okay", "late", "quiet", "different", "strong",
              "older", "younger", "bigger", "smaller", "stupid", "afraid", "upset", "dead",
              "pregnant", "alive", "hungry", "angry", "serious", "safe", "free", "able",
              "real", "worried", "careful", "proud", "special", "friends", "cousins"}

#: Verbs whose bare form after he/she/it is plainly present tense. Verbs AAE also
#: uses as a past tense ("he come home", "she run", "I see him yesterday") are left
#: out, and so are verbs spelt the same in every tense ("put", "cut", "read"), and
#: "like", which after a pronoun is mostly the quotative or a filler ("she like, ...").
BASE_VERBS = {"go", "say", "have", "do", "want", "know", "need", "live", "work", "get",
              "make", "take", "look", "think", "feel", "try", "seem", "mean", "stay", "play",
              "talk", "sound", "keep", "call", "tell", "love", "hate", "cost", "matter",
              "happen", "help", "drive", "act", "walk", "start", "stop", "use", "own",
              "believe", "remember", "understand", "care", "hurt", "pay", "leave", "smell",
              "look", "watch", "teach", "wear", "sleep", "cook", "clean", "buy", "send"}

PAST = {"went", "told", "said", "got", "seen", "did", "came", "ate", "gave", "took", "made",
        "left", "bought", "brought", "thought", "had", "heard", "been", "gone", "saw", "ran",
        "wrote", "broke", "forgot", "lost", "sold", "spent", "caught", "taught", "found",
        "knew", "grew", "threw", "fell", "felt", "kept", "paid", "won", "moved", "finished"}

NEG_FIRST = {"not", "never", "aint"}
NEG_WORDS = {"no", "nobody", "nothing", "none", "nowhere", "neither", "noone"}
ANY_WORDS = {"any", "anybody", "anything", "anyone", "anywhere", "ever", "either", "a"}

#: Words said twice on purpose, not as a restart.
SAID_TWICE = {"that", "had", "is", "no", "yeah", "yes", "okay", "right", "bye", "very",
              "really", "so", "oh", "well", "mhm", "uhhuh", "ha", "hey", "now", "please",
              "go", "come", "on", "far", "long", "many", "much", "more", "again", "too",
              "knock", "blah", "hello", "hi", "ok", "huh", "mm", "wow", "bam", "boom",
              "good", "super", "bad", "big", "little", "real", "all", "hard", "fast"}

#: "it's no joke", "it's no use": it is the thing being talked about, not "there".
NOT_EXISTENTIAL = {"more", "use", "big", "good", "problem", "joke", "fun", "different", "better",
                   "wonder", "secret", "longer", "surprise", "excuse", "lie", "game", "play",
                   "picnic", "laughing", "easy", "bueno", "longer"}

ENGINES = ["Whisper", "Qwen3", "Parakeet", "Canary", "Granite"]


def third_person(verb: str) -> set[str]:
    """The -s forms of a verb: go -> goes, try -> tries, have -> has, do -> does."""
    special = {"have": "has", "do": "does", "go": "goes", "say": "says", "be": "is"}
    if verb in special:
        return {special[verb]}
    if verb.endswith("y") and verb[-2:-1] not in "aeiou":
        return {verb[:-1] + "ies"}
    if verb.endswith(("s", "sh", "ch", "x", "z", "o")):
        return {verb + "es"}
    return {verb + "s"}


def is_ing_verb(token: str) -> bool:
    return token.endswith("ing") and len(token) >= 5 and token not in NOT_VERB_ING


# ---------------------------------------------------------------------------
# What each engine wrote over a stretch of the reference
# ---------------------------------------------------------------------------

class EngineView:
    """One engine's alignment, read from the reference's side.

    `at[i]` is the engine token index lined up with reference token i (equal or
    substitute), or None where the engine wrote nothing there. `gaps[g]` holds the
    engine tokens it added just before reference token g.
    """

    def __init__(self, alignment, words):
        self.ref = alignment.reference.tokens
        self.hyp = alignment.hypothesis.tokens
        self.hyp_source = alignment.hypothesis.source_index
        self.words = words
        self.at: list[int | None] = [None] * len(self.ref)
        self.equal = [False] * len(self.ref)
        self.gaps: dict[int, list[int]] = {}
        for c in alignment.chunks:
            if c.kind in ("equal", "substitute"):
                for k in range(c.ref_end - c.ref_start):
                    self.at[c.ref_start + k] = c.hyp_start + k
                    self.equal[c.ref_start + k] = c.kind == "equal"
            elif c.kind == "insert":
                self.gaps[c.ref_start] = list(range(c.hyp_start, c.hyp_end))

    def core(self, a: int, b: int) -> list[str]:
        """What the engine wrote over reference tokens a..b-1, with words it added inside."""
        out = []
        for i in range(a, b):
            if i > a:
                out += [self.hyp[k] for k in self.gaps.get(i, [])]
            if self.at[i] is not None:
                out.append(self.hyp[self.at[i]])
        return out

    def edges(self, a: int, b: int) -> tuple[list[str], list[str]]:
        """Words the engine added just before and just after the stretch."""
        return ([self.hyp[k] for k in self.gaps.get(a, [])],
                [self.hyp[k] for k in self.gaps.get(b, [])])

    def hyp_span(self, a: int, b: int) -> tuple[int, int] | None:
        """The engine tokens the stretch covers, words added inside it included."""
        ks = [self.at[i] for i in range(a, b) if self.at[i] is not None]
        ks += [k for g in range(a + 1, b) for k in self.gaps.get(g, [])]
        return (min(ks), max(ks)) if ks else None

    def times(self, a: int, b: int) -> tuple[float, float]:
        """Seconds the stretch covers in this engine's timing; the nearest written
        words either side where it wrote nothing there."""
        span = self.hyp_span(a, b)
        if span:
            w0, w1 = self.words[self.hyp_source[span[0]]], self.words[self.hyp_source[span[1]]]
            return round(w0.start, 2), round(w1.end, 2)
        # As far as it takes: looking only ten words either side gave a long gap the time
        # 0.0, and showed the judges the wrong place (bug-audit-2026-11-05.md).
        before = next((self.at[i] for i in range(a - 1, -1, -1) if self.at[i] is not None), None)
        after = next((self.at[i] for i in range(b, len(self.ref)) if self.at[i] is not None), None)
        start = self.words[self.hyp_source[before]].end if before is not None else None
        end = self.words[self.hyp_source[after]].start if after is not None else None
        if start is None:
            start = end if end is not None else 0.0
        return round(start, 2), round(end if end is not None else start, 2)

    def written(self, a: int, b: int) -> str:
        """The engine's own words over the stretch, as it wrote them ("we'd be")."""
        span = self.hyp_span(a, b)
        if not span:
            return ""
        sources = sorted({self.hyp_source[k] for k in range(span[0], span[1] + 1)})
        return " ".join(self.words[i].text.strip() for i in sources)

    def context(self, a: int, b: int) -> str:
        """The engine's own words around the stretch, the stretch in [brackets]."""
        span = self.hyp_span(a, b)
        if span:
            i0, i1 = self.hyp_source[span[0]], self.hyp_source[span[1]]
        else:
            before = [self.at[i] for i in range(max(0, a - 10), a) if self.at[i] is not None]
            i1 = self.hyp_source[before[-1]] if before else -1
            i0 = i1 + 1
        text = lambda ws: " ".join(w.text.strip() for w in ws)  # noqa: E731
        return (f"{text(self.words[max(0, i0 - CONTEXT):i0])} [{text(self.words[i0:i1 + 1])}] "
                f"{text(self.words[i1 + 1:i1 + 1 + CONTEXT])}").strip()


# ---------------------------------------------------------------------------
# Finding the features in the reference
# ---------------------------------------------------------------------------

def breaks(reference_words: list[str], ref_source: list[int], turns: list[int]) -> list[bool]:
    """brk[i] is True when a sentence mark, a comma or a change of turn sits
    between reference token i-1 and token i. A feature may not cross one."""
    brk = [True] * len(ref_source)
    for i in range(1, len(ref_source)):
        s0, s1 = ref_source[i - 1], ref_source[i]
        if s0 == s1:
            brk[i] = False
            continue
        between = reference_words[s0:s1]
        brk[i] = (turns[s0] != turns[s1]
                  or any(re.search(r"[.,?!;:]$", w) or w.strip("-") == "" for w in between))
    return brk


def subject_before(R: list[str], brk: list[bool], i: int) -> int | None:
    """Index of the subject of the verb at i: the first word before it that is
    not one of ADVERBS, as long as no break comes between."""
    j = i - 1
    while j >= 0 and not brk[j + 1] and R[j] in ADVERBS:
        j -= 1
    if j < 0 or brk[j + 1]:
        return None
    return j


def prev(R: list[str], brk: list[bool], j: int) -> str:
    """The token before j, or "" if a break or the start comes first."""
    return "" if j == 0 or brk[j] else R[j - 1]


def you_is_subject(R, brk, j) -> bool:
    """"you" is the subject only at the start of a clause, not after a verb."""
    return prev(R, brk, j) in CLAUSE_START | {""}


def find_features(R: list[str], brk: list[bool]) -> list[tuple[str, int, int, str]]:
    """Every dialect feature in the reference: (feature, start, end, note)."""
    found = []
    n = len(R)
    for i, tok in enumerate(R):
        nxt = R[i + 1] if i + 1 < n and not brk[i + 1] else ""

        # habitual be: subject (adverbs) be, not a question, not after a modal or "to"
        if tok == "be":
            j = subject_before(R, brk, i)
            if j is not None and R[j] in {"i", "you", "he", "she", "it", "we", "they", "people",
                                          "everybody", "somebody", "kids", "folks", "this"}:
                if R[j] == "you" and not you_is_subject(R, brk, j):
                    continue
                # "whether it be", "let these kids be kids": standard English.
                if prev(R, brk, j) in OBJECT_BEFORE | AUX | {"to", "let", "whether"}:
                    continue
                if "let" in R[max(0, j - 2):j]:
                    continue
                found.append(("habitual-be", j, i + 1, f"{R[j]} be {nxt}".strip()))

        # zero copula: he/she/they/we/you then -ing, a place or an adjective
        if tok in {"he", "she", "they", "we", "you"} and nxt:
            p = prev(R, brk, i)
            if p in AUX or (tok == "you" and not you_is_subject(R, brk, i)):
                continue
            if is_ing_verb(nxt) or nxt in PLACE or nxt in ADJECTIVES:
                if nxt == "not" and i + 2 < n and R[i + 2] in {"be", "never"}:
                    continue
                found.append(("zero-copula", i, i + 2, f"{tok} {nxt}"))

        # ain't
        if tok == "aint":
            found.append(("aint", i, i + 1, "aint"))

        # third person singular with no -s: he/she/it + bare verb, or "he don't"
        if tok in {"he", "she", "it"}:
            # "it" is also an object ("keeping it clean"), so it counts only at
            # the start of a clause, like "you".
            if tok == "it" and not you_is_subject(R, brk, i):
                pass
            elif prev(R, brk, i) not in OBJECT_BEFORE | AUX:
                k = i + 1
                while k < n and not brk[k] and R[k] in ADVERBS - {"all"}:
                    k += 1
                if k < n and not brk[k]:
                    verb = R[k]
                    after = R[k + 1] if k + 1 < n and not brk[k + 1] else ""
                    # "he do" without "not" is too often a cut-off "he do- does it".
                    if (verb == "do" and after == "not") or (verb in BASE_VERBS - {"do"}):
                        found.append(("third-person-s", i, k + 1, f"{tok} {verb}"))

        # was with a plural subject
        if tok == "was":
            j = i - 1
            if j >= 0 and not brk[i]:
                subject = R[j]
                if subject == "all" and j > 0 and not brk[j] and R[j - 1] in {"you", "we", "they"}:
                    j -= 1
                    subject = R[j]
                if subject in {"they", "we"} or (subject == "you" and you_is_subject(R, brk, j)):
                    found.append(("was-levelling", j, i + 1, " ".join(R[j:i + 1])))

        # negative concord: not/never/ain't, then within three words no/nobody/nothing
        if tok in NEG_FIRST:
            for k in range(i + 1, min(n, i + 5)):
                if brk[k] or R[k] in {"and", "but", "or", "because", "cause", "if", "so"}:
                    break
                if R[k] in NEG_WORDS:
                    # "I don't know, no" and "I don't No.": the no is an answer.
                    if R[k] == "no" and (R[k - 1] == "know" or k + 1 >= n or brk[k + 1]):
                        break
                    found.append(("negative-concord", i, k + 1, " ".join(R[i:k + 1])))
                    break

        # existential it: it is/was/ain't + no / plenty / many / a lot of + plural
        if tok == "it" and nxt in {"is", "was", "aint"}:
            rest = [R[k] for k in range(i + 2, min(n, i + 6)) if not any(brk[i + 2:k + 1])]
            plural = lambda w: w.endswith("s") or w in {"people", "folks", "kids", "children", "men", "women", "stuff", "money", "crime", "violence", "drugs"}  # noqa: E731
            hit = False
            if len(rest) >= 2 and rest[0] in {"no", "plenty", "many"}:
                hit = not (rest[0] == "no" and rest[1:2] and rest[1] in NOT_EXISTENTIAL)
            if rest[:3] == ["a", "lot", "of"] and len(rest) > 3 and plural(rest[3]):
                hit = True
            if rest[:1] == ["some"] and len(rest) > 1 and plural(rest[1]):
                hit = True
            if hit and prev(R, brk, i) not in {"that", "what", "because", "cause"}:
                found.append(("existential-it", i, i + 2, " ".join([tok, nxt] + rest[:3])))

        # completive done: subject done + past tense verb
        if tok == "done" and (nxt in PAST or (nxt.endswith("ed") and len(nxt) > 4)):
            j = i - 1
            if j >= 0 and not brk[i] and R[j] in {"i", "you", "he", "she", "we", "they", "it"}:
                if prev(R, brk, j) not in AUX:
                    found.append(("completive-done", j, i + 1, f"{R[j]} done {nxt}"))

        if tok == "finna":
            found.append(("finna", i, i + 1, "finna"))
    return found


IRREGULAR_PAST = {"say": "said", "go": "went", "have": "had", "do": "did", "get": "got",
                  "make": "made", "take": "took", "think": "thought", "feel": "felt",
                  "keep": "kept", "tell": "told", "know": "knew", "mean": "meant", "pay": "paid",
                  "leave": "left", "teach": "taught", "wear": "wore", "sleep": "slept",
                  "buy": "bought", "send": "sent", "understand": "understood", "drive": "drove"}


def past_forms(verb: str) -> set[str]:
    """called, stayed, tried, said, went..."""
    if verb in IRREGULAR_PAST:
        return {IRREGULAR_PAST[verb]}
    if verb.endswith("e"):
        return {verb + "d"}
    if verb.endswith("y") and verb[-2:-1] not in "aeiou":
        return {verb[:-1] + "ied"}
    return {verb + "ed", verb + verb[-1] + "ed"}


def judge(feature: str, ref: list[str], core: list[str], before: list[str],
          after: list[str], following: list[str] = (), preceding: list[str] = ()) -> tuple[str, str]:
    """(outcome, how). The outcome is kept, standardised, dropped (the feature
    word left out, nothing in its place) or other (misheard, or the subject lost);
    `how` says in a few words what the standard form was. `following` is the
    reference tokens just after the stretch and `preceding` the ones just
    before it, up to three each way and never across a break."""
    if core == ref:
        return "kept", ""
    full = before + core + after
    tail = core[1:] + after
    if feature == "habitual-be":
        if "be" not in core and set(tail) & (AUX | {"being", "been"}):
            return "standardised", "be -> " + " ".join(t for t in tail if t in AUX | {"being", "been"})
        modal = set(core[1:]) & {"will", "would", "could", "should", "can", "might", "to"}
        if modal and "be" in core:
            return "standardised", f"{sorted(modal)[0]} added before be"
        return ("dropped", "be left out") if core == ref[:-1] else ("other", "")
    if feature == "zero-copula":
        added = set(core[1:-1]) & (FINITE_BE | {"has", "have"})
        if len(core) >= 3 and added:
            return "standardised", f"{sorted(added)[0]} added"
        return "other", ""
    if feature == "aint":
        if "aint" not in full and ({"not", "never"} & set(full)):
            return "standardised", "ain't -> " + " ".join(core or after)
        if not core and "aint" in list(following[:2]) + list(preceding[-2:]):
            return "other", "one of two ain'ts left out (a restart)"
        if not core and set(following[:3]) & ({"never"} | NEG_WORDS):
            # "I ain't never understood" -> "I never understood": the double
            # negative undone, which is standard English.
            negative = next(t for t in following[:3] if t in {"never"} | NEG_WORDS)
            return "standardised", f"ain't left out before {negative}"
        # Otherwise leaving it out turns the sentence positive: "I ain't have
        # the slightest idea" -> "I have the slightest idea".
        return ("dropped", "ain't left out, sentence now positive") if not core else ("other", "")
    if feature == "third-person-s":
        verb = ref[-1]
        written = set(core[1:] + after[:1])
        if written & third_person(verb) or (verb == "do" and "does" in full):
            return "standardised", "-s added"
        if written & past_forms(verb) or (verb == "do" and "did" in full):
            return "standardised", "made past tense"
        return "other", ""
    if feature == "was-levelling":
        return ("standardised", "was -> were") if "were" in core else ("other", "")
    if feature == "negative-concord":
        swapped = set(core) & (ANY_WORDS - {"a"})
        if swapped:
            return "standardised", f"{ref[-1]} -> {sorted(swapped)[0]}"
        negatives = sum(t in NEG_FIRST | NEG_WORDS for t in core)
        if negatives == 1 and ref[-1] in core:
            return "standardised", f"{ref[0]} left out, {ref[-1]} kept"
        if negatives == 1 and set(core) & {"a", "an"}:
            return "standardised", f"{ref[-1]} -> a"
        return "other", ""
    if feature == "existential-it":
        if core[:1] == ["there"] or before[-1:] == ["there"]:
            return "standardised", "it -> there"
        return "other", ""
    if feature == "completive-done":
        if "done" not in core and set(core) & {"have", "has", "had", "already"}:
            return "standardised", "done -> " + " ".join(set(core) & {"have", "has", "had", "already"})
        return ("dropped", "done left out") if core == ref[:1] else ("other", "")
    if feature == "finna":
        if set(full) & {"going", "about", "fixing", "gonna", "fitting", "trying"}:
            return "standardised", "finna -> " + " ".join(core)
        return ("dropped", "finna left out") if not core else ("other", "")
    return "other", ""


def find_restarts(R: list[str], brk: list[bool], reference_words, ref_source, turns) -> list[tuple]:
    """Repeated words and phrases inside one turn: "I I", "it was it was".

    A sentence mark between the two copies ("No. No.") or a change of turn rules
    it out; a comma or a dash between them is how a restart is written. Words
    people say twice on purpose ("very very", "no no", "that that") are left out.
    """
    found = []
    i, n = 0, len(R)
    while i < n:
        hit = None
        for size in (3, 2, 1):
            a, b = R[i:i + size], R[i + size:i + 2 * size]
            if len(b) < size or a != b:
                continue
            if any(ch.isdigit() for ch in "".join(a)) or set(a) <= SAID_TWICE:
                continue
            # A lone letter is a cut-off word ("f- f- thankfully"), not a word said twice.
            if size == 1 and len(a[0]) == 1 and a[0] not in ("i", "a"):
                continue
            first, last = ref_source[i], ref_source[i + 2 * size - 1]
            if turns[first] != turns[last]:
                continue
            # The two copies must be separate words in the record, not one word
            # the rule split in two ("do not" from "don't" said twice is fine).
            middle = reference_words[ref_source[i + size - 1]:ref_source[i + size]]
            # Spelt the same in the record too: "2254(a), a" is a statute letter
            # and then the article, not "a" said twice.
            spelt = lambda ks: re.sub(r"[^a-z0-9']", "", "".join(  # noqa: E731
                reference_words[k].lower() for k in sorted({ref_source[x] for x in ks})))
            if spelt(range(i, i + size)) != spelt(range(i + size, i + 2 * size)):
                continue
            if any(re.search(r"[.?!;:]$", w) for w in middle):
                continue
            dash = any("-" in w for w in middle)
            hit = (size, dash)
            break
        if hit:
            size, dash = hit
            found.append(("restart", i, i + 2 * size, f"{'dash ' if dash else ''}repeat of {size} word{'s' if size > 1 else ''}"))
            i += 2 * size
        else:
            i += 1
    return found


def judge_restart(view: EngineView, a: int, b: int) -> tuple[str, str]:
    """kept (both copies written), dropped (one copy written, the other left out) or other."""
    size = (b - a) // 2
    equal = sum(view.equal[a:b])
    nothing = sum(view.at[i] is None for i in range(a, b))
    if equal == 2 * size and not any(view.gaps.get(g) for g in range(a + 1, b)):
        return "kept", ""
    if equal == size and nothing == size:
        return "dropped", "written once"
    return "other", ""


# ---------------------------------------------------------------------------
# One recording
# ---------------------------------------------------------------------------

def record_context(reference_words, ref_source, a, b) -> str:
    s0, s1 = ref_source[a], ref_source[b - 1]
    return (f"{' '.join(reference_words[max(0, s0 - CONTEXT):s0])} "
            f"[{' '.join(reference_words[s0:s1 + 1])}] "
            f"{' '.join(reference_words[s1 + 1:s1 + 1 + CONTEXT])}").strip()


def sides_right(view: EngineView, a: int, b: int) -> bool:
    """Whether the engine wrote the reference words just before and just after
    the stretch. Where it did, it was plainly following the speaker there, so
    what it did inside the stretch is a choice, not a stretch it lost track of."""
    return (a == 0 or view.equal[a - 1]) and (b >= len(view.ref) or view.equal[b])


def check(job: dict) -> list[dict]:
    """Every feature and restart in one recording, with each engine's outcome."""
    lined = lineup.load(job)
    names = [e for e in ENGINES if e in lined]
    transcript, reference_words, alignment, _ = lined[names[0]]
    R = alignment.reference.tokens
    ref_source = alignment.reference.source_index
    turns = lineup.word_turns(transcript)
    brk = breaks(reference_words, ref_source, turns)
    views = {name: EngineView(lined[name][2], lined[name][3]) for name in names}

    stretches = find_restarts(R, brk, reference_words, ref_source, turns)
    if job["corpus"] == "coraal":
        stretches = find_features(R, brk) + stretches

    rows = []
    for subkind, a, b, note in stretches:
        # A stray CORAAL mark ("/Ain't" with one slash) the corpus reader let through.
        if any("/" in w for w in reference_words[ref_source[a]:ref_source[b - 1] + 1]):
            continue
        outcome, how = {}, {}
        for name, view in views.items():
            if subkind == "restart":
                outcome[name], how[name] = judge_restart(view, a, b)
            else:
                before, after = view.edges(a, b)
                following = []
                for k in range(b, min(len(R), b + 3)):
                    if brk[k]:
                        break
                    following.append(R[k])
                preceding = []
                for k in range(a - 1, max(-1, a - 4), -1):
                    if brk[k + 1]:
                        break
                    preceding.insert(0, R[k])
                outcome[name], how[name] = judge(subkind, R[a:b], view.core(a, b), before, after,
                                                 following, preceding)
        turn = transcript.turns[turns[ref_source[a]]]
        for name, view in views.items():
            start, end = view.times(a, b)
            rows.append({
                "corpus": job["corpus"], "part": job["term"], "recording": job["docket"],
                "engine": name, "kind": "edits", "subkind": subkind,
                "start": start, "end": end,
                "record": " ".join(reference_words[ref_source[a]:ref_source[b - 1] + 1]),
                "engine_wrote": view.written(a, b),
                "record_context": record_context(reference_words, ref_source, a, b),
                "engine_context": view.context(a, b),
                "others_right": " ".join(o for o in names if o != name and outcome[o] == "kept"),
                "outcome": outcome[name],
                "how": how[name],
                "record_tokens": " ".join(R[a:b]),
                "engine_tokens": " ".join(view.core(a, b)),
                "note": note,
                "speaker": getattr(turn, "speaker", ""),
                "interviewer": "_int_" in str(getattr(turn, "speaker", "")),
                "sides_right": sides_right(view, a, b),
                "ref_index": a,
            })
    return rows


def evidence(row: pd.Series) -> str:
    """One short line: the feature, what each side has, who kept it."""
    label = {"habitual-be": "habitual be", "zero-copula": "no is/are",
             "aint": "ain't", "third-person-s": "verb with no -s",
             "was-levelling": "was with a plural subject",
             "negative-concord": "double negative", "existential-it": "it for there",
             "completive-done": "completive done", "finna": "finna",
             "restart": "restart"}[row["subkind"]]
    kept = f"; {row['others_right'].replace(' ', ' and ')} kept it" if row["others_right"] else "; no engine kept it"
    how = f" ({row['how']})" if row["how"] else ""
    first = row["note"] if row["subkind"] == "restart" else label
    return f"{first}: record '{row['record_tokens']}', engine '{row['engine_tokens']}'{how}{kept}"


def hours_of(jobs: list[dict]) -> dict[tuple, float]:
    """Hours of audio per (corpus, part). The Supreme Court has no lengths
    listed, so there it is the last word any engine timed."""
    hours = {}
    for corpus in {j["corpus"] for j in jobs}:
        wanted = {j["docket"] for j in jobs if j["corpus"] == corpus}
        if corpus != "scotus":
            for line in (lineup.corpus_root(corpus) / "recordings.jsonl").read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                if entry["id"] in wanted:
                    key = (corpus, entry["split"])
                    hours[key] = hours.get(key, 0) + entry["duration"] / 3600
    return hours


def load_with_retry(job: dict, tries: int = 20):
    """The cache is still being filled; a half-written file gets a second go."""
    import gzip
    for attempt in range(tries):
        try:
            return check(job)
        except (EOFError, gzip.BadGzipFile, OSError) as error:
            if attempt == tries - 1:
                raise
            print(f"  {job['docket']}: {type(error).__name__}, waiting", flush=True)
            time.sleep(15)


# ---------------------------------------------------------------------------

def pct(part: pd.Series, whole: pd.Series) -> pd.Series:
    return (100 * part / whole.where(whole > 0)).round(1)


def rate_table(table: pd.DataFrame, keys: list[str], outcomes: list[str]) -> pd.DataFrame:
    """Per group: how many places, and the share of each outcome. `other`
    takes in every outcome not listed. Then the same for the clear places only
    (the engine wrote the words either side right)."""
    out = None
    for scope, rows in (("", table), ("clear_", table[table["sides_right"]])):
        named = rows["outcome"].where(rows["outcome"].isin(outcomes), "other")
        counts = (rows.assign(outcome=named).groupby(keys + ["outcome"]).size()
                  .unstack("outcome", fill_value=0))
        for column in outcomes + ["other"]:
            if column not in counts:
                counts[column] = 0
        part = pd.DataFrame({f"{scope}in_record": counts[outcomes + ["other"]].sum(axis=1)})
        for column in outcomes + ["other"]:
            part[f"{scope}{column}_pct"] = pct(counts[column], part[f"{scope}in_record"])
        if not scope:
            for column in outcomes + ["other"]:
                part[column] = counts[column]
            if "dropped" not in outcomes:
                part["of_which_dropped"] = (rows["outcome"] == "dropped").groupby(
                    [rows[k] for k in keys]).sum()
        out = part if out is None else out.join(part, how="left")
    return out.reset_index()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", nargs="+", choices=list(lineup.PARTS),
                        default=["coraal", "earnings22", "edacc", "scotus"])
    parser.add_argument("--limit", type=int, help="only the first N recordings of each part")
    parser.add_argument("--show", metavar="FEATURE",
                        help="print every instance of one feature (one line per place)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    jobs = []
    for corpus in args.corpus:
        for part in lineup.PARTS[corpus]:
            some = lineup.recordings(corpus, [part])
            jobs += some[:args.limit] if args.limit else some
    print(f"{len(jobs)} recording(s)")

    started = time.monotonic()
    rows, scotus_hours = [], {}
    for number, job in enumerate(jobs, 1):
        found = load_with_retry(job)
        rows += found
        if job["corpus"] == "scotus":
            lined = lineup.load(job)
            last = max((w[3][-1].end for w in lined.values() if w[3]), default=0)
            scotus_hours[("scotus", job["term"])] = scotus_hours.get(("scotus", job["term"]), 0) + last / 3600
        if number % 25 == 0 or number == len(jobs):
            print(f"[{number}/{len(jobs)}] {(time.monotonic() - started) / 60:.1f} min", flush=True)

    table = pd.DataFrame(rows)
    table["engine_tokens"] = table["engine_tokens"].fillna("")
    table["how"] = table["how"].fillna("")
    table["evidence"] = table.apply(evidence, axis=1)

    if args.show:
        one = table[(table["subkind"] == args.show) & (table["engine"] == table["engine"].iloc[0])]
        for row in one.itertuples():
            print(f"{row.recording} {row.start:>8} | {row.record_context}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    extra = ["outcome", "how", "sides_right", "speaker", "interviewer", "note", "record_tokens",
             "engine_tokens"]
    # Every dialect place with every engine's outcome, kept or not, so the rates
    # can be checked by hand.
    is_dialect = table["subkind"] != "restart"
    table[is_dialect][SHARED + extra].to_csv(args.out / "dialect-instances.csv", index=False)
    candidates = table[table["outcome"].isin(["standardised", "dropped"])]
    candidates = candidates.sort_values(["corpus", "part", "recording", "start", "engine"])
    # The dialect cases are a few hundred rows. The restarts an engine wrote once
    # are tens of thousands (24 MB as plain text), so they go in a compressed file
    # of their own with the same columns, to keep the repository small.
    candidates[candidates["subkind"] != "restart"][SHARED + extra].to_csv(
        args.out / "candidates.csv", index=False)
    candidates[candidates["subkind"] == "restart"][SHARED + extra].to_csv(
        args.out / "restarts-dropped.csv.gz", index=False, compression="gzip")

    dialect = table[table["subkind"] != "restart"].rename(columns={"subkind": "feature",
                                                                    "part": "component"})
    if len(dialect):
        # ROC+PRV is the table quoted before Washington DC (DCB) was added; "all"
        # pools every component, DCB included.
        first_two = dialect[dialect["component"].isin(["ROC", "PRV"])]
        both = rate_table(first_two, ["feature", "engine"], ["kept", "standardised"])
        every = rate_table(dialect, ["feature", "engine"], ["kept", "standardised"])
        apart = rate_table(dialect, ["component", "feature", "engine"], ["kept", "standardised"])
        rates = pd.concat([every.assign(component="all"), both.assign(component="ROC+PRV"), apart])
        rates = rates[["component"] + [c for c in apart.columns if c != "component"]]
        order = {"all": 0, "ROC+PRV": 1, "ROC": 2, "PRV": 3, "DCB": 4, "ATL": 5, "DCA": 6,
                 "DTA": 7, "LES": 8, "VLD": 9}
        rates = rates.sort_values(["component", "feature", "engine"],
                                  key=lambda c: c.map(order) if c.name == "component" else c)
        rates.to_csv(args.out / "dialect-rates.csv", index=False)
        print(rates[rates["component"] == "all"].iloc[:, :7].to_string(index=False))

    restarts = table[table["subkind"] == "restart"]
    restart_rates = rate_table(restarts, ["corpus", "engine"], ["kept", "dropped"])
    restart_rates.to_csv(args.out / "restart-rates.csv", index=False)
    print(restart_rates.to_string(index=False))

    # One row for every corpus, part and engine, zero where nothing was found.
    hours = hours_of(jobs) | scotus_hours
    grid = table[["corpus", "part", "engine"]].drop_duplicates()
    found = candidates.groupby(["corpus", "part", "engine"]).agg(
        candidates=("subkind", "size"),
        dialect_changed=("subkind", lambda s: int((s != "restart").sum())),
        restarts_dropped=("subkind", lambda s: int((s == "restart").sum()))).reset_index()
    counts = grid.merge(found, how="left").fillna(0)
    counts["recordings"] = counts.apply(lambda r: sum(
        1 for j in jobs if (j["corpus"], j["term"]) == (r["corpus"], r["part"])), axis=1)
    counts["hours"] = counts.apply(lambda r: round(hours.get((r["corpus"], r["part"]), 0), 1), axis=1)
    counts["candidates_per_hour"] = (counts["candidates"] / counts["hours"]).round(2)
    counts = counts.astype({"candidates": int, "dialect_changed": int, "restarts_dropped": int})
    counts = counts[["corpus", "part", "engine", "recordings", "hours", "candidates",
                     "candidates_per_hour", "dialect_changed", "restarts_dropped"]]
    counts = counts.sort_values(["corpus", "part", "engine"])
    counts.to_csv(args.out / "counts.csv", index=False)
    print(counts.to_string(index=False))
    print(f"in {(time.monotonic() - started) / 60:.1f} min -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Stop the comparison from inventing differences nobody could hear.

Reading 157 flagged spots by hand (`flagged-spots-review.md`) showed that about a
fifth of them were not differences at all. The scoring had made them:

- Whisper's normaliser deletes anything in parentheses, so "3553(e)" lost its
  "e" and every model that said it was charged with adding a word.
- It turns every 's into "is", so "Vogt's" became "vogt is" and could never
  match "votes", though the two sound the same.
- Hyphens split a word in two: "e-mails" became "e mails", "emails" stayed one.
- The same thing written two ways - "all right" and "alright", "$10" and
  "10 dollars", "U.S.C." and "usc" - counted as different words.

The fixes come in two strengths, because the rules ask different questions.

`fix_words` (for `standard` and `lowercase_nopunct`)
    These rules ask "are the words the same?" So anything that sounds identical
    is made identical: subsection letters kept, possessives and plurals merged,
    initialisms joined, the alternate forms in ALTERNATES mapped to one form.

`fix_words_verbatim` (for `verbatim`)
    This rule asks "is it the same record?" Style still counts - "Article III"
    against "Article 3" is a real difference in a transcript. Only spellings a
    reporter is allowed to choose between are forgiven: a hyphenated, spaced or
    joined compound. Possessives are left alone, because where the apostrophe
    goes is part of a correct record.

After each side is normalised, `join_compounds` merges two neighbouring tokens
when the joined word appears anywhere in either text. It is applied to both
sides the same way, so "a part" and "apart" become one form wherever they
occur. They sound the same, so the comparison should not tell them apart.
"""

from __future__ import annotations

import re

#: Words whose 's is "is", "has" or "us", never a possessive.
CONTRACTED = {
    "it", "that", "there", "here", "what", "who", "he", "she", "where", "how", "when",
    "why", "let", "this", "everyone", "everybody", "nobody", "somebody", "someone",
    "everything", "something", "nothing", "one", "which", "anyone", "anybody",
}

#: Roman numerals as they appear after "Article", "Title" and the like.
ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7",
         "viii": "8", "ix": "9", "x": "10", "xi": "11", "xii": "12", "xiii": "13", "xiv": "14"}
ROMAN_AFTER = {"article", "title", "chapter", "part", "patchak"}

#: The same word written different ways. Keys are compared in lower case, with
#: surrounding punctuation stripped. Edit freely: this is a list of judgement
#: calls, and the person making them should be a court reporter.
ALTERNATES = {
    "alright": "all right",
    "ok": "okay",
    "o.k.": "okay",
    "mt.": "mount",
    "mt": "mount",
    "uh-huh": "uhhuh",
    "uh-hum": "uhhuh",
    "mm-hmm": "uhhuh",
    "mm-hm": "uhhuh",
    "mhm": "uhhuh",
    "mm-mm": "mmmm",
    "uh-uh": "uhuh",
}

#: An apostrophe is not counted as edge punctuation: in "Respondents'" it is
#: part of the possessive, which is handled on its own.
_EDGE_PUNCT = re.compile(r"^([\"(\[]*)(.*?)([\")\].,;:?!]*)$")
_SUBSECTION = re.compile(r"\(([A-Za-z0-9]{1,4})\)")
_INITIALISM = re.compile(r"^(?:[A-Za-z]\.){2,}$")
_DIGIT_LETTER = re.compile(r"(\d)([A-Za-rt-z])$")
_LETTER_DIGIT = re.compile(r"^([A-Za-z])(\d{1,3})$")
_POSSESSIVE = re.compile(r"^(.*?)(['’]s|s['’])$")
_INNER_HYPHEN = re.compile(r"(?<=\w)-(?=\w)")


def _split_edges(word: str) -> tuple[str, str, str]:
    """Leading punctuation, the word itself, trailing punctuation."""
    match = _EDGE_PUNCT.match(word)
    return match.group(1), match.group(2), match.group(3)


#: A piece of a word that the engine's timings split off: ".S." of "U.S.",
#: ",000" of "$5,000", "'Connor" of "O'Connor".
_SPLIT_PIECE = re.compile(r"^[.,'’%]\S*$")


def _glue_pieces(words: list[str]) -> tuple[list[str], list[int]]:
    """Put back together words the timings split at punctuation.

    Returns the glued words and, for each, the position of its first piece.
    """
    glued, first = [], []
    for i, word in enumerate(words):
        word = word.strip()  # some engines keep a leading space: " arm's"
        if glued and _SPLIT_PIECE.match(word) and (any(ch.isalnum() for ch in word) or word == "%"):
            glued[-1] += word
        else:
            glued.append(word)
            first.append(i)
    return glued, first


def fix_words(words: list[str]) -> list[list[str]]:
    """The word-level fixes for the two rules that compare words, not records.

    Returns one list per input word, because a fix can turn one word into two
    ("3553(e)" into "3553 e") and the caller needs to know where each piece came
    from. A word glued onto the one before it gets an empty list.
    """
    glued, first = _glue_pieces(words)
    fixed = _fix_glued(glued)
    out: list[list[str]] = [[] for _ in words]
    for position, pieces in zip(first, fixed):
        out[position] = pieces
    return out


def _fix_glued(words: list[str]) -> list[list[str]]:
    out = []
    for i, word in enumerate(words):
        # Subsection letters first, before the closing parenthesis can be
        # mistaken for punctuation: "3553(e)." -> "3553 e .", "(b)(1)" -> "b 1".
        if _SUBSECTION.search(word):
            pieces = [p for p in _SUBSECTION.sub(r" \1 ", word).split()
                      if any(ch.isalnum() for ch in p)]
            out.append([p for fixed in _fix_glued(pieces) for p in fixed] or [word])
            continue
        lead, core, trail = _split_edges(word)
        low = core.lower()
        previous = _split_edges(words[i - 1])[1].lower().split("-")[-1] if i else ""
        following = _split_edges(words[i + 1])[1].lower() if i + 1 < len(words) else ""

        if low in ALTERNATES:
            core = ALTERNATES[low]
        elif (low + trail[:1]) in ALTERNATES:  # "O.K." keeps its last full stop in trail
            core, trail = ALTERNATES[low + trail[:1]], trail[1:]
        elif low in ROMAN and previous in ROMAN_AFTER:
            core = ROMAN[low]
        elif _INITIALISM.match(core + trail[:1]) and trail[:1] == ".":
            core, trail = (core + ".").replace(".", ""), trail[1:]
        elif _INITIALISM.match(core):
            core = core.replace(".", "")
        elif core.startswith("$") and core[1:].replace(",", "").replace(".", "").isdigit():
            core = core[1:] + (" dollar" if core[1:] == "1" else " dollars")
        elif core.endswith("%") and core[:-1].replace(".", "").isdigit():
            core = core[:-1] + " percent"

        # "3553e" -> "3553 e" and "B9" -> "B 9", so they line up with the
        # official "3553(e)" and "(b)(9)".
        core = _DIGIT_LETTER.sub(r"\1 \2", core)
        core = _LETTER_DIGIT.sub(r"\1 \2", core)

        # Possessives and plurals sound the same: "Vogt's", "Vogts'" and "Vogts".
        possessive = _POSSESSIVE.match(core)
        if possessive and " " not in core:
            base = possessive.group(1)
            if base.lower() in CONTRACTED:
                if following in ("been", "got", "gotten"):
                    core = base + " has"
            else:
                core = base + "s" if not base.lower().endswith("s") else base

        out.append(f"{lead}{core}{trail}".split() or [word])
    return out


def fix_words_verbatim(words: list[str]) -> list[list[str]]:
    """The verbatim fix: only a hyphen inside a word is forgiven."""
    return [[_INNER_HYPHEN.sub("", word)] for word in words]


def _key(token: str) -> str:
    """What two tokens are compared on when deciding to join them."""
    return _INNER_HYPHEN.sub("", token)


def join_compounds(
    tokens: list[str], source: list[int], vocabulary: set[str]
) -> tuple[list[str], list[int]]:
    """Merge neighbouring tokens whose joined form is a word in `vocabulary`.

    "e mails" becomes "emails" when "emails" is used anywhere in either text.
    Repeats until nothing changes, so "u s c" can become "usc". The merged
    token keeps the first piece's source position.
    """
    tokens, source = list(tokens), list(source)
    changed = True
    while changed:
        changed = False
        out_t, out_s, i = [], [], 0
        while i < len(tokens):
            if i + 1 < len(tokens):
                joined = tokens[i] + tokens[i + 1]
                # Verbatim tokens carry punctuation: join only when the first
                # piece has none of its own at the end.
                letters = len(tokens[i]) == len(tokens[i + 1]) == 1  # "d c" -> "dc"
                # A repeated word is a stammer, never a compound: "I -- I"
                # must not become "ii" just because "Title II" is in the text.
                repeat = tokens[i] == tokens[i + 1]
                if (joined in vocabulary and (len(joined) >= 4 or letters)
                        and not repeat and tokens[i][-1:].isalnum()):
                    out_t.append(joined)
                    out_s.append(source[i])
                    i += 2
                    changed = True
                    continue
            out_t.append(tokens[i])
            out_s.append(source[i])
            i += 1
        tokens, source = out_t, out_s
    return tokens, source

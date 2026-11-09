"""Build the project website from the findings: a front page, one page per data set,
a page comparing the data sets, and a data page.

The website leads with where speech recognition goes wrong in a way that matters,
sorted by what an error does to a reader: says the opposite, gets a fact wrong,
adds words nobody said, leaves out what was said, rewrites how the speaker talks.
The sorting leans on the machine judges' answers (findings/judge/) and is
preliminary. Every data set gets the same page, from one template: a link to the
data set, the big picture, who wrote its reference transcript, the cards, then the
numbers.

    python tools/build_data.py            # first: the data page's tables
    python tools/build_site.py            # the pages, reusing clips already cut
    python tools/build_site.py --clips    # cut the cards' clips again first

Writes site/index.html, site/<data set>.html, site/compare.html,
site/data.html and site/ai.html (how AI was used), assembled from the shared widgets in web/widget/ and the
templates in tools/site_page/, with one block of data each.

Cards: each plays about 15 and about 30 seconds, cut to fall between sentences
where it can (tools/clips.py, snap_window); clips go to site/clips/failures/ (not
in git). Supreme Court audio is public domain; EdAcc's is CC BY-SA 4.0 and
CORAAL's CC BY-NC-SA 4.0, and each page credits its corpus; Earnings-22's cards
are text only. Cutting needs the runs and the corpora on the 5090 laptop.
Published as a private claude.ai artifact, with the other pages, the clips and
site/data/ as files beside the front page. The whole-recording pages
(tools/build_explorer.py) are artifacts of their own, listed in
tools/explorer_page/published.json.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
FINDINGS = CAPSTONE / "findings"
FAILURES = FINDINGS / "failures"
SITE = CAPSTONE / "site"
WIDGETS = CAPSTONE / "web" / "widget"
PAGES = CAPSTONE / "tools" / "site_page"
CARD_CLIPS = SITE / "clips" / "failures"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(CAPSTONE / "pipeline"))

TERMS = ["OT2010", "OT2017", "OT2021", "OT2025"]
ENGINE_NAMES = {"Qwen3": "Qwen3-ASR 1.7B", "Whisper": "Whisper large-v3", "Voxtral": "Voxtral Mini 3B",
                "Canary": "Canary 1B v2", "Parakeet": "Parakeet TDT 0.6B", "Granite": "Granite 4.1 2B",
                "Granite Plus": "Granite 4.1 2B Plus"}

#: What each data set's page says about itself. The rest of the page is the same
#: for all of them, filled from findings/.
DATASETS = {
    "scotus": {
        "name": "Supreme Court", "file": "scotus.html", "unit": "arguments",
        "engines": ["Qwen3", "Whisper", "Parakeet"],
        "title": "The Supreme Court: the engines against the official record",
        "lede": "Oral arguments from four terms, 2010 to 2025, transcribed by three engines and checked word by word against the Court's own transcript, made by a professional court reporter.",
        "extras": ["odds"],
        "credit": "Supreme Court audio and transcripts are public domain.",
    },
    "edacc": {
        "name": "EdAcc", "file": "edacc.html", "unit": "conversations",
        "engines": ["Qwen3", "Whisper", "Parakeet", "Canary", "Granite"],
        "title": "EdAcc: friends talking on video calls, in many accents of English",
        "lede": "Conversations from the Edinburgh International Accents of English Corpus. Many of the speakers learned English as a second language. Its reference has no capitals or punctuation, so only the benchmark rule is fair here.",
        "extras": ["odds"],
        "credit": "Audio: EdAcc, the Edinburgh International Accents of English Corpus (Sanabria et al. 2023), CC BY-SA 4.0, clipped.",
    },
    "coraal": {
        "name": "CORAAL", "file": "coraal.html", "unit": "interviews",
        "engines": ["Qwen3", "Whisper", "Parakeet"],
        "title": "CORAAL: interviews in African American English",
        "lede": "Sociolinguistic interviews from the Corpus of Regional African American Language, from eight places and times: Rochester, New York (2016), Princeville, North Carolina (2004), Washington, DC (1968 and 2015-17), Detroit (1966), Atlanta (2017-18), Valdosta, Georgia (2017-19) and New York's Lower East Side (2008-09). The 1960s ones were recorded on reel-to-reel tape. Its transcripts keep the speakers' own grammar, so they show when an engine rewrites it.",
        "extras": [],
        "credit": "Audio: CORAAL (Kendall & Farrington 2023; ROC: King et al. 2020; PRV: Rowe et al. 2018; DCB: Kendall et al. 2018), CC BY-NC-SA 4.0, clipped. Names and places are bleeped in the original recordings. Every part's authors are listed on the data page.",
    },
    "earnings22": {
        "name": "Earnings-22", "file": "earnings22.html", "unit": "calls",
        "engines": ["Qwen3", "Whisper", "Parakeet"],
        "title": "Earnings-22: company earnings calls, in accented English",
        "lede": "Earnings calls from companies in 27 countries, many of the speakers using English as a second language, some over the phone. Rev's transcribers wrote the reference word for word, fillers and false starts included. Three of the calls are in Korean with an English interpreter, and the reference has only the English.",
        "extras": [],
        # The calls' audio has no stated licence, so no clips are cut from it.
        "clips": False,
        "credit": "Earnings-22 (Del Rio et al. 2022): transcripts CC BY-SA 4.0. The audio has no stated licence, so none of it is played here.",
    },
}
#: Where each data set comes from and who wrote its reference ("true") transcript,
#: shown in a box of its own on each page. Links checked on 29 Oct 2026.
SOURCES = {
    "scotus": {
        "home": ["supremecourt.gov: oral argument transcripts", "https://www.supremecourt.gov/oral_arguments/argument_transcript/2025"],
        "links": [["Argument audio", "https://www.supremecourt.gov/oral_arguments/argument_audio/2025"],
                  ["A transcript by Heritage (2026)", "https://www.supremecourt.gov/oral_arguments/argument_transcripts/2025/25-466_ec8f.pdf"],
                  ["A transcript by Alderson (2017)", "https://www.supremecourt.gov/oral_arguments/argument_transcripts/2016/16-399_3f14.pdf"],
                  ["Heritage Reporting Corporation", "https://www.hrcreporters.com/"]],
        "by": "Professional court reporters under contract to the Court. The Court's transcripts page says: “Heritage Reporting Corporation provides the oral argument transcripts that are posted on this website on the same day an argument is heard.” Before the 2017 term it was Alderson Reporting Company; each transcript's cover page names the firm. Same-day transcripts are “considered official but subject to final review.”",
        "licence": "Made by the federal government. The Court's pages state no licence; U.S. government works are not under copyright.",
        "cite": "Supreme Court of the United States, oral argument audio and transcripts, 2010-2025 terms.",
    },
    "edacc": {
        "home": ["EdAcc at the University of Edinburgh", "https://groups.inf.ed.ac.uk/edacc/"],
        "links": [["Download (Edinburgh DataShare, v1.0)", "https://doi.org/10.7488/ds/7914"],
                  ["The paper (arXiv)", "https://arxiv.org/abs/2303.18110"]],
        "by": "Professional transcribers from a transcription company the paper does not name. The paper says: “All conversations were manually transcribed by multiple professional transcribers,” with overlaps, noise, laughter and hesitations marked; the authors then removed punctuation. So the reference is in capitals with no punctuation, and only the benchmark rule is fair here.",
        "licence": "CC BY-SA 4.0.",
        "cite": "Sanabria, Bogoychev, Markl, Carmantini, Klejch and Bell (2023), The Edinburgh International Accents of English Corpus: Towards the Democratization of English ASR, ICASSP 2023.",
    },
    "coraal": {
        "home": ["CORAAL, the Corpus of Regional African American Language", "https://oraal.github.io/coraal"],
        "links": [["Download (University of Oregon)", "https://lingtools.uoregon.edu/coraal/"],
                  ["CORAAL user guide (PDF)", "https://lingtools.uoregon.edu/coraal/userguide/CORAALUserGuide_current.pdf"]],
        "by": "The CORAAL project, in three rounds: an undergraduate research assistant transcribed each file, a graduate student in linguistics listened to the whole file and corrected it, and a third round marked names and places to be bleeped. The user guide says the aim is “not to make an exact, textually accurate representation of the speech”: grammar is kept as spoken (“was” for “were”), pronunciation is not.",
        "licence": "CC BY-NC-SA 4.0.",
        "cite": "Kendall and Farrington (2023), The Corpus of Regional African American Language, version 2023.06, Online Resources for African American Language Project, doi:10.7264/1ad5-6t35.",
    },
    "earnings22": {
        "home": ["Earnings-22 on GitHub (Rev)", "https://github.com/revdotcom/speech-datasets/tree/main/earnings22"],
        "links": [["The paper (arXiv)", "https://arxiv.org/abs/2203.15591"],
                  ["Rev on verbatim transcripts", "https://www.rev.com/resources/verbatim-transcription"]],
        "by": "Rev's own human transcription service. The paper says the files went to “our own human transcription platform”, each transcript was checked by “a separate group of graders”, and they “chose to produce verbatim transcriptions”: fillers, false starts and repeats included.",
        "licence": "Transcripts CC BY-SA 4.0. No source states a licence for the audio, so none of it is played on this site.",
        "cite": "Del Rio, Ha, McNamara, Miller and Chandra (2022), Earnings-22: A Practical Benchmark for Accents in the Wild, arXiv:2203.15591.",
    },
}

#: Who to credit for what the pages show, and what was changed, as each licence asks.
#: CORAAL's and EdAcc's citations are the ones their own guide and data page give.
_SAME = "These and the reference text shown here are shared under the same licence."
CREDITS = {
    "scotus": {
        "name": "Supreme Court", "uses": "Audio and transcripts of oral arguments.",
        "licence": "the Court's pages state none; U.S. government works are not under copyright",
        "licenceUrl": None, "source": ["supremecourt.gov", "https://www.supremecourt.gov/oral_arguments/"],
        "changed": "Audio cut into clips, joined into longer files or kept whole, and re-encoded at lower quality.",
        "cite": ["Supreme Court of the United States, oral argument audio and transcripts, 2010-2025 terms."],
    },
    "edacc": {
        "name": "EdAcc", "uses": "Audio and reference transcripts.",
        "licence": "CC BY-SA 4.0", "licenceUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source": ["Edinburgh DataShare", "https://doi.org/10.7488/ds/7914"],
        "changed": f"Audio cut into clips, joined into longer files or kept whole, and re-encoded at lower quality. {_SAME}",
        "cite": ["Sanabria, Ramon; Markl, Nina; Carmantini, Andrea; Klejch, Ondrej; Bell, Peter; Bogoychev, Nikolay. (2025). The Edinburgh International Accents of English Corpus, [dataset]. University of Edinburgh. School of Informatics. The Institute for Language, Cognition and Computation. The Centre for Speech Technology Research. https://doi.org/10.7488/ds/7914.",
                 "Sanabria, Bogoychev, Markl, Carmantini, Klejch and Bell (2023), The Edinburgh International Accents of English Corpus: Towards the Democratization of English ASR, ICASSP 2023."],
    },
    "coraal": {
        "name": "CORAAL", "uses": "Audio and reference transcripts, for non-commercial use.",
        "licence": "CC BY-NC-SA 4.0", "licenceUrl": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "source": ["The Online Resources for African American Language Project", "https://doi.org/10.7264/1ad5-6t35"],
        "changed": f"Audio cut into clips, joined into longer files or kept whole, and re-encoded at lower quality. Names and places are bleeped in the original recordings. {_SAME}",
        "cite": ["Kendall, Tyler and Charlie Farrington. 2023. The Corpus of Regional African American Language. Version 2023.06. Eugene, OR: The Online Resources for African American Language Project. https://doi.org/10.7264/1ad5-6t35."],
        "more": [
            "Farrington, Charlie, Tyler Kendall, Patrick Slay Brooks, Lucas Jenson, Chloe Tacata, and Jaidan McLean. 2020. The Corpus of Regional African American Language: ATL (Atlanta, GA 2017). Version 2020.05. Eugene, OR: The Online Resources for African American Language Project.",
            "Kendall, Tyler, Ralph Fasold, Charlie Farrington, Jason McLarty, Shelby Arnson, and Brooke Josler. 2018. The Corpus of Regional African American Language: DCA (Washington DC 1968). Version 2018.10.06. Eugene, OR: The Online Resources for African American Language Project.",
            "Fasold, Ralph. 1972. Tense marking in Black English: A linguistic and social analysis. Arlington, VA: Center for Applied Linguistics.",
            "Kendall, Tyler, Minnie Quartey, Charlie Farrington, Jason McLarty, Shelby Arnson, and Brooke Josler. 2018. The Corpus of Regional African American Language: DCB (Washington DC 2016). Version 2018.10.06. Eugene, OR: The Online Resources for African American Language Project.",
            "Shuy, Roger, Walt Wolfram, Charlie Farrington, Tyler Kendall, Jaidan McLean, and Chloe Tacata. 2023. The Corpus of Regional African American Language: DTA (Detroit, MI 1966). Version 2023.06. Eugene, OR: The Online Resources for African American Language Project.",
            "Shuy, Roger W., Walter A. Wolfram, and William K. Riley. 1967. Linguistic Correlates of Social Stratification in Detroit Speech. East Lansing, MI: Michigan State University.",
            "Shuy, Roger W., Walter A. Wolfram, and William K. Riley. 1968. Field Techniques in an Urban Language Study. Urban Language Series 3. Washington D.C.: Center for Applied Linguistics.",
            "Becker, Kara, Charlie Farrington, Tyler Kendall, Chloe Tacata, and Jaidan McLean. 2021. The Corpus of Regional African American Language: LES (Lower East Side, NY 2008). Version 2021.07. Eugene, OR: The Online Resources for African American Language Project.",
            "Becker, Kara. 2010. Regional dialect features on the Lower East Side of New York City: Sociophonetics, ethnicity, and identity. Ph.D. dissertation. New York, New York: New York University.",
            "Rowe, Ryan, Walt Wolfram, Tyler Kendall, Charlie Farrington, and Brooke Josler. 2018. The Corpus of Regional African American Language: PRV (Princeville, NC 2004). Version 2018.10.06. Eugene, OR: The Online Resources for African American Language.",
            "Rowe, Ryan. 2005. The development of African American English in the oldest Black town in America: Plural -s absence in Princeville, North Carolina. MA Thesis. Raleigh: North Carolina State University.",
            "King, Sharese, Charlie Farrington, Tyler Kendall, Emma Mullen, Shelby Arnson, and Lucas Jenson. 2020. The Corpus of Regional African American Language: ROC (Rochester, NY 2016). Version 2020.05. Eugene, OR: The Online Resources for African American Language Project.",
            "King, Sharese. 2018. Exploring social and linguistic diversity across African Americans from Rochester, New York. Ph.D. dissertation. Palo Alto, CA: Stanford University.",
            "Quartey, Minnie, Charlie Farrington, Tyler Kendall, Lucas Jenson, Chloe Tacata, and Jaidan McLean. 2020. The Corpus of Regional African American Language: VLD (Valdosta, GA 2017). Version 2021.07. Eugene, OR: The Online Resources for African American Language Project.",
        ],
    },
    "earnings22": {
        "name": "Earnings-22", "uses": "Reference transcripts only. The audio has no stated licence, so none of it is played here.",
        "licence": "CC BY-SA 4.0", "licenceUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source": ["Rev's speech-datasets on GitHub", "https://github.com/revdotcom/speech-datasets/tree/main/earnings22"],
        "changed": "The reference text is shown split by time, beside the engines' transcripts, and is shared under the same licence.",
        "cite": ["Del Rio, Ha, McNamara, Miller and Chandra (2022), Earnings-22: A Practical Benchmark for Accents in the Wild, arXiv:2203.15591."],
    },
}

#: Each data set's whole-recording page (tools/build_explorer.py), its own artifact.
EXPLORER_URLS = json.loads((CAPSTONE / "tools" / "explorer_page" / "published.json").read_text(encoding="utf-8"))     if (CAPSTONE / "tools" / "explorer_page" / "published.json").exists() else {}

PART_LABELS = {"test": "Test", "dev": "Dev", "ROC": "Rochester", "PRV": "Princeville", "DCB": "Washington DC",
               "DCA": "Washington DC 1968", "DTA": "Detroit", "ATL": "Atlanta", "VLD": "Valdosta", "LES": "Lower East Side",
               "Spanish/Portuguese": "Spanish and Portuguese"}

#: The four kinds of failure, in order of how much harm they could do to a record.
KINDS = [
    ("meaning", "Meaning changes",
     "The engine writes something fluent that says something different: a dropped “not”, a different number, another real word. Nothing on the page shows a reader it is wrong."),
    ("invented", "Invented words",
     "Words written where nobody spoke: a quiet stretch the voice detector hears no speech in, and the record has nothing."),
    ("edits", "The engine edits the speaker",
     "It writes what it expected to hear rather than how the person spoke: restarts tidied away, and on CORAAL the grammar of African American English rewritten as standard English."),
    ("skips", "Silent skips",
     "A stretch of clear speech from one speaker left out, with nothing to mark the gap. Other engines wrote it, so the audio was clear."),
]
KIND_TITLE = {k: t for k, t, _ in KINDS}


def r2(x: float) -> float:
    # Halves round up, as in the numbers pack (17.005 is 17.01, not 17.00).
    return round(x + 1e-9, 2)


def short_engine(name: str) -> str:
    """'whisper-large-v3' -> 'Whisper', as the pages name engines."""
    if name == "company":
        return "Commercial engine shipped with EdAcc"
    for short in ["Qwen3", "Whisper", "Parakeet", "Canary", "Granite", "Voxtral"]:
        if name.lower().startswith(short.lower()):
            return short
    return name


def clock(seconds: float) -> str:
    h, m, s = int(seconds // 3600), int(seconds % 3600 // 60), int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# The Supreme Court's own numbers, each from its file in findings/
# ---------------------------------------------------------------------------

def four_terms() -> list[dict]:
    """Each default engine's average in each term, on both rules."""
    frames = []
    # An engine can have several runs of a term, and the first found is kept. Parakeet's
    # -reread runs come first: its older runs are from before the full-stop fix.
    runs = sorted((FINDINGS / "harmonise").glob("run-*/before-after.csv"))
    rereads = [p for p in runs if "reread" in p.parent.name]
    for path in rereads + [FINDINGS / "harmonise" / "before-after.csv"] + [p for p in runs if p not in rereads]:
        t = pd.read_csv(path)
        if "term" not in t.columns:
            t["term"] = "OT2017"
            t["cases"] = 61
        frames.append(t)
    t = pd.concat(frames)
    t["engine"] = t.model.str.extract(r"^(Qwen3|Whisper|whisper|Parakeet|parakeet)", expand=False).str.capitalize()
    # A few early test runs scored only one or eight arguments.
    t = t[t.engine.notna() & t.term.isin(TERMS) & (t.cases > 20)].drop_duplicates(["engine", "term"])
    rows = []
    for rule, col in [("benchmark", "standard_after"), ("verbatim", "verbatim_after")]:
        for engine in ["Qwen3", "Whisper", "Parakeet"]:
            got = t[t.engine == engine].set_index("term")[col]
            rows.append({"engine": engine, "rule": rule, **{x: r2(got[x]) if x in got else None for x in TERMS}})
    return rows


ODDS_LABELS = {
    "word_type=legal": "A legal term",
    "near_dash": "A reporter's dash nearby (someone was cut off)",
    "word_type=name": "A name",
    "word_type=number": "A number",
    "word_type=filler": "A filler word",
    "word_type=function": "A small word (the, of, to)",
    "turn=0": "The first word after a new speaker starts",
    "turn=1-3": "1-3 words after a new speaker starts",
    "turn=4-10": "4-10 words after a new speaker starts",
    "disfluency_near": "A filler or repeated word nearby",
    "rate": "Each extra word per second of speech",
    "role=justice": "Spoken by a justice, not a lawyer",
}


def odds_label(key: str) -> str | None:
    """A plain label for a term of the error model; engines are against Qwen3."""
    if key.startswith("engine="):
        return f"{short_engine(key.split('=', 1)[1])} instead of Qwen3"
    return ODDS_LABELS.get(key)


def odds_table(t: pd.DataFrame) -> dict:
    t = t.set_index("term")
    return {k: {"v": round(t.loc[k, "odds_ratio"], 2), "lo": round(t.loc[k, "ci_low"], 2),
                "hi": round(t.loc[k, "ci_high"], 2)} for k in t.index if odds_label(k)}


def refit_date() -> str:
    """When the main error model was last fitted, from the first line of its README."""
    first = (FINDINGS / "error-model" / "README.md").read_text(encoding="utf-8").splitlines()[0]
    m = re.search(r"re-fitted (\d{1,2} \w+)", first)
    return m.group(1) if m else "November"


def refit_note() -> str:
    """The seven-engine Supreme Court fit (2017 term), done again on the repaired
    transcripts, and the same fit with Parakeet left out: one plain paragraph."""
    folder = FINDINGS / "error-model"
    odds = pd.read_csv(folder / "odds-ratios-scotus.csv").set_index("term").odds_ratio
    nopk = pd.read_csv(folder / "without-parakeet" / "odds-ratios-scotus.csv").set_index("term").odds_ratio
    r2s = pd.read_csv(folder / "variance-explained.csv")
    r2s = r2s[r2s.corpus == "scotus"].set_index("model").mcfadden_r2_beyond_recording
    keys = ["turn=0", "near_dash", "word_type=legal"]
    return (f"The bars above are the three engines that ran every term, fitted on 23 October. The same model with all "
            f"seven engines on the 2017 term was fitted again on {refit_date()}, after the repairs to the "
            f"engines' transcripts, and the pattern held: the first word after a new speaker starts has "
            f"{odds['turn=0']:.1f} times the odds of a miss, a word near a reporter's dash {odds['near_dash']:.1f} times "
            f"and a legal term {odds['word_type=legal']:.1f} times, and what is going on around a word explains about "
            f"{round(r2s['conditions'] / r2s['engine'])} times as much as which engine wrote it. It holds with Parakeet "
            f"left out too (its old fault struck after full stops, often where a speaker changes): "
            f"{', '.join(f'{nopk[k]:.1f}' for k in keys[:2])} and {nopk[keys[2]]:.1f}. "
            f"From findings/error-model/odds-ratios-scotus.csv and without-parakeet/.")


def error_model(corpus: str) -> dict:
    """The odds-ratio bars: by term on the Supreme Court, one set on EdAcc."""
    refit = ""
    if corpus == "scotus":
        folder = FINDINGS / "error-model" / "three-engines-by-term"
        modes = [("all-four", "All four terms")] + [(t, t.replace("OT", "")) for t in TERMS]
        values = {m: odds_table(pd.read_csv(folder / f"odds-ratios-{m}.csv")) for m, _ in modes}
        r2s = pd.read_csv(folder / "variance-explained.csv")
        source = "Odds ratios with 95% intervals from findings/error-model/three-engines-by-term/. Association, not cause; the record decides what counts as a dash or a change of speaker. Fitted on 23 October, before the November repairs to some engines' transcripts; the seven-engine fit above, done again after the repairs, shows how little such figures moved."
        refit = refit_note()
    else:
        modes = [(corpus, "Test split")]
        values = {corpus: odds_table(pd.read_csv(FINDINGS / "error-model" / f"odds-ratios-{corpus}.csv"))}
        r2s = pd.read_csv(FINDINGS / "error-model" / "variance-explained.csv")
        source = f"Odds ratios with 95% intervals from findings/error-model/odds-ratios-{corpus}.csv, the test split. Association, not cause. First fitted on 16 October, and fitted again on {refit_date()} on the repaired transcripts; the pattern is the same."
    fit = {m: {row.model: row.mcfadden_r2_beyond_recording for row in r2s[r2s.corpus == m].itertuples()}
           for m, _ in modes}
    first = values[modes[0][0]]
    order = sorted(first, key=lambda k: -first[k]["v"])
    return {"rows": [{"key": k, "label": odds_label(k)} for k in order], "modes": modes,
            "values": values, "fit": fit, "source": source, "refit": refit}


# ---------------------------------------------------------------------------
# What every data set has: error rates, coverage, failures
# ---------------------------------------------------------------------------

def scores(corpus: str) -> dict:
    """Error rates by engine and part, in the same shape for every data set."""
    if corpus == "scotus":
        rows = [r for r in four_terms() if r["rule"] == "benchmark"]
        # The mean over every argument, from the unrounded rates: averaging the term
        # figures above would round them twice.
        means = pd.read_csv(FINDINGS / "flip" / "per-argument.csv").mean(numeric_only=True)
        for r in rows:
            r["all"] = r2(means[f"{r['engine']}_benchmark"])
        return {"rules": [["benchmark", "Benchmark rule"]],
                "parts": [{"key": t, "label": t.replace("OT", "")} for t in TERMS] + [{"key": "all", "label": "All four"}],
                "rows": rows, "digits": 2,
                "intro": "Average error rate per argument, in percent, by term (the benchmark rule: case, punctuation and fillers ignored). Click a heading to sort.",
                "source": "From findings/harmonise/*/before-after.csv (the \"after\" columns, with the October scoring fixes)."}
    # The same benchmark rule as the Supreme Court's, fixes included (tools/benchmark_tables.py).
    t = pd.read_csv(FINDINGS / corpus / "benchmark.csv")
    keys = [p for p in dict.fromkeys(t.part) if p != "all"]
    rows = []
    for engine in dict.fromkeys(t.engine):
        got = t[t.engine == engine].set_index("part").benchmark
        rows.append({"engine": engine, "rule": "benchmark",
                     **{p: r2(got[p]) if p in got else None for p in keys + ["all"]}})
    rows.sort(key=lambda r: (r["all"] is None, r["all"] or 0))
    labels = {**PART_LABELS, "test": "Test (as published)"} if corpus == "edacc" else PART_LABELS
    return {"rules": [["benchmark", "Benchmark rule"]],
            "parts": [{"key": p, "label": labels.get(p, p)} for p in keys]
                     + [{"key": "all", "label": "All"}],
            "rows": rows, "digits": 2,
            "intro": "Errors over every reference word, pooled, in percent (the benchmark rule: case, punctuation and fillers ignored). Click a heading to sort.",
            "source": f"From findings/{corpus}/benchmark.csv (tools/benchmark_tables.py), with the October scoring fixes."}


def scotus_coverage() -> list[dict]:
    """Every Supreme Court term, and how far each default engine has got through it."""
    import clips
    cases = [f for f in clips.cases_dir().iterdir() if f.is_dir() and f.name.startswith("OT")]
    per_term: dict[str, int] = {}
    for f in cases:
        per_term[f.name[:6]] = per_term.get(f.name[:6], 0) + 1
    # A re-argued case has a folder in each term it was argued in.
    terms_of: dict[str, set[str]] = {}
    for f in cases:
        terms_of.setdefault(f.name.split("_")[1], set()).add(f.name[:6])

    def done(run: str, engine_file: str) -> set[tuple[str, str]]:
        """(docket, term) for every finished transcript in a run."""
        asr = clips.runs_dir() / run / "asr"
        out = set()
        for p in asr.glob(f"*.{engine_file}*.json") if asr.exists() else []:
            name = p.name.split(".")[0]
            docket, _, term = name.partition("_")
            for t in ([term] if term else sorted(terms_of.get(docket, []))):
                out.add((docket, t))
        return out

    engines = {
        # Parakeet: the -reread runs (findings/parakeet-stall/).
        "Parakeet": done("run-scotus250-parakeet-reread", "parakeet") | done("run-20260924-064733-reread", "parakeet"),
        "Whisper": done("run-scotus250-whisper", "whisper") | done("run-20260918-035220", "whisper"),
        "Qwen3": done("run-scotus250-qwen3-reread", "Qwen3") | done("run-20260921-051927-reread", "Qwen3"),
    }
    return [{"key": term, "label": term.replace("OT", ""), "n": per_term[term],
             "note": "by telephone" if term == "OT2020" else "",
             "done": {e: min(per_term[term], sum(1 for d, t in got if t == term)) for e, got in engines.items()}}
            for term in sorted(per_term)]


def coverage(corpus: str) -> dict:
    spec = DATASETS[corpus]
    if corpus == "scotus":
        return {"cells": scotus_coverage(), "engines": ["Parakeet", "Whisper", "Qwen3"], "unit": "arguments",
                "clickable": True,
                "intro": "Every term of arguments on disk, and how far each of the three default engines has got."}
    import lineup
    root = lineup.corpus_root(corpus)
    index = [json.loads(line) for line in (root / "recordings.jsonl").read_text(encoding="utf-8").splitlines()]
    models = [lineup.model_run(name, root / "runs" / run) for name, run in lineup.OTHER_RUNS[corpus].items()]
    have = {m.name: m.recordings() for m in models}
    cells = []
    for part in dict.fromkeys(e["split"] for e in index):
        ids = {e["id"] for e in index if e["split"] == part}
        cells.append({"key": part, "label": PART_LABELS.get(part, part), "n": len(ids), "note": "",
                      "done": {m: len(ids & have[m]) for m in spec["engines"]}})
    return {"cells": cells, "engines": spec["engines"], "unit": spec["unit"], "clickable": False,
            "intro": f"Each part of {spec['name']} on disk, and how far each engine has got."}


#: Kinds whose counts mean different things by subkind are shown subkind by
#: subkind, per hour. Meaning changes: a lost "not" or a wrong number is nearly
#: always a real change of meaning; most "other word" swaps are plain mishearings
#: that leave the sentence garbled, so that column is an upper bound.
SUBKIND_COLUMNS = {
    "meaning": [("negation", "A “not” lost or added"), ("number", "A different number"),
                ("word", "Another word (upper bound)")],
    "edits": [("dialect_changed", "Grammar rewritten"), ("restarts_dropped", "Restart tidied away")],
}


def kind_counts(kind: str, corpus: str) -> dict | None:
    """Cases per hour by engine for one kind on one data set, pooled over its parts."""
    path = FAILURES / kind / "counts.csv"
    if not path.exists():
        return None
    t = pd.read_csv(path)
    t = t[t.corpus == corpus]
    if "candidates" not in t.columns and "skips" in t.columns:
        t = t.rename(columns={"skips": "candidates"})
    if t.empty or "candidates" not in t.columns:
        return None
    # A column only where this data set has something in it (no dialect features
    # are looked for outside CORAAL).
    subkinds = [(k, label) for k, label in SUBKIND_COLUMNS.get(kind, []) if t[k].sum() > 0]
    g = t.groupby("engine", sort=False)[["hours", "candidates"] + [k for k, _ in subkinds]].sum().reset_index()
    rows = []
    for r in g.to_dict("records"):
        row = {"engine": r["engine"], "hours": round(r["hours"], 1), "n": int(r["candidates"]),
               "perHour": round(r["candidates"] / r["hours"], 2)}
        row.update({k: round(r[k] / r["hours"], 2) for k, _ in subkinds})
        rows.append(row)
    if subkinds:
        columns = ([{"key": "engine", "label": "Engine"}]
                   + [{"key": k, "label": f"{label}, per hour", "num": True, "digits": 2} for k, label in subkinds]
                   + [{"key": "hours", "label": "Hours of audio", "num": True}])
        return {"columns": columns, "rows": rows, "sort": {"key": subkinds[0][0], "dir": -1}}
    return {"columns": [{"key": "engine", "label": "Engine"},
                        {"key": "n", "label": "Found by the rules", "num": True},
                        {"key": "hours", "label": "Hours of audio", "num": True},
                        {"key": "perHour", "label": "Per hour", "num": True, "digits": 1}],
            "rows": rows, "sort": {"key": "perHour", "dir": -1}}


#: The features of African American English grammar the edits finder looks
#: for, in plain words, most common first. Features found fewer than 50 times
#: in the record are left off the page: too few for a rate.
FEATURES = {
    "zero-copula": "No “is” or “are”: “they working”",
    "negative-concord": "Double negative: “didn't do nothing”",
    "was-levelling": "“We was”, “they was”",
    "aint": "“Ain't”",
    "third-person-s": "Verb without -s: “she help”",
    "habitual-be": "Habitual be: “we be walking”",
}


def dialect_rates(corpus: str) -> dict | None:
    """On CORAAL, how often each engine rewrote each feature of the speakers' grammar."""
    path = FAILURES / "edits" / "dialect-rates.csv"
    if corpus != "coraal" or not path.exists():
        return None
    t = pd.read_csv(path)
    t = t[(t.component == "all") & t.feature.isin(FEATURES)]
    engines = DATASETS[corpus]["engines"]
    rows = []
    for feature, label in FEATURES.items():
        got = t[t.feature == feature].set_index("engine")
        if got.empty or got.in_record.max() < 50:
            continue
        rows.append({"feature": label, "n": int(got.in_record.max()),
                     **{e: float(got.loc[e, "standardised_pct"]) for e in engines if e in got.index}})
    return {"intro": "Where the record keeps a feature of African American English grammar, how often each engine rewrote it as standard English, in percent. The rest of the time it kept it, or misheard the words altogether.",
            "columns": [{"key": "feature", "label": "In the record"},
                        {"key": "n", "label": "Times", "num": True}]
                       + [{"key": e, "label": f"{e} rewrote", "num": True, "digits": 0} for e in engines],
            "rows": rows, "sort": None}


#: The rule counts behind each section, per hour: what the Python rules found,
#: before any judge or ear has looked. "Another word" is left out: most of those
#: are plain mishearings, so its count says little.
CLASS_COLUMNS = [("opposite", "“Not” lost or added"), ("fact", "Number changed"),
                 ("invented", "Added in silence"), ("skips", "Speech left out"),
                 ("edits", "Tidied or rewritten")]


def class_rates(corpus: str) -> dict:
    """Each engine's rule-found cases per hour, one column per section."""
    def per_engine(kind: str, cols: list[str]) -> pd.DataFrame:
        t = pd.read_csv(FAILURES / kind / "counts.csv")
        t = t[t.corpus == corpus]
        return t.groupby("engine", sort=False)[["hours"] + cols].sum()
    meaning = per_engine("meaning", ["negation", "number"])
    invented = per_engine("invented", ["candidates"])
    skips = per_engine("skips", ["candidates"])
    edits = per_engine("edits", ["dialect_changed", "restarts_dropped"])
    rows = []
    for engine in DATASETS[corpus]["engines"]:
        if engine not in meaning.index:
            continue
        hours = meaning.loc[engine, "hours"]
        row = {"engine": engine, "hours": round(hours, 1),
               "opposite": meaning.loc[engine, "negation"] / hours, "fact": meaning.loc[engine, "number"] / hours,
               "invented": invented.loc[engine, "candidates"] / hours if engine in invented.index else None,
               "skips": skips.loc[engine, "candidates"] / hours if engine in skips.index else None,
               "edits": (edits.loc[engine, "dialect_changed"] + edits.loc[engine, "restarts_dropped"]) / hours
               if engine in edits.index else None}
        rows.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()})
    return {"columns": [{"key": "engine", "label": "Engine"}]
                       + [{"key": k, "label": f"{label}, per hour", "num": True, "digits": 2} for k, label in CLASS_COLUMNS]
                       + [{"key": "hours", "label": "Hours", "num": True}],
            "rows": rows, "sort": {"key": "opposite", "dir": -1}}


def overall_rates(corpus: str) -> list[dict]:
    """One error rate per engine over the whole data set (the benchmark rule)."""
    s = scores(corpus)
    return [{"engine": r["engine"], "rate": r["all"]} for r in s["rows"] if r.get("all") is not None]


def opposite_share(corpus: str) -> dict:
    """Of the rule's "not" cases Sonnet judged, how many it says reverse the meaning."""
    t = judged()
    t = t[(t.corpus == corpus) & (t.kind == "meaning") & (t.subkind == "negation") & (t.s_meaning != "")]
    n = len(t)
    return {"n": n, "opposite": int((t.s_meaning == "opposite").sum()),
            "share": round(100 * (t.s_meaning == "opposite").mean(), 0) if n else None}


#: Said after every count taken from the judge's answers.
BY_TEXT = "That is judged from the text by a language model, not yet checked by ear."


def and_list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def opposite_tally(corpus: str, recordings: str) -> str:
    """How many meaning cases Sonnet called "opposite", engine by engine, over the
    whole data set (every engine on a page ran every recording), most first."""
    t = judged()
    t = t[(t.corpus == corpus) & (t.kind == "meaning") & (t.s_meaning == "opposite")]
    t = t[t.engine.isin(DATASETS[corpus]["engines"])]
    if t.empty:
        return ""
    every = t.groupby("engine").size().sort_values(ascending=False, kind="stable")
    nots = t[t.subkind == "negation"].groupby("engine").size().reindex(every.index, fill_value=0)
    counts = [f"{n} for {e}" if i else f"{n} times for {e}" for i, (e, n) in enumerate(every.items())]
    return (f"In all {recordings}, Claude Sonnet says the engine's words reverse the meaning {and_list(counts)}; "
            f"a lost or added “not” is {and_list([str(n) for n in nots])} of them. {BY_TEXT}")


def reference_doubt(corpus: str) -> str:
    """The share of judged cases where Sonnet says the reference itself looks wrong,
    here and on the other data sets."""
    t = judged()
    t = t[t.s_meaning != ""]
    share = lambda c, v: 100 * (t[t.corpus == c].s_reference_doubt == v).mean()
    others = [f"{DATASETS[c]['name']} {share(c, 'yes'):.0f}%" for c in DATASETS if c != corpus]
    return (f"Claude Sonnet, reading each case the searches found here, says the reference itself looks wrong in "
            f"{share(corpus, 'yes'):.0f}% of them, and maybe wrong in another {share(corpus, 'maybe'):.0f}%. "
            f"On the other data sets: {and_list(others)}. {BY_TEXT}")


# ---------------------------------------------------------------------------
# The failure cards: one shortlisted case each, with a clip to hear
# ---------------------------------------------------------------------------

def split_context(text: str, fallback: str) -> dict:
    """'before [the words] after' -> the Record line of a card."""
    m = re.match(r"^(.*?)\[(.*?)\](.*)$", text or "")
    if not m:
        return {"before": "", "mark": fallback, "after": ""}
    return {"before": m.group(1).strip(), "mark": m.group(2).strip(), "after": m.group(3).strip()}


def quote(text: str, most: int = 40) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= most else text[:most - 1].rstrip() + "…"


def card_title(kind: str, r) -> str:
    record, wrote = quote(r.record), quote(r.engine_wrote)
    if kind == "meaning":
        return f"{r.engine} wrote “{wrote}” where the speaker said “{record}”" if wrote else \
               f"{r.engine} left out “{record}”"
    if kind == "invented":
        return f"{r.engine} wrote “{wrote}” where nobody spoke"
    if kind == "edits":
        return f"{r.engine} rewrote “{record}” as “{wrote}”" if wrote else \
               f"{r.engine} tidied away “{record}”"
    return f"{r.engine} left out {len(str(r.record).split())} words of clear speech"


def card_where(corpus: str, job: dict, start: float) -> str:
    import clips
    at = f"{clock(start)} into the recording"
    if corpus == "scotus":
        docket = job["docket"].split("_")[0]
        return f"{clips.case_name(docket, job['term'])}, No. {docket}, {job['term'].replace('OT', '')} term, {at}"
    if corpus == "coraal":
        place = PART_LABELS.get(job["term"], job["term"])
        return f"{place} interview {job['docket']}, {at}"
    if corpus == "earnings22":
        return f"Earnings call {job['docket']} ({job['term']} region), {at}"
    return f"EdAcc conversation {job['docket']} ({job['term']} split), {at}"


def plain(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def find_passage(words: list[str], times: list[float], record: str, near: float) -> set[int]:
    """The indexes of the record's words a case is about, found by their text.

    The case gives the words (`record`) and the engine's time; the same words can
    come up more than once in a window, so the copy closest in time wins.
    """
    want = [plain(w) for w in str(record or "").split() if plain(w)]
    if not want:
        return set()
    flat = [plain(w) for w in words]
    hits = [i for i in range(len(flat) - len(want) + 1)
            if flat[i:i + len(want)] == want and abs(times[i] - near) < 40]
    if not hits:
        return set()
    best = min(hits, key=lambda i: abs(times[i] - near))
    return set(range(best, best + len(want)))


def make_card(kind: str, r, jobs: dict, explanation: str, score: float, notes: list[str] | None = None) -> dict | None:
    """Cut the clip for one case and lay out its card.

    The clip runs about LONG seconds and ends between sentences where it can
    (clips.snap_window); a shorter stretch of about SHORT seconds inside it is
    the first thing played. Both buttons say how long they really are.
    """
    import clips
    import lineup
    import soundfile as sf
    job = jobs.get((r.part, r.recording))
    if job is None:
        print(f"  card: {r.corpus} {r.recording} not found; left out")
        return None
    lined = lineup.load(job)
    start, end = float(r.start), float(r.end)
    right = [e for e in str(r.others_right or "").split() if e in lined and e != r.engine]
    other = right[:1] or [e for e in ("Qwen3", "Whisper", "Parakeet") if e in lined and e != r.engine][:1]
    shown = [r.engine] + other
    duration = sf.info(job["audio"]).duration
    breaks = clips.sentence_breaks([lined[e][3] for e in shown])
    long_a, long_b = clips.snap_window(start, end, clips.LONG, breaks, duration)
    short_a, short_b = clips.snap_window(start, end, clips.SHORT, breaks, duration)
    a, b = min(long_a, short_a), max(long_b, short_b)
    clip = None
    if DATASETS[r.corpus].get("clips", True):
        clip = f"clips/failures/{r.corpus}/{kind}-{r.recording}-{r.engine}-{int(start * 10)}.mp3"
        clips.cut_clip(job["audio"], a, b, SITE / clip)

    def line(engine: str) -> dict:
        _, _, al, words = lined[engine]
        hs = al.hypothesis.source_index
        off = {hs[h] for c in al.chunks if c.kind != "equal" for h in range(c.hyp_start, c.hyp_end)}
        if engine == r.engine:
            # The case's own words, too: "would" for "wouldn't" lines up as "would"
            # against "would not", so only the missing "not" counts as different.
            off |= {i for i, w in enumerate(words)
                    if w.start is not None and start - 0.05 <= w.start <= end + 0.05}
        timed = clips.timed_words(words, a, b, off)
        return {"who": engine, "w": clips.join_hyphen_pieces(timed) if engine == "Whisper" else timed}

    ref_words = lined[r.engine][1]
    times = lineup.reference_times(lined)
    marked = find_passage(ref_words, times, r.record, start)
    record = {"who": "Record", "w": clips.timed_reference(ref_words, times, a, b, marked)}
    if not record["w"]:
        record = {"who": "Record", **split_context(r.record_context, r.record)}
    has_audio = clip is not None
    short_from, short_to, long_to = round(short_a - a, 2), round(short_b - a, 2), round(b - a, 2)
    short_label = f"{round(short_to - short_from)} seconds" if has_audio else "Shorter passage"
    long_label = f"{round(long_to)} seconds" if has_audio else "Longer passage"
    return {
        "kind": kind, "kindLabel": KIND_TITLE[kind], "title": card_title(kind, r),
        "where": card_where(r.corpus, job, start), "explanation": explanation,
        "notes": notes or [],
        "heard": str(getattr(r, "heard", "no")).lower() == "yes",
        "clip": clip, "view": "short",
        "views": [{"key": "short", "label": short_label, "from": short_from, "to": short_to},
                  {"key": "long", "label": long_label, "from": 0.0, "to": long_to}],
        "lines": [record, line(r.engine)] + [line(e) for e in other],
        "score": score,
        "corpus": r.corpus, "part": r.part, "recording": r.recording, "engine": r.engine,
        "start": round(start, 2),
    }


#: How the cards are grouped: by what the error does to someone reading the
#: transcript. Preliminary: it leans on the machine judges' answers
#: (findings/judge/), and none of the cases has been checked by ear yet.
SECTIONS = [
    ("opposite", "Says the opposite",
     "A “not” dropped or added, “can” for “can't”: the sentence still reads smoothly, and says the reverse of what the speaker said."),
    ("fact", "Gets a fact wrong",
     "A different number, or another real word that changes what happened. Nothing on the page tells a reader it is wrong."),
    ("invented", "Adds words nobody said",
     "Words written into a pause where nobody spoke: a stock phrase, or a plausible end to someone's sentence."),
    ("skips", "Leaves out what was said",
     "A stretch of clear speech left out with no sign of the gap. Other engines wrote it, so the audio was clear."),
    ("edits", "Rewrites how the speaker talks",
     "The engine writes what it expected rather than what was said: restarts tidied away, and on CORAAL the grammar of African American English rewritten as standard English."),
]
SECTION_TITLE = {k: t for k, t, _ in SECTIONS}
#: How the pages describe the judging, so every page says the same thing.
JUDGE_NOTE = ("The failures worth a reader's attention, sorted by what they do to someone reading the transcript. "
              "The sorting leans on an AI judge, Claude Sonnet, which read every case; it is preliminary, and none of "
              "these cases has been checked by ear yet. A second AI judge, Qwen 3.8, is still reading the cases on the "
              "laptop, so its answers are not shown yet.")
SUBKIND_LABELS = {"negation": "a “not” lost or added", "number": "a different number", "word": "another word",
                  "dialect_changed": "dialect grammar rewritten", "restarts_dropped": "a restart tidied away"}
JUDGE = FINDINGS / "judge"
CASE_KEY = ["corpus", "part", "recording", "engine", "kind", "subkind", "start"]
#: Cards per section on one page (four shown, the rest behind "Show more").
PER_SECTION = 12
#: At most this many of them from the hand-read shortlists, so every section also
#: shows what the judges found across all the cases (Sonnet has read every one).
HAND_MOST = 8
#: Whether the pages show the Qwen judge's answers. Off while its run on full-v1 is
#: still going (tools/run_qwen_judge.ps1): its file then holds only part of the cases,
#: and a page would show them as if Qwen had read everything. With this off, judged()
#: never reads that file, so the cards, the data page and the whole-recording pages
#: all go by Sonnet alone. Turn it on once Qwen has read every case.
SHOW_QWEN = False
_judged = None


def read_growing_csv(path: Path) -> pd.DataFrame:
    """A CSV another program may be adding to (the Qwen judge runs for days): a
    last row caught half-written is left out rather than stopping the build."""
    text = path.read_text(encoding="utf-8")
    for _ in range(5):
        try:
            return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        except pd.errors.ParserError:
            text = text[:text.rstrip("\r\n").rfind("\n") + 1]
    raise SystemExit(f"Can't read {path.name}, even without its last rows.")


def judge_answers(file: str, ask: str, prefix: str) -> pd.DataFrame:
    """One judge's answers to one question, a column per field, one row per case."""
    t = read_growing_csv(JUDGE / file)
    t = t[(t.ask == ask) & (t.valid == "True")]
    rows = []
    for c, a in zip(t.case, t.answer):
        try:
            rows.append({"case": c, **{prefix + k: v for k, v in json.loads(a).items()}})
        except json.JSONDecodeError:
            pass   # the last answer, cut off while being written
    return pd.DataFrame(rows).drop_duplicates("case", keep="last") if rows else pd.DataFrame({"case": []})


def judged() -> pd.DataFrame:
    """Every failure case (judge/full-v1.csv), with what Sonnet and Qwen said about it."""
    global _judged
    if _judged is None:
        import lineup
        full =pd.read_csv(JUDGE / "full-v1.csv", dtype=str, keep_default_na=False)
        if "not_counted" not in full:
            full["not_counted"] = ""
        # Whisper's split hyphens ("dope [-themed]"), joined back for showing.
        w = full.engine == "Whisper"
        full.loc[w, "engine_context"] = full.loc[w, "engine_context"].map(lineup.join_split_hyphens)
        piece = w & full.engine_wrote.str.match(r"-[\w$]")
        full.loc[piece, "engine_wrote"] = full.loc[piece, "engine_context"].str.extract(r"\[([^\]]*)\]", expand=False) \
            .fillna(full.loc[piece, "engine_wrote"])
        full.loc[w, "engine_wrote"] = full.loc[w, "engine_wrote"].map(lineup.join_split_hyphens)
        # The meaning search's engine_wrote kept only the words it lined up, so a word
        # inside the spot could drop out ("$2 billion," for "$2 .5 billion,"; fixed in
        # find_meaning_changes.py for its next run). engine_context has the whole spot
        # in [brackets]: shown instead wherever it holds every word of engine_wrote in order.
        full["engine_wrote"] = [whole_spot(wrote, context) for wrote, context in zip(full.engine_wrote, full.engine_context)]
        # Whisper's timings also split numbers: "$2 .5", "140 ,000", "28 %".
        for col in ("engine_wrote", "engine_context"):
            full.loc[w, col] = full.loc[w, col].map(join_number_pieces)
        asks = [("answers-claude-sonnet-5-5-full-v1.csv", "meaning", "s_"),
                ("answers-claude-sonnet-5-5-full-v1.csv", "story", "story_")]
        if SHOW_QWEN:
            asks.insert(1, ("answers-qwen3.8-27b-full-v1.csv", "meaning", "q_"))
        for file, ask, prefix in asks:
            full = full.merge(judge_answers(file, ask, prefix), on="case", how="left")
        if not SHOW_QWEN:
            full["q_meaning"] = ""
            full["q_severity"] = ""
        full["start"] = full.start.astype(float).round(2)
        full["s_severity"] = pd.to_numeric(full.s_severity, errors="coerce")
        full["story_example"] = pd.to_numeric(full.story_example, errors="coerce")
        text = [c for c in full.columns if c not in ("start", "s_severity", "story_example")]
        full[text] = full[text].fillna("")
        _judged = full
    return _judged


def whole_spot(wrote: str, context: str) -> str:
    """The engine's words at a spot, taken from the [bracketed] part of its context
    when that has more words and every word of `wrote` in the same order."""
    m = re.search(r"\[([^\]]*)\]", context or "")
    if not m:
        return wrote
    spot, have = m.group(1).split(), str(wrote).split()
    if len(spot) <= len(have):
        return wrote
    rest = iter(spot)
    return " ".join(spot) if all(word in rest for word in have) else wrote


_NUMBER_PIECE = re.compile(r"(?<=\d) (?=[.,]\d)|(?<=\d) (?=%)")


def join_number_pieces(text: str) -> str:
    """Whisper text with its split numbers joined back: "$2 .5" is "$2.5", "28 %" is "28%"."""
    return _NUMBER_PIECE.sub("", str(text))


def section_of(kind: str, subkind: str, sonnet: str) -> str:
    if kind != "meaning":
        return kind
    if sonnet == "opposite" or (not sonnet and subkind == "negation"):
        return "opposite"
    return "fact"


def card_notes(r) -> list[str]:
    notes = [f"Found by the rule for {SUBKIND_LABELS.get(r.subkind, r.subkind.replace('_', ' '))}"]
    if getattr(r, "s_meaning", ""):
        notes.append(f"Sonnet: {r.s_meaning}, severity {int(r.s_severity)} of 4")
    if getattr(r, "q_meaning", ""):
        notes.append(f"Qwen: {r.q_meaning}")
    return notes


#: Cases that must not be cards, whatever a judge said: (recording, engine, start, why).
#: All three are invented-words cases; another kind of case at the same spot can still be one.
NOT_CARDS = [
    ("EDACC-C18", "Qwen3", 112.5, "the last words of the read-aloud passage, said a few seconds earlier; its word times "
                                  "are spread evenly (findings/failures/invented/README.md)"),
    ("ATL_se0_ag1_f_01_1", "Parakeet", 1522.72, "shown as added where nobody spoke, but it replaces the record's \"I don't be\""),
    ("DTA_se1_ag1_f_01_1", "Parakeet", 1481.84, "shown as added where nobody spoke, but it replaces the record's \"There are lots of ways\""),
]


def not_a_card(recording: str, engine: str, start: float, kind: str = "invented") -> bool:
    return kind == "invented" and any(recording == r and engine == e and abs(start - s) < 0.05 for r, e, s, _ in NOT_CARDS)


def pick_judged(t: pd.DataFrame, section: str, taken: set, per_engine: int) -> list:
    """Judged cases for a section, the strongest first, spread over engines and recordings."""
    good = t[(t.s_meaning != "") & (t.s_reference_doubt == "no") & (t.s_misspoke == "no") & (t.not_counted == "")]
    if section == "opposite":
        good = good[(good.kind == "meaning") & (good.s_meaning == "opposite") & (good.s_severity >= 3)]
    elif section == "fact":
        good = good[(good.kind == "meaning") & (good.s_meaning == "changed") & (good.s_severity >= 3)
                    & ~good.s_follow_up.isin(["garble", "no change", "same thing", "meaning kept"])]
    else:
        good = good[(good.kind == section) & (good.s_severity >= 2)]
    # Only a Qwen answer that disagrees counts against a case: Qwen has read a
    # quarter of them, mostly the ones Sonnet read first, so "Qwen agrees" would
    # keep picking from that old pool.
    good = good.assign(agree=((good.q_meaning == "") | (good.q_meaning == good.s_meaning)).astype(int))
    good = good.assign(story=good.story_example.fillna(-1))
    good = good.sort_values(["agree", "story", "s_severity", "case"], ascending=[False, False, False, True])
    # Take turns between the rules' subkinds (a "not" lost, a word swapped, ...),
    # each in its own order, so the most common one can't fill the section: the
    # story scores exist only for the 300 combo-v1 cases, mostly negations.
    good = good.assign(turn=good.groupby("subkind").cumcount()).sort_values("turn", kind="stable")
    out, engines = [], {}
    for r in good.itertuples():
        if r.recording in taken or engines.get(r.engine, 0) >= per_engine or not_a_card(r.recording, r.engine, r.start, r.kind):
            continue
        taken.add(r.recording)
        engines[r.engine] = engines.get(r.engine, 0) + 1
        out.append(r)
    return out


def section_cards(corpus: str, rebuild: bool) -> dict[str, list[dict]]:
    """The cards on one data set's page, by section, each cut once and kept in site/clips/failures/."""
    import clips
    t = judged()
    t = t[t.corpus == corpus]
    plan: dict[str, list] = {s: [] for s, _, _ in SECTIONS}
    taken: set = set()
    # The hand-read shortlists first: each has a sentence written for it after reading it.
    for kind, _, _ in KINDS:
        path = FAILURES / kind / "shortlist.csv"
        rows = pd.read_csv(path, keep_default_na=False) if path.exists() else pd.DataFrame()
        rows = rows[rows.corpus == corpus] if len(rows) else rows
        if len(rows):   # the best first, so the cap keeps them
            rows = rows.assign(best=rows.interest.astype(float) + rows.clarity.astype(float)) \
                .sort_values("best", ascending=False, kind="stable")
        for r in rows.itertuples():
            if not_a_card(str(r.recording), r.engine, float(r.start), kind):
                continue
            match = t[(t.recording == str(r.recording)) & (t.engine == r.engine) & (t.kind == kind)
                      & ((t.start - float(r.start)).abs() < 0.02)]
            j = match.iloc[0] if len(match) else None
            sonnet = j.s_meaning if j is not None else ""
            section = section_of(kind, r.subkind, sonnet)
            if len(plan[section]) >= HAND_MOST:
                continue
            plan[section].append(
                ("hand", r, r.explanation, 10 + float(r.interest) + float(r.clarity), j))
            taken.add(str(r.recording))
    engines = len(DATASETS[corpus]["engines"])
    for section in plan:
        room = PER_SECTION - len(plan[section])
        if room > 0:
            for r in pick_judged(t, section, taken, max(2, -(-PER_SECTION // engines)))[:room]:
                score = float(r.s_severity) + (float(r.story_example) if pd.notna(r.story_example) else 0)
                plan[section].append(("judge", r, f"The judge's reading: {r.s_reason}", score, r))

    cache_file = CARD_CLIPS / "cards-v2.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    jobs = None
    out: dict[str, list[dict]] = {}
    for section, picks in plan.items():
        cards = []
        for source, r, explanation, score, j in picks:
            key = f"{r.kind}|{corpus}|{r.recording}|{r.engine}|{float(r.start):.2f}|{explanation}"
            if rebuild or key not in cache:
                if jobs is None:
                    import lineup
                    jobs = {(job["term"], job["docket"]): job for job in lineup.recordings(corpus)}
                print(f"  card: {section} {corpus} {r.recording} {r.engine} {r.start}", flush=True)
                cache[key] = make_card(r.kind, r, jobs, explanation, score)
            card = cache[key]
            if not card:
                continue
            # Cards cut before Whisper's split hyphens were joined (30 Oct) get it here.
            card = card | {"lines": [ln | {"w": clips.join_hyphen_pieces(ln["w"])} if ln["who"] == "Whisper" else ln
                                     for ln in card["lines"]]}
            notes = card_notes(j if j is not None else r)
            if source == "hand":
                notes.insert(1, "explained by Claude (AI) after reading the text, not by ear")
            cards.append(card | {"section": section, "kindLabel": SECTION_TITLE[section], "notes": notes,
                                 "score": score})
        out[section] = sorted(cards, key=lambda c: -c["score"])
    CARD_CLIPS.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return out


def failures(corpus: str, rebuild: bool) -> list[dict]:
    cards = section_cards(corpus, rebuild)
    out = []
    for section, title, why in SECTIONS:
        rates = dialect_rates(corpus) if section == "edits" else None
        out.append({"kind": section, "title": title, "why": why, "cards": cards[section], "counts": None,
                    "rates": rates,
                    "empty": "" if cards[section] else "Nothing of this kind clear enough to show here yet.",
                    "source": ""})
    return out


# ---------------------------------------------------------------------------
# The front page and the work in progress
# ---------------------------------------------------------------------------

def roadmap() -> list[dict]:
    text = (CAPSTONE / "app-roadmap.md").read_text(encoding="utf-8")
    return [{"done": box == "x", "n": int(n), "title": title.rstrip(". ")}
            for box, n, title in re.findall(r"^- \[( |x)\] \*\*(\d+)\. ([^*]+)\*\*", text, re.M)]


def queue() -> dict:
    import overnight_watch as ow
    runs = ow.local_path("scotus_corpus") / "runs"
    rows, left, todo, done = [], 0.0, 0, 0
    for row in ow.queue_rows():
        if row["status"] == "done":
            done += 1
            continue
        if row["status"] != "todo":
            continue
        todo += 1
        p = ow.row_progress(row, runs)
        left += p["hours_left"] or 0
        if len(rows) < 10:
            rows.append({"engine": ow.row_label(row), "terms": row["terms"] or "all", "done": p["transcribed"],
                         "total": p["total"], "hours": round(p["hours_left"], 1) if p["hours_left"] is not None else None})
    return {"done": done, "todo": todo, "hours": round(left), "rows": rows}


def dataset_facts(corpus: str) -> list[dict]:
    if corpus == "scotus":
        t = pd.read_csv(FINDINGS / "corpus" / "terms.csv")
        done = t[t.term.isin(TERMS)]
        return [{"n": f"{int(done.arguments.sum())}", "what": "arguments, in four terms"},
                {"n": f"{done.audio_hours.sum():.0f}", "what": "hours of audio"},
                {"n": "3", "what": "engines on every term, seven on 2017"}]
    t = pd.read_csv(FINDINGS / corpus / "engines-by-part.csv")
    first = t.drop_duplicates("part")
    return [{"n": f"{int(first.recordings.sum())}", "what": DATASETS[corpus]["unit"]},
            {"n": f"{first.audio_hours.sum():.0f}", "what": "hours of audio"},
            {"n": f"{len(DATASETS[corpus]['engines'])}", "what": "engines"}]


def average_rate(classes: dict, key: str) -> float | None:
    got = [r[key] for r in classes["rows"] if r.get(key) is not None and r["engine"] in ("Qwen3", "Whisper", "Parakeet")]
    return round(sum(got) / len(got), 2) if got else None


def front(pages: dict, built: dict) -> dict:
    """The front page: one reversal from each data set, the five kinds across data sets, the doors."""
    opposite = []
    for corpus, page in pages.items():
        k = next(k for k in page["failures"] if k["kind"] == "opposite")
        if k["cards"]:
            opposite.append(k["cards"][0])
    kinds = []
    for section, title, why in SECTIONS:
        per = []
        for corpus, page in pages.items():
            rate = average_rate(page["big"]["classes"], section)
            text = "–" if rate is None else (f"{rate:.1f} an hour" if rate >= 0.1 else f"{rate:.2f} an hour")
            per.append({"name": DATASETS[corpus]["name"], "file": DATASETS[corpus]["file"], "text": text})
        kinds.append({"kind": section, "title": title, "why": why, "perDataset": per})
    datasets = []
    for corpus, page in pages.items():
        facts = page["facts"]
        datasets.append({"name": DATASETS[corpus]["name"], "file": DATASETS[corpus]["file"], "corpus": corpus,
                         "span": f"{facts[0]['n']} {facts[0]['what']}, {facts[1]['n']} hours",
                         "headline": (lambda t: t[:1].upper() + t[1:])(DATASETS[corpus]["title"].split(": ", 1)[-1]) + ".",
                         "home": SOURCES[corpus]["home"]})
    shown = sum(len(k["cards"]) for p in pages.values() for k in p["failures"])
    return {
        "built": built["date"], "pages": built["pages"],
        "lede": "AI speech engines on four kinds of speech: Supreme Court arguments, friends on video calls in many accents, interviews in African American English, and company earnings calls. Most of what they get wrong is harmless. Some of it changes what the transcript says, and reads so smoothly that nobody would notice.",
        "ai": ai_use(built),
        "opposite": opposite,
        "shown": shown,
        "kinds": kinds, "datasets": datasets,
        "queue": queue(), "roadmap": roadmap(),
        "credit": " ".join(DATASETS[c]["credit"] for c in pages),
    }


def compare(pages: dict, built: dict) -> dict:
    """Every data set side by side: error rates by engine, and the five kinds per hour."""
    engines = list(dict.fromkeys(e for c in DATASETS for e in DATASETS[c]["engines"]))
    rates = []
    for engine in engines:
        row = {"engine": engine}
        for corpus, page in pages.items():
            got = [r["rate"] for r in page["big"]["rates"] if r["engine"] == engine]
            row[corpus] = got[0] if got else None
        rates.append(row)
    classes = []
    for corpus, page in pages.items():
        row = {"dataset": DATASETS[corpus]["name"], "file": DATASETS[corpus]["file"]}
        row.update({k: average_rate(page["big"]["classes"], k) for k, _ in CLASS_COLUMNS})
        share = page["big"]["opposite"]
        row["judged"] = share["n"]
        row["share"] = share["share"]
        classes.append(row)
    return {"built": built["date"], "pages": built["pages"],
            "datasets": [{"key": c, "name": DATASETS[c]["name"], "file": DATASETS[c]["file"]} for c in pages],
            "rates": rates, "classes": classes,
            "classColumns": [{"key": k, "label": label} for k, label in CLASS_COLUMNS]}


#: Who made each engine, for the page on how AI was used (engine-architectures.md).
MAKERS = {"Qwen3": "Alibaba", "Whisper": "OpenAI", "Parakeet": "NVIDIA", "Canary": "NVIDIA",
          "Voxtral": "Mistral", "Granite": "IBM", "Granite Plus": "IBM"}


def commit_counts() -> dict:
    """How many of the project's git commits name Claude as a co-author."""
    import subprocess
    try:
        log = subprocess.run(["git", "log", "--format=%x1e%B"], cwd=CAPSTONE, capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"total": 0, "claude": 0}
    commits = [c for c in log.split("\x1e") if c.strip()]
    return {"total": len(commits), "claude": sum("Co-Authored-By: Claude" in c for c in commits)}


def ai_use(built: dict) -> dict:
    """The facts on the page about how AI was used, counted rather than typed in."""
    return {"built": built["date"], "pages": built["pages"],
            "engines": [{"name": ENGINE_NAMES[e], "maker": MAKERS[e]} for e in ENGINE_NAMES],
            "cases": int((judged().s_meaning != "").sum()), "commits": commit_counts()}


# ---------------------------------------------------------------------------

def fill(template: str, data: dict, title: str = "") -> str:
    page = (PAGES / template).read_text(encoding="utf-8")
    for name in ("listen", "compare", "chart", "table", "cards", "credits"):
        page = page.replace(f"/*{name.upper()}*/", (WIDGETS / f"{name}.js").read_text(encoding="utf-8"))
    return (page.replace("/*TOKENS*/", (WIDGETS / "tokens.css").read_text(encoding="utf-8"))
                .replace("/*SITECSS*/", (PAGES / "site.css").read_text(encoding="utf-8"))
                .replace("/*SITEJS*/", (PAGES / "site.js").read_text(encoding="utf-8"))
                .replace("/*EXPLORERS*/{}", json.dumps(EXPLORER_URLS))
                .replace("/*TITLE*/", title)
                .replace("/*DATA*/{}", json.dumps(data, ensure_ascii=False)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clips", action="store_true", help="cut the failure cards' clips again")
    args = parser.parse_args()
    built = {"date": date.today().isoformat(),
             "pages": [{"file": s["file"], "name": s["name"], "corpus": c} for c, s in DATASETS.items()]}
    SITE.mkdir(exist_ok=True)
    pages = {}
    for corpus, spec in DATASETS.items():
        facts = dataset_facts(corpus)
        data = {
            "built": built["date"], "pages": built["pages"], "file": spec["file"], "corpus": corpus,
            "name": spec["name"], "title": spec["title"], "lede": spec["lede"], "facts": facts,
            "source": SOURCES[corpus],
            "big": {"rates": overall_rates(corpus), "classes": class_rates(corpus),
                    "opposite": opposite_share(corpus)},
            "wrongIntro": JUDGE_NOTE + " Names spelled differently, missing speaker labels, capitals, punctuation and “uh” are left out on purpose.",
            "failures": failures(corpus, args.clips),
            "scores": scores(corpus), "extras": spec["extras"], "coverage": coverage(corpus),
            "credit": spec["credit"], "credits": [CREDITS[corpus]],
            "referenceDoubt": reference_doubt(corpus),
        }
        for k in data["failures"]:
            if k["kind"] == "opposite":
                k["tally"] = opposite_tally(corpus, f"{facts[0]['n']} {spec['unit']}")
        if not spec.get("clips", True):
            data["compareKey"] = "A yellow highlight marks an engine's word that differs from the record; the highlighted words in the record are the ones in question. There is no audio on this page: the calls have no stated licence."
        if "odds" in spec["extras"]:
            data["odds"] = error_model(corpus)
        page = fill("dataset.html", data, f"{spec['name']}: Where Speech Recognition Goes Wrong")
        (SITE / spec["file"]).write_text(page, encoding="utf-8")
        pages[corpus] = data
        print(f"site/{spec['file']}: {len(page) / 1e6:.2f} MB; "
              f"{sum(len(k['cards']) for k in data['failures'])} cards")
    page = fill("front.html", front(pages, built))
    (SITE / "index.html").write_text(page, encoding="utf-8")
    (SITE / "compare.html").write_text(fill("compare.html", compare(pages, built), "Comparing the data sets"), encoding="utf-8")
    (SITE / "ai.html").write_text(fill("ai.html", ai_use(built), "How AI Was Used"), encoding="utf-8")
    # The data page lists the tables tools/build_data.py wrote; run that first.
    tables = SITE / "data" / "tables.json"
    (SITE / "data.html").write_text(fill("data.html", {
        "built": built["date"], "pages": built["pages"], "credits": list(CREDITS.values()),
        "tables": json.loads(tables.read_text(encoding="utf-8")) if tables.exists() else []}), encoding="utf-8")
    clips = sorted((SITE / "clips" / "failures").rglob("*.mp3"))
    print(f"site/index.html: {len(page) / 1e6:.2f} MB; {len(clips)} card clips, "
          f"{sum(p.stat().st_size for p in clips) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

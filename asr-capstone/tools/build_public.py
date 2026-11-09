"""Build the public version of the website into public/, ready to upload to
Cloudflare Pages (hosting/SETUP.md).

The private build stays as it is: tools/build_site.py writes site/ and
tools/build_explorer.py writes explorer/<data set>/, both published as claude.ai
artifacts. This script only reads what they wrote, and writes a normal static site
beside them:

    public/index.html, scotus.html, ... data.html, ai.html   the site's pages
    public/recordings/<data set>/                            the whole-recording pages
    public/rate.html, account.html, admin.html               ratings and accounts
    public/privacy.html, terms.html, licences.html           the notices
    public/clips/, data/, rate/, js/, css/, config.js        what they load
    public/404.html, robots.txt, favicon.svg                 for any web host
    public/_headers, _routes.json, _worker.js, _redirects    read by Cloudflare Pages

What changes on the way: links between artifacts (the claude.ai addresses in
tools/explorer_page/published.json, and the #go-... links the whole-recording pages
used to reach the home page) become relative links; each card and each serious row
of the data page gets a "Rate this" link; every page gets the licence line, the
account link and, on localhost without a Firebase config, the test-mode banner.
Earnings-22 stays text only. Only the clips the pages use are copied. Every page
gets a description and the site's icon, and its inline scripts are moved into
js/inline/, so the Content-Security-Policy in _headers can refuse inline scripts.

Cloudflare Pages answers a request for part of a file with the whole file, so on
its own a browser could not jump inside a clip. _routes.json sends the audio, and
only the audio, through _worker.js (tools/public_page/_worker.js), which answers
with just the part asked for (hosting/cloudflare-readiness.md).

The rating queue (public/rate/cases.json) is every case with a clip on the data page
(Sonnet: opposite, or severity 3-4), every card's case, and a fixed random sample of
other judged cases whose recording has its audio on a whole-recording page. The
judge's labels go to a separate file (rate/judge.json), which the rating page reads
only after a person has answered.

    python tools/build_site.py && python tools/build_explorer.py   # first, as usual
    python tools/build_public.py                                   # then this
    python tools/check_public.py                                   # and check it

Fill in hosting/firebase-config.js first for a real deploy; without it the pages
run in test mode on localhost. No GPU, no corpora: it reads only site/ and explorer/.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

CAPSTONE = Path(__file__).resolve().parent.parent
SITE = CAPSTONE / "site"
EXPLORER = CAPSTONE / "explorer"
OUT = CAPSTONE / "public"
WIDGETS = CAPSTONE / "web" / "widget"
SITE_PAGE = CAPSTONE / "tools" / "site_page"
PUBLIC_PAGE = CAPSTONE / "tools" / "public_page"
CONFIG = CAPSTONE / "hosting" / "firebase-config.js"

CORPORA = ["scotus", "edacc", "coraal", "earnings22"]
#: Data sets whose audio may be played (Earnings-22's has no stated licence).
WITH_AUDIO = ["scotus", "edacc", "coraal"]
SITE_PAGES = ["index.html", "scotus.html", "edacc.html", "coraal.html", "earnings22.html",
              "compare.html", "data.html", "ai.html"]
#: Other judged cases with audio added to the queue, for "Random" and "Fewest ratings first".
EXTRA_CASES = 1500
SEED = 2026
#: Cloudflare Pages: 20,000 files and 25 MiB a file; its dashboard upload takes 1,000 files.
MAX_FILES, MAX_FILE_MB, DASHBOARD_FILES = 20000, 25, 1000

#: The new pages: file, title, body, script.
NEW_PAGES = [
    ("rate.html", "Rate Clips", "rate.html", "rate.js"),
    ("account.html", "Your Account", "account.html", "account.js"),
    ("admin.html", "Admin", "admin.html", "admin.js"),
    ("privacy.html", "Privacy", "privacy.html", "static.js"),
    ("terms.html", "Contributor Terms", "terms.html", "static.js"),
    ("licences.html", "Credits and Licences", "licences.html", "static.js"),
]

#: One line for search results and link previews, for every page.
DESCRIPTIONS = {
    "index.html": "Where speech-recognition engines get real speech wrong: court arguments, video calls and "
                  "interviews, with the clips to hear and the official transcript beside each engine's.",
    "scotus.html": "Supreme Court oral arguments: the speech-recognition errors that matter most, with clips to hear.",
    "edacc.html": "EdAcc video calls in many accents of English: the speech-recognition errors that matter most, with clips to hear.",
    "coraal.html": "CORAAL interviews in African American Language: the speech-recognition errors that matter most, with clips to hear.",
    "earnings22.html": "Earnings-22 company calls: the speech-recognition errors that matter most, side by side with the transcript.",
    "compare.html": "The four data sets side by side: how often each speech engine is wrong, and in what way.",
    "data.html": "Search every error the study found, download the tables, and see how they were made.",
    "ai.html": "How AI tools were used in this project, and how their work was checked.",
    "rate.html": "Listen to a short clip and say who got it right: the official transcript or the speech engine.",
    "account.html": "Make an account to save ratings, change your display name, or delete your account and ratings.",
    "admin.html": "The site admin's page for exporting ratings.",
    "privacy.html": "What this site keeps about you, why, and how to have it deleted.",
    "terms.html": "What happens to the ratings and corrections you submit, and the licence they are shared under.",
    "licences.html": "Who made the recordings and transcripts on this site, and the licence each one is under.",
    "404.html": "That page isn't here.",
}
RECORDING_DESCRIPTION = "Whole {name} recordings, with the reference transcript and each speech engine's text, word by word."
#: Pages search engines should leave out of their results.
NOINDEX = {"admin.html", "404.html"}
#: Until a date is written into tools/public_page/privacy.html, the build says so.
RETENTION_PLACEHOLDER = "[date not set yet]"

#: Audio types, for the worker in front of the audio (tools/public_page/_worker.js).
AUDIO = (".mp3", ".ogg")


def patch(text: str, old: str, new: str, where: str) -> str:
    """Replace `old` once; stop if it isn't there, so a change to a template can't
    slip a claude.ai-only piece through to the public site unnoticed."""
    if old not in text:
        raise SystemExit(f"build_public: expected text not found in {where}:\n  {old[:120]}")
    return text.replace(old, new)


def json_after(text: str, marker: str) -> tuple[dict, int, int]:
    """The JSON value right after `marker`, and where it starts and ends."""
    at = text.index(marker) + len(marker)
    value, end = json.JSONDecoder().raw_decode(text, at)
    return value, at, end


def replace_json(text: str, marker: str, value) -> str:
    _, a, b = json_after(text, marker)
    return text[:a] + json.dumps(value, ensure_ascii=False) + text[b:]


def as_document(text: str) -> str:
    """The private pages leave the document skeleton to claude.ai; a normal host needs it."""
    text = text.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    if text.lstrip().lower().startswith("<!doctype"):
        return text.replace("<!doctype html>\n", '<!doctype html>\n<html lang="en">\n', 1)
    return ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + text)


def clock(seconds: float) -> str:
    s = max(0, int(seconds))
    h, m, x = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m}:{x:02d}"


def recording_link(corpus: str, recording: str, start: float, root: str = "") -> str:
    """A moment on a whole-recording page, written as site.js's recordingHash does."""
    rid = str(recording).replace("-", "-h").replace("_", "-u")
    return f"{root}recordings/{corpus}/#r-{corpus}-{max(0, math.floor(start - 5))}-{rid}"


def split_context(text: str, fallback: str) -> list[str]:
    """'before [the words] after' -> [before, words, after]."""
    m = re.match(r"^(.*?)\[(.*?)\](.*)$", text or "")
    return [m.group(1).strip(), m.group(2).strip(), m.group(3).strip()] if m else ["", fallback, ""]


# ---------------------------------------------------------------------------
# The rating queue
# ---------------------------------------------------------------------------

def card_cases(pages: dict[str, dict], errors: pd.DataFrame) -> dict[tuple, str]:
    """Each card's case id, found by data set, recording, engine, kind and time."""
    index: dict[tuple, list] = {}
    for r in errors.itertuples():
        if r.start != "":
            index.setdefault((r.corpus, r.recording, r.engine, r.kind), []).append((float(r.start), r.case))
    out = {}
    for d in pages.values():
        for c in all_cards(d):
            got = [case for s, case in index.get((c["corpus"], str(c["recording"]), c["engine"], c["kind"]), [])
                   if abs(s - float(c["start"])) < 0.02]
            if got:
                out[card_key(c)] = got[0]
    return out


def clips_in(value) -> set[str]:
    """Every clip a page's data names (clips/....mp3 or .ogg), wherever it sits."""
    if isinstance(value, dict):
        return set().union(*(clips_in(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(clips_in(v) for v in value)) if value else set()
    return {value} if isinstance(value, str) and re.fullmatch(r"clips/[\w./-]+\.(?:mp3|ogg)", value) else set()


def all_cards(d: dict) -> list[dict]:
    return list(d.get("opposite", [])) + [c for k in d.get("failures", []) for c in k["cards"]]


def card_key(c: dict) -> tuple:
    return (c["corpus"], str(c["recording"]), c["engine"], c["kind"], round(float(c["start"]), 2))


def rating_queue(pages: dict[str, dict], errors: pd.DataFrame, catalogs: dict) -> tuple[dict, dict, dict]:
    """(cases.json, judge.json, {card key: case id}) for the rating page."""
    rows = json.loads((SITE / "data" / "row-clips.json").read_text(encoding="utf-8"))
    by_case = {r.case: r for r in errors.itertuples()}
    audio_of = {(c, r["id"]): r["audio"] for c, cat in catalogs.items() for r in cat if r.get("audio")}
    titles = {(c, r["id"]): r["title"] for c, cat in catalogs.items() for r in cat}
    cards = card_cases(pages, errors)
    card_of = {}
    for d in pages.values():
        for c in all_cards(d):
            if c.get("clip") and card_key(c) in cards:
                card_of[cards[card_key(c)]] = c

    def serious(r) -> bool:
        return r.sonnet_meaning == "opposite" or r.sonnet_severity in ("3", "4")

    picked = [cid for cid in rows["rows"] if cid in by_case] + [cid for cid in card_of if cid not in rows["rows"]]
    have = set(picked)
    others = [r.case for r in errors.itertuples()
              if r.case not in have and r.corpus in WITH_AUDIO and r.start != "" and r.sonnet_meaning != ""
              and (r.corpus, r.recording) in audio_of]
    picked += random.Random(SEED).sample(others, min(EXTRA_CASES, len(others)))

    cases, judge = [], {}
    for cid in picked:
        r = by_case[cid]
        if r.corpus not in WITH_AUDIO:
            continue
        start, end = float(r.start), float(r.end or r.start)
        if cid in card_of:
            c = card_of[cid]
            clip, views, view = c["clip"], c["views"], c["view"]
        elif cid in rows["rows"]:
            f, a, b = rows["rows"][cid]
            clip, view = rows["files"][f], "short"
            views = [{"key": "short", "label": f"{round(b - a)} seconds", "from": a, "to": b}]
        else:
            clip, view = f"recordings/{r.corpus}/{audio_of[(r.corpus, r.recording)]}", "short"
            short, long = [max(0.0, start - 4), end + 4], [max(0.0, start - 12), end + 12]
            views = [{"key": "short", "label": f"{round(short[1] - short[0])} seconds", "from": round(short[0], 2), "to": round(short[1], 2)},
                     {"key": "long", "label": f"{round(long[1] - long[0])} seconds", "from": round(long[0], 2), "to": round(long[1], 2)}]
        title = titles.get((r.corpus, r.recording), f"Recording {r.recording}")
        cases.append({
            "id": cid, "c": r.corpus, "where": f"{title}, {clock(start)} into the recording", "eng": r.engine,
            "rec": split_context(r.record_context, r.record), "hyp": split_context(r.engine_context, r.engine_wrote),
            "clip": clip, "views": views, "view": view,
            "whole": recording_link(r.corpus, r.recording, start) if (r.corpus, r.recording) in titles else "",
            "serious": serious(r),
        })
        judge[cid] = {"meaning": r.sonnet_meaning, "severity": r.sonnet_severity, "reason": r.sonnet_reason,
                      "kind": r.kind, "subkind": r.subkind}
    rng = random.Random(SEED + 1)
    order = [c["id"] for c in cases]
    rng.shuffle(order)
    is_serious = {c["id"]: c.pop("serious") for c in cases}
    return ({"cases": cases, "serious": [i for i in order if is_serious[i]], "all": order},
            judge, cards)


# ---------------------------------------------------------------------------
# The pages
# ---------------------------------------------------------------------------

def public_site_js() -> str:
    """tools/site_page/site.js with the whole-recording pages as relative links and two
    more pages in the bar."""
    js = (SITE_PAGE / "site.js").read_text(encoding="utf-8")
    js = patch(js, "const EXPLORERS = /*EXPLORERS*/{};",
               "const EXPLORERS = " + json.dumps({c: f"recordings/{c}/" for c in CORPORA}) + ";", "site.js")
    return patch(js, '{ file: "ai.html", name: "How AI was used" }]',
                 '{ file: "ai.html", name: "How AI was used" }, { file: "rate.html", name: "Rate clips" }, { file: "account.html", name: "Sign in" }]',
                 "site.js")


def site_page(name: str, text: str, cards: dict, pool: set) -> str:
    """One of build_site.py's pages, made public."""
    text = as_document(text)
    text = replace_json(text, "const EXPLORERS = ", {c: f"recordings/{c}/" for c in CORPORA})
    text = patch(text, '{ file: "ai.html", name: "How AI was used" }]',
                 '{ file: "ai.html", name: "How AI was used" }, { file: "rate.html", name: "Rate clips" }, { file: "account.html", name: "Sign in" }]',
                 name)
    # Each card's case, for its "Rate this" link (public.js draws the link).
    d, _, _ = json_after(text, "const D = ")
    for c in all_cards(d):
        cid = cards.get(card_key(c))
        if cid in pool:
            c["rateCase"] = cid
    text = replace_json(text, "const D = ", d)
    text = patch(text, "</style>", '</style>\n<link rel="stylesheet" href="css/public.css">', name)
    scripts = '<script src="config.js"></script>\n<script src="js/backend.js"></script>\n<script src="js/public.js"></script>\n'
    if name == "data.html":
        scripts += "<script>const RATE_POOL = new Set(" + json.dumps(sorted(pool)) + ");</script>\n"
        text = patch(text, 'link: which === "errors" ? hearAt : null,',
                     'link: which === "errors" ? hearAt : null,\n    rate: which === "errors" ? (r => RATE_POOL.has(r.case) ? `rate.html#case=${r.case}&from=data` : "") : null,',
                     name)
        text = patch(text, '"Open") : ""));',
                     '"Open") : ""));\n        if (opts.rate && opts.rate(r)) tr.lastChild.append(" ", el("a", { href: opts.rate(r), class: "rate-link" }, "Rate this"));',
                     name)
    return patch(text, "<script>\nconst D = ", scripts + "<script>\nconst D = ", name)


def public_meta(meta: dict) -> dict:
    """A whole-recording page's settings, with relative links in place of claude.ai's."""
    return meta | {"siteUrl": "../../index.html", "explorers": {c: f"../{c}/" for c in meta.get("explorers", {})}}


def explorer_page(corpus: str, text: str) -> str:
    """A whole-recording page, made a page of this site at recordings/<data set>/."""
    where = f"explorer/{corpus}/index.html"
    text = as_document(text)
    meta, _, _ = json_after(text, "const META = ")
    text = replace_json(text, "const META = ", public_meta(meta))
    # The laptop-only mode plays files from tools/explore_local.py; never on the public site.
    text = patch(text, 'const LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname) && !location.search.includes("web");',
                 "const LOCAL = false;", where)
    text = patch(text, 'const out = (href, text) => el("a", { href, target: "_blank", rel: "noopener" }, text);',
                 'const out = (href, text) => el("a", href.startsWith("http") ? { href, target: "_blank", rel: "noopener" } : { href }, text);', where)
    text = patch(text, 'out(`${META.siteUrl}#go-${file.replace(".html", "")}`, META.names[c])', "out(`../../${file}`, META.names[c])", where)
    text = patch(text, 'out(`${META.siteUrl}#go-compare`, "Big picture"), out(`${META.siteUrl}#go-data`, "Search the data"),\n    out(`${META.siteUrl}#go-ai`, "How AI was used"));',
                 'out("../../compare.html", "Big picture"), out("../../data.html", "Search the data"),\n    out("../../ai.html", "How AI was used"), out("../../rate.html", "Rate clips"), out("../../account.html", "Sign in"));', where)
    text = patch(text, 'el("a", { href: `${META.siteUrl}#go-ai`, target: "_blank", rel: "noopener" }, "How AI was used")',
                 'el("a", { href: "../../ai.html" }, "How AI was used")', where)
    text = patch(text, 'Full audio is here for as many recordings as the page can hold; the local copy on the 5090 laptop (tools/explore_local.py) plays every one.',
                 "Full audio is here for some of the recordings; the others are text only.", where)
    text = patch(text, "</style>", '</style>\n<link rel="stylesheet" href="../../css/public.css">', where)
    scripts = ('<script>window.SITE_ROOT = "../../";</script>\n<script src="../../config.js"></script>\n'
               '<script src="../../js/backend.js"></script>\n<script src="../../js/public.js"></script>\n')
    return patch(text, "<script>\nconst META = ", scripts + "<script>\nconst META = ", where)


def new_page(file: str, title: str, body: str, script: str, pages: list) -> str:
    shell = (PUBLIC_PAGE / "shell.html").read_text(encoding="utf-8")
    return (shell.replace("/*TITLE*/", title)
                 .replace("/*BODY*/", (PUBLIC_PAGE / body).read_text(encoding="utf-8"))
                 .replace("/*PAGEJS*/", script)
                 .replace("/*DATA*/{}", json.dumps({"pages": pages, "current": file})))


def head_extras(text: str, description: str, root: str, noindex: bool = False) -> str:
    """A description for search results, the site's icon, and noindex where wanted,
    right after the page's title."""
    title = re.search(r"<title>[^<]*</title>\n?", text)
    if not title:
        raise SystemExit("build_public: a page has no <title>")
    extra = (f'<meta name="description" content="{html.escape(description, quote=True)}">\n'
             f'<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">\n')
    if noindex:
        extra += '<meta name="robots" content="noindex">\n'
    if not title.group(0).endswith("\n"):
        extra = "\n" + extra
    return text[:title.end()] + extra + text[title.end():]


def externalise_scripts(text: str, root: str, w: "Writer") -> str:
    """Move each inline <script> into its own file under js/inline/, named by its
    content, so the Content-Security-Policy can refuse every inline script.

    Plain scripts share one set of top-level names whether inline or loaded from a
    file, and a file loaded with <script src> runs at the same point in the page, so
    the pages behave as before. Files with the same content are written once."""
    def move(m: re.Match) -> str:
        code = m.group(1)
        name = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        w.text(f"js/inline/{name}.js", code)
        return f'<script src="{root}js/inline/{name}.js"></script>'
    return re.sub(r"<script>(.*?)</script>", move, text, flags=re.S)


# ---------------------------------------------------------------------------
# The files Cloudflare Pages reads: _headers, _routes.json, _worker.js
# ---------------------------------------------------------------------------

def firebase_version() -> str:
    m = re.search(r'FIREBASE_VERSION = "([\d.]+)"', (PUBLIC_PAGE / "backend.js").read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("build_public: can't find FIREBASE_VERSION in backend.js")
    return m.group(1)


def auth_domain() -> str:
    m = re.search(r'authDomain:\s*"([^"]*)"', CONFIG.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def content_security_policy(pages: dict[str, str]) -> str:
    """The pages' Content-Security-Policy, built from what they load.

    External scripts and stylesheets are allowed by their exact address, taken from
    the pages themselves. The rest is what the Firebase SDK reaches (checked in its
    code, 12.19.0): sign-in at identitytoolkit and securetoken, the database at
    firestore; on phones and Safari, sign-in also opens a hidden frame from the
    project's authDomain, with a loader script from apis.google.com; when the
    database's connection fails it tests the network by loading one image from
    www.google.com. tools/check_public.py loads every page under this policy in Edge,
    in test mode and against a stand-in Firebase, and fails on any refusal."""
    scripts, styles = set(), set()
    for text in pages.values():
        scripts |= set(re.findall(r'<script[^>]*\ssrc="(https://[^"]+)"', text))
        styles |= {u.split("?")[0] for u in re.findall(r'<link rel="stylesheet" href="(https://[^"]+)"', text)}
    fonts = {"https://fonts.gstatic.com"} if any("fonts.googleapis.com" in s for s in styles) else set()
    domain = auth_domain()
    frame = f"https://{domain}" if domain else "https://*.firebaseapp.com"
    parts = [
        ("default-src", ["'self'"]),
        ("script-src", ["'self'", f"https://www.gstatic.com/firebasejs/{firebase_version()}/", "https://apis.google.com", *sorted(scripts)]),
        ("style-src", ["'self'", "'unsafe-inline'", *sorted(styles)]),
        ("font-src", ["'self'", *sorted(fonts)]),
        ("img-src", ["'self'", "data:", "https://www.google.com/images/cleardot.gif"]),
        ("media-src", ["'self'"]),
        ("connect-src", ["'self'", "https://identitytoolkit.googleapis.com", "https://securetoken.googleapis.com",
                         "https://firestore.googleapis.com"]),
        ("frame-src", [frame]),
        ("worker-src", ["'self'"]),
        ("object-src", ["'none'"]),
        ("base-uri", ["'self'"]),
        ("form-action", ["'self'"]),
        ("frame-ancestors", ["'none'"]),
    ]
    return "; ".join(f"{k} {' '.join(v)}" for k, v in parts)


def headers_file(csp: str) -> str:
    """public/_headers: security headers on everything, and how long browsers keep files.

    Cloudflare Pages already sends nosniff and strict-origin-when-cross-origin; they
    are written here too so the file says everything in one place. HTML, data and
    transcripts keep Pages' default (check with the server each time, cheap thanks
    to ETags), so an update shows at once. The scripts moved out of the pages are
    named by their content and never change, so they are kept for a year. Audio is
    kept a day: its names don't change when a clip is re-cut."""
    return "\n".join([
        "# Made by tools/build_public.py; edit there, not here. Cloudflare Pages reads this",
        "# file and does not serve it. Limits: 100 rules, 2,000 characters a line.",
        "/*",
        f"  Content-Security-Policy: {csp}",
        "  Strict-Transport-Security: max-age=31536000",
        "  X-Content-Type-Options: nosniff",
        "  X-Frame-Options: DENY",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
        "  Cross-Origin-Opener-Policy: same-origin",
        "",
        "/js/inline/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
        "/clips/*",
        "  Cache-Control: public, max-age=86400",
        "",
        "/recordings/:corpus/audio/*",
        "  Cache-Control: public, max-age=86400",
        "",
    ])


def routes_file() -> str:
    """public/_routes.json: send only the audio through _worker.js. Everything else is
    served by Pages directly, free and without counting against the worker's daily
    allowance."""
    include = ["/clips/*"] + [f"/recordings/{c}/audio/*" for c in WITH_AUDIO]
    return json.dumps({"version": 1, "include": include, "exclude": []}, indent=2) + "\n"


def robots_file() -> str:
    return "# Everything here is public. Preview deployments are kept out of search by Cloudflare itself.\nUser-agent: *\nAllow: /\n"


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="6" fill="#14213d"/>
<path d="M6 16h3M11 10v12M15 6v20M19 11v10M23 13v6M26 16h0" stroke="#ffe066" stroke-width="2.4" stroke-linecap="round"/>
</svg>
"""


# ---------------------------------------------------------------------------

class Writer:
    """Writes public/, copying a file only when it changed, and removes what is no
    longer part of the site."""

    def __init__(self, root: Path):
        self.root, self.kept = root, set()

    def text(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8", newline="\n")
        self.kept.add(path)

    def copy(self, rel: str, src: Path) -> None:
        if not src.is_file():
            raise SystemExit(f"build_public: a page needs {src}, which isn't there. Run the site's builders first.")
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        s = src.stat()
        if not path.exists() or path.stat().st_size != s.st_size or int(path.stat().st_mtime) != int(s.st_mtime):
            shutil.copy2(src, path)
        self.kept.add(path)

    def prune(self) -> int:
        gone = 0
        for p in sorted(self.root.rglob("*"), reverse=True):
            if p.is_file() and p not in self.kept:
                p.unlink()
                gone += 1
            elif p.is_dir() and not any(p.iterdir()):
                p.rmdir()
        return gone


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=OUT, help="where to write (default public/)")
    args = parser.parse_args()
    out = args.out.resolve()
    w = Writer(out)

    texts = {name: (SITE / name).read_text(encoding="utf-8") for name in SITE_PAGES}
    pages = {name: json_after(t, "const D = ")[0] for name, t in texts.items()}
    errors = pd.read_csv(SITE / "data" / "errors.csv", dtype=str, keep_default_na=False)
    catalogs = {c: json.loads((EXPLORER / c / "catalog.json").read_text(encoding="utf-8")) for c in CORPORA}

    queue, judge, cards = rating_queue(pages, errors, catalogs)
    pool = {c["id"] for c in queue["cases"]}
    w.text("rate/cases.json", json.dumps(queue, ensure_ascii=False, separators=(",", ":")))
    w.text("rate/judge.json", json.dumps(judge, ensure_ascii=False, separators=(",", ":")))

    # Every page goes out through finish(): a description, the icon, and its inline
    # scripts moved to files (for the Content-Security-Policy).
    built: dict[str, str] = {}

    def finish(rel: str, text: str, description: str) -> None:
        root = "../" * rel.count("/")
        text = externalise_scripts(head_extras(text, description, root, Path(rel).name in NOINDEX and "/" not in rel), root, w)
        built[rel] = text
        w.text(rel, text)

    # The site's pages, and every clip and data file they use.
    used = set()
    for name, text in texts.items():
        finish(name, site_page(name, text, cards, pool), DESCRIPTIONS[name])
        used |= clips_in(pages[name])
    rows = json.loads((SITE / "data" / "row-clips.json").read_text(encoding="utf-8"))
    used |= set(rows["files"])
    used |= {c["clip"] for c in queue["cases"] if c["clip"].startswith("clips/")}
    for rel in sorted(used):
        w.copy(rel, SITE / rel)
    for p in sorted((SITE / "data").iterdir()):
        if p.is_file():
            w.copy(f"data/{p.name}", p)

    # The whole-recording pages, without the laptop's own file list or screenshots.
    for c in CORPORA:
        src = EXPLORER / c
        meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
        name = (meta.get("names") or {}).get(c) or c
        finish(f"recordings/{c}/index.html", explorer_page(c, (src / "index.html").read_text(encoding="utf-8")),
               RECORDING_DESCRIPTION.format(name=name))
        w.copy(f"recordings/{c}/catalog.json", src / "catalog.json")
        w.text(f"recordings/{c}/meta.json", json.dumps(public_meta(meta)))
        for sub in ("rec", "audio"):
            if c == "earnings22" and sub == "audio":
                continue
            for p in sorted((src / sub).glob("*")) if (src / sub).exists() else []:
                w.copy(f"recordings/{c}/{sub}/{p.name}", p)

    # The public site's own pages and what they load.
    nav_pages = pages["index.html"]["pages"]
    for file, title, body, script in NEW_PAGES:
        finish(file, new_page(file, title, body, script, nav_pages), DESCRIPTIONS[file])
    w.text("css/site.css", "\n".join((p).read_text(encoding="utf-8") for p in
                                     (WIDGETS / "tokens.css", SITE_PAGE / "site.css", PUBLIC_PAGE / "public.css")))
    w.text("css/public.css", (PUBLIC_PAGE / "public.css").read_text(encoding="utf-8"))
    w.text("js/widgets.js", (WIDGETS / "listen.js").read_text(encoding="utf-8") + "\n" + (WIDGETS / "compare.js").read_text(encoding="utf-8"))
    w.text("js/site.js", public_site_js())
    for name in ("backend.js", "public.js", "rate.js", "account.js", "admin.js", "static.js"):
        w.text(f"js/{name}", (PUBLIC_PAGE / name).read_text(encoding="utf-8"))
    w.text("config.js", CONFIG.read_text(encoding="utf-8"))
    # Cloudflare serves 404.html at whatever address was missing, however deep, so
    # its links and scripts are taken from the top of the site.
    page404 = new_page("404.html", "Not Found", "404.html", "static.js", nav_pages)
    finish("404.html", patch(page404, "<title>", '<base href="/">\n<title>', "404.html"), DESCRIPTIONS["404.html"])

    # What Cloudflare Pages reads (hosting/cloudflare-readiness.md).
    w.text("_headers", headers_file(content_security_policy(built)))
    w.text("_routes.json", routes_file())
    w.text("_worker.js", (PUBLIC_PAGE / "_worker.js").read_text(encoding="utf-8"))
    w.text("robots.txt", robots_file())
    w.text("favicon.svg", FAVICON)
    w.text("_redirects", "# Made by tools/build_public.py. Browsers ask for /favicon.ico on their own.\n/favicon.ico /favicon.svg 301\n")

    gone = w.prune()
    files = [p for p in out.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    biggest = max(files, key=lambda p: p.stat().st_size)
    print(f"{out}: {len(files)} files, {size / 1e9:.2f} GB; largest {biggest.relative_to(out)} "
          f"({biggest.stat().st_size / 2**20:.1f} MiB); {gone} old files removed")
    print(f"rating queue: {len(queue['cases'])} clips, {len(queue['serious'])} of them likely serious; "
          f"{sum(1 for d in pages.values() for c in all_cards(d))} cards, "
          f"{sum(1 for c in cards.values() if c in pool)} with a Rate link")
    config = CONFIG.read_text(encoding="utf-8")
    configured = re.search(r'apiKey:\s*"[^"]+"', config)
    print("Firebase config: " + ("filled in" if configured else "EMPTY - the pages run in test mode on localhost only"))
    # What still needs a person before the site goes live (hosting/SETUP.md, go-live checklist).
    todo = []
    if not configured:
        todo.append("hosting/firebase-config.js: paste the Firebase web config (SETUP.md step 6)")
    if not re.search(r'contactEmail:\s*"[^"]+"', config):
        todo.append("hosting/firebase-config.js: contactEmail is empty, so the privacy page has no contact address")
    if RETENTION_PLACEHOLDER in (PUBLIC_PAGE / "privacy.html").read_text(encoding="utf-8"):
        todo.append(f"tools/public_page/privacy.html: the date email addresses are deleted is still {RETENTION_PLACEHOLDER}")
    for t in todo:
        print("Before going live: " + t)
    if len(files) > MAX_FILES or biggest.stat().st_size > MAX_FILE_MB * 2**20:
        print(f"WARNING: over Cloudflare Pages' limits ({MAX_FILES} files, {MAX_FILE_MB} MiB a file)")
        return 1
    if len(files) > DASHBOARD_FILES:
        print(f"Note: more than {DASHBOARD_FILES} files, so the dashboard's drag-and-drop upload won't take it; use wrangler (SETUP.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

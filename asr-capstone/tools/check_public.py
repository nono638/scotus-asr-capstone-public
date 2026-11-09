"""Check the public site (tools/build_public.py -> public/) before uploading it.

Two kinds of check:

- On the files: every link and every file a page or its data names is in public/;
  no claude.ai address is left; every clip in the rating queue exists; nothing is
  over Cloudflare Pages' limits.
- In Edge, in the pages' TEST MODE (a pretend backend in the browser; there is no
  Firebase project to talk to): make an account, confirm the email, sign out and
  in, reset a password; rate a clip with the gate closed (refused), then as an
  allowlisted tester (saved), change the answer (saved again, still one rating);
  the judge's labels stay hidden until the answer is saved; the admin page refuses
  a non-admin and exports a CSV of the right shape; the cards and the data page's
  serious rows have "Rate this" links; the whole-recording pages load; every link
  drawn on each page leads to a file that exists. Clips play (tools/check_page.py's
  player check).

- The hosting files: _headers parses, stays inside Cloudflare's limits and has the
  security headers; its Content-Security-Policy allows every outside script and
  stylesheet the pages name and no inline script; _routes.json sends every audio
  file, and nothing else, through _worker.js; 404.html, robots.txt and the icon
  are there; no page has an inline script left.
- Every page: a title of its own, a description, a language, one main heading,
  labels on every form field, alt text on every image, names on buttons and
  links, and the footer's links to the credits, privacy, contributor terms and
  contact. The sign-up form links the privacy notice.

Served from a local port the way Cloudflare Pages serves it: the headers from
_headers on every response, /page for /page.html, 404.html with status 404 for any
missing address, and a request for part of a file answered with the whole file.
public/_worker.js is run in Edge as a service worker in front of the audio, as Pages
runs it, so the clips' jumps go through the same code. Any Content-Security-Policy
refusal on any page is a failure. A second run puts the pages in Firebase mode
against a stand-in config: the real SDK loads from gstatic, and calls to Google's
sign-in and database addresses are answered locally, so nothing reaches a real
project; it checks the policy lets those calls out (desktop, and as an iPhone, where
sign-in also opens a hidden frame).

    python tools/check_public.py [--show]
    python tools/check_public.py --serve 8000     # just serve public/ to try it by hand
    python tools/check_public.py --live https://asr-errors.pages.dev   # after uploading

--live checks the real site from outside, with Python alone: the headers arrive,
/no-such-page gives the 404 page with status 404, a clip answers a range with 206,
each file type has the right Content-Type, and _headers is not served.

Prints one line per check and exits 1 if any failed. What it cannot check: Firebase
itself and the Firestore rules (hosting/firestore.rules), which need a real project.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import functools
import re
import socketserver
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_page  # noqa: E402  (its server, check() and player check)
from check_page import check  # noqa: E402

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright  # noqa: E402


def _wait_for_function(self, expression, arg=None, timeout=30000, polling=None):
    """Page.wait_for_function, by asking again and again. Playwright's own version
    runs its test through eval inside the page, which the site's
    Content-Security-Policy refuses (rightly); page.evaluate is not affected."""
    end = time.monotonic() + (timeout or 30000) / 1000
    while True:
        if self.evaluate(expression, arg) if arg is not None else self.evaluate(expression):
            return True
        if time.monotonic() > end:
            raise PlaywrightTimeout(f"Timeout {timeout}ms exceeded waiting for: {expression[:100]}")
        time.sleep(0.05)


Page.wait_for_function = _wait_for_function   # also used by check_page.play_and_watch

CAPSTONE = Path(__file__).resolve().parent.parent
PUBLIC = CAPSTONE / "public"
TEXT = {".html", ".js", ".json", ".css", ".csv", ".txt"}
COLUMNS = ["rating_id", "uid", "case", "corpus", "licence", "guidelines", "came_from", "features",
           "who_right", "record_right", "corrected", "feedback", "played", "created", "updated"]


def target(root: Path, base: str, href: str) -> Path | None:
    """The file in public/ an address on page `base` points to, or None if it leaves the site.
    /page means page.html, as on Cloudflare Pages."""
    url = urljoin(base, href)
    p = urlparse(url)
    if p.scheme not in ("http", "https") or p.netloc != urlparse(base).netloc:
        return None
    path = unquote(p.path).lstrip("/")
    f = root / path
    if not path or path.endswith("/"):
        return f / "index.html"
    if not f.exists() and f.with_name(f.name + ".html").exists():
        return f.with_name(f.name + ".html")
    return f


# ---------------------------------------------------------------------------
# Cloudflare Pages' files, and a local server that behaves like Pages
# ---------------------------------------------------------------------------

AUDIO = (".mp3", ".ogg")
HOSTING = {"_headers", "_routes.json", "_worker.js", "_redirects"}


def read_headers(path: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    """public/_headers as [(path pattern, [(name, value), ...]), ...]. A name starting
    with "! " removes that header, as on Pages."""
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            rules.append((line.strip(), []))
        elif rules:
            name, _, value = line.strip().partition(":")
            rules[-1][1].append((name.strip(), value.strip()))
    return rules


def pattern_regex(pattern: str) -> re.Pattern:
    """A _headers or _routes.json path: * matches anything, :name one path segment."""
    out = ""
    for part in re.split(r"(\*|:[A-Za-z]\w*)", pattern):
        out += ".*" if part == "*" else "[^/]+" if part.startswith(":") and len(part) > 1 else re.escape(part)
    return re.compile(out)


def headers_for(rules, path: str) -> dict[str, str]:
    """The headers Pages adds to `path`: every matching rule, the same header joined with commas."""
    got: dict[str, list[str]] = {}
    for pattern, items in rules:
        if pattern_regex(pattern).fullmatch(path):
            for name, value in items:
                if name.startswith("!"):
                    got.pop(name[1:].strip().lower(), None)
                else:
                    got.setdefault(name.lower(), []).append(value)
    return {k: ", ".join(v) for k, v in got.items()}


def csp_of(headers: dict[str, str]) -> dict[str, list[str]]:
    out = {}
    for part in headers.get("content-security-policy", "").split(";"):
        bits = part.split()
        if bits:
            out[bits[0]] = bits[1:]
    return out


def csp_allows(sources: list[str], url: str) -> bool:
    """Whether a CSP source list lets `url` load (host, and path when the source has one)."""
    u = urlparse(url)
    for s in sources:
        if s in ("*",) or s == f"{u.scheme}:":
            return True
        if not s.startswith("https://"):
            continue
        h = urlparse(s)
        host_ok = u.hostname == h.hostname or (h.hostname.startswith("*.") and u.hostname.endswith(h.hostname[1:]))
        path = h.path or "/"
        path_ok = path == "/" or (u.path.startswith(path) if path.endswith("/") else u.path == path)
        if host_ok and path_ok:
            return True
    return False


def routes_hit(routes: dict, path: str) -> bool:
    hit = lambda rules: any(pattern_regex(r).fullmatch(path) for r in rules)
    return hit(routes.get("include", [])) and not hit(routes.get("exclude", []))


SERVICE_WORKER = """// Only for tools/check_public.py: runs public/_worker.js in front of the audio, as
// Cloudflare Pages does, with Pages' assets standing behind it.
import worker from "/__check_worker.js";
const INCLUDE = %s, EXCLUDE = %s;   // _routes.json, as patterns
const hit = (p, rules) => rules.some(r => new RegExp("^(?:" + r + ")$").test(p));
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin || !hit(u.pathname, INCLUDE) || hit(u.pathname, EXCLUDE)) return;
  e.respondWith(worker.fetch(e.request, { ASSETS: { fetch: r => fetch(r) } }));
});
"""


def service_worker(root: Path) -> bytes:
    routes = json.loads((root / "_routes.json").read_text(encoding="utf-8"))
    pats = lambda key: json.dumps([pattern_regex(r).pattern for r in routes.get(key, [])])
    return (SERVICE_WORKER % (pats("include"), pats("exclude"))).encode("utf-8")


class PagesHandler(check_page.RangeHandler):
    """Serves public/ as Cloudflare Pages does (hosting/cloudflare-readiness.md):
    _headers on every response; /page.html redirected to /page and /dir/index.html to
    /dir/; /page served from page.html; 404.html with status 404 for anything missing;
    the hosting files not served; the redirects in _redirects; and, unless `ranges` is
    set (for --serve), a Range request answered with the whole file and 200."""

    ranges = False
    root = PUBLIC

    def send_head(self):
        self._left = None
        self._extra = headers_for(self._rules(), urlparse(self.path).path)
        path = unquote(urlparse(self.path).path)
        if path == "/__check_sw.js":
            return self._bytes(200, "text/javascript", service_worker(self.root))
        if path == "/__check_worker.js":
            return self._bytes(200, "text/javascript", (self.root / "_worker.js").read_bytes())
        for line in self._redirects():
            src, dest, *code = line.split()
            if path == src:
                return self._redirect(dest, int(code[0]) if code else 302)
        name = path.rsplit("/", 1)[-1]
        if path.count("/") == 1 and name in HOSTING:
            return self._not_found()
        if path.endswith("/index.html"):
            return self._redirect(path[:-len("index.html")], 308)
        if path.endswith(".html") and path != "/404.html":
            return self._redirect(path[:-len(".html")], 308)
        # Pages knows files, not folders: /x is x.html, or x/index.html after a redirect
        # to /x/. (So /rate is rate.html, though rate/cases.json sits beside it.)
        f = self.root / path.lstrip("/")
        page = self.root / (path.strip("/") + ".html")
        if path.endswith("/"):
            if (f / "index.html").is_file():
                f = f / "index.html"
            elif path != "/" and page.is_file():
                return self._redirect(path.rstrip("/"), 308)
            else:
                return self._not_found()
        elif not f.is_file():
            if page.is_file():
                f = page
            elif (f / "index.html").is_file():
                return self._redirect(path + "/", 308)
            else:
                return self._not_found()
        self.path = "/" + f.relative_to(self.root).as_posix()
        if not self.ranges and "Range" in self.headers:
            del self.headers["Range"]
        return super().send_head()

    def _rules(self):
        h = self.root / "_headers"
        return read_headers(h) if h.exists() else []

    def _redirects(self):
        r = self.root / "_redirects"
        return [l for l in r.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if r.exists() else []

    def _bytes(self, status: int, kind: str, data: bytes):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        return io.BytesIO(data)

    def _redirect(self, where: str, status: int):
        query = urlparse(self.path).query
        self.send_response(status)
        self.send_header("Location", where + ("?" + query if query else ""))
        self.send_header("Content-Length", "0")
        self.end_headers()
        return None

    def _not_found(self):
        page = self.root / "404.html"
        return self._bytes(404, "text/html; charset=utf-8", page.read_bytes() if page.exists() else b"Not found")

    def end_headers(self):
        for k, v in getattr(self, "_extra", {}).items():
            self.send_header(k, v)
        super().end_headers()


def serve_like_pages(root: Path, port: int = 0, ranges: bool = False):
    handler = functools.partial(type("Handler", (PagesHandler,), {"root": root, "ranges": ranges}), directory=str(root))
    server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def check_hosting(root: Path) -> None:
    """The files Cloudflare Pages reads, and what every page needs from them."""
    for name in ("_headers", "_routes.json", "_worker.js", "404.html", "robots.txt", "favicon.svg"):
        check((root / name).is_file(), f"public/{name} is there")
    text = (root / "_headers").read_text(encoding="utf-8")
    rules = read_headers(root / "_headers")
    check(0 < len(rules) <= 100, f"_headers: {len(rules)} rules (Pages takes up to 100)")
    long = [l[:60] for l in text.splitlines() if len(l) > 2000]
    check(not long, "_headers: no line over 2,000 characters" + (f": {long}" if long else ""))
    check(all(p.startswith("/") and items for p, items in rules), "_headers: every rule is a path with at least one header")
    check(all(re.fullmatch(r"!?\s?[A-Za-z0-9-]+", n) and v for _, items in rules for n, v in items),
          "_headers: every line is 'Name: value'")
    check(all(p.count("*") <= 1 for p, _ in rules), "_headers: at most one * in each path, as Pages allows")
    page = headers_for(rules, "/scotus")
    for name in ("content-security-policy", "strict-transport-security", "x-content-type-options",
                 "referrer-policy", "permissions-policy", "x-frame-options"):
        check(name in page, f"_headers: pages get {name}")
    check(page.get("x-content-type-options") == "nosniff", "_headers: nosniff")
    check(page.get("referrer-policy") in ("strict-origin-when-cross-origin", "strict-origin"),
          "_headers: the referrer policy still sends the site's address to Firebase (an API key limited to the site needs it)")
    check("max-age=" in page.get("strict-transport-security", ""), "_headers: HSTS has a max-age")
    csp = csp_of(page)
    check(page.get("content-security-policy", "").count("default-src") == 1, "_headers: exactly one Content-Security-Policy applies to a page")
    check(csp.get("object-src") == ["'none'"] and csp.get("frame-ancestors") == ["'none'"] and csp.get("base-uri") == ["'self'"],
          "CSP: no plugins, no framing by other sites, no outside <base>")
    script = csp.get("script-src", [])
    check(script and not any(s in script for s in ("'unsafe-inline'", "'unsafe-eval'", "*", "https:", "data:")),
          f"CSP: scripts only from named places, no inline scripts or eval")
    check(not any(s in ("https://www.gstatic.com", "https://cdnjs.cloudflare.com") for s in script),
          "CSP: shared script hosts (gstatic, cdnjs) are allowed by exact path, not whole")
    version = re.search(r'FIREBASE_VERSION = "([\d.]+)"', (root / "js" / "backend.js").read_text(encoding="utf-8")).group(1)
    check(csp_allows(script, f"https://www.gstatic.com/firebasejs/{version}/firebase-auth.js"), f"CSP: the Firebase SDK {version} may load")
    for need in ("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword", "https://securetoken.googleapis.com/v1/token",
                 "https://firestore.googleapis.com/google.firestore.v1.Firestore/Listen/channel"):
        check(csp_allows(csp.get("connect-src", []), need), f"CSP: the pages may reach {urlparse(need).hostname}")
    # Every outside script and stylesheet any page names is allowed.
    outside, inline = [], []
    for f in root.rglob("*.html"):
        t = f.read_text(encoding="utf-8")
        rel = f.relative_to(root).as_posix()
        for u in re.findall(r'<script[^>]*\ssrc="(https?://[^"]+)"', t):
            if not csp_allows(script, u):
                outside.append(f"{rel}: {u}")
        for u in re.findall(r'<link rel="stylesheet" href="(https?://[^"]+)"', t):
            if not csp_allows(csp.get("style-src", []), u):
                outside.append(f"{rel}: {u}")
        if re.search(r"<script(?![^>]*\ssrc=)[^>]*>\s*\S", t) or re.search(r"\son[a-z]+=\"", t):
            inline.append(rel)
    check(not outside, "CSP: allows every outside script and stylesheet the pages name" + (f": {outside[:3]}" if outside else ""))
    check(not inline, "no page has an inline script or onclick= left (the CSP would refuse it)" + (f": {inline[:4]}" if inline else ""))
    # _routes.json: every audio file through the worker, nothing else.
    routes = json.loads((root / "_routes.json").read_text(encoding="utf-8"))
    rules_n = len(routes.get("include", [])) + len(routes.get("exclude", []))
    check(routes.get("version") == 1 and routes.get("include") and rules_n <= 100
          and all(len(r) <= 100 and r.startswith("/") for r in routes["include"] + routes.get("exclude", [])),
          f"_routes.json: version 1, {rules_n} rules, within Pages' limits")
    files = ["/" + p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    audio = [f for f in files if f.endswith(AUDIO)]
    missed = [f for f in audio if not routes_hit(routes, f)]
    extra = [f for f in files if routes_hit(routes, f) and not f.endswith(AUDIO)]
    check(not missed, f"_routes.json: all {len(audio)} audio files go through the worker (so they can jump)" + (f": {missed[:3]}" if missed else ""))
    check(not extra, "_routes.json: nothing but audio goes through it (the rest stays free and unlimited)" + (f": {extra[:3]}" if extra else ""))
    check(len(files) <= 1000, f"{len(files)} files: fits the dashboard's drag-and-drop upload (1,000)")
    check(b"Allow: /" in (root / "robots.txt").read_bytes(), "robots.txt lets search engines in")
    check('<base href="/">' in (root / "404.html").read_text(encoding="utf-8"),
          "404.html takes its links from the top of the site (it is shown at any depth)")


# ---------------------------------------------------------------------------
# The files
# ---------------------------------------------------------------------------

def with_scripts(root: Path, page: str) -> str:
    """A page and the scripts build_public.py moved out of it (js/inline/), as one text."""
    text = (root / page).read_text(encoding="utf-8")
    for src in re.findall(r'<script src="((?:\.\./)*js/inline/[0-9a-f]+\.js)"', text):
        text += "\n" + (root / Path(page).parent / src).resolve().read_text(encoding="utf-8")
    return text


def check_files(root: Path) -> None:
    files = [p for p in root.rglob("*") if p.is_file()]
    check(bool(files), f"public/ has {len(files)} files")
    check(len(files) <= 20000, f"under Cloudflare Pages' 20,000 files ({len(files)}; the dashboard upload takes 1,000)")
    big = [p for p in files if p.stat().st_size > 25 * 2**20]
    check(not big, "no file over 25 MiB" + (f": {big[:3]}" if big else ""))
    left = []
    for p in files:
        if p.suffix in TEXT and re.search(r"https?://claude\.ai|claude\.ai/(artifact|code)", p.read_text(encoding="utf-8", errors="replace")):
            left.append(str(p.relative_to(root)))
    check(not left, "no claude.ai addresses left" + (f": {left[:5]}" if left else ""))
    check(not list(root.rglob("local-audio.json")), "the laptop's own audio list is not published")

    # Static src= and href= in the pages.
    missing = []
    for page in root.rglob("*.html"):
        base = "http://site/" + page.relative_to(root).as_posix()
        for href in re.findall(r'(?:src|href)="([^"]+)"', page.read_text(encoding="utf-8")):
            if "${" in href or href.startswith(("#", "mailto:")):
                continue
            f = target(root, base, href)
            if f is not None and not f.exists():
                missing.append(f"{page.relative_to(root)} -> {href}")
    check(not missing, "every static link and script in the pages exists" + (f": {missing[:5]}" if missing else ""))

    # The rating queue's clips, and the whole-recording pages' audio.
    queue = json.loads((root / "rate" / "cases.json").read_text(encoding="utf-8"))
    gone = sorted({c["clip"] for c in queue["cases"] if not (root / c["clip"]).exists()})
    check(not gone, f"all {len(queue['cases'])} clips in the rating queue have their audio" + (f": {gone[:3]}" if gone else ""))
    check(all(c["c"] in ("scotus", "edacc", "coraal") for c in queue["cases"]), "no Earnings-22 audio in the rating queue")
    leaked = [k for c in queue["cases"] for k in c if k in ("meaning", "severity", "reason", "sonnet_meaning", "serious")]
    check(not leaked, "the queue file holds none of the judge's labels (they are in rate/judge.json)")
    judge = json.loads((root / "rate" / "judge.json").read_text(encoding="utf-8"))
    check(set(judge) == {c["id"] for c in queue["cases"]}, "rate/judge.json has every queued case")
    for c in ("scotus", "edacc", "coraal", "earnings22"):
        cat = json.loads((root / "recordings" / c / "catalog.json").read_text(encoding="utf-8"))
        no = [r["audio"] for r in cat if r.get("audio") and not (root / "recordings" / c / r["audio"]).exists()]
        shards = [r["shard"] for r in cat if not (root / "recordings" / c / r["shard"]).exists()]
        check(not no and not shards, f"recordings/{c}: every catalogued audio file and transcript exists")
        check(c != "earnings22" or not list((root / "recordings" / c).glob("audio/*")), f"recordings/{c}: no audio" if c == "earnings22" else f"recordings/{c}: ok")
    rows = json.loads((root / "data" / "row-clips.json").read_text(encoding="utf-8"))
    check(all((root / f).exists() for f in rows["files"]), "the data page's row clips exist")
    for page in ("scotus.html", "edacc.html", "coraal.html", "index.html"):
        text = with_scripts(root, page)
        clips = set(re.findall(r'"clip": ?"(clips/[^"]+)"', text))
        check(all((root / c).exists() for c in clips), f"{page}: all {len(clips)} card clips exist")


# ---------------------------------------------------------------------------
# In the browser
# ---------------------------------------------------------------------------

def links_on(page, root: Path, label: str) -> None:
    """Every link drawn on the page that stays on the site leads to a file."""
    hrefs = page.eval_on_selector_all("a[href]", "as => as.map(a => a.href)")
    bad = sorted({h for h in hrefs if (f := target(root, page.url, h)) is not None and not f.exists()})
    check(not bad, f"{label}: all {len(hrefs)} links lead somewhere" + (f": {bad[:4]}" if bad else ""))


def test_state(page) -> dict:
    return page.evaluate("JSON.parse(localStorage.getItem('site.testBackend') || '{}')")


def check_account(page, url: str) -> None:
    page.goto(f"{url}/account.html")
    page.wait_for_selector("#test-banner")
    check("TEST MODE" in page.inner_text("#test-banner"), "account: the test-mode banner shows")
    page.click("[data-test=wipe]")
    page.wait_for_selector("#signup-form", state="visible")
    # A short password is refused before anything is made.
    page.fill("#up-name", "Tester")
    page.fill("#up-email", "tester@example.com")
    page.fill("#up-password", "short")
    page.check("#up-adult"); page.check("#up-terms")
    page.evaluate("document.querySelector('#up-password').removeAttribute('minlength')")
    page.click("#signup-form button[type=submit]")
    page.wait_for_function("document.querySelector('#up-say').textContent.includes('8 characters')", timeout=3000)
    check(True, "account: a short password is refused")
    page.fill("#up-password", "a-long-password")
    page.click("#signup-form button[type=submit]")
    page.wait_for_selector("#verify", state="visible")
    check(page.is_visible("#verify"), "account: after sign-up it asks to confirm the email")
    try:
        page.wait_for_function("document.querySelector('#nav').innerText.includes('Account (Tester)')", timeout=5000)
    except Exception:
        pass
    check("Account (Tester)" in page.inner_text("#nav"), "account: the bar shows the display name")
    check("check your address" in page.inner_text("#test-banner"), "account: a (pretend) verification email was sent")
    page.click("[data-test=verify]")
    page.click("#verify-done")
    page.wait_for_selector("#verify", state="hidden")
    check(True, "account: after the link is clicked the email counts as confirmed")
    page.fill("#me-name", "Tester Two")
    page.click("#profile-form button[type=submit]")
    page.wait_for_function("document.querySelector('#me-say').textContent === 'Saved.'")
    check(test_state(page)["profiles"] and list(test_state(page)["profiles"].values())[0]["displayName"] == "Tester Two",
          "account: the display name is saved")
    check("tester@example.com" not in json.dumps(test_state(page)["profiles"]), "account: the profile has no email in it")
    check(not page.is_visible("#bg-label"), "account: the background question is off")
    page.click("#signout")
    page.wait_for_selector("#signin-form", state="visible")
    check(True, "account: sign out")
    page.fill("#in-email", "tester@example.com"); page.fill("#in-password", "wrong-password")
    page.click("#signin-form button[type=submit]")
    page.wait_for_function("document.querySelector('#in-say').textContent.includes(\"don't match\")")
    check(True, "account: a wrong password is refused")
    page.fill("#in-password", "a-long-password")
    page.click("#signin-form button[type=submit]")
    page.wait_for_selector("#signed-in", state="visible")
    check(True, "account: sign in")
    page.click("#signout")
    page.wait_for_selector("#reset-form", state="visible")
    page.fill("#reset-email", "tester@example.com")
    page.click("#reset-form button[type=submit]")
    page.wait_for_function("document.querySelector('#reset-say').textContent.includes('on its way')")
    check("reset your password" in page.inner_text("#test-banner"), "account: password reset sends a (pretend) email")
    page.fill("#in-email", "tester@example.com"); page.fill("#in-password", "a-long-password")
    page.click("#signin-form button[type=submit]")
    page.wait_for_selector("#signed-in", state="visible")


def answer_clip(page) -> None:
    page.check("#features input[value=soundalike]")
    page.check("#features input[value=small]")
    page.check("#who input[value=record]")
    page.check("#record input[value=yes]")
    page.fill("#feedback", "=1+1 a test, with a comma")


def check_rate(page, url: str, judge_requests: list) -> str:
    page.goto(f"{url}/rate.html")
    page.wait_for_selector("#case .failure-card")
    page.wait_for_selector("#gate", state="visible", timeout=5000)
    check(page.is_visible("#gate"), "rate: the gate notice shows while the site is closed to the public")
    case_id = page.evaluate("current.id")
    check(not page.is_visible("#judge") and not judge_requests, "rate: the judge's labels are hidden and not even fetched before answering")
    # Play the clip.
    button = page.locator("#case .listen-controls button").first
    check_page.play_and_watch(page, button, "rate: the clip")
    answer_clip(page)
    page.click("#save")
    page.wait_for_function("document.querySelector('#say').textContent.includes('invited testers')")
    check(not test_state(page)["ratings"], "rate: with the gate closed and not on the allowlist, nothing is saved")
    check(not page.is_visible("#judge"), "rate: still blind after a refused save")
    page.check("[data-test=allowlist]")
    page.wait_for_timeout(200)
    answer_clip(page)
    page.click("#save")
    page.wait_for_function("document.querySelector('#say').textContent.includes('Saved')")
    s = test_state(page)
    r = list(s["ratings"].values())
    check(len(r) == 1 and r[0]["case"] == case_id, "rate: on the allowlist, the rating is saved, one per person per case")
    check(r and r[0]["features"] == ["soundalike", "small"] and r[0]["who_right"] == "record" and r[0]["played"],
          f"rate: the answer is stored as given ({r[0] if r else None})")
    check(s["counts"].get(case_id) == 1, "rate: the case's rating count is 1")
    page.wait_for_selector("#judge", state="visible")
    check(bool(judge_requests) and "AI judge" in page.inner_text("#judge"), "rate: the judge's labels show after answering")
    first = r[0]
    # Change the answer.
    page.wait_for_timeout(50)
    page.check("#who input[value=engine]")
    page.fill("#corrected", "what I heard")
    page.click("#save")
    page.wait_for_function("document.querySelector('#say').textContent.includes('changes are saved')")
    s = test_state(page)
    r = list(s["ratings"].values())
    check(len(r) == 1 and r[0]["who_right"] == "engine" and r[0]["corrected"] == "what I heard"
          and r[0]["created"] == first["created"] and r[0]["updated"] >= first["updated"],
          "rate: changing the answer updates the same rating")
    check(s["counts"].get(case_id) == 1, "rate: and the count stays at 1")
    check(case_id in page.inner_text("#mine"), "rate: the clip is listed under Your ratings")
    # Save and next moves on; coming back fills the form in.
    page.click("#save-next")
    page.wait_for_function(f"current && current.id !== '{case_id}'")
    check(True, "rate: Save and go to the next clip moves on")
    page.click(f"#mine a[href*='{case_id}']")
    page.wait_for_function(f"current && current.id === '{case_id}'")
    check(page.is_checked("#who input[value=engine]") and page.input_value("#corrected") == "what I heard",
          "rate: going back to a rated clip shows the saved answer")
    # The queues.
    for mode in ("random", "fewest", "serious"):
        page.click(f"#modes button[data-mode={mode}]")
        page.wait_for_timeout(100)
        check(page.evaluate("!!current") and page.evaluate("!mine.has(current.id)"), f"rate: the {mode} queue offers a clip not yet rated")
    page.select_option("#corpus", "coraal")
    page.wait_for_timeout(100)
    check(page.evaluate("current.c") == "coraal", "rate: choosing a data set limits the queue to it")
    check("bleeps" in page.inner_text("#correct-hint"), "rate: on CORAAL, it asks not to fill in bleeped names")
    links_on(page, PUBLIC, "rate")
    return case_id


def check_signed_out_rate(page, url: str) -> None:
    page.click("[data-test=wipe]") if page.is_visible("[data-test=wipe]") else None
    page.goto(f"{url}/rate.html#case=nope")
    page.wait_for_selector("#case .notice")
    check("isn't in the rating queue" in page.inner_text("#case"), "rate: an unknown case says so")


def check_admin(page, url: str, out: Path) -> None:
    page.goto(f"{url}/admin.html")
    page.wait_for_selector("#not-admin", state="visible")
    check("isn't one" in page.inner_text("#not-admin"), "admin: a non-admin is turned away")
    page.check("[data-test=admin]")
    page.wait_for_selector("#admin", state="visible")
    page.wait_for_function("document.querySelector('#summary').textContent.includes('rating')")
    with page.expect_download() as got:
        page.click("#dl-all")
    path = out / "ratings-test.csv"
    got.value.save_as(path)
    text = path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    check(rows[0] == COLUMNS, f"admin: the CSV has the expected columns ({rows[0]})")
    check(len(rows) == 2, f"admin: one row per rating ({len(rows) - 1})")
    check("@" not in text, "admin: no email address anywhere in the CSV")
    check(rows[1][1].startswith("test") and rows[1][4] in ("CC BY 4.0", "CC BY-SA 4.0", "CC BY-NC-SA 4.0"),
          "admin: each row has the uid and the licence of its recording")
    check(rows[1][11].startswith("'="), "admin: a cell that looks like a formula is defused")
    import read_ratings
    t = read_ratings.load(path)
    check(len(t) == 1 and t.feedback.iloc[0].startswith("=1+1") and bool(t.f_soundalike.iloc[0]),
          "admin: tools/read_ratings.py reads the CSV back")
    page.uncheck("[data-test=admin]")


def check_delete(page, url: str) -> None:
    page.goto(f"{url}/account.html")
    page.wait_for_selector("#delete-form", state="visible")
    page.fill("#del-password", "a-long-password")
    page.check("#del-sure")
    page.click("#delete-form button[type=submit]")
    page.wait_for_selector("#signup-form", state="visible")
    s = test_state(page)
    check(not s["ratings"] and not s["users"] and not s["profiles"] and not any(s["counts"].values()),
          "account: deleting removes the account, profile and every rating")


def check_pages(page, url: str) -> None:
    page.goto(f"{url}/scotus.html")
    page.wait_for_selector(".failure-card")
    rate = page.locator(".failure-card a.rate-link")
    check(rate.count() > 0, f"scotus: cards have a Rate this link ({rate.count()} shown)")
    href = rate.first.get_attribute("href")
    check(bool(re.fullmatch(r"rate\.html#case=[a-z]\d+&from=card", href or "")), f"scotus: the link names a case ({href})")
    check("Credits and licences" in page.inner_text("footer"), "scotus: the footer has the licence line")
    links_on(page, PUBLIC, "scotus")
    page.click(".failure-card a.rate-link >> nth=0")
    page.wait_for_selector("#case .failure-card")
    check(page.evaluate("cameFrom") == "card", "rate: a card's link opens that case, marked as from a card")
    for name in ("index.html", "edacc.html", "coraal.html", "earnings22.html", "compare.html", "ai.html",
                 "privacy.html", "terms.html", "licences.html", "404.html"):
        page.goto(f"{url}/{name}")
        page.wait_for_load_state("networkidle")
        check(page.locator("footer .licence-line").count() == 1, f"{name}: the licence line is in the footer")
        links_on(page, PUBLIC, name)
    page.goto(f"{url}/earnings22.html")
    check(page.locator(".failure-card a.rate-link").count() == 0, "earnings22: no Rate links (no audio)")
    page.goto(f"{url}/data.html")
    page.wait_for_selector("#viewer-errors table", timeout=60000)
    page.wait_for_timeout(500)
    n = page.locator("#viewer-errors a.rate-link").count()
    check(n > 0, f"data: rows in the rating queue have a Rate this link ({n} on this page of rows)")
    links_on(page, PUBLIC, "data")
    for c in ("scotus", "edacc", "coraal", "earnings22"):
        page.goto(f"{url}/recordings/{c}/")
        page.wait_for_selector("#view a, #view button", timeout=20000)
        nav = page.inner_text("#nav")
        check("Rate clips" in nav, f"recordings/{c}: the bar links to the rating page")
        links_on(page, PUBLIC, f"recordings/{c}")
    # A card's moment in the whole recording.
    page.goto(f"{url}/scotus.html")
    page.wait_for_selector(".failure-card")
    whole = page.locator(".failure-card a", has_text="Open it in the whole recording").first
    if whole.count():
        href = whole.get_attribute("href")
        page.goto(urljoin(f"{url}/scotus.html", href))
        page.wait_for_timeout(1500)
        check("recordings/scotus/#r-scotus-" in page.url, f"scotus: a card opens its moment in the whole recording ({href})")


# ---------------------------------------------------------------------------
# The worker in front of the audio, every page's basics, and Firebase mode
# ---------------------------------------------------------------------------

def start_worker(page, url: str) -> bool:
    """Put public/_worker.js in front of the audio, as Pages does, and say whether it took."""
    page.goto(f"{url}/")
    page.evaluate("""async () => {
        await navigator.serviceWorker.register('/__check_sw.js', { type: 'module', scope: '/' });
        await navigator.serviceWorker.ready; }""")
    page.reload()
    page.wait_for_function("!!navigator.serviceWorker.controller", timeout=10000)
    on = page.evaluate("!!navigator.serviceWorker.controller")
    check(on, "the audio worker (public/_worker.js) runs in front of the audio, as on Pages")
    return on


RANGES = """async clip => {
  const get = async range => {
    const r = await fetch(clip, { headers: range ? { Range: range } : {}, cache: 'no-store' });
    return { status: r.status, bytes: Array.from(new Uint8Array(await r.arrayBuffer())), range: r.headers.get('Content-Range'),
             accept: r.headers.get('Accept-Ranges'), type: r.headers.get('Content-Type'), keep: r.headers.get('Cache-Control') };
  };
  const whole = await get(null);
  const n = whole.bytes.length;
  const out = { n, whole: { ...whole, bytes: null }, parts: {} };
  for (const r of ['bytes=100-199', `bytes=${n - 50}-`, 'bytes=-30', `bytes=${n}-`, 'bytes=0-1,5-6', `bytes=7-${n + 99}`]) {
    const g = await get(r);
    out.parts[r] = { ...g, bytes: null, len: g.bytes.length, same: g.bytes.join() === (g.status === 206 ? whole.bytes.slice(
      Number(/bytes (\\d+)-/.exec(g.range || 'bytes 0-')[1]), Number(/-(\\d+)\\//.exec(g.range || '-0/')[1]) + 1) : g.status === 200 ? whole.bytes : []).join() };
  }
  const plainRange = await fetch('/js/site.js', { headers: { Range: 'bytes=0-9' }, cache: 'no-store' });
  out.static = plainRange.status;
  return out;
}"""


def check_worker(page, url: str, clip: str) -> None:
    """Ask the worker for parts of a clip, as a browser jumping inside it does."""
    page.goto(f"{url}/")
    got = page.evaluate(RANGES, "/" + clip)
    n, p = got["n"], got["parts"]
    check(got["static"] == 200, "the local server answers a range on a plain file with the whole file, as Pages does")
    check(got["whole"]["status"] == 200 and got["whole"]["accept"] == "bytes" and (got["whole"]["type"] or "").startswith("audio/"),
          f"worker: the whole clip, with Accept-Ranges and an audio type ({got['whole']['type']})")
    check("max-age=86400" in (got["whole"]["keep"] or ""), "worker: audio is kept a day")
    a = p["bytes=100-199"]
    check(a["status"] == 206 and a["len"] == 100 and a["same"] and a["range"] == f"bytes 100-199/{n}", f"worker: bytes=100-199 gives those 100 bytes (206, {a['range']})")
    b = p[f"bytes={n - 50}-"]
    check(b["status"] == 206 and b["len"] == 50 and b["same"], "worker: bytes=N- gives the rest of the file")
    c = p["bytes=-30"]
    check(c["status"] == 206 and c["len"] == 30 and c["same"], "worker: bytes=-30 gives the last 30 bytes")
    d = p[f"bytes={n}-"]
    check(d["status"] == 416 and d["range"] == f"bytes */{n}", "worker: a range past the end gets 416")
    e = p["bytes=0-1,5-6"]
    check(e["status"] == 200 and e["len"] == n, "worker: several ranges at once get the whole file")
    f = p[f"bytes=7-{n + 99}"]
    check(f["status"] == 206 and f["len"] == n - 7 and f["same"], "worker: a range running past the end is cut at the end")


def check_seeking(page, url: str, queue: dict) -> None:
    """Through the worker, a clip starts where its view starts, not at 0: a rating
    case far into a whole recording, and a card."""
    far = next((c for c in queue["cases"] if c["clip"].startswith("recordings/") and c["views"][0]["from"] > 120), None)
    if far is None:
        check(False, "rate: no case far into a whole recording, to check jumping")
    else:
        page.goto(f"{url}/rate.html#case={far['id']}")
        page.wait_for_selector("#case .failure-card")
        v = far["views"][0]
        check_page.play_and_watch(page, page.locator(f'#case [data-play="{v["key"]}"]').first,
                                  f"rate, {v['from']:.0f} s into {far['clip'].rsplit('/', 1)[-1]}, through the worker", (v["from"], v["to"]))
        page.evaluate("Listen.stop()")
    page.goto(f"{url}/scotus.html")
    page.wait_for_selector(".failure-card")
    views = page.evaluate("D.failures.flatMap(k => k.cards.slice(0, 4))")
    n = next((i for i, c in enumerate(views) if c.get("clip") and max(v["from"] for v in c["views"]) > 2), None)
    check(n is not None, "scotus: a card whose clip starts after 2 s, to check jumping")
    if n is not None:
        card = page.locator("#kinds .failure-card").nth(n)
        card.scroll_into_view_if_needed()
        v = max(views[n]["views"], key=lambda v: v["from"])
        check_page.play_and_watch(page, card.locator(f'[data-play="{v["key"]}"]'), f"scotus card {n + 1}, {v['key']}, through the worker", (v["from"], v["to"]))
        page.evaluate("Listen.stop()")


ALL_PAGES = ["index.html", "scotus.html", "edacc.html", "coraal.html", "earnings22.html", "compare.html", "data.html",
             "ai.html", "rate.html", "account.html", "admin.html", "privacy.html", "terms.html", "licences.html",
             "recordings/scotus/", "recordings/edacc/", "recordings/coraal/", "recordings/earnings22/"]

BASICS = """() => {
  const text = n => (n.getAttribute('aria-label') || n.getAttribute('title') || n.textContent || '').trim()
    || [...n.querySelectorAll('img[alt], [aria-label]')].map(i => i.getAttribute('alt') || i.getAttribute('aria-label')).join('').trim();
  const shown = n => !!(n.offsetWidth || n.offsetHeight || n.getClientRects().length);
  const labelled = n => (n.labels && n.labels.length) || n.getAttribute('aria-label') || n.getAttribute('aria-labelledby') || n.getAttribute('title');
  const fields = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')];
  return {
    lang: document.documentElement.lang, title: document.title,
    description: (document.querySelector('meta[name=description]') || {}).content || '',
    h1: document.querySelectorAll('h1').length,
    unlabelled: fields.filter(n => !labelled(n)).map(n => n.id || n.outerHTML.slice(0, 60)),
    noAlt: [...document.querySelectorAll('img')].filter(n => !n.hasAttribute('alt')).map(n => n.src.slice(-40)),
    buttons: [...document.querySelectorAll('button')].filter(n => shown(n) && !text(n)).map(n => n.outerHTML.slice(0, 80)),
    links: [...document.querySelectorAll('a[href]')].filter(n => shown(n) && !text(n)).map(n => n.outerHTML.slice(0, 80)),
    footer: [...document.querySelectorAll('footer a')].map(a => a.getAttribute('href').replace(/^(\\.\\.\\/)+/, '')),
  };
}"""

# Text and its background, for every element with its own words on screen (WCAG AA:
# 4.5 to 1, or 3 to 1 for large text). Backgrounds are found by walking up to the
# first element with a solid colour; text over pictures isn't checked.
CONTRAST = """() => {
  const rgb = s => { const m = s.match(/[\\d.]+/g); return m ? m.map(Number) : null; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
                     return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const bg = n => { for (; n; n = n.parentElement) { const c = rgb(getComputedStyle(n).backgroundColor); if (c && (c.length < 4 || c[3] > 0.9)) return c; } return [255, 255, 255]; };
  const low = [];
  for (const n of document.querySelectorAll('body *')) {
    if (![...n.childNodes].some(t => t.nodeType === 3 && t.textContent.trim())) continue;
    const s = getComputedStyle(n);
    if (s.visibility === 'hidden' || !(n.offsetWidth || n.offsetHeight) || Number(s.opacity) === 0) continue;
    if (n.closest('svg, #test-banner, [aria-hidden=true]') || n.disabled || n.closest(':disabled')) continue;
    const fg = rgb(s.color), b = bg(n);
    if (!fg) continue;
    const a = fg.length > 3 ? fg[3] : 1;
    const mix = [0, 1, 2].map(i => fg[i] * a + b[i] * (1 - a));
    const [l1, l2] = [lum(mix), lum(b)].sort((x, y) => y - x);
    const ratio = (l1 + 0.05) / (l2 + 0.05);
    const size = parseFloat(s.fontSize), bold = Number(s.fontWeight) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    if (ratio < need - 0.05) low.push(`${n.tagName.toLowerCase()}${n.className && typeof n.className === 'string' ? '.' + n.className.split(' ')[0] : ''} ${ratio.toFixed(2)}: ${n.textContent.trim().slice(0, 30)}`);
  }
  return [...new Set(low)];
}"""


def check_basics(page, url: str) -> None:
    """Titles, descriptions, headings, labels, alt text, names, the footer's links and contrast, page by page."""
    titles = {}
    for name in ALL_PAGES:
        page.goto(f"{url}/{name}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(300)
        b = page.evaluate(BASICS)
        titles[name] = b["title"]
        check(b["lang"] == "en" and b["title"] and len(b["description"]) > 20, f"{name}: has a language, a title and a description")
        check(b["h1"] == 1, f"{name}: one main heading ({b['h1']})")
        check(not b["unlabelled"], f"{name}: every form field has a label" + (f": {b['unlabelled'][:4]}" if b["unlabelled"] else ""))
        check(not b["noAlt"], f"{name}: every image has alt text" + (f": {b['noAlt'][:3]}" if b["noAlt"] else ""))
        check(not b["buttons"] and not b["links"], f"{name}: every button and link has a name"
              + (f": {(b['buttons'] + b['links'])[:3]}" if b["buttons"] or b["links"] else ""))
        need = {"licences.html", "privacy.html", "terms.html", "privacy.html#contact-us"}
        check(need <= set(b["footer"]), f"{name}: the footer links the credits, privacy, contributor terms and contact"
              + (f" (missing {sorted(need - set(b['footer']))})" if not need <= set(b["footer"]) else ""))
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            page.wait_for_timeout(100)
            low = page.evaluate(CONTRAST)
            check(not low, f"{name}: text contrast, {scheme} ({len(low)} too faint)" + (f": {low[:4]}" if low else ""))
        page.emulate_media(color_scheme="light")
    same = {t for t in titles.values() if list(titles.values()).count(t) > 1}
    check(not same, "every page has a title of its own" + (f": {sorted(same)}" if same else ""))
    page.goto(f"{url}/account.html")
    page.wait_for_selector("#signup-form", state="attached")
    check(page.locator("#signup-form a[href='privacy.html']").count() == 1, "account: the sign-up form links the privacy notice")
    # Keyboard: Tab reaches the rating page's play button and Save.
    page.goto(f"{url}/rate.html")
    page.wait_for_selector("#case .failure-card")
    reached = set()
    for _ in range(80):
        page.keyboard.press("Tab")
        reached.add(page.evaluate("(document.activeElement.id || '') + '|' + (document.activeElement.dataset.play || '')"))
    check(any(r.endswith("|short") for r in reached) and "save|" in reached, "rate: the keyboard alone reaches a play button and Save")
    # The 404 page, at any depth.
    for missing in ("no-such-page", "recordings/scotus/deep/no-such-page"):
        r = page.goto(f"{url}/{missing}")
        page.wait_for_load_state("networkidle")
        ok = r.status == 404 and "That page isn't here" in page.inner_text("h1") and page.locator("footer .licence-line").count() == 1
        check(ok, f"/{missing}: the 404 page, with status 404, its bar and footer ({r.status})")
        links_on(page, PUBLIC, f"404 at /{missing}")


IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/18.0 Mobile/15E148 Safari/604.1")


def stand_in_config() -> tuple[str, str]:
    """A Firebase config that points nowhere real, and its authDomain. A real
    authDomain from hosting/firebase-config.js is kept (calls to it are answered
    locally), so the policy is tested against the address it will meet."""
    real = re.search(r'authDomain:\s*"([^"]+)"', (CAPSTONE / "hosting" / "firebase-config.js").read_text(encoding="utf-8"))
    domain = real.group(1) if real else "csp-check.firebaseapp.com"
    cfg = {"apiKey": "check-public-stand-in", "authDomain": domain, "projectId": "csp-check",
           "storageBucket": "", "messagingSenderId": "0", "appId": "1:0:web:0"}
    return f"window.SITE_CONFIG = {{ firebase: {json.dumps(cfg)}, contactEmail: '', askBackground: false }};", domain


def check_firebase_mode(browser, url: str, phone: bool) -> None:
    """The pages in Firebase mode, against a stand-in: the policy lets the SDK reach
    Google's sign-in and database, and on a phone the sign-in frame too."""
    label = "firebase mode" + (" (iPhone)" if phone else "")
    opts = {"service_workers": "block"}
    if phone:
        opts |= {"user_agent": IPHONE, "viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
    ctx = browser.new_context(**opts)
    config, domain = stand_in_config()
    seen, refused = [], []
    cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}

    def google(route):
        u = route.request.url
        seen.append(u)
        if "accounts:signInWithPassword" in u:
            body = {"error": {"code": 400, "message": "INVALID_LOGIN_CREDENTIALS",
                              "errors": [{"message": "INVALID_LOGIN_CREDENTIALS", "domain": "global", "reason": "invalid"}]}}
            return route.fulfill(status=400, headers=cors, content_type="application/json", body=json.dumps(body))
        if "getProjectConfig" in u or "/projects" in u:
            return route.fulfill(status=200, headers=cors, content_type="application/json",
                                 body=json.dumps({"projectId": "csp-check", "authorizedDomains": ["localhost", "127.0.0.1"]}))
        return route.fulfill(status=403, headers=cors, content_type="application/json",
                             body=json.dumps({"error": {"code": 403, "message": "stand-in", "status": "PERMISSION_DENIED"}}))

    ctx.route(re.compile(r"^http://127\.0\.0\.1:\d+/(.*/)?config\.js$"), lambda r: r.fulfill(content_type="text/javascript", body=config))
    ctx.route(re.compile(r"^https://[a-z]+\.googleapis\.com/"), google)
    ctx.route(f"https://{domain}/**", lambda r: (seen.append(r.request.url),
                                                r.fulfill(content_type="text/html", body="<!doctype html><title>stand-in</title>")))
    page = ctx.new_page()
    page.on("console", lambda m: refused.append(f"{page.url}: {m.text[:160]}") if "Content Security Policy" in m.text else None)
    page.goto(f"{url}/account.html")
    page.wait_for_selector("#signin-form", state="visible", timeout=30000)
    check(page.evaluate("Backend.mode") == "firebase", f"{label}: the pages talk to (stand-in) Firebase")
    page.fill("#in-email", "nobody@example.com")
    page.fill("#in-password", "not-a-real-password")
    page.click("#signin-form button[type=submit]")
    try:
        page.wait_for_function("document.querySelector('#in-say').textContent.includes(\"don't match\")", timeout=20000)
        said = True
    except Exception:
        said = False
    check(said, f"{label}: a sign-in reaches Google's sign-in address and its answer is shown ({page.inner_text('#in-say')[:80]})")
    check(any("identitytoolkit.googleapis.com" in u for u in seen), f"{label}: the policy lets sign-in out")
    for name in ("rate.html", "scotus.html", "data.html", "recordings/coraal/"):
        page.goto(f"{url}/{name}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
    page.goto(f"{url}/rate.html")
    page.wait_for_timeout(4000)
    check(any("firestore.googleapis.com" in u for u in seen), f"{label}: the policy lets the database calls out")
    if phone:
        check(any(u.startswith(f"https://{domain}/__/auth/iframe") for u in seen),
              f"{label}: sign-in's hidden frame from {domain} may open")
    check(not refused, f"{label}: nothing refused by the Content-Security-Policy" + (f": {refused[:3]}" if refused else ""))
    ctx.close()


# ---------------------------------------------------------------------------
# After uploading: the real site, from outside
# ---------------------------------------------------------------------------

def check_live(base: str) -> int:
    """The deployed site's headers, 404, ranges and types, with Python alone."""
    import http.client
    base = base.rstrip("/")
    site = urlparse(base)

    def get(path: str, headers: dict | None = None) -> tuple[int, dict, bytes]:
        conn = (http.client.HTTPSConnection if site.scheme == "https" else http.client.HTTPConnection)(site.netloc, timeout=60)
        conn.request("GET", path, headers={"User-Agent": "check_public.py", **(headers or {})})
        r = conn.getresponse()
        body = r.read()
        conn.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body

    want = headers_for(read_headers(PUBLIC / "_headers"), "/")
    status, h, body = get("/")
    check(status == 200 and b"Where Speech Recognition Goes Wrong" in body, f"live /: the home page ({status})")
    for name in ("content-security-policy", "strict-transport-security", "x-content-type-options", "referrer-policy",
                 "permissions-policy", "x-frame-options"):
        check(h.get(name) == want.get(name), f"live /: {name} as in _headers" + ("" if h.get(name) == want.get(name) else f" (got {h.get(name)!r:.120})"))
    status, h, _ = get("/scotus.html")
    check(status in (301, 308) and h.get("location", "").endswith("/scotus"), f"live: /scotus.html redirects to /scotus ({status})")
    status, h, body = get("/scotus")
    check(status == 200 and "content-security-policy" in h, f"live /scotus: served, with the policy ({status})")
    status, _, body = get("/no-such-page-check-public")
    check(status == 404 and b"That page isn" in body, f"live: a missing page gets the 404 page with status 404 ({status})")
    for hidden in ("/_headers", "/_routes.json", "/_worker.js"):
        status, _, body = get(hidden)
        check(status == 404 or b"That page isn" in body, f"live: {hidden} is not served ({status})")
    status, h, _ = get("/favicon.ico")
    check(status in (301, 302, 308) and h.get("location", "").endswith("/favicon.svg"), f"live: /favicon.ico goes to the icon ({status})")
    queue = json.loads((PUBLIC / "rate" / "cases.json").read_text(encoding="utf-8"))
    mp3 = next(c["clip"] for c in queue["cases"] if c["clip"].startswith("clips/") and c["clip"].endswith(".mp3"))
    whole = next(c["clip"] for c in queue["cases"] if c["clip"].startswith("recordings/"))
    for path in (mp3, whole):
        size = (PUBLIC / path).stat().st_size
        status, h, body = get("/" + path, {"Range": f"bytes={size // 2}-{size // 2 + 99}"})
        check(status == 206 and len(body) == 100 and body == (PUBLIC / path).read_bytes()[size // 2:size // 2 + 100]
              and h.get("content-range") == f"bytes {size // 2}-{size // 2 + 99}/{size}",
              f"live /{path}: a range in the middle gives those 100 bytes ({status}, {h.get('content-range')})")
        check(h.get("content-type", "").startswith("audio/") and h.get("accept-ranges") == "bytes",
              f"live /{path}: an audio type and Accept-Ranges ({h.get('content-type')})")
    for path, kind in (("/data/tables-rates.json", "application/json"), ("/data/errors.csv", "text/csv"),
                       ("/recordings/scotus/rec/001.txt", "text/plain"), ("/js/site.js", "javascript"),
                       ("/css/site.css", "text/css"), ("/favicon.svg", "image/svg+xml"), ("/robots.txt", "text/plain")):
        status, h, _ = get(path)
        check(status == 200 and kind in h.get("content-type", ""), f"live {path}: {h.get('content-type')}")
    status, _, body = get("/config.js")
    check(status == 200 and re.search(rb'apiKey:\s*"[^"]+"', body), "live /config.js: the Firebase config is filled in")
    print(f"\n{len(check_page.failures)} failed")
    return 1 if check_page.failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", action="store_true", help="open a visible window")
    parser.add_argument("--serve", type=int, metavar="PORT", help="just serve public/ on this port (with byte ranges, so clips can seek) until Ctrl+C")
    parser.add_argument("--live", metavar="URL", help="check the uploaded site from outside (headers, 404, ranges, types)")
    args = parser.parse_args()
    if args.live:
        return check_live(args.live)
    if args.serve:
        serve_like_pages(PUBLIC, args.serve, ranges=True)
        print(f"http://localhost:{args.serve}/  (served as Cloudflare Pages serves it, but with ranges; Ctrl+C to stop)")
        threading.Event().wait()
    check_files(PUBLIC)
    check_hosting(PUBLIC)
    server, port = serve_like_pages(PUBLIC)
    url = f"http://127.0.0.1:{port}"
    out = CAPSTONE / "site" / "checks"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=not args.show,
                                    args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page = context.new_page()
        errors, judge_requests, refused = [], [], []
        page.on("pageerror", lambda e: errors.append(f"{page.url}: {e}"))
        page.on("request", lambda r: judge_requests.append(r.url) if r.url.endswith("rate/judge.json") else None)
        page.on("console", lambda m: refused.append(f"{page.url}: {m.text[:160]}") if "Content Security Policy" in m.text else None)
        queue = json.loads((PUBLIC / "rate" / "cases.json").read_text(encoding="utf-8"))
        clip = next(c["clip"] for c in queue["cases"] if c["clip"].startswith("clips/"))
        page.goto(f"{url}/account.html")
        page.evaluate("localStorage.clear(); sessionStorage.clear()")
        for name, step in [("worker", lambda: start_worker(page, url) and check_worker(page, url, clip)),
                           ("seeking", lambda: check_seeking(page, url, queue)),
                           ("account", lambda: check_account(page, url)),
                           ("rate", lambda: check_rate(page, url, judge_requests)),
                           ("admin", lambda: check_admin(page, url, out)),
                           ("delete", lambda: check_delete(page, url)),
                           ("signed-out rate", lambda: check_signed_out_rate(page, url)),
                           ("pages", lambda: check_pages(page, url)),
                           ("basics", lambda: check_basics(page, url))]:
            try:
                step()
            except Exception as e:   # one stuck step shouldn't hide the rest
                check(False, f"{name}: stopped with {type(e).__name__}: {str(e).splitlines()[0][:200]}")
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{url}/rate.html")
        page.wait_for_selector("#case .failure-card")
        check_page.no_sideways_scroll(page, "rate (phone)")
        page.screenshot(path=str(out / "public-rate-phone.png"), full_page=False)
        page.goto(f"{url}/account.html")
        check_page.no_sideways_scroll(page, "account (phone)")
        check(not errors, "no script errors" + (f": {errors[:3]}" if errors else ""))
        check(not refused, "test mode: nothing on any page refused by the Content-Security-Policy" + (f": {refused[:3]}" if refused else ""))
        context.close()
        for phone in (False, True):
            try:
                check_firebase_mode(browser, url, phone)
            except Exception as e:
                check(False, f"firebase mode{' (iPhone)' if phone else ''}: stopped with {type(e).__name__}: {str(e).splitlines()[0][:200]}")
        browser.close()
    server.shutdown()
    print(f"\n{len(check_page.failures)} failed")
    return 1 if check_page.failures else 0


if __name__ == "__main__":
    sys.exit(main())

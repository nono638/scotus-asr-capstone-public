"""Check a built page in a real browser before it is published.

Opens the page in the Edge already installed on the laptop (through Playwright,
which downloads no browser of its own) and does what a visitor would: plays
clips at each length and checks that the audio moves and that the highlighted
word is the one being spoken; on the website, also switches each chart's rule
and filters and clicks a dot to hear it. Screenshots go beside the page in
`checks/`, at desktop and phone width, light and dark.

    python tools/check_page.py --bench <folder with listening.html>
    python tools/check_page.py --site  <folder with index.html and the data-set pages>

Prints one line per check and exits 1 if any failed. The page is served from a
local port, so the clips load the way they do once published.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

PLAY_SECONDS = 1.6
failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        failures.append(what)


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Serves part of a file when asked, as any real host does.

    Python's own server always sends the whole file, and a browser that cannot
    ask for part of an MP3 cannot jump inside it: every clip would play from
    0 seconds, whatever the button said.
    """

    def log_message(self, *args):
        pass

    def send_head(self):
        path = Path(self.translate_path(self.path))
        wanted = self.headers.get("Range", "")
        if not path.is_file() or not wanted.startswith("bytes="):
            return super().send_head()
        size = path.stat().st_size
        first, _, last = wanted[6:].partition("-")
        first = int(first) if first else 0
        last = min(int(last), size - 1) if last else size - 1
        f = path.open("rb")
        f.seek(first)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
        self.send_header("Content-Length", str(last - first + 1))
        self.end_headers()
        self._left = last - first + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        while left > 0:
            chunk = source.read(min(65536, left))
            if not chunk:
                break
            outputfile.write(chunk)
            left -= len(chunk)


def serve(folder: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(RangeHandler, directory=str(folder))
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


# Read the audio's time and the lit words in one go, so they describe the same moment.
MOMENT = """() => {
  const a = Listen.audio, p = Listen.active;
  const t = a.currentTime;
  const lit = p ? [...p.root.querySelectorAll('.word.now')].map(n => [Number(n.dataset.s), Number(n.dataset.e), n.textContent]) : [];
  const timed = p ? p.root.querySelectorAll('.word').length : 0;
  return {t, paused: a.paused, src: a.src, lit, timed, error: a.error && a.error.code};
}"""


def play_and_watch(page, button, label: str, view: tuple[float, float] | None = None) -> None:
    """Click a play button, let it play, and check the audio and the highlight.

    `view` is the stretch of the clip the button should play, when known.
    """
    button.click()
    # Measure from when sound starts, not from the click: the first clip of a
    # page has to load, and the browser takes about a second to open its sound
    # output the first time (traced 19 Oct: the time sits still, then runs at
    # exactly real speed).
    page.wait_for_timeout(100)
    start = page.evaluate("Listen.audio.currentTime")
    try:
        page.wait_for_function("t => Listen.audio.currentTime > t + 0.05", arg=start, timeout=8000)
    except Exception:
        pass
    before = page.evaluate(MOMENT)
    page.wait_for_timeout(PLAY_SECONDS * 1000)
    after = page.evaluate(MOMENT)
    check(after["error"] is None, f"{label}: clip loads ({after['src'].rsplit('/', 1)[-1]})")
    if view:
        check(view[0] - 0.05 <= start <= view[1], f"{label}: starts inside its view ({start:.2f} s, view {view[0]:.2f}-{view[1]:.2f})")
    moved = after["t"] - before["t"]
    check(moved > 0.8 or (after["paused"] and after["t"] > 0), f"{label}: audio plays ({moved:.2f} s in {PLAY_SECONDS} s)")
    if after["timed"]:
        # A word stays lit 0.12 s past its end (listen.js), and the highlight is
        # redrawn once a frame, which a headless browser can run a tenth of a
        # second behind the time read here; hence 0.3 s of slack after the end.
        wrong = [w for w in after["lit"] if not (w[0] - 0.05 <= after["t"] <= w[1] + 0.3)]
        check(not wrong, f"{label}: {len(after['lit'])} lit word(s) at {after['t']:.2f} s match the audio"
                         + (f" - off: {wrong}" if wrong else ""))


def shots(page, out: Path, name: str) -> None:
    out.mkdir(exist_ok=True)
    for width, tag in ((1280, "desktop"), (390, "phone")):
        for scheme in ("light", "dark"):
            page.set_viewport_size({"width": width, "height": 900})
            page.emulate_media(color_scheme=scheme)
            page.wait_for_timeout(250)
            page.screenshot(path=str(out / f"{name}-{tag}-{scheme}.png"), full_page=(tag == "desktop" and scheme == "light"))
    page.set_viewport_size({"width": 1280, "height": 900})
    page.emulate_media(color_scheme="light")


def check_bench(page, url: str, out: Path) -> None:
    page.goto(url + "/listening.html")
    page.wait_for_selector(".spot")
    for spot in range(2):
        for key in ("bite", "sentence", "three"):
            view = page.evaluate(f"SPOTS[index].views['{key}']")
            play_and_watch(page, page.locator(f'[data-play="{key}"]'), f"bench spot {spot + 1}, {key}", tuple(view))
        page.evaluate("Listen.stop()")
        page.locator("#next").click()
    page.locator("#prev").click()
    page.locator("#prev").click()
    shots(page, out, "bench")


def play_cards(page, label: str, cards, views_js: str, how_many: int = 2) -> None:
    """Play the first few failure cards at each of their lengths."""
    for n in range(min(how_many, cards.count())):
        card = cards.nth(n)
        card.scroll_into_view_if_needed()
        views = page.evaluate(f"({views_js})[{n}].views")
        for v in views:
            play_and_watch(page, card.locator(f'[data-play="{v['key']}"]'), f"{label} card {n + 1}, {v['key']}",
                           (v["from"], v["to"]))
        page.evaluate("Listen.stop()")


def visible_words(card) -> int:
    return card.evaluate("c => [...c.querySelectorAll('.compare-line .word')].filter(n => !n.classList.contains('outside')).length")


def check_stopping(page, label: str, card) -> None:
    """A length that is playing stops when pressed again, and no word stays lit after a clip."""
    button = card.locator('[data-play="short"]')
    button.click()
    page.wait_for_timeout(300)
    if page.evaluate("Listen.audio.paused"):
        return   # Earnings-22: no audio on this page, so nothing to stop
    page.evaluate("Listen.stop()")
    button.click()
    page.wait_for_function("!Listen.audio.paused && Listen.audio.readyState >= 3", timeout=15000)
    page.wait_for_timeout(1500)
    check(card.locator(".word.now").count() > 0, f"{label}: words light up as it plays")
    button.click()
    page.wait_for_timeout(300)
    check(page.evaluate("Listen.audio.paused"), f"{label}: pressing the playing length again stops it")
    check(card.locator(".word.now").count() == 0, f"{label}: no word stays lit after stopping")
    button.click()
    page.wait_for_function("!Listen.audio.paused", timeout=15000)
    page.evaluate("Listen.audio.currentTime = Listen.active.stopAt - 0.4")
    page.wait_for_timeout(1500)
    check(page.evaluate("Listen.audio.paused"), f"{label}: the clip stops at its end")
    check(card.locator(".word.now").count() == 0, f"{label}: no word stays lit after the clip ends")


def check_lengths(page, label: str, card) -> None:
    """The longer button shows more of the text than the shorter one."""
    card.locator('[data-play="short"]').click()
    short = visible_words(card)
    card.locator('[data-play="long"]').click()
    long = visible_words(card)
    page.evaluate("Listen.stop()")
    check(long > short > 0, f"{label}: the longer view shows more words ({short} -> {long})")
    labels = card.locator("[data-play]").all_inner_texts()
    check(all("moment" not in t.lower() for t in labels), f"{label}: buttons say how long they are ({labels})")


def no_sideways_scroll(page, label: str) -> None:
    page.set_viewport_size({"width": 390, "height": 900})
    page.wait_for_timeout(200)
    wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check(wide <= 1, f"{label}: no sideways scroll on a phone ({wide}px over)")
    page.set_viewport_size({"width": 1280, "height": 900})


def check_top_button(page, label: str) -> None:
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)
    button = page.locator(".to-top")
    check(button.is_visible(), f"{label}: the back-to-top button shows after scrolling")
    button.click()
    try:
        page.wait_for_function("window.scrollY < 5", timeout=5000)
    except Exception:
        pass
    check(page.evaluate("window.scrollY") < 5, f"{label}: back-to-top goes to the top (at {page.evaluate('window.scrollY')})")


def check_site(page, url: str, out: Path) -> None:
    page.goto(url + "/index.html")
    page.wait_for_selector("#kinds > div")
    pages = page.evaluate("D.pages.length")
    check(page.locator("#nav .links a").count() == 4 + pages,
          f"Front page bar: Home, one link to each of {pages} data sets, Big picture, Search the data and How AI was used")
    check(page.locator("#ai a[href='ai.html']").count() == 1 and len(page.locator("#ai-text").inner_text()) > 200,
          "Front page: the summary of how AI was used, linked to its page")
    check(page.locator("#nav .recordings a").count() == pages,
          f"Front page bar: one link to each of {pages} whole-recording pages")
    check(page.locator(".across a[href='compare.html']").count() == 1 and page.locator(".across a[href='data.html']").count() == 1,
          "Front page: the big picture and the data linked under the data sets")
    check(page.locator("#kinds > div").count() == 5, "Front page: the five kinds of failure")
    opposite = page.locator("#opposite .failure-card")
    check(opposite.count() >= 3, f"Front page: {opposite.count()} reversals, one per data set")
    play_cards(page, "front page", opposite, "D.opposite", 1)
    check(page.locator(".dataset-card a[target=_blank]").count() == 2 * pages,
          "Front page: each data set links to its whole recordings and to its own site")
    no_sideways_scroll(page, "front page")
    shots(page, out, "front")
    for name in page.evaluate("D.pages.map(p => p.file)"):
        page.goto(f"{url}/{name}")
        page.wait_for_selector(".kind-section")
        label = name.replace(".html", "")
        check(page.locator("#home-link").get_attribute("href").startswith("http"), f"{label}: a link to the data set's home")
        check(page.locator("#truth-links a").count() >= 2 and len(page.locator("#truth-by").inner_text()) > 40,
              f"{label}: the box saying who wrote the reference, with links")
        check(page.locator("#rates .bar-row").count() >= 3, f"{label}: the error-rate bars")
        check(page.locator("#classes tbody tr").count() >= 3, f"{label}: the kinds-per-hour table")
        check(page.locator(".kind-section").count() == 5, f"{label}: five failure sections")
        cards = page.locator("#kinds .failure-card")
        total = page.evaluate("D.failures.reduce((n, k) => n + k.cards.length, 0)")
        check(cards.count() == sum(min(4, n) for n in page.evaluate("D.failures.map(k => k.cards.length)")),
              f"{label}: {cards.count()} cards shown of {total}")
        if page.evaluate("D.failures.some(k => k.cards.some(c => c.clip))"):
            play_cards(page, label, cards, "D.failures.flatMap(k => k.cards.slice(0, 4))")
        elif total:
            check(page.evaluate("!document.querySelector('#kinds audio[src], #kinds .listen-controls .label')?.textContent?.includes('Hear')"),
                  f"{label}: cards without audio offer no sound")
        if cards.count():
            check_lengths(page, f"{label} first card", cards.first)
            check_stopping(page, f"{label} first card", cards.first)
        check(page.locator("#scores-table tbody tr").count() >= 3, f"{label}: the error-rate table")
        if page.locator("#odds").count():
            check(page.locator("#odds .bar-fill").count() > 3, f"{label}: the error model's bars")
        check(page.locator("#coverage .term-cell").count() >= 2, f"{label}: how much is done")
        check_top_button(page, label)
        no_sideways_scroll(page, label)
        shots(page, out, label)

    page.goto(url + "/compare.html")
    page.wait_for_selector("#rate-chart .bar-row")
    before = page.locator("#rate-chart").inner_text()
    page.locator("#ds-switch button").nth(1).click()
    check(page.locator("#rate-chart").inner_text() != before, "Compare: the data-set switch changes the bars")
    check(page.locator("#class-table tbody tr").count() == pages, "Compare: one row per data set in the kinds table")
    no_sideways_scroll(page, "compare")
    shots(page, out, "compare")

    # The whole-recording pages link to the site's own pages through the front page.
    for name in ("compare", "data", "coraal", "ai"):
        page.goto(f"{url}/index.html#go-{name}")
        page.wait_for_url(f"**/{name}.html", timeout=10000)
        check(page.url.endswith(f"/{name}.html"), f"Front page: #go-{name} opens {name}.html")

    # How AI was used: its own page, linked from the bar and the foot of every page.
    page.goto(url + "/ai.html")
    page.wait_for_selector("#engines li")
    check(page.locator("#engines li").count() == 7 and "Claude Sonnet" in page.locator("#sonnet").inner_text(),
          "AI page: the seven engines and the judges")
    for name in ["index.html", "compare.html", "data.html", "ai.html"] + page.evaluate("D.pages.map(p => p.file)"):
        page.goto(f"{url}/{name}")
        page.wait_for_selector("#nav a")
        check(page.locator("#nav a[href='ai.html']").count() == 1 and page.locator("footer .ai-note a[href='ai.html']").count() == 1,
              f"{name}: How AI was used, in the bar and at the foot")

    page.goto(url + "/data.html")
    page.wait_for_selector("#viewer-errors table.data", timeout=30000)
    total = page.evaluate("Number(document.querySelector('#viewer-errors .viewer-count').textContent.split(' of ')[1].split(' ')[0].replace(/,/g, ''))")
    check(total > 30000, f"Data: the error table loads ({total} rows)")
    rows_now = lambda: int(page.locator("#viewer-errors .viewer-count").inner_text().split(" of ")[0].replace(",", ""))
    page.locator("#viewer-errors input[type=search]").fill("can't")
    page.wait_for_timeout(600)
    searched = rows_now()
    check(0 < searched < total, f"Data: searching for “can't” narrows it to {searched}")
    page.locator("#viewer-errors input[type=search]").fill("")
    page.locator("#viewer-errors details").first.locator("summary").click()
    page.locator('#viewer-errors select[aria-label="corpus"]').select_option("coraal")
    page.wait_for_timeout(400)
    filtered = rows_now()
    check(0 < filtered < total, f"Data: the corpus filter narrows it to {filtered}")
    check(page.locator("#viewer-errors tbody tr").count() == 50, "Data: 50 rows a page")
    check(page.locator("#viewer-errors .viewer-tools button").count() == 1, "Data: a download button")
    # The row clips: every data set with audio, jumping into a long file and stopping on time.
    only = page.locator("#viewer-errors .viewer-only input")
    check(only.count() == 1, "Data: an 'only rows with a clip' box")
    only.check()
    page.wait_for_timeout(400)
    for corpus in ("coraal", "edacc", "scotus"):
        page.locator('#viewer-errors select[aria-label="corpus"]').select_option(corpus)
        page.wait_for_timeout(400)
        with_clips = rows_now()
        button = page.locator("#viewer-errors tbody .hear button").nth(min(20, with_clips - 1))
        button.click()
        # The first reading once the audio is really moving, against where the row's clip starts.
        got = page.evaluate("""() => new Promise(done => {
            const t0 = performance.now();
            const t = setInterval(() => {
                const moving = !player.paused && player.readyState >= 3 && playing && player.currentTime >= playing.from - 1;
                if (moving || performance.now() - t0 > 20000) {
                    clearInterval(t);
                    done({now: player.currentTime, from: playing && playing.from, stuck: !moving});
                }
            }, 50);
        })""")
        check(not got["stuck"] and abs(got["now"] - got["from"]) < 1.0,
              f"Data: a {corpus} row ({with_clips} with clips) starts at its place: {got['now']:.2f} s, clip starts {got['from']} s")
        # Skip to just before the clip's end and see that it stops by itself.
        page.evaluate("player.currentTime = playing.to - 0.5")
        page.wait_for_timeout(1800)
        check(page.evaluate("player.paused") and button.get_attribute("aria-pressed") == "false",
              f"Data: the {corpus} clip stops at its end")
    # Pressing Stop before the file has loaded: it must not start later, or be unstoppable.
    stuck = page.evaluate("""() => new Promise(done => {
        const b = document.querySelector("#viewer-errors tbody .hear button");
        player.removeAttribute("src");
        player.load();
        b.click();
        const pressed = b.getAttribute("aria-pressed");
        b.click();
        setTimeout(() => done({pressed, paused: player.paused, after: b.getAttribute("aria-pressed")}), 2500);
    })""")
    check(stuck["pressed"] == "true" and stuck["paused"] and stuck["after"] == "false",
          f"Data: Stop before the clip has loaded means it never starts ({stuck})")
    only.uncheck()
    page.locator('#viewer-errors select[aria-label="corpus"]').select_option(label="Any")
    page.wait_for_timeout(400)
    check(rows_now() == total, f"Data: 'Any' clears the filter ({rows_now()} of {total})")
    # "(empty)" lists the rows with nothing in that column, and "Any" still means no filter.
    menu = page.locator('#viewer-errors select[aria-label="not_counted"]')
    menu.select_option(label="(empty)")
    page.wait_for_timeout(400)
    empties = rows_now()
    check(0 < empties < total, f"Data: the (empty) filter lists the rows that are counted ({empties})")
    menu.select_option(label="Any")
    page.wait_for_timeout(400)
    check(rows_now() == total, "Data: 'Any' clears the (empty) filter")
    # A row whose place the search lost: its time is unknown, with nothing to play or open.
    page.locator("#viewer-errors input[type=search]").fill("f23725")
    page.wait_for_timeout(600)
    row = page.locator("#viewer-errors tbody tr").first
    check(rows_now() == 1 and "unknown" in row.inner_text() and row.locator(".hear button").count() == 0
          and row.locator("a").count() == 0, "Data: a row with no real time says unknown, with no Play and no Open")
    page.locator("#viewer-errors input[type=search]").fill("")
    page.wait_for_timeout(600)
    shown_qwen = page.evaluate("document.querySelector('#viewer-errors select[aria-label=\"qwen_meaning\"]') !== null")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_site
    check(shown_qwen == build_site.SHOW_QWEN,
          "Data: Qwen's answers are in the table only once its run is finished (build_site.SHOW_QWEN)")
    # The keyboard stays on the button after the table is drawn again.
    page.locator("#viewer-errors .pager button", has_text="Next 50").click()
    check(page.evaluate("document.activeElement.textContent") == "Next 50", "Data: Next 50 keeps the keyboard")
    page.locator("#viewer-errors th button", has_text="engine").first.click()
    page.wait_for_timeout(300)
    check(page.evaluate("document.activeElement.textContent") == "engine", "Data: a sorted heading keeps the keyboard")
    # Credit for every data set: who made it, and a link to its licence.
    credits = page.locator("#credits").inner_text()
    wanted = ["Sanabria", "Kendall", "Del Rio", "Supreme Court of the United States"]
    check(all(n in credits for n in wanted), "Data: the credits name each data set's makers")
    page.evaluate("document.querySelectorAll('#credits details').forEach(d => d.open = true)")
    credits = page.locator("#credits").inner_text()
    parts = ["ATL (Atlanta", "DCA (Washington", "DCB (Washington", "DTA (Detroit", "LES (Lower", "PRV (Princeville", "ROC (Rochester", "VLD (Valdosta"]
    check(all(p in credits for p in parts), "Data: the credits name all eight CORAAL parts")
    check(page.locator("#credits a[href*='licenses/by-nc-sa/4.0']").count() == 1 and page.locator("#credits a[href*='licenses/by-sa/4.0']").count() == 2,
          "Data: the credits link to the licences")
    page.locator("#tab-recordings").click()
    page.wait_for_selector("#viewer-recordings table.data", timeout=30000)
    check(page.locator("#viewer-recordings tbody tr").count() == 50, "Data: the recordings table loads")
    page.locator("#tab-other").click()
    page.locator("#groups details").first.locator("summary").click()
    page.locator("#groups details").first.locator("li button").first.click()
    page.wait_for_selector("#viewer-other table.data", timeout=30000)
    check(page.locator("#viewer-other tbody tr").count() > 0, "Data: one of the other tables opens")
    no_sideways_scroll(page, "data")
    shots(page, out, "data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--bench", type=Path)
    which.add_argument("--site", type=Path)
    parser.add_argument("--show", action="store_true", help="open a visible window")
    args = parser.parse_args()
    folder = (args.bench or args.site).resolve()
    server, port = serve(folder)
    out = folder / "checks"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=not args.show,
                                    args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        (check_bench if args.bench else check_site)(page, f"http://127.0.0.1:{port}", out)
        check(not errors, "no script errors" + (f": {errors[:3]}" if errors else ""))
        browser.close()
    server.shutdown()
    print(f"\n{len(failures)} failed; screenshots in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

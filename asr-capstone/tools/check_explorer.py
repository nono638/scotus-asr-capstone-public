"""Check a whole-recording page in a real browser before it is published.

Serves asr-capstone/explorer/<data set>/ with tools/explore_local.py's server and
opens it in the Edge installed on the laptop (Playwright, no browser download),
twice:

- as the website (the address carries "?web"): only the audio published with
  the page plays;
- as the local copy: any recording plays from the laptop's own file.

It filters the list, opens recordings, plays them and checks that the lit words
are the ones being spoken, jumps with the strip, a word, the ten-second buttons
and the error buttons and keys, opens a recording at a moment from its address,
and checks the errors are highlighted. Screenshots go to explorer/<data set>/checks/.

    python tools/check_explorer.py scotus
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import explore_local  # noqa: E402

OUT = explore_local.OUT   # set from the command line in main()
failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        failures.append(what)


# The audio's time and the lit words, read in one go so they describe one moment.
MOMENT = """() => {
  const a = document.querySelector('audio');
  const lit = [...document.querySelectorAll('.word.now')].map(n => {
    const l = n.closest('.compare-line').dataset.who; return [l, n.textContent];
  });
  return {t: a ? a.currentTime : null, paused: a ? a.paused : null, error: a && a.error && a.error.code, lit};
}"""


def rec_hash(corpus: str, recording: str, at: int | None = None) -> str:
    """A recording's address, as explorer.js and site.js write it."""
    name = recording.replace("-", "-h").replace("_", "-u")
    return f"r-{corpus}-{'x' if at is None else at}-{name}"


def open_recording(page, base: str, row: dict, label: str) -> None:
    page.goto(f"{base}#{rec_hash(row['c'], row['id'])}")
    page.wait_for_selector(".block", timeout=20000)
    check(page.locator("h1").inner_text().strip() == row["title"].strip(), f"{label}: opens with its title")
    # The blocks are drawn as they come near the screen, so go down to them first.
    page.locator(".transcript").scroll_into_view_if_needed()
    page.wait_for_selector(".block.drawn", timeout=10000)
    n = page.locator(".block").count()
    check(n >= int(row["min"] * 60 // 30), f"{label}: {n} blocks of transcript for {row['min']} minutes")
    lines = page.locator(".block.drawn").first.locator(".compare-line").count()
    check(lines == 1 + len(row["engines"]), f"{label}: the record and {len(row['engines'])} engines in each block")


def play_and_watch(page, label: str) -> None:
    page.locator(".player .btn.big").click()
    try:
        page.wait_for_function("() => document.querySelector('audio').currentTime > 0.3", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    m = page.evaluate(MOMENT)
    check(m["error"] is None and (m["t"] or 0) > 0.3, f"{label}: audio plays ({m['t']} s, error {m['error']})")
    if not m["lit"]:
        # Many recordings open with a few seconds of silence; give it a few more.
        page.wait_for_timeout(3000)
        m = page.evaluate(MOMENT)
    check(len(m["lit"]) >= 1, f"{label}: words light up as it plays ({m['lit'][:4]} at {m['t']:.1f} s)")
    # Jump with the strip to 60% of the way through, then check the lit words there.
    strip = page.locator("canvas.strip")
    strip.scroll_into_view_if_needed()
    box = strip.bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.6, box["y"] + box["height"] / 2)
    page.wait_for_timeout(1500)
    length = page.evaluate("Number(document.querySelector('.player input[type=range]').max)")
    lit = page.evaluate("""() => [...document.querySelectorAll('.word.now')].map(n => {
        const b = n.closest('.block'); return Number(b.dataset.k); })""")
    t = page.evaluate("document.querySelector('audio').currentTime")
    k = int(t // 30)
    check(0.55 * length <= t <= 0.68 * length, f"{label}: clicking 60% along the strip jumps there ({t:.0f} of {length} s)")
    check(lit and all(abs(x - k) <= 1 for x in lit), f"{label}: after a jump the lit words are in the block being played (t {t:.0f} s, blocks {sorted(set(lit))})")
    # Click a word in the current block: playback moves to it.
    word = page.locator(f"#b-{k} .compare-line[data-who='Record'] .word").nth(3)
    if word.count():
        word.click()
        page.wait_for_timeout(600)
        t2 = page.evaluate("document.querySelector('audio').currentTime")
        check(k * 30 - 1 <= t2 <= (k + 1) * 30 + 2, f"{label}: clicking a word plays from it ({t2:.1f} s)")
    page.locator(".player .btn.big").click()


#: A name each data set's credit must show.
CREDIT_NAMES = {"scotus": "Supreme Court of the United States", "edacc": "Sanabria", "coraal": "Kendall", "earnings22": "Del Rio"}


def check_reader_actions(page, label: str, has_audio: bool, corpus: str, row: dict, web: str) -> None:
    """What a reader does that the older checks never did: each was a bug in the 5 Nov audit."""
    box = page.locator(".lines-pick input").first
    who = box.get_attribute("id").removeprefix("show-")
    line = page.locator(f'.block.drawn [data-who="{who}"]').first
    check(line.is_visible(), f"{label}: {who}'s line shows to begin with")
    box.uncheck()
    check(not line.is_visible(), f"{label}: unticking {who} hides its line")
    box.check()
    check(line.is_visible(), f"{label}: ticking {who} brings its line back")

    # The keys still work with the keyboard left on a tick box, and the box keeps Space.
    now = "(document.querySelector('audio')?.currentTime ?? 0)"
    box.focus()
    page.keyboard.press("Space")
    check(not box.is_checked(), f"{label}: Space on a tick box ticks the box")
    page.keyboard.press("Space")
    moved = page.evaluate("window.scrollY") if not has_audio else page.evaluate(now)
    page.keyboard.press("k")
    page.wait_for_timeout(600)
    after = page.evaluate("window.scrollY") if not has_audio else page.evaluate(now)
    check(after != moved, f"{label}: K works with the keyboard left on a tick box ({moved:.0f} -> {after:.0f})")

    # Space on a panel's heading opens the panel and plays nothing.
    panel = page.locator("details.panel").nth(1)
    panel.locator("summary").focus()
    page.keyboard.press("Space")
    check(panel.get_attribute("open") is not None, f"{label}: Space on a panel's heading opens it")
    if has_audio:
        check(page.evaluate("document.querySelector('audio').paused"), f"{label}: ...and plays nothing")
    panel.locator("summary").click()

    if has_audio:
        # The slider keeps moving after it has been touched, and its arrows go from where it is.
        slider = page.locator('input[aria-label="Position"]')
        slider.click()
        page.wait_for_timeout(300)
        page.evaluate("document.querySelector('audio').play()")
        page.wait_for_function("document.querySelector('audio').currentTime > 0 && !document.querySelector('audio').paused", timeout=10000)
        page.wait_for_timeout(2500)
        got = page.evaluate("[Number(document.querySelector('input[aria-label=Position]').value), document.querySelector('audio').currentTime]")
        check(abs(got[0] - got[1]) < 2, f"{label}: the slider follows the audio after being touched ({got[0]} at {got[1]:.1f} s)")
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(300)
        t = page.evaluate(now)
        check(8 < t - got[1] < 13, f"{label}: the right arrow on the slider goes forward ten seconds ({got[1]:.1f} -> {t:.1f})")
        page.evaluate("document.querySelector('audio').pause()")

    # A jump lands below the sticky player, on a laptop and on a phone.
    for width, height in [(1280, 900), (390, 800)]:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(300)
        k = min(20, page.locator(".block").count() - 1)
        if has_audio:
            # Moved while paused: the block's top shows below the player.
            page.evaluate(f"""() => {{
                document.querySelector('audio').pause();
                const s = document.querySelector('input[aria-label=Position]');
                s.value = {k * 30};
                s.dispatchEvent(new Event('input'));
            }}""")
        else:
            page.locator(f"#b-{k} .block-time .jump").click()
        page.wait_for_timeout(700)
        gap = page.evaluate(f"document.querySelector('#b-{k}').getBoundingClientRect().top - document.querySelector('.player').getBoundingClientRect().bottom")
        check(gap >= -1, f"{label}: at {width} wide a jump lands below the player ({gap:.0f} px clear)")
        # The error Next error goes to shows between the player and the bottom of the screen.
        page.locator(".player button", has_text="Next error").click()
        page.wait_for_timeout(900)
        got = page.evaluate("""() => {
            const w = document.querySelector('.word.flash');
            if (!w) return null;
            const r = w.getBoundingClientRect(), p = document.querySelector('.player').getBoundingClientRect();
            return [r.top - p.bottom, innerHeight - r.bottom];
        }""")
        check(got is None or min(got) >= 0, f"{label}: at {width} wide the next error isn't behind the player ({got})")
        if has_audio:
            # While it plays, the word being spoken stays in the clear too.
            page.evaluate("document.querySelector('audio').play()")
            page.wait_for_timeout(2500)
            spoken = page.evaluate("""() => {
                const w = [...document.querySelectorAll('.word.now')].find(n => n.offsetParent);
                if (!w) return null;
                const r = w.getBoundingClientRect(), p = document.querySelector('.player').getBoundingClientRect();
                document.querySelector('audio').pause();
                return [r.top - p.bottom, innerHeight - r.bottom];
            }""")
            page.evaluate("document.querySelector('audio').pause()")
            check(spoken is None or min(spoken) >= -2, f"{label}: at {width} wide the spoken word isn't behind the player ({spoken})")
    page.set_viewport_size({"width": 1280, "height": 900})

    if not has_audio:
        # The marker on the strip moves, though there is no audio to move it.
        page.wait_for_timeout(300)
        before = page.evaluate("document.querySelector('canvas.strip').toDataURL()")
        page.locator(".block-time .jump").nth(min(40, page.locator(".block").count() - 1)).click()
        page.wait_for_timeout(500)
        check(page.evaluate("document.querySelector('canvas.strip').toDataURL()") != before, f"{label}: the marker on the strip moves with no audio")

    # Out and straight back while the transcripts load draws it once, not twice.
    page.goto(web)
    page.wait_for_selector(".picker-table tbody tr", timeout=20000)
    keys = page.evaluate("""async hash => {
      shards.clear();
      let keys = 0;
      const add = window.addEventListener, remove = window.removeEventListener;
      window.addEventListener = function (t, ...r) { if (t === "keydown") keys++; return add.call(this, t, ...r); };
      window.removeEventListener = function (t, ...r) { if (t === "keydown") keys--; return remove.call(this, t, ...r); };
      const wait = ms => new Promise(done => setTimeout(done, ms));
      location.hash = hash; await wait(5);
      location.hash = ""; await wait(5);
      location.hash = hash;
      while (!document.querySelector(".player")) await wait(50);
      await wait(1500);
      window.addEventListener = add; window.removeEventListener = remove;
      return keys;
    }""", rec_hash(corpus, row["id"]))
    check(keys == 1, f"{label}: a quick return draws the recording once ({keys} key listeners)")

    # The list keeps its sort when you come back to it.
    page.goto(web)
    page.wait_for_selector(".picker-table tbody tr", timeout=20000)
    page.locator(".picker-table th button", has_text="Minutes").click()
    focused = page.evaluate("document.activeElement.textContent")
    check(focused == "Minutes", f"{label}: the heading keeps the keyboard after sorting ({focused!r})")
    page.locator(".picker-table a.rec").first.click()
    page.wait_for_selector(".player", timeout=20000)
    page.locator("a.back").click()
    page.wait_for_selector(".picker-table tbody tr", timeout=20000)
    check(page.locator(".picker-table th[aria-sort]").inner_text() == "Minutes", f"{label}: the list keeps its sort on return")
    page.evaluate("localStorage.clear()")


def check_controls(page, label: str, has_audio: bool) -> None:
    """The error highlights, the error buttons and keys, and back to the top."""
    page.locator(".transcript").scroll_into_view_if_needed()
    page.wait_for_selector(".block.drawn", timeout=10000)
    check(page.locator(".case-key .case").count() >= 1, f"{label}: a key to the highlighted errors")
    before = page.evaluate("window.scrollY")
    page.locator(".player button", has_text="Next error").click()
    page.wait_for_timeout(800)
    marked = page.locator(".word.case").count()
    check(marked > 0, f"{label}: errors are highlighted in the transcript ({marked} words drawn so far)")
    looks = page.evaluate("""() => {
      const fill = s => { const n = document.querySelector(s); return n ? getComputedStyle(n).backgroundColor : null; };
      return {
        engine: fill(".compare-line:not([data-who='Record']) .word.off:not(.case)"),
        record: fill(".compare-line[data-who='Record'] .word.miss:not(.case), .compare-line[data-who='Record'] .word.miss-all:not(.case)"),
        serious: fill(".word.case:not(.case-minor):not(.now)"),
        fillers: [...document.querySelectorAll(".word.miss-all:not(.case)")].filter(n => /^(uh|um|mm|hmm)[.,]?$/i.test(n.textContent)).length,
      };
    }""")
    clear = "rgba(0, 0, 0, 0)"
    check(looks["engine"] not in (None, clear), f"{label}: an engine's differing word has a filled highlight ({looks['engine']})")
    check(looks["record"] not in (None, clear), f"{label}: a record word an engine missed has a filled highlight ({looks['record']})")
    if looks["serious"]:
        check(looks["serious"] != looks["engine"], f"{label}: a serious error looks different from a plain difference")
    check(looks["fillers"] == 0, f"{label}: no filler word claims every engine missed it ({looks['fillers']})")
    # An error marks the engine's words it quotes, not everything timed near it.
    painted = page.evaluate("""() => {
      const seen = new Map();
      for (const n of document.querySelectorAll(".compare-line:not([data-who='Record']) .word.case")) {
        const m = n.title.match(/wrote “(.*?)”/);
        const key = n.closest(".compare-line").dataset.who + n.title;
        const allowed = m && m[1] !== "(nothing)" ? m[1].trim().split(/\\s+/).length : 0;
        seen.set(key, { count: (seen.get(key)?.count || 0) + 1, allowed });
      }
      return [...seen.values()].filter(v => v.count > 2 * v.allowed + 2).length;
    }""")
    check(painted == 0, f"{label}: no error paints more of an engine's words than it quotes ({painted} do)")
    if has_audio:
        t = page.evaluate("document.querySelector('audio').currentTime")
        check(t > 0, f"{label}: Next error moves the audio to the next error ({t:.1f} s)")
        page.select_option("#err-which", "all")
        page.locator("h2", has_text="The transcripts").click()   # keys go to the page, not the menu
        page.keyboard.press("k")
        page.wait_for_timeout(500)
        t2 = page.evaluate("document.querySelector('audio').currentTime")
        check(t2 > t, f"{label}: the K key steps to the next error ({t:.1f} -> {t2:.1f} s)")
        page.locator(".player button", has_text="+10 s").click()
        page.wait_for_timeout(300)
        t3 = page.evaluate("document.querySelector('audio').currentTime")
        check(abs(t3 - t2 - 10) < 1.5, f"{label}: +10 s moves ten seconds ({t2:.1f} -> {t3:.1f})")
    else:
        check(page.evaluate("window.scrollY") != before, f"{label}: with no audio, Next error scrolls to it")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)
    check(page.locator(".to-top").is_visible(), f"{label}: a back-to-top button after scrolling")
    page.locator(".to-top").click()
    try:
        page.wait_for_function("window.scrollY < 5", timeout=5000)
    except Exception:
        pass
    check(page.evaluate("window.scrollY") < 5, f"{label}: back to the top works")


def shots(page, name: str) -> None:
    (OUT / "checks").mkdir(exist_ok=True)
    for width, tag in ((1280, "desktop"), (390, "phone")):
        for scheme in ("light", "dark"):
            page.set_viewport_size({"width": width, "height": 900})
            page.emulate_media(color_scheme=scheme)
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "checks" / f"{name}-{tag}-{scheme}.png"))
    page.set_viewport_size({"width": 1280, "height": 900})
    page.emulate_media(color_scheme="light")


def main() -> int:
    global OUT
    corpus = sys.argv[1] if len(sys.argv) > 1 else "scotus"
    OUT = explore_local.OUT = explore_local.lineup.CAPSTONE / "explorer" / corpus
    catalog = json.loads((OUT / "catalog.json").read_text(encoding="utf-8"))
    explore_local.Handler.audio = json.loads((OUT / "local-audio.json").read_text(encoding="utf-8"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), explore_local.Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    with_audio = next((r for r in catalog if r.get("audio")), None)
    no_audio = next((r for r in catalog if not r.get("audio")), None)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        web = f"http://127.0.0.1:{port}/?web"
        page.goto(web)
        page.wait_for_selector("table.sortable tbody tr", timeout=20000)
        rows = page.locator(".picker-table tbody tr").count()
        check(rows == len(catalog), f"web: the list has every recording ({rows} of {len(catalog)})")
        check(page.locator("a.source-button").get_attribute("href").startswith("http"), "web: a link to the data set's own site")
        page.select_option("#pick-kind", "skips")
        rows = page.locator(".picker-table tbody tr").count()
        want = sum(r["k"]["skips"] > 0 for r in catalog)
        check(rows == want, f"web: the failure-kind filter works ({rows} with a skip, expected {want})")
        page.select_option("#pick-kind", "any")
        credit = page.evaluate("document.querySelector('#footer').innerText")
        check(CREDIT_NAMES[corpus] in credit, f"web: the footer credits {CREDIT_NAMES[corpus]}")
        if corpus != "scotus":
            check(page.locator("#footer a[href*='creativecommons.org/licenses']").count() == 1, "web: the footer links to the licence")
        check(page.locator("#nav a[href$='#go-ai']").count() == 1 and page.locator("#footer a[href$='#go-ai']").count() == 1,
              "web: How AI was used, linked in the bar and the footer")
        page.check("#pick-audio")
        rows = page.locator(".picker-table tbody tr").count()
        want = sum(1 for r in catalog if r.get("audio"))
        check(rows == want, f"web: 'full audio only' leaves the {want} with audio published ({rows})")
        page.uncheck("#pick-audio")
        shots(page, "picker")

        if with_audio:
            label = f"web, {with_audio['id']}"
            open_recording(page, web, with_audio, label)
            play_and_watch(page, label)
            check_controls(page, label, True)
            check_reader_actions(page, label, True, corpus, with_audio, web)
            open_recording(page, web, with_audio, label)
            shots(page, "recording")
            at = int(with_audio["min"] * 60 * 0.5)
            page.goto(f"{web}#{rec_hash(corpus, with_audio['id'], at)}")
            page.wait_for_selector(".block.drawn", timeout=20000)
            page.wait_for_timeout(800)
            t = page.evaluate("document.querySelector('audio').currentTime")
            check(abs(t - at) < 2, f"web: an address with {at} seconds opens the recording there ({t:.0f} s)")
        if no_audio:
            label = f"web, {no_audio['id']} (no audio here)"
            open_recording(page, web, no_audio, label)
            check(page.locator(".player .btn.big").count() == 0, f"{label}: no player, and a note says why")
            check_controls(page, label, False)
            check_reader_actions(page, label, False, corpus, no_audio, web)
            open_recording(page, web, no_audio, label)
            # Most rows on the data page link to a recording without audio here.
            at = int(no_audio["min"] * 60 * 0.5)
            page.goto(f"{web}#{rec_hash(corpus, no_audio['id'], at)}")
            page.wait_for_selector(".block.drawn", timeout=20000)
            page.wait_for_timeout(800)
            scrolled = page.evaluate("window.scrollY")
            check(scrolled > 1000, f"{label}: an address with {at} seconds scrolls down to it ({scrolled:.0f} px)")

        # Every recording's address must hold only what claude.ai lets through, and read back.
        bad = page.evaluate("""() => catalog.filter(r => {
            const h = recordingHash(r.c, r.id, 61), back = readHash(h);
            return !/^[A-Za-z0-9-]+$/.test(h) || back.id !== r.id || back.c !== r.c || back.at !== 61;
        }).map(r => r.id)""")
        check(not bad, f"every recording's address is letters, digits and hyphens and reads back ({len(bad)} bad: {bad[:3]})")
        wrong = page.evaluate("""() => [...document.querySelectorAll('#nav a')].map(a => a.getAttribute('href'))
            .filter(h => h.includes('#') && !/#[A-Za-z0-9-]*$/.test(h))""")
        check(not wrong, f"the links across the top have addresses claude.ai lets through ({wrong[:2]})")
        page.goto(f"{web}#r.{corpus}.{(with_audio or no_audio)['id']}@30")
        page.wait_for_selector(".block", timeout=20000)
        check(page.locator("h1").inner_text().strip() == (with_audio or no_audio)["title"].strip(), "the old form of address still opens the recording")

        local = f"http://127.0.0.1:{port}/"
        if no_audio:
            open_recording(page, local, no_audio, f"local, {no_audio['id']}")
            play_and_watch(page, f"local, {no_audio['id']}")
            page.locator("details.panel summary", has_text="Every file").click()
            href = page.locator(".file-list a").first.get_attribute("href")
            resp = page.request.get(f"{local}{href}", headers={"Range": "bytes=0-99"})
            check(resp.status == 206, f"local: the file links open the laptop's files ({resp.status})")

        page.set_viewport_size({"width": 390, "height": 900})
        page.wait_for_timeout(300)
        wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(wide <= 1, f"no sideways scroll on a phone ({wide}px over)")
        check(not errors, "no script errors" + (f": {errors[:3]}" if errors else ""))
        browser.close()
    server.shutdown()
    print(f"\n{len(failures)} failed; screenshots in {OUT / 'checks'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

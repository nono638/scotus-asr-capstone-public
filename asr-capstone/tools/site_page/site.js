// Small helpers shared by the front page and every data-set page.
const $ = s => document.querySelector(s);
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  for (const k of kids) n.append(k);
  return n;
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = v => (v === null || v === undefined) ? "–" : v.toFixed(1) + "%";
const pct2 = v => (v === null || v === undefined) ? "–" : v.toFixed(2) + "%";

// The whole-recording pages (tools/build_explorer.py), one per data set: each is
// its own page, since one page cannot hold the audio of them all.
const EXPLORERS = /*EXPLORERS*/{};

// The bar across the top: the site's name, home, a link to each data set, the
// big picture and the data; under it, the whole-recording pages, which are
// separate pages and open in a new tab.
function siteNav(root, pages, current) {
  root.append(el("a", { class: "home", href: "index.html" }, "Where speech recognition goes wrong"));
  const links = el("span", { class: "links" });
  [{ file: "index.html", name: "Home" }, ...pages,
   { file: "compare.html", name: "Big picture" }, { file: "data.html", name: "Search the data" },
   { file: "ai.html", name: "How AI was used" }].forEach(p => {
    const a = el("a", { href: p.file }, p.name);
    if (p.file === current) a.setAttribute("aria-current", "page");
    links.append(a);
  });
  root.append(links);
  const rec = el("span", { class: "recordings" }, "Whole recordings:");
  pages.forEach(p => {
    const url = EXPLORERS[p.corpus];
    if (url) rec.append(el("a", { href: url, target: "_blank", rel: "noopener" }, p.name));
  });
  if (rec.children.length) root.append(rec);
  backToTop();
  aiNote();
}

// A line at the foot of every page: AI did much of the work, and where to read how.
function aiNote() {
  const foot = document.querySelector("footer");
  if (!foot || foot.querySelector(".ai-note")) return;
  foot.append(el("p", { class: "ai-note" }, "This site was built with a lot of help from AI: the speech engines, the judges that labelled the errors, and the assistant that wrote most of the code. ",
    el("a", { href: "ai.html" }, "How AI was used"), "."));
}

// A button in the corner that takes you back to the top, shown once you have
// scrolled down a screen or so.
function backToTop() {
  const b = el("button", { type: "button", class: "to-top", "aria-label": "Back to top" }, "↑ Top");
  b.hidden = true;
  b.addEventListener("click", () => window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }));
  document.body.append(b);
  const check = () => { b.hidden = window.scrollY < window.innerHeight * 0.8; };
  window.addEventListener("scroll", check, { passive: true });
  check();
}

// A switch of buttons (role group); calls pick(key) and marks the pressed one.
function switchOf(root, options, chosen, pick) {
  options.forEach(([key, label]) => {
    const b = el("button", { type: "button", "data-mode": key, "aria-pressed": String(key === chosen) }, label);
    b.addEventListener("click", () => {
      root.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      pick(key);
    });
    root.append(b);
  });
}

// The address of a moment on a whole-recording page, 5 seconds before `start`.
// claude.ai passes only letters, digits and hyphens from a link to the page, so in the
// recording's name "-" is written "-h" and "_" "-u"; explorer.js reads it back.
function recordingHash(corpus, recording, start) {
  const id = String(recording).replace(/-/g, "-h").replace(/_/g, "-u");
  return `r-${corpus}-${Math.max(0, Math.floor(start - 5))}-${id}`;
}

// A link into the whole-recording page at a moment, when that recording has audio there.
function hearLink(c) {
  const url = EXPLORERS[c.corpus];
  return url && c.recording ? `${url}#${recordingHash(c.corpus, c.recording, c.start)}` : "";
}

// A grid of failure cards, the first `shown` visible and a button for the rest.
function cardGrid(root, cards, shown = 4) {
  const grid = el("div", { class: "cards" });
  root.append(grid);
  const draw = c => Cards.failure(grid, { ...c, hear: hearLink(c) });
  cards.slice(0, shown).forEach(draw);
  if (cards.length > shown) {
    const more = el("button", { type: "button", class: "more-cards" }, `Show ${cards.length - shown} more`);
    more.addEventListener("click", () => { cards.slice(shown).forEach(draw); more.remove(); });
    root.append(more);
  }
}

// Columns from the data can't carry functions; "digits" asks for a fixed number of decimals.
function withFormats(columns) {
  return columns.map(c => c.digits === undefined ? c :
    { ...c, fmt: v => (v === null || v === undefined) ? "–" : Number(v).toFixed(c.digits) });
}

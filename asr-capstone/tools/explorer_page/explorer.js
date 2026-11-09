// The whole-recording page of one data set: pick any recording, then read the
// reference and every engine's words side by side, listen where the audio is here,
// and step from one highlighted error to the next. Everything shown is fetched
// from files beside the page, written by tools/build_explorer.py.
//
// A whole argument is about 10,000 words a transcript, so the transcript is drawn
// in 30-second blocks as they scroll into view, and the word being spoken is found
// by time within the current block, never by walking every word on the page.
//
// The address picks the view: no # for the list, or #r-<data set>-<seconds>-<recording>
// for one recording, opened at that moment ("x" for no moment). claude.ai passes only
// letters, digits and hyphens from a link to the page, so in the recording's name "-"
// is written "-h" and "_" "-u". The website's links are made the same way (site.js).
function recordingHash(c, id, at) {
  return `r-${c}-${at === undefined ? "x" : Math.floor(at)}-${id.replace(/-/g, "-h").replace(/_/g, "-u")}`;
}
function readHash(text) {
  const m = text.match(/^r-([a-z0-9]+)-(x|\d+)-(.+)$/);
  if (m) return { c: m[1], at: m[2] === "x" ? undefined : Number(m[2]), id: m[3].replace(/-([hu])/g, (_, k) => k === "h" ? "-" : "_") };
  // The old form, #r.<data set>.<recording>@<seconds>, still works where it reaches the page.
  if (!text.startsWith("r.")) return null;
  const [, c, ...rest] = text.split(".");
  const [id, at] = rest.join(".").split("@");
  return { c, id, at: at === undefined ? undefined : Number(at) };
}
const hashNow = () => readHash(decodeURIComponent(location.hash.slice(1)));


// On the laptop (tools/explore_local.py) every recording plays from its own file.
// "?web" makes the laptop behave like the published page, for tools/check_explorer.py.
const LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname) && !location.search.includes("web");
const ENGINE_ORDER = ["Qwen3", "Whisper", "Parakeet", "Canary", "Granite"];
const COLOUR = { Record: "--record", Qwen3: "--qwen3", Whisper: "--whisper", Parakeet: "--parakeet",
                 Canary: "--canary", Granite: "--granite" };
const KIND = { meaning: ["Meaning change", "--k-misheard"], invented: ["Invented words", "--k-notreal"],
               edits: ["Edits the speaker", "--k-disfluency"], skips: ["Silent skip", "--k-leftout"] };
// The website's sections, in its words, each with a colour; "minor" is a plain
// mishearing, marked more quietly.
const SECTION = Object.fromEntries([...META.sections, ["minor", "Another word (a plain mishearing)"]]
  .map(([k, t]) => [k, { label: t, colour: { opposite: "--e-meaning", fact: "--e-fact", invented: "--e-invented",
    skips: "--e-skips", edits: "--e-edits", minor: "--mark" }[k] }]));
const BLOCK = 30;          // seconds of recording in one block of transcript

const $ = s => document.querySelector(s);
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v);
  for (const k of kids) if (k !== null && k !== undefined) n.append(k);
  return n;
}
const clock = s => {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0");
};
const pct = v => (v === null || v === undefined) ? "–" : Number(v).toFixed(2) + "%";
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const store = {
  get(k, d) { try { const v = localStorage.getItem("explorer." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("explorer." + k, JSON.stringify(v)); } catch { /* private window */ } },
};

// Files beside the page. The transcripts (rec/*.txt) are gzipped and then written
// as base64 text, because the website serves only a fixed list of file types and
// a compressed file is not one of them.
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} answered ${r.status}`);
  let buf = new Uint8Array(await r.arrayBuffer());
  if (url.endsWith(".txt")) buf = Uint8Array.from(atob(new TextDecoder().decode(buf).trim()), c => c.charCodeAt(0));
  if (buf[0] === 0x1f && buf[1] === 0x8b) {
    const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
    return JSON.parse(await new Response(stream).text());
  }
  return JSON.parse(new TextDecoder().decode(buf));
}

let catalog = [];
const shards = new Map();
const view = $("#view");
let leave = () => {};      // stops whatever the last view was playing
const NAME = META.names[META.corpus];

// --- the bar across the top, the footer, and back to the top ----------------------------

// The website and the other recording pages are separate pages, so they open in a
// new tab; #go-data, say, asks the website's home page to open one of its own pages.
function nav(current) {
  const bar = $("#nav");
  const out = (href, text) => el("a", { href, target: "_blank", rel: "noopener" }, text);
  const site = el("span", { class: "links" }, out(META.siteUrl, "Home"));
  Object.entries(META.pages).forEach(([c, file]) => site.append(out(`${META.siteUrl}#go-${file.replace(".html", "")}`, META.names[c])));
  site.append(out(`${META.siteUrl}#go-compare`, "Big picture"), out(`${META.siteUrl}#go-data`, "Search the data"),
    out(`${META.siteUrl}#go-ai`, "How AI was used"));
  const rec = el("span", { class: "recordings" }, "Whole recordings:");
  Object.entries(META.explorers).forEach(([c, url]) => rec.append(c === META.corpus
    ? el("a", { href: "#", "aria-current": current === "picker" ? "page" : "true" }, META.names[c])
    : out(url, META.names[c])));
  bar.replaceChildren(out(META.siteUrl, "Where speech recognition goes wrong"), site, rec,
    el("span", { class: "own" }, out(META.home[1], `${NAME}: the data set's own site`)));
  bar.firstChild.classList.add("home");
}

function footer() {
  const credits = el("div", {});
  Credits.list(credits, META.credits);
  $("#footer").replaceChildren(
    credits,
    el("p", {}, LOCAL ? "This is the local copy: every recording plays in full, from the laptop's own files."
      : "Full audio is here for as many recordings as the page can hold; the local copy on the 5090 laptop (tools/explore_local.py) plays every one."),
    el("p", {}, "This page was built with a lot of help from AI: the engines' transcripts are AI, the error labels come from an AI judge, and an AI assistant wrote the code. ",
      el("a", { href: `${META.siteUrl}#go-ai`, target: "_blank", rel: "noopener" }, "How AI was used"), "."),
    el("p", {}, `Built ${META.built} by tools/build_explorer.py.`));
}

(function backToTop() {
  const b = el("button", { type: "button", class: "to-top", "aria-label": "Back to top" }, "↑ Top");
  b.hidden = true;
  b.addEventListener("click", () => window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }));
  document.body.append(b);
  const check = () => { b.hidden = window.scrollY < window.innerHeight * 0.8; };
  window.addEventListener("scroll", check, { passive: true });
  check();
})();

// --- the picker ------------------------------------------------------------------------

function audioOf(row) {
  if (LOCAL) return `local/audio/${encodeURIComponent(row.id)}`;
  return row.audio || null;
}
const partLabel = p => META.parts[p] || p;
const casesOf = row => Object.values(row.k).reduce((a, b) => a + b, 0);

function showPicker() {
  nav("picker");
  const st = Object.assign({ part: "all", kind: "any", audio: false, q: "" }, store.get("picker." + META.corpus, {}));
  const save = () => store.set("picker." + META.corpus, st);
  const withAudio = catalog.filter(r => audioOf(r));
  const hours = withAudio.reduce((n, r) => n + r.min, 0) / 60;
  const part = el("select", { id: "pick-part" });
  const kind = el("select", { id: "pick-kind" },
    el("option", { value: "any" }, "Any"),
    ...Object.entries(KIND).map(([k, [label]]) => el("option", { value: k }, label)));
  kind.value = st.kind;
  const audio = el("input", { type: "checkbox", id: "pick-audio" });
  audio.checked = st.audio;
  const q = el("input", { type: "search", id: "pick-q", placeholder: "Case name, docket or recording", value: st.q });
  const count = el("p", { class: "count-line", role: "status" });
  const host = el("div", { class: "picker-table" });

  function fillParts() {
    const parts = [...new Set(catalog.map(r => r.p))];
    part.replaceChildren(el("option", { value: "all" }, "Every part"),
      ...parts.map(p => el("option", { value: p }, partLabel(p))));
    part.value = parts.includes(st.part) ? st.part : "all";
  }
  part.addEventListener("change", () => { st.part = part.value; save(); apply(); });
  kind.addEventListener("change", () => { st.kind = kind.value; save(); apply(); });
  audio.addEventListener("change", () => { st.audio = audio.checked; save(); apply(); });
  q.addEventListener("input", () => { st.q = q.value; save(); apply(); });

  const columns = [
    { key: "title", label: "Recording", fmt: (v, r) => el("span", {},
        el("a", { class: "rec", href: "#" + recordingHash(r.row.c, r.row.id) }, v),
        el("span", { class: "id" }, [r.row.id, r.row.sub].filter(Boolean).join(" · "))) },
    { key: "set", label: "Part" },
    { key: "min", label: "Minutes", num: true, fmt: v => v.toFixed(0) },
    ...["Qwen3", "Whisper", "Parakeet"].map(e => ({ key: e, label: e, num: true, fmt: pct })),
    { key: "cases", label: "Errors found", num: true },
    { key: "cards", label: "On the website", num: true, fmt: v => v ? String(v) : "" },
    { key: "audio", label: "Audio", fmt: v => v ? el("span", { class: "pill full" }, "full") : el("span", { class: "pill" }, "text only") },
  ];
  // Unsorted to begin with: the catalog's own order, Supreme Court first.
  // The reader's own sort, if they made one, is kept for when they come back to the list.
  const opts = { columns, rows: [], caption: "Recordings",
                 sort: columns.some(c => c.key === st.sort?.key) ? st.sort : null,
                 onSort: sort => { st.sort = sort; save(); } };
  let table = null;

  function apply() {
    const words = st.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const rows = catalog.filter(r =>
      (st.part === "all" || r.p === st.part) &&
      (st.kind === "any" || r.k[st.kind] > 0) &&
      (!st.audio || audioOf(r)) &&
      words.every(w => `${r.title} ${r.id} ${r.sub}`.toLowerCase().includes(w)));
    opts.rows.length = 0;
    for (const r of rows) {
      opts.rows.push({ row: r, title: r.title, set: partLabel(r.p), min: r.min, cards: r.cards,
        Qwen3: r.sc.Qwen3?.benchmark, Whisper: r.sc.Whisper?.benchmark, Parakeet: r.sc.Parakeet?.benchmark,
        cases: casesOf(r), audio: audioOf(r) ? 1 : 0 });
    }
    count.textContent = `${rows.length} of ${catalog.length} recordings. Error rates are the benchmark rule. ` +
      "“On the website” counts the cards about it there. Click a heading to sort, a name to open it.";
    if (!table) table = Table.sortable(host, opts);
    else table.redraw();
  }

  view.replaceChildren(
    el("h1", {}, `Every ${NAME} recording`),
    el("p", { class: "lede" }, `All ${catalog.length} recordings, each transcribed by ${catalog[0]?.engines.length || 3} speech engines. ` +
      "Open one to read the reference and every engine's words side by side, with every error the searches found highlighted before you reach it. " +
      (withAudio.length ? `The audio is here for ${withAudio.length} of them (${hours.toFixed(0)} hours): tick “Full audio only” to list just those.`
                        : "None of the audio is on this page: " + (META.corpus === "earnings22" ? "the calls have no stated licence." : "it would not fit."))),
    el("p", {}, el("a", { class: "source-button", href: META.home[1], target: "_blank", rel: "noopener" }, `Go to the data set: ${META.home[0]}`)),
    el("div", { class: "filters" },
      el("div", { class: "filter-row" },
        el("label", { for: "pick-part" }, "Part", part),
        el("label", { for: "pick-kind" }, "Has a failure of this kind", kind),
        el("label", { for: "pick-audio" }, audio, "Full audio only"),
        el("label", { for: "pick-q", class: "sr-only" }, "Search"), q)),
    count, host);
  fillParts();
  apply();
}

// --- one recording ----------------------------------------------------------------------

async function showRecording(c, id, at, ticket) {
  nav("rec");
  const row = catalog.find(r => r.c === c && r.id === id);
  if (!row) {
    view.replaceChildren(el("a", { class: "back", href: "#" }, "← All recordings"),
      el("p", { class: "problem" }, `There is no recording called ${id} in ${META.names[c] || c}.`));
    return;
  }
  view.replaceChildren(el("p", { class: "loading" }, "Loading the transcripts…"));
  let rec;
  try {
    if (!shards.has(row.shard)) shards.set(row.shard, await fetchJSON(row.shard));
    rec = shards.get(row.shard)[id];
  } catch (e) {
    if (ticket !== routes) return;
    view.replaceChildren(el("a", { class: "back", href: "#" }, "← All recordings"),
      el("p", { class: "problem" }, "The transcripts didn't load: " + e.message));
    return;
  }
  // The reader moved on while it loaded, perhaps out and back to this same recording.
  if (ticket !== routes) return;
  drawRecording(row, rec, at);
}

function decodeLine(line, last) {
  const words = line.t.split(" ");
  const n = words.length;
  const s = new Float64Array(n), e = new Float64Array(n);
  let acc = 0;
  for (let i = 0; i < n; i++) { acc += line.s[i]; s[i] = acc / 100; }
  for (let i = 0; i < n; i++) {
    // The reference has no ends of its own: a word lasts until the next begins.
    e[i] = line.d ? s[i] + line.d[i] / 100 : (i + 1 < n ? Math.max(s[i] + 0.05, s[i + 1]) : Math.min(s[i] + 0.4, last));
  }
  return { words, s, e, off: line.off || "", missed: line.missed || "" };
}

// The record's speakers. The transcripts name them by code (CORAAL's
// ROC_se0_ag1_f_01, EdAcc's EDACC-C01-A, Earnings-22's 0, 1, 2); META.speakers
// gives a plain name for each, from the corpus's own metadata. CORAAL starts a
// new row at every pause, so a name is shown only when the speaker changes.
function speakersOf(ref, recording) {
  META.speakers = META.speakers || {};
  const at = new Map();
  let last = null;
  for (const [i, t] of ref.turns) {
    const code = ref.speakers[t];
    if (code !== last) at.set(i, code);
    last = code;
  }
  const codes = [...new Set(at.values())];
  const asks = code => (META.interviewer?.[code] || []).includes(recording);
  const base = code => asks(code) ? "Interviewer" : (META.speakers[code] || [])[0]
    || (/^\d+$/.test(code) ? `Speaker ${Number(code) + 1}` : `Speaker ${code}`);
  const count = {};
  codes.forEach(c => { count[base(c)] = (count[base(c)] || 0) + 1; });
  const seen = {};
  const name = new Map(codes.map(c => {
    const b = base(c);
    if (count[b] < 2 || /\d$/.test(b) || /^Speaker [A-Z]$/.test(b)) return [c, b];
    seen[b] = (seen[b] || 0) + 1;
    return [c, `${b} ${seen[b]}`];
  }));
  const about = code => (META.speakers[code] || [])[1] || "";
  const title = code => [about(code), `code ${code}`].filter(Boolean).join("; ");
  const key = () => {
    if (!codes.some(c => META.speakers[c])) return null;
    return el("ul", { class: "who-speaks", "aria-label": "Who speaks" }, el("li", { class: "label" }, "Who speaks:"),
      ...codes.map(c => el("li", {}, el("b", {}, name.get(c)), about(c) ? `: ${about(c)}` : "", el("span", { class: "code" }, ` (${c})`))));
  };
  return { at, name, title, key };
}

function drawRecording(row, rec, at) {
  const duration = row.min * 60;
  const engines = ENGINE_ORDER.filter(e => rec.engines[e]);
  const lines = [{ who: "Record", ...decodeLine(rec.ref, duration) },
                 ...engines.map(e => ({ who: e, ...decodeLine(rec.engines[e], duration) }))];
  const voices = speakersOf(rec.ref, row.id);
  const nBlocks = Math.max(1, Math.ceil(duration / BLOCK),
    ...lines.map(l => l.s.length ? Math.floor(l.s[l.s.length - 1] / BLOCK) + 1 : 1));
  for (const l of lines) {
    l.buckets = Array.from({ length: nBlocks }, () => []);
    for (let i = 0; i < l.s.length; i++) l.buckets[Math.min(nBlocks - 1, Math.floor(l.s[i] / BLOCK))].push(i);
  }
  const hidden = new Set(store.get("hidden", []));
  const src = audioOf(row);

  // ---- the head: what it is, and how each engine scored
  const scoreCols = [{ key: "engine", label: "Engine" }, { key: "benchmark", label: "Error rate", num: true, fmt: pct },
    { key: "swapped", label: "Words swapped", num: true, fmt: pct }, { key: "dropped", label: "Words dropped", num: true, fmt: pct },
    { key: "added", label: "Words added", num: true, fmt: pct }];
  const scoreBox = el("div", { class: "rec-scores" });
  Table.sortable(scoreBox, { columns: scoreCols, rows: engines.map(e => ({ engine: e, ...(row.sc[e] || {}) })),
                             sort: { key: "benchmark", dir: 1 }, caption: "Error rates" });

  // ---- the player
  const audio = el("audio", { preload: "none" });
  const playBtn = el("button", { type: "button", class: "btn big", "aria-pressed": "false", title: "Play or pause (Space)" }, "Play");
  const backBtn = el("button", { type: "button", class: "btn", title: "Back 10 seconds (left arrow)" }, "−10 s");
  const fwdBtn = el("button", { type: "button", class: "btn", title: "Forward 10 seconds (right arrow)" }, "+10 s");
  const prevErr = el("button", { type: "button", class: "btn", title: "The error before this point (J)" }, "◂ Previous error");
  const nextErr = el("button", { type: "button", class: "btn", title: "The next error (K)" }, "Next error ▸");
  const errWhich = el("select", { id: "err-which", "aria-label": "Which errors to step through" },
    el("option", { value: "serious" }, "the serious ones"), el("option", { value: "all" }, "every one"));
  errWhich.value = store.get("errWhich", "serious");
  errWhich.addEventListener("change", () => store.set("errWhich", errWhich.value));
  const time = el("span", { class: "clock" }, `0:00 / ${clock(duration)}`);
  const seek = el("input", { type: "range", min: "0", max: String(Math.ceil(duration)), step: "1", value: "0", "aria-label": "Position" });
  const speed = el("select", { id: "speed" }, ...[1, 1.25, 1.5, 2].map(v => el("option", { value: String(v) }, v + "×")));
  const follow = el("input", { type: "checkbox", id: "follow" });
  follow.checked = store.get("follow", true);
  follow.addEventListener("change", () => store.set("follow", follow.checked));
  speed.addEventListener("change", () => { audio.playbackRate = Number(speed.value); });
  const linesPick = el("div", { class: "lines-pick", role: "group", "aria-label": "Lines shown" },
    ...engines.map(e => {
      const box = el("input", { type: "checkbox", id: `show-${e}` });
      box.checked = !hidden.has(e);
      box.addEventListener("change", () => {
        box.checked ? hidden.delete(e) : hidden.add(e);
        store.set("hidden", [...hidden]);
        transcript.querySelectorAll(`[data-who="${e}"]`).forEach(n => { n.hidden = hidden.has(e); });
      });
      const label = el("label", { for: `show-${e}` }, box, el("b", {}, e));
      label.style.setProperty("--who", `var(${COLOUR[e]})`);
      return label;
    }));
  const player = el("div", { class: "player" });
  const errRow = el("div", { class: "player-row" }, prevErr, nextErr, el("label", { for: "err-which" }, "Step through", errWhich));
  if (src) {
    audio.src = src;
    player.append(audio, el("div", { class: "player-row" }, playBtn, backBtn, fwdBtn, time, seek), errRow,
      el("div", { class: "player-row" },
        el("label", { for: "speed" }, "Speed", speed),
        el("label", { for: "follow" }, follow, "Keep the words in view"),
        linesPick),
      el("p", { class: "note keys" }, "Keys: Space play or pause, ← and → ten seconds, J and K the previous and next error."));
  } else {
    player.append(el("p", { class: "note" }, noAudioNote(row)), errRow, el("div", { class: "player-row" }, linesPick));
  }
  backBtn.addEventListener("click", () => jump((audio.currentTime || pos) - 10, !audio.paused));
  fwdBtn.addEventListener("click", () => jump((audio.currentTime || pos) + 10, !audio.paused));
  prevErr.addEventListener("click", () => stepError(-1));
  nextErr.addEventListener("click", () => stepError(1));
  playBtn.addEventListener("click", () => { audio.paused ? audio.play().catch(playFailed) : audio.pause(); });
  const status = el("p", { class: "note", role: "status" });
  player.append(status);
  function playFailed(e) { if (e.name !== "AbortError") status.textContent = `The audio didn't play (${e.name}: ${e.message}).`; }
  audio.addEventListener("error", () => { status.textContent = "The audio didn't load from " + audio.src + "."; });
  audio.addEventListener("play", () => { playBtn.textContent = "Pause"; playBtn.setAttribute("aria-pressed", "true"); frame(); });
  audio.addEventListener("pause", () => { playBtn.textContent = "Play"; playBtn.setAttribute("aria-pressed", "false"); });
  seek.addEventListener("input", () => { jump(Number(seek.value), false); });
  // The slider follows the audio unless the reader is holding it. Having been touched
  // isn't enough: it keeps the keyboard afterwards, and must not freeze.
  let dragging = false;
  seek.addEventListener("pointerdown", () => { dragging = true; });
  const letGo = () => { dragging = false; };
  addEventListener("pointerup", letGo);
  addEventListener("pointercancel", letGo);

  // ---- the strip: where the engines differ, and where the failure cases are
  const strip = el("canvas", { class: "strip", role: "img",
    "aria-label": "How much of each 30 seconds the engines got differently from the record, with the failure cases marked below" });
  const share = Array.from({ length: nBlocks }, (_, k) => {
    let off = 0, all = 0;
    for (const l of lines.slice(1)) for (const i of l.buckets[k]) { all++; if (l.off[i] === "1") off++; }
    return all ? off / all : 0;
  });
  function drawStrip(t = src ? audio.currentTime : pos) {
    const w = strip.clientWidth, h = strip.clientHeight, dpr = window.devicePixelRatio || 1;
    if (!w) return;
    strip.width = w * dpr; strip.height = h * dpr;
    const g = strip.getContext("2d");
    g.scale(dpr, dpr);
    const bw = w / nBlocks, top = 4, room = h - 18;
    g.fillStyle = css("--diff");
    share.forEach((v, k) => { const bh = Math.min(1, v / 0.4) * room; g.fillRect(k * bw, top + room - bh, Math.max(1, bw - 0.5), bh); });
    for (const c of rec.cases) {
      if (c.sec === "minor") continue;
      g.fillStyle = css(SECTION[c.sec].colour);
      g.fillRect((c.s / duration) * w - 1, h - 10, 2, 8);
    }
    g.fillStyle = css("--ink");
    g.fillRect((t / duration) * w - 1, 0, 2, h);
  }
  strip.addEventListener("click", ev => {
    const r = strip.getBoundingClientRect();
    jump(((ev.clientX - r.left) / r.width) * duration, !audio.paused);
  });
  const stripKey = el("div", { class: "strip-key" },
    el("span", { style: "--c: var(--diff)" }, "Bars: share of the engines' words that differ from the record, per 30 seconds"),
    el("span", { style: "--c: var(--faint)" }, "Ticks below: the errors, coloured as in the transcript"));

  // ---- which words each error covers, so they can be highlighted before they are heard
  const serious = c => c.sec !== "minor";
  const casesSorted = [...rec.cases].sort((a, b) => a.s - b.s);
  const marks = lines.map(() => new Map());
  const lineOf = Object.fromEntries(lines.map((l, i) => [l.who, i]));
  const labelOf = c => `${SECTION[c.sec].label}: the record has “${c.record || "(nothing)"}”, ${c.engine} wrote “${c.wrote || "(nothing)"}”.` +
    (c.judge ? ` ${c.judge}.` : "") + (c.note ? ` ${c.note}` : "");
  const better = (old, c) => !old || (old.sec === "minor" && c.sec !== "minor");
  // The words of an engine's line that a case is about: the ones it quotes, found
  // inside its time span. The span alone won't do: an aligner can give hundreds of
  // words one time, and a case that lost its place spans the whole recording.
  const plainWord = w => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
  function wordsOfCase(l, c) {
    const goal = plainWord(c.wrote || "");
    if (!goal) return [0, 0];                 // the engine wrote nothing here
    const from = lowerBound(l.s, c.s - 0.05);
    let to = from;
    while (to < l.s.length && l.s[to] <= c.e + 0.05) to++;
    for (let i = from; i < to; i++) {
      let got = "", k = i;
      while (k < to && got.length < goal.length) got += plainWord(l.words[k++]);
      if (got === goal) return [i, k];
    }
    return [from, Math.min(to, from + c.wrote.trim().split(/\s+/).length)];
  }
  for (const c of casesSorted) {
    const li = lineOf[c.engine];
    if (li !== undefined) {
      const [from, to] = wordsOfCase(lines[li], c);
      for (let i = from; i < to; i++) if (better(marks[li].get(i), c)) marks[li].set(i, c);
    }
    if (c.ri) for (let i = c.ri[0]; i < c.ri[1]; i++) if (better(marks[0].get(i), c)) marks[0].set(i, c);
  }
  const legend = el("div", { class: "case-key" }, "Key: ",
    ...Object.entries(SECTION).filter(([k]) => k !== "minor").map(([k, v]) => {
      const n = rec.cases.filter(c => c.sec === k).length;
      return n ? el("span", { class: `case case-${k}` }, `${v.label} (${n})`) : null;
    }).filter(Boolean),
    el("span", { class: "case case-minor" }, "Differs from the record"),
    el("span", { class: "case case-all" }, "Every engine differs"));

  // ---- the failure cases, in time order
  const cases = [...rec.cases].sort((a, b) => a.s - b.s);
  const casesPanel = el("details", { class: "panel", open: cases.length ? "" : null },
    el("summary", {}, "Failure cases found here", el("small", {}, `${cases.length}`)));
  if (cases.length) {
    const host = el("div", { class: "cases-table" });
    Table.sortable(host, {
      columns: [
        { key: "s", label: "At", num: true, fmt: v => jumpButton(v) },
        { key: "sec", label: "What it does", fmt: v => el("span", { class: `kind case case-${v}` }, SECTION[v].label) },
        { key: "engine", label: "Engine" },
        { key: "record", label: "Record, then what the engine wrote", sort: false, fmt: (v, r) => el("span", {},
            el("span", { class: "quote" }, `“${r.record || "(nothing)"}” → “${r.wrote || "(nothing)"}”`),
            el("span", { class: "note" }, [r.note || r.why || "", r.judge || ""].filter(Boolean).join(" "))) },
      ],
      rows: cases, sort: { key: "s", dir: 1 }, caption: "Failure cases" });
    casesPanel.append(el("p", { class: "hint" }, "Every case the four failure searches found in this recording " +
      "(findings/failures/), with what the AI judge, Claude Sonnet, said about it (preliminary, not checked by a person; a second AI judge, Qwen, is still running and not shown). The ones with a written explanation were read through by Claude (AI), from the text, for the website; the rest are the searches' raw finds."), host);
  } else {
    casesPanel.append(el("p", { class: "hint" }, "The four failure searches found nothing in this recording."));
  }

  // ---- the files behind it
  const fileList = el("ul", { class: "file-list" });
  for (const f of rec.files) {
    const where = el("span", {});
    if (f.path) where.append(LOCAL ? el("a", { href: `local/file?p=${encodeURIComponent(f.path)}`, target: "_blank" }, el("code", {}, f.path))
                                   : el("code", {}, f.path));
    if (f.url) where.append(f.path ? " " : "", el("a", { href: f.url, target: "_blank", rel: "noopener" }, f.path ? "(online)" : f.url));
    fileList.append(el("li", {}, el("span", {}, f.what), where));
  }
  const filesPanel = el("details", { class: "panel" }, el("summary", {}, "Every file behind it", el("small", {}, `${fileList.children.length}`)),
    el("p", { class: "hint" }, LOCAL ? "Click a path to open the file itself."
      : "Paths are on the 5090 laptop, where the runs and corpora live; the local copy of this page opens them. Its rows in the big tables are on the website's data page."),
    fileList);

  // ---- the transcript, block by block
  const transcript = el("div", { class: "transcript" });
  const drawn = new Map();
  const blocks = [];
  for (let k = 0; k < nBlocks; k++) {
    const b = el("section", { class: "block", id: `b-${k}`, "data-k": String(k) },
      el("h3", { class: "block-time" }, jumpButton(k * BLOCK, `${clock(k * BLOCK)} – ${clock(Math.min(duration, (k + 1) * BLOCK))}`)));
    blocks.push(b);
    transcript.append(b);
  }
  function drawBlock(k) {
    if (drawn.has(k)) return drawn.get(k);
    const box = el("div", { class: "compare" + (src ? "" : " plain") });
    const spans = [];
    for (const [li, l] of lines.entries()) {
      const text = el("div", { class: "compare-text" });
      const mine = [];
      l.buckets[k].forEach((i, n) => {
        // A new speaker starts a new line, as in a transcript.
        if (li === 0 && voices.at.has(i)) {
          const code = voices.at.get(i);
          text.append(n ? el("br") : "", el("span", { class: "spk", title: voices.title(code) }, voices.name.get(code)));
        }
        // Whisper splits a hyphenated word ("dope", "-themed"): no space between the pieces.
        else if (n && !(l.who === "Whisper" && /^-[\w$]/.test(l.words[i]))) text.append(" ");
        let cls = "word";
        if (li > 0 && l.off[i] === "1") cls += " off";
        if (li === 0 && l.missed[i] && l.missed[i] !== "0") cls += Number(l.missed[i]) >= engines.length ? " miss-all" : " miss";
        const mark = marks[li].get(i);
        if (mark) cls += ` case case-${mark.sec}`;
        const span = el("span", { class: cls, "data-l": String(li), "data-i": String(i), title: mark ? labelOf(mark) : null }, l.words[i]);
        text.append(span);
        mine.push([span, l.s[i], l.e[i]]);
      });
      if (!l.buckets[k].length) text.append(el("span", { class: "spk" }, "(nothing)"));
      const who = el("div", { class: "compare-who" }, l.who);
      who.style.setProperty("--who", `var(${COLOUR[l.who]})`);
      const lineEl = el("div", { class: "compare-line", "data-who": l.who }, who, text);
      if (hidden.has(l.who)) lineEl.hidden = true;
      box.append(lineEl);
      spans.push(mine);
    }
    blocks[k].append(box);
    blocks[k].classList.add("drawn");
    drawn.set(k, spans);
    return spans;
  }
  const keepClear = new ResizeObserver(() => transcript.style.setProperty("--player-h", `${player.offsetHeight}px`));
  keepClear.observe(player);
  const seen = new IntersectionObserver(entries => {
    for (const en of entries) if (en.isIntersecting) { drawBlock(Number(en.target.dataset.k)); seen.unobserve(en.target); }
  }, { rootMargin: "1200px 0px" });
  blocks.forEach(b => seen.observe(b));
  transcript.addEventListener("click", ev => {
    const w = ev.target.closest(".word");
    if (!w || !src) return;
    const l = lines[Number(w.dataset.l)], i = Number(w.dataset.i);
    jump(l.s[i], true);
  });

  // ---- moving about, and the word being spoken
  function jumpButton(t, label) {
    const b = el("button", { type: "button", class: "jump", title: src ? "Play from here" : "Go to this point" }, label || clock(t));
    b.addEventListener("click", () => jump(t, Boolean(src)));
    return b;
  }
  function jump(t, play) {
    t = Math.max(0, Math.min(duration, t));
    pos = t;
    const k = Math.min(nBlocks - 1, Math.floor(t / BLOCK));
    // Draw the blocks around it first: a block grows when it is drawn, and blocks
    // drawn above it after the jump would push it down out of view.
    for (let j = Math.max(0, k - 3); j <= Math.min(nBlocks - 1, k + 2); j++) drawBlock(j);
    blocks[k].scrollIntoView({ block: "start", behavior: "auto" });
    setTimeout(() => { if (audio.paused || !follow.checked) blocks[k].scrollIntoView({ block: "start", behavior: "auto" }); }, 350);
    if (src) {
      audio.currentTime = t;
      if (play) audio.play().catch(playFailed);
      show(t);
    } else drawStrip(t);
  }
  // Bring something to the middle of the screen that's left below the sticky player.
  // The player can cover half of a phone, so the screen's own middle may be behind it.
  function centre(node, behavior = "auto") {
    const r = node.getBoundingClientRect(), top = Math.max(0, player.getBoundingClientRect().bottom);
    window.scrollBy({ top: (r.top + r.bottom) / 2 - (top + innerHeight) / 2, behavior });
  }
  let lit = [], raf = null, lastScroll = 0, lastStrip = 0, litBlock = -1;
  let pos = 0;   // where the reader is, for a recording with no audio here
  function show(t) {
    lit.forEach(n => n.classList.remove("now"));
    lit = [];
    const k = Math.min(nBlocks - 1, Math.floor(t / BLOCK));
    const spans = drawBlock(k);
    for (const mine of spans) {
      let hit = null;
      for (const [span, s, e] of mine) if (t >= s && t < e + 0.12) hit = span;
      if (hit) { hit.classList.add("now"); lit.push(hit); }
    }
    time.textContent = `${clock(t)} / ${clock(duration)}`;
    if (!dragging) seek.value = String(Math.floor(t));
    const now = performance.now();
    if (now - lastStrip > 250) { drawStrip(t); lastStrip = now; }
    if (follow.checked && !audio.paused && now - lastScroll > 800) {
      const target = lit.find(n => !n.closest("[hidden]")) || blocks[k];
      const r = target.getBoundingClientRect(), top = player.getBoundingClientRect().bottom;
      if (r.top < top + 8 || r.bottom > innerHeight - 40 || k !== litBlock) {
        centre(target, matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
        lastScroll = now;
      }
      litBlock = k;
    }
  }
  function frame() {
    show(audio.currentTime);
    raf = audio.paused ? null : requestAnimationFrame(frame);
  }
  // The next or previous error from here, two seconds before it so it can be heard coming.
  function stepError(dir) {
    const now = src ? audio.currentTime : pos;
    const pool = casesSorted.filter(c => (errWhich.value === "all" || serious(c)) && !hidden.has(c.engine));
    const target = dir > 0 ? pool.find(c => c.s - 2 > now + 0.5) : [...pool].reverse().find(c => c.s - 2 < now - 1);
    if (!target) { status.textContent = dir > 0 ? "No more errors after this point." : "No errors before this point."; return; }
    status.textContent = "";
    jump(target.s - 2, Boolean(src) && !audio.paused);
    flash(target);
  }
  // Make the error's first word blink once, and bring it to the middle of the screen.
  function flash(c) {
    const k = Math.min(nBlocks - 1, Math.floor(c.s / BLOCK));
    drawBlock(k);
    const li = lineOf[c.engine];
    const n = [...blocks[k].querySelectorAll(`.word.case[data-l="${li}"]`)]
      .find(x => lines[li].s[Number(x.dataset.i)] >= c.s - 0.05);
    if (n) {
      n.classList.add("flash");
      setTimeout(() => n.classList.remove("flash"), 1600);
      centre(n);
      setTimeout(() => centre(n), 400);
    }
  }
  const onKey = ev => {
    if (ev.ctrlKey || ev.metaKey || ev.altKey || !ev.target.closest) return;
    // Only typing keeps every key. After a click on a tick box or a menu the keyboard
    // stays there, and the player's keys should still work; each control keeps just the
    // keys it needs. Space presses a button, opens a panel or ticks a box; a menu's
    // arrows change its choice. The slider's arrows move ten seconds, as everywhere.
    if (ev.target.closest("textarea, input:not([type=checkbox], [type=range])")) return;
    const menu = ev.target.closest("select");
    if (ev.key === " ") {
      if (src && !ev.target.closest("button, summary, a, select, input[type=checkbox]")) { ev.preventDefault(); playBtn.click(); }
    } else if (ev.key === "ArrowLeft" && src && !menu) { ev.preventDefault(); backBtn.click(); }
    else if (ev.key === "ArrowRight" && src && !menu) { ev.preventDefault(); fwdBtn.click(); }
    else if (ev.key === "j" || ev.key === "J") { ev.preventDefault(); stepError(-1); }
    else if (ev.key === "k" || ev.key === "K") { ev.preventDefault(); stepError(1); }
  };
  addEventListener("keydown", onKey);
  audio.addEventListener("seeked", () => show(audio.currentTime));
  leave = () => { audio.pause(); audio.removeAttribute("src"); seen.disconnect(); keepClear.disconnect(); if (raf) cancelAnimationFrame(raf);
                  removeEventListener("resize", onResize); removeEventListener("keydown", onKey);
                  removeEventListener("pointerup", letGo); removeEventListener("pointercancel", letGo); };
  const onResize = () => drawStrip();
  addEventListener("resize", onResize);

  view.replaceChildren(
    el("a", { class: "back", href: "#" }, "← All recordings"),
    el("p", { class: "crumb" }, `${META.names[row.c]} · ${partLabel(row.p)} · ${row.id}`),
    el("div", { class: "rec-head" }, el("h1", {}, row.title), row.sub ? el("p", { class: "sub" }, row.sub) : null, voices.key()),
    el("div", { class: "facts" },
      el("div", {}, el("b", {}, clock(duration)), "long"),
      el("div", {}, el("b", {}, lines[0].words.length.toLocaleString()), "words in the reference"),
      el("div", {}, el("b", {}, String(engines.length)), "engines"),
      el("div", {}, el("b", {}, String(cases.length)), "failure cases found")),
    scoreBox,
    el("p", { class: "source" }, "Error rates on the benchmark rule (case, punctuation and fillers ignored), as a share of the reference's words; from the website's recordings table."),
    player,
    el("div", { class: "strip-box" }, strip, stripKey),
    casesPanel, filesPanel,
    el("h2", {}, "The transcripts"),
    legend,
    el("p", { class: "legend" }, "The record first, then each engine, 30 seconds at a time. The bold solid colours are the errors the searches found, on the engine's words and on the record's; hover over one to see what it is. " +
      "Yellow on an engine's line is any other word that differs from the record. Yellow on the record's line is a word at least one engine got wrong, and bright yellow is one that every engine did. " +
      "A word an engine left out has nothing to highlight on that engine's line, so it shows on the record's line only. " +
      (src ? "Click any word to play from it; the word being spoken lights up." : "") +
      (row.c === "scotus" ? " The record has no times of its own: each of its words takes the time of the engine word it lines up with." : "")),
    transcript);
  requestAnimationFrame(() => drawStrip(0));
  if (at !== undefined && !isNaN(at)) requestAnimationFrame(() => jump(at, false));
}

// The first index of a sorted array whose value is at least v.
function lowerBound(a, v) {
  let lo = 0, hi = a.length;
  while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < v) lo = m + 1; else hi = m; }
  return lo;
}

function noAudioNote(row) {
  if (row.c === "earnings22") return "Earnings-22's audio has no stated licence, so it is not published here; the local copy on the laptop plays it.";
  if (row.c === "scotus" && row.ext) return el("span", {}, "This argument's audio did not fit on this page. ",
    el("a", { href: row.ext.audio, target: "_blank", rel: "noopener" }, "Listen on supremecourt.gov"),
    " or open the local copy on the laptop, where the words light up as it plays.");
  return "This recording's audio did not fit on this page; the local copy on the laptop plays it.";
}

// --- which view ---------------------------------------------------------------------------

let routes = 0;   // counts the views asked for, so a slow one can tell it was left behind
function route() {
  leave();
  leave = () => {};
  routes++;
  const h = hashNow();
  if (h) showRecording(h.c, h.id, h.at, routes);
  else showPicker();
  window.scrollTo(0, 0);
}

footer();
nav("picker");
view.replaceChildren(el("p", { class: "loading" }, "Loading the list of recordings…"));
fetchJSON("catalog.json").then(c => {
  catalog = c;
  addEventListener("hashchange", route);
  route();
}).catch(e => {
  view.replaceChildren(el("p", { class: "problem" }, "The list of recordings didn't load: " + e.message));
});

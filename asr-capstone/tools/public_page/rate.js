// The rating page: a queue of clips, the listening bench's questions
// (labelling-guidelines.md, version 0.2), and the answers saved per person per case
// through Backend (backend.js). The AI judge's labels are in a separate file,
// fetched only after the person has answered, so the rating is blind to them.
//
// rate/cases.json (tools/build_public.py):
//   {cases: [{id, c, where, eng, rec: [before, mark, after], hyp: [...], clip, views, view, whole}],
//    serious: [ids], all: [ids]}     both lists in a fixed shuffled order
// rate/judge.json: {id: {meaning, severity, reason, kind, subkind}}

const NAMES = { scotus: "Supreme Court", edacc: "EdAcc", coraal: "CORAAL" };
// The eight questions and the two extras, worded as in labelling-guidelines.md.
const FEATURE_TEXT = [
  ["overlap", "Overlap or hand-over", "Someone else is speaking during the highlighted words, or a new speaker starts inside them or on the word right next to them."],
  ["stumble", "Stumble", "A repeated word (\"I -- I think\"), a restart, a word cut off partway, or a filler that is part of a stumble (uh, um, you know, I mean)."],
  ["name", "Name or legal term", "A person, place, case name, statute name or legal term of art is involved."],
  ["number", "Number or citation", "A number, date, statute, section or subsection is involved."],
  ["written", "Same words, written differently", "Read aloud, both would sound the same; only spelling, spacing, hyphens, an abbreviation or punctuation differ."],
  ["soundalike", "Sound-alike", "The words differ but sound alike or nearly alike: relief and belief, \"him to\" and \"into\"."],
  ["small", "Small word or ending", "The difference is in a short common word (a, the, is, of, to, can) or a word ending (-s, -ed, -ing, 's)."],
  ["oneside", "Words on one side only", "At least one whole word on one side has nothing matching it on the other."],
  ["none", "None of these", "You looked, and none of the eight is true."],
  ["cant_tell", "Can't tell", "The audio isn't enough to answer."],
];
const WHO_TEXT = [
  ["record", "The record", "What you hear matches the record."],
  ["engine", "The engine", "What you hear matches what the engine wrote."],
  ["both", "Both reasonable", "Both are fair ways to write what was said."],
  ["neither", "Neither", "What you hear matches neither."],
  ["cant_tell", "Can't tell", "The audio isn't clear enough to say."],
];
const RECORD_TEXT = [["yes", "Yes", ""], ["no", "No", ""], ["unsure", "Not sure", ""]];
const MEANING = { opposite: "says the opposite", changed: "changes the meaning", reworded: "says the same thing in other words",
                  same: "means the same", garbled: "garbled, no clear meaning" };
const KIND = { meaning: "a meaning change", invented: "words added where nobody spoke", edits: "an edit of how the speaker talks", skips: "speech left out" };

const store = {
  get(k, d) { try { const v = localStorage.getItem("rate." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("rate." + k, JSON.stringify(v)); } catch { /* private window */ } },
};

let data = null, byId = {}, judge = null;
let user = null, mine = new Map(), counts = {}, open = false;
let current = null, played = new Set(), cameFrom = "queue";
let mode = store.get("mode", "serious"), corpusPick = store.get("corpus", "all");

function choices(root, name, list, type) {
  list.forEach(([key, label, help]) => {
    const input = el("input", { type, name, value: key, "data-q": key });
    root.append(el("label", {}, input, el("span", {}, label, help ? el("small", {}, help) : "")));
  });
}
choices($("#features"), "features", FEATURE_TEXT, "checkbox");
choices($("#who"), "who", WHO_TEXT, "radio");
choices($("#record"), "record", RECORD_TEXT, "radio");
$("#contrib").textContent = window.CONTRIBUTOR_LINE;

// "None" and "Can't tell" stand alone; "written" and "sound-alike" never go together.
$("#features").addEventListener("change", e => {
  const k = e.target.value;
  if (!e.target.checked) return;
  const boxes = [...$("#features").querySelectorAll("input")];
  const off = k === "none" || k === "cant_tell" ? boxes.filter(b => b.value !== k)
    : boxes.filter(b => b.value === "none" || b.value === "cant_tell" || (k === "written" && b.value === "soundalike") || (k === "soundalike" && b.value === "written"));
  off.forEach(b => { b.checked = false; });
});

const MODES = [["serious", "Likely serious first"], ["random", "Random"], ["fewest", "Fewest ratings first"]];
if (!MODES.some(([k]) => k === mode)) mode = "serious";
switchOf($("#modes"), MODES, mode, k => { mode = k; store.set("mode", k); next(); });
$("#corpus").value = corpusPick;
$("#corpus").addEventListener("change", () => { corpusPick = $("#corpus").value; store.set("corpus", corpusPick); next(); });
$("#skip").addEventListener("click", () => next());

function say(text, cls = "") { const s = $("#say"); s.textContent = text; s.className = "say " + cls; }

// ---- which clip next ------------------------------------------------------------
function next() {
  if (!data) return;
  const list = (mode === "serious" ? data.serious : data.all)
    .filter(id => (corpusPick === "all" || byId[id].c === corpusPick) && !mine.has(id) && (!current || id !== current.id));
  let pick = list[0];
  if (mode === "random") pick = list[Math.floor(Math.random() * list.length)];
  if (mode === "fewest") pick = list.reduce((best, id) => (counts[id] || 0) < (counts[best] || 0) ? id : best, list[0]);
  $("#queue-note").textContent = `${list.length.toLocaleString()} clips left in this queue for you.`;
  if (!pick) { $("#case").replaceChildren(el("p", { class: "notice" }, "You have rated every clip in this queue. Thank you! Try another queue or data set.")); return; }
  show(pick, "queue");
  history.replaceState(null, "", `#case=${pick}`);
}

// ---- one clip ---------------------------------------------------------------------
function show(id, from) {
  const c = byId[id];
  $("#judge").hidden = true;
  say("");
  if (!c) {
    current = null;
    $("#case").replaceChildren(el("p", { class: "notice" }, `Case ${id} isn't in the rating queue: it has no audio that may be shared here.`));
    $("#questions").hidden = true;
    return;
  }
  $("#questions").hidden = false;
  // Drawn again for the same clip (after signing in, say): keep what was played.
  if (!current || current.id !== id) played = new Set();
  current = c;
  cameFrom = from;
  const card = el("article", { class: "failure-card" });
  card.append(el("p", { class: "card-kind" }, `${NAMES[c.c]} · case ${c.id}`),
    el("h3", {}, "What do you hear at the highlighted words?"),
    el("p", { class: "card-where" }, c.where));
  const player = Listen.create(card, { clip: c.clip, views: c.views, view: c.view,
    onPlayed: key => { played.add(key === "word" ? "word" : key); } });
  card.append(player.controls("Hear"), Compare.lines(player, [
    { who: "Record", before: c.rec[0], mark: c.rec[1], after: c.rec[2] },
    { who: c.eng, before: c.hyp[0], mark: c.hyp[1], after: c.hyp[2] },
  ], { key: false }));
  const foot = el("p", { class: "card-heard" }, "The highlighted words are what to rate; the rest is there to help.");
  if (c.whole) foot.append(" ", el("a", { href: c.whole, target: "_blank", rel: "noopener" }, "Open it in the whole recording"));
  card.append(foot);
  $("#case").replaceChildren(card);
  $("#correct-hint").textContent = c.c === "coraal"
    ? "Type the highlighted words as you hear them. CORAAL bleeps names and places: leave those out, and don't try to fill them in."
    : "Type the highlighted words as you hear them.";
  fill(mine.get(id));
  if (mine.has(id)) revealJudge();
}

function fill(r) {
  $("#questions").querySelectorAll("input").forEach(i => { i.checked = false; });
  $("#corrected").value = r ? r.corrected : "";
  $("#feedback").value = r ? r.feedback : "";
  if (!r) return;
  r.features.forEach(f => { const i = $(`#features input[value="${f}"]`); if (i) i.checked = true; });
  const w = $(`#who input[value="${r.who_right}"]`); if (w) w.checked = true;
  const k = $(`#record input[value="${r.record_right}"]`); if (k) k.checked = true;
  say(`You rated this clip on ${new Date(r.updated).toLocaleDateString()}. Change anything and save again.`);
}

function answer() {
  const picked = name => { const i = $(`#questions input[name="${name}"]:checked`); return i ? i.value : ""; };
  return {
    features: [...$("#features").querySelectorAll("input:checked")].map(i => i.value),
    who_right: picked("who"), record_right: picked("record"),
    corrected: $("#corrected").value.trim(), feedback: $("#feedback").value.trim(),
    played: [...played].slice(0, 3), came_from: cameFrom,
  };
}

async function save(goOn) {
  if (!current) return;
  const a = answer();
  if (!a.features.length) return say("Please tick at least one box under the first question (or \"None of these\").", "bad");
  if (!a.who_right) return say("Please say who got it right.", "bad");
  if (!a.record_right) return say("Please say whether the record is right here.", "bad");
  if (!user) return say("Please sign in to save your answers.", "bad");
  const c = current;
  $("#save").disabled = $("#save-next").disabled = true;
  say("Saving…");
  try {
    const got = await Backend.saveRating(c.id, c.c, a);
    mine.set(c.id, { ...a, case: c.id, corpus: c.c, updated: new Date().toISOString() });
    if (got.created) counts[c.id] = (counts[c.id] || 0) + 1;
    drawMine();
    say(got.created ? "Saved. Thank you!" : "Your changes are saved.", "good");
    if (goOn) next(); else revealJudge();
  } catch (e) {
    say(e.message, "bad");
  } finally {
    $("#save").disabled = $("#save-next").disabled = false;
  }
}
$("#questions").addEventListener("submit", e => { e.preventDefault(); save(true); });
$("#save").addEventListener("click", () => save(false));

// After answering: what the AI judge said, and what the rules found.
async function revealJudge() {
  const c = current;
  try { judge = judge || await fetch("rate/judge.json").then(r => r.json()); } catch (e) { return; }
  const j = judge[c.id];
  if (!j || current !== c) return;
  const box = $("#judge");
  box.replaceChildren(el("b", {}, "What the AI judge (Claude Sonnet) said, now that you have answered: "),
    `${MEANING[j.meaning] || j.meaning || "no answer"}, severity ${j.severity} of 4. `, el("q", {}, j.reason),
    el("br"), `The rules found it as ${KIND[j.kind] || j.kind}${j.subkind ? ` (${j.subkind.replace(/_/g, " ")})` : ""}. Neither has been checked by ear, so your answer counts.`);
  box.hidden = false;
}

// ---- who is here ------------------------------------------------------------------
function drawMine() {
  const ul = $("#mine");
  const rows = [...mine.values()].sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
  ul.replaceChildren(...rows.map(r => el("li", {},
    el("a", { href: `#case=${r.case}&from=mine` }, `Case ${r.case}`),
    ` · ${byId[r.case] ? byId[r.case].where : NAMES[r.corpus] || ""} · ${new Date(r.updated).toLocaleDateString()}`)));
  if (!rows.length) ul.append(el("li", {}, user ? "None yet." : "Sign in to see the clips you have rated."));
}

function drawWho() {
  const note = $("#who-note"), gate = $("#gate"), link = $("#signin-to-save");
  const here = encodeURIComponent("rate.html" + location.hash);
  note.hidden = false;
  link.hidden = true;
  if (Backend.mode === "off") {
    note.textContent = "Accounts are not switched on yet, so answers can't be saved. You can still listen.";
  } else if (!user) {
    note.replaceChildren("You can listen without an account. To save answers, ", el("a", { href: `account.html?next=${here}` }, "sign in or make an account"), ".");
    link.hidden = false;
    link.href = `account.html?next=${here}`;
    link.textContent = "Sign in to save";
  } else if (!user.verified) {
    note.replaceChildren("Please confirm your email address before saving: use the link in the email we sent. ", el("a", { href: "account.html" }, "Your account"), ".");
  } else {
    note.hidden = true;
  }
  gate.hidden = open || Backend.mode === "off";
  gate.textContent = "Saving ratings is open only to invited testers for now, while CUNY's research office reviews the study. If you are not one, your answers won't be saved yet; you can still listen and look around.";
}

function route() {
  const m = location.hash.match(/case=([a-z0-9]+)(?:&from=([a-z]+))?/);
  if (!m) return next();
  show(m[1], ["card", "data", "mine"].includes(m[2]) ? m[2] : "link");
}

siteNav($("#nav"), D.pages, "rate.html");
fetch("rate/cases.json").then(r => r.json()).then(got => {
  data = got;
  byId = Object.fromEntries(got.cases.map(c => [c.id, c]));
  route();
  addEventListener("hashchange", route);
  drawMine();
}).catch(e => { $("#case").textContent = `The clips didn't load (${e.message}).`; });

Backend.onUser(async u => {
  user = u;
  mine = new Map();
  counts = {};
  open = await Backend.isOpen().catch(() => false);
  if (u) {
    try { (await Backend.myRatings()).forEach(r => mine.set(r.case, r)); } catch (e) { say(e.message, "bad"); }
    try { counts = await Backend.counts(); } catch (e) { counts = {}; }
  }
  drawWho();
  drawMine();
  if (current && data) show(current.id, cameFrom);
});

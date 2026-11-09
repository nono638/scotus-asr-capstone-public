// Listen: play a clip at a choice of lengths, with each word highlighted as it is
// spoken. Written once here and inlined by every page that plays audio (the
// listening bench, the website), so it works the same everywhere.
//
//   const p = Listen.create(card, {
//     clip: "clips/x.mp3",
//     views: [{key: "short", label: "16 seconds", from: 7.5, to: 23.5, note: ""}, ...],
//     view: "short",                     // the one in use to begin with
//     onPlayed: key => {},               // a view, or "word" for a clicked word
//     onStatus: (text, cls) => {},       // a clip that will not load or play
//   });
//   card.append(p.controls());           // the buttons
//   line.append(...p.words({t: "...", w: [[word, start, end, off], ...]}));
//
// Times are seconds from the start of the clip. A word with a fourth item of 1
// differs from the record and is highlighted; 2 marks the
// record's words the card is about. Only the words inside the view in use are
// shown, so choosing a longer view shows more of the text. With no clip (audio
// that may not be shared) the buttons only change how much text is shown.
// One audio element serves the whole page; starting one player stops the others.

const Listen = (() => {
  const audio = document.createElement("audio");
  audio.preload = "auto";
  document.body.append(audio);
  let active = null;
  let frame = null;

  const clean = s => (s || "").split(/\s+/).filter(Boolean).join(" ");
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }

  function create(root, opts) {
    const p = {
      root, opts,
      view: opts.view || (opts.views[0] && opts.views[0].key),
      stopAt: null,
      timed: [],
      buttons: {},
      playing: null,
      status: null,
    };
    root.dataset.view = p.view;

    // `label` is text or an element (the bench adds its keyboard keys to it).
    p.controls = (label = "Play") => {
      const box = el("div", { class: "listen-controls", role: "group", "aria-label": typeof label === "string" ? label : "Play" });
      if (label) box.append(el("span", { class: "label" }, label));
      for (const v of opts.views) {
        const b = el("button", { class: "btn", type: "button", "data-play": v.key, "aria-pressed": String(v.key === p.view) },
          v.label, el("small", {}, v.note || ""));
        // The length that is playing stops when pressed again.
        b.addEventListener("click", () => {
          if (active === p && p.view === v.key && !audio.paused) stop();
          else p.play(v.key);
        });
        p.buttons[v.key] = b;
        box.append(b);
      }
      p.playing = el("span", { class: "playing", "aria-live": "polite" });
      p.status = el("span", { class: "listen-status", role: "status" });
      box.append(p.playing, p.status);
      return box;
    };

    // One span per word, with its time in the clip; plain text where there are
    // no times or they don't cover every word (the record has none).
    p.words = seg => {
      const text = clean(seg.t !== undefined ? seg.t : (seg.w || []).map(w => w[0]).join(" "));
      if (!seg.w || seg.w.length !== text.split(" ").length) return [text];
      const out = [];
      seg.w.forEach(([word, s, e, off], i) => {
        const span = el("span", { class: "word" + (off === 1 ? " off" : off === 2 ? " passage" : ""), "data-s": s, "data-e": e }, word);
        if (outside(s)) span.classList.add("outside");
        span.addEventListener("click", () => p.playFrom(s));
        if (i) out.push(" ");
        out.push(span);
      });
      return out;
    };

    // Whether a word at clip time s falls outside the view in use.
    const outside = s => {
      const v = opts.views.find(x => x.key === p.view);
      return v ? (s < v.from - 0.05 || s >= v.to) : false;
    };
    p.fit = () => root.querySelectorAll(".word[data-s]").forEach(n => n.classList.toggle("outside", outside(Number(n.dataset.s))));

    p.setNote = (key, text) => {
      const small = p.buttons[key] && p.buttons[key].querySelector("small");
      if (small) small.textContent = text;
    };

    p.play = key => {
      const v = opts.views.find(x => x.key === key);
      if (!v) return;
      p.view = key;
      root.dataset.view = key;
      Object.entries(p.buttons).forEach(([k, b]) => b.setAttribute("aria-pressed", String(k === key)));
      p.fit();
      if (opts.clip) start(p, v.from, v.to);
      if (opts.onPlayed) opts.onPlayed(key);
    };

    // Clicking a word plays from it to the end of the view in use.
    p.playFrom = t => {
      if (!opts.clip) return;
      const v = opts.views.find(x => x.key === p.view) || opts.views[0];
      start(p, t, Math.max(v.to, t + 3));
      if (opts.onPlayed) opts.onPlayed("word");
    };
    return p;
  }

  function say(p, text, cls) {
    if (p.opts.onStatus) p.opts.onStatus(text, cls);
    else if (p.status) p.status.textContent = text;
  }

  // play() is called right away, inside the click: some browsers refuse it once
  // the page has waited for the file to load first. Setting the time before the
  // file loads is allowed; the browser jumps there as soon as it can.
  function start(p, from, to) {
    if (active && active !== p) clear(active);
    active = p;
    p.timed = [...p.root.querySelectorAll(".word")].map(n => [n, Number(n.dataset.s), Number(n.dataset.e)]);
    if (p.status) p.status.textContent = "";
    if (!audio.src.endsWith(p.opts.clip)) audio.src = p.opts.clip;
    audio.currentTime = from;
    p.stopAt = to;
    audio.play().catch(e => {
      // Moving on mid-load interrupts play(); that isn't a failure.
      if (e.name !== "AbortError") say(p, "The clip didn't play (" + e.name + ": " + e.message + ").", "bad");
    });
  }

  function clear(p) {
    p.timed.forEach(([n]) => n.classList.remove("now"));
    if (p.playing) p.playing.textContent = "";
  }

  function tick() {
    if (!active) { frame = null; return; }
    // Paused since the last frame: one more pass would light a word again and leave it.
    if (audio.paused) { clear(active); frame = null; return; }
    const t = audio.currentTime;
    // A short grace after each word's end keeps the highlight from flickering
    // off in the small gaps between words.
    for (const [n, s, e] of active.timed) n.classList.toggle("now", t >= s && t < e + 0.12);
    frame = requestAnimationFrame(tick);
  }

  audio.addEventListener("error", () => {
    if (!active) return;
    const why = { 1: "loading was stopped", 2: "network error", 3: "the file couldn't be decoded", 4: "the file wasn't found or isn't allowed here" };
    say(active, "The clip didn't load: " + (why[audio.error && audio.error.code] || "unknown error") + ". Tried " + audio.src, "bad");
  });
  audio.addEventListener("timeupdate", () => {
    if (active && active.stopAt !== null && audio.currentTime >= active.stopAt) { audio.pause(); active.stopAt = null; }
  });
  audio.addEventListener("play", () => {
    if (active && active.playing) active.playing.textContent = "playing… press again to stop";
    if (!frame) frame = requestAnimationFrame(tick);
  });
  audio.addEventListener("pause", () => { if (active) clear(active); });

  function stop() {
    audio.pause();
    if (active) { active.stopAt = null; clear(active); }
  }

  return { create, stop, audio, get active() { return active; } };
})();

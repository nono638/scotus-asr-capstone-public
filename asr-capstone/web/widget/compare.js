// Compare: the record's words beside one or more engines', marked the same way on
// every page. Pairs with Listen: engine words carry times, so they light up as
// the clip plays, and a word that differs from the record is highlighted.
//
//   card.append(Compare.lines(player, [
//     {who: "Record", before: "...", mark: "the passage", after: "..."},
//     {who: "Qwen3", w: [[word, start, end, off], ...]},
//   ]));

const Compare = (() => {
  const COLOUR = { Record: "--record", Qwen3: "--qwen3", Whisper: "--whisper", Parakeet: "--parakeet",
                   Canary: "--canary", Granite: "--granite" };

  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }

  function line(player, row) {
    const text = el("div", { class: "compare-text" });
    if (row.mark !== undefined) {
      if (row.before) text.append(el("span", { class: "ctx" }, row.before), " ");
      text.append(el("mark", {}, row.mark || "(nothing)"));
      if (row.after) text.append(" ", el("span", { class: "ctx" }, row.after));
    } else if (player && row.w) {
      text.append(...player.words(row));
    } else if (row.w) {
      // No clip (audio that may not be shared): the words alone, still marked.
      row.w.forEach(([word, , , off], i) => {
        if (i) text.append(" ");
        text.append(el("span", { class: "word" + (off ? " off" : "") }, word));
      });
    } else {
      text.append(row.t || "");
    }
    const colour = COLOUR[row.who];
    const who = el("div", { class: "compare-who" }, row.label || row.who);
    if (colour) who.style.setProperty("--who", "var(" + colour + ")");
    return el("div", { class: "compare-line" }, who, text);
  }

  function lines(player, rows, { key = true } = {}) {
    const box = el("div", { class: "compare" });
    rows.forEach(row => box.append(line(player, row)));
    if (!key) return box;
    return el("div", {}, box, el("p", { class: "compare-key" },
      "The word being spoken lights up as the clip plays; click a word to play from it. " +
      "A yellow highlight marks an engine's word that differs from the record."));
  }

  return { lines, line };
})();

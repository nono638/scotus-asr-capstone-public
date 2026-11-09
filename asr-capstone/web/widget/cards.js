// Cards: one failure to hear, drawn the same way on every page. Uses Listen and
// Compare, so load those first.
//
//   Cards.failure(grid, {
//     kindLabel: "Says the opposite", title: "Whisper dropped the “not”",
//     where: "Rochester interview ROC_se0_ag1_f_01_1, 12:03 in",
//     explanation: "One plain sentence.", heard: false,
//     notes: ["Rule: a “not” lost", "Sonnet: opposite, severity 4"],
//     clip: "clips/failures/coraal/meaning-....mp3",     // null: no audio, text only
//     views: [{key: "short", label: "16 seconds", from, to}, {key: "long", label: "31 seconds", from, to}],
//     view: "short",
//     lines: [{who: "Record", w: [[word, start, end, 2], ...]}, {who: "Whisper", w: [[word, start, end, off], ...]}],
//     hear: "https://...#rec=...&t=723",                 // optional: the whole recording
//   });
//
// Each card is an <article class="failure-card">; the page lays out the grid.

const Cards = (() => {
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }

  function failure(grid, c) {
    const card = el("article", { class: "failure-card", "data-kind": c.kind || "" });
    card.append(
      el("p", { class: "card-kind" }, c.kindLabel || ""),
      el("h3", {}, c.title),
      el("p", { class: "card-where" }, c.where || ""),
      el("p", { class: "card-note" }, c.explanation || ""));
    const player = Listen.create(card, { clip: c.clip || null, views: c.views, view: c.view });
    card.append(player.controls(c.clip ? "Hear" : "Show"), Compare.lines(player, c.lines, { key: false }));
    player.fit();
    const foot = el("p", { class: "card-heard" });
    if (c.notes && c.notes.length) foot.append(c.notes.join(" · "), el("br"));
    foot.append(c.heard ? "Checked by ear." : "Not yet checked by ear.");
    if (c.hear) foot.append(" ", el("a", { href: c.hear, target: "_blank", rel: "noopener" }, "Open it in the whole recording"));
    card.append(foot);
    grid.append(card);
    return card;
  }

  return { failure };
})();

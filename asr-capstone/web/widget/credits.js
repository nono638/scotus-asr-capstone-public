// Credits: who made the audio and transcripts on a page, under what licence, and what
// was changed. Written once here and inlined by every page that shows them, from
// CREDITS in tools/build_site.py.
//
//   Credits.list(root, [{name, uses, licence, licenceUrl, source: [label, url], changed,
//                        cite: [...], more: [...]}]);

const Credits = (() => {
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }

  function one(c) {
    const licence = c.licenceUrl ? el("a", { href: c.licenceUrl, target: "_blank", rel: "noopener" }, c.licence) : c.licence;
    const box = el("div", { class: "credit-one" }, el("h3", {}, c.name),
      el("p", {}, `${c.uses} Licence: `, licence, ". ", el("a", { href: c.source[1], target: "_blank", rel: "noopener" }, c.source[0]), "."));
    if (c.changed) box.append(el("p", {}, c.changed));
    box.append(el("ul", {}, ...c.cite.map(t => el("li", {}, t))));
    if (c.more && c.more.length) {
      box.append(el("details", {}, el("summary", {}, `The citations for each part (${c.more.length})`),
        el("ul", {}, ...c.more.map(t => el("li", {}, t)))));
    }
    return box;
  }

  function list(root, items) {
    root.append(el("div", { class: "credit-list" }, ...items.map(one)));
  }

  return { list };
})();

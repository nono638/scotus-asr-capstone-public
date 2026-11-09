// Table: scores with sortable columns. Click a heading to sort by it, again to
// reverse. A row can carry an action (a button that plays it, say).
//
//   Table.sortable(root, {
//     columns: [{key: "engine", label: "Engine"}, {key: "rate", label: "Error rate", num: true, fmt: v => v + "%"}],
//     rows: [{engine: "Qwen3", rate: 4.44}, ...],
//     sort: {key: "rate", dir: 1},
//     onSort: sort => {},                // told when the reader sorts, to remember it
//     rowClass: row => "",
//     caption: "...",
//   });

const Table = (() => {
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }

  function sortable(root, opts) {
    let sort = opts.sort || null;
    const table = el("table", { class: "sortable" });
    if (opts.caption) table.append(el("caption", { class: "sr-only" }, opts.caption));
    const head = el("tr");
    const body = el("tbody");
    table.append(el("thead", {}, head), body);

    function draw() {
      head.textContent = "";
      opts.columns.forEach((c, at) => {
        const th = el("th", { scope: "col", class: c.num ? "num" : "" });
        if (sort && sort.key === c.key) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
        if (c.sort === false) th.append(c.label);
        else {
          const b = el("button", { type: "button" }, c.label);
          b.addEventListener("click", () => {
            sort = { key: c.key, dir: sort && sort.key === c.key ? -sort.dir : (c.num ? 1 : 1) };
            draw();
            if (opts.onSort) opts.onSort(sort);
            // The headings were drawn again, so the button that had the keyboard is gone.
            head.children[at].querySelector("button").focus();
          });
          th.append(b);
        }
        head.append(th);
      });
      const rows = [...opts.rows];
      if (sort) {
        rows.sort((a, b) => {
          const x = a[sort.key], y = b[sort.key];
          if (x === y) return 0;
          if (x === null || x === undefined) return 1;
          if (y === null || y === undefined) return -1;
          return (x < y ? -1 : 1) * sort.dir;
        });
      }
      body.textContent = "";
      for (const r of rows) {
        const tr = el("tr", { class: opts.rowClass ? opts.rowClass(r) : "" });
        for (const c of opts.columns) {
          const v = r[c.key];
          const td = el("td", { class: c.num ? "num" : "" });
          const shown = c.fmt ? c.fmt(v, r) : (v === null || v === undefined ? "" : v);
          td.append(shown);
          tr.append(td);
        }
        body.append(tr);
      }
    }
    draw();
    root.append(el("div", { class: "table-wrap" }, table));
    return { redraw: draw, table };
  }

  return { sortable };
})();

// Chart: interactive charts drawn by hand in SVG and HTML (no library to load).
//
// Chart.scatter - one dot per item, x against y, with a diagonal. The modes are
// alternative values for every dot (the scoring rules); switching mode slides the
// dots to their new places. Hover or focus a dot to see what it is; click to pick it.
//
//   const fig = Chart.scatter(root, {
//     points: [{id, group, x: {benchmark: 5.7, verbatim: 14.5}, y: {...}}],
//     mode: "benchmark", groups: {OT2010: "var(--k-overlap)"},
//     xLabel: "Whisper error rate (%)", yLabel: "Qwen3 error rate (%)",
//     below: "Qwen3 better", above: "Whisper better",
//     tip: p => "text", label: p => "accessible name", onPick: p => {},
//   });
//   fig.setMode("verbatim"); fig.filter(p => p.group === "OT2021"); fig.pick(id);
//
// Chart.bars - one horizontal bar per row on a log scale from 1, with a 95%
// interval; the modes switch every bar at once (the terms of the error model).
//
//   const bars = Chart.bars(root, {rows: [{key, label}], mode, value: (row, mode) => ({v, lo, hi}), tip});
//   bars.setMode("OT2021");

const Chart = (() => {
  const NS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs = {}, ...kids) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  }
  function niceTicks(lo, hi, n = 5) {
    const step0 = (hi - lo) / n;
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
    const out = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(6));
    return out;
  }

  function tipBox(root) {
    const tip = el("div", { class: "chart-tip", hidden: "" });
    root.append(tip);
    return {
      show(html, x, y) {
        tip.innerHTML = html;
        tip.hidden = false;
        const w = root.clientWidth, tw = tip.offsetWidth;
        tip.style.left = Math.min(Math.max(0, x + 12), w - tw) + "px";
        tip.style.top = (y + 12) + "px";
      },
      hide() { tip.hidden = true; },
    };
  }

  function scatter(root, o) {
    const W = 560, H = 560, M = { l: 54, r: 16, t: 16, b: 46 };
    root.classList.add("chart");
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.ariaLabel || "" });
    const axisX = svg("g", { class: "axis" }), axisY = svg("g", { class: "axis" });
    const diag = svg("line", { class: "diagonal" });
    const below = svg("text", { class: "zone", "text-anchor": "end" });
    const above = svg("text", { class: "zone" });
    const dots = svg("g");
    plot.append(axisX, axisY, diag, below, above, dots,
      svg("text", { class: "axis-label", x: (M.l + W - M.r) / 2, y: H - 6, "text-anchor": "middle", fill: "var(--muted)", "font-size": 13 }, o.xLabel),
      svg("text", { class: "axis-label", transform: `translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`, "text-anchor": "middle", fill: "var(--muted)", "font-size": 13 }, o.yLabel));
    root.append(plot);
    const tip = tipBox(root);
    let mode = o.mode, keep = () => true, picked = null;
    const nodes = new Map();

    o.points.forEach(p => {
      const g = svg("g", { class: "dot", tabindex: "-1", role: "button", "aria-label": o.label ? o.label(p) : p.id });
      g.append(svg("circle", { r: 5, fill: o.groups[p.group] || "var(--accent)", "fill-opacity": 0.78 }));
      const show = e => {
        const r = root.getBoundingClientRect();
        tip.show(o.tip(p, mode), e.clientX - r.left, e.clientY - r.top);
      };
      g.addEventListener("mouseenter", show);
      g.addEventListener("mousemove", show);
      g.addEventListener("mouseleave", () => tip.hide());
      g.addEventListener("click", () => pick(p.id));
      g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(p.id); } });
      dots.append(g);
      nodes.set(p.id, [g, p]);
    });

    function scale() {
      const shown = o.points.filter(keep);
      const all = (shown.length ? shown : o.points).flatMap(p => [p.x[mode], p.y[mode]]);
      let lo = Math.min(...all), hi = Math.max(...all);
      const pad = (hi - lo) * 0.06 || 1;
      lo = Math.max(0, lo - pad); hi = hi + pad;
      const sx = v => M.l + (v - lo) / (hi - lo) * (W - M.l - M.r);
      const sy = v => H - M.b - (v - lo) / (hi - lo) * (H - M.t - M.b);
      return { lo, hi, sx, sy };
    }

    function draw() {
      const { lo, hi, sx, sy } = scale();
      axisX.textContent = ""; axisY.textContent = "";
      for (const t of niceTicks(lo, hi)) {
        axisX.append(svg("line", { x1: sx(t), x2: sx(t), y1: H - M.b, y2: H - M.b + 5 }),
          svg("text", { x: sx(t), y: H - M.b + 19, "text-anchor": "middle" }, t + ""));
        axisY.append(svg("line", { x1: M.l - 5, x2: M.l, y1: sy(t), y2: sy(t) }),
          svg("text", { x: M.l - 8, y: sy(t) + 4, "text-anchor": "end" }, t + ""));
      }
      axisX.append(svg("line", { x1: M.l, x2: W - M.r, y1: H - M.b, y2: H - M.b }));
      axisY.append(svg("line", { x1: M.l, x2: M.l, y1: M.t, y2: H - M.b }));
      diag.setAttribute("x1", sx(lo)); diag.setAttribute("y1", sy(lo));
      diag.setAttribute("x2", sx(hi)); diag.setAttribute("y2", sy(hi));
      below.setAttribute("x", W - M.r - 6); below.setAttribute("y", H - M.b - 10); below.textContent = o.below || "";
      above.setAttribute("x", M.l + 8); above.setAttribute("y", M.t + 14); above.textContent = o.above || "";
      for (const [g, p] of nodes.values()) {
        g.style.transform = `translate(${sx(p.x[mode]).toFixed(1)}px, ${sy(p.y[mode]).toFixed(1)}px)`;
        g.classList.toggle("hidden", !keep(p));
        g.setAttribute("tabindex", keep(p) ? "0" : "-1");
      }
    }

    function pick(id) {
      if (picked) { const n = nodes.get(picked); if (n) n[0].classList.remove("picked"); }
      picked = id;
      const n = nodes.get(id);
      if (!n) return;
      n[0].classList.add("picked");
      if (o.onPick) o.onPick(n[1]);
    }

    draw();
    return {
      setMode(m) { mode = m; tip.hide(); draw(); },
      filter(fn) { keep = fn || (() => true); tip.hide(); draw(); },
      pick,
      get mode() { return mode; },
      count(fn) { return o.points.filter(p => keep(p) && fn(p, mode)).length; },
      shown() { return o.points.filter(keep).length; },
    };
  }

  function bars(root, o) {
    root.classList.add("chart", "bars");
    let mode = o.mode;
    const max = o.max || 20;
    const pos = v => Math.log(Math.max(v, 1)) / Math.log(max) * 100;
    const tip = tipBox(root);
    const list = el("div", { class: "bar-list", role: "list" });
    const rows = o.rows.map(r => {
      const bar = el("div", { class: "bar-fill" });
      const ci = el("div", { class: "bar-ci" });
      const value = el("span", { class: "bar-value" });
      const track = el("div", { class: "bar-track" }, bar, ci);
      const row = el("div", { class: "bar-row", role: "listitem", tabindex: "0" },
        el("span", { class: "bar-label" }, r.label), track, value);
      const show = e => {
        const box = root.getBoundingClientRect();
        const at = e.clientX ? [e.clientX - box.left, e.clientY - box.top] : [row.offsetLeft + 40, row.offsetTop + 10];
        tip.show(o.tip(r, mode), at[0], at[1]);
      };
      row.addEventListener("mouseenter", show);
      row.addEventListener("mousemove", show);
      row.addEventListener("focus", show);
      row.addEventListener("mouseleave", () => tip.hide());
      row.addEventListener("blur", () => tip.hide());
      list.append(row);
      return { r, bar, ci, value };
    });
    const scaleRow = el("div", { class: "bar-row bar-scale", "aria-hidden": "true" }, el("span", { class: "bar-label" }, ""),
      el("div", { class: "bar-track" }, ...[1, 2, 5, 10, 20].filter(t => t <= max).map(t => {
        const s = el("span", {}, t === 1 ? "1 (no change)" : t + "×");
        s.style.left = pos(t) + "%";
        if (t === 1) s.style.transform = "none";   // the first sits at the edge, not centred on it
        return s;
      })), el("span", { class: "bar-value" }, ""));
    list.append(scaleRow);
    root.append(list);
    function draw() {
      for (const { r, bar, ci, value } of rows) {
        const d = o.value(r, mode);
        if (!d) { bar.style.width = "0"; ci.style.width = "0"; value.textContent = "–"; continue; }
        bar.style.width = pos(d.v) + "%";
        ci.style.left = pos(d.lo) + "%";
        ci.style.width = Math.max(0.4, pos(d.hi) - pos(d.lo)) + "%";
        value.textContent = d.v.toFixed(1) + "×";
      }
    }
    draw();
    return { setMode(m) { mode = m; tip.hide(); draw(); }, get mode() { return mode; } };
  }

  // Plain bars on a straight scale, one per row, coloured per row:
  //   Chart.plain(root, {rows: [{label, value, colour}], fmt: v => v + "%", max})
  function plain(root, o) {
    root.classList.add("chart", "plain-bars");
    const max = o.max || Math.max(...o.rows.map(r => r.value || 0)) * 1.1 || 1;
    const fmt = o.fmt || (v => String(v));
    const list = el("div", { class: "bar-list", role: "list" });
    o.rows.forEach(r => {
      const bar = el("div", { class: "bar-fill" });
      bar.style.width = (r.value === null || r.value === undefined ? 0 : 100 * r.value / max) + "%";
      if (r.colour) bar.style.background = r.colour;
      list.append(el("div", { class: "bar-row", role: "listitem" },
        el("span", { class: "bar-label" }, r.label), el("div", { class: "bar-track" }, bar),
        el("span", { class: "bar-value" }, r.value === null || r.value === undefined ? "–" : fmt(r.value))));
    });
    root.append(list);
  }

  return { scatter, bars, plain };
})();

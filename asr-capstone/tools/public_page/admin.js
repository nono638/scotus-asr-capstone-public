// The admin page: every rating as a CSV, for tools/read_ratings.py. Only someone
// whose uid is in config/access.admins can read the ratings (hosting/firestore.rules),
// so the page just tries, and says so if it may not.

// The columns, in order. No email or display name: the uid links one person's answers.
const COLUMNS = ["rating_id", "uid", "case", "corpus", "licence", "guidelines", "came_from", "features",
                 "who_right", "record_right", "corrected", "feedback", "played", "created", "updated"];

function csvCell(v) {
  let s = Array.isArray(v) ? v.join(";") : v === null || v === undefined ? "" : String(v);
  // A cell starting with = + - @ would run as a formula in a spreadsheet; read_ratings.py takes the ' off.
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
function toCsv(rows) {
  const lines = [COLUMNS.join(",")];
  rows.forEach(r => lines.push(COLUMNS.map(c => csvCell(c === "rating_id" ? r.id : r[c])).join(",")));
  return lines.join("\r\n") + "\r\n";
}

let ratings = [];
const SLUG = { "CC BY 4.0": "scotus", "CC BY-SA 4.0": "edacc", "CC BY-NC-SA 4.0": "coraal" };
document.querySelectorAll("#admin button[data-licence]").forEach(b => b.addEventListener("click", () => {
  const licence = b.dataset.licence;
  const rows = licence ? ratings.filter(r => r.licence === licence) : ratings;
  const name = `ratings-${licence ? SLUG[licence] : "all"}-${new Date().toISOString().slice(0, 10)}.csv`;
  const a = el("a", { href: URL.createObjectURL(new Blob([toCsv(rows)], { type: "text/csv" })), download: name });
  document.body.append(a); a.click(); a.remove();
  $("#say").textContent = `${rows.length} rating${rows.length === 1 ? "" : "s"} in ${name}.`;
}));

siteNav($("#nav"), D.pages, "admin.html");
Backend.onUser(async u => {
  const no = text => { $("#admin").hidden = true; $("#not-admin").hidden = false; $("#not-admin").textContent = text; };
  if (Backend.mode === "off") return no("Accounts are not switched on yet on this site.");
  if (!u) return no("Please sign in first.");
  if (!(await Backend.isAdmin())) return no("This page is for the site's admin. Your account isn't one.");
  $("#not-admin").hidden = true;
  $("#admin").hidden = false;
  try {
    ratings = await Backend.allRatings();
    const people = new Set(ratings.map(r => r.uid)).size;
    const by = {};
    ratings.forEach(r => { by[r.corpus] = (by[r.corpus] || 0) + 1; });
    $("#summary").textContent = `${ratings.length} rating${ratings.length === 1 ? "" : "s"} from ${people} ${people === 1 ? "person" : "people"}` +
      (ratings.length ? ` (${Object.entries(by).map(([c, n]) => `${c} ${n}`).join(", ")}).` : ".");
  } catch (e) { $("#summary").textContent = e.message; }
});

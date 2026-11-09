// What every page of the public site adds to the pages it shares with the private
// build (tools/build_public.py puts it on all of them): the account link in the bar
// across the top, a "Rate this" link on each failure card, the licence line in the
// footer, and in test mode a banner saying so, with its switches.
//
// Loaded after cards.js and before the page's own script, so the cards the page
// draws get their link. SITE_ROOT is "" on the site's pages and "../../" on the
// whole-recording pages.

// The contributor line from going-public.md, on the sign-up and rating pages.
window.CONTRIBUTOR_LINE = "What you submit here (ratings, labels, corrected transcripts) may be published for research, without your name or email. You agree it is shared under the licence of the recording it is about: CC BY-NC-SA 4.0 for CORAAL, CC BY-SA 4.0 for EdAcc and Earnings-22, and CC BY 4.0 for the Supreme Court.";

(() => {
  const ROOT = window.SITE_ROOT || "";
  const make = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  };

  // "Rate this" on every card that has a case in the rating queue.
  if (typeof Cards !== "undefined" && !Cards.wrapped) {
    const draw = Cards.failure;
    Cards.failure = (grid, c) => {
      const card = draw(grid, c);
      if (c.rateCase) {
        const foot = card.querySelector(".card-heard") || card;
        foot.append(" ", make("a", { href: `${ROOT}rate.html#case=${c.rateCase}&from=card`, class: "rate-link" }, "Rate this"));
      }
      return card;
    };
    Cards.wrapped = true;
  }

  const licenceLine = () => make("p", { class: "licence-line" },
    "Text and charts © Noah Collin, ", make("a", { href: "https://creativecommons.org/licenses/by/4.0/" }, "CC BY 4.0"),
    ", except where noted; the code is under the MIT licence. Audio and transcripts keep their own licences: Supreme Court (public domain), EdAcc and Earnings-22 text (CC BY-SA 4.0), CORAAL (CC BY-NC-SA 4.0, non-commercial). ",
    make("a", { href: ROOT + "licences.html" }, "Credits and licences"), " · ",
    make("a", { href: ROOT + "privacy.html" }, "Privacy"), " · ",
    make("a", { href: ROOT + "terms.html" }, "Contributor terms"), " · ",
    make("a", { href: ROOT + "privacy.html#contact-us" }, "Contact"),
    ". A CUNY SPS student project; not legal advice, not an official record.");

  // The footer can be drawn again by the page (the whole-recording pages do), so
  // the line is put back whenever it goes missing.
  function keepFooter() {
    const foot = document.querySelector("footer");
    if (!foot) return;
    const add = () => { if (!foot.querySelector(".licence-line")) foot.append(licenceLine()); };
    add();
    new MutationObserver(add).observe(foot, { childList: true });
  }

  // The account link says who is signed in. The bar can be drawn again too.
  let who = "Sign in";
  function keepAccountLink() {
    const nav = document.querySelector(".site-nav");
    if (!nav) return;
    const fix = () => nav.querySelectorAll(`a[href$="account.html"]`).forEach(a => { if (a.textContent !== who) a.textContent = who; });
    fix();
    new MutationObserver(fix).observe(nav, { childList: true, subtree: true });
    if (typeof Backend === "undefined" || Backend.mode === "off") return;
    Backend.onUser(async u => {
      who = "Sign in";
      if (u) {
        try { const p = await Backend.getProfile(); who = p && p.displayName ? `Account (${p.displayName})` : "Account"; }
        catch (e) { who = "Account"; }
      }
      fix();
    });
  }

  // Test mode: a banner that cannot be missed, with the switches the real site keeps
  // in Firestore's config documents.
  function testBanner() {
    if (typeof Backend === "undefined" || Backend.mode !== "test") return;
    const box = make("div", { class: "test-banner", role: "note", id: "test-banner" });
    document.body.prepend(box);
    const draw = () => {
      const s = Backend.test.state();
      const tick = (key, label, on, needUser) => {
        const input = make("input", { type: "checkbox", "data-test": key });
        input.checked = on;
        input.disabled = needUser && !s.user;
        input.addEventListener("change", () => Backend.test.set(key, input.checked));
        return make("label", {}, input, " " + label);
      };
      const mail = s.mail.length ? s.mail[s.mail.length - 1] : null;
      box.replaceChildren(
        make("b", {}, "TEST MODE"),
        " A pretend backend in this browser: no Firebase, nothing leaves this computer. ",
        tick("allowlist", "I'm on the allowlist", !!(s.user && s.config.allowlist.includes(s.user.uid)), true), " ",
        tick("admin", "I'm the admin", !!(s.user && s.config.admins.includes(s.user.uid)), true), " ",
        tick("open_to_public", "Open to the public", s.config.open_to_public, false), " ");
      if (mail) box.append(make("span", { class: "test-mail" }, `Last pretend email: ${mail.kind === "verify" ? "check your address" : "reset your password"}, to ${mail.to}. `));
      if (s.user && !s.user.verified) {
        const b = make("button", { type: "button", class: "btn", "data-test": "verify" }, "Click the link in the pretend email");
        b.addEventListener("click", () => { Backend.test.clickVerifyLink(); draw(); });
        box.append(b, " ");
      }
      const wipe = make("button", { type: "button", class: "btn", "data-test": "wipe" }, "Wipe test data");
      wipe.addEventListener("click", () => { Backend.test.wipe(); location.reload(); });
      box.append(wipe);
    };
    draw();
    Backend.onUser(draw);
  }

  const start = () => { keepFooter(); keepAccountLink(); testBanner(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

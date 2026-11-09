// The account page: sign up (with email checking), sign in, password reset, a small
// profile, sign out, and deleting the account with all its ratings. Everything goes
// through Backend (backend.js).

const msg = (id, text, cls = "") => { const s = $(id); s.textContent = text; s.className = "say " + cls; };
// Where to go after signing in: a page of this site only, never another address.
const nextPage = (() => {
  const n = new URLSearchParams(location.search).get("next") || "";
  return /^[a-z0-9-]+\.html(#[a-z0-9=&-]*)?$/i.test(n) ? n : "";
})();

siteNav($("#nav"), D.pages, "account.html");
$("#contrib").textContent = window.CONTRIBUTOR_LINE;
$("#bg-label").hidden = !Backend.askBackground;
if (Backend.mode === "off") $("#off").hidden = false;

async function busy(form, f) {
  const b = form.querySelector("button[type=submit]");
  b.disabled = true;
  try { await f(); } finally { b.disabled = false; }
}

$("#signin-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.target, async () => {
    msg("#in-say", "Signing in…");
    try {
      await Backend.signIn($("#in-email").value, $("#in-password").value);
      msg("#in-say", "");
      if (nextPage) location.href = nextPage;
    } catch (err) { msg("#in-say", err.message, "bad"); }
  });
});

$("#reset-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.target, async () => {
    try {
      await Backend.resetPassword($("#reset-email").value);
      msg("#reset-say", "If there is an account with that email, a link to reset the password is on its way. Check your spam folder too.", "good");
    } catch (err) { msg("#reset-say", err.message, "bad"); }
  });
});

$("#signup-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.target, async () => {
    msg("#up-say", "Making your account…");
    try {
      await Backend.signUp($("#up-email").value, $("#up-password").value, $("#up-name").value);
      msg("#up-say", "");
    } catch (err) { msg("#up-say", err.message, "bad"); }
  });
});

$("#verify-done").addEventListener("click", async () => {
  const u = await Backend.refresh().catch(() => null);
  if (u && u.verified) { msg("#verify-say", "Thank you, your email is confirmed.", "good"); draw(u); }
  else msg("#verify-say", "It isn't confirmed yet. Click the link in the email, then try again.", "bad");
});
$("#verify-again").addEventListener("click", async () => {
  try { await Backend.resendVerification(); msg("#verify-say", "Sent again. Check your spam folder too.", "good"); }
  catch (err) { msg("#verify-say", err.message, "bad"); }
});

$("#profile-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.target, async () => {
    const p = { displayName: $("#me-name").value };
    if (Backend.askBackground && $("#me-background").value) p.background = $("#me-background").value;
    try { await Backend.saveProfile(p); msg("#me-say", "Saved.", "good"); }
    catch (err) { msg("#me-say", err.message, "bad"); }
  });
});

$("#signout").addEventListener("click", () => Backend.signOut());

$("#delete-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.target, async () => {
    msg("#del-say", "Deleting…");
    try {
      await Backend.deleteEverything($("#del-password").value);
      msg("#in-say", "Your account and ratings are deleted.", "good");
    } catch (err) { msg("#del-say", err.message, "bad"); }
  });
});

async function draw(u) {
  $("#signed-out").hidden = !!u || Backend.mode === "off";
  $("#signed-in").hidden = !u;
  if (!u) return;
  $("#me-email").textContent = u.email;
  $("#verify").hidden = u.verified;
  $("#verify-email").textContent = u.email;
  try {
    const p = await Backend.getProfile();
    $("#me-name").value = (p && p.displayName) || "";
    $("#me-background").value = (p && p.background) || "";
  } catch (err) { msg("#me-say", err.message, "bad"); }
  try {
    const n = (await Backend.myRatings()).length;
    $("#me-ratings").textContent = n ? `You have rated ${n} clip${n === 1 ? "" : "s"}.` : "You haven't rated any clips yet.";
  } catch (err) { $("#me-ratings").textContent = ""; }
  $("#go-admin").hidden = !(await Backend.isAdmin().catch(() => false));
  if (nextPage && u.verified) $("#go-rate").href = nextPage;
}

Backend.onUser(draw);

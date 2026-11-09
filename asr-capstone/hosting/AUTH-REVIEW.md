# Sign-in and the ratings database: a review

Written 8 November 2026. I researched current best practice for sign-in on a small
static site, then read what is already built against it: `going-public.md`,
`hosting/SETUP.md`, `hosting/firestore.rules`, `hosting/firebase-config.js`,
`tools/build_public.py` and the account, rating and admin pages in `tools/public_page/`.
No code or settings were changed. There is no Firebase project yet, so nothing here was
run against a real Firestore. **Not verified** marks things I could not check. "My
reading" marks a judgement no source states outright.

## Summary

**Recommendation: keep what is built.** Firebase Authentication (email and password)
plus Firestore on the free Spark plan is a standard, maintained setup. It suits a
solo student who has no server and installs nothing. The site does **not** write its
own authentication. Firebase's own SDK, loaded from Google's CDN (version 12.19.0,
checked to exist), takes the passwords, stores the hashes, keeps the session, sends
the emails and slows down password guessing. The forms on `account.html` are thin
wrappers around Firebase calls. A prebuilt sign-in screen would not make it safer.
FirebaseUI's new version 7 is still a beta, needs npm and a bundler, and supports
React, Angular and Shadcn only. The old version 6 is archived and does not work with
the modular SDK the site uses.

**What to change before go-live** (small fixes, not a rebuild):

1. **The "Rate" save can wrongly say "invited testers only".** Every database refusal
   shows the gate message. Just after someone confirms their email, their sign-in token
   can still say "not confirmed" for up to an hour, so the rules refuse them (likely,
   not verified). Fix: on a refusal, refresh the token once and retry, and show the gate
   message only for the gate.
2. **The shared `stats/counts` counter is the one unusual, home-made part.** It is
   clever but can be gamed. A tester can push one clip's count up again and again.
   A tester could also fill the document with fake case ids until every save fails.
   Simplest fix: drop the live counter and put the counts into `cases.json` at each
   rebuild, from the admin export.
3. **The database trusts the browser about which data set a rating belongs to.**
   Case ids do not contain the data set (all 4,183 start with `f`). So a tampered
   rating of a CORAAL clip could say "Supreme Court, CC BY 4.0", and
   `read_ratings.py --split` would file it in the wrong licence. Fix: look up each
   case's data set in `public/rate/cases.json` when reading the export.
4. **Password length.** The page asks for 8 characters, but Firebase's default only
   enforces 6. NIST's 2025 rules say 15 for a password used alone. Set a password
   policy in the console and make the page say the same number.

**Top risks on go-live:** the misleading gate message (1); the counter (2); free
quotas used up by a few heavy users or a script, which stops saving for **everyone**
until midnight Pacific; a bot using up the 1,000-a-day confirmation emails; and no
real backup on the free plan.

**What Noah must decide:** the password minimum (15, as NIST says, or something
shorter); whether to keep "Fewest ratings first" as a live counter; whether to switch
on App Check now or when the site opens to the public; and the date when all accounts
are deleted ("when the study ends" needs a real date).

**Setup time:** about **3½-4½ hours** in all. That is the 2-3 hours in `SETUP.md` plus
about an hour and a half for the extra settings and tests below. The code fixes above
are a few hours of work for whoever writes them, and are not counted.

---

## 1. What "tried and true" looks like

### Managed sign-in, not self-built

Every source agrees: let a provider handle passwords. OWASP's cheat sheets and NIST
SP 800-63B list many duties: hashing, rate limiting, generic error messages, reset
links, email checks and session tokens. Each one is easy to get slightly wrong.
`going-public.md` already rules out building it on Cloudflare D1 for this reason.

| Option | Free tier (late 2026) | Upkeep | Lock-in | Fit for this site |
|--|--|--|--|--|
| **Firebase Auth** (chosen) | 50,000 monthly users on Spark; sends its own emails (1,000 confirmations and 150 resets a day); 100 new accounts per hour per IP [1] [2] | None: Google runs it | Medium. Users can be exported with their password hashes, but only with the Firebase command line (needs Node) | Good. Already built, no server, works from a CDN script, pairs with Firestore rules |
| Supabase Auth | 50,000 monthly users; needs your own email sender; free projects pause after a quiet week [3] | Low, plus the email sender | Low (it is Postgres) | Good runner-up if SQL matters more |
| Auth0 | 25,000 monthly users (third-party sources, not checked on auth0.com) [4] | Low, but a lot of settings | Medium | Login only. Still needs a database and a way for the database to trust Auth0's tokens |
| Clerk | 50,000 monthly retained users since Feb 2026 (third-party sources, not checked on clerk.com) [5] | Low | Medium | Built for React apps. Still needs a database |
| Cloudflare Access | Zero Trust free plan, up to 50 users, email one-time code (not checked on Cloudflare's own price page) [6] | Low | Low | Locks whole pages, not per-person data. Could guard testers or `admin.html`, but cannot hold ratings |
| Self-built (D1, PocketBase) | Free or a few dollars | High: you own every security bug | — | No |

### Prebuilt sign-in screen or custom forms

- **FirebaseUI v7** is a full rewrite for "React, Shadcn and Angular", installed from
  npm, with the beta tag in its install commands [7] [8]. It has no plain-script
  version. Using it would mean adding Node and a build step, which this project avoids.
- **FirebaseUI v6** has been moved to a `v6-archive` branch [7]. It works only with the
  older "compat" SDK. Adding an archived library to a new site is not best practice.
- **So the custom forms are the right call here**, as long as they only call Firebase
  and do no password logic of their own. They don't. They follow OWASP's form advice:
  real `type="email"`/`type="password"` fields, `autocomplete` values so password
  managers work, and pasting allowed [9].

### Passwords

NIST SP 800-63B (revision 4, the 2025 edition) [10]:

- "a minimum of 15 characters" when a password is used alone (8 is the floor only
  alongside a second factor);
- allow at least 64 characters;
- "SHALL NOT impose other composition rules" (no "must contain a symbol");
- check new passwords against a list of common or leaked passwords;
- no forced periodic changes; limit failed attempts; allow password managers and paste.

Firebase lets you set a **password policy** (Authentication > Settings > Password
policy): a minimum length of 6 to 30, a maximum, optional character rules, in
"Require" or "Notify" mode [11]. The Firebase page describes it without saying an
upgrade is needed. Whether the tab shows on a plain Spark project is **not verified**.
Firebase has no leaked-password check that I could find (not verified). Firebase slows
down repeated failed sign-ins on its own (`auth/too-many-requests`, which the site
already handles).

### Email checks, enumeration and abuse

- **Email verification** before saving ratings is the standard pattern. The checklist
  says to protect data "by requiring a non-anonymous provider or a verified email" [12].
  The site does this in the rules (`email_verified == true`).
- **Email enumeration protection** has been on by default for projects made since
  15 September 2023 [11] [13]. With it on, wrong-email and wrong-password sign-ins give
  the same error, and a reset request says nothing about whether the account exists.
  Sign-up still says "email already in use" ("Invalid sign-up cases continue to return
  `EMAIL_EXISTS` errors") [13]. That cannot be avoided with self-service sign-up.
- **Abuse:** Firebase allows 100 new accounts per hour per IP address [2]. A bot could
  still spend the project's 1,000 confirmation emails a day and send unwanted mail to
  strangers. Google's answer is **App Check** [12].
- **App Check with reCAPTCHA Enterprise** works on the web. "reCAPTCHA Enterprise is
  no-cost for 10,000 assessments each month" [14]. Without a billing account a project
  gets the free "Essentials" tier [15]. Over the limit, one Google staff answer says it
  returns errors rather than charging (not verified in the docs). App Check covers
  Firestore, and Authentication "(Preview)" [14]. On Spark, fewer score levels are
  available [16]. It needs a few lines of code and a "debug token" for localhost.
- **Passwordless email links: not on Spark.** The free plan sends only **5** sign-in
  link emails a day [2].
- **Google sign-in** is free, sends no email, and gives people Google's two-step
  sign-in. A good later addition, especially for the admin account. On a site not hosted
  by Firebase, use the pop-up flow, not the redirect flow (my reading of Firebase's
  redirect notes; test it).

### Session in the browser

The Firebase SDK keeps the session in the browser's IndexedDB by default. Its sign-in
token lasts an hour and renews itself. This is normal for a Firebase site. OWASP's
warning is that "a single Cross-Site Scripting vulnerability can read or write any data
in IndexedDB" [17]. So the real defence is never putting untrusted text into the page as
HTML. A Content-Security-Policy header helps as a second layer. Cloudflare Pages can
set one from a `_headers` file [18].

### Account deletion and re-authentication

OWASP: "require the current credentials for an account before updating sensitive
account information" [9]. Firebase refuses `deleteUser` without a recent sign-in. The
usual fix is `reauthenticateWithCredential` first [19].

### Firestore security rules

From the checklist [12] and the rules guides [20] [21]:

- start in production mode (deny all) and open only what is needed;
- "write a rule before adding a new document type": the rules are the schema;
- per-person documents tied to `request.auth.uid`;
- check every field (`hasOnly`, `hasAll`, types, sizes) and use server timestamps;
- remember that `get()`/`exists()` inside rules are billed reads, "even if your rules
  reject the request", up to 10 per request (20 in a batch) [20];
- admins: either **custom claims** (set with the Admin SDK from a trusted machine) or a
  **document listing roles** (Firebase's own example checks a field in a user document)
  [20]. Claims cost no reads but need a service-account key and the Admin SDK. A config
  document is editable only in the console. Both are standard.
- test rules: the checklist says to use the Local Emulator Suite [12], which needs Java
  and Node (ruled out here). The console's **Rules Playground** can try single reads and
  writes as a chosen user [22]. It cannot try a batch of writes, so it cannot test
  `existsAfter` (my understanding, not verified).

### Backups, monitoring, money

- **Backups:** managed export and scheduled backups need billing: "Firebase projects
  must be on the Blaze plan to use the managed export and import service" [23]. On
  Spark the only backup is your own export, which here is the admin CSV.
- **Money:** Spark has no card on file, so it cannot charge. When a daily limit runs
  out, that part stops until the next day [1]. The checklist's advice on budget alerts
  only matters if billing is ever linked [12]. If it ever is, add a budget alert at a
  few dollars. Budgets warn; they do not stop spending.
- **Monitoring:** Firestore > Usage, and Authentication > Usage, in the console.
- **API key:** the web config is not a secret [24]. The checklist still says to
  restrict the key to the APIs it uses, in Google Cloud console > APIs & Services >
  Credentials [12] [24]. Be careful: removing a needed API breaks sign-in.

### Privacy basics (my reading; see `going-public.md` section 3)

Keep only what the study needs; no emails in Firestore; a real retention date; deletion
on request. Put the site's adults-only rule and a short privacy notice up front. GDPR
probably does not reach an English-language U.S. site, but its basics are cheap to meet.
New York's SHIELD Act asks for "reasonable safeguards". A managed sign-in service, tight
rules and careful exports cover that.

---

## 2. Review of what is built

### Sound

- **No home-made password handling.** Sign-up, sign-in, reset, email check and deletion
  all call the Firebase SDK (`backend.js`, `firebaseBackend`). Passwords never touch
  Firestore or the page's own storage.
- **Firebase errors are reworded in a safe way.** `user-not-found`, `wrong-password` and
  `invalid-credential` all show the same message. The reset page says "If there is an
  account with that email…" (OWASP's wording) [9].
- **Email verification is enforced by the rules**, not only by the page.
- **Deletion is done properly.** It signs the person in again with their password, then
  deletes the ratings, then the profile, then the account. The order matters: once the
  account is gone, the rules would refuse to delete its data.
- **The rules follow the standard pattern.** There is a final deny-all. Profiles and
  ratings are per person. Every rating's id must be `<uid>__<case>` and its `uid` field
  must match. Every field is listed and checked for type, choice and size. Timestamps
  must be `request.time`. `created` cannot be changed later. The two config documents
  cannot be written from any page.
- **Admin by config document** is a documented pattern. It keeps the Admin SDK and a
  service-account key off the laptops.
- **Minimum data.** No email or display name goes into ratings or the CSV. Google
  Analytics is off. The display name is visible only to its owner.
- **Safe page building.** The pages make HTML with `createElement`/`textContent`, not
  `innerHTML`. The only `innerHTML` is a chart tooltip in `web/widget/chart.js`, which
  shows build-time numbers, not visitors' text. The CSV export guards against
  spreadsheet formulas. The `?next=` redirect accepts only a page of this site.
- **Test mode cannot reach the live site.** It runs only on `localhost`/`127.0.0.1`. (It
  keeps pretend passwords in plain text in `localStorage`. That is fine for a local
  stand-in, but never reuse a real password there.)
- **The Firebase SDK version is pinned** (12.19.0, which exists on gstatic).

### Risky or non-standard

1. **Every refusal shows the gate message** (`saveRating`: any `permission-denied` →
   `GATE_MESSAGE`). Three different causes give the same message: an out-of-date
   token, a rules mistake, and the real gate. Just after someone confirms their email,
   the account page refreshes the token, but the rating page does not. If a person
   confirms in another tab and goes straight to rating, their token may still say
   "unverified" for up to an hour. They are then told they are not an invited tester
   (likely, not verified). On go-live day this will also hide any rule mistake. Fix:
   refresh the token and retry once. Better still, let a tester read their own
   allowlist entry, so the page knows which case it is.
2. **The live counter (`stats/counts`)** is the most home-made part, and the only one
   that is not a common Firebase pattern.
   - A rating can be deleted on its own (the rules allow it), so the count is not
     lowered. Create, delete, create again, and the count grows by one each time. That
     skews "Fewest ratings first".
   - Fake case ids that match `[a-z][0-9]{5,6}` each add a key to the one document.
     Every key is indexed (about 2 index entries each), and a document may have 40,000
     index entries and 1 MiB [25]. A tester who adds about 20,000 fake ratings (two or
     three days of the write quota) would make every later save fail, for everyone.
   - It is one document written by everyone. Firestore's guidance is about one
     sustained write per second per document (from memory, not re-checked). That is
     fine at this size.
   - Fixes, simplest first: drop it and bake counts into `cases.json` at rebuild; or
     keep it and add a single-field index exemption for `stats/counts` field `n`
     (Firestore > Indexes > Single field), plus a rule that a rating delete must lower
     the count in the same batch.
3. **`corpus` and `licence` are not tied to the case.** The rules check that the pair
   matches (CORAAL ↔ CC BY-NC-SA 4.0), not that the case really is a CORAAL case. Case
   ids do not say which data set they belong to. `read_ratings.py --split` groups by the
   stored `licence`. Fix: when reading the export, look each case up in
   `public/rate/cases.json` and drop rows that disagree or name unknown cases.
4. **Password length does not match.** The form says "At least 8". Firebase enforces 6
   until a policy is set. Neither meets NIST's 15 for a password used alone.
5. **Quotas are shared by everyone.** 50,000 reads and 20,000 writes a day [1].
   - Opening the rating page reads every rating the person has saved, so 1,000 ratings
     means 1,000 reads per visit.
   - Opening `admin.html` reads the **whole** ratings collection straight away, before
     any button is pressed.
   - There is no per-person write limit, so one script could use up the day's writes.
   - On Spark this costs nothing. It just stops saving for everyone until midnight
     Pacific. Watch the Usage tab during the study. Have the admin page read only when a
     button is pressed. App Check makes scripting harder.
6. **App Check would cost an assessment on every page.** `public.js` starts Firebase on
   every page (for the "Account" link), so every visitor would use reCAPTCHA
   assessments, readers included. Start App Check only on `account.html`, `rate.html`
   and `admin.html`, or the 10,000 a month could run out. If App Check is enforced when
   that happens, sign-in would stop.
7. **The admin account is the weak point.** It can read every rating. Firebase
   email/password has no second factor without the Identity Platform upgrade [12]. Give
   it a long random password from a password manager, or later make the admin a Google
   sign-in account (Google's two-step sign-in then protects it).
8. **No backup but the CSV.** There is no point-in-time restore on Spark [23]. A rules
   mistake or a bad script could delete ratings for good.
9. **Deletion requests by email.** If Noah deletes a user in the console, Firestore
   keeps their profile and ratings, because nothing links the two on Spark. Firebase's
   "Delete User Data" extension needs Cloud Functions, which need Blaze (from memory,
   not re-checked). Write down the manual steps: find the uid, delete
   `users/<uid>` and every `ratings/<uid>__*`, then delete the user.
10. **Retention.** The privacy page promises to delete emails "when the study ends",
    with no date. The console deletes users a few at a time. Bulk deletion needs the
    Admin SDK (not verified whether the console now selects many).
11. **No security headers.** `build_public.py` writes no `_headers` file. Optional, but a
    Content-Security-Policy (scripts only from the site and `www.gstatic.com`;
    connections to `*.googleapis.com`; `frame-ancestors 'none'`) is a cheap second layer.
    Test it carefully: a wrong CSP silently breaks sign-in.
12. Minor: `background` can be written by anyone through their own profile even while
    `askBackground` is false (only by someone poking the database by hand). Duplicate
    ticks in `features` are allowed. Cloudflare preview addresses
    (`<hash>.asr-errors.pages.dev`) are not authorised domains, so sign-in fails there.
    That is expected.

### What I could and could not check without a Firebase project

- **Read and checked by hand:** the rules against the data model and against every
  write the pages make. The create, update and delete batches match what the rules
  expect. The admin's unfiltered list should pass because `isAdmin()` does not depend
  on the document. Owner queries use `where('uid','==',uid)`, as "rules are not
  filters" requires. A rule that calls `get()` counts against the 10/20 limits, and
  these rules stay under them.
- **Not verified:** that the rules compile, especially `let` inside `countsWrite`,
  `map.diff().affectedKeys()` and `existsAfter`; that the admin's unfiltered query is
  allowed; how long a stale `email_verified` token lasts in practice; whether the
  password-policy tab shows on Spark; and whether the Rules Playground can set
  `email_verified`. `SETUP.md` step 9 is the first real test of all of these.

---

## 3. Recommendation

**Keep:** Cloudflare Pages + Firebase Authentication (email/password) + Firestore on
Spark; the custom forms; email verification in the rules; the config-document admin and
allowlist; per-person rating documents; deletion with re-authentication; the CSV export.

**Do not swap in:** FirebaseUI (beta or archived, and needs a build step). No other
provider fits better.

**Change in the code before go-live** (all small): the token refresh and clearer
refusal messages (risk 1); drop or harden the counter (2); check the data set in
`read_ratings.py` (3); make the form's password text match the policy (4); have the
admin page read on demand (5); if App Check is added, start it only on the three
account pages (6).

### Firebase and Google settings, in order

Do these alongside `SETUP.md`:

| When | Setting | Where | Time |
|--|--|--|--|
| SETUP step 2 | Two-step sign-in on the Google account that owns the project | myaccount.google.com > Security | 5 min |
| SETUP step 3 | Check **Email enumeration protection** is on | Authentication > Settings > User actions | 2 min |
| SETUP step 3 | **Password policy**: minimum 15 (or your choice), maximum 64 or more, no character rules, mode **Require** | Authentication > Settings > Password policy (if shown on Spark) | 5 min |
| SETUP step 3 | Set the sender name on the email templates | Authentication > Templates | 5 min |
| SETUP step 4 | Stay on **Spark**; never accept an "upgrade" prompt | Usage and billing | — |
| SETUP step 5 | If you keep the counter: index exemption for collection `stats`, field `n` | Firestore > Indexes > Single field | 5 min |
| SETUP step 7 | Admin account with a long random password from a password manager | — | 5 min |
| SETUP step 9 | Run the step 9 list, plus: a second user tries to `get` your rating (refused); a write with an extra field (refused); a rating with `licence` wrong for its `corpus` (refused); before and after confirming email | Rules > Rules Playground, and the site | 30-40 min |
| After step 11 | Restrict the browser API key: keep the Firebase APIs it needs (Identity Toolkit, Token Service, Firestore, Installations); try sign-in again at once | Google Cloud console > APIs & Services > Credentials | 15 min |
| Before step 13 (going public) | **App Check**: register the web app with reCAPTCHA Enterprise; watch the metrics for a week; then enforce for Firestore (and Authentication, still preview) | App Check in the console (needs the code change) | 30-45 min |
| Weekly during the study | Download "All ratings (CSV)" into a git-ignored folder (not GitHub: it holds research data); glance at Firestore > Usage | admin.html, console | 5 min a week |
| Study end | Delete all accounts; keep only the anonymised export | Authentication > Users | 15-30 min |

**Time:** about 1½ hours beyond `SETUP.md`'s 2-3, so **3½-4½ hours** of Noah's own
time, spread over the setup day and the week before opening.

### Decisions for Noah

1. **Password minimum:** 15, as NIST 2025 says for a password used alone, or a
   shorter, friendlier 10-12. Adding Google sign-in later would let most people avoid
   passwords altogether.
2. **"Fewest ratings first":** keep a live counter (and harden it), or update counts
   only when the site is rebuilt (simpler, safer).
3. **App Check:** before the testers arrive, or only before opening to the public.
4. **A real end date** for deleting accounts, for the privacy page.
5. **Where the CSV backups live** (a private, git-ignored folder; not the public repo).

---

## Sources

1. Firebase pricing: https://firebase.google.com/pricing
2. Firebase Authentication limits: https://firebase.google.com/docs/auth/limits
3. Supabase pricing and pausing: https://supabase.com/pricing, https://supabase.com/docs/guides/platform/free-project-pausing
4. Auth0 free plan (third-party summary; official page not checked): https://www.costbench.com/software/identity-access-management/auth0/free-plan/ ; official: https://auth0.com/pricing
5. Clerk pricing (vendor article; official page not checked): https://clerk.com/articles/clerk-pricing-explained ; official: https://clerk.com/pricing
6. Cloudflare's free Teams/Zero Trust plan, 50 users: https://blog.cloudflare.com/teams-plans
7. FirebaseUI for Web (v7 README, v6 archive branch): https://github.com/firebase/firebaseui-web
8. v7 beta status, July 2026 (Japanese guide, third-party): https://issoh.co.jp/?p=3397
9. OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
10. NIST SP 800-63B (revision 4): https://pages.nist.gov/800-63-4/sp800-63b.html
11. Firebase, password authentication on the web (password policy, enumeration protection): https://firebase.google.com/docs/auth/web/password-auth ; Identity Platform password policies: https://docs.cloud.google.com/identity-platform/docs/password-policy
12. Firebase security checklist: https://firebase.google.com/support/guides/security-checklist
13. Email enumeration protection: https://docs.cloud.google.com/identity-platform/docs/admin/email-enumeration-protection
14. Firebase App Check overview: https://firebase.google.com/docs/app-check
15. reCAPTCHA billing (Essentials tier, 10,000 free): https://docs.cloud.google.com/recaptcha/docs/billing-information
16. App Check with reCAPTCHA Enterprise on the web: https://firebase.google.com/docs/app-check/web/recaptcha-enterprise-provider
17. OWASP HTML5 Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
18. Cloudflare Pages headers: https://developers.cloudflare.com/pages/configuration/headers/
19. Firebase, manage users (re-authenticate, delete): https://firebase.google.com/docs/auth/web/manage-users
20. Firestore rules conditions (role documents, get() limits and billing): https://firebase.google.com/docs/firestore/security/rules-conditions
21. Firestore rules and queries ("rules are not filters"): https://firebase.google.com/docs/firestore/security/rules-query
22. Rules Playground: https://firebase.google.com/docs/rules/simulator
23. Firestore export and import (Blaze only): https://firebase.google.com/docs/firestore/manage-data/export-import
24. Firebase API keys: https://firebase.google.com/docs/projects/api-keys
25. Firestore quotas and limits: https://firebase.google.com/docs/firestore/quotas

Sources 19 and 21 are Firebase's standard pages for those topics; I relied on what I
already knew of them and did not re-open them for this note.

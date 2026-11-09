# Putting the public site online

Step by step, for Noah. Pages and audio go on **Cloudflare Pages**; accounts and
ratings go in **Firebase** (Authentication and Firestore, the free Spark plan). Why these
two: `going-public.md`, section 4. Nothing here needs Node, the Firebase command line or
anything else installed: every step is in a web browser, apart from two Python commands.

Total time: **about 2-3 hours**, plus up to a day for a new domain's DNS. Steps marked
*(optional)* can wait. What the site needs from Cloudflare, and why (headers, the audio
worker, the 404 page), is in `cloudflare-readiness.md`. Before going live, run the
checklist at the end.

| Step | What | Time |
|--|--|--|
| 0 | Decide the contact address and the date email addresses are deleted | 10 min |
| 1 | Build the site and try it in test mode | 15 min |
| 2 | Make the Firebase project | 10 min |
| 3 | Turn on email and password sign-in | 10 min |
| 4 | Make the Firestore database | 10 min |
| 5 | Paste the rules | 5 min |
| 6 | Paste the web config into `hosting/firebase-config.js` | 10 min |
| 7 | Allow localhost, make your own account and find your uid | 15 min |
| 8 | Make the two config documents (admin, allowlist, gate) | 10 min |
| 9 | Try the rules | 20 min |
| 10 | Upload to Cloudflare Pages, set it to fail open | 25-45 min |
| 11 | Tell Firebase the site's address, then check the live site | 10 min |
| 12 | *(optional)* Your own domain and a contact address | 30-60 min, plus DNS |
| 13 | Later: opening it to everyone, after CUNY's HRPP answers | 5 min |

---

## 0. Two decisions

Nobody else can make these, and the pages show placeholders until you do:

- **A contact address** for deletion requests and questions. It goes in `contactEmail`
  in `hosting/firebase-config.js` (step 6), and shows in the privacy notice's Contact
  section and the footer's Contact link. It does not have to be your personal email:
  step 12 makes a free forwarding address on your own domain. With it empty, the
  Contact section says the address isn't set up yet and points to the account page's
  "Delete my account and ratings".
- **The date email addresses are deleted** ("when the study ends, by ..."). Replace
  `[date not set yet]` in `tools/public_page/privacy.html`, for example "31 May 2027".
  `build_public.py` prints a reminder while it is still there.

## 1. Build the site and try it in test mode

```powershell
.\.venv\Scripts\python.exe asr-capstone\tools\build_public.py
.\.venv\Scripts\python.exe asr-capstone\tools\check_public.py          # about 5 minutes, in Edge
.\.venv\Scripts\python.exe asr-capstone\tools\check_public.py --serve 8000
```

Then open http://localhost:8000/. With no Firebase config yet, a yellow **TEST MODE**
banner is on every page: a pretend backend kept in the browser, with switches for "I'm on
the allowlist", "I'm the admin" and "Open to the public", and a button that stands in for
the link in the confirmation email. Nothing leaves the laptop. (Plain
`python -m http.server` works too, but it can't jump inside an audio file, so clips play
from the start; `--serve` can.)

`build_public.py` only reads `site/` and `explorer/`. If the site has changed, run
`tools/build_site.py` and `tools/build_explorer.py` first, as usual. It prints the file
count (today 640 files, 0.88 GB, largest 14.5 MiB) and a "Before going live" line for each
placeholder still empty.

`check_public.py` serves `public/` the way Cloudflare Pages does (its headers, its 404,
`/page` for `page.html`, no part-of-a-file answers) and runs the audio worker in front of
the clips. It fails if the Content-Security-Policy refuses anything on any page, also in a
second run against a stand-in Firebase (it downloads the Firebase code from Google's CDN;
nothing reaches a real project). `--serve` is lighter: it answers part-of-a-file requests
itself, so clips jump without the worker.

## 2. Make the Firebase project

1. Go to https://console.firebase.google.com and sign in with the Google account you
   want to own it. Turn on two-step sign-in for that account if it isn't on.
2. **Create a project.** Name it, for example, `asr-ratings`.
3. When it asks about **Google Analytics, turn it off.** The privacy notice says there is
   no tracking.
4. It starts on the free **Spark** plan. Leave it there: Spark has no card on file and
   cannot charge you. If a daily limit runs out, that part stops until the next day.

## 3. Turn on email and password sign-in

1. **Build > Authentication > Get started.**
2. **Sign-in method > Email/Password > Enable** (the first switch only, not "Email link").
   Save.
3. **Templates** shows the emails Firebase sends (address confirmation, password reset).
   The defaults are fine. You can set the sender name to the site's name.
4. Leave **Settings > User actions > Email enumeration protection** on (the default).

Email verification needs no switch: the site asks Firebase to send the confirmation email
when an account is made, and the database rules refuse ratings until the address is
confirmed.

## 4. Make the Firestore database

1. **Build > Firestore Database > Create database.**
2. Location: **nam5 (United States)**. It can't be changed later.
3. Start in **production mode** (everything closed). Step 5 opens what is needed.

## 5. Paste the rules

1. **Firestore Database > Rules.**
2. Replace everything there with the whole of `hosting/firestore.rules`, and **Publish**.

What the rules allow: each person reads and changes only their own profile and ratings;
nobody can read anyone's email (it is never stored in Firestore at all); only uids in
the admin list can read everyone's ratings; and ratings can be saved only by people with a
confirmed email who are on the allowlist, until you set `open_to_public` (step 13). Every
field of a rating is checked for type and size.

**The rules have not been run against a real Firestore yet.** They were written and
checked by reading them against the data model, and the test mode copies the same checks,
but step 9 is the first real test. If something is refused that should not be, the
browser's console (F12) shows `permission-denied`; the rules file has comments for each
part.

## 6. Paste the web config

1. **Project settings** (the gear) **> General > Your apps > Add app > Web** (`</>`).
2. Nickname: anything. Do **not** tick Firebase Hosting (the pages go on Cloudflare).
3. It shows `const firebaseConfig = { apiKey: ..., authDomain: ..., ... }`. Copy those six
   values into `hosting/firebase-config.js`, between the quotes.
4. In the same file, put the contact address for deletion requests in `contactEmail`
   (step 12 has a free way to make one), or leave it empty for now.
5. Leave `askBackground: false` until CUNY's HRPP has answered.

This config is not a secret: every visitor's browser receives it, and the rules decide
what it can do. It is fine to commit. Then rebuild: `tools/build_public.py`. **Rebuild
before every upload after changing it:** the Content-Security-Policy in `public/_headers`
names the `authDomain` from this file, so sign-in on phones and Safari works.

## 7. Allow localhost, make your own account and find your uid

1. **Authentication > Settings > Authorized domains > Add domain: `localhost`.** Firebase
   projects made after 28 April 2025 no longer have it by default. Without it the account
   is made but the confirmation email is refused, because its link back to the site is on
   a domain Firebase doesn't know. (Google advises removing `localhost` again once the
   site is live; you can, at the cost of testing on the laptop.)
2. Serve the rebuilt site (`check_public.py --serve 8000`) and open
   http://localhost:8000/account.html (`localhost`, not `127.0.0.1`). With a config in
   place, the test banner is gone and the page talks to Firebase. To get test mode back
   on localhost, add `?test` to the address.
3. Make an account with your own email. Open the confirmation email, click the link,
   come back and press "I've clicked the link".
4. In the Firebase console: **Authentication > Users**. Copy your **User UID** (a string
   like `aB3dE...`).

## 8. Make the two config documents

In **Firestore Database > Data**:

1. **Start collection**, id `config`.
2. First document, id **`public`**, one field: `open_to_public`, type **boolean**,
   value **false**.
3. **Add document** in `config`, id **`access`**, two fields, both type **array**:
   - `admins`: one **string** item, your uid.
   - `allowlist`: one **string** item, your uid.

The console ignores the rules, so you can always edit these by hand; no page can. To let
a tester rate before the gate opens, add their uid to `allowlist` (they make an account
first and send you their uid, which is shown in the console's Users list next to their
email).

## 9. Try the rules (the first real test)

On localhost, signed in as yourself:

- [ ] `rate.html`: answer a clip and press Save. It says "Saved"; the AI judge's answer
      appears below only then.
- [ ] Change the answer and save again: "Your changes are saved". In the console, the
      `ratings` collection has one document named `<your uid>__<case>`, and
      `stats/counts` has that case at 1.
- [ ] `admin.html`: the counts show; "All ratings (CSV)" downloads a file. Check it with
      `python asr-capstone\tools\read_ratings.py <file>`.
- [ ] In a private window, make a second account (another email). Before confirming
      the email, Save says to confirm it; after confirming, Save gives the "invited testers"
      message. `admin.html` turns it away.
- [ ] Delete the second account from its account page; its profile and ratings go from
      the console too.

The console's **Rules > Rules Playground** can also try single reads and writes.

## 10. Upload to Cloudflare Pages

1. Make a Cloudflare account at https://dash.cloudflare.com (free; a card only if you buy
   a domain).
2. **Workers & Pages > Create > Pages > Upload assets** (also called Direct Upload).
3. Project name, for example `asr-errors`; the site will be at
   `https://asr-errors.pages.dev`.
4. Drag in the **`asr-capstone/public` folder** and **Deploy**. About 0.9 GB, so give it a
   while. The folder includes four files Cloudflare reads and does not serve: `_headers`
   (security headers), `_routes.json` and `_worker.js` (the audio worker, below) and
   `_redirects`. Drag the folder itself, so they go too.
5. **Settings > Runtime > Fail open / closed: choose Fail open.** The audio worker runs on
   the Workers Free plan's 100,000 runs a day. If they are ever used up, "fail open" keeps
   serving the files directly (clips still play, but can't jump to their start); "fail
   closed" would show an error page instead.
6. Don't turn on **Web Analytics** for the project: it adds a Cloudflare script the
   privacy notice doesn't mention and the Content-Security-Policy would refuse.

Why there is a worker: Pages answers a request for part of a file with the whole file, so
a browser can't start a clip in its middle. Tested here: the cards' clips played from 0
seconds. Safari is reported not to play such audio at all. `_worker.js` answers those
requests for the audio only; everything else is served by Pages directly, free and
unlimited. Details in `cloudflare-readiness.md`, section 3.

Limits checked on 8 November 2026: the dashboard upload takes **up to 1,000 files**, 25 MiB
each, as a folder or a zip, and it accepts `_worker.js`. The site is 640 files, so it fits.
`build_public.py` warns if it ever passes 1,000. Past that, the route is Cloudflare's
`wrangler` command (up to 20,000 files), which needs Node.js, and Node is **not** installed
on either laptop; say if you want it set up then.

To update the site later: rebuild, then in the project **Create new deployment** and drag
the folder in again. Each upload is a full copy, and you can roll back to an earlier one.

## 11. Tell Firebase the site's address, then check the live site

1. **Authentication > Settings > Authorized domains > Add domain**: `asr-errors.pages.dev`
   (your project's name), and your own domain if you add one in step 12. Without this,
   the confirmation and password-reset emails can't link back to the site. Each preview
   address (`<hash>.asr-errors.pages.dev`) would need its own entry, so test sign-in on
   the main address.
2. Check the uploaded site from the laptop (Python only, about 30 seconds):

   ```powershell
   .\.venv\Scripts\python.exe asr-capstone\tools\check_public.py --live https://asr-errors.pages.dev
   ```

   It checks that the security headers arrive, a missing page gets the 404 page, the
   hosting files aren't served, a clip answers a part-of-a-file request (so the worker
   is running), each kind of file has the right type, and the Firebase config is in.
   If the clip check fails, the worker isn't running: see `cloudflare-readiness.md`,
   section 3. Deleting `public/_worker.js` and `public/_routes.json` and uploading
   again always gives a working site, only without jumps.
3. Open the site on a phone, play a card's clip, and sign in once.

## 12. *(optional)* Your own domain and a contact address

- **Domain:** Cloudflare dashboard **> Domain registration > Register**, about $11-12 a
  year for a `.com` (going-public.md). Then in the Pages project **> Custom domains > Set
  up a domain**. Add it in Pages first, before any DNS record by hand (a CNAME made first
  gives error 522). DNS can take a few hours. Add it to Firebase too (step 11), and run
  `check_public.py --live https://yourdomain` again.
- In the domain's **SSL/TLS > Edge Certificates**, turn on **Always Use HTTPS**.
- *(optional)* To send `asr-errors.pages.dev` visitors to your own domain, Cloudflare
  suggests a **Bulk Redirect** at account level.
- **Contact address:** with a domain on Cloudflare, **Email > Email Routing** forwards
  something like `privacy@yourdomain` to your own inbox for free. Put it in
  `contactEmail` (step 6) and rebuild.

## 13. Later: opening it to everyone

Only after CUNY's HRPP has said yes (going-public.md, section 3; the draft email is in
`midterm/drafts/email-hrpp-ratings.md`):

1. Merge any consent wording CUNY asks for into `tools/public_page/privacy.html` and
   `terms.html`, rebuild and upload.
2. In Firestore, set `config/public.open_to_public` to **true**.
3. If CUNY approves the background question: `askBackground: true` in the config file,
   rebuild, upload.

---

## Go-live checklist

Before sending the link to anyone:

- [ ] Contact address decided and in `contactEmail` (steps 0, 6, 12).
- [ ] Deletion date written into `tools/public_page/privacy.html` (step 0).
- [ ] Firebase config pasted, site rebuilt, `build_public.py` prints no "Before going
      live" lines.
- [ ] `check_public.py` ends with "0 failed".
- [ ] Rules tried (step 9).
- [ ] Uploaded, **Fail open** chosen, Web Analytics off (step 10).
- [ ] Site address in Firebase's authorized domains (step 11).
- [ ] `check_public.py --live <address>` ends with "0 failed".
- [ ] Tried on a phone: a clip plays from its start; sign-in works.
- [ ] `config/public.open_to_public` is still **false**. Opening ratings to others waits
      for CUNY's HRPP answer (step 13). Until then, only uids on the allowlist can save.
- [ ] Two-step sign-in on the Google account that owns Firebase and on Cloudflare.

## Free limits, and what would cost money

| Service | Free (what this site uses) | What would cost money |
|--|--|--|
| Cloudflare Pages | 20,000 files, 25 MiB a file, 500 builds a month, no bandwidth limit stated | Only a domain (~$11-12 a year). Workers Paid ($5 a month) only if the site passes 20,000 files. |
| The audio worker (Workers Free) | 100,000 runs a day, reset at midnight UTC; one play is one to three runs | Nothing: past the limit, "fail open" serves the audio without jumps. |
| Firebase Authentication (Spark) | 50,000 monthly users; about 1,000 confirmation emails and 150 password resets a day; 100 new accounts an hour from one address | Nothing on Spark. |
| Firestore (Spark) | 1 GiB stored; 50,000 reads, 20,000 writes and 20,000 deletes a day | Nothing on Spark: when a day's quota runs out, saving or loading stops until midnight Pacific. Only upgrading to the Blaze plan (pay as you go, no hard cap) would ever charge. |

What a rating costs in Firestore: saving one is 2 writes and about 5 reads (the rules'
own lookups count as reads). Opening the rating page reads one document per rating that
person has saved, plus 2. So 50,000 reads a day is roughly a hundred people rating a
hundred clips each. A ratings document is under 1 KB, so 1 GiB is about a million ratings.

## How it fits together (for later changes)

- `tools/build_public.py` reads `site/` and `explorer/` and writes `public/`. It changes
  only the public copy; the private claude.ai pages are untouched.
- `tools/public_page/`: the new pages, `backend.js` (Firebase and the test mode behind
  the same calls), `public.js` (the account link, "Rate this" links, licence line, test
  banner), `public.css`.
- `hosting/firestore.rules`: the data model is at the top of the file.
- `tools/public_page/_worker.js`: answers part-of-a-file requests for the audio on Pages.
- `public/_headers`, `_routes.json`, `_redirects`, `robots.txt`: written by
  `build_public.py` (`headers_file()` and its neighbours); change them there.
- `tools/check_public.py`: the checks, in Edge, in test mode, served like Pages.
  `--serve PORT` just serves; `--live URL` checks the uploaded site.
- `tools/read_ratings.py`: reads the admin page's CSV; `--split` writes one file per
  licence (CORAAL's must stay apart from EdAcc's).

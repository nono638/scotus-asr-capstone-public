# Getting the public site ready for Cloudflare Pages

Researched on 8 November 2026, Cloudflare's own documentation first. These notes say what
a static site on Cloudflare Pages needs, what `public/` had and lacked, and what the build
now does about it. "Not verified" marks something no source settled and no test here could
check. "Tested" means `tools/check_public.py` checks it in Edge or on the files. The steps
for Noah are in `SETUP.md`; this file is the why.

## Summary

- **The site fits.** 640 files, 0.88 GB, largest 14.5 MiB. The dashboard's drag-and-drop
  upload takes 1,000 files of up to 25 MiB [1]. No `wrangler`, no Node.
- **The one real problem: audio could not jump.** Pages "currently returns `200` responses
  for HTTP range requests" [2]: asked for part of a file, it sends the whole file. Tested
  here with a server that does the same: Edge played each card's short clip from 0 seconds
  instead of from its start (3 of 4 cards wrong on the Supreme Court page). Safari is
  reported not to play audio at all without proper range answers [9] (not verified here:
  no Safari on Windows). **Fixed** with a small `_worker.js` in front of the audio only.
- **Security headers added** in a `_headers` file: a Content-Security-Policy that allows
  exactly what the pages load, HSTS, nosniff, a referrer policy, a permissions policy and
  no framing by other sites.
- **To make that policy strict,** the build now moves every inline script into its own
  file under `js/inline/`. Nothing else about the pages changes.
- **Smaller fixes:** a working 404 page at any depth, page descriptions, a site icon,
  `robots.txt`, a Contact section and footer link, two colours a shade darker for
  contrast, and an honest line in the privacy notice about Google Fonts and gstatic.
- **New from Firebase:** projects made after 28 April 2025 no longer allow `localhost`
  by default [10]. `SETUP.md` said they did. It is fixed there.

## 1. Upload limits

| What | Limit | Source |
|--|--|--|
| Files, dashboard drag-and-drop | 1,000 | [1] |
| Files, `wrangler` | 20,000 (Free plan) | [1] [3] |
| Size of one file | 25 MiB | [1] [3] |
| Zip upload | Dashboard yes, `wrangler` no | [1] |
| `_headers` | 100 rules, 2,000 characters a line | [3] [4] |
| `_redirects` | 2,000 static and 100 dynamic | [3] |
| `_routes.json` | 100 rules, 100 characters each | [5] |
| Custom domains per project | 100 on Free | [3] |

- `_worker.js` is accepted by both upload methods [1].
- A `functions/` folder is **not** compiled by drag-and-drop [1]. That is why the worker
  is a single `_worker.js` file and not a `functions/` folder.
- The total size is not limited, only file count and file size (no limit found on [3]).

## 2. How Pages serves files

From [2] unless marked.

- `/about.html` is redirected to `/about`, and `/about/index.html` to `/about/`. The
  redirect code is not stated (not verified; Workers static assets use 307 [6]).
  Relative links keep working, because the folder is the same. Tested.
- A request for `/rate` gets `rate.html`. The `rate/` folder beside it does not get in the
  way: Pages knows files, not folders (my reading of [6]; the local test server copies it).
- **404:** with a `404.html` at the top, Pages serves it for any missing address, looking
  up the folder tree for the nearest one. **Without one, Pages assumes a single-page app
  and serves the home page for every address**, with status 200. `public/404.html`
  exists. It is shown at whatever address was missing, however deep, so the build gives
  it `<base href="/">` and its links and scripts are taken from the top of the site.
  Tested at `/no-such-page` and `/recordings/scotus/deep/no-such-page`.
- **Caching:** Pages sends `Cache-Control: public, max-age=0, must-revalidate` and an
  `ETag`. The browser asks each time and gets a cheap `304 Not Modified` when nothing
  changed. That is right for HTML and data: an update shows at once.
- **Compression:** gzip and Brotli "whenever possible". Audio is already compressed.
- **Headers Pages always adds:** `Access-Control-Allow-Origin: *`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Content-Type-Options: nosniff`.
  Preview addresses also get `X-Robots-Tag: noindex`, so previews stay out of search.
- **Content types:** Pages "always adds" one, but the page does not say how it is chosen
  [2]. No Cloudflare page lists the type for `.ogg`, `.csv` or `.txt` (not verified). The
  worker sets `audio/mpeg` and `audio/ogg` itself. `check_public.py --live` reports the type
  of every kind of file after upload. There are no `.opus` or `.gz` files in `public/`.
  If `.txt` or `.csv` arrive without `charset=utf-8`, the pages still read them right:
  `fetch().text()` always decodes UTF-8.

## 3. Audio and range requests

- A browser that wants to start a clip at 12 seconds asks for part of the file
  (`Range: bytes=...`). A normal server answers `206 Partial Content` with just those bytes.
- Pages answers `200` with the whole file [2]. Several projects found the same in 2025-26
  and put a small worker in front of their audio [8]. Those reports are not Cloudflare's.
- **What it does to this site** (tested, served the way Pages serves): the cards' MP3 clips
  started at 0 seconds instead of their view. The long Ogg recordings on the rating page
  still jumped in Edge, after the whole 13 MB file had loaded, which is slow on a phone.
- **Safari and iPhones** ask for `bytes=0-1` first and are reported to fail on a `200`
  [9]. Community reports only, not verified: there is no Safari to test with here.
- **The fix:** `tools/public_page/_worker.js`, copied to `public/_worker.js`. It is
  Pages' "advanced mode" [7]: a module with `export default { fetch }`. It fetches the
  whole file from Pages with `env.ASSETS.fetch()` and returns only the bytes asked for,
  with `206`, `Content-Range` and `Accept-Ranges`. A range past the end gets `416`.
  Several ranges at once, or a stale `If-Range`, get the whole file, which the standard
  allows.
- **Only the audio goes through it.** `public/_routes.json` lists `/clips/*` and
  `/recordings/<data set>/audio/*`. Every other request is static: "free and unlimited"
  and not counted against the worker's allowance [11] [5].
- **Allowance:** worker runs count toward the Workers Free plan, 100,000 a day, reset at
  midnight UTC [11]. One play is one to three runs, so that is tens of thousands of plays
  a day. Pages has a "fail open" setting: when the allowance is used up, the static files
  are served directly again [5]. Then clips still play but can't jump. Turn it on (SETUP).
- **Not verified:**
  - that `_routes.json` applies to `_worker.js` and not only to a `functions/` folder.
    Cloudflare's pages don't say; Astro's Cloudflare adapter relies on it [12];
  - that `_headers` reaches responses that pass through the worker. Cloudflare says it
    does not apply to Functions' responses [4]. The worker sets the audio's own headers,
    so it does not matter for audio;
  - the worker's CPU time. The Free plan allows 10 ms per run (Workers limits page, not
    re-read for this note). The worker reads the file into memory and slices it, which is
    copying, not computing; the largest audio is 13.6 MB.
  - `check_public.py --live` checks the first two after upload: the home page must have
    the policy header, and a clip must answer a range with 206.
- **Tested:** `check_public.py` runs the same `_worker.js` in Edge as a service worker in
  front of a server that answers ranges the way Pages does. It checks six kinds of range
  answers byte for byte, and that a card's clip and a clip 49 minutes into a CORAAL
  recording start inside their views.
- **If the worker ever causes trouble,** delete `public/_worker.js` and
  `public/_routes.json` and upload again. The site works as before, without jumps. The
  longer-term route is R2 for the audio: it answers ranges, but needs its own domain,
  since the free `r2.dev` address is rate-limited (`going-public.md`, section 4).

## 4. Security headers (`public/_headers`)

Written by `tools/build_public.py` (`headers_file()`), on every path (`/*`).

| Header | Value | Why |
|--|--|--|
| Content-Security-Policy | below | Stops injected scripts, and limits where the pages may connect. |
| Strict-Transport-Security | `max-age=31536000` | Browsers use HTTPS only, for a year. No `includeSubDomains` and no `preload`: both are hard to undo on a domain of your own. |
| X-Content-Type-Options | `nosniff` | Pages sends it already [2]; written here too. |
| X-Frame-Options | `DENY` | For old browsers; `frame-ancestors 'none'` does the same in new ones. |
| Referrer-Policy | `strict-origin-when-cross-origin` | Pages' default [2]. Other sites see only the site's address, never the page. Not `no-referrer`: an API key limited to the site's address (SETUP, optional step) checks the referrer. |
| Permissions-Policy | camera, microphone, geolocation, payment, usb, browsing-topics off | The site uses none of them. Autoplay is left alone. |
| Cross-Origin-Opener-Policy | `same-origin` | Other windows can't reach into the site's. Sign-in uses no pop-ups, so nothing breaks. |

How `_headers` works [4]: a path line, then indented `Name: value` lines. Every matching
rule applies, and the same header from two rules is joined with a comma. So the policy
is set once, in `/*`, and no other rule sets it: two policies would both be enforced.
`! Name` removes a header.

### The Content-Security-Policy

```
default-src 'self';
script-src 'self' https://www.gstatic.com/firebasejs/12.19.0/ https://apis.google.com
           https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com/css2;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https://www.google.com/images/cleardot.gif;
media-src 'self';
connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com
            https://firestore.googleapis.com;
frame-src https://<authDomain from firebase-config.js>;
worker-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
```

Where each entry comes from:

- **Scripts.** The site's own, from `'self'`. The Firebase SDK, by its exact version folder
  (the version is read from `backend.js`). PapaParse on the data page, by its exact file.
  Whole hosts like `www.gstatic.com` or `cdnjs.cloudflare.com` would let in every library
  they carry, so they are allowed by path only. The build collects every outside script
  and stylesheet from the pages themselves, so a new one gets into the policy on its own.
- **No inline scripts.** The pages had 1-7 inline `<script>` blocks each. The build now
  moves each into `js/inline/<hash of its content>.js`. Plain scripts share their
  top-level names and run at the same point either way, so nothing else changes. The
  policy can then leave out `'unsafe-inline'` for scripts, which is most of its value.
  Tested: every earlier check still passes with the policy on (323 checks in all now).
- **Styles** keep `'unsafe-inline'`. The pages have a large inline `<style>` and style
  attributes. Injected CSS can do far less harm than injected script.
- **Fonts:** Google Fonts' stylesheet and font files. Self-hosting them would remove one
  outside host, but every page already loads the Firebase SDK from Google, so Google sees
  each visit either way. The privacy notice now says so.
- **Firebase, read from the SDK's own code (12.19.0):** sign-in calls
  `identitytoolkit.googleapis.com` and `securetoken.googleapis.com`; the database calls
  `firestore.googleapis.com`. On phones, iPads and Safari the sign-in code also opens a
  hidden frame from `https://<authDomain>/__/auth/iframe`, loaded by a script from
  `apis.google.com` (`_shouldInitProactively` is true on mobile and Safari). When the
  database's connection fails, it loads one tiny image from
  `www.google.com/images/cleardot.gif` to test the network.
- **authDomain:** taken from `hosting/firebase-config.js` at build time. While the config
  is empty the policy says `https://*.firebaseapp.com`. **Rebuild after pasting the
  config** so the policy names the real one.
- **Not allowed, on purpose:** reCAPTCHA (`www.google.com/recaptcha`). Firebase only uses
  it if "reCAPTCHA protection" is switched on for sign-in in the console. If it ever is,
  the policy needs `https://www.google.com/recaptcha/` and
  `https://www.gstatic.com/recaptcha/` in `script-src` and `https://www.google.com` in
  `frame-src`. The same for Cloudflare Web Analytics (`static.cloudflareinsights.com`):
  leave it off, as the privacy notice promises no tracking.
- **Tested:** every page is loaded in Edge under this policy, served with the real
  `_headers`, and any refusal is a failure. A second run puts the pages in Firebase mode
  with a stand-in config: the real SDK loads from gstatic, sign-in and database calls
  leave the page and are answered locally, so no real project is touched. Run again
  with an iPhone user agent, the hidden sign-in frame loads too. The old Playwright
  `wait_for_function` uses `eval` in the page, which the policy refuses; the checker now
  polls with `evaluate` instead.

## 5. Caching

| Files | Cache-Control | Why |
|--|--|--|
| HTML, `data/`, transcripts, `config.js` | Pages' default: check each time | Changes show at once; a `304` costs almost nothing. |
| `js/inline/*` | one year, `immutable` | Named by their content: a change makes a new name. |
| Audio (`clips/`, `recordings/*/audio/`) | one day | Names don't change when a clip is re-cut, so a returning visitor may hear the old cut for up to a day after an update. Saves worker runs. |

The other scripts and styles (`js/site.js`, `css/site.css`) keep the default, because
their names don't change.

## 6. Domains and HTTPS

- **pages.dev:** HTTPS comes with it. The whole `.dev` top-level domain is on browsers'
  HSTS preload list, so browsers never use plain HTTP there [13].
- **Your own domain** [14]:
  - An apex domain (`example.com`) must be a zone on the same Cloudflare account, using
    Cloudflare's nameservers. Buying it from Cloudflare's registrar does that.
  - A subdomain (`asr.example.com`) only needs a CNAME to `<project>.pages.dev`. Add the
    domain in Pages first; a CNAME made by hand first gives error 522.
  - CAA records that don't allow Cloudflare's certificate authorities stop it working.
  - How long the certificate takes is not stated (not verified; usually minutes).
  - In the zone, turn on **SSL/TLS > Edge Certificates > Always Use HTTPS** (not
    re-checked for this note).
  - To send `<project>.pages.dev` visitors to your own domain, Cloudflare suggests a
    Bulk Redirect at account level [14]. Optional.
- **Firebase authorised domains** [10]:
  - **Authentication > Settings > Authorized domains.** Add `<project>.pages.dev` and your
    own domain.
  - For this site it matters for the email links: the confirmation email's link back to
    `account.html` must be on an authorised domain [10].
  - **`localhost` is no longer there by default** for projects made after 28 April 2025.
    Add it by hand to test with the real Firebase on the laptop; Google advises removing
    it again from a project in real use.
  - The list takes whole domain names, so each preview address
    (`<hash>.<project>.pages.dev`) would need its own entry (no source found on
    wildcards; not verified). Test sign-in on the main address.

## 7. Public-site basics

| Item | Before | Now |
|--|--|--|
| Page titles | All there | Checked unique (`check_public.py`). |
| Descriptions | None | One per page, in `DESCRIPTIONS` in `build_public.py`. |
| `noindex` | — | `admin.html` and `404.html`. |
| `robots.txt` | None | Allows everything. |
| Icon | None; browsers' `/favicon.ico` hit the 404 | `favicon.svg`, with `/favicon.ico` redirected to it in `_redirects`. |
| Credits, privacy, terms | In every footer | Plus a **Contact** link to `privacy.html#contact-us`. Checked on all 18 pages and the 404. |
| Contact | "the address given on this site" when empty | A Contact section. With `contactEmail` empty it says so and points to self-service deletion. **Noah decides the address.** |
| Data-retention date | "when the study ends" | "by [date not set yet]". **Noah decides the date.** The build prints a reminder until it is set. |
| Privacy notice from sign-up | Linked | Checked. |
| Language, one `<h1>`, labels, alt text, named buttons and links | — | Checked on every page. All passed. |
| Contrast | Whisper's name (4.35 to 1) and the "full" label (4.36) a little under 4.5 in light mode | Both a shade darker on the public site (`public.css`). Checked on every page, light and dark, by a simple script (text on solid colours only; not a full audit like axe). |
| Keyboard | — | Tab reaches the rating page's play button and Save. Checked. Not a full keyboard audit. |

Not done, to keep it plain: Open Graph cards, a sitemap, self-hosted fonts, an
accessibility audit with a dedicated tool.

## 8. Auth and database notes (not changed here)

Another review covers authentication. Noticed in passing:

- The `localhost` change above. With the real config on the laptop, sign-up will fail at
  the confirmation-email step until `localhost` is added (the account is made, the email
  is refused). On the public address it works once the domain is added.
- Optional hardening not in the setup yet: restrict the Firebase browser API key to the
  site's addresses in Google Cloud's credentials page, and Firebase App Check. Neither is
  required. The rules are what protect the data.

## Sources

1. Cloudflare Pages, Direct Upload: https://developers.cloudflare.com/pages/get-started/direct-upload/
2. Cloudflare Pages, Serving Pages: https://developers.cloudflare.com/pages/configuration/serving-pages/
3. Cloudflare Pages, Limits: https://developers.cloudflare.com/pages/platform/limits/
4. Cloudflare Pages, Headers: https://developers.cloudflare.com/pages/configuration/headers/
5. Cloudflare Pages Functions, Routing (`_routes.json`, fail open): https://developers.cloudflare.com/pages/functions/routing/
6. Cloudflare Workers static assets, HTML handling: https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/
7. Cloudflare Pages Functions, Advanced mode: https://developers.cloudflare.com/pages/functions/advanced-mode/
8. Projects that hit the range problem on Pages (community, not Cloudflare): https://github.com/albert429/Bible150/pull/6, https://github.com/tilakpatell/tilakpatell.com/pull/1187, https://github.com/lorenzolewis/te-falado/issues/2
9. Safari and range requests (community): https://dev.to/philnash/service-workers-beware-safaris-range-request-38i7, https://answers.netlify.com/t/add-support-for-range-header-for-large-media-files/5733
10. Firebase, email link sign-in (authorised domains, localhost since 28 April 2025): https://firebase.google.com/docs/auth/web/email-link-auth
11. Cloudflare Pages Functions, Pricing: https://developers.cloudflare.com/pages/functions/pricing/
12. Astro's Cloudflare adapter README (uses `_worker.js` with `_routes.json`): https://github.com/withastro/astro/tree/main/packages/integrations/cloudflare
13. The `.dev` domain and HSTS preloading: https://get.dev/ and https://hstspreload.org/
14. Cloudflare Pages, Custom domains: https://developers.cloudflare.com/pages/configuration/custom-domains/
15. Firebase SDK 12.19.0, read for the addresses it calls: https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js and `firebase-firestore.js`

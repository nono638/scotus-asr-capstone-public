// Runs on Cloudflare Pages in front of the audio, and only the audio: public/_routes.json
// sends /clips/* and /recordings/<data set>/audio/* here; every other address is
// served by Pages directly. (tools/build_public.py copies this file to public/.)
//
// Why: Pages answers a request for part of a file ("Range: bytes=...") with the whole
// file and status 200. A browser then can't jump to the middle of a clip, so a card's
// clip would start from 0 seconds, and Safari on an iPhone may not play it at all.
// This answers such a request with just the bytes asked for (status 206), the way an
// ordinary web server does. It needs no settings.
//
// If the free allowance of worker runs (100,000 a day) is ever used up, Pages can
// "fail open" and serve the audio directly again: it plays, but can't jump.
// tools/check_public.py runs this file in Edge (as a service worker) and checks it.

const TYPES = { mp3: "audio/mpeg", ogg: "audio/ogg" };
const KEEP_FOR = "public, max-age=86400";   // a day, as in _headers

// "bytes=a-b", "bytes=a-" or "bytes=-n" -> [first, last], "bad" if it can't be met,
// or null for anything else (several ranges, other units), which gets the whole file.
function parseRange(header, size) {
  const m = /^bytes=(\d*)-(\d*)$/.exec((header || "").trim());
  if (!m || (m[1] === "" && m[2] === "")) return null;
  let first, last;
  if (m[1] === "") {                       // the last n bytes
    const n = Number(m[2]);
    if (n === 0) return "bad";
    first = Math.max(0, size - n);
    last = size - 1;
  } else {
    first = Number(m[1]);
    last = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
    if (m[2] !== "" && Number(m[2]) < first) return null;
  }
  if (first >= size) return "bad";
  return [first, last];
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const type = TYPES[url.pathname.split(".").pop().toLowerCase()];
    if (!type || !["GET", "HEAD"].includes(request.method)) return env.ASSETS.fetch(request);

    // Ask Pages for the whole file, keeping If-None-Match so a cached copy still gets a 304.
    const ask = new Headers(request.headers);
    ask.delete("Range");
    ask.delete("If-Range");
    const asset = await env.ASSETS.fetch(new Request(url.toString(), { method: "GET", headers: ask }));
    if (asset.status !== 200) return asset;   // 304, 404 and the like, as they are

    const headers = new Headers(asset.headers);
    headers.set("Content-Type", type);
    headers.set("Accept-Ranges", "bytes");
    headers.set("Cache-Control", KEEP_FOR);
    const head = request.method === "HEAD";

    // If-Range: only send part of the file if it is still the version the browser has.
    const ifRange = request.headers.get("If-Range");
    const wanted = ifRange && ifRange !== asset.headers.get("ETag") ? null : request.headers.get("Range");
    if (!wanted) return new Response(head ? null : asset.body, { status: 200, headers });

    const body = await asset.arrayBuffer();
    const size = body.byteLength;
    const range = parseRange(wanted, size);
    if (range === null) {
      headers.set("Content-Length", String(size));
      return new Response(head ? null : body, { status: 200, headers });
    }
    if (range === "bad") {
      headers.set("Content-Range", `bytes */${size}`);
      headers.delete("Content-Length");
      return new Response(null, { status: 416, headers });
    }
    const [first, last] = range;
    headers.set("Content-Range", `bytes ${first}-${last}/${size}`);
    headers.set("Content-Length", String(last - first + 1));
    return new Response(head ? null : body.slice(first, last + 1), { status: 206, headers });
  },
};

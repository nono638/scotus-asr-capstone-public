// The public site's settings: the one file to fill in (hosting/SETUP.md, step 6).
// tools/build_public.py copies it to public/config.js.
//
// The Firebase web config is not a secret: every visitor's browser gets it, and what
// they may do is decided by hosting/firestore.rules. Paste it from the Firebase
// console (Project settings > Your apps > Web app > SDK setup and configuration > Config).
//
// While apiKey is empty the pages run in TEST MODE on localhost (a pretend backend in
// the browser) and say "accounts are not switched on yet" anywhere else.
window.SITE_CONFIG = {
  firebase: {
    apiKey: "",
    authDomain: "",
    projectId: "",
    storageBucket: "",
    messagingSenderId: "",
    appId: "",
  },

  // Where people write to have their account and ratings deleted (the privacy page).
  // Cloudflare's free email forwarding works for this (SETUP.md, step 11).
  contactEmail: "",

  // The optional question "Which fits you best: court reporter, captioner or
  // transcriber, linguist, other?". Keep this false until CUNY's HRPP has answered
  // (going-public.md, section 3): it is information about the person.
  askBackground: false,
};

// Accounts and ratings for the public site, in one place, so every page uses the
// same calls. Two backends behind the same functions:
//
//   firebase  Firebase Authentication and Firestore, loaded from gstatic's CDN. Used
//             once hosting/firebase-config.js has an apiKey.
//   test      A pretend backend kept in this browser's localStorage. Used on
//             localhost while there is no Firebase config, or with ?test in the
//             address. It copies the checks in hosting/firestore.rules (the gate,
//             email checking, the admin), so the pages can be tried without a
//             Firebase project. Nothing leaves the computer.
//   off       No config and not on localhost: the pages say accounts are not on yet.
//
// Every call returns a promise. Errors are thrown as {code, message}, with the
// message in plain words for the page to show.

const Backend = (() => {
  const CFG = window.SITE_CONFIG || {};
  const FIREBASE_VERSION = "12.19.0";
  const GUIDELINES = "0.2";
  const LICENCE = { scotus: "CC BY 4.0", edacc: "CC BY-SA 4.0", coraal: "CC BY-NC-SA 4.0" };
  const FEATURES = ["overlap", "stumble", "name", "number", "written", "soundalike", "small", "oneside", "none", "cant_tell"];
  const WHO = ["record", "engine", "both", "neither", "cant_tell"];
  const RECORD = ["yes", "no", "unsure"];
  const FROM = ["queue", "card", "data", "mine", "link"];
  const PLAYED = ["short", "long", "word"];
  const BACKGROUNDS = ["court_reporter", "transcriber", "linguist", "other"];

  const local = ["localhost", "127.0.0.1"].includes(location.hostname);
  const configured = !!(CFG.firebase && CFG.firebase.apiKey);
  let askedForTest = false;
  try {
    if (/[?&]test\b/.test(location.search)) sessionStorage.setItem("site.test", "1");
    askedForTest = sessionStorage.getItem("site.test") === "1";
  } catch (e) { /* storage blocked */ }
  const mode = local && (!configured || askedForTest) ? "test" : configured ? "firebase" : "off";

  const fail = (code, message) => { const e = new Error(message); e.code = code; e.ours = true; return e; };
  const GATE_MESSAGE = "Saving ratings is open only to invited testers for now, while CUNY's research office reviews the study. Your answers were not saved. You can still listen and look around.";

  // The same checks as validRating() in hosting/firestore.rules, so a page finds a
  // mistake before the database does.
  function checkRating(caseId, corpus, a) {
    const bad = [];
    if (!/^[a-z][0-9]{5,6}$/.test(caseId)) bad.push("case");
    if (!LICENCE[corpus]) bad.push("corpus");
    if (!Array.isArray(a.features) || a.features.length > 10 || a.features.some(f => !FEATURES.includes(f))) bad.push("features");
    if (!WHO.includes(a.who_right)) bad.push("who_right");
    if (!RECORD.includes(a.record_right)) bad.push("record_right");
    if (typeof a.corrected !== "string" || a.corrected.length > 2000) bad.push("corrected");
    if (typeof a.feedback !== "string" || a.feedback.length > 2000) bad.push("feedback");
    if (!Array.isArray(a.played) || a.played.length > 3 || a.played.some(p => !PLAYED.includes(p))) bad.push("played");
    if (!FROM.includes(a.came_from)) bad.push("came_from");
    if (bad.length) throw fail("invalid", "Something in the answer isn't in the right form (" + bad.join(", ") + ").");
    return {
      uid: null, case: caseId, corpus, licence: LICENCE[corpus], guidelines: GUIDELINES, came_from: a.came_from,
      features: a.features, who_right: a.who_right, record_right: a.record_right,
      corrected: a.corrected, feedback: a.feedback, played: a.played,
    };
  }
  function checkProfile(p) {
    const name = String(p.displayName || "").trim();
    if (name.length < 1 || name.length > 40) throw fail("invalid", "A display name needs 1 to 40 characters.");
    const out = { displayName: name };
    if (p.background) {
      if (!BACKGROUNDS.includes(p.background)) throw fail("invalid", "That background isn't one of the choices.");
      out.background = p.background;
    }
    return out;
  }

  // ---------------------------------------------------------------------------
  // The test backend
  // ---------------------------------------------------------------------------
  function testBackend() {
    const KEY = "site.testBackend";
    const empty = () => ({ users: {}, profiles: {}, ratings: {}, counts: {}, mail: [], session: null,
                           config: { open_to_public: false, admins: [], allowlist: [] } });
    let memory = null;   // used when localStorage is blocked
    const load = () => {
      try { const v = localStorage.getItem(KEY); return v ? JSON.parse(v) : empty(); }
      catch (e) { return memory || (memory = empty()); }
    };
    const save = db => { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) { memory = db; } };
    const listeners = [];
    const userOf = db => {
      const uid = db.session;
      if (!uid) return null;
      const u = Object.values(db.users).find(x => x.uid === uid);
      return u ? { uid: u.uid, email: u.email, verified: u.verified } : null;
    };
    const tell = () => { const u = userOf(load()); listeners.forEach(cb => cb(u)); };
    const later = v => new Promise(r => setTimeout(() => r(v), 30));
    const need = db => { const u = userOf(db); if (!u) throw fail("signed-out", "Please sign in first."); return u; };
    const now = () => new Date().toISOString();
    const isAdmin = (db, u) => !!u && db.config.admins.includes(u.uid);
    const mayRate = (db, u) => !!u && u.verified && (db.config.open_to_public || db.config.allowlist.includes(u.uid));

    return {
      onUser(cb) { listeners.push(cb); later().then(() => cb(userOf(load()))); },
      async signUp(email, password, displayName) {
        const db = load();
        email = String(email).trim().toLowerCase();
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw fail("auth/invalid-email", "That doesn't look like an email address.");
        if (db.users[email]) throw fail("auth/email-already-in-use", "There is already an account with that email. Try signing in, or reset the password.");
        if (String(password).length < 8) throw fail("auth/weak-password", "Please use a password of at least 8 characters.");
        const profile = checkProfile({ displayName });
        const uid = "test" + Math.random().toString(36).slice(2, 12);
        db.users[email] = { uid, email, password, verified: false };
        db.profiles[uid] = { ...profile, updated: now() };
        db.session = uid;
        db.mail.push({ to: email, kind: "verify", at: now() });
        save(db); tell();
        return later(userOf(db));
      },
      async signIn(email, password) {
        const db = load();
        const u = db.users[String(email).trim().toLowerCase()];
        if (!u || u.password !== password) throw fail("auth/invalid-credential", "That email and password don't match an account.");
        db.session = u.uid; save(db); tell();
        return later(userOf(db));
      },
      async signOut() { const db = load(); db.session = null; save(db); tell(); return later(); },
      async resetPassword(email) {
        const db = load();
        email = String(email).trim().toLowerCase();
        // Firebase says the same thing whether or not the account exists.
        if (db.users[email]) db.mail.push({ to: email, kind: "reset", at: now() });
        save(db); tell(); return later();
      },
      async resendVerification() {
        const db = load(); const u = need(db);
        db.mail.push({ to: u.email, kind: "verify", at: now() }); save(db); tell(); return later();
      },
      async refresh() { return later(userOf(load())); },
      async getProfile() { const db = load(); const u = need(db); return later(db.profiles[u.uid] || null); },
      async saveProfile(p) {
        const db = load(); const u = need(db);
        db.profiles[u.uid] = { ...checkProfile(p), updated: now() }; save(db); return later();
      },
      async isOpen() { return later(!!load().config.open_to_public); },
      async getRating(caseId) { const db = load(); const u = need(db); return later(db.ratings[u.uid + "__" + caseId] || null); },
      async myRatings() {
        const db = load(); const u = need(db);
        return later(Object.values(db.ratings).filter(r => r.uid === u.uid));
      },
      async saveRating(caseId, corpus, answer) {
        const db = load(); const u = need(db);
        const d = checkRating(caseId, corpus, answer);
        if (!u.verified) throw fail("unverified", "Please confirm your email address first: use the link in the email we sent.");
        if (!mayRate(db, u)) throw fail("gate", GATE_MESSAGE);
        const id = u.uid + "__" + caseId;
        const old = db.ratings[id];
        db.ratings[id] = { ...d, uid: u.uid, created: old ? old.created : now(), updated: now() };
        if (!old) db.counts[caseId] = (db.counts[caseId] || 0) + 1;
        save(db);
        return later({ created: !old });
      },
      async counts() { const db = load(); need(db); return later({ ...db.counts }); },
      async isAdmin() { const db = load(); return later(isAdmin(db, userOf(db))); },
      async allRatings() {
        const db = load(); const u = need(db);
        if (!isAdmin(db, u)) throw fail("permission-denied", "Only the site's admin can see everyone's ratings.");
        return later(Object.entries(db.ratings).map(([id, r]) => ({ id, ...r })));
      },
      async deleteEverything(password) {
        const db = load(); const u = need(db);
        if (db.users[u.email].password !== password) throw fail("auth/invalid-credential", "That password isn't right.");
        for (const [id, r] of Object.entries(db.ratings)) if (r.uid === u.uid) {
          delete db.ratings[id];
          db.counts[r.case] = (db.counts[r.case] || 1) - 1;
        }
        delete db.profiles[u.uid];
        delete db.users[u.email];
        db.session = null;
        save(db); tell();
        return later();
      },
      // Only in test mode: the switches the banner shows, and the pretend inbox.
      test: {
        state() { const db = load(); const u = userOf(db); return { user: u, config: db.config, mail: db.mail.slice(-3) }; },
        set(key, on) {
          const db = load(); const u = userOf(db);
          if (key === "open_to_public") db.config.open_to_public = on;
          else if (u) {
            const list = db.config[key === "admin" ? "admins" : "allowlist"];
            const i = list.indexOf(u.uid);
            if (on && i < 0) list.push(u.uid);
            if (!on && i >= 0) list.splice(i, 1);
          }
          save(db); tell();
        },
        clickVerifyLink() {
          const db = load(); const u = userOf(db);
          // Like Firebase, nothing tells the page; it finds out when it asks (refresh).
          if (u) { db.users[u.email].verified = true; save(db); }
        },
        wipe() { save(empty()); tell(); },
      },
    };
  }

  // ---------------------------------------------------------------------------
  // The Firebase backend
  // ---------------------------------------------------------------------------
  function firebaseBackend() {
    const base = `https://www.gstatic.com/firebasejs/${FIREBASE_VERSION}/`;
    const sdk = Promise.all([import(base + "firebase-app.js"), import(base + "firebase-auth.js"), import(base + "firebase-firestore.js")])
      .then(([app, auth, fs]) => {
        const a = app.initializeApp(CFG.firebase);
        return { A: auth, F: fs, auth: auth.getAuth(a), db: fs.getFirestore(a) };
      });
    const plainAuth = {
      "auth/email-already-in-use": "There is already an account with that email. Try signing in, or reset the password.",
      "auth/invalid-email": "That doesn't look like an email address.",
      "auth/weak-password": "Please use a password of at least 8 characters.",
      "auth/invalid-credential": "That email and password don't match an account.",
      "auth/wrong-password": "That email and password don't match an account.",
      "auth/user-not-found": "That email and password don't match an account.",
      "auth/too-many-requests": "Too many tries. Please wait a few minutes and try again.",
      "auth/network-request-failed": "The network didn't answer. Are you online?",
      "auth/requires-recent-login": "Please sign out, sign in again, and then try once more.",
    };
    const wrap = e => {
      if (e && e.code && plainAuth[e.code]) return fail(e.code, plainAuth[e.code]);
      if (e && e.code === "permission-denied") return fail("permission-denied", "The database said no to that.");
      return fail((e && e.code) || "error", (e && e.message) || String(e));
    };
    const call = async f => { try { return await f(await sdk); } catch (e) { throw e && e.ours ? e : wrap(e); } };
    const userOf = u => u ? { uid: u.uid, email: u.email, verified: u.emailVerified } : null;
    const need = s => { if (!s.auth.currentUser) throw fail("signed-out", "Please sign in first."); return s.auth.currentUser; };
    const iso = v => v && v.toDate ? v.toDate().toISOString() : v;
    const plain = d => { const x = d.data(); return { ...x, created: iso(x.created), updated: iso(x.updated) }; };
    const verifyLink = () => ({ url: new URL("account.html", location.href.replace(/\/recordings\/[^/]+\/.*$/, "/")).href });

    return {
      onUser(cb) { sdk.then(s => s.A.onAuthStateChanged(s.auth, u => cb(userOf(u)))).catch(() => cb(null)); },
      signUp: (email, password, displayName) => call(async s => {
        const profile = checkProfile({ displayName });
        const cred = await s.A.createUserWithEmailAndPassword(s.auth, String(email).trim(), password);
        await s.F.setDoc(s.F.doc(s.db, "users", cred.user.uid), { ...profile, updated: s.F.serverTimestamp() });
        await s.A.sendEmailVerification(cred.user, verifyLink());
        return userOf(cred.user);
      }),
      signIn: (email, password) => call(async s => userOf((await s.A.signInWithEmailAndPassword(s.auth, String(email).trim(), password)).user)),
      signOut: () => call(s => s.A.signOut(s.auth)),
      resetPassword: email => call(s => s.A.sendPasswordResetEmail(s.auth, String(email).trim())),
      resendVerification: () => call(s => s.A.sendEmailVerification(need(s), verifyLink())),
      // After the email link is clicked: reload the user, and get a new token so the
      // database sees email_verified too.
      refresh: () => call(async s => {
        const u = s.auth.currentUser;
        if (!u) return null;
        await s.A.reload(u);
        await u.getIdToken(true);
        return userOf(s.auth.currentUser);
      }),
      getProfile: () => call(async s => {
        const snap = await s.F.getDoc(s.F.doc(s.db, "users", need(s).uid));
        return snap.exists() ? plain(snap) : null;
      }),
      saveProfile: p => call(s => s.F.setDoc(s.F.doc(s.db, "users", need(s).uid), { ...checkProfile(p), updated: s.F.serverTimestamp() })),
      isOpen: () => call(async s => {
        const snap = await s.F.getDoc(s.F.doc(s.db, "config", "public"));
        return snap.exists() && snap.data().open_to_public === true;
      }),
      getRating: caseId => call(async s => {
        const snap = await s.F.getDoc(s.F.doc(s.db, "ratings", need(s).uid + "__" + caseId));
        return snap.exists() ? plain(snap) : null;
      }),
      myRatings: () => call(async s => {
        const q = s.F.query(s.F.collection(s.db, "ratings"), s.F.where("uid", "==", need(s).uid));
        return (await s.F.getDocs(q)).docs.map(plain);
      }),
      saveRating: (caseId, corpus, answer) => call(async s => {
        const u = need(s);
        const d = { ...checkRating(caseId, corpus, answer), uid: u.uid };
        if (!u.emailVerified) throw fail("unverified", "Please confirm your email address first: use the link in the email we sent.");
        const ref = s.F.doc(s.db, "ratings", u.uid + "__" + caseId);
        const old = await s.F.getDoc(ref);
        const batch = s.F.writeBatch(s.db);
        if (old.exists()) {
          batch.update(ref, { ...d, updated: s.F.serverTimestamp() });
        } else {
          batch.set(ref, { ...d, created: s.F.serverTimestamp(), updated: s.F.serverTimestamp() });
          batch.set(s.F.doc(s.db, "stats", "counts"), { n: { [caseId]: s.F.increment(1) }, last: caseId }, { merge: true });
        }
        try { await batch.commit(); }
        catch (e) { if (e.code === "permission-denied") throw fail("gate", GATE_MESSAGE); throw e; }
        return { created: !old.exists() };
      }),
      counts: () => call(async s => {
        need(s);
        const snap = await s.F.getDoc(s.F.doc(s.db, "stats", "counts"));
        return snap.exists() ? (snap.data().n || {}) : {};
      }),
      // Only an admin may read config/access, so trying is the test.
      isAdmin: () => call(async s => {
        if (!s.auth.currentUser) return false;
        try { await s.F.getDoc(s.F.doc(s.db, "config", "access")); return true; } catch (e) { return false; }
      }),
      allRatings: () => call(async s => {
        need(s);
        return (await s.F.getDocs(s.F.collection(s.db, "ratings"))).docs.map(d => ({ id: d.id, ...plain(d) }));
      }),
      deleteEverything: password => call(async s => {
        const u = need(s);
        await s.A.reauthenticateWithCredential(u, s.A.EmailAuthProvider.credential(u.email, password));
        const q = s.F.query(s.F.collection(s.db, "ratings"), s.F.where("uid", "==", u.uid));
        for (const d of (await s.F.getDocs(q)).docs) {
          // One batch per rating: the rules let the count change for one case at a time.
          const b = s.F.writeBatch(s.db);
          b.delete(d.ref);
          b.set(s.F.doc(s.db, "stats", "counts"), { n: { [d.data().case]: s.F.increment(-1) }, last: d.data().case }, { merge: true });
          await b.commit();
        }
        await s.F.deleteDoc(s.F.doc(s.db, "users", u.uid));
        await s.A.deleteUser(u);
      }),
    };
  }

  function offBackend() {
    const no = () => Promise.reject(fail("off", "Accounts are not switched on yet on this site."));
    return {
      onUser(cb) { setTimeout(() => cb(null), 0); },
      signUp: no, signIn: no, signOut: no, resetPassword: no, resendVerification: no, refresh: () => Promise.resolve(null),
      getProfile: no, saveProfile: no, isOpen: () => Promise.resolve(false), getRating: no, myRatings: no,
      saveRating: no, counts: () => Promise.resolve({}), isAdmin: () => Promise.resolve(false), allRatings: no, deleteEverything: no,
    };
  }

  const impl = mode === "test" ? testBackend() : mode === "firebase" ? firebaseBackend() : offBackend();
  return { mode, LICENCE, FEATURES, GATE_MESSAGE, askBackground: !!CFG.askBackground, contactEmail: CFG.contactEmail || "", ...impl };
})();

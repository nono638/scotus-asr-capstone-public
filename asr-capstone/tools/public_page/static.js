// The plain pages (privacy, contributor terms, credits): the bar across the top,
// the contributor line and the contact address.
siteNav($("#nav"), D.pages, D.current);
const contrib = $("#contrib");
if (contrib) contrib.textContent = window.CONTRIBUTOR_LINE;
const contact = $("#contact");
if (contact && Backend.contactEmail) contact.replaceChildren(el("a", { href: "mailto:" + Backend.contactEmail }, Backend.contactEmail));

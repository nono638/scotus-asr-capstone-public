"""Reading the Court's per-term listing pages to find out what exists.

The Court publishes one page per term listing that term's arguments, one for
transcripts and one for audio:

    /oral_arguments/argument_transcript/2024
    /oral_arguments/argument_audio/2024

Both are plain tables of links. **Every address used anywhere in this module is
read off one of those pages, never built from a docket number.** That is not
tidiness, it is the difference between a correct corpus and a silently wrong one,
and it costs an extra request per case:

  - Transcript PDFs carry an arbitrary suffix - `24-316_1a72.pdf` - so there is
    no pattern to construct.
  - Audio rows link to a landing page, not the recording, so the MP3 takes a
    second hop.
  - Louisiana v. Callais was argued twice. Its 2025 row points at `24-109_2`,
    and the landing page at plain `24-109` exists but carries no recording at
    all. Guessing the obvious name gets you a page with nothing on it, or worse,
    in other terms, the wrong argument paired with the right transcript and
    nothing anywhere reporting an error.

The one sanity check that matters is that the page served is the page asked for.
The 2017-term audio index is known to serve the current term's list instead, and
a scraper that trusts it collects the same arguments over and over under the
wrong term. So every row's argument date is checked against the term it was
supposed to come from, and rows that do not belong are dropped with a warning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .web import PoliteSession

BASE = "https://www.supremecourt.gov/oral_arguments/"

#: A docket number as the Court writes it: `24-316`, `09-834`, or `22A901` for
#: an application. The listing puts it at the start of the case cell.
DOCKET = re.compile(r"^\s*(\d{2}[-A]\w+)\s+(.*)$")


@dataclass(frozen=True)
class ArgumentLink:
    """One row of a listing page.

    Attributes:
        docket: The Court's docket number.
        case_name: The case as the listing names it.
        argued: Date of argument.
        url: Where the row points - a PDF for transcripts, a landing page for
            audio. Read from the page, never constructed.
    """

    docket: str
    case_name: str
    argued: date | None
    url: str


@dataclass
class TermListing:
    """What one term's listing page turned out to contain.

    Attributes:
        term: The October Term, as a four-digit year.
        kind: `transcript` or `audio`.
        links: Rows that belong to this term.
        rejected: Rows whose argument date falls outside the term, which is how
            a page serving the wrong term's content gives itself away.
        warnings: Anything worth knowing that did not stop the parse.
    """

    term: int
    kind: str
    links: list[ArgumentLink] = field(default_factory=list)
    rejected: list[ArgumentLink] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def term_window(term: int) -> tuple[date, date]:
    """First and last plausible argument date for an October Term.

    The term opens on the first Monday in October and arguments run into the
    following summer, so anything from 1 October to 30 September belongs.

    Args:
        term: The October Term, e.g. 2024.

    Returns:
        `(earliest, latest)` argument date.
    """
    return date(term, 10, 1), date(term + 1, 9, 30)


def _parse_date(text: str) -> date | None:
    """Read `MM/DD/YY` as the listing writes it."""
    try:
        return datetime.strptime(text.strip(), "%m/%d/%y").date()
    except ValueError:
        return None


def parse_listing(html: str, term: int, kind: str) -> TermListing:
    """Pull the argument rows out of one listing page.

    Args:
        html: The page.
        term: Which term it was asked for.
        kind: `transcript` or `audio`, used only for reporting.

    Returns:
        The rows that belong to this term, and the ones that do not.
    """
    listing = TermListing(term=term, kind=kind)
    earliest, latest = term_window(term)
    soup = BeautifulSoup(html, "html.parser")

    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        anchor = cells[0].find("a", href=True)
        if anchor is None:
            continue

        match = DOCKET.match(cells[0].get_text(" ", strip=True))
        if match is None:
            continue

        docket, case_name = match.group(1), match.group(2).strip()
        argued = _parse_date(cells[1].get_text(" ", strip=True))

        link = ArgumentLink(
            docket=docket,
            case_name=case_name,
            argued=argued,
            # Resolved against the page it came from, so a relative href like
            # `../audio/2025/24-109_2` becomes a real address.
            url=urljoin(f"{BASE}{'argument_transcript' if kind == 'transcript' else 'argument_audio'}/{term}", anchor["href"]),
        )

        if argued is not None and not (earliest <= argued <= latest):
            listing.rejected.append(link)
        else:
            listing.links.append(link)

    if listing.rejected:
        listing.warnings.append(
            f"{len(listing.rejected)} of {len(listing.rejected) + len(listing.links)} rows on the "
            f"{term} {kind} page were argued outside October Term {term}. The page is probably "
            f"serving a different term - this is known to happen to the 2017 audio index."
        )
    if not listing.links:
        listing.warnings.append(f"No usable rows found on the {term} {kind} page.")

    return listing


def fetch_listing(session: PoliteSession, term: int, kind: str) -> TermListing:
    """Fetch and parse one term's listing page.

    Args:
        session: The polite client to fetch with.
        term: The October Term.
        kind: `transcript` or `audio`.

    Returns:
        What the page contained.

    Raises:
        ValueError: If `kind` is not one of the two page types.
    """
    if kind not in ("transcript", "audio"):
        raise ValueError(f"kind should be 'transcript' or 'audio', not {kind!r}")

    path = "argument_transcript" if kind == "transcript" else "argument_audio"
    return parse_listing(session.text(f"{BASE}{path}/{term}"), term, kind)


def resolve_audio(session: PoliteSession, landing_url: str) -> str | None:
    """Follow an audio row to the recording itself.

    The listing links to a page about the argument; the MP3 is named on that
    page. Cases with no recording posted give a page with no MP3 on it, which is
    a real answer rather than an error.

    Args:
        session: The polite client to fetch with.
        landing_url: The address from the audio listing row.

    Returns:
        The recording's address, or None if the page names no recording.
    """
    soup = BeautifulSoup(session.text(landing_url), "html.parser")

    for tag in soup.find_all(["source", "a"]):
        for attribute in ("src", "href"):
            value = tag.get(attribute)
            if value and value.lower().endswith(".mp3"):
                return urljoin(landing_url, value)

    return None


#: How the Court marks the recording of a reargument. Both spellings appear:
#: `13-7120rearg` in 2014, `17-647rehearing` in the 2018 transcript name.
REARGUMENT = re.compile(r"(rearg|rehearing)", re.IGNORECASE)


def audio_by_case_page(
    session: PoliteSession, term: int, docket: str
) -> list[str]:
    """Find a case's recordings from its own audio page, not the term listing.

    A fallback, used only when a term's audio listing is unusable. OT2017's is:
    it serves the current term's list, so there are no links to read and all 61
    of that term's arguments would otherwise have transcripts and no audio.

    This does construct one address - `audio/<term>/<docket>` - which is the
    thing this module otherwise refuses to do. Three reasons it is acceptable
    here, in order of how much they matter:

    1. It builds the *page*, not the recording. The MP3 address is still read
       off whatever page comes back, so the file is never guessed at.
    2. A wrong guess returns a page naming no recording, rather than the wrong
       recording. Checked against OT2017: `audio/2017/15-1498` names nothing,
       and the reargument's real file sits at `audio/2017/15-1498rearg`. Failure
       is empty, not silently incorrect.
    3. The docket comes from that term's transcript listing, which works fine.
       Nothing here is invented.

    Args:
        session: The polite client to fetch with.
        term: The October Term.
        docket: The Court's docket number.

    Returns:
        Every recording found, first argument first. Empty if there are none.
    """
    found: list[str] = []
    for suffix in ("", "rearg"):
        try:
            mp3 = resolve_audio(
                session, f"{BASE}audio/{term}/{docket}{suffix}"
            )
        except Exception:
            # A missing page is a real answer: this case has no recording of
            # that kind. Anything else worth knowing shows up as a gap in the
            # manifest, which is reported.
            continue
        if mp3 and mp3 not in found:
            found.append(mp3)
    return found


def folder_name(
    term: int, docket: str, case_name: str, argued: date | None = None
) -> str:
    """The directory a case's files live in, matching the sample's layout.

    Args:
        term: The October Term.
        docket: The Court's docket number.
        case_name: The case as the listing names it.
        argued: Include the date, for a case argued more than once in one term.
            Without it both arguments get the same folder and the same filenames
            inside it, so the second download silently overwrites the first.

    Returns:
        A name like `OT2024_24-316_Kennedy_Sec_of_H_HS_v_Braidwood_Mgmt_Inc`.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", case_name).strip("_")
    name = f"OT{term}_{docket}_{slug}"[:100]
    return f"{name}_{argued.isoformat()}" if argued is not None else name


def pair_audio(
    transcripts: list[ArgumentLink], recordings: list[ArgumentLink]
) -> list[tuple[ArgumentLink, ArgumentLink | None]]:
    """Match each transcript of one docket to its own recording.

    Almost always one of each, and then this is trivial. It exists for the cases
    argued twice in a single term - Johnson v. United States in OT2014, Knick v.
    Township of Scott in OT2018 - where there are two of each and getting it
    wrong pairs one argument's audio with the other argument's transcript.

    Pairing by date does not work. The 2014 audio page gives *both* of that
    docket's recordings the date of the first argument, so the reargument's date
    there is simply wrong. What is reliable is that the Court names the
    reargument's recording with a `rearg` or `rehearing` marker and the first
    one without. So both sides are put in argument order - transcripts by date,
    recordings by that marker - and lined up.

    Args:
        transcripts: Every transcript row for one docket in one term.
        recordings: Every audio row for the same docket and term.

    Returns:
        `(transcript, recording or None)` in argument order.
    """
    in_order = sorted(transcripts, key=lambda link: (link.argued is None, link.argued))
    heard = sorted(
        recordings,
        key=lambda link: (bool(REARGUMENT.search(link.url)), link.argued is None, link.argued),
    )
    return [
        (transcript, heard[index] if index < len(heard) else None)
        for index, transcript in enumerate(in_order)
    ]


def assign_case_ids(entries: list[dict]) -> list[str]:
    """Give every entry an identifier that is unique across the whole manifest.

    The pipeline keys everything - output files, ledger rows, result tables - by
    docket number, which is unique within a term and not across them. A case
    reargued in a later term appears twice with the same docket, and the second
    run would quietly overwrite the first.

    Rare but real: Louisiana v. Callais is argued in both OT2024 and OT2025. So
    the docket is kept as the identifier wherever it is unambiguous, and the term
    is appended only where it is not. That keeps 119 of 120 identifiers stable
    and readable, and makes the one collision impossible.

    Args:
        entries: Manifest entries. Modified in place, gaining a `case_id`.

    Returns:
        The identifiers that needed a term appended, for reporting.
    """
    def count(key) -> dict:
        totals: dict = {}
        for entry in entries:
            totals[key(entry)] = totals.get(key(entry), 0) + 1
        return totals

    by_docket = count(lambda entry: entry["docket"])
    by_term = count(lambda entry: (entry["docket"], entry["term"]))

    disambiguated: list[str] = []
    for entry in entries:
        docket, term = entry["docket"], entry["term"]

        if by_docket[docket] == 1:
            entry["case_id"] = docket
            continue

        # Argued in more than one term: the term separates them. Argued twice
        # inside one term - Johnson in OT2014, Knick in OT2018 - and it does not,
        # so the date has to come along too.
        if by_term[(docket, term)] > 1:
            entry["case_id"] = f"{docket}_{entry['argued']}"
        else:
            entry["case_id"] = f"{docket}_OT{term}"
        disambiguated.append(entry["case_id"])

    return disambiguated


def build_term(
    session: PoliteSession, term: int, resolve_mp3: bool = True
) -> tuple[list[dict], list[str]]:
    """Work out what one term contains, as manifest entries.

    Pairs each transcript with its recording by docket number. A case with a
    transcript and no audio is kept with `audio_url` of None - that is the normal
    state of everything before the 2010 term, and the pipeline already treats
    such a case as transcript-only rather than as an error.

    Args:
        session: The polite client to fetch with.
        term: The October Term.
        resolve_mp3: Follow each audio row to its recording. Costs one request
            per case; without it the entry keeps the landing page instead.

    Returns:
        `(entries, warnings)`, entries in the same shape as `sample/manifest.json`.
    """
    transcripts = fetch_listing(session, term, "transcript")
    audio = fetch_listing(session, term, "audio")
    warnings = list(transcripts.warnings) + list(audio.warnings)

    spoken: dict[str, list[ArgumentLink]] = {}
    for link in audio.links:
        spoken.setdefault(link.docket, []).append(link)

    written: dict[str, list[ArgumentLink]] = {}
    for link in transcripts.links:
        written.setdefault(link.docket, []).append(link)

    # The term listing gave nothing usable but the transcripts did, so the audio
    # page for this term is broken rather than the term being audio-less. Go to
    # each case's own page instead. Costs one request per case and rescues a
    # whole term.
    by_case_page = bool(written) and not spoken
    if by_case_page:
        warnings.append(
            f"OT{term}: the audio listing named no arguments for this term, so "
            f"each case's own audio page was read instead ({len(written)} extra "
            f"requests). Recordings found this way are still read off a page, "
            f"never constructed."
        )

    entries: list[dict] = []

    for docket, rows in written.items():
        recordings = spoken.get(docket, [])
        argued_twice = len(rows) > 1

        # Already real MP3 addresses when they come from a case page, so they
        # skip the resolve step below.
        from_case_page: list[str] = []
        if by_case_page and resolve_mp3:
            from_case_page = audio_by_case_page(session, term, docket)
            if not from_case_page:
                warnings.append(f"{docket}: no recording on its own audio page either.")

        if argued_twice:
            warnings.append(
                f"{docket}: argued {len(rows)} times in OT{term}, with "
                f"{len(recordings) or len(from_case_page)} recording(s). "
                f"Paired in argument order."
            )

        in_order = sorted(rows, key=lambda link: (link.argued is None, link.argued))
        paired = (
            [(link, None) for link in in_order]
            if by_case_page
            else pair_audio(rows, recordings)
        )

        for index, (link, heard) in enumerate(paired):
            audio_url: str | None = None

            if by_case_page:
                audio_url = from_case_page[index] if index < len(from_case_page) else None
            elif heard is not None:
                if resolve_mp3:
                    audio_url = resolve_audio(session, heard.url)
                    if audio_url is None:
                        warnings.append(f"{docket}: the audio page names no recording.")
                else:
                    audio_url = heard.url

            entries.append({
                # The date goes in the folder name only for a case argued more
                # than once in one term, so 1,035 of 1,037 names stay readable.
                "folder": folder_name(
                    term, docket, link.case_name, link.argued if argued_twice else None
                ),
                "docket": docket,
                "case_name": link.case_name,
                "term": term,
                "argued": link.argued.isoformat() if link.argued else "",
                "transcript_url": link.url,
                "audio_url": audio_url,
                "audio_minutes": None,
                "turns": None,
                "spoken_words": None,
            })

    return entries, warnings

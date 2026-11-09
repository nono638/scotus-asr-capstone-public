"""Tests for reading the Court's per-term listing pages.

No network here: the pages are fabricated to the shape the real ones have. The
point is not that the parser handles today's HTML - it is that the two ways this
can go silently wrong are caught.

Both are documented in the scoping work. A URL built from a docket number can
fetch the wrong argument, and the 2017 audio page serves a different term's list
while looking perfectly normal. Neither raises an error on its own.
"""

from __future__ import annotations

from datetime import date

from scotus_asr.corpus.listing import (
    ArgumentLink,
    assign_case_ids,
    folder_name,
    pair_audio,
    parse_listing,
    term_window,
)


def _page(rows: str) -> str:
    """A listing page with the search box the real ones carry above the table."""
    return f"""
    <html><body>
      <table><tr><td>SEARCH TIPS</td><td>ADVANCED SEARCH</td></tr></table>
      <table>
        <tr><th>Oral Argument</th><th>Date Argued</th></tr>
        {rows}
      </table>
    </body></html>
    """


def test_it_reads_docket_name_date_and_link():
    page = _page(
        '<tr><td><a href="../argument_transcripts/2024/24-316_1a72.pdf">'
        "24-316 Kennedy v. Braidwood</a></td><td>04/21/25</td></tr>"
    )

    listing = parse_listing(page, 2024, "transcript")

    assert len(listing.links) == 1
    link = listing.links[0]
    assert link.docket == "24-316"
    assert link.case_name == "Kennedy v. Braidwood"
    assert link.argued == date(2025, 4, 21)
    # The suffix is arbitrary, which is exactly why it has to be read not built.
    assert link.url.endswith("/argument_transcripts/2024/24-316_1a72.pdf")


def test_a_relative_link_becomes_a_real_address():
    page = _page(
        '<tr><td><a href="../audio/2025/24-109_2">24-109 Louisiana v. Callais</a>'
        "</td><td>10/15/25</td></tr>"
    )

    link = parse_listing(page, 2025, "audio").links[0]

    assert link.url == "https://www.supremecourt.gov/oral_arguments/audio/2025/24-109_2"


def test_rows_from_another_term_are_rejected_rather_than_collected():
    """The 2017 audio page serves the current term's list and says nothing.

    Without this check a scraper gathers the same arguments under every term it
    asks for, and the corpus is wrong in a way no error message reports.
    """
    page = _page(
        '<tr><td><a href="../audio/2017/17-530">17-530 Real Case</a></td>'
        "<td>04/16/18</td></tr>"
        '<tr><td><a href="../audio/2017/24-813">24-813 Wrong Term</a></td>'
        "<td>01/12/26</td></tr>"
    )

    listing = parse_listing(page, 2017, "audio")

    assert [link.docket for link in listing.links] == ["17-530"]
    assert [link.docket for link in listing.rejected] == ["24-813"]
    assert listing.warnings


def test_the_search_box_above_the_table_is_not_mistaken_for_an_argument():
    listing = parse_listing(_page(""), 2024, "transcript")

    assert listing.links == []
    assert listing.warnings


def test_a_term_runs_from_october_into_the_following_summer():
    first, last = term_window(2024)

    assert first == date(2024, 10, 1)
    assert last == date(2025, 9, 30)


def test_a_case_argued_in_two_terms_gets_two_identifiers():
    """Louisiana v. Callais is argued in OT2024 and again in OT2025.

    The pipeline keys every output file by this identifier, so leaving both as
    `24-109` means the second run overwrites the first.
    """
    entries = [
        {"docket": "24-109", "term": 2024},
        {"docket": "24-109", "term": 2025},
        {"docket": "24-316", "term": 2024},
    ]

    renamed = assign_case_ids(entries)

    assert [entry["case_id"] for entry in entries] == [
        "24-109_OT2024", "24-109_OT2025", "24-316",
    ]
    assert renamed == ["24-109_OT2024", "24-109_OT2025"]


def test_folder_names_survive_punctuation_in_a_case_name():
    name = folder_name(2024, "24-316", "Kennedy, Sec. of H&HS v. Braidwood Mgmt., Inc.")

    assert name.startswith("OT2024_24-316_Kennedy_Sec_of_H_HS_v_Braidwood")
    assert " " not in name


def _link(docket: str, argued: date, url: str) -> ArgumentLink:
    return ArgumentLink(docket=docket, case_name="A Case", argued=argued, url=url)


def test_one_transcript_and_one_recording_pair_up():
    transcripts = [_link("24-316", date(2025, 4, 21), ".../24-316_1a72.pdf")]
    recordings = [_link("24-316", date(2025, 4, 21), ".../audio/2024/24-316")]

    paired = pair_audio(transcripts, recordings)

    assert len(paired) == 1
    assert paired[0][1].url.endswith("24-316")


def test_a_case_reargued_in_one_term_gets_its_own_recording_each_time():
    """Johnson v. United States, OT2014: argued November, reargued April.

    The audio page gives *both* recordings the November date, so pairing on date
    would hand the same file to both arguments. The `rearg` marker in the URL is
    what actually distinguishes them.
    """
    transcripts = [
        _link("13-7120", date(2015, 4, 20), ".../13-7120_hd1a.pdf"),
        _link("13-7120", date(2014, 11, 5), ".../13-7120_aa7i.pdf"),
    ]
    recordings = [
        _link("13-7120", date(2014, 11, 5), ".../audio/2014/13-7120rearg"),
        _link("13-7120", date(2014, 11, 5), ".../audio/2014/13-7120"),
    ]

    paired = pair_audio(transcripts, recordings)

    first, second = paired
    assert first[0].argued == date(2014, 11, 5)
    assert first[1].url.endswith("/13-7120")
    assert second[0].argued == date(2015, 4, 20)
    assert second[1].url.endswith("rearg")


def test_the_rehearing_spelling_is_recognised_too():
    """Knick v. Township of Scott, OT2018, where the dates are right."""
    transcripts = [
        _link("17-647", date(2019, 1, 16), ".../17-647rehearing_lkgm.pdf"),
        _link("17-647", date(2018, 10, 3), ".../17-647_aplc.pdf"),
    ]
    recordings = [
        _link("17-647", date(2019, 1, 16), ".../audio/2018/17-647rearg"),
        _link("17-647", date(2018, 10, 3), ".../audio/2018/17-647"),
    ]

    paired = pair_audio(transcripts, recordings)

    assert paired[0][1].url.endswith("/17-647")
    assert paired[1][1].url.endswith("rearg")


def test_a_transcript_with_no_recording_pairs_with_nothing():
    paired = pair_audio([_link("99-1", date(2011, 1, 1), ".../a.pdf")], [])

    assert paired == [(paired[0][0], None)]


def test_a_case_argued_twice_in_one_term_needs_the_date_not_just_the_term():
    """The term alone cannot separate two arguments that share it."""
    entries = [
        {"docket": "13-7120", "term": 2014, "argued": "2014-11-05"},
        {"docket": "13-7120", "term": 2014, "argued": "2015-04-20"},
        {"docket": "24-109", "term": 2024, "argued": "2025-03-24"},
        {"docket": "24-109", "term": 2025, "argued": "2025-10-15"},
        {"docket": "24-316", "term": 2024, "argued": "2025-04-21"},
    ]

    assign_case_ids(entries)
    identifiers = [entry["case_id"] for entry in entries]

    assert identifiers == [
        "13-7120_2014-11-05", "13-7120_2015-04-20",
        "24-109_OT2024", "24-109_OT2025",
        "24-316",
    ]
    # The whole point: no two entries can address the same output files.
    assert len(set(identifiers)) == len(identifiers)


def test_the_date_keeps_two_same_term_arguments_in_separate_folders():
    first = folder_name(2014, "13-7120", "Johnson v. United States", date(2014, 11, 5))
    second = folder_name(2014, "13-7120", "Johnson v. United States", date(2015, 4, 20))

    assert first != second

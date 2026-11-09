"""Download the papers cited in the project notes into literature/pdfs/ (git-ignored).

The PDFs are copyrighted, so they stay on the laptop; this script and the index it
writes (pdf-index.md) are what git keeps. Run it again on the other laptop to get the
same set. Papers already downloaded are skipped.

    python asr-capstone/literature/fetch_papers.py

arXiv papers are named from arXiv's own records (first author, year, title), so the
index also checks each citation's authors and title. Everything else is listed by hand
below, with a note where no free copy exists.
"""

from __future__ import annotations

import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDFS = HERE / "pdfs"
AGENT = {"User-Agent": "Mozilla/5.0 (student capstone; literature download)"}

#: Every arXiv paper cited in the notes (reading list, scoping report, engine note,
#: data-set notes), collected by searching them on 1 November 2026.
ARXIV = """1610.05256 1703.02136 1708.08615 2003.07705 2004.09249 2011.01991 2101.09624
2104.01304 2104.02138 2104.02724 2104.11348 2203.15591 2209.10591 2210.13352 2212.04356
2303.18110 2304.06795 2307.04172 2309.10088 2310.02943 2402.08021 2407.13982 2408.11940
2408.15616 2408.16589 2409.02449 2409.03059 2412.07937 2502.12414 2505.08699 2505.13404
2505.23627 2506.06096 2507.13264 2509.14128 2510.06961 2510.16567 2601.21337 2606.21237
2606.23060 cs/0010012""".split()

#: Papers not on arXiv: (file name, citation, PDF address or None if no free copy).
OTHER = [
    # The journal version's free copy (Stanford) timed out on 1 Nov 2026; the shorter
    # ACL 2008 paper with the same title and findings is free and is used instead.
    ("goldwater-2010-which-words-are-hard.pdf",
     "Goldwater, Jurafsky & Manning (2010). Which words are hard to recognize? Speech Communication 52(3)",
     "https://nlp.stanford.edu/~manning/papers/goldwater10.pdf"),
    ("goldwater-2008-which-words-are-hard-acl.pdf",
     "Goldwater, Jurafsky & Manning (2008). Which words are hard to recognize? ACL-08: HLT, 380-388",
     "https://aclanthology.org/P08-1044.pdf"),
    # Free, but the publishers refuse scripted downloads: saved from a browser by hand.
    ("koenecke-2020-racial-disparities-asr.pdf",
     "Koenecke et al. (2020). Racial disparities in automated speech recognition. PNAS 117(14). "
     "Save by hand from https://pmc.ncbi.nlm.nih.gov/articles/PMC7149386/",
     "https://www.pnas.org/doi/pdf/10.1073/pnas.1915768117"),
    ("shriberg-2001-observations-on-overlap.pdf",
     "Shriberg, Stolcke & Baron (2001). Observations on overlap. Eurospeech 2001",
     "https://www.isca-archive.org/eurospeech_2001/shriberg01_eurospeech.pdf"),
    ("delrio-2021-earnings21-interspeech.pdf",
     "Del Rio et al. (2021). Earnings-21: A practical benchmark for ASR in the wild. Interspeech 2021",
     "https://www.isca-archive.org/interspeech_2021/delrio21_interspeech.pdf"),
    ("cetin-2006-overlaps-in-meetings.pdf",
     "Cetin & Shriberg (2006). Analysis of overlaps in meetings. Interspeech 2006",
     "https://www.isca-archive.org/interspeech_2006/cetin06_interspeech.pdf"),
    ("morris-2004-wer-mer-wil.pdf",
     "Morris, Maier & Green (2004). From WER and RIL to MER and WIL. Interspeech 2004",
     "https://www.isca-archive.org/interspeech_2004/morris04_interspeech.pdf"),
    ("tatman-2017-gender-dialect-bias-captions.pdf",
     "Tatman (2017). Gender and dialect bias in YouTube's automatic captions. ACL Ethics in NLP workshop",
     "https://aclanthology.org/W17-1606.pdf"),
    ("chen-2023-hyporadise.pdf",
     "Chen et al. (2023). HyPoradise. NeurIPS 36 Datasets and Benchmarks",
     "https://proceedings.neurips.cc/paper_files/paper/2023/file/6492267465a7ac507be1f9fd1174e78d-Paper-Datasets_and_Benchmarks.pdf"),
    ("saadany-2025-uk-supreme-court-asr.pdf",
     "Saadany et al. (2025). Employing AI for better access to justice. Applied Sciences 15(16). "
     "Save by hand from https://www.mdpi.com/2076-3417/15/16/9205",
     "https://www.mdpi.com/2076-3417/15/16/9205/pdf"),
    ("hwang-2026-whisper-clinical-french.pdf",
     "Hwang et al. (2026). Towards a clinical adaptation of the Whisper model for French. ICNLSP 2026",
     "https://aclanthology.org/2026.icnlsp-1.32.pdf"),
    ("ghodsi-2020-rnn-transducer-stateless-prediction-network.pdf",
     "Ghodsi, Liu, Apfel, Cabrera & Weinstein (2020). RNN-Transducer with stateless prediction network. ICASSP 2020",
     "https://storage.googleapis.com/gweb-research2023-media/pubtools/5775.pdf"),
    ("coraal-user-guide.pdf",
     "Kendall & Farrington (2023). CORAAL user guide (Version 2023.06)",
     "https://lingtools.uoregon.edu/coraal/userguide/CORAALUserGuide_current.pdf"),
    ("jones-2019-testifying-while-black.pdf",
     "Jones, Kalbfeld, Hancock & Clark (2019). Testifying while Black. Language 95(2). "
     "Restricted on Project MUSE (https://muse.jhu.edu/article/727848); no free copy found", None),
    ("fiscus-1997-rover.pdf",
     "Fiscus (1997). ROVER. IEEE ASRU 1997", None),
    ("bucholtz-2000-politics-of-transcription.pdf",
     "Bucholtz (2000). The politics of transcription. Journal of Pragmatics 32(10)", None),
]


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=60) as r:
        return r.read()


def arxiv_records(ids: list[str]) -> dict[str, dict]:
    """Title, authors and year for each id, from arXiv's API (one request)."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    feed = ET.fromstring(get("http://export.arxiv.org/api/query?max_results=200&id_list=" + ",".join(ids)))
    out = {}
    for entry in feed.findall("a:entry", ns):
        # The entry's own id, e.g. http://arxiv.org/abs/2212.04356v1 -> 2212.04356
        found = re.sub(r"v\d+$", "", entry.findtext("a:id", "", ns).split("/abs/")[-1])
        title = " ".join(entry.findtext("a:title", "", ns).split())
        authors = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
        out[found] = {"title": title, "authors": authors,
                      "year": entry.findtext("a:published", "", ns)[:4]}
    missing = [i for i in ids if i not in out]
    if missing:
        raise SystemExit(f"arXiv has no record of: {missing}")
    return out


def slug(text: str, words: int = 5) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower())[:words])


def save(name: str, url: str) -> str:
    target = PDFS / name
    if target.exists():
        return "already here"
    try:
        data = get(url)
    except Exception as error:  # a missing paper is reported, not fatal
        return f"failed: {error}"
    if not data.startswith(b"%PDF"):
        return "failed: not a PDF (probably a login or cookie page)"
    target.write_bytes(data)
    return f"downloaded, {len(data) / 1e6:.1f} MB"


def main() -> None:
    PDFS.mkdir(exist_ok=True)
    rows = []
    records = arxiv_records(ARXIV)
    for arxiv_id in ARXIV:
        rec = records[arxiv_id]
        surname = rec["authors"][0].split()[-1] if rec["authors"] else "unknown"
        name = f"{slug(surname, 1)}-{rec['year']}-{slug(rec['title'])}.pdf"
        status = save(name, f"https://arxiv.org/pdf/{arxiv_id}")
        who = rec["authors"][0] + (" et al." if len(rec["authors"]) > 1 else "")
        rows.append((name, f"{who} ({rec['year']}). {rec['title']}. arXiv:{arxiv_id}", status))
        print(f"{status:30} {name}")
        if status != "already here":
            time.sleep(3)  # arXiv asks for a pause between requests
    for name, citation, url in OTHER:
        if url:
            status = save(name, url)
        else:
            status = "already here (bought)" if (PDFS / name).exists() else "no free copy found"
        rows.append((name, citation, status))
        print(f"{status:30} {name}")

    lines = ["# Papers on disk", "",
             "Written by `fetch_papers.py`. The PDFs are in `pdfs/`, which git ignores because",
             "they are copyrighted; run the script again on another laptop to fetch them.", "",
             "| File | Paper | Status |", "|---|---|---|"]
    lines += [f"| `{n}` | {c} | {s} |" for n, c, s in rows]
    (HERE / "pdf-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

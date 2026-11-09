"""Building the list of work for a run.

Each function here turns a list of cases into a list of `Task`s. Nothing is
executed; the runner decides what to skip and what to do.

Keeping this apart from both the runner and the command line means the same task
list can be built by a graphical interface, shown to somebody before it runs, or
counted to estimate how long a run will take.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from .asr.base import AsrResult, Segment, Word
from .asr.registry import build_engine
from .config import Config
from .corpus.fetch import download, missing_files
from .corpus.manifest import Case
from .corpora.base import Corpus
from .events import EventBus
from .ocr.base import PageReading
from .scoring.metrics import score_case
from .scoring.normalize import NORMALIZERS
from .scoring.seams import deduplicate_seams
from .store import RunStore, read_json
from .tasks import Stage, Task, TaskKey
from .transcripts.model import Transcript

logger = logging.getLogger(__name__)

#: Column order for each results table, so a file written across several runs
#: keeps a stable shape.
SCORES_COLUMNS = [
    "docket", "engine", "model", "normalizer", "wer", "wer_percent",
    "hits", "substitutions", "deletions", "insertions",
    "reference_tokens", "hypothesis_tokens", "deletion_rate",
]

OMISSIONS_COLUMNS = [
    "docket", "engine", "rank", "word_count", "gap_seconds", "expected_seconds",
    "audio_start", "audio_end", "audio_start_clock", "timing_disagrees",
    "at_start", "at_end", "ref_start_token", "ref_end_token", "text",
]

#: Only the long silences are written out. Half-second gaps are ordinary speech
#: rhythm and there are tens of thousands of them; the point of the file is to
#: open the audio at a moment and hear what is actually there.
SILENCES_COLUMNS = [
    "docket", "engine", "rank", "seconds",
    "audio_start", "audio_end", "audio_start_clock", "at_start", "at_end",
]

#: cases.csv went without one of these for a long time, and that was a quiet
#: hazard rather than an oversight with no consequence.
#:
#: `append_csv_row` writes a header only when the file is new, and passes
#: `extrasaction="ignore"` - so a column the first scored case did not produce is
#: dropped from every later row, silently, with no warning and no error. Adding a
#: measure therefore appeared to work and then wrote nothing, unless the file
#: happened to be deleted first.
#:
#: The error-rate columns are built from NORMALIZERS rather than typed out,
#: because `case_row` generates one per way of comparing. A fourth way of
#: comparing should not need an edit here to be recorded.
CASES_COLUMNS = [
    "docket", "engine", "model",
    "audio_minutes", "reference_words", "hypothesis_words",
    "words_per_minute", "speaking_rate_ok",
    "runtime_seconds", "speed_x_realtime",
    "omission_basis",
    # from summarize_omissions
    "omitted_spans", "omitted_words", "seconds_lost",
    "longest_span_words", "longest_span_seconds", "spans_with_odd_timing",
    # from summarize_coverage
    "silent_seconds", "silent_share_percent", "silences_over_10s",
    "longest_silence_seconds", "silence_at_start_seconds", "silence_at_end_seconds",
    *[f"wer_{name}" for name in NORMALIZERS],
    "warnings",
]


def build_fetch_tasks(cases: Iterable[Case], store: RunStore, events: EventBus) -> list[Task]:
    """Tasks that download whatever a case is missing.

    A case with everything already on disk produces no task at all, rather than a
    task that immediately does nothing. That keeps the run summary honest: it
    reports what was actually needed.
    """
    tasks: list[Task] = []

    for case in cases:
        wanted = missing_files(case)
        if not wanted:
            continue

        def fetch(case=case, wanted=wanted) -> dict:
            total = 0
            for url, destination in wanted:
                total += download(
                    url,
                    destination,
                    on_progress=lambda got, size, d=destination: _report_download(
                        events, case.docket, d, got, size
                    ),
                )
            return {"files": len(wanted), "megabytes": round(total / 1e6, 1)}

        tasks.append(
            Task(
                key=TaskKey(case.docket, Stage.FETCH),
                run=fetch,
                # The last file to arrive stands in for the whole task.
                output=wanted[-1][1],
                description=f"Downloading {len(wanted)} file(s) for {case.docket}",
            )
        )

    return tasks


def build_transcript_tasks(
    cases: Iterable[Case], store: RunStore, corpus: "Corpus | None" = None
) -> list[Task]:
    """Tasks that turn each recording's reference into turns and save them.

    The corpus decides how: the Supreme Court parses a PDF, a speech corpus reads
    its STM or TextGrid files. With no corpus given it is the Supreme Court's
    PDF, as it always was.
    """
    tasks: list[Task] = []

    for case in cases:
        output = store.reference_path(case.docket)

        def parse(case=case, output=output) -> dict:
            if corpus is None:
                from .transcripts.parse import parse_transcript

                transcript = parse_transcript(case.transcript_pdf, case.docket)
            else:
                transcript = corpus.reference(case)
            store.write_json(output, transcript.to_dict())
            return {"turns": len(transcript.turns), "words": transcript.word_count}

        tasks.append(
            Task(
                key=TaskKey(case.docket, Stage.TRANSCRIPT),
                run=parse,
                output=output,
                description=f"Reading the reference for {case.docket}",
            )
        )

    return tasks


def build_asr_tasks(
    cases: Iterable[Case], config: Config, store: RunStore, events: EventBus
) -> list[Task]:
    """Tasks that run the speech recognition model over each recording.

    Cases with no audio are left out rather than failing. The Court does not host
    recordings before the 2010 term, so a transcript-only case is a normal state
    of affairs, not an error.

    **One engine for the whole run.** Every engine holds about 4 GB of video
    memory for as long as it exists, so building one per case fills a 24 GB card
    on the sixth. It does not crash there: decoding carries on at roughly a
    twelfth of the speed, turning a seven-hour run into a two-day one while
    every number it produces stays correct. Two runs were lost to this before it
    was noticed, and only by reading the speeds in a finished log.

    Still not loaded until the first transcription runs, so building tasks costs
    nothing and a fully-resumed run never touches the GPU.
    """
    tasks: list[Task] = []
    engine = build_engine(config.asr)

    for case in cases:
        if not case.has_audio:
            continue

        # Per case, because it is where this recording's segments are streamed
        # as they decode. It is passed to transcribe rather than held on the
        # engine, which is what lets the engine be shared.
        partial = store.path("asr", f"{case.docket}.partial.jsonl")
        output = store.asr_path(case.docket, engine.name)
        task_id = str(TaskKey(case.docket, Stage.ASR, engine.name))

        def transcribe(case=case, output=output, task_id=task_id, partial=partial) -> dict:
            result = engine.transcribe(
                case.audio_path,
                case.docket,
                on_progress=lambda fraction, note: events.task_progress(
                    task_id, note, fraction
                ),
                partial_path=partial,
            )
            store.write_json(output, result.to_dict())
            return {
                "words": result.word_count,
                "segments": len(result.segments),
                "times_realtime": round(result.speed, 1),
            }

        tasks.append(
            Task(
                key=TaskKey(case.docket, Stage.ASR, engine.name),
                run=transcribe,
                output=output,
                description=(
                    f"Transcribing {case.docket} "
                    f"({case.audio_minutes or 0:.0f} minutes) with {engine.name}"
                ),
            )
        )

    return tasks


def scanned_extras(config: Config) -> list[Case]:
    """Scanned transcripts that sit outside the manifest.

    The manifest lists cases with audio and a modern transcript, which is what
    the speech side of the project needs. The one genuinely scanned transcript in
    the sample - a 1969 argument kept as an example of what the old archive looks
    like - is not in it, because it has no matching audio and never will: the
    Court hosts no recordings before the 2010 term.

    It is still the only file here that actually requires OCR, so leaving it out
    would mean the OCR stage never ran on anything that needed it.

    Returns:
        A `Case` for each such transcript found, empty if none are present.
    """
    example = config.paths.sample_dir / "OCR_example" / "69-13_05-04-1970.pdf"
    if not example.exists():
        return []

    return [
        Case(
            docket="69-13",
            folder=example.parent,
            argued="1970-05-04",
            transcript_url=None,
            audio_url=None,
            audio_minutes=None,
            expected_turns=None,
            expected_words=None,
            transcript_file=example,
        )
    ]


OCR_COLUMNS = [
    "docket", "page", "engine", "line_numbers_found", "highest_line_number",
    "expected_lines", "numbers_misread", "numbers_missed", "misread_rate",
    "source", "warnings",
]


def build_ocr_tasks(
    cases: Iterable[Case],
    config: Config,
    store: RunStore,
    events: EventBus,
    read_text: bool = False,
    pages: Iterable[int] | None = None,
) -> list[Task]:
    """Tasks that read each transcript's pages and measure how well they read.

    Run over every case, not only the scanned ones, and deliberately.

    For a scanned transcript this is the only way to get the text. For a
    born-digital one the text is already exact, so the OCR is not needed - but
    that is precisely what makes those pages worth reading. The right answer is
    known, so the OCR's mistakes can be counted, which says how far to trust the
    same process on the 1969 scans where nothing exists to check against.

    What is measured on every page is the line numbers, because their right value
    is known independently: they run 1 to 25 down the margin. Comparing what the
    OCR read against where the box sat gives an error rate per page without
    anyone marking up a single page by hand.
    """
    # The page readers need PyMuPDF, which only the Supreme Court's PDFs call for.
    from .ocr.embedded_engine import EmbeddedTextEngine
    from .ocr.pipeline import read_document
    from .ocr.render import is_scanned

    tasks: list[Task] = []
    wanted = list(cases) + scanned_extras(config)

    for case in wanted:
        if not case.transcript_pdf.exists():
            continue

        # The summary file stands for the whole case, so a resumed run skips a
        # transcript it has already read rather than redoing a hundred pages.
        output = store.path("ocr", f"{case.docket}.summary.json")
        task_id = str(TaskKey(case.docket, Stage.OCR))

        def read(case=case, output=output, task_id=task_id) -> dict:
            engine = EmbeddedTextEngine()
            # Built only when asked for. Loading a vision model costs seconds and
            # reading a page costs about fifteen, so a run that only wants the
            # line-number measurement must not pay for it.
            text_engine = None
            if read_text:
                from .ocr.glm_engine import GlmOcrEngine

                text_engine = GlmOcrEngine(
                    model_id=config.ocr.text_model, device=config.asr.device
                )

            scanned = is_scanned(case.transcript_pdf)
            rows: list[dict[str, Any]] = []

            # Clear this case's earlier rows before writing new ones, so redoing
            # a case replaces its results instead of adding a second copy.
            store.remove_csv_rows(
                store.results_path("ocr_quality.csv"), "docket", case.docket
            )

            def save(reading: PageReading) -> None:
                # Written as each page is read, so a crash at page 80 of 104
                # costs one page rather than eighty.
                store.write_json(
                    store.ocr_page_path(case.docket, reading.page), reading.to_dict()
                )
                rows.append(_ocr_row(case.docket, reading, scanned, config))

            readings = read_document(
                case.transcript_pdf,
                engine,
                config.ocr,
                text_engine=text_engine,
                pages=pages,
                on_page=lambda page, done, total: events.task_progress(
                    task_id, f"page {page} ({done} of {total})", done / total
                ),
                save_page=save,
            )

            store.append_csv_rows(
                store.results_path("ocr_quality.csv"), rows, fieldnames=OCR_COLUMNS
            )

            with_numbers = [r for r in readings if r.geometry and r.geometry.lines]
            full = [
                r for r in with_numbers
                if r.geometry.highest_line == config.ocr.expected_lines_per_page
            ]
            misread = sum(r.geometry.disagreements for r in with_numbers)
            total_numbers = sum(r.geometry.line_count for r in with_numbers)

            store.write_json(output, {
                "docket": case.docket,
                "scanned": scanned,
                "pages": len(readings),
                "pages_with_line_numbers": len(with_numbers),
                "pages_numbered_to_25": len(full),
                "line_numbers_read": total_numbers,
                "line_numbers_misread": misread,
                "misread_rate": round(misread / total_numbers, 4) if total_numbers else 0.0,
            })

            return {
                "pages": len(readings),
                "misread_line_numbers": misread,
            }

        tasks.append(
            Task(
                key=TaskKey(case.docket, Stage.OCR),
                run=read,
                output=output,
                description=f"Reading the pages of {case.docket}",
            )
        )

    return tasks


def _ocr_row(docket: str, reading: PageReading, scanned: bool, config: Config
             ) -> dict[str, Any]:
    """One row of `ocr_quality.csv`, describing how well one page read."""
    geometry = reading.geometry
    found = geometry.line_count if geometry else 0
    misread = geometry.disagreements if geometry else 0

    return {
        "docket": docket,
        "page": reading.page,
        "engine": reading.engine,
        "line_numbers_found": found,
        "highest_line_number": geometry.highest_line if geometry else 0,
        "expected_lines": config.ocr.expected_lines_per_page,
        "numbers_misread": misread,
        "numbers_missed": len(geometry.missing_numbers) if geometry else 0,
        "misread_rate": round(misread / found, 4) if found else "",
        # The honest label on every row: a born-digital page is a known-answer
        # test, a scanned one is the real thing.
        "source": "scan" if scanned else "born-digital",
        "warnings": " | ".join(geometry.warnings) if geometry else "",
    }


def build_score_tasks(
    cases: Iterable[Case], config: Config, store: RunStore
) -> list[Task]:
    """Tasks that compare each machine transcription against the record.

    Reads the reference and the transcription back from the files the earlier
    stages wrote, rather than keeping them in memory. That is what allows scoring
    to be rerun on its own after a threshold changes, without transcribing
    anything again.
    """
    tasks: list[Task] = []
    engine_name = build_engine(config.asr).name

    for case in cases:
        if not case.has_audio:
            continue

        output = store.score_path(case.docket, engine_name)

        def score(case=case, output=output, engine_name=engine_name) -> dict:
            transcript = Transcript.from_dict(read_json(store.reference_path(case.docket)))
            result = _load_asr_result(store.asr_path(case.docket, engine_name))

            case_score = score_case(
                transcript,
                result,
                config.scoring,
                audio_minutes=case.audio_minutes,
            )

            store.write_json(output, case_score.to_dict())

            # Clear this case's earlier rows first, so rescoring replaces its
            # results rather than adding a second copy of them.
            for table in ("scores.csv", "cases.csv", "omissions.csv", "silences.csv"):
                store.remove_csv_rows(store.results_path(table), "docket", case.docket)

            # Appended as they are produced, so a run stopped halfway still
            # leaves usable tables.
            store.append_csv_rows(
                store.results_path("scores.csv"),
                [row.to_row() for row in case_score.rows],
                fieldnames=SCORES_COLUMNS,
            )
            store.append_csv_row(
                store.results_path("cases.csv"),
                case_score.case_row(),
                fieldnames=CASES_COLUMNS,
            )
            store.append_csv_rows(
                store.results_path("omissions.csv"),
                case_score.omission_rows(),
                fieldnames=OMISSIONS_COLUMNS,
            )
            store.append_csv_rows(
                store.results_path("silences.csv"),
                case_score.silence_rows(),
                fieldnames=SILENCES_COLUMNS,
            )

            standard = next(
                (r for r in case_score.rows if r.normalizer == "standard"), None
            )
            summary = {
                "omitted_spans": len(case_score.omissions),
            }
            if standard:
                summary["percent_wer"] = round(standard.wer * 100, 2)
            return summary

        tasks.append(
            Task(
                key=TaskKey(case.docket, Stage.SCORE, engine_name),
                run=score,
                output=output,
                description=f"Scoring {case.docket} against the reference",
            )
        )

    return tasks


def _load_asr_result(path: Path) -> AsrResult:
    """Rebuild an `AsrResult` from the JSON the transcription stage wrote.

    **Words that two neighbouring chunks both transcribed are dropped here.**
    Not in the engines, because the file on disk is what the model actually
    produced and that is the evidence; and not at scoring time per metric,
    because then the three scoring rules could disagree about what was said.

    Doing it on the way in means the correction is uniform across engines and
    reaches runs that finished weeks ago without re-transcribing a thing. See
    `scoring/seams.py` for why the midpoint rule needs it and how much it moves:
    between 0.001% and 0.888% of words depending on the engine, which is a
    ninefold-hundred spread across a comparison whose closest pair sits a tenth
    of a point apart.
    """
    data = read_json(path)
    segments = [
        Segment(
            index=segment.get("index", index),
            start=segment["start"],
            end=segment["end"],
            text=segment["text"],
            words=[
                Word(
                    text=word["text"],
                    start=word["start"],
                    end=word["end"],
                    probability=word.get("probability"),
                )
                for word in segment.get("words", [])
            ],
            no_speech_prob=segment.get("no_speech_prob"),
            avg_logprob=segment.get("avg_logprob"),
            compression_ratio=segment.get("compression_ratio"),
            temperature=segment.get("temperature"),
        )
        for index, segment in enumerate(data.get("segments", []))
    ]

    # chunk_seconds is None for Whisper, whose segments are utterances decided
    # inside faster-whisper rather than chunk boundaries this project created.
    # deduplicate_seams treats that as "change nothing"; see its note.
    settings = data.get("settings", {}) or {}
    segments, dropped = deduplicate_seams(segments, settings.get("chunk_seconds"), data.get("engine"))
    if dropped:
        logger.info(
            "[%s/%s] Dropped %d words that two neighbouring chunks both "
            "transcribed. The file on disk is unchanged.",
            data.get("docket", "?"), data.get("engine", "?"), dropped,
        )

    return AsrResult(
        docket=data.get("docket", ""),
        engine=data.get("engine", ""),
        model=data.get("model", ""),
        segments=segments,
        audio_seconds=data.get("audio_seconds", 0.0),
        runtime_seconds=data.get("runtime_seconds", 0.0),
        language=data.get("language", ""),
        settings=data.get("settings", {}),
    )


def _report_download(
    events: EventBus, docket: str, destination: Path, got: int, total: int
) -> None:
    """Turn download byte counts into an occasional readable progress line."""
    if total <= 0:
        return
    fraction = got / total
    # Only every 10%, otherwise a 70 MB file produces a thousand log lines.
    if got % (max(total // 10, 1)) < (1 << 16):
        events.task_progress(
            str(TaskKey(docket, Stage.FETCH)),
            f"{destination.name}: {got / 1e6:.0f} of {total / 1e6:.0f} MB",
            fraction,
        )

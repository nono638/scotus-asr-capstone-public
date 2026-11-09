"""Settings for a run, loaded from a YAML file.

Everything adjustable lives here rather than scattered through the code as literal
numbers. That matters for a study: when a result looks odd, the first question is
always "what settings produced this", and the answer should be one file you can
read, not a hunt through source.

Every run saves a copy of the settings it actually used, so an old result can
always be traced back to the configuration that produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

# Where this file sits, used to find the defaults and the sample data without
# depending on the working directory the command happened to be run from.
_PACKAGE_DIR = Path(__file__).resolve().parent
_PIPELINE_DIR = _PACKAGE_DIR.parent
_CAPSTONE_DIR = _PIPELINE_DIR.parent

DEFAULT_CONFIG_PATH = _PIPELINE_DIR / "config" / "default.yaml"

# Where the corpora live on this laptop. The two laptops keep them in different
# places (and the steno laptop has none), so no tracked file says where they
# are: each laptop has its own copy of this file, which git ignores. A file
# rather than an environment variable, because a new environment variable only
# reaches programs started after it is set.
LOCAL_PATHS_FILE = _CAPSTONE_DIR / "local-paths.yaml"
LOCAL_PATHS_EXAMPLE = _CAPSTONE_DIR / "local-paths.example.yaml"

# A name in braces, like {scotus_corpus}, stands for that entry of the file.
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def local_path(name: str) -> Path:
    """Where `name` (e.g. "scotus_corpus") lives on this laptop.

    Read from `local-paths.yaml` each time it is asked for, so nothing needs the
    file until it actually works on a corpus.

    Raises:
        SystemExit: If the file or the entry is missing, with a message saying
            which, rather than a traceback.
    """
    help_text = (f"Copy {LOCAL_PATHS_EXAMPLE.name} to {LOCAL_PATHS_FILE.name} in "
                 f"{LOCAL_PATHS_FILE.parent} and set where the corpus is on this laptop. "
                 f"The corpus only exists on the 5090 laptop.")
    if not LOCAL_PATHS_FILE.exists():
        raise SystemExit(f"Need {name!r} from {LOCAL_PATHS_FILE}, but that file does not exist. "
                         f"{help_text}")
    data = yaml.safe_load(LOCAL_PATHS_FILE.read_text(encoding="utf-8")) or {}
    if not data.get(name):
        raise SystemExit(f"{LOCAL_PATHS_FILE} has no {name!r} entry. {help_text}")
    return Path(data[name])


def expand_local(text: str) -> str:
    """Fill in placeholders like "{scotus_corpus}/runs" from local-paths.yaml.

    Text without a placeholder comes back exactly as it was, and does not need
    the file at all.
    """
    return _PLACEHOLDER.sub(lambda match: local_path(match.group(1)).as_posix(), str(text))


@dataclass(frozen=True)
class Paths:
    """Where things live on disk.

    All paths are absolute by the time a `Config` exists, so nothing downstream
    has to care about the current working directory.
    """

    capstone_dir: Path
    sample_dir: Path
    runs_dir: Path

    @property
    def manifest(self) -> Path:
        """The file listing every case, its source URLs and its expected counts."""
        return self.sample_dir / "manifest.json"


@dataclass(frozen=True)
class CorpusSettings:
    """Which recordings to run over, and where they live.

    The Supreme Court is the default and needs nothing set here: its case list
    is `paths.sample_dir`'s manifest. Any other corpus names its adapter and the
    folder it is kept in (see `corpora/registry.py`).
    """

    name: str = "scotus"
    # Where the corpus is downloaded and unpacked. Outside the repository.
    root: str = ""
    # The corpus's own division to use, e.g. "test". Empty for all of it.
    split: str = ""
    # Only these recordings (docket numbers, or the corpus's own ids), as
    # `--case` does. For a queue row that re-runs a scattered few: the runner
    # passes settings files through but not `--case`. Empty for all of them.
    recordings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AsrSettings:
    """How to run the speech recognition model.

    The defaults here are deliberately the *cautious* ones rather than the fast
    ones. `condition_on_previous_text` is off because feeding the model its own
    previous output is the main cause of it getting stuck repeating a phrase, and
    a repetition loop in the middle of a 150-minute argument destroys the run.

    `vad_filter` (voice activity detection - skipping parts of the audio that
    sound like silence) is off by default for a more specific reason. It is a
    known source of silently dropped speech, and dropped speech is the exact thing
    this project measures. Leaving it on would mean reporting the filter's
    mistakes as the model's. It can be switched on deliberately as a second
    condition, and the difference between the two runs is itself a result.
    """

    engine: str = "faster-whisper"
    model: str = "large-v3"
    device: str = "cuda"
    # float16 rather than an 8-bit type. Quantizing would save about 2 GB, which
    # is not worth having on a 24 GB card, and half precision is the
    # best-travelled path - it is what the published numbers were measured with.
    compute_type: str = "float16"
    language: str = "en"
    beam_size: int = 5
    word_timestamps: bool = True
    condition_on_previous_text: bool = False
    vad_filter: bool = False
    # Falling back to a higher temperature lets the decoder retry a segment it
    # made a mess of, instead of accepting a degenerate result.
    temperatures: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    # Settings that belong to one engine only, passed to it as they are. The
    # fields above are Whisper's; an engine with other knobs (a cloud service's
    # model name, say) reads them from here instead of each needing a new field.
    engine_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoringSettings:
    """Thresholds for turning an alignment into reported numbers."""

    # A run of missing words this long or longer counts as an omitted span.
    # 25 words is roughly ten seconds at the speaking rate of appellate argument,
    # which is long enough that a reader would notice the record makes no sense.
    omission_min_words: int = 25
    # A dropped span often contains one or two common words the model happened to
    # emit anyway ("the", "Court"). Without this, a single stray match splits one
    # sixty-second omission into two shorter ones and the worst failures vanish
    # from the statistics.
    omission_merge_gap: int = 2
    # Spoken words divided by audio minutes. Outside this band, the audio and the
    # transcript are probably not the same proceeding.
    #
    # These are the real defaults. config/default.yaml documents them and is only
    # read when no --config is given, so a settings file that leaves a value out
    # falls back to here rather than to that file. Changing one without the other
    # is how you get a run that quietly ignores the number you just edited.
    #
    # Widened from 165-197 after measuring 138 arguments across OT2010 and OT2017.
    # The original pair came from three hand-checked cases; the real spread is
    # 152.9 to 203.7, so the old band flagged 23% of the corpus and every one was
    # a false alarm - their error rates sit inside the range of the cases it
    # passed. A check that cries wolf that often is worse than none, because the
    # one real mismatch reads as more noise.
    words_per_minute_min: float = 145.0
    words_per_minute_max: float = 210.0


@dataclass(frozen=True)
class OcrSettings:
    """How to read scanned transcript pages.

    The rendering settings were chosen by measurement rather than by reasoning.
    The expectation was that enlarging would help, since the scans are about 150
    dots per inch and recognition models are usually trained nearer 300. It does
    not: reading the same page at 150, 200 and 300 dots per inch produced
    character-for-character identical text, because the model normalises the
    image itself. Rendering larger only costs time, so it is not done.
    """

    layout_engine: str = "embedded"
    text_engine: str = "glm-ocr"
    text_model: str = "zai-org/GLM-OCR"
    render_dpi: int = 200
    upscale: float = 1.0
    # Each transcript page carries lines numbered 1 to 25 down the left margin.
    expected_lines_per_page: int = 25
    # A word box whose left edge sits in the leftmost this-fraction of the page
    # is a candidate line number.
    gutter_width_fraction: float = 0.12


@dataclass(frozen=True)
class RunSettings:
    """How the task loop behaves when things go wrong."""

    # Transient failures (a download, a flaky server) are worth retrying.
    # A model that runs out of memory will fail the same way every time, so the
    # count stays small.
    max_attempts: int = 3
    retry_backoff_seconds: float = 5.0
    # Write a results row as soon as it exists rather than at the end.
    flush_every_row: bool = True


@dataclass(frozen=True)
class Config:
    """Everything one run needs to know."""

    paths: Paths
    corpus: CorpusSettings = field(default_factory=CorpusSettings)
    asr: AsrSettings = field(default_factory=AsrSettings)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    ocr: OcrSettings = field(default_factory=OcrSettings)
    run: RunSettings = field(default_factory=RunSettings)

    def to_dict(self, engine: Any | None = None) -> dict[str, Any]:
        """A plain dictionary, for saving alongside the results.

        Args:
            engine: The engine a run is about to use. Given one, the speech
                recognition section records what that engine will actually run
                with, rather than every field this file can hold.

        Returns:
            The settings, as plain values that survive YAML.

        Nine of the thirteen speech-recognition fields are Whisper's - beam size,
        the temperature ladder, the silence filter - and the other engines ignore
        them. Written out regardless, a Parakeet run's record listed a beam size
        it never used and omitted the chunk length it depended on: plausible,
        complete-looking and wrong about the experiment it described.

        The engine is asked instead. It is the same method that fills the
        per-case result, so the run's record and the case's cannot disagree.
        Optional because the fetch, transcript and OCR commands never build an
        engine, and because a run that fails while building its tasks should
        still leave a record of what it was asked to do.
        """
        data = asdict(self)
        # Paths are not YAML-friendly on their own.
        data["paths"] = {k: str(v) for k, v in data["paths"].items()}
        data["asr"]["temperatures"] = list(self.asr.temperatures)

        if engine is not None and hasattr(engine, "settings_used"):
            # The registry name stays: it is how the run is reproduced, and it is
            # the one field the engine has no reason to report about itself.
            data["asr"] = {
                "engine": self.asr.engine,
                "engine_name": getattr(engine, "name", ""),
                **engine.settings_used(),
            }
        return data


def _merge(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Overlay one settings dictionary on another, one level deep per section.

    Only the keys actually given are replaced, so a config file can set a single
    value without having to restate the whole section.
    """
    merged = dict(defaults)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    path: Path | str | list[Path | str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Build a `Config`, from a YAML file if one is given.

    Args:
        path: A YAML settings file, or several, applied in order so a later one
            overrides an earlier one key by key. That is how a model's file and
            a corpus's file combine - `config/qwen3.yaml` then
            `config/corpora/edacc.yaml` - instead of one file per pairing. Falls
            back to `config/default.yaml`, and to the dataclass defaults if that
            is missing too.
        overrides: Values applied on top of the files, for command line flags.

    Returns:
        A frozen `Config` with absolute paths.

    Raises:
        FileNotFoundError: If a file was given explicitly and does not exist.
    """
    if path is None:
        paths_given = [DEFAULT_CONFIG_PATH] if DEFAULT_CONFIG_PATH.exists() else []
    else:
        paths_given = [Path(p) for p in (path if isinstance(path, (list, tuple)) else [path])]
        for config_path in paths_given:
            if not config_path.exists():
                raise FileNotFoundError(f"No settings file at {config_path}")

    raw: dict[str, Any] = {}
    for config_path in paths_given:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        # An empty YAML file parses as None rather than an empty dictionary.
        raw = _merge(raw, loaded or {})

    if overrides:
        raw = _merge(raw, overrides)

    # A YAML section whose entries are all commented out parses as None rather
    # than as an empty mapping, so `raw.get(name, {})` is not enough - the key is
    # present and its value is None. `or {}` covers both cases.
    def section(name: str) -> dict[str, Any]:
        return raw.get(name) or {}

    # A path may start with a placeholder such as {scotus_corpus}, filled in from
    # local-paths.yaml, so the settings files say nothing about this laptop.
    def path_of(value: Any) -> Path:
        return Path(expand_local(value)).resolve()

    path_settings = section("paths")
    capstone_dir = path_of(path_settings.get("capstone_dir", _CAPSTONE_DIR))
    paths = Paths(
        capstone_dir=capstone_dir,
        sample_dir=path_of(path_settings.get("sample_dir", capstone_dir / "sample")),
        runs_dir=path_of(path_settings.get("runs_dir", capstone_dir / "runs")),
    )

    corpus_settings = dict(section("corpus"))
    if corpus_settings.get("root"):
        corpus_settings["root"] = expand_local(corpus_settings["root"])
    if "recordings" in corpus_settings:
        corpus_settings["recordings"] = tuple(str(r) for r in corpus_settings["recordings"] or ())

    asr_settings = dict(section("asr"))
    if "temperatures" in asr_settings:
        asr_settings["temperatures"] = tuple(asr_settings["temperatures"])

    return Config(
        paths=paths,
        corpus=CorpusSettings(**corpus_settings),
        asr=AsrSettings(**asr_settings),
        scoring=ScoringSettings(**section("scoring")),
        ocr=OcrSettings(**section("ocr")),
        run=RunSettings(**section("run")),
    )

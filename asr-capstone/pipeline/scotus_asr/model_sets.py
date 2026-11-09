"""Which models to compare, and which run holds each one's transcriptions.

Each run folder holds one engine's output for one corpus:

    <run>/asr/<recording>.<engine>.json     what the model wrote
    <run>/reference/<recording>.json        the reference it was scored against
    <run>/config_used.yaml                  the settings, engine included

A comparison across models needs a list of (name, run) pairs. There are three
ways to give one, so any combination of engines can be compared:

- a model-set file: a short YAML naming each model and its run. Fixed runs, so a
  published table can always be rebuilt from the same files. The Supreme Court's
  seven are `config/model-sets/scotus-seven.yaml`.
- discovery: every engine found in a runs folder, each from the run that covers
  the most recordings (the newest, on a tie), named after the engine.
- by hand: `Name=path/to/run`, as many as wanted.

Recording identifiers must not contain a dot: the part of a file name before the
first dot is the recording, the rest is the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import expand_local


@dataclass(frozen=True)
class ModelRun:
    """One model, and the run its transcriptions come from.

    Attributes:
        name: What the tables call it - "Qwen3", or the engine name if no
            shorter one was given.
        run_dir: The run folder.
        engine: The engine name as it appears in the transcription file names.
    """

    name: str
    run_dir: Path
    engine: str

    def asr_file(self, recording: str) -> Path:
        return self.run_dir / "asr" / f"{recording}.{self.engine}.json"

    def reference_file(self, recording: str) -> Path:
        return self.run_dir / "reference" / f"{recording}.json"

    def recordings(self) -> set[str]:
        """Every recording this run has a finished transcription for."""
        return engines_in(self.run_dir).get(self.engine, set())


@dataclass
class ModelSet:
    """The models to compare, plus the choices that go with them.

    Attributes:
        models: In the order the tables list them.
        pivot: The model the vote lines the others up against. The first model
            unless the set says otherwise; it should be chosen before looking at
            any result.
        out: Where results go, if the set says.
        description: A line saying what the set is, for the printout.
    """

    models: list[ModelRun]
    pivot: str = ""
    out: Path | None = None
    description: str = ""
    notes: dict = field(default_factory=dict)

    def __post_init__(self):
        names = [m.name for m in self.models]
        if len(set(names)) != len(names):
            raise ValueError(f"Two models share a name: {names}")
        if len(self.models) < 2:
            raise ValueError(f"Comparing models needs at least two; got {names}")
        if not self.pivot:
            self.pivot = names[0]
        if self.pivot not in names:
            raise ValueError(f"The pivot {self.pivot!r} is not one of {names}")

    @property
    def names(self) -> list[str]:
        return [m.name for m in self.models]

    def by_name(self, name: str) -> ModelRun:
        return next(m for m in self.models if m.name == name)

    def shared_recordings(self) -> tuple[list[str], dict[str, list[str]]]:
        """The recordings every model transcribed, and what each one lacks.

        Returns:
            (recordings all of them have, sorted; {model: recordings only others have})
        """
        have = {m.name: m.recordings() for m in self.models}
        everything = set().union(*have.values())
        shared = set.intersection(*have.values())
        missing = {name: sorted(everything - got) for name, got in have.items() if everything - got}
        return sorted(shared), missing


def engines_in(run_dir: Path) -> dict[str, set[str]]:
    """{engine name: recordings} for every finished transcription in a run."""
    found: dict[str, set[str]] = {}
    folder = Path(run_dir) / "asr"
    if not folder.is_dir():
        return found
    for path in folder.glob("*.json"):
        recording, _, rest = path.name.partition(".")
        engine = rest[: -len(".json")]
        if engine:
            found.setdefault(engine, set()).add(recording)
    return found


def discover(runs_dir: Path, names: list[str] | None = None) -> list[ModelRun]:
    """Every engine in a runs folder, each from its most complete run.

    Args:
        runs_dir: A folder of run folders.
        names: Keep only these engines, in this order. Matched against the
            engine name in the file names, case-insensitively, by prefix, so
            "qwen3" finds "Qwen3-ASR-1.7B-hf".

    Raises:
        ValueError: If a name matches no engine, or more than one.
    """
    best: dict[str, tuple[int, str, Path]] = {}
    for run in sorted(Path(runs_dir).iterdir()):
        if not run.is_dir() or not run.name.startswith("run-"):
            continue   # skips folders renamed "superseded-..." on purpose
        for engine, recordings in engines_in(run).items():
            candidate = (len(recordings), run.name, run)
            if engine not in best or candidate[:2] > best[engine][:2]:
                best[engine] = candidate
    runs = [ModelRun(engine, best[engine][2], engine) for engine in sorted(best)]
    if names is None:
        return runs

    chosen = []
    for wanted in names:
        hits = [r for r in runs if r.engine.lower().startswith(wanted.lower())]
        if len(hits) != 1:
            known = ", ".join(r.engine for r in runs) or "none"
            raise ValueError(f"{wanted!r} matches {len(hits)} engines in {runs_dir}. Known: {known}")
        chosen.append(hits[0])
    return chosen


def from_pair(text: str, runs_dir: Path | None = None) -> ModelRun:
    """A model given by hand as `Name=run`, the run a path or a folder name.

    The run must hold exactly one engine, so the name cannot point at the wrong
    model's files.
    """
    name, sep, run = text.partition("=")
    if not sep or not name or not run:
        raise ValueError(f"Expected Name=run, got {text!r}")
    return _model(name.strip(), run.strip(), runs_dir)


def load_set(path: Path) -> ModelSet:
    """Read a model-set file.

    The file looks like:

        description: The seven models of the Supreme Court study
        runs_dir: "{scotus_corpus}/runs"   # where relative runs are looked for
        pivot: Whisper                      # optional; the first model otherwise
        out: findings/crowd                 # optional; relative to the capstone
        models:
          Whisper: run-20260918-035220
          Qwen3: run-20260921-051927

    `{scotus_corpus}` is filled in from local-paths.yaml (see config.py), so the
    file does not say where the runs are on any one laptop.
    """
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    runs_dir = Path(expand_local(data["runs_dir"])) if data.get("runs_dir") else None
    models = [_model(str(name), str(run), runs_dir) for name, run in (data.get("models") or {}).items()]
    out = data.get("out")
    capstone = Path(__file__).resolve().parents[2]
    return ModelSet(
        models=models,
        pivot=data.get("pivot", ""),
        out=(capstone / out) if out and not Path(out).is_absolute() else (Path(out) if out else None),
        description=data.get("description", ""),
        notes={k: v for k, v in data.items()
               if k not in ("models", "runs_dir", "pivot", "out", "description")},
    )


def _model(name: str, run: str, runs_dir: Path | None) -> ModelRun:
    run_dir = Path(run)
    if not run_dir.is_absolute() and runs_dir is not None:
        run_dir = runs_dir / run
    engines = engines_in(run_dir)
    if len(engines) != 1:
        raise ValueError(
            f"{name}: {run_dir} holds {len(engines)} engines ({', '.join(engines) or 'none'}); "
            f"expected exactly one"
        )
    return ModelRun(name, run_dir, next(iter(engines)))

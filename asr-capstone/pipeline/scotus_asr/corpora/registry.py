"""Choosing a corpus by name, from the settings file's `corpus:` section."""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from .base import Corpus


def build_corpus(config: Config) -> Corpus:
    """The corpus a run's settings ask for.

    Imported lazily, so a run over one corpus never loads another's adapter.

    Raises:
        SystemExit: For a name with no adapter, listing the ones there are, or
            for a corpus other than the Supreme Court with no `root` set.
    """
    name = config.corpus.name
    if name == "scotus":
        from .scotus import ScotusCorpus
        return ScotusCorpus(config.paths.sample_dir, manifest=config.paths.manifest)

    adapters = {"edacc": ("edacc", "EdaccCorpus"), "coraal": ("coraal", "CoraalCorpus"),
                "earnings22": ("earnings22", "Earnings22Corpus")}
    if name not in adapters:
        raise SystemExit(f"No corpus called {name!r}. Known: scotus, {', '.join(adapters)}")
    if not config.corpus.root:
        raise SystemExit(f"corpus.root is not set; say where {name} should live.")

    module, cls = adapters[name]
    adapter = getattr(__import__(f"{__package__}.{module}", fromlist=[cls]), cls)
    return adapter(Path(config.corpus.root), split=config.corpus.split)

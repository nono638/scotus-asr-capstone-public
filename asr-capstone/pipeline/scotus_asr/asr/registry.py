"""Looking up a speech recognition engine by name.

Engines are named in the settings file, not chosen in code. Adding a second model
to the study should be an edit to a YAML file and one new module, not a change to
the runner, the scorer or the command line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..config import AsrSettings
from .base import AsrEngine

#: Name in the settings file -> how to build it.
_BUILDERS: dict[str, Callable[[AsrSettings, Path | None], AsrEngine]] = {}


def register(name: str, builder: Callable[[AsrSettings, Path | None], AsrEngine]) -> None:
    """Make an engine available under `name`."""
    _BUILDERS[name] = builder


def available_engines() -> list[str]:
    """Every engine name that can be asked for, sorted."""
    return sorted(_BUILDERS)


def build_engine(
    settings: AsrSettings, partial_path: Path | None = None
) -> AsrEngine:
    """Create the engine named in the settings.

    Args:
        settings: Must have `engine` set to a registered name.
        partial_path: Where the engine may stream partial results, if it can.

    Returns:
        A ready-to-use engine. The model itself is not loaded until the first
        transcription, so building one is cheap.

    Raises:
        KeyError: If the name is not registered, listing what is.
    """
    try:
        builder = _BUILDERS[settings.engine]
    except KeyError:
        raise KeyError(
            f"No speech recognition engine called {settings.engine!r}. "
            f"Available: {', '.join(available_engines()) or 'none'}."
        ) from None
    return builder(settings, partial_path)


def _build_faster_whisper(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the faster-whisper engine.

    Imported inside the function so that merely listing the available engines
    does not pull in faster-whisper, CTranslate2 and the CUDA libraries behind
    them.
    """
    from .faster_whisper_engine import FasterWhisperEngine

    return FasterWhisperEngine(settings, partial_path=partial)


register("faster-whisper", _build_faster_whisper)


def _build_parakeet(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the Parakeet engine.

    Imported inside the function for the same reason as the other one: listing
    the engines must not drag in transformers and torch.
    """
    from .parakeet_engine import ParakeetEngine

    return ParakeetEngine(settings, partial_path=partial)


register("parakeet", _build_parakeet)


def _build_qwen3(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the Qwen3-ASR engine.

    Imported inside the function for the same reason as the others: listing the
    engines must not drag in transformers and torch.
    """
    from .qwen3_engine import Qwen3Engine

    return Qwen3Engine(settings, partial_path=partial)


register("qwen3-asr", _build_qwen3)


def _build_canary(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the Canary engine.

    Imported inside the function for the same reason as the others: listing the
    engines must not drag in transformers and torch.
    """
    from .canary_engine import CanaryEngine

    return CanaryEngine(settings, partial_path=partial)


register("canary", _build_canary)


def _build_voxtral(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the Voxtral engine, batch or streaming.

    One builder for both of Mistral's models: they differ in which transformers
    class loads them, which the engine works out from the repository name.

    Imported inside the function for the same reason as the others: listing the
    engines must not drag in transformers and torch.
    """
    from .voxtral_engine import VoxtralEngine

    return VoxtralEngine(settings, partial_path=partial)


register("voxtral", _build_voxtral)


def _build_granite(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the Granite Speech engine.

    Only the 4.1 models. The 3.3-8b loads through the same classes and cannot
    punctuate - four prompts returned byte-identical lowercase text - so wiring
    it up would produce a transcript no court could certify. See the note in
    `granite_engine`.

    Imported inside the function for the same reason as the others: listing the
    engines must not drag in transformers and torch.
    """
    from .granite_engine import GraniteEngine

    return GraniteEngine(settings, partial_path=partial)


register("granite", _build_granite)


def _build_granite_plus(settings: AsrSettings, partial: Path | None) -> AsrEngine:
    """Build the Granite Speech 4.1 Plus engine.

    A separate module rather than a flag on the Granite engine, because the two
    differ in more than weights. Plus is asked a different prompt, parses
    timestamps out of its own output, and loads no forced aligner. Folding that
    into one class would mean four branches on a boolean.

    Imported inside the function for the same reason as the others: listing the
    engines must not drag in transformers and torch.
    """
    from .granite_plus_engine import GranitePlusEngine

    return GranitePlusEngine(settings, partial_path=partial)


register("granite-plus", _build_granite_plus)

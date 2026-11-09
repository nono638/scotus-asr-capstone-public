"""The shipped settings file must agree with the code's own defaults.

There are two places a threshold appears to live. `config/default.yaml` reads
like the settings, and `config.py` holds the dataclass defaults. Only the second
is the fallback: a run given `--config something_else.yaml` takes anything that
file leaves out from the dataclass, and never opens default.yaml at all.

That cost a rescore. The speaking-rate band was widened in default.yaml, the run
was given corpus.yaml, and it quietly scored 138 cases with the old numbers. The
only reason it was caught is that every run writes a config_used.yaml recording
what it actually used - which is the right safeguard, but it catches the mistake
after the compute rather than before.

So: the two must agree, and a test is cheaper than reading both.
"""

from __future__ import annotations

import yaml

from scotus_asr.config import DEFAULT_CONFIG_PATH, load_config


def test_the_shipped_file_matches_the_code_defaults():
    """Every value written in default.yaml must equal what the code falls back to.

    If this fails, decide which one is right and change the other. Do not just
    make the test pass: the numbers here decide what a run measured.
    """
    written = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    # Loading with no file gives pure dataclass defaults - the real fallback.
    fallback = load_config().to_dict()

    mismatches = []
    for section, values in written.items():
        if not isinstance(values, dict) or section == "paths":
            continue
        for key, value in values.items():
            if key not in fallback.get(section, {}):
                continue
            if fallback[section][key] != value:
                mismatches.append(
                    f"{section}.{key}: default.yaml says {value!r}, "
                    f"config.py falls back to {fallback[section][key]!r}"
                )

    assert not mismatches, (
        "The settings file and the code disagree. A run given any other config "
        "file uses the code's value and never reads default.yaml:\n  "
        + "\n  ".join(mismatches)
    )


def test_the_speaking_rate_band_is_the_measured_one():
    """Pinned because it was set from three cases and wrong for 23% of 138."""
    scoring = load_config().scoring

    assert scoring.words_per_minute_min == 145.0
    assert scoring.words_per_minute_max == 210.0
    # The observed spread across OT2010 and OT2017, with a little margin.
    assert scoring.words_per_minute_min < 152.9
    assert scoring.words_per_minute_max > 203.7

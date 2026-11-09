"""Tests for loading settings.

Settings decide what an experiment measured, so loading them wrongly is worse
than loading them not at all: a silently mistaken threshold produces numbers that
look fine and are not.
"""

from __future__ import annotations

import pytest

from scotus_asr.config import DEFAULT_CONFIG_PATH, load_config


def test_the_shipped_settings_file_loads():
    """The file in config/ must actually work, not just look right."""
    config = load_config(DEFAULT_CONFIG_PATH)
    assert config.asr.model
    assert config.paths.sample_dir.name == "sample"


def test_a_section_with_everything_commented_out_still_loads(tmp_path):
    """YAML gives None, not an empty mapping, for a section with no entries.

    The shipped settings file has exactly this shape - a `paths:` heading with
    every line beneath it commented out - and it stopped the whole command line
    from starting until this was handled.
    """
    settings = tmp_path / "settings.yaml"
    settings.write_text("paths:\n  # capstone_dir: somewhere\nasr:\n", encoding="utf-8")

    config = load_config(settings)
    assert config.asr.model == "large-v3"


def test_an_empty_file_falls_back_to_the_defaults(tmp_path):
    settings = tmp_path / "settings.yaml"
    settings.write_text("", encoding="utf-8")
    assert load_config(settings).asr.engine == "faster-whisper"


def test_only_the_named_values_are_replaced(tmp_path):
    """Changing one threshold must not reset the rest of the section."""
    settings = tmp_path / "settings.yaml"
    settings.write_text("scoring:\n  omission_min_words: 40\n", encoding="utf-8")

    config = load_config(settings)
    assert config.scoring.omission_min_words == 40
    assert config.scoring.omission_merge_gap == 2


def test_a_missing_settings_file_is_an_error_when_asked_for_by_name(tmp_path):
    """Silently using the defaults instead would be the worst outcome here."""
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "not-here.yaml")


def test_silence_filtering_is_off_by_default():
    """Not a preference - a measurement decision.

    Voice activity detection is a known cause of quietly dropped speech, and
    dropped speech is what this project measures. Leaving it on would report the
    filter's mistakes as the model's.
    """
    assert load_config(DEFAULT_CONFIG_PATH).asr.vad_filter is False


def test_the_model_is_not_shown_its_own_output_by_default():
    """The main cause of a transcription getting stuck repeating a phrase."""
    assert load_config(DEFAULT_CONFIG_PATH).asr.condition_on_previous_text is False


def test_the_settings_can_be_written_back_out():
    """Every run saves what it used, so a result can be traced to its settings."""
    data = load_config(DEFAULT_CONFIG_PATH).to_dict()
    assert isinstance(data["paths"]["sample_dir"], str)
    assert isinstance(data["asr"]["temperatures"], list)


def test_engine_only_settings_pass_through(tmp_path):
    """An engine with its own knobs reads them from `engine_options`.

    The other speech settings are Whisper's and any unknown key is refused, so
    a cloud engine's model name has to go somewhere that takes anything.
    """
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        "asr:\n  engine: someday-cloud\n  engine_options:\n    model: flash\n    timeout: 30\n",
        encoding="utf-8",
    )
    config = load_config(settings)
    assert config.asr.engine_options == {"model": "flash", "timeout": 30}
    assert load_config(DEFAULT_CONFIG_PATH).asr.engine_options == {}


def test_a_settings_file_can_name_the_recordings_to_run(tmp_path):
    # Docket numbers that look like numbers must stay text: "4481766", not 4481766.
    settings = tmp_path / "settings.yaml"
    settings.write_text("corpus:\n  recordings:\n    - 18-1323\n    - 4481766\n", encoding="utf-8")
    assert load_config(settings).corpus.recordings == ("18-1323", "4481766")


def test_no_recordings_named_means_all_of_them():
    assert load_config().corpus.recordings == ()

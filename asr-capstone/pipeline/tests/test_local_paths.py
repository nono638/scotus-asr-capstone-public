"""Tests for local-paths.yaml: where the corpora are on this laptop.

The settings files say "{scotus_corpus}/runs" rather than a drive letter, and
the placeholder is filled in from a file each laptop keeps for itself. These
tests point the code at a made-up file in a temporary folder, so they pass
the same on a laptop with no local-paths.yaml at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scotus_asr import config
from scotus_asr.config import expand_local, load_config, local_path
from scotus_asr.model_sets import load_set
from test_model_sets import make_run


@pytest.fixture
def local_file(tmp_path, monkeypatch):
    """A local-paths.yaml in a temporary folder, used in place of the real one."""
    path = tmp_path / "local-paths.yaml"
    monkeypatch.setattr(config, "LOCAL_PATHS_FILE", path)
    return path


def test_a_name_in_the_file_gives_its_path(local_file, tmp_path):
    corpus = tmp_path / "corpus"
    local_file.write_text(f"scotus_corpus: {corpus.as_posix()}\n", encoding="utf-8")
    assert local_path("scotus_corpus") == corpus


def test_a_missing_file_says_which_file_and_what_to_copy(local_file):
    with pytest.raises(SystemExit) as stopped:
        local_path("scotus_corpus")
    message = str(stopped.value)
    assert "scotus_corpus" in message and str(local_file) in message
    assert "local-paths.example.yaml" in message and "5090" in message


def test_a_missing_name_says_which_name(local_file):
    local_file.write_text("asr_corpora: E:/elsewhere\n", encoding="utf-8")
    with pytest.raises(SystemExit) as stopped:
        local_path("scotus_corpus")
    assert "'scotus_corpus'" in str(stopped.value)
    assert "local-paths.example.yaml" in str(stopped.value)


def test_a_placeholder_is_filled_in(local_file):
    local_file.write_text("scotus_corpus: E:/somewhere/scotus\n", encoding="utf-8")
    assert expand_local("{scotus_corpus}/runs") == "E:/somewhere/scotus/runs"


def test_a_plain_path_is_left_alone_and_needs_no_file(local_file):
    # The file does not exist here, so reading it at all would fail.
    assert expand_local("E:/a/runs") == "E:/a/runs"
    assert expand_local("runs") == "runs"


def test_settings_files_fill_in_placeholders(local_file, tmp_path):
    local_file.write_text(f"scotus_corpus: {(tmp_path / 's').as_posix()}\n"
                          f"asr_corpora: {(tmp_path / 'a').as_posix()}\n", encoding="utf-8")
    settings = tmp_path / "settings.yaml"
    settings.write_text('paths:\n  sample_dir: "{scotus_corpus}/cases"\n'
                        '  runs_dir: "{asr_corpora}/edacc/runs"\n'
                        'corpus:\n  name: edacc\n  root: "{asr_corpora}/edacc"\n',
                        encoding="utf-8")
    loaded = load_config(settings)
    assert loaded.paths.sample_dir == (tmp_path / "s" / "cases").resolve()
    assert loaded.paths.runs_dir == (tmp_path / "a" / "edacc" / "runs").resolve()
    assert Path(loaded.corpus.root) == tmp_path / "a" / "edacc"


def test_settings_files_with_plain_paths_need_no_file(local_file, tmp_path):
    settings = tmp_path / "settings.yaml"
    settings.write_text(f"paths:\n  runs_dir: {(tmp_path / 'runs').as_posix()}\n",
                        encoding="utf-8")
    assert load_config(settings).paths.runs_dir == (tmp_path / "runs").resolve()


def test_a_model_set_fills_in_its_runs_folder(local_file, tmp_path):
    runs = tmp_path / "corpus" / "runs"
    make_run(runs, "run-1", "whisper", {"R1": "a"})
    make_run(runs, "run-2", "parakeet", {"R1": "a"})
    local_file.write_text(f"scotus_corpus: {(tmp_path / 'corpus').as_posix()}\n", encoding="utf-8")
    settings = tmp_path / "set.yaml"
    settings.write_text('runs_dir: "{scotus_corpus}/runs"\n'
                        "models:\n  Whisper: run-1\n  Parakeet: run-2\n", encoding="utf-8")
    chosen = load_set(settings)
    assert [m.run_dir for m in chosen.models] == [runs / "run-1", runs / "run-2"]

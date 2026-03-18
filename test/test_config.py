"""Tests for library configuration loading.

Spec: specification/prebuilt-distribution.md §4.2

Import paths under test:
  poule.config.load_config
  poule.config.get_libraries_dir
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from Poule.config import load_config, get_libraries_dir

# Valid library identifiers per spec §4.2
VALID_LIBRARIES = {"stdlib", "mathcomp", "stdpp", "flocq", "coquelicot", "coqinterval"}


class TestLoadConfig:
    """load_config reads TOML config and returns library list."""

    def test_reads_configured_libraries(self, tmp_path):
        """§4.2: Given config.toml with [index] libraries, returns the list."""
        config = tmp_path / "config.toml"
        config.write_text('[index]\nlibraries = ["stdlib", "mathcomp"]\n')
        result = load_config(tmp_path)
        assert result == ["stdlib", "mathcomp"]

    def test_all_six_libraries(self, tmp_path):
        """§4.2: All 6 valid identifiers are accepted."""
        all_libs = list(VALID_LIBRARIES)
        config = tmp_path / "config.toml"
        config.write_text(f'[index]\nlibraries = {all_libs}\n')
        result = load_config(tmp_path)
        assert set(result) == VALID_LIBRARIES

    def test_single_library(self, tmp_path):
        """§4.2: A single-element list is valid."""
        config = tmp_path / "config.toml"
        config.write_text('[index]\nlibraries = ["flocq"]\n')
        result = load_config(tmp_path)
        assert result == ["flocq"]

    def test_default_when_no_config_file(self, tmp_path):
        """§4.2: Given no config.toml exists, returns ["stdlib"]."""
        result = load_config(tmp_path)
        assert result == ["stdlib"]

    def test_unknown_library_raises_error(self, tmp_path):
        """§4.2: Unknown identifier raises error listing valid options."""
        config = tmp_path / "config.toml"
        config.write_text('[index]\nlibraries = ["stdlib", "unknown"]\n')
        with pytest.raises(Exception, match="Unknown library 'unknown'"):
            load_config(tmp_path)

    def test_unknown_library_error_lists_valid(self, tmp_path):
        """§4.2: Error message includes all valid library names."""
        config = tmp_path / "config.toml"
        config.write_text('[index]\nlibraries = ["badlib"]\n')
        with pytest.raises(Exception, match="stdlib") as exc_info:
            load_config(tmp_path)
        msg = str(exc_info.value)
        for lib in VALID_LIBRARIES:
            assert lib in msg

    def test_empty_library_list_raises_error(self, tmp_path):
        """§4.2: Empty list raises error."""
        config = tmp_path / "config.toml"
        config.write_text('[index]\nlibraries = []\n')
        with pytest.raises(Exception, match="At least one library must be selected"):
            load_config(tmp_path)

    def test_malformed_toml_raises_error(self, tmp_path):
        """§4.2: Malformed TOML raises an error."""
        config = tmp_path / "config.toml"
        config.write_text('not valid toml [[[')
        with pytest.raises(Exception):
            load_config(tmp_path)

    def test_missing_index_section_uses_default(self, tmp_path):
        """§4.2: Config exists but has no [index] section — treat as no config."""
        config = tmp_path / "config.toml"
        config.write_text('[other]\nfoo = "bar"\n')
        # Spec says file must contain valid [index] section with libraries list.
        # Missing section should either default or error — spec says "malformed" raises error.
        # Since spec says "contains a valid [index] section with a libraries list" is the
        # success case, a missing section falls to the default behavior.
        result = load_config(tmp_path)
        assert result == ["stdlib"]

    def test_nonexistent_directory(self, tmp_path):
        """§4.2: libraries_dir may not exist yet — returns default."""
        nonexistent = tmp_path / "does-not-exist"
        result = load_config(nonexistent)
        assert result == ["stdlib"]


class TestGetLibrariesDir:
    """get_libraries_dir resolves the libraries directory path."""

    def test_default_path(self):
        """§4.2: Without env var, returns ~/poule-libraries."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove POULE_LIBRARIES_PATH if set
            env = os.environ.copy()
            env.pop("POULE_LIBRARIES_PATH", None)
            with patch.dict(os.environ, env, clear=True):
                result = get_libraries_dir()
        assert result == Path.home() / "poule-libraries"

    def test_env_var_override(self):
        """§4.2: POULE_LIBRARIES_PATH overrides default."""
        with patch.dict(os.environ, {"POULE_LIBRARIES_PATH": "/custom/path"}):
            result = get_libraries_dir()
        assert result == Path("/custom/path")

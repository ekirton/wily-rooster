"""Tests for container startup index check.

Spec: specification/prebuilt-distribution.md §4.2, §4.8
Arch: doc/architecture/prebuilt-distribution.md (Container Startup)

Import paths under test:
  Poule.cli.startup_check.startup_check
  Poule.cli.startup_check._read_indexed_libraries
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from Poule.storage import IndexWriter
from Poule.cli.startup_check import (
    _read_indexed_libraries,
    _read_library_versions,
    startup_check,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_per_library_db(
    path: Path,
    library_name: str,
    coq_version: str = "8.19.2",
    schema_version: str = "1",
    library_version: str = "1.0.0",
) -> Path:
    """Create a minimal per-library index database."""
    decl = {
        "name": f"{library_name}.test_decl",
        "module": library_name,
        "kind": "definition",
        "statement": "test",
        "type_expr": "nat",
        "constr_tree": None,
        "node_count": 1,
        "symbol_set": [],
    }
    writer = IndexWriter.create(path)
    writer.insert_declarations([decl])
    writer.insert_wl_vectors([])
    writer.insert_symbol_freq({})
    writer.write_meta("schema_version", schema_version)
    writer.write_meta("coq_version", coq_version)
    writer.write_meta("libraries", json.dumps([library_name]))
    writer.write_meta("library_versions", json.dumps({library_name: library_version}))
    writer.write_meta("created_at", "2026-03-18T00:00:00Z")
    writer.finalize()
    return path


def _write_config(libs_dir: Path, libraries: list[str]) -> None:
    """Write a config.toml with the given libraries."""
    config = libs_dir / "config.toml"
    config.write_text(f'[index]\nlibraries = {json.dumps(libraries)}\n')


# ===========================================================================
# 1. _read_indexed_libraries
# ===========================================================================


class TestReadIndexedLibraries:
    """Read library set from index.db metadata."""

    def test_returns_empty_when_no_index(self, tmp_path):
        """No index.db → empty set."""
        result = _read_indexed_libraries(tmp_path / "index.db")
        assert result == set()

    def test_reads_libraries_from_metadata(self, tmp_path):
        """Reads libraries JSON array from index_meta."""
        from Poule.storage.merge import merge_indexes

        db = _create_per_library_db(tmp_path / "index-stdlib.db", "stdlib")
        dest = tmp_path / "index.db"
        merge_indexes([("stdlib", db)], dest)
        result = _read_indexed_libraries(dest)
        assert result == {"stdlib"}

    def test_reads_multiple_libraries(self, tmp_path):
        """Two libraries merged → both returned."""
        from Poule.storage.merge import merge_indexes

        db1 = _create_per_library_db(tmp_path / "index-stdlib.db", "stdlib")
        db2 = _create_per_library_db(tmp_path / "index-mathcomp.db", "mathcomp")
        dest = tmp_path / "index.db"
        merge_indexes([("stdlib", db1), ("mathcomp", db2)], dest)
        result = _read_indexed_libraries(dest)
        assert result == {"stdlib", "mathcomp"}


# ===========================================================================
# 2. startup_check — config matches index
# ===========================================================================


class TestStartupCheckMatches:
    """When config matches index, no rebuild occurs."""

    def test_no_rebuild_when_config_matches(self, tmp_path):
        """Config lists stdlib, index.db contains stdlib → no merge called."""
        from Poule.storage.merge import merge_indexes

        db = _create_per_library_db(
            tmp_path / "index-stdlib.db", "stdlib", library_version="8.19.2"
        )
        merge_indexes([("stdlib", db)], tmp_path / "index.db")
        _write_config(tmp_path, ["stdlib"])

        with patch("Poule.cli.startup_check.merge_indexes") as mock_merge:
            startup_check(tmp_path)
            mock_merge.assert_not_called()


# ===========================================================================
# 3. startup_check — config differs from index
# ===========================================================================


class TestStartupCheckMismatch:
    """When config differs from index, rebuild occurs."""

    def test_rebuilds_when_library_added(self, tmp_path):
        """Config adds mathcomp, only stdlib indexed → merge called."""
        from Poule.storage.merge import merge_indexes as real_merge

        db1 = _create_per_library_db(
            tmp_path / "index-stdlib.db", "stdlib", library_version="8.19.2"
        )
        real_merge([("stdlib", db1)], tmp_path / "index.db")

        # Add mathcomp per-library db and update config
        _create_per_library_db(
            tmp_path / "index-mathcomp.db", "mathcomp", library_version="2.2.0"
        )
        _write_config(tmp_path, ["stdlib", "mathcomp"])

        startup_check(tmp_path)

        # Verify the merged index now has both libraries
        result = _read_indexed_libraries(tmp_path / "index.db")
        assert result == {"stdlib", "mathcomp"}

    def test_rebuilds_when_library_removed(self, tmp_path):
        """Config has only stdlib, index has stdlib+mathcomp → rebuild."""
        from Poule.storage.merge import merge_indexes as real_merge

        db1 = _create_per_library_db(
            tmp_path / "index-stdlib.db", "stdlib", library_version="8.19.2"
        )
        db2 = _create_per_library_db(
            tmp_path / "index-mathcomp.db", "mathcomp", library_version="2.2.0"
        )
        real_merge([("stdlib", db1), ("mathcomp", db2)], tmp_path / "index.db")

        _write_config(tmp_path, ["stdlib"])

        startup_check(tmp_path)

        result = _read_indexed_libraries(tmp_path / "index.db")
        assert result == {"stdlib"}

    def test_builds_from_scratch_when_no_index(self, tmp_path):
        """No index.db, per-library files exist → merge creates index.db."""
        _create_per_library_db(
            tmp_path / "index-stdlib.db", "stdlib", library_version="8.19.2"
        )
        _write_config(tmp_path, ["stdlib"])

        startup_check(tmp_path)

        assert (tmp_path / "index.db").exists()
        result = _read_indexed_libraries(tmp_path / "index.db")
        assert result == {"stdlib"}


# ===========================================================================
# 4. startup_check — missing per-library files trigger download
# ===========================================================================


class TestStartupCheckDownload:
    """When per-library index files are missing, download is attempted."""

    def test_downloads_missing_libraries(self, tmp_path):
        """Config lists stdlib but index-stdlib.db missing → download called."""
        _write_config(tmp_path, ["stdlib"])

        with patch("Poule.cli.startup_check._download_missing") as mock_dl:
            startup_check(tmp_path)
            mock_dl.assert_called_once()
            args = mock_dl.call_args[0]
            assert "stdlib" in args[1]  # missing list

    def test_skips_download_when_files_exist(self, tmp_path):
        """Per-library files exist, no index.db → merge only, no download."""
        _create_per_library_db(
            tmp_path / "index-stdlib.db", "stdlib", library_version="8.19.2"
        )
        _write_config(tmp_path, ["stdlib"])

        with patch("Poule.cli.startup_check._download_missing") as mock_dl:
            startup_check(tmp_path)
            mock_dl.assert_not_called()


# ===========================================================================
# 5. startup_check — default config
# ===========================================================================


class TestStartupCheckDefaultConfig:
    """When no config.toml exists, defaults to stdlib."""

    def test_defaults_to_stdlib(self, tmp_path):
        """No config.toml → acts as if libraries = ["stdlib"]."""
        _create_per_library_db(
            tmp_path / "index-stdlib.db", "stdlib", library_version="8.19.2"
        )
        # No config.toml written

        startup_check(tmp_path)

        result = _read_indexed_libraries(tmp_path / "index.db")
        assert result == {"stdlib"}


# ===========================================================================
# 6. Entrypoint wiring
# ===========================================================================


class TestEntrypointWiring:
    """Verify the entrypoint calls the startup check."""

    def test_entrypoint_contains_startup_check(self):
        """docker/entrypoint.sh invokes the startup check module."""
        entrypoint = Path("/poule/docker/entrypoint.sh")
        if not entrypoint.exists():
            pytest.skip("entrypoint.sh not found")
        content = entrypoint.read_text()
        assert "startup_check" in content, (
            "entrypoint.sh must invoke Poule.cli.startup_check"
        )

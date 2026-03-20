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


def _create_index_db(
    path: Path,
    libraries: list[str],
    library_versions: dict[str, str] | None = None,
    coq_version: str = "8.19.2",
    schema_version: str = "1",
) -> Path:
    """Create a minimal merged index.db with the given libraries."""
    if library_versions is None:
        library_versions = {lib: "1.0.0" for lib in libraries}

    writer = IndexWriter.create(path)
    decls = []
    for lib in libraries:
        decls.append({
            "name": f"{lib}.test_decl",
            "module": lib,
            "kind": "definition",
            "statement": "test",
            "type_expr": "nat",
            "constr_tree": None,
            "node_count": 1,
            "symbol_set": [],
        })
    writer.insert_declarations(decls)
    writer.insert_wl_vectors([])
    writer.insert_symbol_freq({})
    writer.write_meta("schema_version", schema_version)
    writer.write_meta("coq_version", coq_version)
    writer.write_meta("libraries", json.dumps(libraries))
    writer.write_meta("library_versions", json.dumps(library_versions))
    writer.write_meta("created_at", "2026-03-18T00:00:00Z")
    writer.finalize()
    return path


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
        dest = tmp_path / "index.db"
        _create_index_db(dest, ["stdlib"])
        result = _read_indexed_libraries(dest)
        assert result == {"stdlib"}

    def test_reads_multiple_libraries(self, tmp_path):
        """Multiple libraries in index → all returned."""
        dest = tmp_path / "index.db"
        _create_index_db(dest, ["stdlib", "mathcomp"])
        result = _read_indexed_libraries(dest)
        assert result == {"stdlib", "mathcomp"}


# ===========================================================================
# 2. startup_check — index.db exists
# ===========================================================================


class TestStartupCheckExists:
    """When index.db exists, startup_check reports status without downloading."""

    def test_reports_status_when_index_exists(self, tmp_path, capsys):
        """index.db present → reports libraries, no warning."""
        _create_index_db(
            tmp_path / "index.db",
            ["stdlib", "mathcomp"],
            {"stdlib": "8.19.2", "mathcomp": "2.2.0"},
        )

        startup_check(tmp_path)

        captured = capsys.readouterr()
        assert "stdlib 8.19.2" in captured.err
        assert "mathcomp 2.2.0" in captured.err
        assert "WARNING" not in captured.err

    def test_reports_all_six_libraries(self, tmp_path, capsys):
        """index.db with all 6 libraries → all reported."""
        all_libs = ["stdlib", "mathcomp", "stdpp", "flocq", "coquelicot", "coqinterval"]
        versions = {lib: f"{i}.0.0" for i, lib in enumerate(all_libs)}
        _create_index_db(tmp_path / "index.db", all_libs, versions)

        startup_check(tmp_path)

        captured = capsys.readouterr()
        for lib in all_libs:
            assert lib in captured.err


# ===========================================================================
# 3. startup_check — index.db missing prints warning
# ===========================================================================


class TestStartupCheckMissing:
    """When index.db is missing, startup_check warns without downloading."""

    def test_warns_when_index_missing(self, tmp_path, capsys):
        """No index.db → warning printed, no download attempted."""
        startup_check(tmp_path)

        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "index.db not found" in captured.err

    def test_suggests_rebuild(self, tmp_path, capsys):
        """Warning message tells user how to fix."""
        startup_check(tmp_path)

        captured = capsys.readouterr()
        assert "Rebuild the container image" in captured.err

    def test_returns_without_crash(self, tmp_path):
        """Missing index.db does not raise."""
        startup_check(tmp_path)  # should not raise


# ===========================================================================
# 4. _read_library_versions
# ===========================================================================


class TestReadLibraryVersions:
    """Read library version metadata from index.db."""

    def test_returns_empty_when_no_index(self, tmp_path):
        """No index.db → empty dict."""
        result = _read_library_versions(tmp_path / "index.db")
        assert result == {}

    def test_reads_versions(self, tmp_path):
        """Reads library_versions JSON from index_meta."""
        dest = tmp_path / "index.db"
        versions = {"stdlib": "8.19.2", "mathcomp": "2.2.0"}
        _create_index_db(dest, ["stdlib", "mathcomp"], versions)
        result = _read_library_versions(dest)
        assert result == versions


# ===========================================================================
# 5. Entrypoint wiring
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

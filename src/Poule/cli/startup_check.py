"""Container startup index check.

Verifies that index.db exists in the data directory. If missing,
prints a warning — the index is baked into the image at build time
so a missing index means the image was built incorrectly or the
file was deleted.  The startup check never downloads at runtime
because a downloaded index may not match the installed library
versions.

Called by the container entrypoint before starting the MCP server.

Spec: specification/prebuilt-distribution.md §4.2, §4.8, §4.9
Arch: doc/architecture/prebuilt-distribution.md (Container Startup)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def _read_indexed_libraries(index_path: Path) -> set[str]:
    """Read the set of library identifiers from index.db metadata."""
    if not index_path.exists():
        return set()
    try:
        conn = sqlite3.connect(str(index_path))
        row = conn.execute(
            "SELECT value FROM index_meta WHERE key = 'libraries'"
        ).fetchone()
        conn.close()
        if row:
            return set(json.loads(row[0]))
    except Exception:
        pass
    return set()


def _read_library_versions(index_path: Path) -> dict[str, str]:
    """Read library_versions from index.db metadata."""
    if not index_path.exists():
        return {}
    try:
        conn = sqlite3.connect(str(index_path))
        row = conn.execute(
            "SELECT value FROM index_meta WHERE key = 'library_versions'"
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return {}


def startup_check(libraries_dir: Path) -> None:
    """Check that index.db exists; warn if missing."""
    libraries_dir.mkdir(parents=True, exist_ok=True)
    index_path = libraries_dir / "index.db"

    if not index_path.exists():
        print(
            "[poule] WARNING: index.db not found at "
            f"{index_path}. Search will not work.",
            file=sys.stderr,
        )
        print(
            "[poule] Rebuild the container image to bake in the index.",
            file=sys.stderr,
        )
        return

    libraries = sorted(_read_indexed_libraries(index_path))
    versions = _read_library_versions(index_path)
    _report_status(libraries, versions)


def _report_status(libraries: list[str], versions: dict[str, str]) -> None:
    """Print the startup status line."""
    parts = []
    for lib in libraries:
        ver = versions.get(lib, "?")
        parts.append(f"{lib} {ver}")
    print(f"[poule] Indexed libraries: {', '.join(parts)}", file=sys.stderr)


def main() -> None:
    """Entry point for ``python -m Poule.cli.startup_check``."""
    startup_check(Path("/data"))


if __name__ == "__main__":
    main()

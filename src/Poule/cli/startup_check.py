"""Container startup index check.

Verifies that index.db exists in the data directory. If missing,
downloads the pre-merged index from the latest GitHub Release.
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


def _download_index(dest: Path) -> None:
    """Download the pre-merged index.db from the latest GitHub Release."""
    from Poule.cli.download import (
        _download_and_verify,
        _find_asset,
        _find_latest_release,
    )
    import urllib.request

    release = _find_latest_release()
    manifest_asset = _find_asset(release, "manifest.json")
    req = urllib.request.Request(manifest_asset["browser_download_url"])
    with urllib.request.urlopen(req) as resp:
        manifest = json.loads(resp.read().decode())

    index_entry = manifest.get("index")
    if index_entry is None:
        raise RuntimeError("No 'index' entry in release manifest.")

    asset_name = index_entry["asset_name"]
    expected_sha = index_entry["sha256"]
    _download_and_verify(release, asset_name, dest, expected_sha, asset_name)


def startup_check(libraries_dir: Path) -> None:
    """Check that index.db exists, downloading if needed."""
    libraries_dir.mkdir(parents=True, exist_ok=True)
    index_path = libraries_dir / "index.db"

    if not index_path.exists():
        print("[poule] Downloading index...", file=sys.stderr)
        try:
            _download_index(index_path)
        except Exception as exc:
            print(f"[poule] Download failed: {exc}", file=sys.stderr)
            print(
                "[poule] Run 'poule download-index' to download manually.",
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

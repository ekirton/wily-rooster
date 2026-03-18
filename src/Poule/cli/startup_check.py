"""Container startup index check.

Compares the user's library configuration against the current index.db
and downloads/merges as needed. Called by the container entrypoint
before starting the MCP server.

Spec: specification/prebuilt-distribution.md §4.2, §4.8, §4.9
Arch: doc/architecture/prebuilt-distribution.md (Container Startup)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from Poule.config import load_config
from Poule.storage.merge import merge_indexes


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
    """Check index configuration and rebuild if needed.

    Parameters
    ----------
    libraries_dir
        Directory containing config.toml, per-library index files,
        and the merged index.db.
    """
    libraries_dir.mkdir(parents=True, exist_ok=True)

    # 1. Read configuration
    try:
        configured = load_config(libraries_dir)
    except Exception as exc:
        print(f"[poule] Config error: {exc}", file=sys.stderr)
        configured = ["stdlib"]

    configured_set = set(configured)

    # 2. Check current index.db
    index_path = libraries_dir / "index.db"
    indexed_set = _read_indexed_libraries(index_path)

    # 3. Compare
    if configured_set == indexed_set and index_path.exists():
        # Index matches config — report and return
        versions = _read_library_versions(index_path)
        _report_status(configured, versions)
        return

    # 4. Check which per-library index files are available
    missing = []
    available = []
    for lib in configured:
        lib_path = libraries_dir / f"index-{lib}.db"
        if lib_path.exists():
            available.append((lib, lib_path))
        else:
            missing.append(lib)

    # 5. Download missing per-library indexes
    if missing:
        print(
            f"[poule] Downloading missing indexes: {', '.join(missing)}",
            file=sys.stderr,
        )
        try:
            _download_missing(libraries_dir, missing)
        except Exception as exc:
            print(f"[poule] Download failed: {exc}", file=sys.stderr)
            # Continue with whatever we have

        # Re-check available after download
        available = []
        for lib in configured:
            lib_path = libraries_dir / f"index-{lib}.db"
            if lib_path.exists():
                available.append((lib, lib_path))

    if not available:
        print(
            "[poule] No per-library indexes available. "
            "Run 'poule download-index' to download.",
            file=sys.stderr,
        )
        return

    # 6. Merge
    print(
        f"[poule] Building index from {len(available)} "
        f"{'library' if len(available) == 1 else 'libraries'}...",
        file=sys.stderr,
    )
    try:
        result = merge_indexes(available, index_path)
        print(
            f"[poule] Merged {result['total_declarations']} declarations",
            file=sys.stderr,
        )
    except Exception as exc:
        print(f"[poule] Merge failed: {exc}", file=sys.stderr)
        return

    # 7. Report status
    versions = _read_library_versions(index_path)
    _report_status(configured, versions)


def _report_status(configured: list[str], versions: dict[str, str]) -> None:
    """Print the startup status line."""
    parts = []
    for lib in configured:
        ver = versions.get(lib, "?")
        parts.append(f"{lib} {ver}")
    print(f"[poule] Indexed libraries: {', '.join(parts)}", file=sys.stderr)


def _download_missing(libraries_dir: Path, missing: list[str]) -> None:
    """Download missing per-library indexes from the latest release."""
    from Poule.cli.download import (
        _download_and_verify,
        _find_asset,
        _find_latest_release,
    )
    import json
    import urllib.request

    release = _find_latest_release()
    manifest_asset = _find_asset(release, "manifest.json")
    req = urllib.request.Request(manifest_asset["browser_download_url"])
    with urllib.request.urlopen(req) as resp:
        manifest = json.loads(resp.read().decode())

    for lib in missing:
        lib_entry = manifest["libraries"].get(lib)
        if lib_entry is None:
            print(
                f"[poule]   Warning: '{lib}' not in release manifest.",
                file=sys.stderr,
            )
            continue
        asset_name = lib_entry["asset_name"]
        expected_sha = lib_entry["sha256"]
        dest = libraries_dir / asset_name
        _download_and_verify(release, asset_name, dest, expected_sha, asset_name)


def main() -> None:
    """Entry point for ``python -m Poule.cli.startup_check``."""
    startup_check(Path("/data"))


if __name__ == "__main__":
    main()

"""Library configuration loading.

Reads config.toml from the libraries directory and returns the list of
libraries to index.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import click

VALID_LIBRARIES = frozenset({
    "stdlib", "mathcomp", "stdpp", "flocq", "coquelicot", "coqinterval",
})

DEFAULT_LIBRARIES = ["stdlib"]


def load_config(libraries_dir: Path) -> list[str]:
    """Load library configuration from *libraries_dir*/config.toml.

    Returns the list of library identifiers to index.  Falls back to
    ``["stdlib"]`` when the file or the ``[index]`` section is absent.
    """
    config_path = libraries_dir / "config.toml"

    if not config_path.is_file():
        return list(DEFAULT_LIBRARIES)

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    index = data.get("index")
    if index is None:
        return list(DEFAULT_LIBRARIES)

    libraries = index.get("libraries")
    if libraries is None:
        return list(DEFAULT_LIBRARIES)

    if not libraries:
        raise click.ClickException("At least one library must be selected")

    for lib in libraries:
        if lib not in VALID_LIBRARIES:
            valid_str = ", ".join(sorted(VALID_LIBRARIES))
            raise click.ClickException(
                f"Unknown library '{lib}'. Valid libraries: {valid_str}"
            )

    return list(libraries)


def get_libraries_dir() -> Path:
    """Return the path to the libraries directory (``~/poule-home/data``)."""
    d = Path.home() / "poule-home" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d

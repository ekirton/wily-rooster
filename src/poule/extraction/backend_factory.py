"""Backend factory and auto-detection for Coq extraction backends."""

from __future__ import annotations

import shutil

from .coq_backend import CoqBackend
from .errors import CoqNotInstalledError


def create_coq_backend(backend_type: str | None = None) -> CoqBackend:
    """Create and return a Coq backend instance.

    Parameters
    ----------
    backend_type:
        Explicit backend selection: ``"coqlsp"`` or ``"serapi"``.
        If ``None``, auto-detect by probing for ``coq-lsp`` first,
        then ``sertop``.

    Returns
    -------
    CoqBackend
        An initialized backend instance.

    Raises
    ------
    CoqNotInstalledError
        If neither coq-lsp nor sertop is found on the system.
    """
    if backend_type == "coqlsp":
        from poule.extraction.backends.coqlsp_backend import CoqLspBackend  # type: ignore[import-not-found]
        return CoqLspBackend()

    if backend_type == "serapi":
        from poule.extraction.backends.serapi_backend import SerAPIBackend  # type: ignore[import-not-found]
        return SerAPIBackend()

    # Auto-detect: try coq-lsp first, then sertop
    if shutil.which("coq-lsp") is not None:
        from poule.extraction.backends.coqlsp_backend import CoqLspBackend  # type: ignore[import-not-found]
        return CoqLspBackend()

    if shutil.which("sertop") is not None:
        from poule.extraction.backends.serapi_backend import SerAPIBackend  # type: ignore[import-not-found]
        return SerAPIBackend()

    raise CoqNotInstalledError()

"""Extraction backends for communicating with Coq toolchain."""

from .coqlsp_backend import CoqLspBackend

try:
    from .serapi_backend import SerAPIBackend
except ImportError:
    SerAPIBackend = None  # type: ignore[assignment,misc]

__all__ = ["CoqLspBackend", "SerAPIBackend"]

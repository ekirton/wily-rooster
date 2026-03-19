"""Error types and error code constants for the compatibility analysis engine."""

from __future__ import annotations

# Error code constants (spec section 7)
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
NO_DEPENDENCIES = "NO_DEPENDENCIES"
INVALID_PARAMETER = "INVALID_PARAMETER"
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
PACKAGE_NOT_FOUND = "PACKAGE_NOT_FOUND"
OPAM_TIMEOUT = "OPAM_TIMEOUT"
CONSTRAINT_PARSE_ERROR = "CONSTRAINT_PARSE_ERROR"


class CompatError(Exception):
    """Structured error raised by the compatibility analysis engine."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

"""Error codes and exception type for the session manager."""

from __future__ import annotations


FILE_NOT_FOUND = "FILE_NOT_FOUND"
PROOF_NOT_FOUND = "PROOF_NOT_FOUND"
SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
SESSION_EXPIRED = "SESSION_EXPIRED"
BACKEND_CRASHED = "BACKEND_CRASHED"
TACTIC_ERROR = "TACTIC_ERROR"
STEP_OUT_OF_RANGE = "STEP_OUT_OF_RANGE"
NO_PREVIOUS_STATE = "NO_PREVIOUS_STATE"
PROOF_COMPLETE = "PROOF_COMPLETE"


class SessionError(Exception):
    """Structured error raised by the session manager."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}" if message else code)

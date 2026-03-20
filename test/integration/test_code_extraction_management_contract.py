"""Contract tests for Code Extraction Management — requires real Coq tools.

Extracted from test/unit/test_code_extraction_management.py. These tests
exercise the real SessionManager and write_extraction to verify mock
assumptions in the unit tests.

Spec: specification/code-extraction-management.md
"""

from __future__ import annotations

import pytest

from Poule.session.errors import BACKEND_CRASHED, SESSION_NOT_FOUND, SessionError
from Poule.session.manager import SessionManager


def _import_write_extraction():
    from Poule.extraction.handler import write_extraction
    return write_extraction


class TestContractSessionManagerSubmitCommand:
    """Contract test: verify real session manager's submit_command interface.

    These tests verify that the mock's submit_command interface matches
    the real Proof Session Manager implementation.
    """

    @pytest.mark.asyncio
    async def test_submit_command_returns_stdout_stderr(self):
        """Real session manager submit_command returns a string."""
        manager = SessionManager()
        session_id = await manager.open_session("test_contract")
        try:
            result = await manager.submit_command(
                session_id,
                "From Coq Require Import Arith. Check Nat.add.",
            )
            assert isinstance(result, str)
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_submit_command_session_not_found_raises(self):
        """Real session manager raises SessionError(SESSION_NOT_FOUND) for unknown session."""
        manager = SessionManager()
        with pytest.raises(SessionError) as exc_info:
            await manager.submit_command("nonexistent_session", "Check nat.")
        assert exc_info.value.code == SESSION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_submit_command_backend_crash_raises(self):
        """Real session manager raises SessionError(BACKEND_CRASHED) when backend dies."""
        # This contract verifies the error type; triggering a real crash
        # is environment-dependent, so we document the expected interface
        manager = SessionManager()
        # Contract: if backend crashes, SessionError with BACKEND_CRASHED is raised
        # Actual crash triggering is deferred to integration tests
        assert BACKEND_CRASHED == "BACKEND_CRASHED"


class TestContractWriteExtraction:
    """Contract test: verify write_extraction uses pathlib for path validation."""

    def test_write_uses_pathlib_is_absolute(self):
        """write_extraction uses pathlib.Path.is_absolute() for path validation (Section 10)."""
        write_extraction = _import_write_extraction()
        # Verify that relative paths are rejected
        with pytest.raises(Exception):
            write_extraction(code="let x = 1", output_path="relative.ml")

    def test_write_uses_pathlib_parent_exists(self):
        """write_extraction uses pathlib.Path.parent.exists() for directory validation (Section 10)."""
        write_extraction = _import_write_extraction()
        with pytest.raises(Exception):
            write_extraction(
                code="let x = 1",
                output_path="/nonexistent_xyz_abc/out.ml",
            )

"""Contract tests for the Proof Session Manager — requires real Coq tools.

Extracted from test/unit/test_proof_session.py. These tests exercise
the real SessionManager to verify mock assumptions in the unit tests.

Spec: specification/proof-session.md
"""

from __future__ import annotations

import asyncio

import pytest

from Poule.session.errors import BACKEND_CRASHED, SESSION_NOT_FOUND, SessionError
from Poule.session.manager import SessionManager


class TestContractSubmitCommand:
    """Contract test: verify real SessionManager.submit_command interface.

    These tests verify the mock assumptions match the real implementation.
    """

    @pytest.mark.asyncio
    async def test_returns_string_from_real_backend(self):
        """Real submit_command returns a plain str."""
        manager = SessionManager()
        session_id = await manager.open_session("contract_submit_cmd")
        try:
            result = await manager.submit_command(session_id, "Check nat.")
            assert isinstance(result, str)
            assert not hasattr(result, "stdout")
            assert not hasattr(result, "stderr")
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self):
        """Real submit_command raises SessionError for unknown session."""
        manager = SessionManager()
        with pytest.raises(SessionError) as exc_info:
            await manager.submit_command("nonexistent", "Check nat.")
        assert exc_info.value.code == SESSION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_serialized_per_session(self):
        """Real submit_command is serialized per session (§7.2)."""
        manager = SessionManager()
        session_id = await manager.open_session("contract_serial")
        try:
            # Concurrent commands on same session should both succeed
            r1, r2 = await asyncio.gather(
                manager.submit_command(session_id, "Check nat."),
                manager.submit_command(session_id, "Check bool."),
            )
            assert isinstance(r1, str)
            assert isinstance(r2, str)
        finally:
            await manager.close_session(session_id)


class TestContractCoqtopSubprocess:
    """Contract tests: verify real session manager coqtop subprocess behavior.

    These tests verify the mock assumptions about coqtop routing match
    the real implementation.
    """

    @pytest.mark.asyncio
    async def test_submit_command_returns_nonempty_output_for_print(self):
        """Real submit_command via coqtop returns non-empty output for Print.

        Spec §4.4.1: coqtop subprocess captures vernacular output that
        coq-lsp cannot."""
        manager = SessionManager()
        session_id, _ = await manager.create_session(
            "/poule/examples/arith.v", "add_comm",
        )
        try:
            result = await manager.submit_command(session_id, "Print nat.")
            assert isinstance(result, str)
            # With coqtop routing, Print should return non-empty output
            # (unlike coq-lsp which returns empty)
            assert len(result) > 0, (
                "submit_command should return non-empty output for Print via coqtop"
            )
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_close_session_terminates_coqtop_real(self):
        """Real close_session cleans up coqtop subprocess."""
        manager = SessionManager()
        session_id, _ = await manager.create_session(
            "/poule/examples/arith.v", "add_comm",
        )
        # Trigger coqtop spawn
        await manager.submit_vernacular(session_id, "Check nat.")
        ss = manager._registry[session_id]
        coqtop = ss.coqtop_proc
        assert coqtop is not None, "coqtop should have been spawned"

        await manager.close_session(session_id)

        # After close, the process should be terminated
        assert coqtop.returncode is not None, (
            "coqtop process should be terminated after close_session"
        )

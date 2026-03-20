"""Contract tests for vernacular command output capture via real session manager.

These tests require coqtop and coq-lsp to be installed.

Spec: specification/coq-proof-backend.md
      specification/proof-session.md
"""

from __future__ import annotations

import pytest


class TestSendCommandContract:
    """Contract tests verifying real session manager returns non-empty output.

    These tests require coqtop and coq-lsp to be installed.
    """

    @pytest.mark.asyncio
    async def test_print_nat_via_submit_vernacular(self):
        """Print nat. via submit_vernacular (prefer_coqtop) returns non-empty output."""
        from Poule.session.manager import SessionManager

        mgr = SessionManager()
        sid, _ = await mgr.create_session(
            "/poule/examples/arith.v", "add_comm",
        )
        try:
            result = await mgr.submit_vernacular(sid, "Print nat.")
            assert isinstance(result, str)
            assert len(result) > 0, "submit_vernacular returned empty for Print nat."
            assert "nat" in result.lower()
        finally:
            await mgr.close_session(sid)

    @pytest.mark.asyncio
    async def test_check_nat_via_submit_vernacular(self):
        """Check nat. via submit_vernacular returns non-empty output."""
        from Poule.session.manager import SessionManager

        mgr = SessionManager()
        sid, _ = await mgr.create_session(
            "/poule/examples/arith.v", "add_comm",
        )
        try:
            result = await mgr.submit_vernacular(sid, "Check nat.")
            assert isinstance(result, str)
            assert len(result) > 0, "submit_vernacular returned empty for Check nat."
        finally:
            await mgr.close_session(sid)

    @pytest.mark.asyncio
    async def test_session_loads_file_imports(self):
        """Queries in a proof session have access to the file's imports."""
        from Poule.session.manager import SessionManager

        mgr = SessionManager()
        # arith.v imports PeanoNat
        sid, _ = await mgr.create_session(
            "/poule/examples/arith.v", "add_comm",
        )
        try:
            result = await mgr.submit_vernacular(sid, "Check Nat.add_comm.")
            assert isinstance(result, str)
            assert len(result) > 0, "Nat.add_comm should be available via PeanoNat import"
        finally:
            await mgr.close_session(sid)

    @pytest.mark.asyncio
    async def test_send_command_without_prefer_coqtop_uses_lsp(self):
        """send_command (default) falls back to coq-lsp, which returns empty for Print."""
        from Poule.session.manager import SessionManager

        mgr = SessionManager()
        sid, _ = await mgr.create_session(
            "/poule/examples/arith.v", "add_comm",
        )
        try:
            # send_command without prefer_coqtop goes through coq-lsp
            result = await mgr.send_command(sid, "Print nat.")
            assert isinstance(result, str)
            # coq-lsp returns empty for successful Print — this documents the limitation
            assert result == "", "coq-lsp should return empty for Print (no diagnostics)"
        finally:
            await mgr.close_session(sid)

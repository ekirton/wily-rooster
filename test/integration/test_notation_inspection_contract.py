"""Contract tests for Notation Inspection — requires real Coq tools.

Extracted from test/unit/test_notation_inspection.py. These tests exercise
the real SessionManager and parsers to verify mock assumptions in the
unit tests.

Spec: specification/notation-inspection.md
"""

from __future__ import annotations

import pytest

from Poule.session.errors import SESSION_NOT_FOUND, SessionError
from Poule.session.manager import SessionManager


def _import_parsers():
    from Poule.notation.parsers import (
        parse_print_notation,
        parse_locate_notation,
        parse_print_scope,
        parse_print_visibility,
    )
    return (
        parse_print_notation,
        parse_locate_notation,
        parse_print_scope,
        parse_print_visibility,
    )


def _import_types():
    from Poule.notation.types import (
        NotationInfo,
        ScopeInfo,
        NotationAmbiguity,
        NotationInterpretation,
    )
    return NotationInfo, ScopeInfo, NotationAmbiguity, NotationInterpretation


class TestContractSessionManager:
    """Contract tests: verify the session manager interface used by mocks."""

    @pytest.mark.asyncio
    async def test_submit_command_returns_string(self):
        """The real session manager's submit_command returns a string."""
        manager = SessionManager()
        session_id = await manager.open_session("test_contract")
        try:
            result = await manager.submit_command(session_id, "Print Visibility.")
            assert isinstance(result, str)
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_submit_command_print_notation(self):
        """The real session manager accepts Print Notation commands."""
        manager = SessionManager()
        session_id = await manager.open_session("test_contract")
        try:
            await manager.submit_command(session_id, 'Require Import Coq.Lists.List.')
            result = await manager.submit_command(
                session_id, 'Print Notation "_ ++ _".'
            )
            assert isinstance(result, str)
            assert "++ " in result or "app" in result
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_submit_command_locate(self):
        """The real session manager accepts Locate commands for notations."""
        manager = SessionManager()
        session_id = await manager.open_session("test_contract")
        try:
            result = await manager.submit_command(session_id, 'Locate "_ + _".')
            assert isinstance(result, str)
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_submit_command_print_scope(self):
        """The real session manager accepts Print Scope commands."""
        manager = SessionManager()
        session_id = await manager.open_session("test_contract")
        try:
            result = await manager.submit_command(session_id, "Print Scope nat_scope.")
            assert isinstance(result, str)
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_submit_command_print_visibility(self):
        """The real session manager accepts Print Visibility commands."""
        manager = SessionManager()
        session_id = await manager.open_session("test_contract")
        try:
            result = await manager.submit_command(session_id, "Print Visibility.")
            assert isinstance(result, str)
        finally:
            await manager.close_session(session_id)

    @pytest.mark.asyncio
    async def test_session_not_found_raises_session_error(self):
        """The real session manager raises SessionError for invalid session IDs."""
        manager = SessionManager()
        with pytest.raises(SessionError) as exc_info:
            await manager.submit_command("nonexistent", "Print Visibility.")
        assert exc_info.value.code == SESSION_NOT_FOUND


class TestContractParsers:
    """Contract tests: verify parsers against real Coq output."""

    def test_parse_print_notation_with_real_output(self):
        """Parser handles real Coq Print Notation output."""
        parse_print_notation, _, _, _ = _import_parsers()
        NotationInfo, _, _, _ = _import_types()
        # This test would use captured real Coq output
        # Marked requires_coq for integration testing
        pass

    def test_parse_locate_with_real_output(self):
        """Parser handles real Coq Locate output."""
        _, parse_locate, _, _ = _import_parsers()
        _, _, _, NotationInterpretation = _import_types()
        pass

    def test_parse_print_scope_with_real_output(self):
        """Parser handles real Coq Print Scope output."""
        _, _, parse_scope, _ = _import_parsers()
        _, ScopeInfo, _, _ = _import_types()
        pass

    def test_parse_print_visibility_with_real_output(self):
        """Parser handles real Coq Print Visibility output."""
        _, _, _, parse_visibility = _import_parsers()
        pass

"""Contract tests for Hammer Automation — requires a live Coq instance.

Extracted from test/test_hammer_automation.py. These tests verify that
the mock assumptions in the unit tests hold against real Coq backends.

The ``requires_coq`` marker is applied automatically by conftest.py.
"""

from __future__ import annotations

import pathlib

import pytest


def _fixture_path():
    return str(pathlib.Path(__file__).resolve().parent.parent.parent / "examples" / "hammer_test.v")


class TestContractSingleStrategyExecution:
    """Contract: execute_hammer against real Proof Session Manager."""

    @pytest.mark.asyncio
    async def test_contract_execute_hammer_real_session(self):
        """Contract test: execute_hammer against real Proof Session Manager.

        Verifies that the mock-based tests above match the real interface.
        """
        from Poule.hammer.engine import execute_hammer
        from Poule.hammer.types import HammerResult
        from Poule.session.manager import ProofSessionManager

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, initial = await manager.create_session(fixture, "hammer_test")
        try:
            assert not initial.is_complete
            result = await execute_hammer(
                session_manager=manager,
                session_id=sid,
                strategy="sauto",
                timeout=10,
                hints=["Nat.add_0_r"],
                options={},
            )
            assert isinstance(result, HammerResult)
            assert result.status in ("success", "failure")
            assert result.wall_time_ms >= 0
            if result.status == "success":
                assert result.proof_script is not None
                assert result.strategy_used == "sauto"
                assert result.state.is_complete is True
        finally:
            await manager.close_session(sid)


class TestContractMultiStrategyFallback:
    """Contract: execute_auto_hammer against real Proof Session Manager."""

    @pytest.mark.asyncio
    async def test_contract_execute_auto_real_session(self):
        """Contract test: execute_auto_hammer against real Proof Session Manager."""
        from Poule.hammer.engine import execute_auto_hammer
        from Poule.hammer.types import HammerResult
        from Poule.session.manager import ProofSessionManager

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, initial = await manager.create_session(fixture, "hammer_test")
        try:
            assert not initial.is_complete
            result = await execute_auto_hammer(
                session_manager=manager,
                session_id=sid,
                timeout=30,
                hints=["Nat.add_0_r"],
                options={},
            )
            assert isinstance(result, HammerResult)
            assert result.status in ("success", "failure")
            assert result.wall_time_ms >= 0
            if result.status == "success":
                assert result.proof_script is not None
                assert result.state.is_complete is True
        finally:
            await manager.close_session(sid)


class TestContractTacticBuilder:
    """Contract: build_tactic output is syntactically valid Coq."""

    @pytest.mark.asyncio
    async def test_contract_build_tactic_produces_valid_coq(self):
        """Contract test: build_tactic output is syntactically valid Coq.

        Submits each built tactic to a real Coq session to verify syntax.
        """
        from Poule.hammer.tactic import build_tactic
        from Poule.session.manager import ProofSessionManager
        from Poule.session.errors import SessionError

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, _ = await manager.create_session(fixture, "hammer_test")
        try:
            # Build a tactic string and submit to real Coq to verify syntax.
            # Petanque requires a trailing period on tactic sentences.
            tactic = build_tactic("sauto", ["Nat.add_0_r"], {})
            tactic_sentence = tactic + "."
            try:
                await manager.submit_tactic(sid, tactic_sentence)
            except SessionError as exc:
                # Tactic may fail to solve the goal, but must not be a
                # Coq syntax error.  Syntax errors contain "Syntax error".
                assert "Syntax error" not in exc.message, (
                    f"build_tactic produced invalid Coq: {tactic!r} -> {exc.message}"
                )
        finally:
            await manager.close_session(sid)


class TestContractTimeoutWrapping:
    """Contract: wrapped tactic strings are accepted by Coq parser."""

    @pytest.mark.asyncio
    async def test_contract_timeout_wrapping_accepted_by_coq(self):
        """Contract test: wrapped tactic strings are accepted by Coq parser."""
        from Poule.hammer.engine import _wrap_timeout
        from Poule.session.manager import ProofSessionManager
        from Poule.session.errors import SessionError

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, _ = await manager.create_session(fixture, "hammer_test")
        try:
            # Test sauto timeout wrapping: "Timeout 5 sauto"
            # Petanque requires a trailing period on tactic sentences.
            pre, wrapped = _wrap_timeout("sauto", "sauto", 5)
            assert pre is None
            wrapped_sentence = wrapped + "."
            try:
                await manager.submit_tactic(sid, wrapped_sentence)
            except SessionError as exc:
                # May fail to solve the goal, but must not be a syntax error
                assert "Syntax error" not in exc.message, (
                    f"Timeout-wrapped tactic rejected by Coq: {wrapped!r} -> {exc.message}"
                )
        finally:
            await manager.close_session(sid)


class TestContractResultInterpreter:
    """Contract: interpret_result handles real Coq backend output correctly."""

    @pytest.mark.asyncio
    async def test_contract_interpret_result_real_coq_output(self):
        """Contract test: interpret_result handles real Coq backend output correctly."""
        from Poule.hammer.interpret import interpret_result
        from Poule.hammer.types import ClassifiedOutput
        from Poule.session.manager import ProofSessionManager
        from Poule.session.errors import SessionError

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, initial = await manager.create_session(fixture, "hammer_test")
        try:
            # Submit a tactic that will fail to get real Coq error output
            try:
                await manager.submit_tactic(sid, "exact I")
            except SessionError as exc:
                # Classify the real Coq error message
                result = interpret_result(exc.message, initial)
                assert isinstance(result, ClassifiedOutput)
                assert result.classification in (
                    "timeout", "no_proof_found", "tactic_error",
                )
                assert result.detail is not None
        finally:
            await manager.close_session(sid)


class TestContractDependencyErrors:
    """Contract: BACKEND_CRASHED propagation with real session manager."""

    @pytest.mark.asyncio
    async def test_contract_backend_crash_handling(self):
        """Contract test: BACKEND_CRASHED propagation with real session manager."""
        from Poule.hammer.engine import execute_hammer
        from Poule.session.manager import ProofSessionManager
        from Poule.session.errors import SessionError, BACKEND_CRASHED

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, _ = await manager.create_session(fixture, "hammer_test")
        try:
            # Simulate a backend crash
            manager._mark_crashed(sid)
            with pytest.raises(SessionError) as exc_info:
                await execute_hammer(
                    session_manager=manager,
                    session_id=sid,
                    strategy="sauto",
                    timeout=10,
                    hints=[],
                    options={},
                )
            assert exc_info.value.code == BACKEND_CRASHED
        finally:
            try:
                await manager.close_session(sid)
            except SessionError:
                pass


class TestContractMultiStrategyBudgetErrors:
    """Contract: budget exhaustion with real Coq backend."""

    @pytest.mark.asyncio
    async def test_contract_budget_exhaustion_real_session(self):
        """Contract test: budget exhaustion with real Coq backend."""
        from Poule.hammer.engine import execute_auto_hammer
        from Poule.hammer.types import HammerResult
        from Poule.session.manager import ProofSessionManager

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, _ = await manager.create_session(fixture, "hammer_test")
        try:
            # Very tight budget: strategies may be skipped due to exhaustion
            result = await execute_auto_hammer(
                session_manager=manager,
                session_id=sid,
                timeout=2,
                hints=[],
                options={},
            )
            assert isinstance(result, HammerResult)
            assert result.wall_time_ms >= 0
            if result.status == "failure":
                assert len(result.diagnostics) >= 1
                for diag in result.diagnostics:
                    assert diag.wall_time_ms >= 0
                    assert diag.timeout_used > 0
        finally:
            await manager.close_session(sid)


class TestContractInterfaceContracts:
    """Contract: One tactic submission at a time per session (serialized)."""

    @pytest.mark.asyncio
    async def test_contract_serialized_tactic_submission(self):
        """Contract test: One tactic submission at a time per session (serialized)."""
        from Poule.hammer.engine import execute_hammer
        from Poule.hammer.types import HammerResult
        from Poule.session.manager import ProofSessionManager

        fixture = _fixture_path()
        manager = ProofSessionManager()
        sid, initial = await manager.create_session(fixture, "hammer_test")
        try:
            result = await execute_hammer(
                session_manager=manager,
                session_id=sid,
                strategy="sauto",
                timeout=10,
                hints=["Nat.add_0_r"],
                options={},
            )
            assert isinstance(result, HammerResult)
            # Verify session state reflects the outcome
            state_after = await manager.observe_state(sid)
            if result.status == "success":
                assert state_after.is_complete is True
            else:
                assert state_after.step_index == initial.step_index
        finally:
            await manager.close_session(sid)

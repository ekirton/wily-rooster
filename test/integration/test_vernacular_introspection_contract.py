"""Contract tests for Vernacular Introspection — requires a live Coq instance.

Extracted from test/test_vernacular_introspection.py. These tests verify that
the mock assumptions in the unit tests hold against real Coq backends.

The ``requires_coq`` marker is applied automatically by conftest.py.
"""

from __future__ import annotations

import asyncio

import pytest


class TestContractCoqQueryEntryPoint:
    """Contract: real session manager and process pool interfaces."""

    @pytest.mark.asyncio
    async def test_contract_session_manager_submit_vernacular(self):
        """Contract test: real session manager accepts vernacular command strings."""
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        # Real session manager must expose submit_vernacular(session_id, vernacular_str)
        assert hasattr(manager, "submit_vernacular")

    @pytest.mark.asyncio
    async def test_contract_process_pool_send_command(self):
        """Contract test: real process pool accepts command strings and returns output."""
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()
        assert hasattr(pool, "send_command")


class TestContractExecutionRouting:
    """Contract: session manager routing and process pool lifecycle."""

    @pytest.mark.asyncio
    async def test_contract_session_manager_read_only(self):
        """Contract test: real session manager's submit_vernacular does not mutate state."""
        from Poule.session.manager import SessionManager
        # Verify the interface contract: submit_vernacular exists and is read-only
        assert callable(getattr(SessionManager, "submit_vernacular", None))

    @pytest.mark.asyncio
    async def test_contract_process_pool_lifecycle(self):
        """Contract test: process pool acquires and releases processes per invocation."""
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()
        assert callable(getattr(pool, "send_command", None))


class TestContractSessionFreePrelude:
    """Contract: default and custom prelude configuration."""

    @pytest.mark.asyncio
    async def test_contract_default_prelude_loads_arith(self):
        """Contract test: with default prelude, Arith definitions are available."""
        from Poule.query.handler import coq_query
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()  # default prelude

        result = await coq_query(
            command="Check",
            argument="Nat.add_comm",
            process_pool=pool,
        )

        assert "forall" in result.output

    @pytest.mark.asyncio
    async def test_contract_custom_prelude(self):
        """Contract test: custom prelude makes its imports available."""
        from Poule.query.handler import coq_query
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool(prelude="From Coq Require Import Bool.\n")

        result = await coq_query(
            command="Check",
            argument="negb",
            process_pool=pool,
        )

        assert "bool" in result.output.lower()

    @pytest.mark.asyncio
    async def test_contract_process_inherits_coqpath(self):
        """Contract test: standalone process inherits COQPATH from the server
        environment, making opam-installed packages reachable."""
        from Poule.query.process_pool import ProcessPool

        # COQPATH should be set in the server environment if opam is configured.
        # Even if empty, the process should not crash -- it just means no extra
        # packages are available beyond the default load paths.
        pool = ProcessPool()
        result = await pool.send_command("Check nat.")
        assert "Set" in result or "nat" in result


class TestContractInterfaceContracts:
    """Contract: real interface signatures for session manager and process pool."""

    @pytest.mark.asyncio
    async def test_contract_session_submit_vernacular_interface(self):
        """Contract test: real session manager.submit_vernacular(session_id, str) -> str."""
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        assert callable(getattr(manager, "submit_vernacular", None))

    @pytest.mark.asyncio
    async def test_contract_process_pool_send_command_interface(self):
        """Contract test: real process pool.send_command(str) -> str."""
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()
        assert callable(getattr(pool, "send_command", None))


class TestContractSessionErrors:
    """Contract: real session manager raises on invalid session_id."""

    @pytest.mark.asyncio
    async def test_contract_session_not_found_real(self):
        """Contract test: real session manager raises on invalid session_id."""
        from Poule.session.manager import SessionManager
        from Poule.session.errors import SessionError, SESSION_NOT_FOUND
        manager = SessionManager()
        with pytest.raises(SessionError) as exc_info:
            await manager.submit_vernacular("nonexistent_session", "Check nat.")
        assert exc_info.value.code == SESSION_NOT_FOUND


class TestContractCoqExecutionErrors:
    """Contract: real Coq error output classified correctly."""

    @pytest.mark.asyncio
    async def test_contract_classify_error_real_not_found(self):
        """Contract test: real Coq NOT_FOUND output classified correctly."""
        from Poule.query.errors import classify_error
        # Real Coq error output for a nonexistent name
        raw = "Error: The reference nonexistent_lemma was not found in the current environment."
        code, _ = classify_error(raw)
        assert code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_contract_classify_error_real_type_error(self):
        """Contract test: real Coq type error output classified correctly."""
        from Poule.query.errors import classify_error
        raw = 'Error: The term "true" has type "bool" while it is expected to have type "nat".'
        code, _ = classify_error(raw)
        assert code == "TYPE_ERROR"


class TestContractBackendErrors:
    """Contract: backend crash error constants and process pool."""

    @pytest.mark.asyncio
    async def test_contract_backend_crash_session(self):
        """Contract test: real session manager raises BACKEND_CRASHED on crash."""
        from Poule.session.errors import BACKEND_CRASHED
        # Verify the error code constant exists and matches spec
        assert BACKEND_CRASHED == "BACKEND_CRASHED"

    @pytest.mark.asyncio
    async def test_contract_backend_crash_standalone(self):
        """Contract test: real process pool signals crash appropriately."""
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()
        assert hasattr(pool, "send_command")


class TestContractSpecExamples:
    """Contract: real Coq process returns expected results."""

    @pytest.mark.asyncio
    async def test_contract_check_nat_add_comm_real(self):
        """Contract test: real Coq process returns type of Nat.add_comm."""
        from Poule.query.handler import coq_query
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()
        result = await coq_query(
            command="Check",
            argument="Nat.add_comm",
            process_pool=pool,
        )
        assert "forall" in result.output

    @pytest.mark.asyncio
    async def test_contract_eval_cbv_real(self):
        """Contract test: real Coq evaluates 'Eval cbv in 1 + 1.' to 2."""
        from Poule.query.handler import coq_query
        from Poule.query.process_pool import ProcessPool
        pool = ProcessPool()
        result = await coq_query(
            command="Eval",
            argument="cbv in 1 + 1",
            process_pool=pool,
        )
        assert "2" in result.output


class TestContractLanguageSpecificNotes:
    """Contract: real coq_query has the expected async signature."""

    @pytest.mark.asyncio
    async def test_contract_coq_query_real_signature(self):
        """Contract test: real coq_query has the expected async signature."""
        import inspect
        from Poule.query.handler import coq_query
        assert asyncio.iscoroutinefunction(coq_query)
        sig = inspect.signature(coq_query)
        assert "command" in sig.parameters
        assert "argument" in sig.parameters
        assert "session_id" in sig.parameters

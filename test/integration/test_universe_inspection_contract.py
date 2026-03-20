"""Contract tests for Universe Constraint Inspection — requires a live Coq instance.

Extracted from test/test_universe_inspection.py. These tests verify that
the mock assumptions in the unit tests hold against real Coq backends.

The ``requires_coq`` marker is applied automatically by conftest.py.
"""

from __future__ import annotations

import pytest


class TestContractFullGraphRetrieval:
    """Contract: real coq_query returns text that parses into a ConstraintGraph."""

    @pytest.mark.asyncio
    async def test_contract_retrieve_full_graph(self, coq_test_file):
        """Contract test: real coq_query returns text that parses into a ConstraintGraph."""
        from Poule.universe.retrieval import retrieve_full_graph
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            result = await retrieve_full_graph(manager, session_id)
            assert hasattr(result, "variables")
            assert hasattr(result, "constraints")
            assert result.node_count == len(result.variables)
        finally:
            await manager.close_session(session_id)


class TestContractDefinitionConstraintRetrieval:
    """Contract: real per-definition retrieval returns a ConstraintGraph."""

    @pytest.mark.asyncio
    async def test_contract_retrieve_definition_constraints(self, coq_test_file):
        """Contract test: real per-definition retrieval returns a ConstraintGraph."""
        from Poule.universe.retrieval import retrieve_definition_constraints
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            result = await retrieve_definition_constraints(
                manager, session_id, "nat",
            )
            assert hasattr(result, "filtered_from")
            assert result.filtered_from == "nat"
        finally:
            await manager.close_session(session_id)


class TestContractInconsistencyDiagnosis:
    """Contract: real diagnosis against a Coq backend."""

    @pytest.mark.asyncio
    async def test_contract_diagnose_universe_error(self, coq_test_file):
        """Contract test: real diagnosis against a Coq backend."""
        from Poule.universe.diagnosis import diagnose_universe_error
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            error_msg = (
                "Universe inconsistency: cannot enforce u.1 < u.2 "
                "because u.2 <= u.1 is already required"
            )
            result = await diagnose_universe_error(manager, session_id, error_msg, {})
            assert hasattr(result, "cycle")
            assert hasattr(result, "explanation")
            assert hasattr(result, "suggestions")
        finally:
            await manager.close_session(session_id)


class TestContractSourceAttribution:
    """Contract: real attribution queries About for definitions."""

    @pytest.mark.asyncio
    async def test_contract_attribution_uses_about_command(self, coq_test_file):
        """Contract test: real attribution queries About for definitions."""
        from Poule.universe.diagnosis import diagnose_universe_error
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            error_msg = (
                "Universe inconsistency: cannot enforce u.1 < u.2 "
                "because u.2 <= u.1 is already required"
            )
            result = await diagnose_universe_error(manager, session_id, error_msg, {})
            for attr in result.attributions:
                assert attr.confidence in ("certain", "inferred", "unknown")
        finally:
            await manager.close_session(session_id)


class TestContractPolymorphicInstantiationRetrieval:
    """Contract: real instantiation retrieval returns structured data."""

    @pytest.mark.asyncio
    async def test_contract_retrieve_instantiations(self, coq_test_file):
        """Contract test: real instantiation retrieval returns structured data."""
        from Poule.universe.polymorphic import retrieve_instantiations
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            result = await retrieve_instantiations(manager, session_id, "list")
            assert isinstance(result, list)
        finally:
            await manager.close_session(session_id)


class TestContractPolymorphicCompatibilityComparison:
    """Contract: real comparison against a Coq backend."""

    @pytest.mark.asyncio
    async def test_contract_compare_definitions(self, coq_test_file):
        """Contract test: real comparison against a Coq backend."""
        from Poule.universe.polymorphic import compare_definitions
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            result = await compare_definitions(manager, session_id, "nat", "bool")
            assert result is not None
        finally:
            await manager.close_session(session_id)


class TestContractInterfaceContracts:
    """Contract: coq_query returns raw text for Print Universes."""

    @pytest.mark.asyncio
    async def test_contract_coq_query_returns_text(self, coq_test_file):
        """Contract test: coq_query returns raw text for Print Universes."""
        from Poule.session.manager import SessionManager
        manager = SessionManager()
        session_id = await manager.create_session(str(coq_test_file), "test_proof")
        try:
            raw = await manager.coq_query(session_id, "Print Universes.")
            assert isinstance(raw, str)
        finally:
            await manager.close_session(session_id)

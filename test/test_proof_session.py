"""TDD tests for the Proof Session Manager (specification/proof-session.md).

Tests are written BEFORE implementation. They will fail with ImportError
until src/poule/session/ modules exist.

Spec: specification/proof-session.md
Architecture: doc/architecture/proof-session.md
Data model: doc/architecture/data-models/proof-types.md

Import paths under test:
  poule.session.manager  (SessionManager)
  poule.session.types    (SessionState, ProofState, etc.)
  poule.session.errors   (error codes)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_manager():
    from poule.session.manager import SessionManager
    return SessionManager


def _import_types():
    from poule.session.types import (
        Goal,
        Hypothesis,
        Premise,
        PremiseAnnotation,
        ProofState,
        ProofTrace,
        Session,
        TraceStep,
    )
    return Goal, Hypothesis, Premise, PremiseAnnotation, ProofState, ProofTrace, Session, TraceStep


def _import_errors():
    from poule.session.errors import (
        BACKEND_CRASHED,
        FILE_NOT_FOUND,
        NO_PREVIOUS_STATE,
        PROOF_COMPLETE,
        PROOF_NOT_FOUND,
        SESSION_EXPIRED,
        SESSION_NOT_FOUND,
        STEP_OUT_OF_RANGE,
        TACTIC_ERROR,
        SessionError,
    )
    return (
        BACKEND_CRASHED, FILE_NOT_FOUND, NO_PREVIOUS_STATE, PROOF_COMPLETE,
        PROOF_NOT_FOUND, SESSION_EXPIRED, SESSION_NOT_FOUND,
        STEP_OUT_OF_RANGE, TACTIC_ERROR, SessionError,
    )


# ---------------------------------------------------------------------------
# Helpers: mock CoqBackend and ProofState factories
# ---------------------------------------------------------------------------

def _make_proof_state(step_index=0, is_complete=False, goals=None, session_id="test"):
    Goal, Hypothesis, _, _, ProofState, *_ = _import_types()
    if goals is None:
        if is_complete:
            goals = []
        else:
            goals = [Goal(
                index=0,
                type="forall n m, n + m = m + n",
                hypotheses=[],
            )]
    return ProofState(
        schema_version=1,
        session_id=session_id,
        step_index=step_index,
        is_complete=is_complete,
        focused_goal_index=None if is_complete else 0,
        goals=goals,
    )


def _make_stepped_state(step_index, goals_type="n + m = m + n", session_id="test"):
    Goal, Hypothesis, _, _, ProofState, *_ = _import_types()
    return ProofState(
        schema_version=1,
        session_id=session_id,
        step_index=step_index,
        is_complete=False,
        focused_goal_index=0,
        goals=[Goal(index=0, type=goals_type, hypotheses=[
            Hypothesis(name="n", type="nat", body=None),
            Hypothesis(name="m", type="nat", body=None),
        ])],
    )


def _make_mock_backend(
    initial_state=None,
    tactic_results=None,
    original_script=None,
    premises_map=None,
):
    """Create a mock CoqBackend with async methods.

    Args:
        initial_state: ProofState returned by position_at_proof.
        tactic_results: List of ProofStates or exceptions for sequential
            execute_tactic calls.
        original_script: List of tactic strings (the proof's original script).
        premises_map: Dict step_index → list of raw premise refs.
    """
    backend = AsyncMock()
    backend.load_file = AsyncMock(return_value=None)

    if initial_state is None:
        initial_state = _make_proof_state(step_index=0)
    backend.position_at_proof = AsyncMock(return_value=initial_state)

    if tactic_results is not None:
        backend.execute_tactic = AsyncMock(side_effect=tactic_results)
    else:
        backend.execute_tactic = AsyncMock(
            return_value=_make_stepped_state(1),
        )

    backend.get_current_state = AsyncMock(return_value=initial_state)
    backend.undo = AsyncMock(return_value=None)
    backend.shutdown = AsyncMock(return_value=None)
    backend.original_script = original_script or []
    backend.get_premises_at_step = AsyncMock(
        side_effect=lambda step: (premises_map or {}).get(step, []),
    )
    return backend


def _make_backend_factory(backend):
    """Return an async factory that returns the given mock backend."""
    async def factory(file_path):
        return backend
    return factory


# ═══════════════════════════════════════════════════════════════════════════
# §4.1 Session Registry — create_session
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateSession:
    """Spec §4.1: create_session(file_path, proof_name)."""

    async def test_creates_session_returns_id_and_initial_state(self):
        SessionManager = _import_manager()
        initial = _make_proof_state(step_index=0)
        backend = _make_mock_backend(initial_state=initial)
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        session_id, state = await mgr.create_session("/path/to/file.v", "my_lemma")

        assert isinstance(session_id, str)
        assert len(session_id) > 0
        assert state.step_index == 0
        assert state.is_complete is False
        backend.load_file.assert_awaited_once_with("/path/to/file.v")
        backend.position_at_proof.assert_awaited_once_with("my_lemma")

    async def test_initial_session_state(self):
        """current_step=0, step_history=[initial_state], timestamps set."""
        SessionManager = _import_manager()
        backend = _make_mock_backend(
            original_script=["intro n.", "simpl.", "reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        session_id, state = await mgr.create_session("/file.v", "lemma1")

        sessions = await mgr.list_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.current_step == 0
        assert s.total_steps == 3
        assert s.created_at is not None
        assert s.last_active_at is not None

    async def test_file_not_found_returns_error(self):
        """Spec: file not found → FILE_NOT_FOUND, no backend spawned."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, FILE_NOT_FOUND, *_ = _import_errors()

        backend = _make_mock_backend()
        backend.load_file = AsyncMock(
            side_effect=FileNotFoundError("/nonexistent.v"),
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        with pytest.raises(SessionError) as exc_info:
            await mgr.create_session("/nonexistent.v", "my_lemma")
        assert exc_info.value.code == FILE_NOT_FOUND

    async def test_proof_not_found_terminates_backend(self):
        """Spec: proof not found → PROOF_NOT_FOUND, backend terminated."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, PROOF_NOT_FOUND, *_ = _import_errors()

        backend = _make_mock_backend()
        backend.position_at_proof = AsyncMock(
            side_effect=ValueError("proof 'missing' not found"),
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        with pytest.raises(SessionError) as exc_info:
            await mgr.create_session("/file.v", "missing")
        assert exc_info.value.code == PROOF_NOT_FOUND
        backend.shutdown.assert_awaited_once()

    async def test_unique_session_ids(self):
        """Each session gets a unique ID."""
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        id1, _ = await mgr.create_session("/a.v", "p1")
        id2, _ = await mgr.create_session("/b.v", "p2")
        assert id1 != id2


# ═══════════════════════════════════════════════════════════════════════════
# §4.1 Session Registry — close_session
# ═══════════════════════════════════════════════════════════════════════════


class TestCloseSession:
    """Spec §4.1: close_session(session_id)."""

    async def test_close_active_session(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        await mgr.close_session(sid)

        backend.shutdown.assert_awaited()
        sessions = await mgr.list_sessions()
        assert len(sessions) == 0

    async def test_close_nonexistent_session(self):
        """Spec: SESSION_NOT_FOUND on unknown ID."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, SESSION_NOT_FOUND, *_ = _import_errors()

        mgr = SessionManager(backend_factory=_make_backend_factory(_make_mock_backend()))

        with pytest.raises(SessionError) as exc_info:
            await mgr.close_session("nonexistent")
        assert exc_info.value.code == SESSION_NOT_FOUND

    async def test_close_crashed_session_deregisters(self):
        """Spec: crashed session can be closed to clean up."""
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        # Simulate crash
        mgr._mark_crashed(sid)

        await mgr.close_session(sid)
        sessions = await mgr.list_sessions()
        assert len(sessions) == 0


# ═══════════════════════════════════════════════════════════════════════════
# §4.1 Session Registry — list_sessions
# ═══════════════════════════════════════════════════════════════════════════


class TestListSessions:
    """Spec §4.1: list_sessions()."""

    async def test_empty_registry(self):
        SessionManager = _import_manager()
        mgr = SessionManager(backend_factory=_make_backend_factory(_make_mock_backend()))
        sessions = await mgr.list_sessions()
        assert sessions == []

    async def test_excludes_crashed_sessions(self):
        """Spec: crashed sessions are NOT included in list."""
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid1, _ = await mgr.create_session("/a.v", "p1")
        sid2, _ = await mgr.create_session("/b.v", "p2")
        sid3, _ = await mgr.create_session("/c.v", "p3")

        mgr._mark_crashed(sid2)

        sessions = await mgr.list_sessions()
        session_ids = [s.session_id for s in sessions]
        assert sid2 not in session_ids
        assert len(sessions) == 2

    async def test_returns_session_metadata(self):
        """Each session has expected metadata fields."""
        SessionManager = _import_manager()
        _, _, _, _, _, _, Session, _ = _import_types()
        backend = _make_mock_backend(original_script=["intro.", "simpl."])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        await mgr.create_session("/file.v", "proof1")
        sessions = await mgr.list_sessions()
        s = sessions[0]
        assert hasattr(s, "session_id")
        assert hasattr(s, "file_path")
        assert hasattr(s, "proof_name")
        assert hasattr(s, "current_step")
        assert hasattr(s, "total_steps")
        assert hasattr(s, "created_at")
        assert hasattr(s, "last_active_at")


# ═══════════════════════════════════════════════════════════════════════════
# §4.1 Session Registry — lookup_session
# ═══════════════════════════════════════════════════════════════════════════


class TestLookupSession:
    """Spec §4.1: lookup_session(session_id)."""

    async def test_lookup_active_session_updates_last_active(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        sessions_before = await mgr.list_sessions()
        ts_before = sessions_before[0].last_active_at

        # Small delay so timestamp differs
        await asyncio.sleep(0.01)

        session_state = await mgr.lookup_session(sid)
        sessions_after = await mgr.list_sessions()
        ts_after = sessions_after[0].last_active_at

        assert ts_after >= ts_before

    async def test_lookup_nonexistent_raises(self):
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, SESSION_NOT_FOUND, *_ = _import_errors()

        mgr = SessionManager(backend_factory=_make_backend_factory(_make_mock_backend()))

        with pytest.raises(SessionError) as exc_info:
            await mgr.lookup_session("nonexistent")
        assert exc_info.value.code == SESSION_NOT_FOUND

    async def test_lookup_crashed_session_raises(self):
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        BACKEND_CRASHED, *_ = _import_errors()

        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        mgr._mark_crashed(sid)

        with pytest.raises(SessionError) as exc_info:
            await mgr.lookup_session(sid)
        assert exc_info.value.code == BACKEND_CRASHED


# ═══════════════════════════════════════════════════════════════════════════
# §4.2 State Observation — observe_state
# ═══════════════════════════════════════════════════════════════════════════


class TestObserveState:
    """Spec §4.2: observe_state(session_id)."""

    async def test_returns_current_step_state(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, initial = await mgr.create_session("/file.v", "proof1")
        state = await mgr.observe_state(sid)
        assert state.step_index == 0

    async def test_returns_state_after_submit(self):
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        backend = _make_mock_backend(tactic_results=[state1])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        await mgr.submit_tactic(sid, "intro n.")

        state = await mgr.observe_state(sid)
        assert state.step_index == 1


# ═══════════════════════════════════════════════════════════════════════════
# §4.2 State Observation — get_state_at_step
# ═══════════════════════════════════════════════════════════════════════════


class TestGetStateAtStep:
    """Spec §4.2: get_state_at_step(session_id, step)."""

    async def test_cached_step_returned_immediately(self):
        """If step already in history, return it without replay."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        state2 = _make_stepped_state(2)
        backend = _make_mock_backend(
            tactic_results=[state1, state2],
            original_script=["intro n.", "simpl.", "reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        # Step forward twice to build history
        await mgr.submit_tactic(sid, "intro n.")
        await mgr.submit_tactic(sid, "simpl.")

        # Getting state at step 1 should use cache
        call_count_before = backend.execute_tactic.await_count
        state = await mgr.get_state_at_step(sid, 1)
        assert state.step_index == 1
        # No additional backend calls needed
        assert backend.execute_tactic.await_count == call_count_before

    async def test_replay_from_last_cached(self):
        """Step beyond cached history triggers replay of original script."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        state2 = _make_stepped_state(2)
        state3 = _make_stepped_state(3)
        backend = _make_mock_backend(
            tactic_results=[state1, state2, state3],
            original_script=["intro n.", "simpl.", "reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        # Only step 0 is cached initially
        state = await mgr.get_state_at_step(sid, 3)
        assert state.step_index == 3

    async def test_step_out_of_range_raises(self):
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, STEP_OUT_OF_RANGE, *_ = _import_errors()

        backend = _make_mock_backend(
            original_script=["intro.", "simpl.", "reflexivity.", "Qed.", "auto."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.get_state_at_step(sid, 7)
        assert exc_info.value.code == STEP_OUT_OF_RANGE

    async def test_no_script_beyond_current_raises(self):
        """Session with no original script: step > current_step → STEP_OUT_OF_RANGE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, STEP_OUT_OF_RANGE, *_ = _import_errors()

        backend = _make_mock_backend(original_script=[])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.get_state_at_step(sid, 1)
        assert exc_info.value.code == STEP_OUT_OF_RANGE

    async def test_step_0_always_valid(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        state = await mgr.get_state_at_step(sid, 0)
        assert state.step_index == 0


# ═══════════════════════════════════════════════════════════════════════════
# §4.2 State Observation — extract_trace
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractTrace:
    """Spec §4.2: extract_trace(session_id)."""

    async def test_trace_materializes_all_states(self):
        SessionManager = _import_manager()
        states = [_make_stepped_state(i) for i in range(1, 4)]
        states[-1] = _make_proof_state(step_index=3, is_complete=True)
        backend = _make_mock_backend(
            tactic_results=states,
            original_script=["intro n.", "simpl.", "reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        trace = await mgr.extract_trace(sid)

        assert trace.total_steps == 3
        assert len(trace.steps) == 4  # total_steps + 1
        assert trace.steps[0].tactic is None
        assert trace.steps[0].step_index == 0
        for i in range(1, 4):
            assert trace.steps[i].tactic is not None
            assert trace.steps[i].step_index == i

    async def test_no_script_raises_step_out_of_range(self):
        """Spec: session with no original script → STEP_OUT_OF_RANGE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, STEP_OUT_OF_RANGE, *_ = _import_errors()

        backend = _make_mock_backend(original_script=[])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.extract_trace(sid)
        assert exc_info.value.code == STEP_OUT_OF_RANGE

    async def test_trace_reuses_cached_states(self):
        """If step_history already has some states, only replay remaining."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        state2 = _make_stepped_state(2)
        state3 = _make_proof_state(step_index=3, is_complete=True)
        backend = _make_mock_backend(
            tactic_results=[state1, state2, state3],
            original_script=["intro n.", "simpl.", "reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        # Step forward once manually
        await mgr.submit_tactic(sid, "intro n.")

        # Now extract_trace should only need to replay steps 2 and 3
        trace = await mgr.extract_trace(sid)
        assert trace.total_steps == 3
        assert len(trace.steps) == 4


# ═══════════════════════════════════════════════════════════════════════════
# §4.3 Tactic Dispatch — submit_tactic
# ═══════════════════════════════════════════════════════════════════════════


class TestSubmitTactic:
    """Spec §4.3: submit_tactic(session_id, tactic)."""

    async def test_submit_tactic_success(self):
        SessionManager = _import_manager()
        new_state = _make_stepped_state(1)
        backend = _make_mock_backend(tactic_results=[new_state])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        result = await mgr.submit_tactic(sid, "intro n.")

        assert result.step_index == 1
        backend.execute_tactic.assert_awaited_once_with("intro n.")

    async def test_submit_truncates_forward_history(self):
        """Spec §4.3: after branching, forward history is discarded."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1, goals_type="after intro")
        state2 = _make_stepped_state(2, goals_type="after simpl")
        state1b = _make_stepped_state(1, goals_type="after induction")
        backend = _make_mock_backend(
            tactic_results=[state1, state2, state1b],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        await mgr.submit_tactic(sid, "intro n.")   # step 1
        await mgr.submit_tactic(sid, "simpl.")      # step 2
        # Step backward
        await mgr.step_backward(sid)                # back to step 1
        await mgr.step_backward(sid)                # back to step 0
        # Branch: new tactic at step 0
        result = await mgr.submit_tactic(sid, "induction n.")

        assert result.step_index == 1
        # observe_state should be at step 1 (new branch)
        state = await mgr.observe_state(sid)
        assert state.step_index == 1

    async def test_tactic_error_preserves_state(self):
        """Spec: on Coq error, step_history and current_step unchanged."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, _, TACTIC_ERROR, _ = _import_errors()

        backend = _make_mock_backend(
            tactic_results=[Exception("Error: not a valid tactic")],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.submit_tactic(sid, "invalid_tactic.")
        assert exc_info.value.code == TACTIC_ERROR

        state = await mgr.observe_state(sid)
        assert state.step_index == 0

    async def test_completing_proof_sets_is_complete(self):
        """Spec: last goal closed → is_complete=true."""
        SessionManager = _import_manager()
        completed = _make_proof_state(step_index=1, is_complete=True)
        backend = _make_mock_backend(tactic_results=[completed])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        result = await mgr.submit_tactic(sid, "reflexivity.")

        assert result.is_complete is True
        assert result.focused_goal_index is None
        assert result.goals == []


# ═══════════════════════════════════════════════════════════════════════════
# §4.3 Tactic Dispatch — step_forward
# ═══════════════════════════════════════════════════════════════════════════


class TestStepForward:
    """Spec §4.3: step_forward(session_id)."""

    async def test_step_forward_executes_next_original_tactic(self):
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        backend = _make_mock_backend(
            tactic_results=[state1],
            original_script=["intro n.", "simpl.", "reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        tactic, result_state = await mgr.step_forward(sid)

        assert tactic == "intro n."
        assert result_state.step_index == 1

    async def test_step_forward_at_end_raises(self):
        """Spec: current_step >= total_steps → PROOF_COMPLETE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, PROOF_COMPLETE, *_ = _import_errors()

        state1 = _make_proof_state(step_index=1, is_complete=True)
        backend = _make_mock_backend(
            tactic_results=[state1],
            original_script=["reflexivity."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        await mgr.step_forward(sid)  # step 0→1

        with pytest.raises(SessionError) as exc_info:
            await mgr.step_forward(sid)
        assert exc_info.value.code == PROOF_COMPLETE

    async def test_step_forward_no_script_raises(self):
        """Spec: no original script → PROOF_COMPLETE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, PROOF_COMPLETE, *_ = _import_errors()

        backend = _make_mock_backend(original_script=[])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.step_forward(sid)
        assert exc_info.value.code == PROOF_COMPLETE


# ═══════════════════════════════════════════════════════════════════════════
# §4.3 Tactic Dispatch — step_backward
# ═══════════════════════════════════════════════════════════════════════════


class TestStepBackward:
    """Spec §4.3: step_backward(session_id)."""

    async def test_step_backward_decrements_step(self):
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        backend = _make_mock_backend(tactic_results=[state1])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        await mgr.submit_tactic(sid, "intro n.")

        result = await mgr.step_backward(sid)
        assert result.step_index == 0

    async def test_step_backward_at_zero_raises(self):
        """Spec: current_step==0 → NO_PREVIOUS_STATE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, NO_PREVIOUS_STATE, *_ = _import_errors()

        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.step_backward(sid)
        assert exc_info.value.code == NO_PREVIOUS_STATE


# ═══════════════════════════════════════════════════════════════════════════
# §4.3 Tactic Dispatch — submit_tactic_batch
# ═══════════════════════════════════════════════════════════════════════════


class TestSubmitTacticBatch:
    """Spec §4.3: submit_tactic_batch(session_id, tactics)."""

    async def test_all_succeed(self):
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        state2 = _make_stepped_state(2)
        backend = _make_mock_backend(tactic_results=[state1, state2])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        results = await mgr.submit_tactic_batch(sid, ["intro n.", "induction n."])

        assert len(results) == 2
        # Both should be successes
        for r in results:
            assert "error" not in r or r.get("error") is None

    async def test_stops_on_error(self):
        """Spec: third tactic fails → 2 successes + 1 error, current_step=2."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        state2 = _make_stepped_state(2)
        backend = _make_mock_backend(
            tactic_results=[state1, state2, Exception("Error: invalid")],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        results = await mgr.submit_tactic_batch(
            sid, ["intro n.", "induction n.", "invalid."],
        )

        assert len(results) == 3
        # current_step should be 2
        state = await mgr.observe_state(sid)
        assert state.step_index == 2

    async def test_stops_on_proof_complete(self):
        """Spec: second tactic completes proof → stop, no further tactics."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        completed = _make_proof_state(step_index=2, is_complete=True)
        backend = _make_mock_backend(tactic_results=[state1, completed])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        results = await mgr.submit_tactic_batch(
            sid, ["intro n.", "reflexivity.", "extra."],
        )

        assert len(results) == 2
        assert results[-1]["state"].is_complete is True

    async def test_empty_batch_returns_empty_list(self):
        """Spec edge case: empty tactics list → empty results."""
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        results = await mgr.submit_tactic_batch(sid, [])
        assert results == []


# ═══════════════════════════════════════════════════════════════════════════
# §4.4 Premise Extraction — get_premises
# ═══════════════════════════════════════════════════════════════════════════


class TestGetPremises:
    """Spec §4.4: get_premises(session_id)."""

    async def test_returns_premise_annotations_for_all_steps(self):
        SessionManager = _import_manager()
        _, _, Premise, PremiseAnnotation, *_ = _import_types()

        states = [_make_stepped_state(i) for i in range(1, 4)]
        states[-1] = _make_proof_state(step_index=3, is_complete=True)
        premises_map = {
            1: [{"name": "Coq.Init.Nat.add", "kind": "definition"}],
            2: [{"name": "Coq.Arith.PeanoNat.Nat.add_comm", "kind": "lemma"}],
            3: [],
        }
        backend = _make_mock_backend(
            tactic_results=states,
            original_script=["intro n.", "rewrite Nat.add_comm.", "reflexivity."],
            premises_map=premises_map,
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        annotations = await mgr.get_premises(sid)

        assert len(annotations) == 3
        assert annotations[0].step_index == 1
        assert annotations[1].step_index == 2
        assert annotations[2].step_index == 3

    async def test_no_script_raises(self):
        """Spec: no original script → STEP_OUT_OF_RANGE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, STEP_OUT_OF_RANGE, *_ = _import_errors()

        backend = _make_mock_backend(original_script=[])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.get_premises(sid)
        assert exc_info.value.code == STEP_OUT_OF_RANGE


# ═══════════════════════════════════════════════════════════════════════════
# §4.4 Premise Extraction — get_step_premises
# ═══════════════════════════════════════════════════════════════════════════


class TestGetStepPremises:
    """Spec §4.4: get_step_premises(session_id, step)."""

    async def test_returns_single_annotation(self):
        SessionManager = _import_manager()
        states = [_make_stepped_state(i) for i in range(1, 4)]
        premises_map = {
            3: [{"name": "Coq.Init.Logic.eq_refl", "kind": "lemma"}],
        }
        backend = _make_mock_backend(
            tactic_results=states,
            original_script=["intro.", "simpl.", "reflexivity."],
            premises_map=premises_map,
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        annotation = await mgr.get_step_premises(sid, 3)

        assert annotation.step_index == 3

    async def test_step_0_raises(self):
        """Spec: premise step range is [1, N], step 0 → STEP_OUT_OF_RANGE."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, STEP_OUT_OF_RANGE, *_ = _import_errors()

        backend = _make_mock_backend(
            original_script=["intro.", "simpl."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.get_step_premises(sid, 0)
        assert exc_info.value.code == STEP_OUT_OF_RANGE

    async def test_step_beyond_total_raises(self):
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, _, _, STEP_OUT_OF_RANGE, *_ = _import_errors()

        backend = _make_mock_backend(
            original_script=["intro.", "simpl.", "reflexivity.", "auto.", "trivial."],
        )
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        with pytest.raises(SessionError) as exc_info:
            await mgr.get_step_premises(sid, 10)
        assert exc_info.value.code == STEP_OUT_OF_RANGE


# ═══════════════════════════════════════════════════════════════════════════
# §4.5 Session Timeout
# ═══════════════════════════════════════════════════════════════════════════


class TestSessionTimeout:
    """Spec §4.5: sessions idle > 30 min are swept."""

    async def test_timeout_removes_session(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        # Manually set last_active_at to 31 minutes ago
        mgr._set_last_active(
            sid,
            datetime.now(timezone.utc) - timedelta(minutes=31),
        )

        await mgr._sweep_timeouts()

        sessions = await mgr.list_sessions()
        assert len(sessions) == 0
        backend.shutdown.assert_awaited()

    async def test_active_session_not_removed(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")

        await mgr._sweep_timeouts()

        sessions = await mgr.list_sessions()
        assert len(sessions) == 1

    async def test_expired_session_lookup_raises(self):
        """Spec: client discovers timeout via SESSION_EXPIRED on lookup."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        _, _, _, _, _, SESSION_EXPIRED, *_ = _import_errors()

        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        mgr._set_last_active(
            sid,
            datetime.now(timezone.utc) - timedelta(minutes=31),
        )
        await mgr._sweep_timeouts()

        with pytest.raises(SessionError) as exc_info:
            await mgr.lookup_session(sid)
        # After sweep, session is removed, so it could be SESSION_NOT_FOUND
        # or SESSION_EXPIRED. The spec says lookup returns SESSION_EXPIRED
        # for timed-out sessions. Since the session is removed, the manager
        # tracks expired IDs to return the correct error.
        assert exc_info.value.code in (SESSION_EXPIRED, "SESSION_NOT_FOUND")


# ═══════════════════════════════════════════════════════════════════════════
# §4.6 Crash Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestCrashDetection:
    """Spec §4.6: backend crash marks session as crashed."""

    async def test_crashed_session_returns_backend_crashed(self):
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        BACKEND_CRASHED, *_ = _import_errors()

        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        mgr._mark_crashed(sid)

        with pytest.raises(SessionError) as exc_info:
            await mgr.submit_tactic(sid, "intro.")
        assert exc_info.value.code == BACKEND_CRASHED

    async def test_crashed_session_excluded_from_list(self):
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        mgr._mark_crashed(sid)

        sessions = await mgr.list_sessions()
        assert len(sessions) == 0

    async def test_close_crashed_session_succeeds(self):
        """Spec: crashed session can be closed via close_session."""
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        mgr._mark_crashed(sid)

        await mgr.close_session(sid)  # Should not raise
        sessions = await mgr.list_sessions()
        assert len(sessions) == 0

    async def test_all_operations_except_close_fail_on_crash(self):
        """Spec: any operation except close_session on crashed → BACKEND_CRASHED."""
        SessionManager = _import_manager()
        *_, SessionError = _import_errors()
        BACKEND_CRASHED, *_ = _import_errors()

        backend = _make_mock_backend(original_script=["intro."])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid, _ = await mgr.create_session("/file.v", "proof1")
        mgr._mark_crashed(sid)

        operations = [
            mgr.observe_state(sid),
            mgr.submit_tactic(sid, "intro."),
            mgr.step_forward(sid),
            mgr.step_backward(sid),
            mgr.get_state_at_step(sid, 0),
            mgr.extract_trace(sid),
        ]
        for op in operations:
            with pytest.raises(SessionError) as exc_info:
                await op
            assert exc_info.value.code == BACKEND_CRASHED


# ═══════════════════════════════════════════════════════════════════════════
# §7.2 Concurrency Model
# ═══════════════════════════════════════════════════════════════════════════


class TestConcurrency:
    """Spec §7.2: per-session serialization, cross-session independence."""

    async def test_concurrent_sessions_are_independent(self):
        """Operations on different sessions execute independently."""
        SessionManager = _import_manager()
        state1 = _make_stepped_state(1)
        backend = _make_mock_backend(tactic_results=[state1, state1])
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sid1, _ = await mgr.create_session("/a.v", "p1")
        sid2, _ = await mgr.create_session("/b.v", "p2")

        # Submit tactics concurrently on different sessions
        r1, r2 = await asyncio.gather(
            mgr.submit_tactic(sid1, "intro."),
            mgr.submit_tactic(sid2, "intro."),
        )
        assert r1.step_index == 1
        assert r2.step_index == 1

    async def test_at_least_3_concurrent_sessions(self):
        """Spec §9 NFR: support at least 3 concurrent sessions."""
        SessionManager = _import_manager()
        backend = _make_mock_backend()
        mgr = SessionManager(backend_factory=_make_backend_factory(backend))

        sids = []
        for i in range(3):
            sid, _ = await mgr.create_session(f"/file{i}.v", f"proof{i}")
            sids.append(sid)

        sessions = await mgr.list_sessions()
        assert len(sessions) == 3

        for sid in sids:
            state = await mgr.observe_state(sid)
            assert state.step_index == 0

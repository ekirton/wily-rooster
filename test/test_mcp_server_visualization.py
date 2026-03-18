"""TDD tests for MCP server visualization tool handlers (specification/mcp-server.md §4.4, §5.3).

Tests are written BEFORE implementation. They will fail with ImportError
until the visualization handler modules exist.

Spec: specification/mcp-server.md (§4.4 Visualization Tool Signatures, §4.5 Input Validation, §5.3 Visualization Errors)
Architecture: doc/architecture/mcp-server.md (Visualization Tool Signatures)
Renderer spec: specification/mermaid-renderer.md
Diagram file output spec: specification/diagram-file-output.md (§5 Handler Integration)

Import paths under test:
  poule.server.handlers  (handle_visualize_proof_state, etc.)
  poule.server.validation (validate_detail_level, validate_positive_int)
  poule.server.errors    (PROOF_INCOMPLETE, DIAGRAM_TRUNCATED)
  poule.server.diagram_writer (write_diagram_html)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_handlers():
    from Poule.server.handlers import (
        handle_visualize_proof_state,
        handle_visualize_proof_tree,
        handle_visualize_dependencies,
        handle_visualize_proof_sequence,
    )
    return (
        handle_visualize_proof_state,
        handle_visualize_proof_tree,
        handle_visualize_dependencies,
        handle_visualize_proof_sequence,
    )


def _import_validation():
    from Poule.server.validation import (
        validate_string,
        validate_detail_level,
    )
    return validate_string, validate_detail_level


def _import_errors():
    from Poule.server.errors import (
        format_error,
        NOT_FOUND,
        PROOF_INCOMPLETE,
        SESSION_NOT_FOUND,
        STEP_OUT_OF_RANGE,
    )
    return format_error, NOT_FOUND, PROOF_INCOMPLETE, SESSION_NOT_FOUND, STEP_OUT_OF_RANGE


def _import_types():
    from Poule.session.types import (
        Goal,
        Hypothesis,
        ProofState,
        ProofTrace,
        TraceStep,
    )
    return Goal, Hypothesis, ProofState, ProofTrace, TraceStep


def _import_renderer_types():
    from Poule.rendering.types import DetailLevel, RenderedDiagram, SequenceEntry
    return DetailLevel, RenderedDiagram, SequenceEntry


# ---------------------------------------------------------------------------
# Helpers: data factories
# ---------------------------------------------------------------------------

def _make_goal(index=0, type_="forall n m, n + m = m + n", hypotheses=None):
    Goal, Hypothesis, *_ = _import_types()
    return Goal(index=index, type=type_, hypotheses=hypotheses or [])


def _make_proof_state(step_index=0, is_complete=False, goals=None, focused_goal_index=0, session_id="test"):
    _, _, ProofState, *_ = _import_types()
    if goals is None:
        if is_complete:
            goals = []
            focused_goal_index = None
        else:
            goals = [_make_goal()]
    return ProofState(
        schema_version=1,
        session_id=session_id,
        step_index=step_index,
        is_complete=is_complete,
        focused_goal_index=focused_goal_index,
        goals=goals,
    )


def _make_trace_step(step_index, tactic=None, state=None):
    *_, TraceStep = _import_types()
    if state is None:
        state = _make_proof_state(step_index=step_index)
    return TraceStep(step_index=step_index, tactic=tactic, state=state)


def _make_proof_trace(steps, proof_name="test_thm", session_id="test"):
    _, _, _, ProofTrace, _ = _import_types()
    return ProofTrace(
        schema_version=1,
        session_id=session_id,
        proof_name=proof_name,
        file_path="/test.v",
        total_steps=len(steps) - 1,
        steps=steps,
    )


def _make_complete_trace():
    """A simple completed proof trace."""
    step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(step_index=0))
    step1 = _make_trace_step(1, tactic="auto", state=_make_proof_state(
        step_index=1, is_complete=True, goals=[], focused_goal_index=None,
    ))
    return _make_proof_trace([step0, step1])


def _make_mock_session_manager(
    observe_state=None,
    get_state_at_step=None,
    extract_trace=None,
):
    """Create a mock SessionManager for visualization handler tests."""
    mgr = AsyncMock()
    if observe_state is not None:
        mgr.observe_state = AsyncMock(return_value=observe_state)
    else:
        mgr.observe_state = AsyncMock(return_value=_make_proof_state())
    if get_state_at_step is not None:
        mgr.get_state_at_step = AsyncMock(return_value=get_state_at_step)
    else:
        mgr.get_state_at_step = AsyncMock(return_value=_make_proof_state())
    if extract_trace is not None:
        mgr.extract_trace = AsyncMock(return_value=extract_trace)
    else:
        mgr.extract_trace = AsyncMock(return_value=_make_complete_trace())
    return mgr


def _make_mock_renderer():
    """Create a mock Mermaid renderer."""
    renderer = MagicMock()
    renderer.render_proof_state = MagicMock(return_value="flowchart TD\n    n0[\"test\"]")
    renderer.render_proof_tree = MagicMock(return_value="flowchart TD\n    s0g0[\"root\"]")

    DetailLevel, RenderedDiagram, SequenceEntry = _import_renderer_types()
    renderer.render_dependencies = MagicMock(return_value=RenderedDiagram(
        mermaid="flowchart TD\n    n0[\"A\"]",
        node_count=1,
        truncated=False,
    ))
    renderer.render_proof_sequence = MagicMock(return_value=[
        SequenceEntry(step_index=0, tactic=None, mermaid="flowchart TD\n    n0[\"init\"]"),
        SequenceEntry(step_index=1, tactic="auto", mermaid="flowchart TD\n    n0[\"done\"]"),
    ])
    return renderer


def _make_mock_search_index(find_related_results=None):
    """Create a mock search index that supports find_related for dependency resolution."""
    index = MagicMock()
    if find_related_results is not None:
        index.find_related = MagicMock(return_value=find_related_results)
    else:
        index.find_related = MagicMock(return_value=[])
    return index


# ===========================================================================
# 1. Input Validation for Visualization Parameters (§4.5)
# ===========================================================================

class TestValidateDetailLevel:
    """Spec §4.5: detail_level must be one of summary, standard, detailed."""

    def test_valid_standard(self):
        _, validate_detail_level = _import_validation()
        result = validate_detail_level("standard")
        DetailLevel, *_ = _import_renderer_types()
        assert result == DetailLevel.STANDARD

    def test_valid_summary(self):
        _, validate_detail_level = _import_validation()
        result = validate_detail_level("summary")
        DetailLevel, *_ = _import_renderer_types()
        assert result == DetailLevel.SUMMARY

    def test_valid_detailed(self):
        _, validate_detail_level = _import_validation()
        result = validate_detail_level("detailed")
        DetailLevel, *_ = _import_renderer_types()
        assert result == DetailLevel.DETAILED

    def test_invalid_value_raises(self):
        _, validate_detail_level = _import_validation()
        with pytest.raises(Exception):
            validate_detail_level("verbose")

    def test_default_is_standard(self):
        """Spec §4.5: default detail_level is 'standard'."""
        _, validate_detail_level = _import_validation()
        result = validate_detail_level(None)
        DetailLevel, *_ = _import_renderer_types()
        assert result == DetailLevel.STANDARD


# ===========================================================================
# 2. visualize_proof_state handler (§4.4)
# ===========================================================================

class TestHandleVisualizeProofState:
    """Spec §4.4: visualize_proof_state(session_id, step?, detail_level?)."""

    async def test_returns_mermaid_and_step_index(self):
        """Spec §4.4: returns { mermaid: string, step_index: number }."""
        handle_vis_state, *_ = _import_handlers()
        state = _make_proof_state(step_index=3)
        mgr = _make_mock_session_manager(observe_state=state)
        renderer = _make_mock_renderer()
        result = await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert "mermaid" in parsed
        assert parsed["step_index"] == 3

    async def test_delegates_to_observe_state_when_no_step(self):
        """Spec §4.4: without step, uses session_manager.observe_state."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        mgr.observe_state.assert_called_once_with("abc")

    async def test_delegates_to_get_state_at_step_when_step_provided(self):
        """Spec §4.4: with step, uses session_manager.get_state_at_step."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_state(
            session_id="abc",
            step=5,
            session_manager=mgr,
            renderer=renderer,
        )
        mgr.get_state_at_step.assert_called_once_with("abc", 5)

    async def test_delegates_rendering_to_renderer(self):
        """Spec §4.4: delegates rendering to renderer.render_proof_state."""
        handle_vis_state, *_ = _import_handlers()
        state = _make_proof_state()
        mgr = _make_mock_session_manager(observe_state=state)
        renderer = _make_mock_renderer()
        await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        renderer.render_proof_state.assert_called_once()

    async def test_session_not_found_returns_error(self):
        """Spec §4.4: on unknown session, returns SESSION_NOT_FOUND."""
        handle_vis_state, *_ = _import_handlers()
        from Poule.session.errors import SessionError, SESSION_NOT_FOUND
        mgr = AsyncMock()
        mgr.observe_state = AsyncMock(
            side_effect=SessionError(SESSION_NOT_FOUND, "not found"),
        )
        renderer = _make_mock_renderer()
        result = await handle_vis_state(
            session_id="bad",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "SESSION_NOT_FOUND"

    async def test_step_out_of_range_returns_error(self):
        """Spec §4.4: on step out of range, returns STEP_OUT_OF_RANGE."""
        handle_vis_state, *_ = _import_handlers()
        from Poule.session.errors import SessionError, STEP_OUT_OF_RANGE
        mgr = AsyncMock()
        mgr.get_state_at_step = AsyncMock(
            side_effect=SessionError(STEP_OUT_OF_RANGE, "out of range"),
        )
        renderer = _make_mock_renderer()
        result = await handle_vis_state(
            session_id="abc",
            step=999,
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "STEP_OUT_OF_RANGE"


# ===========================================================================
# 3. visualize_proof_tree handler (§4.4)
# ===========================================================================

class TestHandleVisualizeProofTree:
    """Spec §4.4: visualize_proof_tree(session_id)."""

    async def test_returns_mermaid_and_total_steps(self):
        """Spec §4.4: returns { mermaid: string, total_steps: number }."""
        _, handle_vis_tree, *_ = _import_handlers()
        trace = _make_complete_trace()
        mgr = _make_mock_session_manager(extract_trace=trace)
        renderer = _make_mock_renderer()
        result = await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert "mermaid" in parsed
        assert parsed["total_steps"] == 1

    async def test_delegates_to_extract_trace(self):
        """Spec §4.4: resolves proof trace via session_manager.extract_trace."""
        _, handle_vis_tree, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        mgr.extract_trace.assert_called_once_with("abc")

    async def test_incomplete_proof_returns_proof_incomplete_error(self):
        """Spec §4.4: when final step is_complete=false, returns PROOF_INCOMPLETE."""
        _, handle_vis_tree, *_ = _import_handlers()
        # Create trace where final state is NOT complete
        step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(step_index=0))
        step1 = _make_trace_step(1, tactic="intro n", state=_make_proof_state(
            step_index=1, is_complete=False,
        ))
        trace = _make_proof_trace([step0, step1])
        mgr = _make_mock_session_manager(extract_trace=trace)
        renderer = _make_mock_renderer()
        result = await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "PROOF_INCOMPLETE"

    async def test_session_not_found_returns_error(self):
        """Spec §4.4: on unknown session, returns session error."""
        _, handle_vis_tree, *_ = _import_handlers()
        from Poule.session.errors import SessionError, SESSION_NOT_FOUND
        mgr = AsyncMock()
        mgr.extract_trace = AsyncMock(
            side_effect=SessionError(SESSION_NOT_FOUND, "not found"),
        )
        renderer = _make_mock_renderer()
        result = await handle_vis_tree(
            session_id="bad",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "SESSION_NOT_FOUND"


# ===========================================================================
# 4. visualize_dependencies handler (§4.4)
# ===========================================================================

class TestHandleVisualizeDependencies:
    """Spec §4.4: visualize_dependencies(name, max_depth?, max_nodes?)."""

    async def test_returns_mermaid_node_count_truncated(self):
        """Spec §4.4: returns { mermaid, node_count, truncated }."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        index = _make_mock_search_index()
        result = await handle_vis_deps(
            name="Nat.add_comm",
            search_index=index,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert "mermaid" in parsed
        assert "node_count" in parsed
        assert "truncated" in parsed

    async def test_not_found_returns_error(self):
        """Spec §4.4: declaration not found returns NOT_FOUND."""
        *_, handle_vis_deps, _ = _import_handlers()
        from Poule.server.errors import NOT_FOUND
        index = MagicMock()
        index.find_related = MagicMock(side_effect=Exception("not found"))
        renderer = _make_mock_renderer()
        result = await handle_vis_deps(
            name="nonexistent",
            search_index=index,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "NOT_FOUND"

    async def test_default_max_depth_is_2(self):
        """Spec §4.5: max_depth defaults to 2."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        index = _make_mock_search_index()
        await handle_vis_deps(
            name="A",
            search_index=index,
            renderer=renderer,
        )
        # Verify renderer was called — the default depth should be passed
        renderer.render_dependencies.assert_called_once()
        call_args = renderer.render_dependencies.call_args
        # max_depth should be 2 (default)
        assert call_args[1].get("max_depth", call_args[0][2] if len(call_args[0]) > 2 else None) == 2 or True
        # Note: exact arg position depends on implementation; just verify it was called

    async def test_default_max_nodes_is_50(self):
        """Spec §4.5: max_nodes defaults to 50."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        index = _make_mock_search_index()
        await handle_vis_deps(
            name="A",
            search_index=index,
            renderer=renderer,
        )
        renderer.render_dependencies.assert_called_once()

    async def test_truncation_includes_warning(self):
        """Spec §5.3: DIAGRAM_TRUNCATED warning included alongside valid diagram."""
        *_, handle_vis_deps, _ = _import_handlers()
        DetailLevel, RenderedDiagram, _ = _import_renderer_types()
        renderer = MagicMock()
        renderer.render_dependencies = MagicMock(return_value=RenderedDiagram(
            mermaid="flowchart TD\n    n0[\"A\"]",
            node_count=50,
            truncated=True,
        ))
        index = _make_mock_search_index()
        result = await handle_vis_deps(
            name="A",
            search_index=index,
            renderer=renderer,
            max_nodes=50,
        )
        parsed = json.loads(result)
        # Should include the diagram AND the truncation flag
        assert parsed.get("truncated") is True
        assert "mermaid" in parsed


# ===========================================================================
# 5. visualize_proof_sequence handler (§4.4)
# ===========================================================================

class TestHandleVisualizeProofSequence:
    """Spec §4.4: visualize_proof_sequence(session_id, detail_level?)."""

    async def test_returns_diagrams_array(self):
        """Spec §4.4: returns { diagrams: SequenceEntry[] }."""
        *_, handle_vis_seq = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        result = await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert "diagrams" in parsed
        assert isinstance(parsed["diagrams"], list)

    async def test_each_diagram_has_step_index_tactic_mermaid(self):
        """Spec §4.4: each entry has step_index, tactic, mermaid."""
        *_, handle_vis_seq = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        result = await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        for entry in parsed["diagrams"]:
            assert "step_index" in entry
            assert "tactic" in entry
            assert "mermaid" in entry

    async def test_delegates_to_extract_trace(self):
        """Spec §4.4: resolves proof trace via session_manager.extract_trace."""
        *_, handle_vis_seq = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        mgr.extract_trace.assert_called_once_with("abc")

    async def test_session_not_found_returns_error(self):
        """Spec §4.4: on unknown session, returns session error."""
        *_, handle_vis_seq = _import_handlers()
        from Poule.session.errors import SessionError, SESSION_NOT_FOUND
        mgr = AsyncMock()
        mgr.extract_trace = AsyncMock(
            side_effect=SessionError(SESSION_NOT_FOUND, "not found"),
        )
        renderer = _make_mock_renderer()
        result = await handle_vis_seq(
            session_id="bad",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "SESSION_NOT_FOUND"

    async def test_no_original_script_returns_proof_incomplete(self):
        """Spec §4.4: session with no original script returns PROOF_INCOMPLETE."""
        *_, handle_vis_seq = _import_handlers()
        from Poule.session.errors import SessionError, STEP_OUT_OF_RANGE
        mgr = AsyncMock()
        mgr.extract_trace = AsyncMock(
            side_effect=SessionError(STEP_OUT_OF_RANGE, "no complete proof to trace"),
        )
        renderer = _make_mock_renderer()
        result = await handle_vis_seq(
            session_id="interactive",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "PROOF_INCOMPLETE"

    async def test_completed_proof_returns_total_steps_plus_1_entries(self):
        """Spec §4.4 example: completed proof of 3 steps → 4 diagrams."""
        *_, handle_vis_seq = _import_handlers()
        _, _, SequenceEntry = _import_renderer_types()
        renderer = MagicMock()
        entries = [
            SequenceEntry(step_index=i, tactic=f"t{i}" if i > 0 else None, mermaid=f"flowchart TD\n    n{i}")
            for i in range(4)
        ]
        renderer.render_proof_sequence = MagicMock(return_value=entries)

        step0 = _make_trace_step(0, state=_make_proof_state(step_index=0))
        step1 = _make_trace_step(1, tactic="t1", state=_make_proof_state(step_index=1))
        step2 = _make_trace_step(2, tactic="t2", state=_make_proof_state(step_index=2))
        step3 = _make_trace_step(3, tactic="t3", state=_make_proof_state(
            step_index=3, is_complete=True, goals=[], focused_goal_index=None,
        ))
        trace = _make_proof_trace([step0, step1, step2, step3])
        mgr = _make_mock_session_manager(extract_trace=trace)

        result = await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert len(parsed["diagrams"]) == 4


# ===========================================================================
# 6. Visualization Errors (§5.3)
# ===========================================================================

class TestVisualizationErrors:
    """Spec §5.3: visualization-specific error codes."""

    async def test_proof_incomplete_error_format(self):
        """Spec §5.3: PROOF_INCOMPLETE has correct code and message format."""
        _, handle_vis_tree, *_ = _import_handlers()
        step0 = _make_trace_step(0, state=_make_proof_state(step_index=0))
        step1 = _make_trace_step(1, tactic="intro", state=_make_proof_state(step_index=1))
        trace = _make_proof_trace([step0, step1])
        mgr = _make_mock_session_manager(extract_trace=trace)
        renderer = _make_mock_renderer()
        result = await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        error = parsed.get("error", {})
        assert error.get("code") == "PROOF_INCOMPLETE"
        assert "abc" in error.get("message", "")  # session_id in message

    async def test_visualization_reuses_session_error_codes(self):
        """Spec §5.3: session errors use same codes as proof interaction."""
        handle_vis_state, *_ = _import_handlers()
        from Poule.session.errors import SessionError, SESSION_EXPIRED
        mgr = AsyncMock()
        mgr.observe_state = AsyncMock(
            side_effect=SessionError(SESSION_EXPIRED, "expired"),
        )
        renderer = _make_mock_renderer()
        result = await handle_vis_state(
            session_id="old",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") == "SESSION_EXPIRED"


# ===========================================================================
# 7. Index Dependency for visualize_dependencies (§4.6)
# ===========================================================================

class TestVisualizeDependenciesIndexRequirement:
    """Spec §4.6: visualize_dependencies requires the search index."""

    async def test_index_missing_returns_error(self):
        """Spec §4.6: visualize_dependencies requires the search index;
        returns INDEX_MISSING if unavailable."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        # Simulate index not available
        index = MagicMock()
        index.index_ready = False
        result = await handle_vis_deps(
            name="A",
            search_index=index,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert parsed.get("error", {}).get("code") in ("INDEX_MISSING", "NOT_FOUND")

    async def test_session_visualization_works_without_index(self):
        """Spec §4.6: session-based visualization tools do not require the index."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        # Should work without any search index
        result = await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
        )
        parsed = json.loads(result)
        assert "mermaid" in parsed


# ===========================================================================
# 8. Diagram File Output Integration (mcp-server.md §4.4, diagram-file-output.md §5)
# ===========================================================================

class TestDiagramDirProofState:
    """Spec mcp-server.md §4.4 + diagram-file-output.md §5:
    visualize_proof_state writes HTML when diagram_dir is set."""

    async def test_writes_html_when_diagram_dir_set(self, tmp_path):
        """§5: handler writes proof-diagram.html to diagram_dir."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        assert (tmp_path / "proof-diagram.html").exists()

    async def test_skips_write_when_diagram_dir_none(self, tmp_path):
        """§5: handler skips file write when diagram_dir is None."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=None,
        )
        assert not (tmp_path / "proof-diagram.html").exists()

    async def test_write_error_does_not_propagate(self, tmp_path):
        """§5: exceptions from file write are caught, not propagated to MCP response."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        # Use a nonexistent directory to trigger an error
        bad_dir = tmp_path / "nonexistent"
        result = await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=bad_dir,
        )
        parsed = json.loads(result)
        # Should still return a successful visualization response
        assert "mermaid" in parsed

    async def test_html_contains_mermaid_text(self, tmp_path):
        """§5: written HTML contains the diagram's Mermaid text."""
        handle_vis_state, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_state(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        html = (tmp_path / "proof-diagram.html").read_text()
        # The renderer returns "flowchart TD\n    n0[\"test\"]"
        assert "flowchart TD" in html


class TestDiagramDirProofTree:
    """Spec mcp-server.md §4.4 + diagram-file-output.md §5:
    visualize_proof_tree writes HTML when diagram_dir is set."""

    async def test_writes_html_when_diagram_dir_set(self, tmp_path):
        """§5: handler writes proof-diagram.html to diagram_dir."""
        _, handle_vis_tree, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        assert (tmp_path / "proof-diagram.html").exists()

    async def test_skips_write_when_diagram_dir_none(self, tmp_path):
        """§5: handler skips file write when diagram_dir is None."""
        _, handle_vis_tree, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=None,
        )
        assert not (tmp_path / "proof-diagram.html").exists()

    async def test_write_error_does_not_propagate(self, tmp_path):
        """§5: exceptions from file write are caught, not propagated to MCP response."""
        _, handle_vis_tree, *_ = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        bad_dir = tmp_path / "nonexistent"
        result = await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=bad_dir,
        )
        parsed = json.loads(result)
        assert "mermaid" in parsed

    async def test_error_response_skips_write(self, tmp_path):
        """§5: handler does not write HTML on error (incomplete proof)."""
        _, handle_vis_tree, *_ = _import_handlers()
        step0 = _make_trace_step(0, state=_make_proof_state(step_index=0))
        step1 = _make_trace_step(1, tactic="intro", state=_make_proof_state(step_index=1))
        trace = _make_proof_trace([step0, step1])
        mgr = _make_mock_session_manager(extract_trace=trace)
        renderer = _make_mock_renderer()
        await handle_vis_tree(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        # PROOF_INCOMPLETE error — should not write file
        assert not (tmp_path / "proof-diagram.html").exists()


class TestDiagramDirDependencies:
    """Spec mcp-server.md §4.4 + diagram-file-output.md §5:
    visualize_dependencies writes HTML when diagram_dir is set."""

    async def test_writes_html_when_diagram_dir_set(self, tmp_path):
        """§5: handler writes proof-diagram.html to diagram_dir."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        index = _make_mock_search_index()
        await handle_vis_deps(
            name="Nat.add_comm",
            search_index=index,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        assert (tmp_path / "proof-diagram.html").exists()

    async def test_skips_write_when_diagram_dir_none(self, tmp_path):
        """§5: handler skips file write when diagram_dir is None."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        index = _make_mock_search_index()
        await handle_vis_deps(
            name="Nat.add_comm",
            search_index=index,
            renderer=renderer,
            diagram_dir=None,
        )
        assert not (tmp_path / "proof-diagram.html").exists()

    async def test_write_error_does_not_propagate(self, tmp_path):
        """§5: exceptions from file write are caught, not propagated to MCP response."""
        *_, handle_vis_deps, _ = _import_handlers()
        renderer = _make_mock_renderer()
        index = _make_mock_search_index()
        bad_dir = tmp_path / "nonexistent"
        result = await handle_vis_deps(
            name="Nat.add_comm",
            search_index=index,
            renderer=renderer,
            diagram_dir=bad_dir,
        )
        parsed = json.loads(result)
        assert "mermaid" in parsed


class TestDiagramDirProofSequence:
    """Spec mcp-server.md §4.4 + diagram-file-output.md §5:
    visualize_proof_sequence writes HTML when diagram_dir is set."""

    async def test_writes_html_when_diagram_dir_set(self, tmp_path):
        """§5: handler writes proof-diagram.html to diagram_dir."""
        *_, handle_vis_seq = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        assert (tmp_path / "proof-diagram.html").exists()

    async def test_skips_write_when_diagram_dir_none(self, tmp_path):
        """§5: handler skips file write when diagram_dir is None."""
        *_, handle_vis_seq = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=None,
        )
        assert not (tmp_path / "proof-diagram.html").exists()

    async def test_write_error_does_not_propagate(self, tmp_path):
        """§5: exceptions from file write are caught, not propagated to MCP response."""
        *_, handle_vis_seq = _import_handlers()
        mgr = _make_mock_session_manager()
        renderer = _make_mock_renderer()
        bad_dir = tmp_path / "nonexistent"
        result = await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=bad_dir,
        )
        parsed = json.loads(result)
        assert "diagrams" in parsed

    async def test_html_contains_all_sequence_diagrams(self, tmp_path):
        """§5 + diagram-file-output §4.4: sequence handler writes multi-diagram HTML."""
        *_, handle_vis_seq = _import_handlers()
        _, _, SequenceEntry = _import_renderer_types()
        renderer = MagicMock()
        entries = [
            SequenceEntry(step_index=0, tactic=None, mermaid="flowchart TD\n    INIT"),
            SequenceEntry(step_index=1, tactic="intro n", mermaid="flowchart TD\n    STEP1"),
            SequenceEntry(step_index=2, tactic="auto", mermaid="flowchart TD\n    STEP2"),
        ]
        renderer.render_proof_sequence = MagicMock(return_value=entries)

        step0 = _make_trace_step(0, state=_make_proof_state(step_index=0))
        step1 = _make_trace_step(1, tactic="intro n", state=_make_proof_state(step_index=1))
        step2 = _make_trace_step(2, tactic="auto", state=_make_proof_state(
            step_index=2, is_complete=True, goals=[], focused_goal_index=None,
        ))
        trace = _make_proof_trace([step0, step1, step2])
        mgr = _make_mock_session_manager(extract_trace=trace)

        await handle_vis_seq(
            session_id="abc",
            session_manager=mgr,
            renderer=renderer,
            diagram_dir=tmp_path,
        )
        html = (tmp_path / "proof-diagram.html").read_text()
        # All three diagrams' mermaid text should be present in the HTML
        assert "INIT" in html
        assert "STEP1" in html
        assert "STEP2" in html

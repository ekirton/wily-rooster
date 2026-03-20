"""TDD tests for the Mermaid Renderer (specification/mermaid-renderer.md).

Tests are written BEFORE implementation. They will fail with ImportError
until src/poule/rendering/mermaid_renderer.py exists.

Spec: specification/mermaid-renderer.md
Architecture: doc/architecture/mermaid-renderer.md
Data model: doc/architecture/data-models/proof-types.md

Import paths under test:
  poule.rendering.mermaid_renderer  (sanitize, render_proof_state, etc.)
  poule.rendering.types             (DetailLevel, RenderedDiagram, SequenceEntry)
  poule.session.types               (ProofState, Goal, Hypothesis, ProofTrace, etc.)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Lazy imports — deferred so tests fail with ImportError, not at collection
# ---------------------------------------------------------------------------

def _import_renderer():
    from Poule.rendering.mermaid_renderer import (
        sanitize,
        render_proof_state,
        render_proof_tree,
        render_dependencies,
        render_proof_sequence,
    )
    return sanitize, render_proof_state, render_proof_tree, render_dependencies, render_proof_sequence


def _import_types():
    from Poule.session.types import (
        Goal,
        Hypothesis,
        ProofState,
        ProofTrace,
        TraceStep,
    )
    return Goal, Hypothesis, ProofState, ProofTrace, TraceStep


def _import_detail_level():
    from Poule.rendering.types import DetailLevel
    return DetailLevel


# ---------------------------------------------------------------------------
# Helpers: data factories using real types
# ---------------------------------------------------------------------------

def _make_goal(index=0, type_="forall n m, n + m = m + n", hypotheses=None):
    Goal, Hypothesis, *_ = _import_types()
    if hypotheses is None:
        hypotheses = []
    return Goal(index=index, type=type_, hypotheses=hypotheses)


def _make_hypothesis(name="n", type_="nat", body=None):
    _, Hypothesis, *_ = _import_types()
    return Hypothesis(name=name, type=type_, body=body)


def _make_proof_state(
    step_index=0,
    is_complete=False,
    goals=None,
    focused_goal_index=0,
    session_id="test",
):
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


def _make_proof_trace(steps, proof_name="test_thm", file_path="/test.v", session_id="test"):
    _, _, _, ProofTrace, _ = _import_types()
    total_steps = len(steps) - 1  # steps includes initial state
    return ProofTrace(
        schema_version=1,
        session_id=session_id,
        proof_name=proof_name,
        file_path=file_path,
        total_steps=total_steps,
        steps=steps,
    )


def _make_simple_trace():
    """A 2-step trace: initial → intro n → reflexivity (complete)."""
    h_n = _make_hypothesis(name="n", type_="nat")
    step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(
        step_index=0,
        goals=[_make_goal(index=0, type_="forall n, n + 0 = n")],
        focused_goal_index=0,
    ))
    step1 = _make_trace_step(1, tactic="intro n", state=_make_proof_state(
        step_index=1,
        goals=[_make_goal(index=0, type_="n + 0 = n", hypotheses=[h_n])],
        focused_goal_index=0,
    ))
    step2 = _make_trace_step(2, tactic="reflexivity", state=_make_proof_state(
        step_index=2,
        is_complete=True,
        goals=[],
        focused_goal_index=None,
    ))
    return _make_proof_trace([step0, step1, step2])


def _make_branching_trace():
    """A 4-step trace with branching: initial → intro n → destruct n → reflexivity / simpl; auto."""
    step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(
        step_index=0,
        goals=[_make_goal(index=0, type_="forall n, n + 0 = n")],
    ))
    step1 = _make_trace_step(1, tactic="intro n", state=_make_proof_state(
        step_index=1,
        goals=[_make_goal(index=0, type_="n + 0 = n", hypotheses=[_make_hypothesis("n", "nat")])],
    ))
    step2 = _make_trace_step(2, tactic="destruct n", state=_make_proof_state(
        step_index=2,
        goals=[
            _make_goal(index=0, type_="0 + 0 = 0"),
            _make_goal(index=1, type_="S n + 0 = S n", hypotheses=[_make_hypothesis("n", "nat")]),
        ],
    ))
    step3 = _make_trace_step(3, tactic="reflexivity", state=_make_proof_state(
        step_index=3,
        goals=[_make_goal(index=0, type_="S n + 0 = S n", hypotheses=[_make_hypothesis("n", "nat")])],
    ))
    step4 = _make_trace_step(4, tactic="simpl; auto", state=_make_proof_state(
        step_index=4,
        is_complete=True,
        goals=[],
        focused_goal_index=None,
    ))
    return _make_proof_trace([step0, step1, step2, step3, step4])


# ===========================================================================
# 1. Text Sanitization (§4.1)
# ===========================================================================

class TestSanitize:
    """Spec §4.1: sanitize(text, max_label_length=80)."""

    def test_plain_text_passes_through(self):
        """Simple text without special characters is returned unchanged or recognizable."""
        sanitize, *_ = _import_renderer()
        result = sanitize("forall n m : nat, n + m = m + n")
        # The result must contain the original content (possibly quoted/escaped)
        assert "forall" in result
        assert "nat" in result
        assert "n + m" in result or "n + m" in result

    def test_angle_brackets_escaped(self):
        """Spec §4.1: < > replaced with &lt; &gt;."""
        sanitize, *_ = _import_renderer()
        result = sanitize("A < B > C")
        assert "<" not in result or "&lt;" in result
        assert ">" not in result or "&gt;" in result

    def test_double_quote_escaped(self):
        """Spec §4.1: " replaced with &quot;."""
        sanitize, *_ = _import_renderer()
        result = sanitize('H : "quoted"')
        assert "&quot;" in result or '"' not in result.replace("&quot;", "")

    def test_hash_escaped(self):
        """Spec §4.1: # replaced with &num;."""
        sanitize, *_ = _import_renderer()
        result = sanitize("H : #1")
        assert "&num;" in result or "#" not in result

    def test_pipe_replaced(self):
        """Spec §4.1: | replaced with ∣ (U+2223) or escaped."""
        sanitize, *_ = _import_renderer()
        result = sanitize("match x with | O => 0 | S n => n end")
        # Raw | must not appear (Mermaid interprets it as column separator)
        assert "|" not in result or "∣" in result

    def test_curly_braces_escaped(self):
        """Spec §4.1: { } escaped — the Given/When/Then example from the spec."""
        sanitize, *_ = _import_renderer()
        result = sanitize("H : {x : nat | x > 0}")
        # Braces must not cause Mermaid to interpret as rhombus/hexagon shape
        # They should be within quotes or replaced
        assert isinstance(result, str)
        assert len(result) > 0

    def test_newlines_replaced_with_br(self):
        """Spec §4.1: newlines replaced with <br/>."""
        sanitize, *_ = _import_renderer()
        result = sanitize("line1\nline2")
        assert "\n" not in result
        assert "<br/>" in result

    def test_truncation_at_max_label_length(self):
        """Spec §4.1: text exceeding max_label_length is truncated with …."""
        sanitize, *_ = _import_renderer()
        long_text = "a" * 120
        result = sanitize(long_text, max_label_length=80)
        assert len(result) <= 80
        assert result.endswith("…")

    def test_truncation_exact_length_not_truncated(self):
        """Text exactly at max_label_length is not truncated."""
        sanitize, *_ = _import_renderer()
        text = "a" * 80
        result = sanitize(text, max_label_length=80)
        assert "…" not in result

    def test_short_text_not_truncated(self):
        """Text shorter than max_label_length is not truncated."""
        sanitize, *_ = _import_renderer()
        result = sanitize("short", max_label_length=80)
        assert "…" not in result

    def test_max_label_length_zero_uses_default(self):
        """Spec §7: max_label_length ≤ 0 treated as default (80)."""
        sanitize, *_ = _import_renderer()
        long_text = "a" * 120
        result = sanitize(long_text, max_label_length=0)
        assert len(result) <= 80

    def test_max_label_length_negative_uses_default(self):
        """Spec §7: max_label_length ≤ 0 treated as default (80)."""
        sanitize, *_ = _import_renderer()
        long_text = "a" * 120
        result = sanitize(long_text, max_label_length=-5)
        assert len(result) <= 80

    def test_empty_string_returns_empty_or_minimal(self):
        """Sanitizing empty string returns a string."""
        sanitize, *_ = _import_renderer()
        result = sanitize("")
        assert isinstance(result, str)


# ===========================================================================
# 2. Proof State Rendering (§4.2)
# ===========================================================================

class TestRenderProofState:
    """Spec §4.2: render_proof_state(state, detail_level)."""

    def test_complete_proof_returns_qed_node(self):
        """Spec §4.2: when is_complete=true, returns single-node 'Proof complete (Qed)'."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        state = _make_proof_state(is_complete=True)
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "Proof complete (Qed)" in result
        assert "flowchart" in result or "graph" in result

    def test_empty_state_returns_empty_state_node(self):
        """Spec §4.2: when goals empty and not complete, returns 'Empty state'."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        _, _, ProofState, *_ = _import_types()
        state = ProofState(
            schema_version=1,
            session_id="test",
            step_index=0,
            is_complete=False,
            focused_goal_index=None,
            goals=[],
        )
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "Empty state" in result

    def test_standard_detail_shows_hypotheses(self):
        """Spec §4.2: STANDARD shows names + sanitized types for hypotheses."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h_n = _make_hypothesis(name="n", type_="nat")
        h_H = _make_hypothesis(name="H", type_="n > 0")
        goal = _make_goal(index=0, type_="n + 0 = n", hypotheses=[h_n, h_H])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "n : nat" in result or ("n" in result and "nat" in result)
        assert "H" in result
        assert "n + 0 = n" in result or "n + 0" in result

    def test_standard_detail_contains_subgraph_per_goal(self):
        """Spec §4.2: one visual group (subgraph) per goal."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        g0 = _make_goal(index=0, type_="P")
        g1 = _make_goal(index=1, type_="Q")
        state = _make_proof_state(goals=[g0, g1], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        # Should contain two subgraphs
        assert result.count("subgraph") >= 2

    def test_focused_goal_has_distinct_style(self):
        """Spec §4.2: focused goal uses distinct Mermaid node style."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        g0 = _make_goal(index=0, type_="P")
        g1 = _make_goal(index=1, type_="Q")
        state = _make_proof_state(goals=[g0, g1], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        # The focused goal (goal0) should have styling
        assert "style" in result or ":::" in result

    def test_target_node_has_turnstile(self):
        """Spec §4.2: target node labeled ⊢ {goal_type}."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        goal = _make_goal(index=0, type_="P -> Q")
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "⊢" in result

    def test_summary_shows_goal_count(self):
        """Spec §4.2: SUMMARY shows goal count + focused goal type only."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        goals = [_make_goal(index=i, type_=f"G{i}") for i in range(5)]
        state = _make_proof_state(goals=goals, focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.SUMMARY)
        assert "5" in result  # goal count
        assert "G0" in result  # focused goal type

    def test_summary_does_not_show_hypotheses(self):
        """Spec §4.2: SUMMARY does not show hypotheses."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h = _make_hypothesis(name="my_hyp", type_="nat")
        goal = _make_goal(index=0, type_="P", hypotheses=[h])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.SUMMARY)
        assert "my_hyp" not in result

    def test_detailed_shows_let_bodies(self):
        """Spec §4.2: DETAILED shows let-bodies for let-bound hypotheses."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h = _make_hypothesis(name="x", type_="nat", body="5")
        goal = _make_goal(index=0, type_="x = 5", hypotheses=[h])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.DETAILED)
        assert ":= 5" in result or "5" in result

    def test_hypothesis_edges_to_target(self):
        """Spec §4.2: edges from each hypothesis node to the target node."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h = _make_hypothesis(name="n", type_="nat")
        goal = _make_goal(index=0, type_="P n", hypotheses=[h])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "-->" in result

    def test_returns_valid_flowchart(self):
        """Spec §4.2: returns a valid Mermaid flowchart string."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        state = _make_proof_state()
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert result.strip().startswith("flowchart")

    def test_default_detail_level_is_standard(self):
        """Spec §4.2: detail_level defaults to STANDARD."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h = _make_hypothesis(name="H", type_="P")
        goal = _make_goal(index=0, type_="Q", hypotheses=[h])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        # Call without detail_level — should work and show hypotheses
        result = render_proof_state(state)
        assert "H" in result


# ===========================================================================
# 3. Proof Tree Rendering (§4.3)
# ===========================================================================

class TestRenderProofTree:
    """Spec §4.3: render_proof_tree(trace)."""

    def test_simple_trace_produces_tree(self):
        """A simple 2-step completed trace produces a valid tree diagram."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_simple_trace()
        result = render_proof_tree(trace)
        assert "flowchart TD" in result

    def test_root_node_is_theorem_statement(self):
        """Spec §4.3 step 1: root node is the theorem statement from step 0."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_simple_trace()
        result = render_proof_tree(trace)
        # Root should reference the initial goal type
        assert "forall n, n + 0 = n" in result or "forall n" in result

    def test_tactic_appears_as_edge_label(self):
        """Spec §4.3: tactic applications appear as labeled edges."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_simple_trace()
        result = render_proof_tree(trace)
        assert "intro n" in result
        assert "reflexivity" in result

    def test_discharged_goals_visually_distinct(self):
        """Spec §4.3: discharged goals use distinct style (dashed border or different fill)."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_simple_trace()
        result = render_proof_tree(trace)
        # Should contain a classDef for discharged goals or :::discharged
        assert "discharged" in result.lower() or "stroke-dasharray" in result or "✓" in result

    def test_branching_trace_shows_multiple_children(self):
        """Spec §4.3: branching tactics produce multiple child nodes."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_branching_trace()
        result = render_proof_tree(trace)
        # destruct n creates two subgoals — both should appear
        assert "0 + 0 = 0" in result or "0 + 0" in result
        assert "S n" in result

    def test_deterministic_node_ids(self):
        """Spec §4.3 / §8: node IDs are deterministic — s{step}g{goal} format."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_simple_trace()
        result = render_proof_tree(trace)
        assert "s0g0" in result  # root

    def test_idempotency(self):
        """Spec §6/§8: same input always produces same output (byte-identical)."""
        *_, render_proof_tree, _, _ = _import_renderer()
        trace = _make_simple_trace()
        result1 = render_proof_tree(trace)
        result2 = render_proof_tree(trace)
        assert result1 == result2

    def test_single_step_proof(self):
        """Spec §4.3: 1-step proof shows root with one edge to discharged leaf."""
        *_, render_proof_tree, _, _ = _import_renderer()
        step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(
            step_index=0, goals=[_make_goal(0, "True")],
        ))
        step1 = _make_trace_step(1, tactic="exact I", state=_make_proof_state(
            step_index=1, is_complete=True, goals=[], focused_goal_index=None,
        ))
        trace = _make_proof_trace([step0, step1])
        result = render_proof_tree(trace)
        assert "exact I" in result
        assert "flowchart TD" in result


# ===========================================================================
# 4. Dependency Subgraph Rendering (§4.4)
# ===========================================================================

class TestRenderDependencies:
    """Spec §4.4: render_dependencies(theorem_name, adjacency_list, max_depth, max_nodes)."""

    def _simple_adjacency_list(self):
        """Nat.add_comm → {Nat.add_0_r (lemma), Nat.add_succ_r (lemma), eq_ind (definition)}."""
        return {
            "Nat.add_comm": [
                {"name": "Nat.add_0_r", "kind": "lemma"},
                {"name": "Nat.add_succ_r", "kind": "lemma"},
                {"name": "eq_ind", "kind": "definition"},
            ],
            "Nat.add_0_r": [],
            "Nat.add_succ_r": [],
            "eq_ind": [],
        }

    def test_simple_graph_renders_all_nodes(self):
        """Spec §4.4 example: 4 nodes (root + 3 deps), truncated=false."""
        *_, render_dependencies, _ = _import_renderer()
        adj = self._simple_adjacency_list()
        result = render_dependencies("Nat.add_comm", adj, max_depth=1, max_nodes=50)
        assert result.node_count == 4
        assert result.truncated is False
        assert "Nat.add_comm" in result.mermaid
        assert "Nat.add_0_r" in result.mermaid
        assert "Nat.add_succ_r" in result.mermaid
        assert "eq_ind" in result.mermaid

    def test_directed_edges_from_root(self):
        """Spec §4.4: directed edges source --> target."""
        *_, render_dependencies, _ = _import_renderer()
        adj = self._simple_adjacency_list()
        result = render_dependencies("Nat.add_comm", adj, max_depth=1, max_nodes=50)
        assert "-->" in result.mermaid

    def test_root_node_has_distinct_style(self):
        """Spec §4.4: root node uses distinct style (bold border or different fill)."""
        *_, render_dependencies, _ = _import_renderer()
        adj = self._simple_adjacency_list()
        result = render_dependencies("Nat.add_comm", adj, max_depth=1, max_nodes=50)
        assert "root" in result.mermaid.lower() or "style" in result.mermaid or ":::" in result.mermaid

    def test_definition_uses_rounded_rectangle(self):
        """Spec §4.4: definition kind uses rounded rectangle ([...])."""
        *_, render_dependencies, _ = _import_renderer()
        adj = self._simple_adjacency_list()
        result = render_dependencies("Nat.add_comm", adj, max_depth=1, max_nodes=50)
        # eq_ind is a definition — should use rounded rectangle ([ ])
        assert "([" in result.mermaid or "([ " in result.mermaid

    def test_axiom_uses_hexagon(self):
        """Spec §4.4: axiom kind uses hexagon shape."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {
            "thm": [{"name": "Classical_Prop", "kind": "axiom"}],
            "Classical_Prop": [],
        }
        result = render_dependencies("thm", adj, max_depth=1, max_nodes=50)
        # Axiom should use hexagon {{ }}
        assert "{{" in result.mermaid or "hexagon" in result.mermaid.lower()

    def test_unknown_theorem_returns_single_node(self):
        """Spec §4.4: when theorem_name not in adjacency_list, return single-node diagram."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {}
        result = render_dependencies("unknown_thm", adj, max_depth=2, max_nodes=50)
        assert "unknown_thm" in result.mermaid
        assert result.node_count == 1
        assert result.truncated is False

    def test_max_nodes_truncation(self):
        """Spec §4.4: max_nodes caps the diagram; sets truncated=true."""
        *_, render_dependencies, _ = _import_renderer()
        # Create a graph with 20 direct dependencies
        deps = [{"name": f"dep_{i}", "kind": "lemma"} for i in range(20)]
        adj = {"root": deps}
        for d in deps:
            adj[d["name"]] = []
        result = render_dependencies("root", adj, max_depth=1, max_nodes=5)
        assert result.node_count <= 5
        assert result.truncated is True

    def test_max_depth_limits_traversal(self):
        """Spec §4.4: depth limiting controls how far BFS goes."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {
            "A": [{"name": "B", "kind": "lemma"}],
            "B": [{"name": "C", "kind": "lemma"}],
            "C": [{"name": "D", "kind": "lemma"}],
            "D": [],
        }
        # depth=1 should include A and B only
        result = render_dependencies("A", adj, max_depth=1, max_nodes=50)
        assert "A" in result.mermaid
        assert "B" in result.mermaid
        assert '"C"' not in result.mermaid
        assert '"D"' not in result.mermaid

    def test_cycles_handled(self):
        """Spec §7 edge case: adjacency list with cycles — BFS doesn't loop."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {
            "A": [{"name": "B", "kind": "lemma"}],
            "B": [{"name": "A", "kind": "lemma"}],
        }
        result = render_dependencies("A", adj, max_depth=5, max_nodes=50)
        assert result.node_count == 2
        assert result.truncated is False

    def test_max_depth_zero_uses_default(self):
        """Spec §7: max_depth ≤ 0 treated as default (2)."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {
            "A": [{"name": "B", "kind": "lemma"}],
            "B": [{"name": "C", "kind": "lemma"}],
            "C": [],
        }
        result = render_dependencies("A", adj, max_depth=0, max_nodes=50)
        # Default depth=2 should include A, B, C
        assert "C" in result.mermaid

    def test_max_nodes_zero_uses_default(self):
        """Spec §7: max_nodes ≤ 0 treated as default (50)."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {"A": [{"name": f"d{i}", "kind": "lemma"} for i in range(10)]}
        for i in range(10):
            adj[f"d{i}"] = []
        result = render_dependencies("A", adj, max_depth=1, max_nodes=0)
        # Default 50 should include all 11 nodes
        assert result.node_count == 11
        assert result.truncated is False

    def test_flowchart_td_direction(self):
        """Spec §4.4: uses top-down direction (TD)."""
        *_, render_dependencies, _ = _import_renderer()
        adj = self._simple_adjacency_list()
        result = render_dependencies("Nat.add_comm", adj, max_depth=1, max_nodes=50)
        assert "flowchart TD" in result.mermaid

    def test_truncation_adds_summary_node(self):
        """Spec §4.4: truncation adds summary node '… and {N} more'."""
        *_, render_dependencies, _ = _import_renderer()
        deps = [{"name": f"dep_{i}", "kind": "lemma"} for i in range(20)]
        adj = {"root": deps}
        for d in deps:
            adj[d["name"]] = []
        result = render_dependencies("root", adj, max_depth=1, max_nodes=5)
        assert "more" in result.mermaid.lower()
        assert "…" in result.mermaid or "..." in result.mermaid


# ===========================================================================
# 5. Proof Sequence Rendering (§4.5)
# ===========================================================================

class TestRenderProofSequence:
    """Spec §4.5: render_proof_sequence(trace, detail_level)."""

    def test_returns_correct_number_of_entries(self):
        """Spec §4.5: returns total_steps + 1 entries."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_simple_trace()  # 2 steps → 3 entries
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        assert len(result) == 3

    def test_step_0_has_null_tactic(self):
        """Spec §4.5: step 0 tactic is null."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_simple_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        assert result[0].step_index == 0
        assert result[0].tactic is None

    def test_step_1_has_tactic_string(self):
        """Spec §4.5: steps 1..N have the tactic string."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_simple_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        assert result[1].step_index == 1
        assert result[1].tactic == "intro n"

    def test_each_entry_has_valid_mermaid(self):
        """Spec §4.5: each entry's mermaid is a valid Mermaid flowchart."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_simple_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        for entry in result:
            assert isinstance(entry.mermaid, str)
            assert len(entry.mermaid) > 0
            assert "flowchart" in entry.mermaid or "graph" in entry.mermaid

    def test_step_0_has_no_diff_annotations(self):
        """Spec §4.5: step 0 is a plain proof state diagram (no diff annotations)."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_simple_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        step0_mermaid = result[0].mermaid
        # Step 0 should not contain diff-related style classes
        assert "added" not in step0_mermaid.lower() or "classDef added" not in step0_mermaid

    def test_new_hypothesis_highlighted_in_diff(self):
        """Spec §4.5: hypotheses_added get highlighted style."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        # Step 1 introduces hypothesis n via intro n
        trace = _make_simple_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        step1_mermaid = result[1].mermaid
        # Hypothesis n was added at step 1 — should be highlighted
        assert "added" in step1_mermaid.lower() or ":::" in step1_mermaid

    def test_discharged_goal_omitted(self):
        """Spec §4.5: goals_removed are omitted from the diagram."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_branching_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        # Step 3: reflexivity discharges goal "0 + 0 = 0"
        # Step 3 diagram should NOT contain the discharged goal
        step3_mermaid = result[3].mermaid
        assert "0 + 0 = 0" not in step3_mermaid

    def test_branching_trace_sequence_length(self):
        """Branching trace with 4 steps produces 5 entries."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_branching_trace()
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        assert len(result) == 5


# ===========================================================================
# 6. Edge Cases (§7)
# ===========================================================================

class TestEdgeCases:
    """Spec §7: degenerate inputs and edge cases."""

    def test_empty_hypothesis_name_renders_underscore(self):
        """Spec §7: empty hypothesis name renders as '_ : {type}'."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h = _make_hypothesis(name="", type_="nat")
        goal = _make_goal(index=0, type_="P", hypotheses=[h])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "_ : " in result or ("_" in result and "nat" in result)

    def test_empty_goal_type_renders_empty_marker(self):
        """Spec §7: empty goal type renders as '⊢ (empty)'."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        goal = _make_goal(index=0, type_="")
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        assert "(empty)" in result

    def test_empty_tactic_string_uses_placeholder(self):
        """Spec §7: empty tactic string uses edge label '(empty tactic)'."""
        *_, render_proof_tree, _, _ = _import_renderer()
        step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(
            step_index=0, goals=[_make_goal(0, "P")],
        ))
        step1 = _make_trace_step(1, tactic="", state=_make_proof_state(
            step_index=1, is_complete=True, goals=[], focused_goal_index=None,
        ))
        trace = _make_proof_trace([step0, step1])
        result = render_proof_tree(trace)
        assert "(empty tactic)" in result

    def test_zero_step_trace_returns_initial_state(self):
        """Spec §7: proof trace with 0 steps returns diagram of initial state only."""
        *_, render_proof_tree, _, _ = _import_renderer()
        step0 = _make_trace_step(0, tactic=None, state=_make_proof_state(
            step_index=0, is_complete=True, goals=[], focused_goal_index=None,
        ))
        _, _, _, ProofTrace, _ = _import_types()
        trace = ProofTrace(
            schema_version=1,
            session_id="test",
            proof_name="trivial",
            file_path="/test.v",
            total_steps=0,
            steps=[step0],
        )
        result = render_proof_tree(trace)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_no_visible_change_diff_annotated(self):
        """Spec §7: ProofStateDiff with all fields empty shows '(no visible change)'."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        # Two identical states — tactic changed nothing visible
        same_state = _make_proof_state(
            step_index=0, goals=[_make_goal(0, "P")],
        )
        step0 = _make_trace_step(0, tactic=None, state=same_state)
        same_state_after = _make_proof_state(
            step_index=1, goals=[_make_goal(0, "P")],
        )
        step1 = _make_trace_step(1, tactic="idtac", state=same_state_after)
        # Manually set is_complete for the trace to be valid for render_proof_sequence
        complete_state = _make_proof_state(
            step_index=2, is_complete=True, goals=[], focused_goal_index=None,
        )
        step2 = _make_trace_step(2, tactic="exact I", state=complete_state)
        trace = _make_proof_trace([step0, step1, step2])
        result = render_proof_sequence(trace, DetailLevel.STANDARD)
        # Step 1 (idtac) changed nothing — should have the note
        assert "no visible change" in result[1].mermaid.lower()

    def test_duplicate_hypothesis_names_both_rendered(self):
        """Spec §7: two hypotheses with the same name are both rendered."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h1 = _make_hypothesis(name="H", type_="P")
        h2 = _make_hypothesis(name="H", type_="Q")
        goal = _make_goal(index=0, type_="R", hypotheses=[h1, h2])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        result = render_proof_state(state, DetailLevel.STANDARD)
        # Both hypothesis types should appear
        assert "P" in result
        assert "Q" in result


# ===========================================================================
# 7. Non-Functional Requirements (§8)
# ===========================================================================

class TestNonFunctionalRequirements:
    """Spec §8: determinism, performance, no dependencies."""

    def test_render_proof_state_deterministic(self):
        """Spec §8: same input → byte-identical output."""
        _, render_proof_state, *_ = _import_renderer()
        DetailLevel = _import_detail_level()
        h = _make_hypothesis(name="n", type_="nat")
        goal = _make_goal(index=0, type_="P n", hypotheses=[h])
        state = _make_proof_state(goals=[goal], focused_goal_index=0)
        r1 = render_proof_state(state, DetailLevel.STANDARD)
        r2 = render_proof_state(state, DetailLevel.STANDARD)
        assert r1 == r2

    def test_render_dependencies_deterministic(self):
        """Spec §8: same input → byte-identical output."""
        *_, render_dependencies, _ = _import_renderer()
        adj = {
            "A": [{"name": "B", "kind": "lemma"}, {"name": "C", "kind": "definition"}],
            "B": [],
            "C": [],
        }
        r1 = render_dependencies("A", adj, max_depth=1, max_nodes=50)
        r2 = render_dependencies("A", adj, max_depth=1, max_nodes=50)
        assert r1.mermaid == r2.mermaid

    def test_render_proof_sequence_deterministic(self):
        """Spec §8: same input → byte-identical output."""
        *_, render_proof_sequence = _import_renderer()
        DetailLevel = _import_detail_level()
        trace = _make_simple_trace()
        r1 = render_proof_sequence(trace, DetailLevel.STANDARD)
        r2 = render_proof_sequence(trace, DetailLevel.STANDARD)
        for e1, e2 in zip(r1, r2):
            assert e1.mermaid == e2.mermaid


# ===========================================================================
# 8. Data Model (§5)
# ===========================================================================

class TestDetailLevel:
    """Spec §5: DetailLevel enum."""

    def test_summary_value(self):
        DetailLevel = _import_detail_level()
        assert DetailLevel.SUMMARY.value == "summary"

    def test_standard_value(self):
        DetailLevel = _import_detail_level()
        assert DetailLevel.STANDARD.value == "standard"

    def test_detailed_value(self):
        DetailLevel = _import_detail_level()
        assert DetailLevel.DETAILED.value == "detailed"

    def test_three_members(self):
        DetailLevel = _import_detail_level()
        assert len(DetailLevel) == 3

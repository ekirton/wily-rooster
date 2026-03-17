"""Mermaid diagram renderer for proof visualization.

Pure function component — no I/O, no external dependencies, no state.

Spec: specification/mermaid-renderer.md
Architecture: doc/architecture/mermaid-renderer.md
"""

from __future__ import annotations

from collections import deque
from typing import Any, Optional

from poule.rendering.types import DetailLevel, RenderedDiagram, SequenceEntry
from poule.session.types import (
    Goal,
    Hypothesis,
    ProofState,
    ProofStateDiff,
    ProofTrace,
)

_DEFAULT_MAX_LABEL_LENGTH = 80
_DEFAULT_MAX_DEPTH = 2
_DEFAULT_MAX_NODES = 50
_HARD_NODE_LIMIT = 200


# ---------------------------------------------------------------------------
# Text Sanitization (§4.1)
# ---------------------------------------------------------------------------

def sanitize(text: str, max_label_length: int = _DEFAULT_MAX_LABEL_LENGTH) -> str:
    """Escape Mermaid-significant characters and truncate if needed.

    Spec §4.1: all Coq expression text passes through this function before
    being embedded in Mermaid node or edge labels.
    """
    if max_label_length <= 0:
        max_label_length = _DEFAULT_MAX_LABEL_LENGTH

    # Replace characters that conflict with Mermaid syntax
    result = text
    result = result.replace("&", "&amp;")  # must be first
    result = result.replace("<", "&lt;")
    result = result.replace(">", "&gt;")
    result = result.replace('"', "&quot;")
    result = result.replace("#", "&num;")
    result = result.replace("|", "∣")  # U+2223
    result = result.replace("\n", "<br/>")

    # Truncate if too long
    if len(result) > max_label_length:
        result = result[: max_label_length - 1] + "…"

    return result


def _quote_label(text: str) -> str:
    """Wrap a sanitized label in double quotes for Mermaid."""
    return f'"{text}"'


# ---------------------------------------------------------------------------
# Proof State Rendering (§4.2)
# ---------------------------------------------------------------------------

def render_proof_state(
    state: ProofState,
    detail_level: DetailLevel = DetailLevel.STANDARD,
) -> str:
    """Render a ProofState as a Mermaid flowchart.

    Spec §4.2: one subgraph per goal, hypotheses as nodes, target node
    with turnstile, focused goal highlighted.
    """
    lines: list[str] = ["flowchart TD"]

    # Complete proof
    if state.is_complete:
        lines.append('    n0["Proof complete (Qed)"]')
        return "\n".join(lines)

    # Empty state
    if not state.goals:
        lines.append('    n0["Empty state"]')
        return "\n".join(lines)

    # Summary detail level
    if detail_level == DetailLevel.SUMMARY:
        count = len(state.goals)
        focused_idx = state.focused_goal_index if state.focused_goal_index is not None else 0
        focused_type = sanitize(state.goals[focused_idx].type) if focused_idx < len(state.goals) else ""
        lines.append(f'    n0["{count} goals"]')
        lines.append(f'    n1[{_quote_label("⊢ " + focused_type)}]')
        lines.append("    n0 --> n1")
        return "\n".join(lines)

    # Standard / Detailed
    for goal in state.goals:
        is_focused = goal.index == state.focused_goal_index
        gid = f"goal{goal.index}"
        label_suffix = " ✦" if is_focused else ""
        lines.append(f'    subgraph {gid}["Goal {goal.index}{label_suffix}"]')

        if is_focused:
            lines.append(f"        style {gid} fill:#e8f4fd,stroke:#1a73e8,stroke-width:2px")

        # Hypotheses
        for h_idx, hyp in enumerate(goal.hypotheses):
            h_node_id = f"h{goal.index}_{h_idx}"
            name_part = hyp.name if hyp.name else "_"
            type_part = sanitize(hyp.type)
            label = f"{name_part} : {type_part}"
            if detail_level == DetailLevel.DETAILED and hyp.body is not None:
                body_part = sanitize(hyp.body)
                label += f" := {body_part}"
            lines.append(f'        {h_node_id}[{_quote_label(label)}]')

        # Target node
        goal_type = sanitize(goal.type) if goal.type else "(empty)"
        t_node_id = f"t{goal.index}"
        lines.append(f'        {t_node_id}[{_quote_label("⊢ " + goal_type)}]')

        # Edges from hypotheses to target
        for h_idx in range(len(goal.hypotheses)):
            h_node_id = f"h{goal.index}_{h_idx}"
            lines.append(f"        {h_node_id} --> {t_node_id}")

        lines.append("    end")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Proof Tree Rendering (§4.3)
# ---------------------------------------------------------------------------

def _goals_set(goals: list[Goal]) -> set[tuple[int, str]]:
    """Create a set of (index, type) tuples for goal comparison."""
    return {(g.index, g.type) for g in goals}


def render_proof_tree(trace: ProofTrace) -> str:
    """Render a ProofTrace as a Mermaid top-down tree diagram.

    Spec §4.3: tactic applications as labeled edges, subgoals as nodes,
    discharged goals visually distinct.
    """
    lines: list[str] = ["flowchart TD"]

    if not trace.steps:
        lines.append('    s0g0["(empty)"]')
        return "\n".join(lines)

    # Root node: theorem statement from step 0
    initial_state = trace.steps[0].state
    if initial_state.goals:
        root_type = sanitize(initial_state.goals[0].type)
    else:
        root_type = "Proof complete (Qed)"
    lines.append(f'    s0g0[{_quote_label(root_type)}]')

    if trace.total_steps == 0:
        return "\n".join(lines)

    # Track which nodes exist and which are discharged
    # We use a simple approach: for each step, the tactic acts on the focused
    # goal of the previous state, producing new goals or discharging the current one.
    discharged_nodes: list[str] = []

    for k in range(1, len(trace.steps)):
        step = trace.steps[k]
        prev_state = trace.steps[k - 1].state
        curr_state = step.state
        tactic = step.tactic or "(empty tactic)"
        tactic_label = sanitize(tactic)

        prev_goals = _goals_set(prev_state.goals)
        curr_goals = _goals_set(curr_state.goals)

        # Determine parent: the focused goal of the previous state
        focused_idx = prev_state.focused_goal_index
        if focused_idx is not None and focused_idx < len(prev_state.goals):
            parent_id = f"s{k-1}g{focused_idx}"
        else:
            parent_id = f"s{k-1}g0"

        # Goals introduced (in curr but not in prev)
        added = curr_goals - prev_goals
        # Goals removed (in prev but not in curr)
        removed = prev_goals - curr_goals

        if curr_state.is_complete and not curr_state.goals:
            # Proof completed — all remaining goals discharged
            node_id = f"s{k}g0"
            lines.append(f'    {parent_id} -->|{_quote_label(tactic_label)}| {node_id}["✓"]:::{_DISCHARGED_CLASS}')
            discharged_nodes.append(node_id)
        elif added:
            # New goals introduced
            for g in curr_state.goals:
                if (g.index, g.type) in added:
                    node_id = f"s{k}g{g.index}"
                    goal_label = sanitize(g.type)
                    lines.append(f'    {parent_id} -->|{_quote_label(tactic_label)}| {node_id}[{_quote_label(goal_label)}]')
        elif removed and not added:
            # Goal discharged, remaining goals unchanged
            node_id = f"s{k}g0"
            lines.append(f'    {parent_id} -->|{_quote_label(tactic_label)}| {node_id}["✓"]:::{_DISCHARGED_CLASS}')
            discharged_nodes.append(node_id)
        else:
            # Goal transformed (same count, different content)
            if curr_state.goals:
                for g in curr_state.goals:
                    node_id = f"s{k}g{g.index}"
                    goal_label = sanitize(g.type)
                    lines.append(f'    {parent_id} -->|{_quote_label(tactic_label)}| {node_id}[{_quote_label(goal_label)}]')
                    break  # only the focused goal transforms
            else:
                node_id = f"s{k}g0"
                lines.append(f'    {parent_id} -->|{_quote_label(tactic_label)}| {node_id}["✓"]:::{_DISCHARGED_CLASS}')
                discharged_nodes.append(node_id)

    # Class definition for discharged goals
    lines.append(f"    classDef {_DISCHARGED_CLASS} fill:#d4edda,stroke:#28a745,stroke-dasharray:5 5")

    return "\n".join(lines)


_DISCHARGED_CLASS = "discharged"


# ---------------------------------------------------------------------------
# Dependency Subgraph Rendering (§4.4)
# ---------------------------------------------------------------------------

def render_dependencies(
    theorem_name: str,
    adjacency_list: dict[str, list[dict[str, str]]],
    max_depth: int = _DEFAULT_MAX_DEPTH,
    max_nodes: int = _DEFAULT_MAX_NODES,
) -> RenderedDiagram:
    """Render a dependency subgraph as a Mermaid directed graph.

    Spec §4.4: BFS from theorem_name, bounded by max_depth and max_nodes.
    Returns RenderedDiagram with mermaid text, node_count, and truncated flag.
    """
    if max_depth <= 0:
        max_depth = _DEFAULT_MAX_DEPTH
    if max_nodes <= 0:
        max_nodes = _DEFAULT_MAX_NODES

    lines: list[str] = ["flowchart TD"]

    # Single-node case: theorem not in adjacency list
    if theorem_name not in adjacency_list:
        lines.append(f'    n0[{_quote_label(theorem_name)}]')
        return RenderedDiagram(mermaid="\n".join(lines), node_count=1, truncated=False)

    # BFS
    visited: dict[str, int] = {}  # name -> node index
    node_kinds: dict[str, str] = {}  # name -> kind
    edges: list[tuple[int, int]] = []
    queue: deque[tuple[str, int]] = deque()  # (name, depth)
    truncated = False
    suppressed_count = 0

    # Root
    visited[theorem_name] = 0
    node_kinds[theorem_name] = "theorem"  # root is a theorem
    queue.append((theorem_name, 0))

    while queue:
        name, depth = queue.popleft()

        if depth >= max_depth:
            continue

        deps = adjacency_list.get(name, [])
        for dep in deps:
            dep_name = dep["name"]
            dep_kind = dep["kind"]

            if dep_name not in visited:
                if len(visited) >= max_nodes:
                    truncated = True
                    suppressed_count += 1
                    continue
                idx = len(visited)
                visited[dep_name] = idx
                node_kinds[dep_name] = dep_kind
                queue.append((dep_name, depth + 1))

            if dep_name in visited:
                edges.append((visited[name], visited[dep_name]))

    # Count remaining suppressed from queue
    if truncated:
        # Count how many more in the queue we couldn't expand
        for name, depth in queue:
            deps = adjacency_list.get(name, [])
            for dep in deps:
                if dep["name"] not in visited:
                    suppressed_count += 1

    # Generate Mermaid nodes
    for name, idx in sorted(visited.items(), key=lambda x: x[1]):
        kind = node_kinds[name]
        label = _quote_label(name)
        node_id = f"n{idx}"

        if kind == "definition":
            lines.append(f"    {node_id}([{label}])")
        elif kind == "axiom":
            lines.append(f"    {node_id}{{{{{label}}}}}")
        else:
            lines.append(f"    {node_id}[{label}]")

    # Root styling
    lines.append(f"    n0:::root")

    # Edges
    for src, dst in edges:
        lines.append(f"    n{src} --> n{dst}")

    # Class definitions
    lines.append("    classDef root fill:#fff3cd,stroke:#856404,stroke-width:2px")

    # Truncation summary node
    if truncated and suppressed_count > 0:
        summary_idx = len(visited)
        lines.append(f'    n{summary_idx}[{_quote_label(f"… and {suppressed_count} more")}]')

    return RenderedDiagram(
        mermaid="\n".join(lines),
        node_count=len(visited),
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Proof Sequence Rendering (§4.5)
# ---------------------------------------------------------------------------

def _compute_diff(before: ProofState, after: ProofState) -> ProofStateDiff:
    """Compute the diff between two consecutive proof states.

    Uses (index, type) for goal comparison and name for hypothesis comparison.
    """
    before_goals = {(g.index, g.type): g for g in before.goals}
    after_goals = {(g.index, g.type): g for g in after.goals}

    before_keys = set(before_goals.keys())
    after_keys = set(after_goals.keys())

    goals_added = [after_goals[k] for k in sorted(after_keys - before_keys)]
    goals_removed = [before_goals[k] for k in sorted(before_keys - after_keys)]

    # Hypothesis comparison across all goals
    before_hyps = {}
    for g in before.goals:
        for h in g.hypotheses:
            before_hyps[h.name] = h
    after_hyps = {}
    for g in after.goals:
        for h in g.hypotheses:
            after_hyps[h.name] = h

    before_hnames = set(before_hyps.keys())
    after_hnames = set(after_hyps.keys())

    hyps_added = [after_hyps[n] for n in sorted(after_hnames - before_hnames)]
    hyps_removed = [before_hyps[n] for n in sorted(before_hnames - after_hnames)]

    from poule.session.types import HypothesisChange

    hyps_changed = []
    for n in sorted(before_hnames & after_hnames):
        bh = before_hyps[n]
        ah = after_hyps[n]
        if bh.type != ah.type or bh.body != ah.body:
            hyps_changed.append(HypothesisChange(
                name=n,
                type_before=bh.type,
                type_after=ah.type,
                body_before=bh.body,
                body_after=ah.body,
            ))

    return ProofStateDiff(
        from_step=before.step_index,
        to_step=after.step_index,
        goals_added=goals_added,
        goals_removed=goals_removed,
        goals_changed=[],
        hypotheses_added=hyps_added,
        hypotheses_removed=hyps_removed,
        hypotheses_changed=hyps_changed,
    )


def render_proof_sequence(
    trace: ProofTrace,
    detail_level: DetailLevel = DetailLevel.STANDARD,
) -> list[SequenceEntry]:
    """Render a ProofTrace as a sequence of proof state diagrams with diff annotations.

    Spec §4.5: returns total_steps + 1 entries. Step 0 has no diff annotations.
    Steps 1..N have visual highlighting for added/removed/changed elements.
    """
    entries: list[SequenceEntry] = []

    if not trace.steps:
        return entries

    # Step 0: plain proof state diagram, no diff
    step0 = trace.steps[0]
    mermaid0 = render_proof_state(step0.state, detail_level)
    entries.append(SequenceEntry(step_index=0, tactic=None, mermaid=mermaid0))

    # Steps 1..N: with diff annotations
    for k in range(1, len(trace.steps)):
        step = trace.steps[k]
        prev_state = trace.steps[k - 1].state
        curr_state = step.state

        diff = _compute_diff(prev_state, curr_state)

        # Check if there are any visible changes
        has_changes = (
            diff.goals_added
            or diff.goals_removed
            or diff.hypotheses_added
            or diff.hypotheses_removed
            or diff.hypotheses_changed
            or diff.goals_changed
        )

        # Build annotated diagram
        mermaid = _render_annotated_proof_state(curr_state, detail_level, diff, has_changes)
        entries.append(SequenceEntry(
            step_index=step.step_index,
            tactic=step.tactic,
            mermaid=mermaid,
        ))

    return entries


def _render_annotated_proof_state(
    state: ProofState,
    detail_level: DetailLevel,
    diff: ProofStateDiff,
    has_changes: bool,
) -> str:
    """Render a proof state with diff annotations for sequence diagrams."""
    lines: list[str] = ["flowchart TD"]

    added_goal_keys = {(g.index, g.type) for g in diff.goals_added}
    added_hyp_names = {h.name for h in diff.hypotheses_added}
    changed_hyp_names = {h.name for h in diff.hypotheses_changed}

    # Complete proof
    if state.is_complete:
        lines.append('    n0["Proof complete (Qed)"]')
        return "\n".join(lines)

    # Empty state
    if not state.goals:
        lines.append('    n0["Empty state"]')
        return "\n".join(lines)

    # Summary: simplified
    if detail_level == DetailLevel.SUMMARY:
        count = len(state.goals)
        focused_idx = state.focused_goal_index if state.focused_goal_index is not None else 0
        focused_type = sanitize(state.goals[focused_idx].type) if focused_idx < len(state.goals) else ""
        lines.append(f'    n0["{count} goals"]')
        lines.append(f'    n1[{_quote_label("⊢ " + focused_type)}]')
        lines.append("    n0 --> n1")
        if not has_changes:
            lines.append('    n2["(no visible change)"]')
        return "\n".join(lines)

    has_any_annotation = False

    for goal in state.goals:
        is_focused = goal.index == state.focused_goal_index
        gid = f"goal{goal.index}"
        is_new_goal = (goal.index, goal.type) in added_goal_keys
        label_suffix = " ✦" if is_focused else ""
        lines.append(f'    subgraph {gid}["Goal {goal.index}{label_suffix}"]')

        if is_focused:
            lines.append(f"        style {gid} fill:#e8f4fd,stroke:#1a73e8,stroke-width:2px")

        # Hypotheses
        for h_idx, hyp in enumerate(goal.hypotheses):
            h_node_id = f"h{goal.index}_{h_idx}"
            name_part = hyp.name if hyp.name else "_"
            type_part = sanitize(hyp.type)
            label = f"{name_part} : {type_part}"
            if detail_level == DetailLevel.DETAILED and hyp.body is not None:
                body_part = sanitize(hyp.body)
                label += f" := {body_part}"

            if hyp.name in added_hyp_names:
                lines.append(f'        {h_node_id}[{_quote_label(label)}]:::added')
                has_any_annotation = True
            elif hyp.name in changed_hyp_names:
                lines.append(f'        {h_node_id}[{_quote_label(label + " (changed)")}]:::changed')
                has_any_annotation = True
            else:
                lines.append(f'        {h_node_id}[{_quote_label(label)}]')

        # Target node
        goal_type = sanitize(goal.type) if goal.type else "(empty)"
        t_node_id = f"t{goal.index}"
        if is_new_goal:
            lines.append(f'        {t_node_id}[{_quote_label("⊢ " + goal_type)}]:::added')
            has_any_annotation = True
        else:
            lines.append(f'        {t_node_id}[{_quote_label("⊢ " + goal_type)}]')

        # Edges
        for h_idx in range(len(goal.hypotheses)):
            h_node_id = f"h{goal.index}_{h_idx}"
            lines.append(f"        {h_node_id} --> {t_node_id}")

        lines.append("    end")

    # Add class definitions for diff annotations
    if has_any_annotation:
        lines.append("    classDef added fill:#d4edda,stroke:#28a745,stroke-width:2px")
        lines.append("    classDef changed fill:#fff3cd,stroke:#856404,stroke-width:2px")

    if not has_changes:
        lines.append('    note["(no visible change)"]')

    return "\n".join(lines)

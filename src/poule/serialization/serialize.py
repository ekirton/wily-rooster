"""JSON serialization for proof interaction types.

Per specification/proof-serialization.md: deterministic, compact,
with strict field ordering and validation.
"""

from __future__ import annotations

import json
from typing import Any

from poule.session.types import (
    Goal,
    GoalChange,
    Hypothesis,
    HypothesisChange,
    Premise,
    PremiseAnnotation,
    ProofState,
    ProofStateDiff,
    ProofTrace,
    Session,
    TraceStep,
)

_VALID_PREMISE_KINDS = {"lemma", "hypothesis", "constructor", "definition"}


def _compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=False)


def serialize_hypothesis(h: Hypothesis) -> str:
    return _compact({
        "name": h.name,
        "type": h.type,
        "body": h.body,
    })


def serialize_goal(g: Goal) -> str:
    return _compact({
        "index": g.index,
        "type": g.type,
        "hypotheses": [_hyp_dict(h) for h in g.hypotheses],
    })


def serialize_proof_state(state: ProofState) -> str:
    if (
        not state.is_complete
        and state.focused_goal_index is not None
        and state.focused_goal_index >= len(state.goals)
    ):
        raise ValueError("focused_goal_index out of bounds")
    return _compact({
        "schema_version": state.schema_version,
        "session_id": state.session_id,
        "step_index": state.step_index,
        "is_complete": state.is_complete,
        "focused_goal_index": state.focused_goal_index,
        "goals": [_goal_dict(g) for g in state.goals],
    })


def serialize_proof_trace(trace: ProofTrace) -> str:
    if len(trace.steps) != trace.total_steps + 1:
        raise ValueError(
            f"step count mismatch: expected {trace.total_steps + 1}, "
            f"got {len(trace.steps)}"
        )
    return _compact({
        "schema_version": trace.schema_version,
        "session_id": trace.session_id,
        "proof_name": trace.proof_name,
        "file_path": trace.file_path,
        "total_steps": trace.total_steps,
        "steps": [_trace_step_dict(s) for s in trace.steps],
    })


def serialize_trace_step(ts: TraceStep) -> str:
    _validate_trace_step(ts)
    return _compact(_trace_step_dict(ts))


def serialize_premise(p: Premise) -> str:
    if p.kind not in _VALID_PREMISE_KINDS:
        raise ValueError(
            f"kind must be one of {', '.join(sorted(_VALID_PREMISE_KINDS))}"
        )
    return _compact({"name": p.name, "kind": p.kind})


def serialize_premise_annotation(ann: PremiseAnnotation) -> str:
    return _compact({
        "step_index": ann.step_index,
        "tactic": ann.tactic,
        "premises": [_premise_dict(p) for p in ann.premises],
    })


def serialize_session(s: Session) -> str:
    return _compact({
        "session_id": s.session_id,
        "file_path": s.file_path,
        "proof_name": s.proof_name,
        "current_step": s.current_step,
        "total_steps": s.total_steps,
        "created_at": s.created_at,
        "last_active_at": s.last_active_at,
    })


def serialize_proof_state_diff(diff: ProofStateDiff) -> str:
    return _compact({
        "from_step": diff.from_step,
        "to_step": diff.to_step,
        "goals_added": [_goal_dict(g) for g in diff.goals_added],
        "goals_removed": [_goal_dict(g) for g in diff.goals_removed],
        "goals_changed": [_goal_change_dict(gc) for gc in diff.goals_changed],
        "hypotheses_added": [_hyp_dict(h) for h in diff.hypotheses_added],
        "hypotheses_removed": [_hyp_dict(h) for h in diff.hypotheses_removed],
        "hypotheses_changed": [
            _hyp_change_dict(hc) for hc in diff.hypotheses_changed
        ],
    })


def serialize_goal_change(gc: GoalChange) -> str:
    return _compact(_goal_change_dict(gc))


def serialize_hypothesis_change(hc: HypothesisChange) -> str:
    return _compact(_hyp_change_dict(hc))


# -------------------------------------------------------------------
# Internal dict builders (for embedding in parent structures)
# -------------------------------------------------------------------

def _hyp_dict(h: Hypothesis) -> dict:
    return {"name": h.name, "type": h.type, "body": h.body}


def _goal_dict(g: Goal) -> dict:
    return {
        "index": g.index,
        "type": g.type,
        "hypotheses": [_hyp_dict(h) for h in g.hypotheses],
    }


def _premise_dict(p: Premise) -> dict:
    if p.kind not in _VALID_PREMISE_KINDS:
        raise ValueError(
            f"kind must be one of {', '.join(sorted(_VALID_PREMISE_KINDS))}"
        )
    return {"name": p.name, "kind": p.kind}


def _goal_change_dict(gc: GoalChange) -> dict:
    return {"index": gc.index, "before": gc.before, "after": gc.after}


def _hyp_change_dict(hc: HypothesisChange) -> dict:
    return {
        "name": hc.name,
        "type_before": hc.type_before,
        "type_after": hc.type_after,
        "body_before": hc.body_before,
        "body_after": hc.body_after,
    }


def _validate_trace_step(ts: TraceStep) -> None:
    if ts.step_index == 0 and ts.tactic is not None:
        raise ValueError("step 0 must have null tactic")
    if ts.step_index > 0 and ts.tactic is None:
        raise ValueError("steps 1..N must have non-null tactic")


def _trace_step_dict(ts: TraceStep) -> dict:
    _validate_trace_step(ts)
    return {
        "step_index": ts.step_index,
        "tactic": ts.tactic,
        "state": {
            "schema_version": ts.state.schema_version,
            "session_id": ts.state.session_id,
            "step_index": ts.state.step_index,
            "is_complete": ts.state.is_complete,
            "focused_goal_index": ts.state.focused_goal_index,
            "goals": [_goal_dict(g) for g in ts.state.goals],
        },
    }

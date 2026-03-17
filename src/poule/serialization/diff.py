"""Diff computation between consecutive proof states.

Per specification/proof-serialization.md §4.14.
"""

from __future__ import annotations

from poule.session.types import (
    Goal,
    GoalChange,
    Hypothesis,
    HypothesisChange,
    ProofState,
    ProofStateDiff,
)


def compute_diff(state_before: ProofState, state_after: ProofState) -> ProofStateDiff:
    if state_after.step_index != state_before.step_index + 1:
        raise ValueError(
            "states must be consecutive "
            f"(to_step must equal from_step + 1, "
            f"got {state_before.step_index} and {state_after.step_index})"
        )

    before_goals = {g.index: g for g in state_before.goals}
    after_goals = {g.index: g for g in state_after.goals}

    all_indices = set(before_goals) | set(after_goals)

    goals_added: list[Goal] = []
    goals_removed: list[Goal] = []
    goals_changed: list[GoalChange] = []

    for idx in sorted(all_indices):
        in_before = idx in before_goals
        in_after = idx in after_goals
        if in_before and in_after:
            if before_goals[idx].type != after_goals[idx].type:
                goals_changed.append(GoalChange(
                    index=idx,
                    before=before_goals[idx].type,
                    after=after_goals[idx].type,
                ))
        elif in_before:
            goals_removed.append(before_goals[idx])
        else:
            goals_added.append(after_goals[idx])

    # Hypothesis diff: focused goal only
    hypotheses_added: list[Hypothesis] = []
    hypotheses_removed: list[Hypothesis] = []
    hypotheses_changed: list[HypothesisChange] = []

    can_compare_hyps = (
        state_before.focused_goal_index is not None
        and state_after.focused_goal_index is not None
    )
    if can_compare_hyps:
        before_focused_idx = state_before.focused_goal_index
        after_focused_idx = state_after.focused_goal_index
        # Both focused goals must exist in their respective states AND
        # the before-focused goal must still exist in after (not removed),
        # and the after-focused goal must have existed in before (not added).
        before_focused = before_goals.get(before_focused_idx)
        after_focused = after_goals.get(after_focused_idx)
        # The focused goal from before must also exist in after_goals,
        # and the focused goal from after must also exist in before_goals.
        before_focus_survives = before_focused_idx in after_goals
        after_focus_existed = after_focused_idx in before_goals

        if (
            before_focused is not None
            and after_focused is not None
            and before_focus_survives
            and after_focus_existed
        ):
            before_hyps = {
                h.name: (h.type, h.body, h) for h in before_focused.hypotheses
            }
            after_hyps = {
                h.name: (h.type, h.body, h) for h in after_focused.hypotheses
            }
            all_names = set(before_hyps) | set(after_hyps)
            for name in all_names:
                in_b = name in before_hyps
                in_a = name in after_hyps
                if in_b and in_a:
                    bt, bb, _ = before_hyps[name]
                    at, ab, _ = after_hyps[name]
                    if bt != at or bb != ab:
                        hypotheses_changed.append(HypothesisChange(
                            name=name,
                            type_before=bt,
                            type_after=at,
                            body_before=bb,
                            body_after=ab,
                        ))
                elif in_b:
                    hypotheses_removed.append(before_hyps[name][2])
                else:
                    hypotheses_added.append(after_hyps[name][2])

    return ProofStateDiff(
        from_step=state_before.step_index,
        to_step=state_after.step_index,
        goals_added=goals_added,
        goals_removed=goals_removed,
        goals_changed=goals_changed,
        hypotheses_added=hypotheses_added,
        hypotheses_removed=hypotheses_removed,
        hypotheses_changed=hypotheses_changed,
    )

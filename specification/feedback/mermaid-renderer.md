# Specification Feedback: Mermaid Renderer

**Source:** [specification/mermaid-renderer.md](../mermaid-renderer.md)
**Date:** 2026-03-17
**Reviewer:** TDD test authoring pass

---

## Issue 1: Goal comparison method for tree construction is unspecified

**Severity:** medium
**Location:** Section 4.3, Proof Tree Rendering — Tree construction from linear trace, step 2

**Problem:** The spec says "compare `trace.steps[k-1].state.goals` with `trace.steps[k].state.goals`" and defines goals as "present in step k-1 but absent in step k → discharged" and vice versa. However, it does not specify how goal identity is determined across consecutive states.

The Goal type (per data-models/proof-types.md) has fields `index` (position in the goals list), `type` (Coq expression string), and `hypotheses`. None of these are a stable unique identifier:
- `index` changes when goals are reordered (Coq's `Focus` and `swap` tactics reorder goals)
- `type` is a string that could match between genuinely different goals (e.g., two subgoals with the same type `True`)
- `hypotheses` differ between goals with the same type

Without a defined comparison method, two implementations could produce different tree structures from the same ProofTrace.

**Impact:** Implementers must make an unspecified judgment call. Tests cannot assert tree structure without knowing the comparison method. Non-deterministic tree construction breaks the spec's own §8 determinism NFR.

**Suggested resolution:** Specify that goals are compared by `(index, type)` tuple — two goals are "the same" if they have the same index and the same type string. When Coq reorders goals, this will show as goals removed at old indices and added at new indices, which produces correct (if verbose) tree structure. Alternatively, specify comparison by type string alone with a tie-breaking rule for duplicate types.

---

## Issue 2: Summary node count N is not computable from BFS truncation

**Severity:** medium
**Location:** Section 4.4, line "the renderer shall add a summary node labeled `… and {N} more dependencies`"; Section 7, line "Truncate with `… and N more nodes` summary node"; Section 9, example "… and 150 more dependencies"

**Problem:** When BFS truncation occurs at `max_nodes`, the spec requires a summary node with a count N of suppressed nodes. The §9 example implies N = total_transitive_dependencies - max_nodes (200 - 50 = 150). However, the BFS algorithm in §4.4 stops expanding when `max_nodes` is reached — it does not traverse the full graph. Computing N = 150 would require either:
- A full BFS pass (just to count), which defeats the purpose of `max_nodes` as a performance bound
- The caller providing total node count, which is not in the interface contract

Additionally, §4.4 says "… and {N} more dependencies" while §7 says "… and N more nodes" — inconsistent phrasing.

**Impact:** Implementers must choose between (a) full traversal to compute exact N (expensive for large graphs), (b) reporting N as the number of unexpanded BFS frontier nodes (computable but not equal to total suppressed), or (c) omitting the count entirely ("… and more dependencies"). The §9 example's assertion of "150" would be wrong under option (b).

**Suggested resolution:** Specify that N is the number of nodes remaining in the BFS queue when truncation occurs (i.e., discovered but not expanded frontier nodes). This is computable without full traversal. Update the §9 example to reflect this (N would be the frontier size, not 150). Standardize the phrasing to "… and {N} more" across §4.4 and §7.

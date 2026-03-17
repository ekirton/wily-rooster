# Specification Feedback: MCP Server

**Source:** [specification/mcp-server.md](../mcp-server.md)
**Date:** 2026-03-17
**Reviewer:** TDD test authoring pass

---

## Issue 1: visualize_proof_sequence example assumes in-progress proof produces a ProofTrace

**Severity:** medium
**Location:** Section 4.4, visualize_proof_sequence — second example

**Problem:** The spec example states:

> Given a session with an in-progress proof at step 2
> When visualize_proof_sequence(session_id) is called
> Then the response contains 3 diagrams (initial state + 2 steps observed so far)

The handler "Resolves proof trace: delegates to `session_manager.extract_trace(session_id)`." However, per the proof-types data model (doc/architecture/data-models/proof-types.md), `ProofTrace.total_steps` is a "positive integer, Required" — not nullable. For an interactive session where the proof is being constructed (no original script, `Session.total_steps` is null), `extract_trace` would need to produce a ProofTrace with `total_steps` set to the current step count. But the proof-session spec (specification/proof-session.md §4.3) defines `extract_proof_trace` as replaying the original script to completion — which is undefined for sessions with no original script.

This means the second example cannot work as written: calling `extract_trace` on an in-progress interactive session either fails or produces behavior not covered by the proof-session spec.

**Impact:** Tests cannot be written for this example without assumptions about how partial traces are obtained. The visualization handler may need to build a partial trace from the session's step_history directly, bypassing `extract_trace` — but this is not specified.

**Suggested resolution:** Either (a) remove the in-progress proof example and document that `visualize_proof_sequence` requires a completed proof (like `visualize_proof_tree`), or (b) specify that the handler reads `step_history[0..current_step]` directly from the session manager instead of calling `extract_trace`, and constructs a partial ProofTrace with `total_steps = current_step`. Option (b) requires a new session manager operation not currently in the proof-session spec.

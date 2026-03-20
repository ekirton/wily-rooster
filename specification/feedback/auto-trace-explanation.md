# Specification Feedback: auto-trace-explanation

**Source:** [specification/auto-trace-explanation.md](../auto-trace-explanation.md)
**Date:** 2026-03-20
**Reviewer:** implementation phase

---

## Issue 1: §4.6 rule 4 conflicts with wrong_database diagnosis for focused hint queries

**Severity:** medium
**Location:** Section 4.6, rule 4

**Problem:** Rule 4 states: "When `hint_name` is provided and the name does not appear in any retrieved HintDatabase, the component shall return a `NOT_FOUND` error." The retrieved databases are defined by `_parse_consulted_databases(tactic)` — for `auto` this is only `core`. This means a focused query for a hint registered in `arith` with `tactic="auto"` would always raise `NOT_FOUND`, making it impossible to diagnose `wrong_database` — the most common reason a focused hint query is issued.

The test (`TestDiagnoseAuto.test_wrong_database_diagnosis`) expects the component to find `Nat.add_0_r` in `arith` even though `auto` only consults `core`, and classify it as `wrong_database`. This is the useful behavior: the user asks "why didn't auto use Nat.add_0_r?" and the answer is "because it's in arith, not core."

**Impact:** The spec as written prevents the primary use case for focused hint queries. The implementation resolves this by probing well-known databases beyond the consulted set when `hint_name` is provided, raising `NOT_FOUND` only if the hint is not found anywhere.

**Suggested resolution:** Amend rule 4 to: "When `hint_name` is provided, the component shall search all databases available via `hint_inspect` — not just the consulted databases — to locate the hint. If the hint is found in a non-consulted database, it is classified as `wrong_database`. If the hint is not found in any available database, the component shall return a `NOT_FOUND` error."

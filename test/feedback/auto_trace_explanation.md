# Test Feedback: auto_trace_explanation

**Source:** [test/test_auto_trace_explanation.py](../test_auto_trace_explanation.py)
**Date:** 2026-03-20
**Reviewer:** implementation phase

---

## Issue 1: `_import_parser` returns bare function but call sites unpack as 1-tuple

**Severity:** high
**Location:** `_import_parser()` (line 45), called at lines 388, 402, 413, 434, 446, 462, 477, 488, 498, 513, 522, 531, 764, 798, 822, 839, 1431

**Problem:** `_import_parser()` returns `parse_trace` (a bare function), but every call site destructures it as a 1-tuple: `(parse_trace,) = _import_parser()`. Python's `(x,) = y` syntax requires `y` to be iterable. A function object is not iterable, so every call raises `TypeError: cannot unpack non-iterable function object`.

**Impact:** 12 tests in `TestTraceParsing`, 6 tests in `TestFailureDiagnosis`, and 1 test in `TestEdgeCases` cannot pass regardless of implementation correctness. 19 tests total are blocked.

**Suggested resolution:** Change the return statement to return a 1-tuple: `return (parse_trace,)`.

---

## Issue 2: `_import_classifier` returns bare function but call sites unpack as 1-tuple

**Severity:** high
**Location:** `_import_classifier()` (line 51), called at lines 549, 565, 581, 603, 620, 640, 660, 676

**Problem:** Same as Issue 1. `_import_classifier()` returns `classify_hints` directly, but call sites use `(classify_hints,) = _import_classifier()`.

**Impact:** All 8 tests in `TestHintClassification` cannot pass.

**Suggested resolution:** Change the return statement to return a 1-tuple: `return (classify_hints,)`.

---

## Issue 3: `_import_diagnoser` returns bare function but call sites unpack as 1-tuple

**Severity:** high
**Location:** `_import_diagnoser()` (line 57), called at lines 700, 724, 761, 795, 821, 837

**Problem:** Same as Issue 1. `_import_diagnoser()` returns `diagnose_failures` directly, but call sites use `(diagnose_failures,) = _import_diagnoser()`.

**Impact:** All 6 tests in `TestFailureDiagnosis` cannot pass.

**Suggested resolution:** Change the return statement to return a 1-tuple: `return (diagnose_failures,)`.

---

## Issue 4: `test_detects_divergence_auto_vs_eauto` references undefined `VariantComparison`

**Severity:** high
**Location:** `TestVariantComparison.test_detects_divergence_auto_vs_eauto` (line 897)

**Problem:** The test asserts `assert isinstance(result, VariantComparison)` but `VariantComparison` is never imported or assigned in that method's scope. The preceding test (`test_runs_three_variants`) imports it via `T = _import_types(); VariantComparison = T.VariantComparison`, but local variables do not persist across test methods.

**Impact:** This test always fails with `NameError: name 'VariantComparison' is not defined` regardless of implementation.

**Suggested resolution:** Add `T = _import_types(); VariantComparison = T.VariantComparison` at the beginning of the test method.

---

## Issue 5: `test_wrong_database_diagnosis` expects hint lookup across non-consulted databases

**Severity:** high
**Location:** `TestDiagnoseAuto.test_wrong_database_diagnosis` (line 976–998)

**Problem:** The test provides `hint_inspect` with databases `{"core": ..., "arith": ...}` and calls `diagnose_auto` with `tactic="auto"` and `hint_name="Nat.add_0_r"`. The tactic `"auto"` only consults `"core"`, and `Nat.add_0_r` is in `"arith"`. The test expects the diagnosis to find `Nat.add_0_r` and classify it as `wrong_database`, but `diagnose_auto` would need to search beyond the consulted databases to find the hint. The spec (§4.6 rule 4) says: "When `hint_name` is provided and the name does not appear in any retrieved HintDatabase, the component shall return a `NOT_FOUND` error." The retrieved databases are only the consulted ones (`core`), so the spec says to raise `NOT_FOUND`. But the test expects a successful diagnosis with `wrong_database`. The test and spec conflict.

**Impact:** The test cannot be satisfied while following spec §4.6 rule 4 literally. Either the test expectation or the spec rule needs adjustment.

**Suggested resolution:** Amend spec §4.6 rule 4 to: "When `hint_name` is provided, the component shall search all databases available via `hint_inspect`, not just the consulted databases. If the hint is found in a non-consulted database, it is classified as `wrong_database`. If not found in any database, return `NOT_FOUND`."

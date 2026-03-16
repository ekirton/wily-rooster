# Test Feedback Writing Guidelines

## Authority

Test feedback is informed by the authority chain: specifications (`specification/`) → architecture documents (`doc/architecture/`) → data model documents (`doc/architecture/data-models/`). When filing feedback, verify the issue against the specification before reporting it. An apparent test issue may reflect a specification problem — in that case, file specification feedback instead.

**Before writing feedback:** Read the test's corresponding specification document. Confirm whether the test or the spec is the source of the discrepancy.

## Purpose

Feedback documents capture issues, ambiguities, and errors discovered in test files during implementation or code generation. They exist to inform the test author — not to fix the test directly.

## File Naming

One feedback file per test file. Name matches the source (without the `test_` prefix):

```
test/feedback/<name>.md
```

Example: feedback for `test/test_storage.py` goes in `test/feedback/storage.md`.

## Document Structure

```markdown
# Test Feedback: <test file name>

**Source:** [test/<name>.py](../test_<name>.py)
**Date:** <YYYY-MM-DD of last update>
**Reviewer:** <role or context, e.g., "Implementation pass (code generation)">

---

## Issue <N>: <Short descriptive title>

**Severity:** <high | medium | low>
**Test:** <TestClass::test_method (line N)>

**Problem:** <What is wrong. State the conflict precisely — quote the test assertion and the spec formula/contract where helpful.>

**Impact:** <What breaks if this is not resolved. Frame in terms of test correctness: false pass, false failure, blocked implementation.>

**Suggested resolution:** <Concrete recommendation. If multiple options exist, list them with trade-offs.>

---
```

## Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| **Source** | yes | Relative link to the test file this feedback targets. |
| **Date** | yes | Date of last update (absolute, YYYY-MM-DD). Update when issues are added or removed. |
| **Reviewer** | yes | Who or what produced the feedback. |
| **Severity** | yes | `high` = test cannot pass with correct implementation or produces false passes. `medium` = test is fragile or underspecified. `low` = clarity or coverage gap. |
| **Test** | yes | Fully qualified test name and line number. |
| **Problem** | yes | The issue. Be specific: quote the assertion, name the spec section, show the math. |
| **Impact** | yes | What happens if this is not resolved. |
| **Suggested resolution** | yes | At least one concrete fix. |

## Writing Rules

- **One issue per heading.** Do not combine multiple problems into a single issue.
- **Cite the specification.** Every test issue should reference the spec section the test is derived from.
- **Show the math.** When a numeric bound is wrong, include the formula, the substitution, and the correct result.
- **No fixes in feedback files.** Feedback describes what is wrong and suggests a resolution. The test author decides.
- **Remove resolved issues.** When an issue is resolved, delete it from the feedback file. Do not mark it as resolved — remove it entirely.
- **Delete empty feedback files.** When all issues in a feedback file are resolved and removed, delete the file. No empty feedback files.
- **Number issues sequentially.** Renumber after deletions to keep the sequence contiguous.

## Lifecycle

1. **Created** during implementation or code generation when a test problem is found.
2. **Read** by the test author during the next test revision pass.
3. **Issues removed** as the test author resolves them in the test file.
4. **File deleted** when all issues are resolved (no empty feedback files).

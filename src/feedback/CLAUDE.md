# Implementation Feedback Writing Guidelines

## Authority

Implementation feedback is informed by the authority chain: specifications (`specification/`) → architecture documents (`doc/architecture/`) → data model documents (`doc/architecture/data-models/`). Tests (`test/`) encode the specification contracts and serve as the behavioral authority for implementation. When filing feedback, verify the issue against both the specification and the tests before reporting it.

**Before writing feedback:** Read the implementation file's corresponding specification and test file. Confirm whether the implementation, the test, or the spec is the source of the discrepancy.

## Purpose

Feedback documents capture issues, ambiguities, and errors discovered in implementation files during testing, code review, or integration. They exist to inform the implementer — not to fix the implementation directly.

## File Naming

One feedback file per implementation module. Name matches the source module:

```
src/feedback/<module-path>.md
```

Example: feedback for `src/wily_rooster/channels/mepo.py` goes in `src/feedback/channels-mepo.md`.

## Document Structure

```markdown
# Implementation Feedback: <module name>

**Source:** [src/wily_rooster/<path>.py](../wily_rooster/<path>.py)
**Date:** <YYYY-MM-DD of last update>
**Reviewer:** <role or context, e.g., "Integration testing pass">

---

## Issue <N>: <Short descriptive title>

**Severity:** <high | medium | low>
**Location:** <function or class name (line N)>

**Problem:** <What is wrong. State the conflict precisely — quote the implementation, the spec contract, and/or the failing test where helpful.>

**Impact:** <What breaks if this is not resolved. Frame in terms of correctness: test failure, contract violation, data corruption.>

**Suggested resolution:** <Concrete recommendation. If multiple options exist, list them with trade-offs.>

---
```

## Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| **Source** | yes | Relative link to the implementation file this feedback targets. |
| **Date** | yes | Date of last update (absolute, YYYY-MM-DD). Update when issues are added or removed. |
| **Reviewer** | yes | Who or what produced the feedback. |
| **Severity** | yes | `high` = test fails or contract violated. `medium` = implementation works but diverges from spec intent. `low` = code quality, performance, or clarity. |
| **Location** | yes | Function or class name and line number. |
| **Problem** | yes | The issue. Be specific: quote the code, name the spec section, cite the failing test. |
| **Impact** | yes | What happens if this is not resolved. |
| **Suggested resolution** | yes | At least one concrete fix. |

## Writing Rules

- **One issue per heading.** Do not combine multiple problems into a single issue.
- **Cite the specification and test.** Every implementation issue should reference the spec section and/or test the implementation is expected to satisfy.
- **No fixes in feedback files.** Feedback describes what is wrong and suggests a resolution. The implementer decides.
- **Remove resolved issues.** When an issue is resolved, delete it from the feedback file. Do not mark it as resolved — remove it entirely.
- **Delete empty feedback files.** When all issues in a feedback file are resolved and removed, delete the file. No empty feedback files.
- **Number issues sequentially.** Renumber after deletions to keep the sequence contiguous.

## Resolving Feedback

When asked to resolve a feedback file, follow this workflow for each issue:

1. **Read the feedback issue.** Understand the claimed problem, the affected code, and the suggested resolution.
2. **Read the upstream authority.** Read the specification and test file that the implementation is derived from. Identify the authoritative definition for the expected behavior.
3. **Determine the root cause:**
   - **Implementation is wrong:** The code conflicts with the specification or fails a test. The spec and test are correct. Fix the implementation. Run the tests to verify they pass.
   - **Test is wrong:** The implementation matches the specification but a test has an incorrect assertion. Do not change the test. Instead, file detailed feedback in `test/feedback/` following the standards in `test/feedback/CLAUDE.md`.
   - **Specification is wrong:** The implementation and test agree, but the specification is ambiguous or contradictory. Do not change the specification. Instead, file detailed feedback in `specification/feedback/` following the standards in `specification/feedback/CLAUDE.md`.
4. **Remove the resolved issue** from the feedback file. Do not mark it as resolved — delete it entirely.
5. **Delete the feedback file** if all issues have been removed. No empty feedback files.

## Lifecycle

1. **Created** during testing, code review, or integration when an implementation problem is found.
2. **Read** by the implementer during the next implementation pass.
3. **Issues resolved** by fixing the implementation or escalating to the upstream layer's feedback folder.
4. **Issues removed** from the feedback file after resolution. Do not mark as resolved — delete entirely.
5. **File deleted** when all issues are resolved and removed (no empty feedback files).

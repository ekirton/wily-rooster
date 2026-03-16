## User Story Documents

**Layer:** 2 — Behavioral Specification

**Location:** `doc/requirements/stories/<feature-or-epic>.md`

**When writing or editing user stories:**

- Open each document with a `Derived from` pointer to the PRD it traces to. Stories are derived from PRDs (Layer 1), never from architecture or design documents.
- Use concrete values in acceptance criteria, not placeholders.
- Stories are consumed by the LLM spec-extraction pipeline as a source of behavioral requirements and test assertions.

**Story structure:**
```
### N.M Story Title

**As a** [role],
**I want to** [goal],
**so that** [benefit].

**Priority:** P0 | P1 | P2 | P3
**Stability:** Stable | Draft | Volatile

**Acceptance criteria:**
- GIVEN [precondition] WHEN [action] THEN [expected outcome]
```

**Priority levels:** P0 = must-have, P1 = should-have, P2 = nice-to-have, P3 = future consideration

**Stability indicators:** Stable = unlikely to change, Draft = details may evolve, Volatile = expected to change

**One per:** feature, epic, or cohesive group of related stories

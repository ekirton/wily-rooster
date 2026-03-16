### User Story Documents

**Layer:** 2 — Behavioral Specification

**Location:** `doc/requirements/stories/<feature-or-epic>.md`

**Purpose:** Captures requirements from the user's perspective using the "As a [role], I want [goal], so that [benefit]" format, paired with structured acceptance criteria in GIVEN/WHEN/THEN form. User stories bridge stakeholder intent (PRDs) and feature specification (feature documents) by expressing requirements in a format that is both human-readable and mechanically translatable to test assertions.

**Authoritative for:**
- User role, goal, and motivation for each requirement
- Acceptance criteria in GIVEN/WHEN/THEN format with concrete values
- Priority classification (P0–P3) and stability indicator
- Scope of each story (what it includes and explicitly excludes)

**Derivation:** Each story document opens with a `Derived from` pointer to the PRD it traces to. Stories are derived from PRDs (Layer 1), never from architecture or design documents.

**Structure:** Stories are grouped into epics. Each story follows:
```
### N.M Story Title

**As a** [role],
**I want to** [goal],
**so that** [benefit].

**Priority:** P0 | P1 | P2 | P3
**Stability:** Stable | Draft | Volatile

**Acceptance criteria:**
- GIVEN [precondition] WHEN [action] THEN [expected outcome]
- GIVEN [precondition] WHEN [action] THEN [expected outcome]
```

The user story sentence uses bold for the common phrases (**As a**, **I want to**, **so that**) and each clause appears on its own line. This keeps stories scannable and visually consistent.

**Priority levels:**
- **P0**: Must have — required for the initiative to deliver value
- **P1**: Should have — significantly improves the product but not blocking
- **P2**: Nice to have — desirable but deferrable
- **P3**: Future consideration — captured for completeness, not planned

**Stability indicators:**
- **Stable**: Requirements are well-understood and unlikely to change
- **Draft**: Requirements are directionally correct but details may evolve
- **Volatile**: Requirements are expected to change as design progresses

**Relationship to other types:** User stories are derived from PRDs and feed into feature documents. Each feature document addresses one or more user stories; the feature document provides design rationale while the user story provides testable acceptance criteria. User stories are consumed by the LLM spec-extraction pipeline as a source of behavioral requirements and test assertions. Task breakdown documents organize implementation work by user story.

**One per:** feature, epic, or cohesive group of related stories

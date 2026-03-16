# Before You Start

Read `component-boundaries.md` for the system-level boundary graph and dependency map. This tells you which components exist and how they relate.

## Architecture Documents (Component Specifications)

**Layer:** 3 — Design Specification

**Location:** `doc/architecture/<component-or-concern>.md`

**When writing or editing architecture documents:**

- Follow the specification document structure from `specification/CLAUDE.md` (Purpose, Scope, Definitions, Behavioral Requirements, Data Model, Interface Contracts, State and Lifecycle, Error Specification, NFRs, Examples, Language-Specific Notes). Omit empty sections for small components.
- Open each document with a pointer to the corresponding feature document in `doc/features/`.
- Describe **how** a feature is implemented at the design level — pipelines, data flows, component responsibilities, boundary contracts. Do not re-state **what** the feature does (that belongs in the feature document).
- Keep content language-agnostic. If a platform migration would invalidate a statement, move it to Language-Specific Notes.
- Declare component boundaries and inter-component contracts explicitly — these are the primary input to the LLM spec-extraction pipeline that produces `specification/` artifacts.

**One per:** component, pipeline, or cross-cutting concern

## Component Boundary Document

**Location:** `doc/architecture/component-boundaries.md` (singleton)

- This is a **summary derived from** architecture documents — not a source of truth for boundary design.
- When this document and an architecture document disagree, the architecture document wins.
- Maintain: component taxonomy, dependency graph, boundary contracts (direction + guarantees), and source-to-specification mapping.

## Data Model Documents

**Location:** `doc/architecture/data-models/<domain-or-component>.md`

- Extract a standalone data model document when entities are shared across multiple components or are complex enough to warrant it.
- Define entities with domain-level types, all constraints, validation rules, and relationships with cardinality.
- When an entity appears in both a data model document and an architecture document, the data model document is authoritative for structure; the architecture document is authoritative for usage.

## Task Breakdown Documents

**Layer:** 4 — Implementation Specification

**Location:** `tasks/<feature-or-story>.md`

**When generating task breakdowns:**

- Decompose from architecture documents and user story documents — not from feature documents or PRDs directly.
- Scope each task to a single implementable unit (file, module, or function).
- Trace every task to a specific requirement or acceptance criterion.
- Record any decomposition decisions you made **beyond** what the Layer 3 spec prescribed — surface these to the architect.
- Tasks are disposable LLM artifacts. They are regenerated when upstream specs change.

**Task structure:**
```
- [ ] **Task name** — Brief description
  - **Traces to:** [story or requirement reference]
  - **Depends on:** [prior task references, if any]
  - **Produces:** [files or modules]
  - **Done when:** [completion criteria]
```

**One per:** feature, user story, or cohesive implementation unit

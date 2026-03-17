# Proof Interaction Protocol for Coq/Rocq — Product Requirements Document

Cross-reference: see [coq-ecosystem-gaps.md](coq-ecosystem-gaps.md) for ecosystem context and initiative sequencing.

## 1. Business Goals

Deliver a programmatic proof interaction protocol for Coq/Rocq, exposed via the existing MCP server for Claude Code. Provides standalone value to tool builders and AI researchers; establishes the interaction infrastructure required by Training Data Extraction and LLM Copilot initiatives.

The critical ecosystem gap: no standardized protocol for external tools to observe and interact with Coq proof states. Lean has LeanDojo v2 with proof states at every step, premise annotations, and a gym-like environment. Coq has SerAPI (version-locked, not ML-pipeline friendly) and coq-lsp (IDE-focused). Neither provides a version-stable, external-tool-friendly interaction protocol.

**Success metrics:**
- Correctly extract proof states for ≥ 95% of proofs in the Coq standard library
- Tactic submission round-trip latency < 2 seconds per step
- Premise annotations match ground truth on a hand-curated set of ≥ 50 proofs
- ≥ 3 concurrent proof sessions without state interference

---

## 2. Target Users

| Segment | Needs | Priority |
|---------|-------|----------|
| AI researchers | Extract proof traces and premise annotations for training data | Primary |
| Tool builders | Programmatic proof state observation and tactic submission | Primary |
| Coq developers using Claude Code | Interactive proof exploration within conversational workflow | Secondary |

---

## 3. Competitive Context

**Lean ecosystem (comparative baseline):**
- LeanDojo v2: proof states at every step, premise annotations, gym-like environment, 122K+ theorems
- Standardized interaction model for ML pipelines

**Coq ecosystem (current state):**
- SerAPI: version-locked to specific Coq releases, not ML-pipeline friendly
- coq-lsp: IDE-focused, not designed for external tool interaction
- No standardized, version-stable protocol for external tools to interact with Coq proof states

---

## 4. Requirement Pool

### P0 — Must Have

| ID | Requirement |
|----|-------------|
| R2-P0-1 | Start an interactive proof session by loading a .v file and positioning at a named proof |
| R2-P0-2 | Observe the current proof state including goals, hypotheses, and local context |
| R2-P0-3 | Submit a single tactic and receive the resulting proof state or a structured error |
| R2-P0-4 | Step backward to a previous proof state within the current session |
| R2-P0-5 | Extract the full proof state at each tactic step of an existing completed proof |
| R2-P0-6 | Extract premise annotations for each tactic step, identifying which lemmas and hypotheses the tactic used |
| R2-P0-7 | Expose proof interaction tools via the MCP server compatible with Claude Code (stdio transport) |
| R2-P0-8 | Support multiple concurrent proof sessions with independent state |
| R2-P0-9 | Serialize proof states in a version-stable JSON format with a declared schema version |
| R2-P0-10 | Terminate a proof session and release all associated resources |
| R2-P0-11 | Return structured errors when tactics fail, including the Coq error message and unchanged proof state |
| R2-P0-12 | Return structured errors when a session references a nonexistent proof or file |

### P1 — Should Have

| ID | Requirement |
|----|-------------|
| R2-P1-1 | Incremental tracing: trace changes without reprocessing the entire project |
| R2-P1-2 | Submit a batch of tactics in a single request, receiving state after each step |
| R2-P1-3 | Compute a proof state diff showing what changed between consecutive tactic steps |

### P2 — Nice to Have

| ID | Requirement |
|----|-------------|
| R2-P2-1 | Export proof traces in a training-data format (JSON Lines with standardized fields) |
| R2-P2-2 | Generate benchmark datasets from indexed Coq projects |

---

## 5. Scope Boundaries

**In scope:**
- Interactive proof session management via MCP server (stdio transport, combined with search tools)
- Proof state observation and tactic submission
- Premise annotation extraction for completed proofs
- Proof trace serialization in version-stable JSON format

**Out of scope:**
- Real-time tactic auto-completion or suggestion
- Proof synthesis or automated theorem proving
- Neural premise selection
- Training data export in specialized ML formats (deferred to P2)

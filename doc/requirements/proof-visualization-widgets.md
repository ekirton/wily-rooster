# Proof Visualization Widgets for Coq/Rocq — Product Requirements Document

Cross-reference: see [coq-ecosystem-gaps.md](coq-ecosystem-gaps.md) for ecosystem context and initiative sequencing.

## 1. Business Goals

Coq/Rocq proof developments are opaque to anyone who cannot read raw proof state text. Educators struggle to convey proof structure to students, formalization developers lose time navigating complex proof trees mentally, and AI-assisted workflows lack a visual feedback channel for proof progress. The Lean ecosystem solved this with ProofWidgets4, an extensible widget system embedded in the IDE. Coq has no equivalent — visualization is limited to Alectryon's static HTML and coq-dpdgraph's dependency graphs.

This initiative delivers proof visualization as a set of MCP tools that render proof states, proof trees, and dependency subgraphs as Mermaid diagrams. By targeting MCP rather than a specific IDE, visualizations are available to any MCP-capable client — including Claude Code, web interfaces, and future IDE integrations. Mermaid provides a portable, text-based diagramming format that renders in browsers, Markdown previews, and dedicated rendering services without custom frontend code.

The result is that educators, formalization developers, and AI-assisted proof workflows gain structured visual representations of proof activity without requiring a specific IDE or custom rendering infrastructure.

**Success metrics:**
- Render proof state diagrams (goals, hypotheses, local context) for ≥ 90% of standard Coq tactic proof states
- Render proof tree diagrams for completed proofs with ≥ 5 tactic steps
- Mermaid diagram generation latency < 2 seconds per proof state on a standard development machine
- Successful rendering of proof structures from the Coq standard library and MathComp
- At least two MCP-capable clients can consume and display the generated diagrams

---

## 2. Target Users

| Segment | Needs | Priority |
|---------|-------|----------|
| Educators teaching formal verification | Visual proof trees and goal state diagrams to explain proof structure and tactic effects to students | Primary |
| Formalization developers using Claude Code | Visual feedback on proof progress, dependency context, and proof tree shape during AI-assisted proof development | Primary |
| AI researchers studying proof strategies | Visual representations of proof traces for analysis, comparison, and presentation of proof search behavior | Secondary |
| Coq library maintainers | Dependency subgraph visualizations to understand and communicate cross-module proof relationships | Tertiary |

---

## 3. Competitive Context

Cross-references:
- [Coq ecosystem tooling survey](../background/coq-ecosystem-tooling.md)
- [AI-assisted theorem proving survey](../background/coq-ai-theorem-proving.md)

**Lean ecosystem (comparative baseline):**
- ProofWidgets4: library authors embed arbitrary React components in the Lean Infoview — diagrams, plots, custom mathematical structure visualizations. User Widgets API is a first-class Lean feature. Library-specific visualizations activate automatically based on types, tactics, or proof states.
- Tight coupling to VS Code Infoview panel — visualizations are IDE-bound.

**Coq ecosystem (current state):**
- Alectryon: produces static interactive HTML interleaving proof states with proof scripts. Useful for documentation, not for live proof development.
- coq-dpdgraph: extracts dependency graphs between Coq objects; outputs Graphviz files. Niche tool, not integrated into proof workflows.
- No mechanism for Coq library authors to extend IDE display with custom visualizations.
- No visual representation of proof trees, tactic effects, or goal evolution during proof development.

**Key differentiator of MCP + Mermaid approach:**
- Client-agnostic: any MCP-capable tool can consume visualizations, not locked to a single IDE
- No custom frontend code: Mermaid is a widely supported text-based diagram format
- Composable with AI workflows: Claude Code and other LLM clients can request and display visualizations as part of proof assistance conversations
- Lower barrier to adoption: no VS Code extension installation, no React build toolchain

---

## 4. Requirement Pool

### P0 — Must Have

| ID | Requirement |
|----|-------------|
| R4-P0-1 | Expose an MCP tool that accepts a proof state (goals, hypotheses, local context) and returns a Mermaid diagram rendering that state |
| R4-P0-2 | Expose an MCP tool that accepts a completed proof trace (sequence of tactic steps with proof states) and returns a Mermaid diagram of the proof tree |
| R4-P0-3 | Proof state diagrams must display: goal type, hypothesis names and types, and local context bindings, with clear visual grouping |
| R4-P0-4 | Proof tree diagrams must display: tactic applications as edges, subgoals as nodes, and discharged goals as visually distinct from open goals |
| R4-P0-5 | Generated Mermaid syntax must be valid and render without errors in the Mermaid Chart MCP rendering service |
| R4-P0-6 | Expose an MCP tool that accepts a theorem name and returns a Mermaid diagram of its dependency subgraph (which lemmas, definitions, and axioms the proof depends on) |
| R4-P0-7 | All visualization MCP tools must accept structured input (JSON) and return Mermaid diagram text as output |
| R4-P0-8 | Diagram generation must complete in under 2 seconds per proof state on a standard development machine |
| R4-P0-9 | Support proof states produced by standard Ltac tactics and ssreflect tactics |

### P1 — Should Have

| ID | Requirement |
|----|-------------|
| R4-P1-1 | Expose an MCP tool that accepts a proof trace and returns a sequence of Mermaid diagrams showing proof state evolution step by step |
| R4-P1-2 | Proof state evolution diagrams must visually highlight what changed between consecutive tactic steps (new hypotheses, modified goals, discharged subgoals) |
| R4-P1-3 | Support configurable diagram detail level: summary (goal count and top-level structure only), standard (goals and hypotheses), and detailed (full context with types expanded) |
| R4-P1-4 | Dependency subgraph diagrams must support depth limiting to control diagram complexity for deeply nested dependency chains |
| R4-P1-5 | Diagram layout must remain readable for proofs with up to 50 tactic steps and dependency graphs with up to 100 nodes |

### P2 — Nice to Have

| ID | Requirement |
|----|-------------|
| R4-P2-1 | Support rendering diagrams as SVG or PNG via the Mermaid rendering service for embedding in documents and presentations |
| R4-P2-2 | Support side-by-side comparison diagrams showing two proof states or two proof approaches for the same theorem |
| R4-P2-3 | Generate diagram annotations with natural language summaries of tactic effects (e.g., "intro H splits the conjunction into two subgoals") |
| R4-P2-4 | Support custom color themes for diagrams to accommodate accessibility needs and presentation contexts |

---

## 5. Scope Boundaries

**In scope:**
- MCP tools that generate Mermaid diagram syntax from structured proof data
- Proof state visualization (goals, hypotheses, local context)
- Proof tree visualization (tactic steps, subgoal structure)
- Theorem dependency subgraph visualization
- Step-by-step proof evolution diagrams
- Rendering via the Mermaid Chart MCP service

**Out of scope:**
- VS Code extension or Infoview panel integration
- React widgets or custom frontend components
- Real-time IDE proof state tracking (visualization is request-driven, not live)
- Custom rendering engines or diagram formats beyond Mermaid
- Proof editing or tactic suggestion (this initiative is read-only visualization)
- Visualization of proof terms or Gallina expressions (focus is on tactic-level proof structure)
- Interactive diagram manipulation (pan, zoom, collapse — these are client rendering concerns)

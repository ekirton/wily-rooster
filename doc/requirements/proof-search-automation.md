# Proof Search & Automation for Coq/Rocq — Product Requirements Document

Cross-reference: see [coq-ecosystem-gaps.md](coq-ecosystem-gaps.md) for ecosystem context and initiative sequencing.

Lineage: Depends on Proof Interaction Protocol and Training Data Extraction. Optionally consumes Semantic Lemma Search for premise-augmented candidate generation.

## 1. Business Goals

Claude Code, combined with the Proof Interaction Protocol and Semantic Lemma Search, already functions as an LLM copilot for Coq/Rocq: it observes proof states, reasons about tactic choices, retrieves relevant lemmas, explains proof strategies, and submits tactics — all within the conversational workflow. What Claude Code cannot do efficiently is *algorithmic proof search*: exploring a tree of tactic sequences with systematic backtracking, state caching, and diversity pruning in a tight loop. A conversational round-trip takes seconds per tactic; a dedicated search tool can evaluate hundreds of candidates in the same time.

This initiative delivers proof search and automation tools that Claude Code orchestrates via MCP. These tools handle the computationally intensive, algorithmic aspects of proof automation — tree search, batch admit filling, and few-shot context retrieval — while Claude Code continues to handle the reasoning-intensive aspects: strategy selection, tactic explanation, and interactive proof guidance.

**What this initiative does not do:** It does not build a separate tactic suggestion pipeline (Claude Code reasons about tactics natively), a separate premise selection tool (Semantic Lemma Search already provides this), or tactic explanations (Claude Code generates these naturally). These capabilities already exist in the system; duplicating them would add maintenance burden without user value.

**Success metrics:**
- ≥ 15% of proof search attempts produce a complete, Coq-verified proof for standard library–level goals
- Proof search explores ≥ 50 unique proof states per second (search throughput)
- Proof search latency < 30 seconds per attempt for proofs up to 10 tactic steps
- Fill-admits mode successfully discharges ≥ 25% of `admit` calls in a test corpus of partially complete proofs
- Users report measurable reduction in time spent on routine proof obligations in qualitative evaluation

---

## 2. Target Users

| Segment | Needs | Priority |
|---------|-------|----------|
| Coq developers using Claude Code | Automated discharge of proof obligations that Claude Code can invoke on their behalf during conversational proof development | Primary |
| Coq developers with partially complete proofs | Batch filling of `admit` placeholders without manual intervention | Primary |
| AI researchers | Evaluation platform for proof search strategies and tactic generation models targeting Coq | Secondary |

---

## 3. Competitive Context

Cross-references:
- [AI-assisted theorem proving survey](../background/coq-ai-theorem-proving.md)
- [Premise selection and retrieval survey](../background/coq-premise-retrieval.md)
- [Coq ecosystem tooling survey](../background/coq-ecosystem-tooling.md)

**Lean ecosystem (comparative baseline):**
- LeanCopilot `search_proof`: multi-step proof search with verification, invocable from Lean code.
- AlphaProof, Seed-Prover, DeepSeek-Prover, BFS-Prover: Frontier proof search systems demonstrating best-first search, neuro-symbolic hybridization, and subgoal decomposition (all Lean-only).

**Coq ecosystem (current state):**
- CoqHammer + `sauto`: Mature symbolic automation but no LLM integration, no neural candidate generation, no tree search over LLM-generated tactics.
- Tactician (Graph2Tac): GNN-based tactic prediction with tree search. Architecturally sophisticated but niche adoption; the GNN is trained on Coq-specific data.
- CoqPilot: Collects `admit` holes and generates completions, but no systematic search with backtracking.
- AutoRocq: LLM agent for autonomous proving. Research prototype.
- No tool combines LLM-generated tactic candidates with systematic tree search and Coq verification in a tight loop.

**Key research findings informing design:**
- Best-first search with a strong policy model outperforms MCTS without requiring a separate value model (BFS-Prover), simplifying the search architecture
- Neuro-symbolic hybridization (LLM tactics interleaved with symbolic solvers) is the dominant pattern in frontier systems
- Diversity-aware tactic selection avoids near-duplicate exploration, improving search efficiency (CARTS, 3D-Prover)
- CoqHammer + Tactician combined solve 56.7% of theorems, showing strong complementarity between symbolic automation and learned tactics
- Explicit retrieval provides ~12pp improvement even for large LLMs (REAL-Prover), motivating premise-augmented candidate generation during search

---

## 4. Requirement Pool

### P0 — Must Have

| ID | Requirement |
|----|-------------|
| R4-P0-1 | Given a proof session and current proof state, execute a best-first tree search over tactic candidates, verifying each candidate against Coq via the Proof Interaction Protocol before expanding further |
| R4-P0-2 | Return the verified proof script when search succeeds, including each tactic and the proof state after each step |
| R4-P0-3 | Report structured failure information when search does not find a complete proof, including the deepest partial proof achieved and the number of states explored |
| R4-P0-4 | Expose proof search as an MCP tool compatible with Claude Code (stdio transport) |
| R4-P0-5 | Proof search timeout configurable by the user, with a default of 30 seconds |
| R4-P0-6 | Cache explored proof states during search to detect and prune duplicate states reached by different tactic sequences |
| R4-P0-7 | Generate tactic candidates using Claude, conditioned on the current proof state, local context, and any retrieved premises |
| R4-P0-8 | When Semantic Lemma Search is available, retrieve relevant premises for the current goal and include them in the tactic generation prompt |
| R4-P0-9 | When Semantic Lemma Search is not available, generate tactic candidates using only the proof state and local context |
| R4-P0-10 | Operate without a GPU; use hosted LLM APIs (Claude) for tactic candidate generation |

### P1 — Should Have

| ID | Requirement |
|----|-------------|
| R4-P1-1 | Interleave LLM-generated tactic candidates with symbolic automation tactics (CoqHammer, `auto`, `omega`, `lia`) at each search node, so that mechanical sub-goals are discharged by solvers rather than consuming LLM budget |
| R4-P1-2 | Apply diversity-aware candidate selection during search to filter or de-prioritize near-duplicate tactic candidates before verification |
| R4-P1-3 | Support configurable search depth and breadth limits (maximum tactic sequence length, maximum candidates per node) |
| R4-P1-4 | Retrieve similar proof states and their successful tactics from extracted training data and include them as few-shot context for tactic candidate generation |
| R4-P1-5 | Provide a fill-admits tool that, given a proof script file, identifies all `admit` calls, invokes proof search on each, and returns the script with successfully filled admits replaced by verified tactic sequences |
| R4-P1-6 | Expose fill-admits as an MCP tool compatible with Claude Code (stdio transport) |
| R4-P1-7 | Support sketch-then-prove: accept a proof script with `admit` stubs as intermediate subgoals, invoke proof search independently on each stub, and return the combined result |

### P2 — Nice to Have

| ID | Requirement |
|----|-------------|
| R4-P2-1 | Support pluggable tactic candidate generation backends beyond Claude (e.g., open-source models for offline search) |
| R4-P2-2 | Estimate proof difficulty and remaining proof distance for a given goal to inform search budget allocation |
| R4-P2-3 | Support subgoal decomposition: break a complex goal into a sequence of intermediate subgoals and search each independently |
| R4-P2-4 | Collect search telemetry (states explored, time per candidate, success rate by tactic type) to enable analysis and improvement of search strategies |

---

## 5. Scope Boundaries

**In scope:**
- Algorithmic best-first proof search over LLM-generated and solver tactic candidates, with Coq verification
- MCP tool exposure for Claude Code integration (stdio transport)
- Premise-augmented candidate generation using Semantic Lemma Search when available
- Few-shot context retrieval from extracted training data
- Fill-admits batch automation
- Search strategy configuration (depth, breadth, timeout, diversity)

**Out of scope:**
- Tactic suggestion as a standalone tool (Claude Code reasons about tactics natively using the Proof Interaction Protocol)
- Premise selection as a standalone tool (Semantic Lemma Search already provides this)
- Natural-language tactic explanations as a tool feature (Claude Code generates these naturally)
- Training or fine-tuning ML models (this initiative consumes models, it does not train them)
- IDE plugin development (VS Code, Emacs, etc.) — tools are accessed via Claude Code's MCP integration
- Custom model hosting infrastructure
- Proof visualization (covered by Proof Visualization Widgets initiative)

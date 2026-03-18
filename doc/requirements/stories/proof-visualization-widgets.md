# User Stories: Proof Visualization Widgets

Derived from [doc/requirements/proof-visualization-widgets.md](../proof-visualization-widgets.md).

---

## Epic 1: Proof State Visualization

### 1.1 Render Current Proof State as a Diagram

**As an** educator teaching formal verification,
**I want to** request a visual diagram of the current proof state showing goals, hypotheses, and local context,
**so that** I can show students the structure of what remains to be proved and what assumptions are available.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a proof state with 2 goals and 3 hypotheses WHEN the proof state visualization MCP tool is called with this state THEN it returns valid Mermaid syntax that renders a diagram showing both goals and all 3 hypotheses with their types
- GIVEN a proof state with local context bindings (let-bound variables) WHEN the visualization tool is called THEN the diagram includes the local bindings visually grouped with the hypotheses
- GIVEN a proof state from an ssreflect tactic step WHEN the visualization tool is called THEN it renders correctly, not only standard Ltac states

**Traces to:** R4-P0-1, R4-P0-3, R4-P0-9

### 1.2 Validate Mermaid Output Against Rendering Service

**As a** formalization developer using Claude Code,
**I want** generated diagrams to render without errors in the Mermaid Chart MCP service,
**so that** I can see the visualization immediately without debugging diagram syntax.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a proof state visualization produced by the MCP tool WHEN the Mermaid syntax is submitted to the Mermaid Chart MCP rendering service THEN it renders without syntax errors
- GIVEN a proof state with special characters in hypothesis names or goal types (e.g., subscripts, primes, Unicode) WHEN the visualization tool generates Mermaid syntax THEN special characters are escaped or transliterated so rendering succeeds

**Traces to:** R4-P0-5, R4-P0-7

### 1.3 Receive Diagrams Within Latency Target

**As a** formalization developer,
**I want** proof state diagrams to be generated in under 2 seconds,
**so that** visualization does not interrupt my proof development workflow.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a proof state with up to 10 goals and 20 hypotheses WHEN the visualization MCP tool is called THEN the Mermaid diagram text is returned in under 2 seconds on a standard development machine
- GIVEN a proof state from a MathComp proof with ssreflect-heavy context WHEN the visualization tool is called THEN it completes within the same 2-second latency target

**Traces to:** R4-P0-8

---

## Epic 2: Proof Tree Visualization

### 2.1 Render Proof Tree for a Completed Proof

**As an** educator,
**I want to** see a completed proof rendered as a tree diagram showing how tactics produced and discharged subgoals,
**so that** I can explain the overall proof strategy to students visually.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a completed proof trace with 8 tactic steps WHEN the proof tree visualization MCP tool is called THEN it returns valid Mermaid syntax showing tactic applications as edges and subgoals as nodes
- GIVEN a proof tree where 3 of 5 subgoals are discharged WHEN the diagram is rendered THEN discharged goals are visually distinct from open goals (e.g., different node style or color)
- GIVEN a proof that uses nested tactic combinators (e.g., `split; [apply H1 | apply H2]`) WHEN the proof tree is rendered THEN branching structure is correctly represented

**Traces to:** R4-P0-2, R4-P0-4, R4-P0-5

### 2.2 Render Proof Trees for Standard Library Proofs

**As an** AI researcher studying proof strategies,
**I want to** generate proof tree diagrams for proofs in the Coq standard library,
**so that** I can visually analyze and compare proof structures across the library.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a completed proof trace from a Coq standard library theorem with at least 5 tactic steps WHEN the proof tree tool is called THEN it produces a valid, renderable Mermaid diagram
- GIVEN proof traces from 10 distinct standard library theorems WHEN proof tree diagrams are generated for each THEN at least 9 out of 10 render successfully

**Traces to:** R4-P0-2, R4-P0-9

---

## Epic 3: Dependency Visualization

### 3.1 Render Dependency Subgraph for a Theorem

**As a** formalization developer,
**I want to** see a diagram of which lemmas, definitions, and axioms a theorem depends on,
**so that** I can understand the dependency context before modifying or refactoring a proof.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a theorem that depends on 5 lemmas, 2 definitions, and 1 axiom WHEN the dependency visualization MCP tool is called with the theorem name THEN it returns a Mermaid diagram showing all 8 dependencies with edges from the theorem to each dependency
- GIVEN a dependency that is itself a theorem with its own dependencies WHEN the diagram is rendered THEN transitive dependencies are included up to the configured depth
- GIVEN a theorem name WHEN the dependency tool is called THEN the input is a JSON object containing the theorem name and the output is Mermaid diagram text

**Traces to:** R4-P0-6, R4-P0-7

### 3.2 Limit Dependency Graph Depth

**As a** Coq library maintainer,
**I want to** control how deep the dependency subgraph extends,
**so that** diagrams remain readable for theorems with deeply nested dependency chains.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a theorem with transitive dependencies extending 10 levels deep WHEN the dependency tool is called with a depth limit of 3 THEN only dependencies within 3 hops of the target theorem are included
- GIVEN a dependency graph with 200 transitive nodes WHEN a depth limit of 2 is applied THEN the resulting diagram has no more than 100 nodes and renders readably

**Traces to:** R4-P1-4, R4-P1-5

---

## Epic 4: Proof Sequence Navigation

### 4.1 Generate Step-by-Step Proof Evolution Diagrams

**As an** educator,
**I want to** receive a sequence of diagrams showing how the proof state evolves after each tactic step,
**so that** I can walk students through a proof one step at a time with visual aids.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a proof trace with 6 tactic steps WHEN the proof sequence MCP tool is called THEN it returns 7 Mermaid diagrams (initial state plus one per tactic step)
- GIVEN consecutive proof states in the sequence WHEN the diagrams are compared THEN each diagram reflects the effect of the corresponding tactic (new subgoals introduced, goals discharged, hypotheses added)

**Traces to:** R4-P1-1

### 4.2 Highlight Changes Between Proof Steps

**As a** formalization developer,
**I want** step-by-step diagrams to visually highlight what changed from the previous step,
**so that** I can quickly see the effect of each tactic without comparing diagrams manually.

**Priority:** P1
**Stability:** Draft

**Acceptance criteria:**
- GIVEN two consecutive proof states where a tactic introduced a new hypothesis H WHEN the step diagram is rendered THEN hypothesis H is visually highlighted as new (e.g., distinct styling or annotation)
- GIVEN two consecutive proof states where a tactic discharged a subgoal WHEN the step diagram is rendered THEN the discharged goal is visually marked as resolved
- GIVEN two consecutive proof states where a tactic split a goal into two subgoals WHEN the step diagram is rendered THEN both new subgoals are highlighted as newly introduced

**Traces to:** R4-P1-2

### 4.3 Configure Diagram Detail Level

**As an** educator preparing materials for different audiences,
**I want to** choose between summary, standard, and detailed diagram views,
**so that** I can show simplified proof structure to beginners and full context to advanced students.

**Priority:** P1
**Stability:** Draft

**Acceptance criteria:**
- GIVEN a proof state with 3 goals and 5 hypotheses WHEN the summary detail level is requested THEN the diagram shows goal count and top-level structure only, without listing individual hypotheses
- GIVEN the same proof state WHEN the standard detail level is requested THEN the diagram shows all goals and hypotheses with their names and types
- GIVEN the same proof state WHEN the detailed level is requested THEN the diagram additionally expands type abbreviations and shows full local context

**Traces to:** R4-P1-3

---

## Epic 5: Diagram File Output

### 5.1 Write Rendered Diagram to Project Directory

**As a** formalization developer using Claude Code in a container,
**I want to** have visualization tools write an HTML file I can open in my browser,
**so that** I can see rendered diagrams without configuring a separate viewer or server connection.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a call to `visualize_proof_tree` WHEN the tool returns THEN a file `proof-diagram.html` exists in the project directory containing valid HTML that renders the Mermaid diagram in a browser
- GIVEN the HTML file is opened in a browser without network access to the container THEN the diagram renders (mermaid.js loaded from CDN, no SSE/server dependency)

**Traces to:** R4-P1-6

### 5.2 Multi-Diagram Sequence in Single File

**As an** educator,
**I want** `visualize_proof_sequence` to produce a single HTML file showing all proof steps,
**so that** I can scroll through the full evolution in one page.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a proof trace with 6 tactic steps WHEN `visualize_proof_sequence` is called THEN the HTML file contains 7 rendered diagrams (initial + 6 steps) with step labels
- GIVEN the HTML file WHEN opened in a browser THEN all diagrams render in order with their tactic labels visible

**Traces to:** R4-P1-6, R4-P1-1

### 5.3 Overwrite on Subsequent Calls

**As a** developer,
**I want** subsequent visualization calls to overwrite the same file,
**so that** my project directory doesn't accumulate diagram files.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a previous `proof-diagram.html` exists WHEN a new visualization tool is called THEN the file is overwritten with the new diagram

**Traces to:** R4-P1-6

# User Stories: Semantic Lemma Search

Derived from [doc/requirements/coq-ecosystem-gaps.md](../coq-ecosystem-gaps.md).

---

## Epic 1: Library Indexing

### 1.1 Index the Standard Library

**As a** Coq developer setting up the tool for the first time,
**I want to** index the Coq standard library with a single command,
**so that** I can start searching immediately without manual configuration.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a system with Coq installed WHEN the user runs the indexing command targeting stdlib THEN all declarations are extracted and stored in a single SQLite database file
- GIVEN the indexing command is running WHEN no GPU, external API keys, or network access are available THEN the command completes successfully
- GIVEN the indexing command is running WHEN extraction of an individual declaration fails THEN the error is logged and the remaining declarations continue to be indexed
- GIVEN the indexing completes WHEN the database is inspected THEN it contains declarations, dependencies, symbols, and all data required by the retrieval channels
- GIVEN the indexing completes WHEN the database is inspected THEN it contains a recorded index schema version

### 1.2 Index MathComp

**As a** Coq developer working with MathComp,
**I want to** index the MathComp library alongside the standard library,
**so that** I can search across both libraries in a single query.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a system with MathComp installed WHEN the user runs the indexing command targeting MathComp THEN MathComp declarations are stored in the same database as stdlib declarations
- GIVEN the database contains both stdlib and MathComp WHEN a declaration is inspected THEN it is distinguished by its fully qualified module path
- GIVEN MathComp's nested module structure WHEN declarations are indexed THEN fully qualified names and module membership are recorded correctly

### 1.3 Index a User Project

**As a** Coq developer working on my own project,
**I want to** index my project's declarations alongside library declarations,
**so that** I can search my own lemmas with the same tools.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a user project directory with compiled `.vo` files WHEN the user runs the indexing command targeting that directory THEN project declarations are indexed into the same database as library declarations
- GIVEN a previously indexed user project WHEN the user re-runs the indexing command after modifying some files THEN only changed declarations are updated without rebuilding the entire index

### 1.4 Detect and Rebuild Stale Indexes

**As a** Coq developer who has updated an indexed library,
**I want** the system to detect the update and rebuild the index immediately,
**so that** search results always reflect the current state of my libraries.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN the library's installed version changes THEN the system detects the change before serving any queries
- GIVEN a detected library version change WHEN the MCP server receives a query THEN the index is rebuilt before returning results
- GIVEN a stale index is detected WHEN the rebuild completes THEN the new index replaces the old one atomically

### 1.5 Index Version Compatibility

**As a** Coq developer who has updated the search tool,
**I want** the system to reject incompatible indexes and re-index from scratch,
**so that** I never get incorrect results from an outdated index format.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a database created by a previous tool version WHEN the current tool version opens it THEN it reads the stored index schema version
- GIVEN an index schema version that does not match the current tool version WHEN the MCP server starts THEN it rejects the index and triggers a full re-index from scratch
- GIVEN a re-index is triggered WHEN it completes THEN the new database records the current index schema version

---

## Epic 2: MCP Server and Tool Surface

### 2.1 Start the MCP Server

**As a** Claude Code user,
**I want** the MCP server to start and connect to Claude Code,
**so that** the search tools are available in my conversation.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a valid MCP configuration WHEN the server starts via stdio transport THEN it connects to Claude Code successfully
- GIVEN a connected server WHEN the tool list is requested THEN it exposes all 7 tools: `search_by_name`, `search_by_type`, `search_by_structure`, `search_by_symbols`, `get_lemma`, `find_related`, `list_modules`
- GIVEN a connected server WHEN any tool is called THEN it returns well-formed MCP tool responses with typed `SearchResult` or `LemmaDetail` objects

### 2.2 Search by Name

**As a** Coq developer who partially remembers a lemma name,
**I want to** search for declarations by name pattern,
**so that** I can find lemmas when I know part of their identifier.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `search_by_name` is called with a glob or regex pattern THEN it returns declarations whose fully qualified names match the pattern
- GIVEN matching results WHEN the response is returned THEN each result includes name, statement, type, module, kind, and relevance score
- GIVEN matching results WHEN the response is returned THEN results are ranked by relevance
- GIVEN no limit is specified WHEN results are returned THEN the default limit is 50
- GIVEN a caller-specified limit WHEN results are returned THEN the result count respects the specified limit

### 2.3 Search by Type

**As a** Coq developer who knows the type signature I need,
**I want to** search for declarations whose type matches a pattern,
**so that** I can find lemmas by their logical content.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `search_by_type` is called with a Coq type expression THEN the backend parses the expression and retrieves candidates using multiple retrieval channels
- GIVEN candidates from multiple channels WHEN results are fused THEN items appearing in multiple channels rank higher
- GIVEN fused results WHEN the response is returned THEN each result includes the standard `SearchResult` fields

### 2.4 Search by Structure

**As a** Coq developer (or the LLM on my behalf),
**I want to** find declarations structurally similar to a given expression,
**so that** I can discover lemmas with related logical shapes even when names and symbols differ.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `search_by_structure` is called with a Coq expression string THEN the backend computes structural similarity between the query and indexed declarations
- GIVEN structural similarity scores WHEN results are returned THEN they are ranked by similarity score

### 2.5 Search by Symbols

**As a** Coq developer (or the LLM on my behalf),
**I want to** find declarations that use specific constant/inductive/constructor symbols,
**so that** I can locate lemmas involving particular definitions.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `search_by_symbols` is called with an array of symbol names THEN the backend retrieves declarations containing those symbols
- GIVEN retrieved results WHEN results are ranked THEN rare symbols are weighted more heavily
- GIVEN ranked results WHEN the response is returned THEN results are ordered by relevance score

### 2.6 Get Lemma Details

**As a** Coq developer who found a candidate result,
**I want to** retrieve full details for a specific declaration,
**so that** I can understand its dependencies, dependents, and proof structure.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `get_lemma` is called with a fully qualified declaration name THEN the response includes all `SearchResult` fields plus: dependencies, dependents, proof sketch (if available), symbols list, and node count
- GIVEN a name that does not exist in the index WHEN `get_lemma` is called THEN a clear error message is returned

### 2.7 Find Related Declarations

**As a** Coq developer exploring a neighborhood of the library,
**I want to** navigate the dependency graph from a known declaration,
**so that** I can discover related lemmas by structural relationships.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `find_related` is called with a declaration name and a relation type (`uses`, `used_by`, `same_module`, or `same_typeclass`) THEN results matching the specified relation are returned
- GIVEN no limit is specified WHEN results are returned THEN the default limit is 20
- GIVEN a caller-specified limit WHEN results are returned THEN the result count respects the specified limit
- GIVEN results WHEN the response is returned THEN each result includes the standard `SearchResult` fields

### 2.8 List Modules

**As a** Coq developer browsing library structure,
**I want to** list modules under a given prefix,
**so that** I can orient myself within the library hierarchy.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an indexed library WHEN `list_modules` is called with a module prefix (e.g., `Coq.Arith`, `mathcomp.algebra`) THEN matching module names and their declaration counts are returned
- GIVEN an empty prefix WHEN `list_modules` is called THEN all top-level modules are returned

---

## Epic 3: Retrieval Quality

### 3.1 Multi-Channel Fusion

**As a** user performing a search,
**I want** results to be drawn from multiple retrieval channels and fused,
**so that** I get high recall across different notions of similarity.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a search query WHEN retrieval executes THEN all applicable retrieval channels (structural, symbolic, lexical) are engaged
- GIVEN results from multiple channels WHEN fusion is applied THEN items appearing in multiple channels rank higher than items from a single channel

### 3.2 Recall Target

**As a** project maintainer,
**I want** the retrieval stage to surface the relevant lemma in the top-50 results at least 70% of the time,
**so that** the LLM filtering layer has sufficient candidates to work with.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a hand-curated evaluation set of (query, relevant lemma) pairs from common Coq workflows WHEN the retrieval pipeline is evaluated THEN the system achieves ≥ 70% recall@50
- GIVEN ongoing development WHEN retrieval changes are made THEN recall metrics are tracked and reported

### 3.3 Latency Target

**As a** user in a conversational workflow,
**I want** first-pass retrieval to complete in under 1 second,
**so that** the search feels responsive within the conversation.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN an index of up to 50K declarations WHEN any search tool is called THEN retrieval completes in < 1 second
- GIVEN latency measurement WHEN it is taken THEN it covers end-to-end from MCP tool call receipt to response

---

## Epic 4: Coq-Specific Normalization

### 4.1 Expression Normalization

**As a** developer relying on structural search,
**I want** Coq expressions to be normalized before indexing and comparison,
**so that** surface-level syntactic variation does not obscure structural similarity.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a Coq expression at indexing time WHEN it is stored THEN it is normalized to eliminate surface-level syntactic variation
- GIVEN normalization WHEN applied THEN it handles at minimum: application form, type casts, universe annotations, projections, and notation expansion
- GIVEN a declaration with section-local names WHEN it is indexed THEN names are fully qualified
- GIVEN a query expression at search time WHEN it is processed THEN the same normalization is applied as at indexing time

---

## Epic 5: End-to-End User Experience

### 5.1 Natural Language Lemma Search

**As a** Coq developer using Claude Code,
**I want to** describe what I need in natural language and get a useful, explained result,
**so that** I can find lemmas without knowing exact names, types, or search syntax.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN a user describing a need conversationally (e.g., "find a lemma about commutativity of addition on natural numbers") WHEN the LLM processes the request THEN it formulates one or more tool calls to the MCP server
- GIVEN tool call results WHEN the LLM responds THEN it filters results, selects the most relevant, and explains why each is relevant
- GIVEN the full interaction WHEN the user reads the response THEN they receive a useful answer within one conversational turn

### 5.2 Iterative Refinement

**As a** Coq developer whose initial search didn't find what I need,
**I want** the LLM to reformulate and retry searches automatically,
**so that** I don't have to manually guess different query strategies.

**Priority:** P1
**Stability:** Stable

**Acceptance criteria:**
- GIVEN initial search results that are insufficient WHEN the LLM evaluates them THEN it issues follow-up tool calls with reformulated queries
- GIVEN reformulation WHEN strategies are applied THEN they include: broadening symbol sets, following dependency links, trying different structural patterns, and name pattern variations
- GIVEN refined results WHEN presented to the user THEN the user sees them without needing to re-prompt

---

## Epic 6: Error Handling and Resilience

### 6.1 Missing Index

**As a** Coq developer starting the MCP server for the first time,
**I want** a clear error message when no index database exists,
**so that** I know I need to run the indexing command first.

**Priority:** P0
**Stability:** Stable

**Acceptance criteria:**
- GIVEN no index database at the configured path WHEN the MCP server starts THEN it returns a clear error message indicating the index is missing and how to create it
- GIVEN a missing index WHEN any search tool is called THEN the tool returns an error rather than empty results

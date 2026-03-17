# CLI Search

Standalone command-line access to the same search capabilities exposed by the MCP server, for Coq developers working in a terminal without Claude Code.

**Stories**: [Epic 7: Standalone CLI Search](../requirements/stories/tree-search-mcp.md#epic-7-standalone-cli-search)

---

## Problem

The MCP server requires Claude Code (or another MCP client) to access search results. Coq developers who work in a terminal — scripting, piping results into other tools, or simply preferring the command line — have no way to query the index directly.

## Solution

A set of CLI subcommands that mirror the MCP tool surface: `search-by-name`, `search-by-type`, `search-by-structure`, `search-by-symbols`, `get-lemma`, `find-related`, and `list-modules`. Each command accepts the same logical parameters as its MCP counterpart, queries the same retrieval pipeline, and prints results to stdout.

## Design Rationale

### Why mirror the MCP tools

The MCP tools already represent a well-decomposed, tested API surface. Reusing the same pipeline functions and response types means the CLI is a thin presentation layer — not a second search implementation. Results are identical regardless of whether the query arrives via MCP or CLI.

### Why both human-readable and JSON output

Human-readable output (the default) makes the CLI usable interactively — a developer can scan results at a glance. JSON output (`--json`) makes it composable — results can be piped to `jq`, consumed by scripts, or integrated into CI workflows.

### Why a unified command group

All search commands live under a single entry point (e.g., `poule search-by-name ...`), sharing common options like `--db` and `--json`. This avoids scattering multiple binaries and keeps the interface discoverable via `--help`.

## Scope Boundaries

The CLI is a **presentation layer** over the existing retrieval pipeline. It does not:

- Implement search logic (that is owned by the pipeline)
- Provide interactive or REPL-style search sessions
- Replace the MCP server for Claude Code users
- Support query reformulation or iterative refinement (those are LLM-mediated behaviors)

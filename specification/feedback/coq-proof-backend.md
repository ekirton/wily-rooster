# Feedback: coq-proof-backend.md

## 1. coq-lsp cannot capture vernacular query output

**Severity:** high

**Section:** execute_vernacular (referenced by proof-session.md §4.4)

**Issue:** The spec does not specify which coq-lsp protocol mechanism captures the output of vernacular introspection commands (Print, Check, About, Locate). In practice, coq-lsp:

- Emits LSP diagnostics only for errors and warnings
- Does NOT emit diagnostics for successful Print/Check/About output
- `textDocument/hover` returns type info about identifiers, not command output
- `coq/getDocument` returns span ranges without output content
- No other available endpoint exposes the command result

The current implementation collects diagnostics, which means successful queries always return empty strings.

**Impact:** Any code path that uses `CoqProofBackend.execute_vernacular()` for introspection commands gets empty output. This blocks `coq_query` in proof sessions.

**Workaround implemented:** The session manager now lazily spawns a `coqtop` subprocess (via `_ensure_coqtop`) when `submit_vernacular` is called with `prefer_coqtop=True`. The coqtop process loads the file's imports and handles vernacular queries correctly.

**Suggested resolution:** Add a section to the spec acknowledging that coq-lsp's LSP protocol does not expose vernacular query output, and specify that:
- `execute_vernacular` on the coq-lsp backend is limited to error detection
- Vernacular introspection requiring output capture must route through a coqtop subprocess
- The session manager is responsible for managing this coqtop subprocess lifecycle

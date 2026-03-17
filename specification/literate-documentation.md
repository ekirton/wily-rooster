# Literate Documentation

Alectryon subprocess adapter for interactive proof documentation generation — single-file, proof-scoped, batch, and output customization modes.

**Architecture**: [literate-documentation.md](../doc/architecture/literate-documentation.md), [component-boundaries.md](../doc/architecture/component-boundaries.md)

---

## 1. Purpose

Define the Alectryon Adapter that generates interactive proof documentation from Coq source files by spawning Alectryon as a subprocess — validating inputs, constructing CLI arguments, managing subprocess lifecycle, handling proof-scoped extraction, orchestrating batch generation, and returning structured results or errors.

## 2. Scope

**In scope**: Alectryon availability detection and caching, single-file documentation generation, proof-scoped documentation generation (proof extraction, temporary file management), batch documentation generation (directory enumeration, index page generation), output format selection (HTML, HTML fragment, LaTeX), custom flag passthrough, subprocess timeout enforcement, error classification and reporting.

**Out of scope**: MCP protocol handling (owned by mcp-server), Coq compilation (owned by Alectryon/Coq), Alectryon internals (CLI contract only), Coq project configuration (`_CoqProject`, `COQPATH` — inherited from environment), proof session management (owned by proof-session).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Alectryon | A Python tool that processes Coq source files and generates interactive HTML or LaTeX documentation showing proof states inline |
| Adapter | This component — a subprocess wrapper that translates documentation requests into Alectryon CLI invocations |
| Backend | Alectryon's output mode: `webpage`, `webpage-no-header`, or `latex` |
| Proof-scoped generation | Extracting a single named proof and its compilation context from a `.v` file, then generating documentation for the extract only |
| Sentence boundary | A Coq source position where one vernacular command ends and another begins, identified textually by terminal periods |
| Availability status | Cached state of the Alectryon binary: `available`, `not_installed`, or `version_too_old` |

## 4. Behavioral Requirements

### 4.1 Availability Detection

#### check_availability()

- REQUIRES: Nothing. The adapter has not yet determined Alectryon's presence.
- ENSURES: Executes `alectryon --version` on the system `PATH`. Parses the version string. Caches the result as one of: `available` (version at or above minimum), `not_installed` (binary not found), `version_too_old` (version below minimum). Subsequent calls return the cached result without spawning a process.
- MAINTAINS: The cached status does not change for the lifetime of the server process. No Coq-specific environment variables are set or modified by the adapter.

> **Given** Alectryon is installed at version 1.4.0 and the minimum supported version is 1.3.0
> **When** `check_availability()` is called for the first time
> **Then** the adapter executes `alectryon --version`, parses "1.4.0", caches status as `available`, and returns `available`

> **Given** Alectryon is not installed on the system `PATH`
> **When** `check_availability()` is called
> **Then** the adapter caches status as `not_installed` and all subsequent documentation requests return an `ALECTRYON_NOT_FOUND` error without spawning a process

> **Given** the availability status has already been cached as `available`
> **When** `check_availability()` is called again
> **Then** the cached result is returned without executing any subprocess

### 4.2 Single-File Generation

#### generate_documentation(request: DocumentationRequest) -> DocumentationResult

- REQUIRES: `request.input_file` is an absolute path to an existing `.v` file. `request.format` is one of `"html"`, `"html-fragment"`, `"latex"`. When `request.output_path` is set, its parent directory exists. When `request.output_path` is null, the adapter returns content inline. `request.timeout` is a positive integer or null (default: 120). `request.custom_flags` is a list of strings (may be empty).
- ENSURES: The adapter checks Alectryon availability (cached). Builds the CLI argument list per the argument construction rules. Spawns an Alectryon subprocess with working directory set to the parent directory of the input file. Enforces the timeout. On exit code 0, locates the output file and either moves it to `request.output_path` or reads its content into the result. On non-zero exit code, parses stderr and returns a structured error. Returns a `DocumentationResult`.
- MAINTAINS: The adapter does not modify the input file. The adapter does not set or modify Coq-specific environment variables. Alectryon inherits the server process environment.

**Argument construction**: The adapter shall build the argument list as follows:

| Position | Argument | Source |
|----------|----------|--------|
| 1 | `--frontend coq` | Always: input is a `.v` file |
| 2 | `--backend <backend>` | Mapped from `request.format` (see format mapping table) |
| 3 | `--output-directory <dir>` | Parent of `request.output_path`, or a temporary directory when output is inline |
| 4+ | Custom flags | `request.custom_flags`, passed verbatim |
| Last | `<input_file>` | `request.input_file` (positional) |

**Format mapping**:

| `request.format` | Alectryon `--backend` | Output extension |
|-------------------|-----------------------|------------------|
| `html` | `webpage` | `.html` |
| `html-fragment` | `webpage-no-header` | `.html` |
| `latex` | `latex` | `.tex` |

> **Given** a valid `.v` file at `/project/src/Lemmas.v` with `format = "html"` and no `output_path`
> **When** `generate_documentation(request)` is called
> **Then** the adapter spawns `alectryon --frontend coq --backend webpage --output-directory <tmp> /project/src/Lemmas.v` with working directory `/project/src/`, reads the generated `Lemmas.html` content, and returns a `DocumentationResult` with `status = "success"`, `content` set to the HTML string, and `output_path = null`

> **Given** a valid `.v` file and `output_path = "/docs/Lemmas.html"`
> **When** `generate_documentation(request)` is called and Alectryon exits with code 0
> **Then** the adapter moves the generated file to `/docs/Lemmas.html` and returns a `DocumentationResult` with `output_path = "/docs/Lemmas.html"` and `content = null`

> **Given** a `.v` file containing a Coq syntax error
> **When** `generate_documentation(request)` is called and Alectryon exits with non-zero code
> **Then** the adapter returns a `DocumentationResult` with `status = "failure"` and `error.code = "COQ_ERROR"`

### 4.3 Proof-Scoped Generation

#### generate_proof_documentation(request: DocumentationRequest) -> DocumentationResult

- REQUIRES: `request.proof_name` is a non-null, non-empty string. All other preconditions from §4.2 apply.
- ENSURES: The adapter reads `request.input_file`, scans for a theorem/lemma/definition declaration matching `request.proof_name`, extracts the proof and its compilation context, writes a temporary `.v` file in the same directory as the source file, delegates to single-file generation, cleans up the temporary file (regardless of success or failure), and returns the `DocumentationResult`.
- MAINTAINS: The temporary file is removed after generation completes. The source file is not modified. The temporary file is placed in the same directory as the source file so that relative imports and load paths resolve correctly.

**Proof extraction rules**:

1. The adapter shall scan the source file for declaration keywords (`Theorem`, `Lemma`, `Definition`, `Fixpoint`, `Corollary`, `Proposition`, `Example`, `Fact`, `Remark`) followed by the requested proof name.
2. When a match is found, the adapter shall extract: the declaration statement, the proof body through its terminator (`Qed.`, `Defined.`, `Admitted.`), and any preceding context required for compilation (imports, section variables, local definitions).
3. The extraction is textual — it locates sentence boundaries, not AST nodes.
4. When in doubt about whether a preceding declaration is needed, the adapter shall include it (conservative extraction).

> **Given** a file `/project/src/Arith.v` containing `Lemma add_comm : ...` with proof body
> **When** `generate_proof_documentation(request)` is called with `proof_name = "add_comm"`
> **Then** the adapter extracts the lemma and its context, writes a temporary file `/project/src/.poule_tmp_add_comm.v`, generates documentation from it, removes the temporary file, and returns the result

> **Given** a file that does not contain a proof named `"missing_lemma"`
> **When** `generate_proof_documentation(request)` is called with `proof_name = "missing_lemma"`
> **Then** the adapter returns a `DocumentationResult` with `status = "failure"`, `error.code = "PROOF_NOT_FOUND"`, and the error message lists available proof names

> **Given** a proof that depends on imports and section variables declared earlier in the file
> **When** the adapter extracts the proof
> **Then** the extracted temporary file includes those imports and section variables so that Alectryon can compile the fragment

### 4.4 Batch Generation

#### generate_batch_documentation(request: BatchDocumentationRequest) -> BatchDocumentationResult

- REQUIRES: `request.source_directory` is an absolute path to an existing directory. `request.output_directory` is an absolute path (created if it does not exist). `request.format` is one of `"html"`, `"html-fragment"`, `"latex"`. `request.timeout_per_file` is a positive integer or null (default: 120).
- ENSURES: The adapter checks Alectryon availability. Enumerates all `.v` files in `request.source_directory` recursively. For each `.v` file, computes its relative path from the source root, creates the corresponding subdirectory in the output directory, and invokes single-file generation. A failure in one file does not abort the batch. After all files are processed, generates an `index.html` at the output directory root listing all files with their documentation status (links for successes, error summaries for failures). Returns a `BatchDocumentationResult`.
- MAINTAINS: The output directory mirrors the source directory structure. Each file is processed as an independent subprocess. Cross-file navigation links are generated by the adapter in the index page, not by Alectryon.

> **Given** a source directory `/project/src/` containing `A.v`, `sub/B.v`, and `sub/C.v`
> **When** `generate_batch_documentation(request)` is called with `output_directory = "/docs/"`
> **Then** the adapter generates `/docs/A.html`, `/docs/sub/B.html`, `/docs/sub/C.html`, and `/docs/index.html`; returns a `BatchDocumentationResult` with `total = 3`, `succeeded` + `failed` = 3

> **Given** a batch where `A.v` succeeds and `B.v` has a Coq error
> **When** the batch completes
> **Then** the result contains `succeeded = 1`, `failed = 1`; `B.v`'s `FileOutcome` has `status = "failure"` with the error; `A.v`'s outcome has `status = "success"` with a path to the generated file

> **Given** a source directory containing no `.v` files
> **When** `generate_batch_documentation(request)` is called
> **Then** the adapter returns an error with `code = "NO_INPUT_FILES"` without generating an index page

## 5. Data Model

### DocumentationRequest

| Field | Type | Constraints |
|-------|------|-------------|
| `input_file` | string | Required; absolute path; must have `.v` extension; file must exist |
| `proof_name` | string or null | When non-null, triggers proof-scoped generation; must match a declaration name in the file |
| `output_path` | string or null | When non-null, absolute path where output file is written; parent directory must exist |
| `format` | `"html"` or `"html-fragment"` or `"latex"` | Required; default `"html"` |
| `custom_flags` | list of string | Required; default empty list; passed to Alectryon verbatim |
| `timeout` | positive integer or null | Per-invocation timeout in seconds; default 120 |

### BatchDocumentationRequest

| Field | Type | Constraints |
|-------|------|-------------|
| `source_directory` | string | Required; absolute path; directory must exist |
| `output_directory` | string | Required; absolute path; created if it does not exist |
| `format` | `"html"` or `"html-fragment"` or `"latex"` | Required; default `"html"` |
| `custom_flags` | list of string | Required; default empty list; applied to every file |
| `timeout_per_file` | positive integer or null | Per-file timeout in seconds; default 120 |

### DocumentationResult

| Field | Type | Constraints |
|-------|------|-------------|
| `status` | `"success"` or `"failure"` | Required |
| `output_path` | string or null | Absolute path to generated file; null when content is returned inline or on failure |
| `content` | string or null | Generated content when no `output_path` was specified; null when output was written to disk or on failure |
| `format` | `"html"` or `"html-fragment"` or `"latex"` | Required; format of the generated output |
| `error` | structured error or null | On failure: `code` (string) and `message` (string); null on success |

### BatchDocumentationResult

| Field | Type | Constraints |
|-------|------|-------------|
| `index_path` | string | Required; absolute path to the generated `index.html` |
| `output_directory` | string | Required; absolute path to the output root |
| `results` | list of FileOutcome | Required; one entry per `.v` file enumerated |
| `total` | non-negative integer | Required; count of `.v` files found |
| `succeeded` | non-negative integer | Required; count of successfully documented files |
| `failed` | non-negative integer | Required; `total - succeeded` |

### FileOutcome

| Field | Type | Constraints |
|-------|------|-------------|
| `input_file` | string | Required; absolute path to the source `.v` file |
| `output_file` | string or null | Absolute path to generated file on success; null on failure |
| `status` | `"success"` or `"failure"` | Required |
| `error` | structured error or null | On failure: `code` and `message`; null on success |

All paths in results are absolute.

## 6. Interface Contracts

### Alectryon Adapter → Alectryon CLI (subprocess)

| Property | Value |
|----------|-------|
| Protocol | Subprocess invocation via system `PATH` |
| Input | CLI arguments (see §4.2 argument construction) and a `.v` file |
| Output | Generated file (`.html` or `.tex`) written to the specified output directory; stdout; stderr; exit code |
| Working directory | Parent directory of the input `.v` file |
| Environment | Inherited from server process; adapter does not set or modify variables |
| Timeout | Per-invocation, enforced by the adapter; process killed on expiry |
| Error strategy | Exit code 0 → success. Non-zero → parse stderr for Coq errors (`COQ_ERROR`) or report as `ALECTRYON_ERROR`. |
| Concurrency | Each invocation is an independent subprocess; no shared state between invocations |
| Idempotency | Invocations are idempotent — same input and flags produce the same output file |

### MCP Server → Alectryon Adapter

| Property | Value |
|----------|-------|
| Operations exposed | `generate_documentation`, `generate_proof_documentation`, `generate_batch_documentation` |
| Error strategy | All errors returned as structured `DocumentationResult` or `BatchDocumentationResult` with error codes per §8. Adapter never raises uncaught exceptions to the MCP Server. |
| Concurrency | The MCP Server may invoke the adapter concurrently for independent requests. Each invocation manages its own subprocess. |

## 7. Error Specification

### 7.1 Input Errors

| Condition | Error Code | Message Template | Behavior |
|-----------|-----------|------------------|----------|
| Input `.v` file does not exist | `FILE_NOT_FOUND` | `File not found: {file_path}` | Return failure before subprocess spawn |
| Input file is not a `.v` file | `INVALID_INPUT` | `Expected a .v file, got: {file_path}` | Return failure before subprocess spawn |
| Output directory does not exist (single file, when `output_path` parent is missing) | `OUTPUT_DIR_NOT_FOUND` | `Output directory does not exist: {dir_path}` | Return failure before subprocess spawn |
| Proof name not found in file | `PROOF_NOT_FOUND` | `Proof {proof_name} not found in {file_path}. Available proofs: {names}` | Return failure after file scan, before subprocess spawn |
| Source directory does not exist (batch) | `SOURCE_DIR_NOT_FOUND` | `Source directory does not exist: {dir_path}` | Return failure before enumeration |
| No `.v` files found in source directory (batch) | `NO_INPUT_FILES` | `No .v files found in {dir_path}` | Return failure after enumeration, before any generation |

### 7.2 Dependency Errors

| Condition | Error Code | Message Template | Behavior |
|-----------|-----------|------------------|----------|
| Alectryon binary not found on `PATH` | `ALECTRYON_NOT_FOUND` | `Alectryon is not installed or not on the system PATH. Install it with: pip install alectryon` | Return failure; cached for server lifetime |
| Alectryon version below minimum | `ALECTRYON_VERSION_UNSUPPORTED` | `Alectryon version {found} is below the minimum required version {minimum}. Upgrade with: pip install --upgrade alectryon` | Return failure; cached for server lifetime |
| Coq compilation error during generation | `COQ_ERROR` | `Coq error in {file_path} at line {line}: {coq_message}` | Return failure for the affected file; batch continues |
| Alectryon process timed out | `GENERATION_TIMEOUT` | `Documentation generation timed out after {timeout} seconds for {file_path}` | Kill subprocess; return failure for the affected file; batch continues |
| Alectryon process crashed (non-zero exit, not a Coq error) | `ALECTRYON_ERROR` | `Alectryon failed with exit code {code}: {stderr}` | Return failure for the affected file; batch continues |

### 7.3 Batch Error Aggregation

In batch mode, per-file errors are collected in `FileOutcome` entries. The batch itself returns success with a summary unless a pre-flight check (availability, source directory existence, no input files) fails. When a pre-flight check fails, the batch returns the corresponding error immediately without processing any files.

All errors use the MCP standard error format defined in the mcp-server specification.

## 8. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability check latency | < 2 seconds (single `alectryon --version` invocation) |
| Availability check caching | Exactly one subprocess spawn per server process lifetime |
| Subprocess spawn overhead | < 100 ms from request validation to process spawn |
| Temporary file cleanup | Temporary `.v` files removed within 1 second of generation completion, on both success and failure paths |
| Batch concurrency | Files processed sequentially (one subprocess at a time) to avoid overwhelming Coq compilation resources |
| Memory | Adapter holds at most one file's content in memory at a time; batch results accumulate `FileOutcome` entries (< 1 KB each) |
| Path handling | All paths in requests and results are absolute; the adapter rejects relative paths |

## 9. Examples

### Single-file generation — HTML output to disk

```
generate_documentation({
  input_file: "/project/src/Nat.v",
  proof_name: null,
  output_path: "/docs/Nat.html",
  format: "html",
  custom_flags: [],
  timeout: 120
})

Subprocess: alectryon --frontend coq --backend webpage --output-directory /docs/ /project/src/Nat.v
Working directory: /project/src/
Exit code: 0
Generated: /docs/Nat.html

Result:
{
  "status": "success",
  "output_path": "/docs/Nat.html",
  "content": null,
  "format": "html",
  "error": null
}
```

### Single-file generation — inline content return

```
generate_documentation({
  input_file: "/project/src/Nat.v",
  proof_name: null,
  output_path: null,
  format: "html-fragment",
  custom_flags: ["--long-line-threshold", "80"],
  timeout: 60
})

Subprocess: alectryon --frontend coq --backend webpage-no-header --output-directory <tmp> --long-line-threshold 80 /project/src/Nat.v
Exit code: 0

Result:
{
  "status": "success",
  "output_path": null,
  "content": "<div class=\"alectryon-root\">...</div>",
  "format": "html-fragment",
  "error": null
}
```

### Proof-scoped generation

```
generate_proof_documentation({
  input_file: "/project/src/Arith.v",
  proof_name: "add_comm",
  output_path: null,
  format: "html",
  custom_flags: [],
  timeout: 120
})

Steps:
1. Read /project/src/Arith.v
2. Locate "Lemma add_comm" declaration
3. Extract: imports + section context + lemma declaration + proof body through Qed.
4. Write /project/src/.poule_tmp_add_comm.v
5. Spawn: alectryon --frontend coq --backend webpage --output-directory <tmp> /project/src/.poule_tmp_add_comm.v
6. Exit code: 0
7. Read generated HTML content
8. Delete /project/src/.poule_tmp_add_comm.v

Result:
{
  "status": "success",
  "output_path": null,
  "content": "<html>...<div class=\"alectryon-root\">...</div>...</html>",
  "format": "html",
  "error": null
}
```

### Batch generation with partial failure

```
generate_batch_documentation({
  source_directory: "/project/src/",
  output_directory: "/docs/",
  format: "html",
  custom_flags: [],
  timeout_per_file: 120
})

Enumerated: /project/src/A.v, /project/src/sub/B.v, /project/src/sub/C.v
  A.v → success → /docs/A.html
  sub/B.v → Coq error at line 42 → failure
  sub/C.v → success → /docs/sub/C.html
Generated: /docs/index.html

Result:
{
  "index_path": "/docs/index.html",
  "output_directory": "/docs/",
  "results": [
    {"input_file": "/project/src/A.v", "output_file": "/docs/A.html", "status": "success", "error": null},
    {"input_file": "/project/src/sub/B.v", "output_file": null, "status": "failure", "error": {"code": "COQ_ERROR", "message": "Coq error in /project/src/sub/B.v at line 42: ..."}},
    {"input_file": "/project/src/sub/C.v", "output_file": "/docs/sub/C.html", "status": "success", "error": null}
  ],
  "total": 3,
  "succeeded": 2,
  "failed": 1
}
```

### Alectryon not installed

```
generate_documentation({
  input_file: "/project/src/Nat.v",
  ...
})

Availability check: `alectryon --version` → command not found

Result:
{
  "status": "failure",
  "output_path": null,
  "content": null,
  "format": "html",
  "error": {"code": "ALECTRYON_NOT_FOUND", "message": "Alectryon is not installed or not on the system PATH. Install it with: pip install alectryon"}
}
```

## 10. Language-Specific Notes (Python)

- Use `asyncio.create_subprocess_exec` to spawn Alectryon, enabling async timeout enforcement via `asyncio.wait_for`.
- Use `tempfile.NamedTemporaryFile` with `dir` set to the source file's parent directory for proof-scoped temporary files; use a context manager or `try/finally` to guarantee cleanup.
- Use `pathlib.Path` for all path manipulation. Validate that paths are absolute with `Path.is_absolute()`.
- Use `shutil.move` to relocate generated files to the requested `output_path`.
- Availability cache: module-level or class-level variable holding the `AvailabilityStatus` enum (`available`, `not_installed`, `version_too_old`), set on first check.
- Version parsing: use `packaging.version.Version` or a simple tuple comparison on `(major, minor, patch)`.
- Batch directory enumeration: use `Path.rglob("*.v")`.
- Package location: `src/poule/documentation/`.
- Entry points: `async def generate_documentation(request: DocumentationRequest) -> DocumentationResult`, `async def generate_batch_documentation(request: BatchDocumentationRequest) -> BatchDocumentationResult`.

# Independent Proof Checking

Subprocess adapter wrapping `coqchk` for independent verification of compiled `.vo` files — single-file checking, project-wide checking, output parsing, and failure reporting.

**Architecture**: [independent-proof-checking.md](../doc/architecture/independent-proof-checking.md), [component-boundaries.md](../doc/architecture/component-boundaries.md)

---

## 1. Purpose

Define the Proof Checker Adapter that constructs `coqchk` invocations from structured requests, manages the subprocess lifecycle (spawn, timeout, termination), parses `coqchk` output into classified per-file results, detects stale `.vo` files, and returns a structured verdict to the MCP server.

## 2. Scope

**In scope**: CheckRequest validation, command construction, library path resolution, single-file checking, project-wide file discovery, `_CoqProject` parsing, staleness detection, subprocess lifecycle (spawn, timeout, kill), output parsing (success counting, failure classification), CheckResult assembly.

**Out of scope**: MCP protocol handling (owned by mcp-server), `.v` to `.vo` compilation (owned by build-system-integration), interactive proof sessions (owned by proof-session), search index access (owned by retrieval-pipeline), build system invocation (owned by build-system-integration).

## 3. Definitions

| Term | Definition |
|------|-----------|
| Independent proof checking | Re-verification of compiled `.vo` files using `coqchk`, a standalone binary with its own type checker kernel, independent of the main Coq compiler |
| Load path mapping | A (logical prefix, physical directory) pair that maps filesystem paths to Coq's logical module namespace |
| Library name | A dot-separated logical name (e.g., `MyLib.Arith.Plus`) identifying a Coq module within a load path |
| Stale `.vo` file | A compiled `.vo` file whose modification time is older than its corresponding `.v` source file |
| `_CoqProject` | A project metadata file listing load path directives (`-Q`, `-R`, `-I`) and source files for a Coq project |

## 4. Behavioral Requirements

### 4.1 Request Validation

#### validate_request(request: CheckRequest)

- REQUIRES: `request` is a CheckRequest.
- ENSURES: When `mode` is `"single"`, `file_path` is non-null, the file exists on disk, and the path ends with `.vo`. When `mode` is `"project"`, `project_dir` is non-null and the directory exists on disk. When validation fails, the adapter returns a CheckResult with `status="error"` immediately without spawning a subprocess.

> **Given** a CheckRequest with `mode="single"` and `file_path="/tmp/Missing.vo"` where the file does not exist
> **When** `validate_request` is called
> **Then** a CheckResult with `status="error"` is returned containing a CheckFailure with `failure_kind="missing_dependency"` and no subprocess is spawned

> **Given** a CheckRequest with `mode="single"` and `file_path="/tmp/Foo.v"`
> **When** `validate_request` is called
> **Then** a CheckResult with `status="error"` is returned with a failure message identifying the wrong extension

> **Given** a CheckRequest with `mode="project"` and `project_dir=null`
> **When** `validate_request` is called
> **Then** a CheckResult with `status="error"` is returned immediately

### 4.2 Binary Discovery

#### locate_coqchk()

- REQUIRES: None.
- ENSURES: Returns the absolute path to the `coqchk` binary. The adapter searches the system `PATH` (or a configured override path). When `coqchk` is not found, the adapter returns a CheckResult with `status="error"` and failure message `"coqchk not found"` without spawning a subprocess.

> **Given** `coqchk` is not on the system PATH and no override is configured
> **When** `locate_coqchk` is called
> **Then** a CheckResult with `status="error"` and message `"coqchk not found"` is returned

### 4.3 Library Path Resolution

#### resolve_library_name(file_path, load_paths)

- REQUIRES: `file_path` is an absolute path to a `.vo` file. `load_paths` is a list of (logical prefix, physical directory) pairs.
- ENSURES: Returns a dot-separated logical library name. The adapter strips the `.vo` extension, finds the load path entry whose physical directory is a prefix of the file path, replaces the physical prefix with the logical prefix, and substitutes path separators with dots.
- MAINTAINS: When no load path entry matches, the adapter returns the bare filename (without extension or logical prefix) and emits a warning. This fallback handles ad-hoc files outside a structured project.

> **Given** `file_path="/project/theories/Arith/Plus.vo"` and `load_paths=[("MyLib", "/project/theories")]`
> **When** `resolve_library_name` is called
> **Then** the result is `"MyLib.Arith.Plus"`

> **Given** `file_path="/tmp/Scratch.vo"` and `load_paths=[("Lib", "/project/src")]`
> **When** `resolve_library_name` is called
> **Then** the result is `"Scratch"` and a warning is emitted

> **Given** `file_path="/project/theories/Foo.vo"` and `load_paths=[("A", "/project/theories"), ("B", "/project/theories/sub")]`
> **When** `resolve_library_name` is called
> **Then** the longest matching physical prefix is selected

### 4.4 Command Construction

#### build_command(coqchk_path, load_paths, include_paths, library_names)

- REQUIRES: `coqchk_path` is an absolute path to the `coqchk` binary. `library_names` is a non-empty list of logical library names.
- ENSURES: Returns an argument vector of the form `[coqchk_path, load_path_flags..., include_flags..., library_names...]`. Each `(logical, physical)` pair in `load_paths` produces `-Q physical logical`. Each path in `include_paths` produces `-I path`.
- MAINTAINS: No flags beyond load paths, include paths, and library names are added. No `-silent`, `-norec`, or `-admit` flags. Recursive dependency checking is the default behavior.

> **Given** `load_paths=[("MyLib", "/project/theories")]`, `include_paths=["/project/plugins"]`, `library_names=["MyLib.Foo"]`
> **When** `build_command` is called
> **Then** the result is `["coqchk", "-Q", "/project/theories", "MyLib", "-I", "/project/plugins", "MyLib.Foo"]`

### 4.5 Single-File Checking

#### check_single(file_path, include_paths, load_paths, timeout_seconds)

- REQUIRES: `file_path` is an absolute path to an existing `.vo` file. `timeout_seconds` is a positive integer (default 300).
- ENSURES: Validates the file, detects staleness, resolves the library name, builds the command, spawns `coqchk`, enforces the timeout, parses output, and returns a CheckResult.

**Staleness detection**: the adapter derives the `.v` path by replacing the `.vo` extension with `.v`. When the `.v` file exists and its modification time is strictly greater than the `.vo` file's modification time, the `.vo` path is added to `stale_files`.

**Subprocess lifecycle**: the adapter spawns `coqchk` with the constructed argument vector, captures both stdout and stderr, and enforces the wall-clock timeout. On exit code 0, `status="pass"`. On non-zero exit code, `status="fail"` and output is parsed for failures. On timeout, the process is killed and `status="error"`.

> **Given** a valid `.vo` file whose `.v` source has a newer modification time
> **When** `check_single` is called
> **Then** the CheckResult contains the file in `stale_files` and the check proceeds normally

> **Given** a valid `.vo` file and `coqchk` exits with code 0
> **When** `check_single` completes
> **Then** the CheckResult has `status="pass"`, `files_checked=1`, `files_passed=1`, `files_failed=0`

> **Given** a valid `.vo` file and `coqchk` exceeds `timeout_seconds`
> **When** the timeout triggers
> **Then** the process is killed, partial output is captured, and the CheckResult has `status="error"` with a synthetic CheckFailure indicating timeout

### 4.6 Project-Wide Checking

#### check_project(project_dir, include_paths, load_paths, timeout_seconds)

- REQUIRES: `project_dir` is an absolute path to an existing directory. `timeout_seconds` is a positive integer (default 300).
- ENSURES: Discovers `.vo` files, detects staleness for each, resolves library names, builds a single `coqchk` invocation with all library names, spawns the subprocess, parses output, and returns a CheckResult.

**File discovery**:

| Condition | Behavior |
|-----------|----------|
| `_CoqProject` exists in `project_dir` | Parse `-Q`, `-R`, and `-I` directives; merge with request-provided paths (request paths take precedence on conflict); walk directories referenced by load path entries collecting `.vo` files |
| `_CoqProject` does not exist | Walk `project_dir` recursively collecting all `.vo` files; use request-provided paths only |
| `_CoqProject` exists but contains parse errors | Log a warning; fall back to recursive directory walk |
| No `.vo` files found | Return CheckResult with `status="pass"`, `files_checked=0`, empty failures |

**Invocation strategy**: all discovered library names are passed to a single `coqchk` invocation. A single invocation is preferred because `coqchk` resolves the full dependency graph internally, loading each dependency exactly once.

> **Given** a project directory with a `_CoqProject` containing `-Q theories MyLib` and 3 `.vo` files under `theories/`
> **When** `check_project` is called
> **Then** a single `coqchk` invocation receives all 3 logical library names

> **Given** a project directory with no `.vo` files
> **When** `check_project` is called
> **Then** CheckResult has `status="pass"`, `files_checked=0`, and no subprocess is spawned

> **Given** a `_CoqProject` with a syntax error on one line
> **When** `check_project` parses it
> **Then** a warning is logged and the adapter falls back to recursive directory walk

### 4.7 Output Parsing

#### parse_output(stdout, stderr, exit_code, library_names)

- REQUIRES: `stdout` and `stderr` are strings (possibly empty). `exit_code` is an integer or null (null indicates timeout/kill). `library_names` is the list of library names submitted to `coqchk`.
- ENSURES: Returns a tuple of (`files_checked`, `files_passed`, `files_failed`, `failures`) where `failures` is a list of CheckFailure.

**Success detection**: on exit code 0, the parser counts lines matching the pattern `<module> has been checked` to populate `files_checked` and `files_passed`.

**Failure classification**: on non-zero exit code, the parser scans stderr line by line, matching against patterns in priority order:

| Priority | Pattern | `failure_kind` | Extracted fields |
|----------|---------|----------------|-----------------|
| 1 | `Error: ... is not consistent with ...` | `inconsistency` | `module_name` from context |
| 2 | `Error: Missing library ...` or `Cannot find library ...` | `missing_dependency` | library name |
| 3 | `Error: Anomaly ...` or `Type error ...` | `type_error` | `definition` name if present |
| 4 | `Error: ... (axiom) ...` mismatch patterns | `axiom_mismatch` | axiom name |
| 5 | Any other `Error:` line | `unknown` | raw text |

- MAINTAINS: Unrecognized stderr content is captured in `raw_output` but does not produce spurious CheckFailure entries. The parser only creates CheckFailure for lines matching the patterns above.

**Unchecked file detection**: for project-wide checks, files that appear in neither success lines nor error output are reported as unchecked (they were not reached, typically due to an early abort on a dependency failure).

> **Given** `coqchk` exits with code 0 and stdout contains `MyLib.Foo has been checked\nMyLib.Bar has been checked`
> **When** `parse_output` is called
> **Then** `files_checked=2`, `files_passed=2`, `files_failed=0`, `failures=[]`

> **Given** `coqchk` exits with code 1 and stderr contains `Error: MyLib.Baz is not consistent with MyLib.Foo`
> **When** `parse_output` is called
> **Then** `failures` contains one CheckFailure with `failure_kind="inconsistency"` and `module_name="MyLib.Baz"`

> **Given** `coqchk` exits with code 1 and stderr contains `Error: Missing library MyLib.Gone`
> **When** `parse_output` is called
> **Then** `failures` contains one CheckFailure with `failure_kind="missing_dependency"`

## 5. Data Model

### CheckRequest

| Field | Type | Constraints |
|-------|------|-------------|
| `mode` | `"single"` or `"project"` | Required |
| `file_path` | string or null | Required when `mode="single"`; absolute path ending in `.vo` |
| `project_dir` | string or null | Required when `mode="project"`; absolute path to existing directory |
| `include_paths` | list of string | Optional; default empty list; each entry is an absolute path |
| `load_paths` | list of (string, string) | Optional; default empty list; each entry is (logical prefix, physical directory) |
| `timeout_seconds` | positive integer | Optional; default 300; minimum 1; maximum 3600 |

### CheckResult

| Field | Type | Constraints |
|-------|------|-------------|
| `status` | `"pass"` or `"fail"` or `"error"` | Required |
| `files_checked` | non-negative integer | Required; count of `.vo` files submitted to `coqchk` |
| `files_passed` | non-negative integer | Required; count of files that passed; `files_passed + files_failed <= files_checked` |
| `files_failed` | non-negative integer | Required; count of files that failed |
| `failures` | list of CheckFailure | Required; empty when `status="pass"` |
| `stale_files` | list of string | Required; absolute paths to `.vo` files older than their `.v` source; empty when none stale |
| `wall_time_ms` | non-negative integer | Required; wall-clock time for the entire check in milliseconds |
| `raw_output` | string | Required; full `coqchk` stdout + stderr concatenation; empty string when no subprocess was spawned |

### CheckFailure

| Field | Type | Constraints |
|-------|------|-------------|
| `file_path` | string | Required; absolute path to the `.vo` file that failed |
| `module_name` | string or null | Null when the module cannot be identified from output |
| `definition` | string or null | Null when no specific definition is identified |
| `failure_kind` | `"inconsistency"` or `"missing_dependency"` or `"axiom_mismatch"` or `"type_error"` or `"unknown"` | Required |
| `raw_message` | string | Required; the raw `coqchk` error text for this failure |

### Invariants

- `files_passed + files_failed <= files_checked` (some files may be unchecked if `coqchk` aborts early).
- When `status="pass"`, `failures` is empty and `files_failed=0`.
- When `status="fail"`, `failures` is non-empty.
- When `status="error"`, at least one CheckFailure describes the error condition.

## 6. Interface Contracts

### MCP Server → Proof Checker Adapter

| Property | Value |
|----------|-------|
| Operation | `check_proof(request: CheckRequest) -> CheckResult` |
| Input | A valid CheckRequest (MCP server performs protocol-level validation; adapter performs domain-level validation) |
| Output | A CheckResult with all fields populated |
| Concurrency | Serialized; one `coqchk` invocation at a time per request; multiple concurrent requests may run independent subprocesses |
| Error strategy | All errors are captured in the CheckResult; the adapter does not raise exceptions to the MCP server |
| Idempotency | Yes; the same CheckRequest against the same `.vo` files produces the same CheckResult (modulo timing and external filesystem changes) |

### Proof Checker Adapter → Host Filesystem

| Property | Value |
|----------|-------|
| Operations | Read `.vo` file metadata (existence, modification time), read `.v` file metadata (existence, modification time), read `_CoqProject` contents, enumerate directory contents |
| Write operations | None; the adapter does not modify any files on disk |
| Error strategy | Missing files and unreadable directories produce CheckResult with `status="error"` |

### Proof Checker Adapter → coqchk Binary

| Property | Value |
|----------|-------|
| Invocation | Single subprocess per check request |
| Streams captured | stdout and stderr (both fully buffered until process exit or timeout) |
| Timeout enforcement | Wall-clock timeout; on expiry the process is killed (SIGKILL after grace period) |
| Exit code interpretation | 0 = success; non-zero = failure; null (killed) = error |

## 7. Error Specification

### 7.1 Input Errors

| Condition | Behavior |
|-----------|----------|
| `file_path` is null when `mode="single"` | Return `status="error"`, failure message identifies missing field |
| `project_dir` is null when `mode="project"` | Return `status="error"`, failure message identifies missing field |
| `file_path` does not exist | Return `status="error"`, single CheckFailure with `failure_kind="missing_dependency"` |
| `file_path` does not end in `.vo` | Return `status="error"`, failure message identifies wrong extension |
| `project_dir` does not exist | Return `status="error"`, failure message identifies missing directory |
| `timeout_seconds` < 1 | Clamp to 1 |
| `timeout_seconds` > 3600 | Clamp to 3600 |

### 7.2 Dependency Errors

| Condition | Behavior |
|-----------|----------|
| `coqchk` binary not found on PATH | Return `status="error"`, failure message: `"coqchk not found"` |
| `coqchk` subprocess crashes (non-zero exit, no parseable output) | Return `status="fail"`, single CheckFailure with `failure_kind="unknown"` and `raw_message` containing available output |
| `coqchk` subprocess times out | Kill process, parse partial output, return `status="error"` with a synthetic CheckFailure with `failure_kind="unknown"` and message indicating timeout, plus any failures parsed from partial output |

### 7.3 Filesystem Errors

| Condition | Behavior |
|-----------|----------|
| `_CoqProject` contains parse errors | Log warning, fall back to recursive directory walk; checking proceeds |
| Directory walk encounters permission errors | Skip inaccessible directories, log warning, continue with accessible files |
| No `.vo` files found in project | Return `status="pass"`, `files_checked=0`, empty failures |

### 7.4 Edge Cases

| Condition | Behavior |
|-----------|----------|
| `.vo` file exists but corresponding `.v` does not exist | No staleness warning; `.v` absence is not an error |
| Multiple load path entries match the same `.vo` file | The longest matching physical prefix is selected |
| `coqchk` produces output on stdout but exits non-zero | Both stdout and stderr are parsed; success lines from stdout are counted |
| Empty `load_paths` and empty `include_paths` | Command is constructed with library names only; `coqchk` uses its default load paths |

## 8. Non-Functional Requirements

- The adapter shall impose no more than 50 ms of overhead beyond the `coqchk` subprocess execution time (excluding filesystem enumeration for project-wide checks).
- File discovery for project-wide checks shall complete within 5 seconds for projects with up to 10,000 files.
- The adapter shall not buffer more than 64 MB of `coqchk` output in memory. When output exceeds this limit, the adapter truncates `raw_output` and parses what was captured.
- The adapter shall not spawn more than one `coqchk` process per check request.
- Output parsing shall complete in under 100 ms for output up to 1 MB.

## 9. Examples

### Single-file pass

```
check_proof(CheckRequest(
  mode="single",
  file_path="/project/theories/Arith/Plus.vo",
  load_paths=[("MyLib", "/project/theories")],
  include_paths=[],
  timeout_seconds=300
))

coqchk invocation:
  coqchk -Q /project/theories MyLib MyLib.Arith.Plus

coqchk stdout: "MyLib.Arith.Plus has been checked"
coqchk exit code: 0

Result:
{
  "status": "pass",
  "files_checked": 1,
  "files_passed": 1,
  "files_failed": 0,
  "failures": [],
  "stale_files": [],
  "wall_time_ms": 1200,
  "raw_output": "MyLib.Arith.Plus has been checked"
}
```

### Single-file failure — inconsistency

```
check_proof(CheckRequest(
  mode="single",
  file_path="/project/theories/Bad.vo",
  load_paths=[("MyLib", "/project/theories")],
  timeout_seconds=300
))

coqchk exit code: 1
coqchk stderr: "Error: MyLib.Bad is not consistent with MyLib.Core"

Result:
{
  "status": "fail",
  "files_checked": 1,
  "files_passed": 0,
  "files_failed": 1,
  "failures": [
    {
      "file_path": "/project/theories/Bad.vo",
      "module_name": "MyLib.Bad",
      "definition": null,
      "failure_kind": "inconsistency",
      "raw_message": "Error: MyLib.Bad is not consistent with MyLib.Core"
    }
  ],
  "stale_files": [],
  "wall_time_ms": 800,
  "raw_output": "Error: MyLib.Bad is not consistent with MyLib.Core"
}
```

### Project-wide check with staleness

```
check_proof(CheckRequest(
  mode="project",
  project_dir="/project",
  timeout_seconds=600
))

_CoqProject parsed: -Q theories MyLib
.vo files found: theories/Foo.vo, theories/Bar.vo, theories/Baz.vo
Staleness: theories/Bar.vo is older than theories/Bar.v

coqchk invocation:
  coqchk -Q /project/theories MyLib MyLib.Foo MyLib.Bar MyLib.Baz

coqchk exit code: 0
coqchk stdout:
  MyLib.Foo has been checked
  MyLib.Bar has been checked
  MyLib.Baz has been checked

Result:
{
  "status": "pass",
  "files_checked": 3,
  "files_passed": 3,
  "files_failed": 0,
  "failures": [],
  "stale_files": ["/project/theories/Bar.vo"],
  "wall_time_ms": 4500,
  "raw_output": "MyLib.Foo has been checked\nMyLib.Bar has been checked\nMyLib.Baz has been checked"
}
```

### Error — coqchk not found

```
check_proof(CheckRequest(mode="single", file_path="/project/Foo.vo"))

Result:
{
  "status": "error",
  "files_checked": 0,
  "files_passed": 0,
  "files_failed": 0,
  "failures": [
    {
      "file_path": "/project/Foo.vo",
      "module_name": null,
      "definition": null,
      "failure_kind": "unknown",
      "raw_message": "coqchk not found"
    }
  ],
  "stale_files": [],
  "wall_time_ms": 0,
  "raw_output": ""
}
```

## 10. Language-Specific Notes (Python)

- Use `asyncio.create_subprocess_exec` to spawn `coqchk`, enabling non-blocking stdout/stderr capture and timeout enforcement via `asyncio.wait_for`.
- Use `shutil.which("coqchk")` for binary discovery on PATH.
- Use `pathlib.Path` for all path manipulation: suffix checking (`.suffix == ".vo"`), parent resolution, relative path computation for library name derivation.
- Use `os.path.getmtime` for staleness comparison.
- Parse `_CoqProject` line-by-line; split on whitespace; recognize `-Q`, `-R`, and `-I` directives. Ignore comment lines (starting with `#`) and unrecognized directives.
- Output parsing: compile regex patterns once at module load time. Use `re.search` per line against the priority-ordered pattern list.
- Package location: `src/poule/checker/`.
- Entry point: `async def check_proof(request: CheckRequest) -> CheckResult`.
- Subprocess timeout: use `process.kill()` followed by `process.wait()` on timeout. Capture partial output from the communicate buffer before killing.
- Memory limit on output: read stdout/stderr incrementally using `asyncio.StreamReader`; stop buffering at 64 MB.

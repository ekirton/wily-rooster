# Build System Integration

Adapter layer wrapping `coq_makefile`, Dune, and opam for build system detection, project file generation, build execution, error parsing, and dependency management.

**Architecture**: [build-system-integration.md](../doc/architecture/build-system-integration.md), [component-boundaries.md](../doc/architecture/component-boundaries.md)

---

## 1. Purpose

Define the build system adapter that detects which build system a Coq/Rocq project uses, generates and updates configuration files (`_CoqProject`, `dune-project`, `dune`, `.opam`), executes builds as subprocesses with structured error parsing, and queries/manages opam dependencies -- providing the MCP Server with a uniform interface to heterogeneous build tooling.

## 2. Scope

**In scope**: Build system detection (Dune, coq_makefile), project file generation (`_CoqProject`, `dune-project`, per-directory `dune`, `.opam`), coq_makefile-to-Dune migration, build execution with subprocess management, error parsing (Coq compiler, Dune, opam), package queries (`opam list`, `opam show`), dependency management (`opam install`, conflict detection, dependency addition to project files).

**Out of scope**: MCP protocol handling (owned by mcp-server), Coq proof session management (owned by proof-session), opam switch management (`opam switch create`, `opam switch set`), interactive build modes, persistent build daemons.

## 3. Definitions

| Term | Definition |
|------|-----------|
| Build system | The toolchain that compiles `.v` files: either Dune or coq_makefile/make |
| Marker file | A file whose presence signals a build system: `dune-project` for Dune, `_CoqProject` for coq_makefile |
| Logical path | A dot-separated name mapping a filesystem directory to a Coq library namespace (e.g., `MyLib.Sub`) |
| Build error | A structured record parsed from build output containing category, location, explanation, and suggested fix |
| opam switch | An isolated opam installation environment; the adapter inherits the active switch but never modifies switch configuration |
| Dry-run | An opam operation with `--dry-run` that simulates actions without modifying the switch |

## 4. Behavioral Requirements

### 4.1 Build System Detection

#### detect_build_system(project_dir)

- REQUIRES: `project_dir` is an absolute path to an existing directory.
- ENSURES: Returns a DetectionResult identifying the primary build system, opam presence, and paths to detected configuration files. Detection is deterministic and based on file presence, not file content.
- MAINTAINS: Detection never modifies the filesystem. Detection completes without spawning subprocesses.

The adapter shall apply the following precedence rules:

| Condition | Result |
|-----------|--------|
| `dune-project` exists in `project_dir` | `build_system = DUNE` |
| `_CoqProject` exists in `project_dir` and `dune-project` does not | `build_system = COQ_MAKEFILE` |
| Neither marker file exists | `build_system = UNKNOWN` |

Independently of the primary build system, when any `.opam` file exists in `project_dir`, the adapter shall set `has_opam = true`.

> **Given** a directory containing both `dune-project` and `_CoqProject`
> **When** `detect_build_system` is called
> **Then** the result has `build_system = DUNE` (Dune takes precedence)

> **Given** an empty directory with no marker files
> **When** `detect_build_system` is called
> **Then** the result has `build_system = UNKNOWN` and `has_opam = false`

> **Given** a directory with `_CoqProject` and `mylib.opam`
> **When** `detect_build_system` is called
> **Then** the result has `build_system = COQ_MAKEFILE` and `has_opam = true`

### 4.2 Project File Generation -- _CoqProject

#### generate_coq_project(project_dir, logical_name?, extra_flags?)

- REQUIRES: `project_dir` is an absolute path to an existing directory. `logical_name` is a non-empty string or null (inferred from directory name when null). `extra_flags` is a list of strings or empty.
- ENSURES: Writes a `_CoqProject` file to `project_dir`. The file contains: flags first, then `-Q`/`-R` mappings (one per source directory), then source file paths (alphabetically within each directory). Recursively enumerates all `.v` files in `project_dir`. Each source directory maps to a logical path segment derived from the directory name. The project root maps to `logical_name`.

> **Given** a directory `mylib/` with files `A.v`, `sub/B.v`, `sub/C.v`
> **When** `generate_coq_project("mylib/")` is called
> **Then** `_CoqProject` contains `-Q . MyLib`, `-Q sub MyLib.Sub`, `A.v`, `sub/B.v`, `sub/C.v`

#### update_coq_project(project_dir)

- REQUIRES: `project_dir` contains an existing `_CoqProject` file.
- ENSURES: Parses the existing file, identifies new directories and `.v` files not yet listed, inserts them in the appropriate position, and preserves existing custom flags and comments.

> **Given** a `_CoqProject` listing `A.v` and a new file `B.v` exists on disk
> **When** `update_coq_project` is called
> **Then** `B.v` is added to the file; existing content is preserved

### 4.3 Project File Generation -- Dune

#### generate_dune_project(project_dir, logical_name?, dune_lang_version?, coq_lang_version?)

- REQUIRES: `project_dir` is an absolute path to an existing directory.
- ENSURES: Writes a `dune-project` file at the root with `(lang dune ...)` and `(using coq ...)` declarations. Writes per-directory `dune` files wherever `.v` files exist, each containing a `(coq.theory ...)` stanza with `(name ...)` and `(theories ...)` fields. Dependencies between sub-libraries are declared in `(theories ...)`.

> **Given** a directory with `src/A.v` and `src/util/B.v`
> **When** `generate_dune_project` is called with `logical_name = "MyLib"`
> **Then** `dune-project` is created at the root, `src/dune` has `(coq.theory (name MyLib))`, and `src/util/dune` has `(coq.theory (name MyLib.Util) (theories MyLib))`

### 4.4 Project File Generation -- .opam

#### generate_opam_file(project_dir, metadata)

- REQUIRES: `project_dir` is an absolute path. `metadata` contains: `name` (non-empty string), `version` (string), `synopsis` (string), `maintainer` (string), `dependencies` (list of (name, version_constraint) pairs).
- ENSURES: Writes a `.opam` file with `opam-version: "2.0"`, the specified metadata fields, a `depends` field, and a `build` field matching the detected build system (`["dune" "build" ...]` for Dune, `["make" "-j" jobs]` for coq_makefile).

> **Given** a Dune project with metadata `{name: "mylib", version: "1.0", ...}`
> **When** `generate_opam_file` is called
> **Then** the `.opam` file includes `build: [["dune" "build" ...]]`

### 4.5 coq_makefile-to-Dune Migration

#### migrate_to_dune(project_dir)

- REQUIRES: `project_dir` contains a `_CoqProject` file.
- ENSURES: Parses `-Q` and `-R` flags and source file listings from `_CoqProject`. Generates equivalent `dune-project` and per-directory `dune` files. Returns a MigrationResult listing any `_CoqProject` flags that have no Dune equivalent.
- MAINTAINS: The existing `_CoqProject` file is not deleted or modified.

> **Given** a `_CoqProject` with `-Q src MyLib` and `-arg "-w -notation-overridden"`
> **When** `migrate_to_dune` is called
> **Then** `dune-project` and `src/dune` are generated, and the result lists `-arg "-w -notation-overridden"` as untranslatable

### 4.6 Build Execution

#### execute_build(project_dir, build_system?, target?, timeout?)

- REQUIRES: `project_dir` is an absolute path to an existing directory. `build_system` is a BuildSystem or null (null triggers auto-detection). `timeout` is a positive integer in seconds, minimum 10, default 300.
- ENSURES: Spawns a fresh subprocess for the build command. Returns a BuildResult with exit code, captured stdout and stderr, parsed errors, elapsed time, and timeout status. For `COQ_MAKEFILE` projects with no Makefile, the adapter first runs `coq_makefile -f _CoqProject -o Makefile`, then runs `make`. For `DUNE`, runs `dune build --root <project_dir>`.
- MAINTAINS: No persistent build daemon. Each invocation spawns and waits for a single subprocess. stdin is closed (no interactive input). Environment is inherited from the server process.

**Subprocess lifecycle:**

| Phase | Behavior |
|-------|----------|
| Spawn | Working directory set to `project_dir`; stdout and stderr piped; stdin closed |
| Wait | Block until exit or timeout |
| Timeout | Send SIGTERM; wait 5 seconds; send SIGKILL if still running |
| Capture | stdout and stderr captured separately, bounded at 1 MB per stream; excess truncated from the beginning (tail preserved) |

> **Given** a valid Dune project
> **When** `execute_build(project_dir, timeout=60)` is called and the build succeeds
> **Then** the BuildResult has `success = true`, `exit_code = 0`, and `errors` is empty

> **Given** a coq_makefile project with no Makefile
> **When** `execute_build(project_dir)` is called
> **Then** the adapter runs `coq_makefile -f _CoqProject -o Makefile` before `make`

> **Given** a build that runs for 400 seconds
> **When** `execute_build(project_dir, timeout=300)` is called
> **Then** the BuildResult has `timed_out = true` and contains output captured before termination

### 4.7 Error Parsing

#### parse_build_errors(stdout, stderr, build_system)

- REQUIRES: `stdout` and `stderr` are strings. `build_system` is `DUNE` or `COQ_MAKEFILE`.
- ENSURES: Returns an ordered list of BuildError records parsed from the output. Each record includes category, location (when parseable), raw text, plain-language explanation, and suggested fix (when the category is recognized). Explanations and fix suggestions are template-based and deterministic.

**Coq compiler error patterns** (applies to both build systems):

| Pattern | Category |
|---------|----------|
| `Cannot find a physical path bound to logical path` | `LOGICAL_PATH_NOT_FOUND` |
| `Required library ... not found` | `REQUIRED_LIBRARY_NOT_FOUND` |
| Type checking failure | `TYPE_ERROR` |
| Parsing failure | `SYNTAX_ERROR` |
| Tactic-related build error | `TACTIC_FAILURE` |
| Unrecognized error | `OTHER` |

**Dune-specific error patterns:**

| Pattern | Category |
|---------|----------|
| Missing `coq.theory` dependency | `THEORY_NOT_FOUND` |
| Stanza syntax or field error | `DUNE_CONFIG_ERROR` |
| Unrecognized | `OTHER` |

**opam error patterns:**

| Pattern | Category |
|---------|----------|
| Incompatible version constraints | `VERSION_CONFLICT` |
| Package not in any repository | `PACKAGE_NOT_FOUND` |
| Package build failed during installation | `BUILD_FAILURE` |
| Unrecognized | `OTHER` |

Coq compiler errors are extracted using the pattern `File "{file}", line {line}, characters {start}-{end}:` to populate file path, line number, and character range fields.

> **Given** stderr containing `File "src/A.v", line 10, characters 0-15:\nError: Cannot find a physical path bound to logical path MyLib.`
> **When** `parse_build_errors` is called
> **Then** one BuildError is returned with `category = LOGICAL_PATH_NOT_FOUND`, `file = "src/A.v"`, `line = 10`, and a non-null `suggested_fix`

> **Given** stderr with no recognizable error patterns
> **When** `parse_build_errors` is called with non-empty stderr
> **Then** one BuildError is returned with `category = OTHER` and the full text preserved in `raw_text`

### 4.8 Package Queries

#### query_installed_packages()

- REQUIRES: `opam` is on PATH.
- ENSURES: Runs `opam list --installed --columns=name,version --short`. Returns a list of (name, version) pairs sorted alphabetically by name.

#### query_package_info(package_name)

- REQUIRES: `package_name` is a non-empty string. `opam` is on PATH.
- ENSURES: Runs `opam show` to retrieve version, synopsis, depends, and all-versions fields. Returns a PackageInfo record. When the package does not exist, returns `PACKAGE_NOT_FOUND`.

> **Given** `coq-mathcomp-ssreflect` is installed
> **When** `query_package_info("coq-mathcomp-ssreflect")` is called
> **Then** the result includes `installed_version` with the current version and `available_versions` in descending order

### 4.9 Dependency Management

#### add_dependency(project_dir, package_name, version_constraint?)

- REQUIRES: `project_dir` is an absolute path. `package_name` is a non-empty string.
- ENSURES: Detects the build system. Locates the target file (`dune-project` for Dune, `.opam` for coq_makefile). Parses the existing dependency list. If the package is already present, returns `DEPENDENCY_EXISTS`. Otherwise, inserts the dependency with the specified version constraint (no constraint when unspecified). Writes the updated file, preserving formatting and comments where possible.

> **Given** a Dune project with no dependency on `coq-mathcomp-ssreflect`
> **When** `add_dependency(project_dir, "coq-mathcomp-ssreflect", ">= 2.0")` is called
> **Then** `dune-project` is updated with the new dependency

> **Given** a project that already depends on `coq-stdpp`
> **When** `add_dependency(project_dir, "coq-stdpp")` is called
> **Then** the adapter returns `DEPENDENCY_EXISTS` and makes no file changes

#### check_dependency_conflicts(dependencies)

- REQUIRES: `dependencies` is a non-empty list of (name, version_constraint) pairs. `opam` is on PATH.
- ENSURES: Runs `opam install --dry-run --show-actions` with all specified dependencies. Returns a DependencyStatus: `satisfiable = true` when exit code is 0, or `satisfiable = false` with conflict details when exit code is non-zero.

#### install_package(package_name, version_constraint?)

- REQUIRES: `package_name` is a non-empty string. `opam` is on PATH.
- ENSURES: Runs `opam install <package_name>` with a 600-second timeout. On success, returns the installed version. On failure, returns parsed BuildError records from the opam error parser.
- MAINTAINS: Package installation is never triggered as a side effect of another operation. Only invoked on explicit request.

> **Given** a request to install `coq-equations`
> **When** `install_package("coq-equations")` is called and the install succeeds
> **Then** the result includes the installed version string

## 5. Data Model

### BuildSystem

Enumeration: `COQ_MAKEFILE`, `DUNE`, `UNKNOWN`.

### DetectionResult

| Field | Type | Constraints |
|-------|------|-------------|
| `build_system` | BuildSystem | Required |
| `has_opam` | boolean | Required |
| `config_files` | list of string | Required; absolute paths to detected configuration files; empty when `UNKNOWN` |
| `project_dir` | string | Required; absolute path |

### BuildRequest

| Field | Type | Constraints |
|-------|------|-------------|
| `project_dir` | string | Required; absolute path to existing directory |
| `build_system` | BuildSystem or null | Null triggers auto-detection |
| `target` | string or null | Null uses the default target |
| `timeout` | positive integer | Default: 300; minimum: 10 |

### BuildResult

| Field | Type | Constraints |
|-------|------|-------------|
| `success` | boolean | Required; true when exit code is 0 |
| `exit_code` | integer | Required |
| `stdout` | string | Required; captured standard output |
| `stderr` | string | Required; captured standard error |
| `errors` | list of BuildError | Required; empty on success |
| `elapsed_ms` | non-negative integer | Required; wall-clock milliseconds |
| `build_system` | BuildSystem | Required; the system used |
| `timed_out` | boolean | Required |
| `truncated` | boolean | Required; true when output exceeded 1 MB limit |

### BuildError

| Field | Type | Constraints |
|-------|------|-------------|
| `category` | string | Required; one of the defined category constants |
| `file` | string or null | Null when not parseable from output |
| `line` | positive integer or null | Null when not parseable |
| `char_range` | pair of non-negative integers or null | (start, end); null when not parseable |
| `raw_text` | string | Required; original error text |
| `explanation` | string | Required; template-based plain-language description |
| `suggested_fix` | string or null | Null for `OTHER` category |

### PackageInfo

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | string | Required; non-empty |
| `installed_version` | string or null | Null when not installed |
| `available_versions` | list of string | Required; descending order |
| `synopsis` | string | Required |
| `dependencies` | list of string | Required; direct dependency names |

### MigrationResult

| Field | Type | Constraints |
|-------|------|-------------|
| `generated_files` | list of string | Required; absolute paths of files written |
| `untranslatable_flags` | list of string | Required; `_CoqProject` flags with no Dune equivalent; empty when all flags translate |

### DependencyStatus

| Field | Type | Constraints |
|-------|------|-------------|
| `satisfiable` | boolean | Required |
| `conflicts` | list of ConflictDetail | Required; empty when `satisfiable = true` |

### ConflictDetail

| Field | Type | Constraints |
|-------|------|-------------|
| `package` | string | Required; package with conflicting constraints |
| `constraints` | list of ConstraintSource | Required; the incompatible constraints |

### ConstraintSource

| Field | Type | Constraints |
|-------|------|-------------|
| `required_by` | string | Required; package imposing this constraint |
| `constraint` | string | Required; version constraint expression |

## 6. Interface Contracts

### Build System Adapter -> MCP Server

| Property | Value |
|----------|-------|
| Invocation | In-process function calls from the MCP Server |
| Concurrency | Serialized; one build or opam operation at a time |
| Error strategy | Adapter errors returned as structured error codes; build failures returned as BuildResult with `success = false` |
| Idempotency | Detection and queries are idempotent. Generation overwrites target files. Build execution is not idempotent (filesystem side effects). |

### Build System Adapter -> External Tools

| Property | Value |
|----------|-------|
| Interaction model | Subprocess execution; no persistent connections or linked libraries |
| Required tools | `coq_makefile`, `make`, `dune`, `opam` (each checked on PATH before use) |
| Environment | Inherited from server process; includes PATH, OPAMSWITCH, OPAMROOT |
| Timeout | Per-subprocess; configurable per invocation |
| Error strategy | Non-zero exit code is not an adapter error; it produces a BuildResult or structured error depending on operation type |

### Read-Only vs. Write Operations

| Category | Operations | Safety |
|----------|-----------|--------|
| Read-only | `opam list`, `opam show`, `opam install --dry-run` | Safe at any time; no confirmation needed |
| Write (files) | `generate_*`, `update_*`, `migrate_*`, `add_dependency` | Modifies project files in `project_dir` |
| Write (switch) | `install_package` | Modifies opam switch; only on explicit request |

## 7. Error Specification

### 7.1 Input Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| `project_dir` does not exist | `PROJECT_NOT_FOUND` | Return error immediately; no subprocess spawned |
| `project_dir` is not a directory | `PROJECT_NOT_FOUND` | Return error immediately |
| `timeout` < 10 | Clamp to 10 | No error; silently enforce minimum |
| `timeout` not a positive integer | `INVALID_PARAMETER` | Return error immediately |
| `package_name` is empty | `INVALID_PARAMETER` | Return error immediately |

### 7.2 Dependency Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Build system not detected and not specified | `BUILD_SYSTEM_NOT_DETECTED` | Return error with list of files probed |
| `coq_makefile` not found on PATH | `TOOL_NOT_FOUND` | Return error naming `coq_makefile` |
| `dune` not found on PATH | `TOOL_NOT_FOUND` | Return error naming `dune` |
| `opam` not found on PATH | `TOOL_NOT_FOUND` | Return error naming `opam` |
| `make` not found on PATH | `TOOL_NOT_FOUND` | Return error naming `make` |

### 7.3 Operational Errors

| Condition | Error Code | Behavior |
|-----------|-----------|----------|
| Build timeout exceeded | `BUILD_TIMEOUT` | Terminate subprocess; return partial output |
| Build failed (non-zero exit) | (not an error) | Returned as BuildResult with `success = false` and parsed errors |
| Output exceeds 1 MB per stream | (not an error) | Truncated from beginning; `truncated = true` in result |
| Target file not writable | `FILE_NOT_WRITABLE` | Return error; no modification attempted |
| Dependency already exists | `DEPENDENCY_EXISTS` | Return informational response; no modification |
| Package not found (opam show) | `PACKAGE_NOT_FOUND` | Return error naming the queried package |
| opam dry-run detects conflict | (not an error) | Returned as DependencyStatus with `satisfiable = false` |

All errors surfaced through MCP tools use the MCP standard error format defined in [mcp-server.md](mcp-server.md).

## 8. Non-Functional Requirements

- Build system detection shall complete in < 50 ms for directories with up to 10,000 files.
- The adapter shall support project directories containing up to 50,000 `.v` files for file enumeration during generation.
- Build output capture shall handle up to 1 MB per stream (stdout, stderr) without memory allocation failure.
- Subprocess spawn-to-first-output latency shall not exceed 2 seconds on a system where the tool is installed.
- Error parsing shall process 1 MB of build output in < 500 ms.
- The adapter shall not maintain in-memory state between invocations; each call is self-contained.

## 9. Examples

### Build system detection

```
detect_build_system("/home/user/my-coq-project")

Directory contains: dune-project, _CoqProject, mylib.opam

Result:
{
  "build_system": "DUNE",
  "has_opam": true,
  "config_files": ["/home/user/my-coq-project/dune-project",
                    "/home/user/my-coq-project/_CoqProject",
                    "/home/user/my-coq-project/mylib.opam"],
  "project_dir": "/home/user/my-coq-project"
}
```

### Successful build

```
execute_build("/home/user/my-coq-project", timeout=120)

Build system auto-detected: DUNE
Command: ["dune", "build", "--root", "/home/user/my-coq-project"]

Result:
{
  "success": true,
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "errors": [],
  "elapsed_ms": 15200,
  "build_system": "DUNE",
  "timed_out": false,
  "truncated": false
}
```

### Failed build with parsed errors

```
execute_build("/home/user/my-coq-project", timeout=120)

Build system: COQ_MAKEFILE
Exit code: 2

Result:
{
  "success": false,
  "exit_code": 2,
  "stdout": "...",
  "stderr": "File \"src/Lemmas.v\", line 42, characters 0-24:\nError: Cannot find a physical path bound to logical path MyLib.Utils.",
  "errors": [
    {
      "category": "LOGICAL_PATH_NOT_FOUND",
      "file": "src/Lemmas.v",
      "line": 42,
      "char_range": [0, 24],
      "raw_text": "File \"src/Lemmas.v\", line 42, characters 0-24:\nError: Cannot find a physical path bound to logical path MyLib.Utils.",
      "explanation": "The Coq compiler cannot find a directory mapped to the logical path 'MyLib.Utils'. This path must be declared with a -Q or -R flag in _CoqProject.",
      "suggested_fix": "Add '-Q <directory> MyLib.Utils' to _CoqProject, where <directory> is the filesystem path containing the Utils module."
    }
  ],
  "elapsed_ms": 3400,
  "build_system": "COQ_MAKEFILE",
  "timed_out": false,
  "truncated": false
}
```

### Dependency conflict detection

```
check_dependency_conflicts([("coq-mathcomp-ssreflect", ">= 2.0"), ("coq-stdpp", ">= 1.9")])

Result:
{
  "satisfiable": false,
  "conflicts": [
    {
      "package": "coq",
      "constraints": [
        {"required_by": "coq-mathcomp-ssreflect", "constraint": ">= 8.18"},
        {"required_by": "coq-stdpp", "constraint": "= 8.17.1"}
      ]
    }
  ]
}
```

## 10. Language-Specific Notes (Python)

- Use `asyncio.create_subprocess_exec` for subprocess management, enabling async timeout enforcement without blocking the event loop.
- Use `asyncio.wait_for` with `process.communicate()` for timeout handling.
- Use `pathlib.Path` for all filesystem operations (directory probing, file enumeration, path construction).
- Use `re` module with compiled patterns for error parsing.
- Error explanation templates: dictionary mapping category string to `(explanation_template, fix_template)` pairs with `str.format` placeholders.
- Package location: `src/poule/build/`.
- Entry points:
  - `def detect_build_system(project_dir: Path) -> DetectionResult`
  - `async def execute_build(request: BuildRequest) -> BuildResult`
  - `def generate_coq_project(project_dir: Path, logical_name: str | None = None, extra_flags: list[str] | None = None) -> Path`
  - `def generate_dune_project(project_dir: Path, logical_name: str | None = None) -> list[Path]`
  - `def generate_opam_file(project_dir: Path, metadata: OpamMetadata) -> Path`
  - `def migrate_to_dune(project_dir: Path) -> MigrationResult`
  - `async def query_installed_packages() -> list[tuple[str, str]]`
  - `async def query_package_info(package_name: str) -> PackageInfo`
  - `async def install_package(package_name: str, version_constraint: str | None = None) -> BuildResult`
  - `def add_dependency(project_dir: Path, package_name: str, version_constraint: str | None = None) -> None`
  - `async def check_dependency_conflicts(dependencies: list[tuple[str, str | None]]) -> DependencyStatus`

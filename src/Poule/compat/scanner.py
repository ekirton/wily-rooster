"""Dependency scanning from project files (spec section 4.1)."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

from Poule.build.detection import detect_build_system
from Poule.compat.errors import (
    INVALID_PARAMETER,
    NO_DEPENDENCIES,
    PROJECT_NOT_FOUND,
    CompatError,
)
from Poule.compat.types import DeclaredDependency, DependencySet

# Pattern for opam depends field entries: "pkg-name" or "pkg-name" {constraint}
_OPAM_DEP_RE = re.compile(
    r'"([^"]+)"'            # package name in quotes
    r'(?:\s*\{([^}]*)\})?'  # optional constraint in braces
)

# Pattern for dune-project depends entries
_DUNE_DEP_SIMPLE_RE = re.compile(r"^\s*([a-zA-Z][a-zA-Z0-9_.-]*)\s*$")
_DUNE_DEP_CONSTRAINED_RE = re.compile(
    r"^\s*\(([a-zA-Z][a-zA-Z0-9_.-]*)\s+\((.+)\)\)\s*$"
)


async def _opam_package_exists(package_name: str) -> bool:
    """Check if a package exists in the opam repository."""
    opam = shutil.which("opam")
    if opam is None:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            opam, "show", "--field=name", package_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return proc.returncode == 0 and len(stdout.strip()) > 0
    except (asyncio.TimeoutError, OSError):
        return False


def _parse_opam_depends(content: str, source_file: str) -> list[DeclaredDependency]:
    """Parse dependencies from an opam file's depends field."""
    deps: list[DeclaredDependency] = []
    # Find the depends block
    depends_match = re.search(r"depends:\s*\[([^\]]*)\]", content, re.DOTALL)
    if not depends_match:
        return deps
    depends_block = depends_match.group(1)
    for m in _OPAM_DEP_RE.finditer(depends_block):
        pkg = m.group(1)
        constraint = m.group(2)
        if constraint:
            constraint = constraint.strip()
        else:
            constraint = None
        deps.append(DeclaredDependency(
            package_name=pkg,
            version_constraint=constraint,
            source_file=source_file,
            hypothetical=False,
        ))
    return deps


def _parse_dune_depends(content: str, source_file: str) -> list[DeclaredDependency]:
    """Parse dependencies from a dune-project file."""
    deps: list[DeclaredDependency] = []
    # Find (depends ...) stanza using balanced paren matching
    depends_block = _extract_sexp_body(content, "depends")
    if depends_block is None:
        return deps
    # Split into individual entries
    # Handle both simple names and (name (constraint)) forms
    # Process token by token using a simple s-expression parser
    entries = _parse_dune_depends_entries(depends_block)
    for name, constraint in entries:
        deps.append(DeclaredDependency(
            package_name=name,
            version_constraint=constraint,
            source_file=source_file,
            hypothetical=False,
        ))
    return deps


def _extract_sexp_body(content: str, keyword: str) -> str | None:
    """Extract the body of a top-level s-expression like (keyword ...)."""
    idx = content.find(f"({keyword}")
    if idx == -1:
        return None
    # Find the matching close paren
    start = idx + len(f"({keyword}")
    depth = 1
    i = start
    while i < len(content) and depth > 0:
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return content[start : i - 1]


def _parse_dune_depends_entries(block: str) -> list[tuple[str, str | None]]:
    """Parse individual entries from a dune depends block."""
    entries: list[tuple[str, str | None]] = []
    # Tokenize the block into s-expressions
    tokens = _tokenize_sexp(block)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if isinstance(tok, str):
            # Simple package name
            entries.append((tok, None))
            i += 1
        elif isinstance(tok, list):
            # (name constraint) form
            if len(tok) >= 1:
                name = tok[0] if isinstance(tok[0], str) else str(tok[0])
                constraint = None
                if len(tok) >= 2:
                    constraint = _sexp_to_constraint(tok[1:])
                entries.append((name, constraint))
            i += 1
        else:
            i += 1
    return entries


def _tokenize_sexp(s: str) -> list:
    """Simple s-expression tokenizer."""
    tokens: list = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c == "(":
            # Find matching close paren
            depth = 1
            start = i + 1
            i += 1
            while i < len(s) and depth > 0:
                if s[i] == "(":
                    depth += 1
                elif s[i] == ")":
                    depth -= 1
                i += 1
            inner = s[start : i - 1]
            tokens.append(_tokenize_sexp(inner))
        elif c == ")":
            i += 1
        else:
            # Read a word
            start = i
            while i < len(s) and not s[i].isspace() and s[i] not in ("(", ")"):
                i += 1
            tokens.append(s[start:i])
    return tokens


def _sexp_to_constraint(parts: list) -> str | None:
    """Convert dune constraint s-expression parts to a string."""
    if not parts:
        return None
    # Reconstruct as opam-style constraint
    result_parts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            result_parts.append(part)
        elif isinstance(part, list):
            # (op version) form
            if len(part) >= 2:
                op = part[0] if isinstance(part[0], str) else ""
                ver = part[1] if isinstance(part[1], str) else ""
                result_parts.append(f'{op} "{ver}"')
    if result_parts:
        return " & ".join(result_parts)
    return None


async def _infer_from_coq_project(
    content: str, source_file: str
) -> list[DeclaredDependency]:
    """Infer opam packages from _CoqProject -Q and -R flags (spec §4.1)."""
    deps: list[DeclaredDependency] = []
    # Parse -Q and -R flags: -Q dir LogicalRoot or -R dir LogicalRoot
    flag_re = re.compile(r"-[QR]\s+\S+\s+(\S+)")
    for m in flag_re.finditer(content):
        logical_root = m.group(1)
        # Generate candidate package names
        candidates = _logical_root_to_candidates(logical_root)
        # Check which candidates exist
        found: list[str] = []
        for candidate in candidates:
            if await _opam_package_exists(candidate):
                found.append(candidate)
        if found:
            for pkg in found:
                deps.append(DeclaredDependency(
                    package_name=pkg,
                    version_constraint=None,
                    source_file=source_file,
                    hypothetical=False,
                ))
        else:
            # Primary candidate goes to unknown_packages (handled by caller)
            primary = f"coq-{logical_root.lower()}"
            deps.append(DeclaredDependency(
                package_name=primary,
                version_constraint=None,
                source_file=source_file,
                hypothetical=False,
            ))
    return deps


def _logical_root_to_candidates(logical_root: str) -> list[str]:
    """Convert a logical root to candidate opam package names (spec §4.1).

    Algorithm:
    1. Lowercase the root, prepend 'coq-' prefix
    2. For multi-segment roots (Mathcomp.Algebra), try top-level segment as glob prefix
    """
    candidates: list[str] = []
    root_lower = logical_root.lower()
    # Primary candidate: coq-<root_lower>
    primary = f"coq-{root_lower}"
    candidates.append(primary)
    # If root has segments (e.g., Mathcomp.Algebra), try top-level
    if "." in logical_root:
        top_segment = logical_root.split(".")[0].lower()
        # Try coq-<top>-ssreflect (common pattern for mathcomp)
        top_candidate = f"coq-{top_segment}-ssreflect"
        if top_candidate not in candidates:
            candidates.append(top_candidate)
    else:
        # Single segment: also try coq-<root>-ssreflect for libraries like Mathcomp
        ssreflect = f"coq-{root_lower}-ssreflect"
        if ssreflect not in candidates:
            candidates.append(ssreflect)
    return candidates


async def scan_dependencies(
    project_dir: Path,
    hypothetical_additions: list[str] | None = None,
) -> DependencySet:
    """Scan a project directory for dependency declarations.

    REQUIRES: project_dir is an absolute path to an existing directory.
    ENSURES: Returns a DependencySet with all declared and hypothetical dependencies.
    MAINTAINS: No project files are modified.
    """
    project_dir = Path(project_dir)
    hypothetical_additions = hypothetical_additions or []

    # Validate inputs
    if not project_dir.exists() or not project_dir.is_dir():
        raise CompatError(
            PROJECT_NOT_FOUND,
            f"Project directory does not exist or is not a directory: {project_dir}",
        )

    for h in hypothetical_additions:
        if not h or not h.strip():
            raise CompatError(
                INVALID_PARAMETER,
                f"Empty string in hypothetical_additions",
            )

    # Detect build system using the Build System Adapter
    from Poule.build.detection import detect_build_system as _detect
    detection = _detect(project_dir)
    build_system = detection.build_system.value

    # Scan all project files for dependencies
    all_deps: list[DeclaredDependency] = []
    unknown_packages: list[str] = []

    # Scan .opam files
    for p in project_dir.iterdir():
        if p.suffix == ".opam" and p.is_file():
            content = p.read_text()
            deps = _parse_opam_depends(content, str(p.resolve()))
            all_deps.extend(deps)

    # Scan dune-project
    dune_project = project_dir / "dune-project"
    if dune_project.exists():
        content = dune_project.read_text()
        deps = _parse_dune_depends(content, str(dune_project.resolve()))
        all_deps.extend(deps)

    # Scan _CoqProject
    coq_project = project_dir / "_CoqProject"
    if coq_project.exists():
        content = coq_project.read_text()
        deps = await _infer_from_coq_project(content, str(coq_project.resolve()))
        all_deps.extend(deps)

    # Add hypothetical additions (§4.1)
    # Always include hypothetical packages in dependencies for analysis.
    # Also validate against opam and track unknowns (§7.2).
    for pkg_name in hypothetical_additions:
        all_deps.append(DeclaredDependency(
            package_name=pkg_name,
            version_constraint=None,
            source_file="<hypothetical>",
            hypothetical=True,
        ))
        exists = await _opam_package_exists(pkg_name)
        if not exists:
            unknown_packages.append(pkg_name)

    # Check if we have any dependencies at all
    if not all_deps:
        raise CompatError(
            NO_DEPENDENCIES,
            f"No dependency declarations found in {project_dir}",
        )

    # Validate all package names against the opam repository (§4.1).
    # Unknown packages are tracked but don't block analysis for other deps.
    for dep in all_deps:
        if dep.hypothetical:
            continue  # already validated above
        if dep.package_name in unknown_packages:
            continue  # already flagged
        exists = await _opam_package_exists(dep.package_name)
        if not exists:
            unknown_packages.append(dep.package_name)

    # Filter out non-hypothetical deps that are unknown.
    # Hypothetical additions are always kept (explicitly requested by user).
    validated_deps = [
        d for d in all_deps
        if d.hypothetical or d.package_name not in unknown_packages
    ]

    if not validated_deps and unknown_packages:
        raise CompatError(
            NO_DEPENDENCIES,
            f"No valid dependencies found; unknown packages: {', '.join(unknown_packages)}",
        )

    if not validated_deps:
        raise CompatError(
            NO_DEPENDENCIES,
            f"No dependency declarations found in {project_dir}",
        )

    return DependencySet(
        dependencies=validated_deps,
        project_dir=str(project_dir.resolve()),
        build_system=build_system,
        unknown_packages=unknown_packages,
    )

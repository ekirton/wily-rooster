"""Opam metadata resolution with transitive expansion (spec section 4.2)."""

from __future__ import annotations

import asyncio
import re
import shutil

from Poule.compat.errors import TOOL_NOT_FOUND, CompatError
from Poule.compat.parser import parse_constraint
from Poule.compat.types import (
    ConstraintEdge,
    DependencySet,
    PackageNode,
    ResolvedConstraintTree,
    VersionConstraint,
)

# Pattern for parsing depends field from opam show output
_OPAM_DEP_RE = re.compile(r'"([^"]+)"(?:\s*\{([^}]*)\})?')


async def _opam_show(package: str) -> dict[str, str]:
    """Query opam show for a single package.

    Returns dict with 'depends', 'version', 'all-versions' keys.
    """
    opam = shutil.which("opam")
    if opam is None:
        raise CompatError(TOOL_NOT_FOUND, "opam is not on PATH")

    proc = await asyncio.create_subprocess_exec(
        opam, "show", "--field=depends:,version:,all-versions:",
        package,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)

    result: dict[str, str] = {"depends": "", "version": "", "all-versions": ""}
    output = stdout.decode("utf-8", errors="replace")
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("depends:"):
            result["depends"] = line[len("depends:"):].strip()
        elif line.startswith("version:"):
            result["version"] = line[len("version:"):].strip()
        elif line.startswith("all-versions:"):
            result["all-versions"] = line[len("all-versions:"):].strip()
    return result


def _parse_depends_field(depends_str: str) -> list[tuple[str, str | None]]:
    """Parse an opam depends string into (package, constraint|None) pairs."""
    result: list[tuple[str, str | None]] = []
    for m in _OPAM_DEP_RE.finditer(depends_str):
        pkg = m.group(1)
        constraint = m.group(2)
        if constraint:
            constraint = constraint.strip()
        else:
            constraint = None
        result.append((pkg, constraint))
    return result


def _parse_all_versions(versions_str: str) -> list[str]:
    """Parse all-versions string into a descending-sorted list."""
    versions = [v.strip() for v in versions_str.split() if v.strip()]
    # opam lists versions in ascending order; reverse for descending
    versions.reverse()
    return versions


async def resolve_metadata(
    dependency_set: DependencySet,
    timeout: int = 30,
) -> ResolvedConstraintTree:
    """Resolve opam metadata for all dependencies, building a constraint tree.

    REQUIRES: dependency_set has at least one dependency. opam is on PATH.
    ENSURES: Returns a ResolvedConstraintTree with transitive dependencies.
    MAINTAINS: Only read-only opam commands invoked.
    """
    # Check opam is available
    if shutil.which("opam") is None:
        raise CompatError(TOOL_NOT_FOUND, "opam is not on PATH")

    root_deps = [d.package_name for d in dependency_set.dependencies]
    nodes: dict[str, PackageNode] = {}
    edges: list[ConstraintEdge] = []
    cache: dict[str, dict[str, str]] = {}
    visited: set[str] = set()

    async def _resolve_package(pkg_name: str) -> None:
        """Recursively resolve a package and its transitive dependencies."""
        if pkg_name in visited:
            return  # cycle detection
        visited.add(pkg_name)

        # Query opam (with cache)
        if pkg_name in cache:
            info = cache[pkg_name]
        else:
            try:
                info = await _opam_show(pkg_name)
                cache[pkg_name] = info
            except asyncio.TimeoutError:
                # Record timeout, continue
                nodes[pkg_name] = PackageNode(
                    name=pkg_name, available_versions=[], installed_version=None,
                )
                return
            except CompatError:
                raise
            except Exception:
                nodes[pkg_name] = PackageNode(
                    name=pkg_name, available_versions=[], installed_version=None,
                )
                return

        # Build node
        all_versions = _parse_all_versions(info.get("all-versions", ""))
        installed = info.get("version", "").strip() or None
        nodes[pkg_name] = PackageNode(
            name=pkg_name,
            available_versions=all_versions,
            installed_version=installed,
        )

        # Parse dependencies and create edges
        dep_pairs = _parse_depends_field(info.get("depends", ""))
        for dep_name, raw_constraint in dep_pairs:
            if raw_constraint:
                try:
                    constraint = parse_constraint(raw_constraint)
                except CompatError:
                    constraint = VersionConstraint(intervals=[])
            else:
                constraint = VersionConstraint(
                    intervals=[__import__("Poule.compat.types", fromlist=["VersionInterval"]).VersionInterval()]
                )

            edges.append(ConstraintEdge(
                from_package=pkg_name,
                to_package=dep_name,
                constraint=constraint,
                raw_constraint=raw_constraint or "",
            ))

            # Recursively resolve transitive dependency
            await _resolve_package(dep_name)

    # Resolve all root dependencies
    for dep in dependency_set.dependencies:
        await _resolve_package(dep.package_name)

    return ResolvedConstraintTree(
        root_dependencies=root_deps,
        nodes=nodes,
        edges=edges,
    )

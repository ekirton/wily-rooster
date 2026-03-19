"""Conflict detection via constraint intersection (spec section 4.4)."""

from __future__ import annotations

from collections import defaultdict
from typing import Union

from Poule.compat.types import (
    CompatibleSet,
    Conflict,
    ConflictSet,
    ConstraintEdge,
    ResolvedConstraintTree,
    VersionConstraint,
    VersionInterval,
)
from Poule.compat.versions import compare_versions, intersect, is_empty, version_in_constraint
from Poule.compat.parser import parse_constraint


def detect_conflicts(
    tree: ResolvedConstraintTree,
    target_coq_version: str | None = None,
) -> Union[ConflictSet, CompatibleSet]:
    """Detect version conflicts in a resolved constraint tree.

    REQUIRES: tree is a valid ResolvedConstraintTree.
    ENSURES: Returns ConflictSet if incompatible, CompatibleSet if compatible.
    MAINTAINS: The constraint tree is not modified.
    """
    # Collect constraints per target package (shared resources)
    constraints_by_resource: dict[str, list[ConstraintEdge]] = defaultdict(list)
    for edge in tree.edges:
        constraints_by_resource[edge.to_package].append(edge)

    # If target_coq_version is specified, add a pin constraint
    if target_coq_version is not None:
        pin_constraint = VersionConstraint(intervals=[
            VersionInterval(
                lower=__import__("Poule.compat.types", fromlist=["VersionBound"]).VersionBound(target_coq_version, True),
                upper=__import__("Poule.compat.types", fromlist=["VersionBound"]).VersionBound(target_coq_version, True),
            ),
        ])
        constraints_by_resource["coq"].append(ConstraintEdge(
            from_package="<target-pin>",
            to_package="coq",
            constraint=pin_constraint,
            raw_constraint=f'= "{target_coq_version}"',
        ))

    # Find shared resources (constrained by more than one edge)
    shared_resources: dict[str, list[ConstraintEdge]] = {}
    for resource, edges in constraints_by_resource.items():
        if len(edges) >= 2:
            shared_resources[resource] = edges

    # If no shared resources, everything is compatible
    if not shared_resources:
        version_map = _build_version_map(tree, constraints_by_resource)
        coq_range = _compute_coq_range(constraints_by_resource.get("coq", []))
        return CompatibleSet(
            verdict="compatible",
            version_map=version_map,
            coq_version_range=coq_range,
        )

    # Check each shared resource for conflicts
    conflicts: list[Conflict] = []
    version_map: dict[str, str] = {}

    for resource, edges in shared_resources.items():
        # Compute intersection of all constraints on this resource
        combined = edges[0].constraint
        for edge in edges[1:]:
            combined = intersect(combined, edge.constraint)

        # Check if any available version satisfies the combined constraint
        node = tree.nodes.get(resource)
        available = node.available_versions if node else []
        satisfying = [v for v in available if version_in_constraint(v, combined)]

        if not satisfying:
            # Conflict: no version satisfies all constraints
            conflicts.append(Conflict(
                resource=resource,
                minimal_constraint_set=list(edges),
                explanation=None,
                resolutions=[],
            ))
        else:
            # Compatible: pick the newest version
            version_map[resource] = satisfying[0]

    if conflicts:
        return ConflictSet(verdict="incompatible", conflicts=conflicts)

    # All shared resources are satisfiable
    # Fill in non-shared resources too
    for resource, edges in constraints_by_resource.items():
        if resource not in version_map:
            node = tree.nodes.get(resource)
            if node and node.available_versions:
                # Pick newest that satisfies single constraint
                if edges:
                    for v in node.available_versions:
                        if version_in_constraint(v, edges[0].constraint):
                            version_map[resource] = v
                            break
                    else:
                        version_map[resource] = node.available_versions[0]
                else:
                    version_map[resource] = node.available_versions[0]

    # Also include root deps in version_map
    for pkg_name in tree.root_dependencies:
        if pkg_name not in version_map:
            node = tree.nodes.get(pkg_name)
            if node and node.available_versions:
                version_map[pkg_name] = node.available_versions[0]

    coq_range = _compute_coq_range(constraints_by_resource.get("coq", []))
    return CompatibleSet(
        verdict="compatible",
        version_map=version_map,
        coq_version_range=coq_range,
    )


def _build_version_map(
    tree: ResolvedConstraintTree,
    constraints_by_resource: dict[str, list[ConstraintEdge]],
) -> dict[str, str]:
    """Build version_map for the simple case (no shared resources)."""
    version_map: dict[str, str] = {}
    for pkg_name, node in tree.nodes.items():
        if node.available_versions:
            edges = constraints_by_resource.get(pkg_name, [])
            if edges:
                for v in node.available_versions:
                    if version_in_constraint(v, edges[0].constraint):
                        version_map[pkg_name] = v
                        break
                else:
                    version_map[pkg_name] = node.available_versions[0]
            else:
                version_map[pkg_name] = node.available_versions[0]
    return version_map


def _compute_coq_range(coq_edges: list[ConstraintEdge]) -> VersionConstraint:
    """Compute the combined Coq version range from all constraints."""
    if not coq_edges:
        return VersionConstraint(intervals=[VersionInterval()])
    combined = coq_edges[0].constraint
    for edge in coq_edges[1:]:
        combined = intersect(combined, edge.constraint)
    return combined

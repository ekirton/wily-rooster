"""Resolution suggestion for conflicts (spec section 4.6)."""

from __future__ import annotations

import asyncio
from typing import Optional

from Poule.compat.errors import CompatError
from Poule.compat.parser import parse_constraint
from Poule.compat.types import (
    Conflict,
    ConstraintEdge,
    Resolution,
    ResolvedConstraintTree,
    VersionConstraint,
)
from Poule.compat.versions import intersect, is_empty


async def _check_newer_version_resolves(
    pkg_name: str,
    available_versions: list[str],
    current_constraint: VersionConstraint,
    other_constraints: list[ConstraintEdge],
    resource: str,
) -> Optional[Resolution]:
    """Check if a newer version of pkg relaxes its constraint on resource."""
    from Poule.compat.resolver import _opam_show

    node_versions = available_versions
    if not node_versions or len(node_versions) <= 1:
        return None

    # Check newer versions (they're in descending order)
    current_version = node_versions[-1] if node_versions else None
    for newer_version in node_versions:
        if newer_version == current_version:
            continue
        try:
            info = await _opam_show(pkg_name)
            depends_str = info.get("depends", "")
            # Parse the depends for the resource
            from Poule.compat.resolver import _parse_depends_field
            dep_pairs = _parse_depends_field(depends_str)
            for dep_name, raw in dep_pairs:
                if dep_name == resource and raw:
                    try:
                        new_constraint = parse_constraint(raw)
                    except CompatError:
                        continue
                    # Check if new constraint is compatible with others
                    combined = new_constraint
                    for other_edge in other_constraints:
                        combined = intersect(combined, other_edge.constraint)
                    if not is_empty(combined):
                        return Resolution(
                            strategy="UPGRADE",
                            target_package=pkg_name,
                            target_version=newer_version,
                            alternative_package=None,
                            trade_off=f"Upgrading {pkg_name} to {newer_version} may resolve the conflict, but may introduce API changes.",
                        )
        except Exception:
            continue
        # Only try the first newer version for now
        break

    return None


async def suggest_resolutions(
    conflict: Conflict,
    tree: ResolvedConstraintTree,
) -> list[Resolution]:
    """Suggest resolutions for a conflict.

    REQUIRES: conflict is a Conflict. tree is the ResolvedConstraintTree.
    ENSURES: Returns a sorted list of Resolution (UPGRADE, DOWNGRADE, ALTERNATIVE, NO_RESOLUTION).
    MAINTAINS: Read-only — no project files or opam state modified.
    """
    resolutions: list[Resolution] = []
    resource = conflict.resource
    edges = conflict.minimal_constraint_set

    # For each constraining package, check if upgrading resolves the conflict
    for i, edge in enumerate(edges):
        other_edges = [e for j, e in enumerate(edges) if j != i]
        pkg_name = edge.from_package
        node = tree.nodes.get(pkg_name)
        if node and len(node.available_versions) > 1:
            resolution = await _check_newer_version_resolves(
                pkg_name,
                node.available_versions,
                edge.constraint,
                other_edges,
                resource,
            )
            if resolution is not None:
                resolutions.append(resolution)

    # If no resolutions found, emit NO_RESOLUTION
    if not resolutions:
        resolutions.append(Resolution(
            strategy="NO_RESOLUTION",
            target_package=edges[0].from_package if edges else resource,
            target_version=None,
            alternative_package=None,
            trade_off=f"No compatible combination exists within available package versions for {resource}.",
        ))

    # Sort: UPGRADE, DOWNGRADE, ALTERNATIVE, NO_RESOLUTION
    strategy_order = {"UPGRADE": 0, "DOWNGRADE": 1, "ALTERNATIVE": 2, "NO_RESOLUTION": 3}
    resolutions.sort(key=lambda r: strategy_order.get(r.strategy, 99))

    return resolutions

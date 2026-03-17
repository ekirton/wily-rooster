"""Dependency extraction from expression trees.

Extracts ``uses`` edges from LConst nodes and ``instance_of`` edges
from instance metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from poule.models.tree import ExprTree

from poule.models.labels import LConst


def extract_dependencies(
    tree: ExprTree,
    decl_name: str,
    instance_metadata: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Extract dependency edges from an expression tree.

    Returns a list of ``(target_name, relation)`` tuples where:
    - ``"uses"`` edges come from all ``LConst`` nodes (excluding self-references)
    - ``"instance_of"`` edges come from *instance_metadata* (if provided)

    Edges are deduplicated. Self-references (where ``target_name == decl_name``)
    are excluded from ``uses`` edges.
    """
    from poule.models.tree import TreeNode

    seen: set[str] = set()

    def _walk(node: TreeNode) -> None:
        label = node.label
        if isinstance(label, LConst) and label.name != decl_name:
            seen.add(label.name)
        for child in node.children:
            _walk(child)

    _walk(tree.root)

    result: list[tuple[str, str]] = [(name, "uses") for name in sorted(seen)]

    if instance_metadata:
        instance_seen: set[str] = set()
        for target in instance_metadata:
            if target not in instance_seen:
                instance_seen.add(target)
                result.append((target, "instance_of"))

    return result

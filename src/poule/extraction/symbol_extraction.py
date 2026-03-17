"""Symbol extraction from expression trees.

Extracts fully qualified names from LConst, LInd, and LConstruct nodes
via depth-first traversal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from poule.models.tree import ExprTree

from poule.models.labels import LConst, LConstruct, LInd


def extract_symbols(tree: ExprTree) -> list[str]:
    """Extract sorted, deduplicated symbol names from an expression tree.

    Performs depth-first traversal collecting ``name`` from nodes with
    ``LConst``, ``LInd``, or ``LConstruct`` labels.

    Returns an empty list for a tree with no matching nodes.
    """
    from poule.models.tree import TreeNode

    seen: set[str] = set()

    def _walk(node: TreeNode) -> None:
        label = node.label
        if isinstance(label, (LConst, LInd)):
            seen.add(label.name)
        elif isinstance(label, LConstruct):
            seen.add(label.name)
        for child in node.children:
            _walk(child)

    _walk(tree.root)
    return sorted(seen)

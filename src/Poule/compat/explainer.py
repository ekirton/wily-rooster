"""Explanation building for conflicts (spec section 4.5)."""

from __future__ import annotations

from Poule.compat.types import Conflict, ExplanationText


def build_explanation(conflict: Conflict) -> ExplanationText:
    """Build a plain-language explanation for a conflict.

    REQUIRES: conflict has a non-empty minimal_constraint_set.
    ENSURES: Returns an ExplanationText with summary and constraint chains.
    MAINTAINS: Deterministic — same conflict always produces same explanation.
    """
    resource = conflict.resource
    edges = conflict.minimal_constraint_set

    # Build constraint chains — one per edge in the minimal conflict set
    chains: list[list[str]] = []
    package_names: list[str] = []

    for edge in edges:
        chain: list[str] = []
        chain.append(edge.from_package)
        constraint_desc = f"requires {edge.to_package} {edge.raw_constraint}"
        chain.append(constraint_desc)
        chains.append(chain)
        package_names.append(edge.from_package)

    # Build summary
    if len(package_names) == 2:
        summary = (
            f"{package_names[0]} and {package_names[1]} have incompatible "
            f"requirements on {resource} -- there is no {resource} version "
            f"that satisfies both."
        )
    else:
        pkg_list = ", ".join(package_names[:-1]) + f" and {package_names[-1]}"
        summary = (
            f"{pkg_list} have incompatible requirements on {resource} -- "
            f"there is no {resource} version that satisfies all constraints."
        )

    return ExplanationText(summary=summary, constraint_chains=chains)

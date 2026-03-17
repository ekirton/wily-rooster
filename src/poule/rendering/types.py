"""Types for the Mermaid rendering module.

Spec: specification/mermaid-renderer.md §5
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DetailLevel(Enum):
    """Controls how much proof state information appears in a diagram."""

    SUMMARY = "summary"
    STANDARD = "standard"
    DETAILED = "detailed"


@dataclass
class RenderedDiagram:
    """Return type for render_dependencies."""

    mermaid: str
    node_count: int
    truncated: bool


@dataclass
class SequenceEntry:
    """A single entry in a proof sequence rendering."""

    step_index: int
    tactic: Optional[str]
    mermaid: str

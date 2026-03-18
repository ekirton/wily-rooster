"""Data types for Hammer Automation.

Spec: specification/hammer-automation.md section 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from poule.session.types import ProofState


@dataclass
class StrategyDiagnostic:
    """Diagnostic information for a single strategy attempt."""

    strategy: str  # "hammer" | "sauto" | "qauto"
    failure_reason: str  # "timeout" | "no_proof_found" | "reconstruction_failed" | "tactic_error"
    detail: str
    partial_progress: Optional[str]
    wall_time_ms: int
    timeout_used: float


@dataclass
class ClassifiedOutput:
    """Output of the Result Interpreter (interpret_result).

    Classifies raw Coq output into a structured result that the caller
    uses to build a StrategyDiagnostic (on failure) or populate success
    fields of a HammerResult (on success).
    """

    classification: str  # "success" | "timeout" | "no_proof_found" | "reconstruction_failed" | "tactic_error"
    detail: Optional[str] = None
    partial_progress: Optional[str] = None


@dataclass
class HammerResult:
    """Output of a hammer automation invocation."""

    status: str  # "success" | "failure"
    proof_script: Optional[str]
    atp_proof: Optional[str]
    strategy_used: Optional[str]  # "hammer" | "sauto" | "qauto" | None
    state: ProofState
    diagnostics: list[StrategyDiagnostic] = field(default_factory=list)
    wall_time_ms: int = 0

"""Result Interpreter for Hammer Automation.

Classifies Coq output into structured failure reasons.

Spec: specification/hammer-automation.md section 4.7.
"""

from __future__ import annotations

from poule.hammer.types import ClassifiedOutput
from poule.session.types import ProofState


def interpret_result(coq_output: str, proof_state: ProofState) -> ClassifiedOutput:
    """Classify Coq output into a ClassifiedOutput.

    REQUIRES: coq_output is raw text from the Proof Session Manager.
              proof_state is the ProofState observed after submission.
    ENSURES: Returns a ClassifiedOutput per spec section 4.7 mapping table.
    """
    # Success: goal closed in proof_state_after
    if proof_state.is_complete:
        return ClassifiedOutput(classification="success")

    output_lower = coq_output.lower()

    # Timeout
    if "timeout" in output_lower:
        return ClassifiedOutput(
            classification="timeout",
            detail=coq_output,
        )

    # No proof found / hammer failed
    if "no proof found" in output_lower or "hammer failed" in output_lower:
        return ClassifiedOutput(
            classification="no_proof_found",
            detail=coq_output,
        )

    # Reconstruction failed with ATP proof
    if "reconstruction failed" in output_lower:
        lines = coq_output.split("\n")
        atp_lines = []
        found_reconstruction = False
        for line in lines:
            if found_reconstruction:
                atp_lines.append(line)
            elif "reconstruction failed" in line.lower():
                found_reconstruction = True
        partial = "\n".join(atp_lines).strip() if atp_lines else None
        return ClassifiedOutput(
            classification="reconstruction_failed",
            detail=coq_output,
            partial_progress=partial or None,
        )

    # Fallback: tactic_error
    return ClassifiedOutput(
        classification="tactic_error",
        detail=coq_output,
    )

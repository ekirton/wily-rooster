"""Contract tests for Literate Documentation.

These tests exercise the real Alectryon tool to verify mock/real parity.

Spec: specification/literate-documentation.md
Architecture: doc/architecture/literate-documentation.md
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_types():
    from Poule.documentation.types import (
        DocumentationRequest,
        DocumentationResult,
        BatchDocumentationRequest,
        BatchDocumentationResult,
        FileOutcome,
    )
    return (
        DocumentationRequest,
        DocumentationResult,
        BatchDocumentationRequest,
        BatchDocumentationResult,
        FileOutcome,
    )


def _import_adapter():
    from Poule.documentation.adapter import (
        check_availability,
        generate_documentation,
        generate_proof_documentation,
        generate_batch_documentation,
    )
    return (
        check_availability,
        generate_documentation,
        generate_proof_documentation,
        generate_batch_documentation,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_documentation_request(
    input_file="/project/src/Lemmas.v",
    proof_name=None,
    output_path=None,
    format="html",
    custom_flags=None,
    timeout=120,
):
    DocumentationRequest = _import_types()[0]
    return DocumentationRequest(
        input_file=input_file,
        proof_name=proof_name,
        output_path=output_path,
        format=format,
        custom_flags=custom_flags if custom_flags is not None else [],
        timeout=timeout,
    )


def _make_batch_request(
    source_directory="/project/src/",
    output_directory="/docs/",
    format="html",
    custom_flags=None,
    timeout_per_file=120,
):
    BatchDocumentationRequest = _import_types()[2]
    return BatchDocumentationRequest(
        source_directory=source_directory,
        output_directory=output_directory,
        format=format,
        custom_flags=custom_flags if custom_flags is not None else [],
        timeout_per_file=timeout_per_file,
    )


# ===========================================================================
# Contract: Availability Detection -- Section 4.1
# ===========================================================================

class TestAvailabilityDetectionContract:
    """Contract tests for check_availability against system Alectryon."""

    @pytest.mark.asyncio
    async def test_contract_check_availability_real(self):
        """Contract test: real check_availability against system Alectryon."""
        check_availability, _, _, _ = _import_adapter()
        result = await check_availability(_bypass_cache=True)
        assert result in ("available", "not_installed", "version_too_old")


# ===========================================================================
# Contract: Single-File Generation -- Section 4.2
# ===========================================================================

class TestSingleFileGenerationContract:
    """Contract tests for generate_documentation against real Alectryon."""

    @pytest.mark.asyncio
    async def test_contract_generate_documentation_real(self):
        """Contract test: real generate_documentation against Alectryon."""
        _, generate_documentation, _, _ = _import_adapter()
        DocumentationResult = _import_types()[1]

        # Requires a real .v file on disk
        request = _make_documentation_request(
            input_file="/tmp/poule_test_contract.v",
            format="html",
            output_path=None,
        )
        # Write minimal Coq file
        Path("/tmp/poule_test_contract.v").write_text(
            "Lemma trivial : True. Proof. exact I. Qed.\n"
        )
        try:
            result = await generate_documentation(request)
            assert isinstance(result, DocumentationResult)
            assert result.status in ("success", "failure")
        finally:
            Path("/tmp/poule_test_contract.v").unlink(missing_ok=True)


# ===========================================================================
# Contract: Proof-Scoped Generation -- Section 4.3
# ===========================================================================

class TestProofScopedGenerationContract:
    """Contract tests for generate_proof_documentation against real Alectryon."""

    @pytest.mark.asyncio
    async def test_contract_generate_proof_documentation_real(self):
        """Contract test: real proof-scoped generation against Alectryon."""
        _, _, generate_proof_documentation, _ = _import_adapter()
        DocumentationResult = _import_types()[1]

        coq_source = "Lemma trivial : True.\nProof. exact I. Qed.\n"
        Path("/tmp/poule_test_proof_contract.v").write_text(coq_source)

        request = _make_documentation_request(
            input_file="/tmp/poule_test_proof_contract.v",
            proof_name="trivial",
            format="html",
            output_path=None,
        )
        try:
            result = await generate_proof_documentation(request)
            assert isinstance(result, DocumentationResult)
            assert result.status in ("success", "failure")
        finally:
            Path("/tmp/poule_test_proof_contract.v").unlink(missing_ok=True)


# ===========================================================================
# Contract: Batch Generation -- Section 4.4
# ===========================================================================

class TestBatchGenerationContract:
    """Contract tests for generate_batch_documentation against real Alectryon."""

    @pytest.mark.asyncio
    async def test_contract_generate_batch_documentation_real(self):
        """Contract test: real batch generation against Alectryon."""
        _, _, _, generate_batch_documentation = _import_adapter()
        BatchDocumentationResult = _import_types()[3]

        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as out_dir:
            Path(src_dir, "test.v").write_text(
                "Lemma trivial : True. Proof. exact I. Qed.\n"
            )
            request = _make_batch_request(
                source_directory=src_dir,
                output_directory=out_dir,
            )
            result = await generate_batch_documentation(request)
            assert isinstance(result, BatchDocumentationResult)

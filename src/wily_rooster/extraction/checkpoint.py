"""Extraction checkpointing for resume and incremental re-extraction.

Provides checkpoint persistence so that long-running extraction campaigns
can be resumed after interruption and incremental re-extraction can skip
unchanged files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def checkpoint_path_for(output_path: Path) -> Path:
    """Return the checkpoint file path for a given output path.

    Appends ``.checkpoint`` to the full output path (including its suffix).
    """
    return output_path.parent / (output_path.name + ".checkpoint")


def content_hash(data: bytes) -> str:
    """Compute SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def load_checkpoint(checkpoint_path: Path) -> dict:
    """Load and return the checkpoint dict from *checkpoint_path*.

    Raises an exception containing ``CHECKPOINT_CORRUPT`` if the file
    contains invalid JSON.
    """
    text = checkpoint_path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"CHECKPOINT_CORRUPT: {exc}") from exc


def try_load_checkpoint(checkpoint_path: Path) -> Optional[dict]:
    """Load a checkpoint, returning ``None`` on corruption or missing file.

    Logs a warning when the checkpoint is corrupt or missing.
    """
    try:
        return load_checkpoint(checkpoint_path)
    except (ValueError, FileNotFoundError) as exc:
        logger.warning("Could not load checkpoint %s: %s", checkpoint_path, exc)
        return None


def update_checkpoint(
    checkpoint_path: Path,
    theorem_name: str,
    source_file: str,
    content_hash: str,
    position: dict,
    file_theorems: Optional[list[str]] = None,
) -> None:
    """Record a completed theorem in the checkpoint and write to disk.

    Parameters
    ----------
    checkpoint_path:
        Path to the checkpoint JSON file (must already exist).
    theorem_name:
        Fully-qualified theorem name.
    source_file:
        Source file the theorem belongs to.
    content_hash:
        Content hash for the source file.
    position:
        Current position dict with ``project_index``, ``file_index``,
        ``theorem_index``.
    file_theorems:
        If provided, the full list of theorem names in *source_file*.
        When all are present in ``completed_proofs``, the file is marked
        complete in ``completed_files``.
    """
    ckpt = load_checkpoint(checkpoint_path)

    ckpt["completed_proofs"][theorem_name] = content_hash
    ckpt["last_position"] = position

    if file_theorems is not None:
        if all(t in ckpt["completed_proofs"] for t in file_theorems):
            ckpt["completed_files"][source_file] = content_hash

    checkpoint_path.write_text(json.dumps(ckpt), encoding="utf-8")


def classify_file(
    file_path: str,
    current_hash: Optional[str],
    checkpoint_files: dict[str, str],
) -> str:
    """Classify a single file relative to checkpoint state.

    Returns one of ``"unchanged"``, ``"changed"``, ``"new"``, ``"removed"``.
    """
    if current_hash is None:
        if file_path in checkpoint_files:
            return "removed"
        return "new"

    if file_path not in checkpoint_files:
        return "new"

    if checkpoint_files[file_path] == current_hash:
        return "unchanged"

    return "changed"


def classify_files(
    current_files: dict[str, str],
    checkpoint_files: dict[str, str],
) -> dict[str, str]:
    """Classify every file in *current_files* and *checkpoint_files*.

    Returns a dict mapping file path to one of
    ``"unchanged"``, ``"changed"``, ``"new"``, ``"removed"``.
    """
    result: dict[str, str] = {}

    for path, h in current_files.items():
        result[path] = classify_file(path, h, checkpoint_files)

    # Files in checkpoint but not in current set are removed.
    for path in checkpoint_files:
        if path not in current_files:
            result[path] = classify_file(path, None, checkpoint_files)

    return result


def validate_consistency(
    checkpoint_meta: dict,
    current_projects: list[str],
    coq_version: str,
) -> bool:
    """Return ``True`` if the checkpoint metadata is consistent with the
    current extraction parameters (same projects and Coq version)."""
    if checkpoint_meta.get("projects") != current_projects:
        return False
    if checkpoint_meta.get("coq_version") != coq_version:
        return False
    return True


def merge_outputs(
    prior_records: list[dict],
    new_records: list[dict],
    unchanged_files: set[str],
    file_order: list[str],
) -> list[dict]:
    """Merge prior (reused) records with newly extracted records.

    Records are returned in *file_order* order: for each file in
    *file_order*, records belonging to that file appear in their
    original order.
    """
    # Index records by file.
    by_file: dict[str, list[dict]] = {}
    for rec in prior_records:
        by_file.setdefault(rec["file"], []).append(rec)
    for rec in new_records:
        by_file.setdefault(rec["file"], []).append(rec)

    merged: list[dict] = []
    for f in file_order:
        merged.extend(by_file.get(f, []))

    return merged


def compute_resume_position(last_position: dict, total_files: int) -> dict:
    """Compute the position from which to resume extraction.

    Advances past the last completed theorem: increments ``theorem_index``
    by 1.  If this is still within the same file, the file index stays.
    """
    return {
        "project_index": last_position["project_index"],
        "file_index": last_position["file_index"],
        "theorem_index": last_position["theorem_index"] + 1,
    }


def resume_extract(output_path: Path) -> dict:
    """Load a checkpoint for *output_path* and validate it for resumption.

    Raises
    ------
    FileNotFoundError
        With ``NO_CHECKPOINT`` when the checkpoint file does not exist.
    ValueError
        With ``CHECKPOINT_STALE`` when any project directory listed in
        the checkpoint no longer exists on disk.
    """
    ckpt_path = checkpoint_path_for(output_path)

    if not ckpt_path.exists():
        raise FileNotFoundError(f"NO_CHECKPOINT: {ckpt_path} does not exist")

    ckpt = load_checkpoint(ckpt_path)

    # Verify that all project directories still exist.
    meta = ckpt.get("campaign_metadata", {})
    for proj in meta.get("projects", []):
        if not Path(proj).exists():
            raise ValueError(
                f"CHECKPOINT_STALE: project directory {proj} no longer exists"
            )

    return ckpt


def should_full_extract(output_path: Path, checkpoint_path: Path) -> bool:
    """Return ``True`` if a full (non-incremental) extraction is needed.

    A full extraction is required when:
    - The output file does not exist, or
    - The checkpoint has zero completed proofs.
    """
    if not output_path.exists():
        return True

    try:
        ckpt = load_checkpoint(checkpoint_path)
    except (ValueError, FileNotFoundError):
        return True

    if not ckpt.get("completed_proofs"):
        return True

    return False

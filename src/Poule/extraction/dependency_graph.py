"""Dependency graph extraction from proof traces.

Derives dependency entries from extraction records by collecting premises
across all proof steps, excluding hypotheses, deduplicating by fully
qualified name, and preserving first-appearance order.

Also provides import of premise-based dependency edges into an existing
index database (see ``import_dependencies``).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Union

from Poule.extraction.types import DependencyEntry, DependencyRef

logger = logging.getLogger(__name__)


def extract_dependencies(record: Union[dict, object]) -> DependencyEntry:
    """Extract a DependencyEntry from an ExtractionRecord or dict.

    Collects all premises from all steps, excludes premises with
    kind='hypothesis', deduplicates by fully qualified name keeping
    first occurrence, and preserves first-appearance order across steps.
    """
    if isinstance(record, dict):
        theorem_name = record["theorem_name"]
        source_file = record["source_file"]
        project_id = record["project_id"]
        steps = record.get("steps", [])
    else:
        theorem_name = record.theorem_name
        source_file = record.source_file
        project_id = record.project_id
        steps = record.steps

    seen: set[str] = set()
    depends_on: list[DependencyRef] = []

    for step in steps:
        if isinstance(step, dict):
            premises = step.get("premises", [])
        else:
            premises = step.premises

        for premise in premises:
            if isinstance(premise, dict):
                name = premise["name"]
                kind = premise["kind"]
            else:
                name = premise.name
                kind = premise.kind

            if kind == "hypothesis":
                continue

            if name not in seen:
                seen.add(name)
                depends_on.append(DependencyRef(name=name, kind=kind))

    return DependencyEntry(
        theorem_name=theorem_name,
        source_file=source_file,
        project_id=project_id,
        depends_on=depends_on,
    )


def extract_dependency_graph(input_path: Path, output_path: Path) -> None:
    """Read extraction JSON Lines from input_path, write dependency entries to output_path.

    Skips records with record_type='extraction_error'. Raises ValueError
    with line number for invalid JSON.
    """
    with open(input_path, "r") as inp, open(output_path, "w") as out:
        for line_number, line in enumerate(inp, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON at line {line_number}: {e}"
                ) from e

            if record.get("record_type") == "extraction_error":
                continue

            entry = extract_dependencies(record)
            out.write(entry.to_json() + "\n")


def import_dependencies(
    dependency_graph_path: Path,
    db_path: Path,
) -> int:
    """Import premise-based dependency edges into an existing index database.

    Reads a JSON Lines file of DependencyEntry records (produced by
    ``extract_dependency_graph``) and inserts ``(src, dst, "uses")``
    edges into the ``dependencies`` table.

    Name resolution uses the same multi-strategy approach as
    ``resolve_and_insert_dependencies``: exact match, ``Coq.`` prefix,
    suffix match.

    Returns the number of edges inserted.
    """
    dependency_graph_path = Path(dependency_graph_path)
    db_path = Path(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    # Build name-to-id map from existing index
    rows = conn.execute("SELECT id, name FROM declarations").fetchall()
    name_to_id: dict[str, int] = {name: did for did, name in rows}

    # Build suffix lookup for name resolution
    suffix_to_fqn: dict[str, str | None] = {}
    for fqn in name_to_id:
        parts = fqn.split(".")
        for k in range(1, len(parts)):
            suffix = ".".join(parts[k:])
            if suffix in suffix_to_fqn:
                if suffix_to_fqn[suffix] != fqn:
                    suffix_to_fqn[suffix] = None  # ambiguous
            else:
                suffix_to_fqn[suffix] = fqn

    def _resolve(target_name: str) -> int | None:
        dst_id = name_to_id.get(target_name)
        if dst_id is not None:
            return dst_id
        coq_name = "Coq." + target_name
        dst_id = name_to_id.get(coq_name)
        if dst_id is not None:
            return dst_id
        fqn = suffix_to_fqn.get(target_name)
        if fqn is not None:
            return name_to_id.get(fqn)
        return None

    inserted = 0
    with open(dependency_graph_path, "r") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping invalid JSON at line %d", line_number
                )
                continue

            theorem_name = record.get("theorem_name", "")
            src_id = _resolve(theorem_name)
            if src_id is None:
                continue

            depends_on = record.get("depends_on", [])
            for dep in depends_on:
                dep_name = dep.get("name", "")
                dst_id = _resolve(dep_name)
                if dst_id is None:
                    continue
                if src_id == dst_id:
                    continue
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO dependencies (src, dst, relation) "
                        "VALUES (?, ?, ?)",
                        (src_id, dst_id, "uses"),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass  # duplicate or FK violation — skip

    conn.commit()
    conn.close()
    return inserted

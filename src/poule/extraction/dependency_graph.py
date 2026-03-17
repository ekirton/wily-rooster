"""Dependency graph extraction from proof traces.

Derives dependency entries from extraction records by collecting premises
across all proof steps, excluding hypotheses, deduplicating by fully
qualified name, and preserving first-appearance order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from poule.extraction.types import DependencyEntry, DependencyRef


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

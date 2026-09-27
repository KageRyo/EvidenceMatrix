"""Deterministic machine and human readable report rendering."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from evidencematrix.audit import audit_matrix
from evidencematrix.model import (
    COVERAGE_STATUS_ORDER,
    UNRESOLVED_STATUSES,
    CoverageRecord,
    Manifest,
    Summary,
)

ARTIFACT_NAMES = (
    "coverage_matrix.csv",
    "coverage_report.json",
    "gap_report.json",
    "summary.json",
    "coverage_report.md",
)
CSV_FIELDS = ("entity_id", "source_id", "source_availability", "status", "reason")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def record_to_dict(record: CoverageRecord) -> dict[str, str | None]:
    return {
        "entity_id": record.entity_id,
        "source_id": record.source_id,
        "source_availability": record.source_availability.value,
        "status": record.status.value,
        "reason": record.reason,
    }


def summary_to_dict(summary: Summary) -> dict[str, object]:
    return {
        "schema_version": 1,
        "entity_count": summary.entity_count,
        "source_count": summary.source_count,
        "relationship_count": summary.relationship_count,
        "status_counts": summary.status_counts,
        "finding_count": summary.finding_count,
    }


def audit_to_dict(matrix: tuple[CoverageRecord, ...]) -> dict[str, object]:
    audit = audit_matrix(matrix)
    return {
        "schema_version": 1,
        "relationship_count": audit.relationship_count,
        "finding_count": audit.finding_count,
        "status_counts": {
            status.value: audit.status_counts[status.value]
            for status in COVERAGE_STATUS_ORDER
            if status in UNRESOLVED_STATUSES
        },
        "not_applicable_count": audit.status_counts["not_applicable"],
        "findings": [record_to_dict(item) for item in audit.findings],
    }


def build_artifacts(
    manifest: Manifest,
    matrix: tuple[CoverageRecord, ...],
    summary: Summary,
) -> dict[str, bytes]:
    """Render all version 1 artifacts in memory with stable byte representations."""

    csv_output = io.StringIO(newline="")
    writer = csv.DictWriter(csv_output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for record in matrix:
        row = record_to_dict(record)
        writer.writerow({field: "" if row[field] is None else row[field] for field in CSV_FIELDS})

    report = {
        "schema_version": 1,
        "version": manifest.version,
        "entities": [
            {"id": item.id} for item in sorted(manifest.entities, key=lambda item: item.id)
        ],
        "sources": [
            {"id": item.id, "availability": item.availability.value}
            for item in sorted(manifest.sources, key=lambda item: item.id)
        ],
        "relationships": [record_to_dict(record) for record in matrix],
    }
    audit = audit_to_dict(matrix)
    markdown = [
        "# EvidenceMatrix coverage report",
        "",
        f"- Entities: {summary.entity_count}",
        f"- Sources: {summary.source_count}",
        f"- Relationships: {summary.relationship_count}",
        f"- Unresolved findings: {summary.finding_count}",
        "",
        "## Coverage status counts",
        "",
    ]
    markdown.extend(f"- `{status}`: {count}" for status, count in summary.status_counts.items())
    markdown.extend(
        [
            "",
            "## Unresolved relationships",
            "",
            "| Entity | Source | Status | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    if audit["findings"]:
        for item in audit["findings"]:
            assert isinstance(item, dict)
            values = [item["entity_id"], item["source_id"], item["status"], item["reason"] or ""]
            escaped = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
            markdown.append("| " + " | ".join(escaped) + " |")
    else:
        markdown.append("| — | — | — | No unresolved relationships |")
    markdown_text = "\n".join(markdown) + "\n"
    summary_payload = summary_to_dict(summary)

    return {
        "coverage_matrix.csv": csv_output.getvalue().encode("utf-8"),
        "coverage_report.json": _json_bytes(report),
        "gap_report.json": _json_bytes(audit),
        "summary.json": _json_bytes(summary_payload),
        "coverage_report.md": markdown_text.encode("utf-8"),
    }


def write_artifacts(artifacts: dict[str, bytes], output_dir: str | Path) -> tuple[Path, ...]:
    """Write a complete pre-rendered artifact set to the requested directory."""

    root = Path(output_dir).expanduser()
    if root.exists() and not root.is_dir():
        raise OSError(f"output path is not a directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in ARTIFACT_NAMES:
        destination = root / name
        temporary = root / f".{name}.tmp"
        temporary.write_bytes(artifacts[name])
        temporary.replace(destination)
        written.append(destination)
    return tuple(written)

from __future__ import annotations

import json

from evidencematrix import build_matrix, load_manifest, summarize_matrix
from evidencematrix.output import build_artifacts


def test_build_artifacts_are_byte_deterministic(tmp_path):
    manifest_path = tmp_path / "coverage.yaml"
    manifest_path.write_text(
        """version: 1
entities:
  - id: e2
  - id: e1
sources:
  - id: s2
    availability: unavailable
  - id: s1
    availability: available
coverage:
  - entity: e1
    source: s1
    status: supported
""",
        encoding="utf-8",
    )
    manifest = load_manifest(manifest_path)
    matrix = build_matrix(manifest)
    summary = summarize_matrix(manifest, matrix)

    first = build_artifacts(manifest, matrix, summary)
    second = build_artifacts(manifest, matrix, summary)

    assert first.keys() == {
        "coverage_matrix.csv",
        "coverage_report.json",
        "gap_report.json",
        "summary.json",
        "coverage_report.md",
    }
    assert first == second
    first_row = first["coverage_matrix.csv"].decode().splitlines()[1]
    assert first_row.startswith("e1,s1,available,supported,")
    assert b"timestamp" not in first["coverage_report.json"].lower()
    report = json.loads(first["coverage_report.json"])
    assert [(item["entity_id"], item["source_id"]) for item in report["relationships"]] == [
        ("e1", "s1"),
        ("e1", "s2"),
        ("e2", "s1"),
        ("e2", "s2"),
    ]


def test_gap_report_excludes_not_applicable_and_keeps_unknown(tmp_path):
    path = tmp_path / "coverage.yaml"
    path.write_text(
        """version: 1
entities:
  - id: e1
sources:
  - id: a
    availability: available
  - id: b
    availability: unknown
coverage:
  - entity: e1
    source: a
    status: not_applicable
    reason: outside_scope
""",
        encoding="utf-8",
    )
    manifest = load_manifest(path)
    matrix = build_matrix(manifest)

    artifacts = build_artifacts(manifest, matrix, summarize_matrix(manifest, matrix))
    gap_report = json.loads(artifacts["gap_report.json"])

    assert gap_report["finding_count"] == 1
    assert gap_report["findings"][0]["status"] == "unknown"
    assert gap_report["status_counts"]["unknown"] == 1
    assert "not_applicable" not in gap_report["status_counts"]
    assert gap_report["not_applicable_count"] == 1

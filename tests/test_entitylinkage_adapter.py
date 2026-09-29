from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from evidencematrix.matrix import build_matrix, summarize_matrix
from evidencematrix.parser import load_manifest

EXAMPLE = Path(__file__).parents[1] / "examples" / "entitylinkage-coverage"
ADAPTER = EXAMPLE / "adapter.py"

CONTEXT = {
    "version": 1,
    "entities": [{"id": f"entity-{index}"} for index in range(1, 5)],
    "sources": [
        {"id": "catalog-a", "availability": "available"},
        {"id": "catalog-b", "availability": "available"},
        {"id": "retired-register", "availability": "unavailable"},
        {"id": "spring-supplement", "availability": "not_in_release"},
    ],
    "coverage": [
        {
            "entity": "entity-2",
            "source": "catalog-a",
            "status": "mapping_gap",
            "reason": "shared_name_requires_review",
        },
        {
            "entity": "entity-3",
            "source": "catalog-a",
            "status": "not_applicable",
            "reason": "archive_is_outside_catalog_scope",
        },
        {
            "entity": "entity-4",
            "source": "catalog-a",
            "status": "mapping_gap",
            "reason": "shared_name_requires_review",
        },
    ],
}

RESULTS = [
    {
        "record_id": "record-a-001",
        "status": "resolved",
        "entity_id": "entity-1",
        "candidate_entity_ids": ["entity-1"],
        "reason_codes": ["candidate_match"],
        "normalized_record_name": "north basin observatory",
        "evidence": [
            {
                "rule_id": "publication-name",
                "phase": "candidate",
                "outcome": "matched",
                "entity_id": "entity-1",
                "details": {},
            }
        ],
    },
    {
        "record_id": "record-a-002",
        "status": "ambiguous",
        "entity_id": None,
        "candidate_entity_ids": ["entity-2", "entity-4"],
        "reason_codes": ["multiple_candidates"],
        "normalized_record_name": "highland field station",
        "evidence": [],
    },
    {
        "record_id": "record-a-003",
        "status": "unresolved",
        "entity_id": None,
        "candidate_entity_ids": [],
        "reason_codes": ["no_identity_candidate"],
        "normalized_record_name": "unlisted coastal notice",
        "evidence": [],
    },
    {
        "record_id": "record-b-001",
        "status": "resolved",
        "entity_id": "entity-3",
        "candidate_entity_ids": ["entity-3"],
        "reason_codes": ["candidate_match"],
        "normalized_record_name": "central valley archive",
        "evidence": [],
    },
    {
        "record_id": "record-b-002",
        "status": "not_applicable",
        "entity_id": None,
        "candidate_entity_ids": [],
        "reason_codes": ["not_applicable"],
        "normalized_record_name": None,
        "evidence": [],
    },
]


def write_inputs(
    root: Path,
    *,
    results: list[dict[str, object]] | None = None,
    context: dict[str, object] | None = None,
    mapping_rows: list[tuple[str, str]] | None = None,
    schema_version: str = "entitylinkage-results-v1",
) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    linkage_path = root / "linkage.json"
    linkage_path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "tool_version": "0.1.0",
                "unicode_version": "16.0",
                "results": RESULTS if results is None else results,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    mapping_path = root / "record-sources.csv"
    rows = mapping_rows or [
        ("record-a-001", "catalog-a"),
        ("record-a-002", "catalog-a"),
        ("record-a-003", "catalog-a"),
        ("record-b-001", "catalog-b"),
        ("record-b-002", "catalog-b"),
    ]
    with mapping_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("record_id", "source_id"))
        writer.writerows(rows)
    context_path = root / "context.json"
    context_path.write_text(
        json.dumps(CONTEXT if context is None else context, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return linkage_path, mapping_path, context_path


def run_adapter(
    tmp_path: Path,
    *,
    results: list[dict[str, object]] | None = None,
    context: dict[str, object] | None = None,
    mapping_rows: list[tuple[str, str]] | None = None,
    schema_version: str = "entitylinkage-results-v1",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    inputs = write_inputs(
        tmp_path / "inputs",
        results=results,
        context=context,
        mapping_rows=mapping_rows,
        schema_version=schema_version,
    )
    output = tmp_path / "output"
    completed = subprocess.run(
        [
            sys.executable,
            str(ADAPTER),
            "--linkage",
            str(inputs[0]),
            "--record-sources",
            str(inputs[1]),
            "--context",
            str(inputs[2]),
            "--output-dir",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, output


def test_adapter_preserves_unknowns_and_review_rows(tmp_path: Path) -> None:
    completed, output = run_adapter(tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    manifest = load_manifest(output / "coverage.yaml")
    summary = summarize_matrix(manifest, build_matrix(manifest))
    assert summary.relationship_count == 16
    assert summary.status_counts == {
        "supported": 2,
        "metadata_gap": 0,
        "mapping_gap": 2,
        "source_unavailable": 4,
        "source_not_in_release": 4,
        "not_applicable": 1,
        "unknown": 3,
    }

    with (output / "review.csv").open(encoding="utf-8", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    assert [(row["record_id"], row["status"]) for row in reviews] == [
        ("record-a-002", "ambiguous"),
        ("record-a-003", "unresolved"),
        ("record-b-002", "not_applicable"),
    ]
    assert reviews[0]["normalized_record_name"] == "highland field station"
    assert json.loads(reviews[0]["candidate_entity_ids"]) == ["entity-2", "entity-4"]
    assert json.loads(reviews[0]["evidence"]) == []

    with (output / "resolved-records.csv").open(encoding="utf-8", newline="") as stream:
        resolved = list(csv.DictReader(stream))
    assert resolved == [
        {"entity_id": "entity-1", "source_id": "catalog-a", "record_id": "record-a-001"},
        {"entity_id": "entity-3", "source_id": "catalog-b", "record_id": "record-b-001"},
    ]


def test_resolved_evidence_promotes_only_its_declared_mapping_gap(tmp_path: Path) -> None:
    results = [dict(item) for item in RESULTS]
    results[1] = {
        **results[1],
        "status": "resolved",
        "entity_id": "entity-4",
        "candidate_entity_ids": ["entity-4"],
        "reason_codes": ["manual_override"],
    }
    completed, output = run_adapter(tmp_path, results=results)

    assert completed.returncode == 0, completed.stderr
    manifest = load_manifest(output / "coverage.yaml")
    summary = summarize_matrix(manifest, build_matrix(manifest))
    assert summary.status_counts["supported"] == 3
    assert summary.status_counts["mapping_gap"] == 1
    assert summary.status_counts["unknown"] == 3

    with (output / "resolved-records.csv").open(encoding="utf-8", newline="") as stream:
        resolved = list(csv.DictReader(stream))
    assert any(
        row == {"entity_id": "entity-4", "source_id": "catalog-a", "record_id": "record-a-002"}
        for row in resolved
    )


def test_multiple_resolved_records_share_one_supported_relationship(tmp_path: Path) -> None:
    results = [dict(item) for item in RESULTS]
    results[1] = {
        **results[1],
        "status": "resolved",
        "entity_id": "entity-1",
        "candidate_entity_ids": ["entity-1"],
        "reason_codes": ["manual_override"],
    }
    completed, output = run_adapter(tmp_path, results=results)

    assert completed.returncode == 0, completed.stderr
    manifest = load_manifest(output / "coverage.yaml")
    summary = summarize_matrix(manifest, build_matrix(manifest))
    assert summary.status_counts["supported"] == 2
    with (output / "resolved-records.csv").open(encoding="utf-8", newline="") as stream:
        resolved = list(csv.DictReader(stream))
    assert [row["record_id"] for row in resolved if row["entity_id"] == "entity-1"] == [
        "record-a-001",
        "record-a-002",
    ]


def test_adapter_rejects_resolved_not_applicable_conflict(tmp_path: Path) -> None:
    results = [dict(item) for item in RESULTS]
    results[1] = {
        **results[1],
        "status": "resolved",
        "entity_id": "entity-3",
        "candidate_entity_ids": ["entity-3"],
        "reason_codes": ["manual_override"],
    }
    completed, output = run_adapter(tmp_path, results=results)

    assert completed.returncode == 2
    assert "conflicts with not_applicable" in completed.stderr
    assert not output.exists()


def test_adapter_rejects_missing_record_source_mapping(tmp_path: Path) -> None:
    mappings = [
        ("record-a-001", "catalog-a"),
        ("record-a-002", "catalog-a"),
        ("record-a-003", "catalog-a"),
        ("record-b-001", "catalog-b"),
    ]
    completed, output = run_adapter(tmp_path, mapping_rows=mappings)

    assert completed.returncode == 2
    assert "missing source mapping" in completed.stderr
    assert not output.exists()


def test_adapter_rejects_inconsistent_resolved_candidates(tmp_path: Path) -> None:
    results = [dict(item) for item in RESULTS]
    results[0] = {**results[0], "candidate_entity_ids": ["entity-2"]}
    completed, output = run_adapter(tmp_path, results=results)

    assert completed.returncode == 2
    assert "must list only its resolved entity" in completed.stderr
    assert not output.exists()


def test_adapter_outputs_are_byte_deterministic(tmp_path: Path) -> None:
    first, first_output = run_adapter(tmp_path / "first")
    second, second_output = run_adapter(tmp_path / "second")

    assert first.returncode == second.returncode == 0
    names = {"coverage.yaml", "review.csv", "resolved-records.csv"}
    assert {name: (first_output / name).read_bytes() for name in names} == {
        name: (second_output / name).read_bytes() for name in names
    }


def test_adapter_rejects_bad_inputs_without_partial_outputs(tmp_path: Path) -> None:
    completed, output = run_adapter(tmp_path, schema_version="entitylinkage-results-v2")

    assert completed.returncode == 2
    assert "schema_version" in completed.stderr
    assert not output.exists()

from __future__ import annotations

from evidencematrix import build_matrix, load_manifest, summarize_matrix


def test_matrix_expands_cartesian_product_and_preserves_status_semantics(tmp_path):
    path = tmp_path / "coverage.yaml"
    path.write_text(
        """version: 1
entities:
  - id: entity-b
  - id: entity-a
sources:
  - id: source-unknown
    availability: unknown
  - id: source-out
    availability: not_in_release
  - id: source-down
    availability: unavailable
  - id: source-ok
    availability: available
coverage:
  - entity: entity-a
    source: source-ok
    status: supported
  - entity: entity-b
    source: source-ok
    status: mapping_gap
    reason: no_verified_mapping
  - entity: entity-a
    source: source-out
    status: not_applicable
    reason: source_does_not_cover_entity
  - entity: entity-a
    source: source-unknown
    status: metadata_gap
    reason: missing_release_date
""",
        encoding="utf-8",
    )

    rows = build_matrix(load_manifest(path))

    assert [(row.entity_id, row.source_id) for row in rows] == [
        ("entity-a", "source-down"),
        ("entity-a", "source-ok"),
        ("entity-a", "source-out"),
        ("entity-a", "source-unknown"),
        ("entity-b", "source-down"),
        ("entity-b", "source-ok"),
        ("entity-b", "source-out"),
        ("entity-b", "source-unknown"),
    ]
    assert rows[0].status.value == "source_unavailable"
    assert rows[0].reason == "source_declared_unavailable"
    assert rows[1].status.value == "supported"
    assert rows[2].status.value == "not_applicable"
    assert rows[3].status.value == "metadata_gap"
    assert rows[4].status.value == "source_unavailable"
    assert rows[5].status.value == "mapping_gap"
    assert rows[6].status.value == "source_not_in_release"
    assert rows[7].status.value == "unknown"
    assert rows[5].reason == "no_verified_mapping"
    assert rows[3].reason == "missing_release_date"


def test_summary_counts_all_statuses_and_treats_not_applicable_separately(tmp_path):
    path = tmp_path / "coverage.yaml"
    path.write_text(
        """version: 1
entities:
  - id: e1
  - id: e2
sources:
  - id: available
    availability: available
  - id: unavailable
    availability: unavailable
coverage:
  - entity: e1
    source: available
    status: supported
  - entity: e2
    source: available
    status: not_applicable
""",
        encoding="utf-8",
    )

    summary = summarize_matrix(load_manifest(path), build_matrix(load_manifest(path)))

    assert summary.relationship_count == 4
    assert summary.status_counts == {
        "supported": 1,
        "metadata_gap": 0,
        "mapping_gap": 0,
        "source_unavailable": 2,
        "source_not_in_release": 0,
        "not_applicable": 1,
        "unknown": 0,
    }
    assert summary.finding_count == 2

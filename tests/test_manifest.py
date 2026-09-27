from __future__ import annotations

import textwrap

import pytest
import yaml

from evidencematrix import CoverageStatus, SourceAvailability, load_manifest
from evidencematrix.validation import ManifestError


def write_manifest(tmp_path, content: str):
    path = tmp_path / "coverage.yaml"
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


def test_loads_generic_yaml_manifest(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        version: 1
        entities:
          - id: event-001
        sources:
          - id: source-a
            availability: available
        coverage:
          - entity: event-001
            source: source-a
            status: supported
        """,
    )

    manifest = load_manifest(path)

    assert manifest.version == 1
    assert manifest.entities[0].id == "event-001"
    assert manifest.sources[0].availability is SourceAvailability.AVAILABLE
    assert manifest.coverage[0].status is CoverageStatus.SUPPORTED


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "entities",
            [{"id": "same"}, {"id": "same"}],
            "duplicate entity id",
        ),
        (
            "sources",
            [
                {"id": "same", "availability": "available"},
                {"id": "same", "availability": "unknown"},
            ],
            "duplicate source id",
        ),
        (
            "coverage",
            [{"entity": "missing-entity", "source": "source-a", "status": "supported"}],
            "unknown entity",
        ),
        (
            "coverage",
            [{"entity": "event-001", "source": "missing-source", "status": "supported"}],
            "unknown source",
        ),
        (
            "coverage",
            [{"entity": "event-001", "source": "source-a", "status": "invented"}],
            "status is invalid",
        ),
        (
            "coverage",
            [{"entity": "event-001", "source": "source-a", "status": "source_unavailable"}],
            "conflicts with source availability",
        ),
        (
            "coverage",
            [
                {"entity": "event-001", "source": "source-a", "status": "supported"},
                {"entity": "event-001", "source": "source-a", "status": "unknown"},
            ],
            "duplicate coverage relationship",
        ),
    ],
)
def test_rejects_invalid_manifest_relationships(tmp_path, field, value, message):
    document = {
        "version": 1,
        "entities": [{"id": "event-001"}],
        "sources": [{"id": "source-a", "availability": "available"}],
        "coverage": [],
    }
    document[field] = value
    path = tmp_path / "coverage.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(ManifestError, match=message):
        load_manifest(path)


def test_rejects_duplicate_yaml_keys_and_malformed_input(tmp_path):
    duplicate = write_manifest(
        tmp_path,
        """
        version: 1
        version: 1
        entities: []
        sources: []
        coverage: []
        """,
    )
    with pytest.raises(ManifestError, match="duplicate key"):
        load_manifest(duplicate)

    malformed = tmp_path / "bad.yaml"
    malformed.write_text("entities: [", encoding="utf-8")
    with pytest.raises(ManifestError, match="parse"):
        load_manifest(malformed)


def test_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"version":1,"entities":[],"entities":[],"sources":[],"coverage":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="duplicate key"):
        load_manifest(path)


def test_directory_input_requires_one_manifest(tmp_path):
    first = tmp_path / "coverage.yaml"
    first.write_text("version: 1\nentities: []\nsources: []\ncoverage: []\n", encoding="utf-8")
    assert load_manifest(tmp_path).version == 1

    (tmp_path / "another.json").write_text(
        '{"version": 1, "entities": [], "sources": [], "coverage": []}',
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="exactly one"):
        load_manifest(tmp_path)


def test_validation_does_not_change_input_bytes(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        version: 1
        entities: []
        sources: []
        coverage: []
        """,
    )
    original = path.read_bytes()

    load_manifest(path)

    assert path.read_bytes() == original


def test_json_manifest_is_supported(tmp_path):
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"version":1,"entities":[],"sources":[],"coverage":[]}',
        encoding="utf-8",
    )

    assert load_manifest(path).version == 1


def test_external_payload_paths_are_not_part_of_version_one_schema(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        version: 1
        entities: []
        sources:
          - id: source-a
            availability: available
            path: ../../private/payload.csv
        coverage: []
        """,
    )

    with pytest.raises(ManifestError, match="unknown field.*path"):
        load_manifest(path)

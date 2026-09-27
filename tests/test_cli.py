from __future__ import annotations

import json

from evidencematrix.cli import main


def write_manifest(tmp_path, *, availability="available", relationship_status="mapping_gap"):
    reason = "" if relationship_status == "supported" else "    reason: sample_reason\n"
    path = tmp_path / "coverage.yaml"
    path.write_text(
        f"""version: 1
entities:
  - id: entity-1
sources:
  - id: source-1
    availability: {availability}
coverage:
  - entity: entity-1
    source: source-1
    status: {relationship_status}
{reason}""",
        encoding="utf-8",
    )
    return path


def test_cli_validate_build_audit_and_summary_exit_codes(tmp_path, capsys):
    manifest = write_manifest(tmp_path)
    output = tmp_path / "out"

    assert main(["validate", str(manifest)]) == 0
    original_manifest = manifest.read_bytes()
    assert main(["build", str(manifest), "--output", str(output)]) == 0
    assert sorted(path.name for path in output.iterdir()) == [
        "coverage_matrix.csv",
        "coverage_report.json",
        "coverage_report.md",
        "gap_report.json",
        "summary.json",
    ]
    assert main(["audit", str(manifest)]) == 1
    audit_output = capsys.readouterr().out
    assert "mapping_gap: 1" in audit_output
    assert audit_output.count("not_applicable") == 1
    assert manifest.read_bytes() == original_manifest

    assert main(["summary", str(manifest), "--format", "json"]) == 0
    summary_output = json.loads(capsys.readouterr().out)
    assert summary_output["schema_version"] == 1
    assert summary_output["relationship_count"] == 1
    assert summary_output["status_counts"]["mapping_gap"] == 1


def test_cli_clean_audit_returns_zero_and_json_is_machine_readable(tmp_path, capsys):
    manifest = write_manifest(tmp_path, relationship_status="supported")

    assert main(["audit", str(manifest), "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["finding_count"] == 0


def test_cli_invalid_input_returns_two_and_writes_errors_to_stderr(tmp_path, capsys):
    manifest = tmp_path / "invalid.yaml"
    manifest.write_text("version: 1\n", encoding="utf-8")

    assert main(["validate", str(manifest)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "entities" in captured.err


def test_cli_build_output_is_stable_across_output_directories(tmp_path):
    manifest = write_manifest(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"

    assert main(["build", str(manifest), "--output", str(first)]) == 0
    assert main(["build", str(manifest), "--output", str(second)]) == 0
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {
        p.name: p.read_bytes() for p in second.iterdir()
    }

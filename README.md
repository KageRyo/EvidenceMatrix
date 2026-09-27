# EvidenceMatrix

[![CI](https://github.com/KageRyo/EvidenceMatrix/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/KageRyo/EvidenceMatrix/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/evidencematrix)](https://pypi.org/project/evidencematrix/)
[![Latest release](https://img.shields.io/github/v/release/KageRyo/EvidenceMatrix?display_name=tag&sort=semver)](https://github.com/KageRyo/EvidenceMatrix/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

EvidenceMatrix builds deterministic coverage matrices for a declared set of entities and expected sources. It shows which relationships are supported, have known gaps, are unavailable, remain unknown, or do not apply.

EvidenceMatrix was extracted from source-coverage auditing patterns developed in a real-world multi-source data pipeline. It is a standalone tool and does not require that project or its data.

## What it does

- Validates a small YAML or JSON manifest of entities, sources, and coverage declarations.
- Expands the declared entities and sources into a complete, sorted entity-by-source matrix.
- Reports status counts and unresolved relationships without assigning a subjective quality score.
- Writes stable CSV, JSON, and Markdown reports without adding timestamps.
- Runs locally and offline after installation.

## What it does not do

EvidenceMatrix does not download or transform data, validate arbitrary dataset schemas, verify file integrity, build lineage graphs, align spatial data, manage workflows, or evaluate machine-learning models. Use [LineageGuard](https://github.com/KageRyo/LineageGuard) for artifact origin and lineage, [ReleaseGuard](https://github.com/KageRyo/ReleaseGuard) for dataset release structure and integrity, and [GridForge](https://github.com/KageRyo/GridForge) for spatial alignment.

## Installation

After a release is published, install it with `uv tool install evidencematrix` or `python -m pip install evidencematrix`. To run from a checkout, use Python 3.11 or newer and `uv sync --all-groups`, then prefix commands with `uv run`.

The runtime has one dependency, PyYAML, for safe YAML parsing. JSON input and all audit calculations work offline; the CLI makes no network requests.

## Quick start

The bundled [`examples/basic/coverage.yaml`](examples/basic/coverage.yaml) demonstrates supported, mapping-gap, metadata-gap, unavailable, not-in-release, not-applicable, and unknown relationships.

```bash
evidencematrix validate examples/basic
evidencematrix build examples/basic --output ./out
evidencematrix audit examples/basic
evidencematrix summary examples/basic
evidencematrix summary examples/basic --format json
```

`audit` returns exit code 1 for unresolved relationships in this example. The example contains gaps intentionally; `validate`, `build`, and `summary` succeed with exit code 0.

`build` writes `coverage_matrix.csv`, `coverage_report.json`, `gap_report.json`, `summary.json`, and `coverage_report.md`. The JSON reports use sorted keys and stable indentation; CSV rows sort by entity ID and source ID. Rebuilding identical input with the same tool version produces byte-identical files.

## Input model

A manifest has `version`, `entities`, `sources`, and `coverage` fields. IDs are unique strings. Each source declares its availability. Coverage entries are optional and identify one entity, one source, and one status; `reason` is an optional explanatory string for non-supported states.

```yaml
version: 1

entities:
  - id: event-001
  - id: event-002

sources:
  - id: cwa
    availability: available
  - id: emic
    availability: unavailable

coverage:
  - entity: event-001
    source: cwa
    status: supported
  - entity: event-002
    source: cwa
    status: mapping_gap
    reason: no_verified_mapping
```

The input is deliberately strict: unknown fields, duplicate IDs or relationships, invalid references, duplicate YAML or JSON keys, and contradictory availability declarations fail validation. `PATH` may point to a `.yaml`, `.yml`, or `.json` file, or to a directory containing exactly one such manifest. No external file references are part of schema version 1.

### Availability and coverage status

Source availability and entity-source coverage describe related but separate facts. Availability accepts `available`, `unavailable`, `not_in_release`, and `unknown`. Coverage accepts:

| Status | Meaning |
| --- | --- |
| `supported` | The manifest declares evidence for this entity-source relationship. |
| `metadata_gap` | Required descriptive metadata is missing or unresolved. |
| `mapping_gap` | The source-to-entity relationship is not established. |
| `source_unavailable` | The source payload is declared unavailable. |
| `source_not_in_release` | The expected source is not included in the release being described. |
| `not_applicable` | The relationship is explicitly outside scope. |
| `unknown` | The relationship has not been assessed. |

Each entity is paired with every listed source. An explicit coverage row sets that pair's status. If no row exists, a source marked `unavailable` or `not_in_release` determines the corresponding relationship status; otherwise the relationship remains `unknown`. In particular, a missing relationship is never inferred to be a mapping gap. Explicit `not_applicable` relationships stay visible in the matrix and summary, but are excluded from unresolved audit findings.

`supported` is a manifest declaration. EvidenceMatrix checks that declaration's structure and consistency; it does not inspect or authenticate external evidence.

## Commands and exit codes

```text
evidencematrix validate PATH
evidencematrix build PATH [--output DIR]
evidencematrix audit PATH [--format text|json]
evidencematrix summary PATH [--format text|json]
```

`validate` checks input without modifying it. `build` creates deterministic reports. `audit` lists unresolved rows and returns 1 when it finds any; `not_applicable` rows are reported separately and do not fail the audit. `summary` prints counts, including all status categories, and supports machine-readable JSON. Commands are noninteractive; diagnostics go to stderr.

Exit codes are 0 for a valid command with no blocking finding, 1 for unresolved audit findings, and 2 for invalid input or execution errors.

## Development

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

GitHub Actions runs lint and format checks, tests, package builds, and CLI smoke checks on Python 3.11, 3.12, and 3.13.

## Real-dataset dogfood

The public [TWDisaster dataset](https://github.com/KageRyo/TWDisaster) publishes positive event-source links but no expected-source eligibility matrix. The [dogfood assessment](examples/twdisaster/README.md) explains why converting absent links into gaps would invent facts and why the current release cannot provide a useful matrix of expected coverage.

## License

EvidenceMatrix is distributed under the [Apache License 2.0](LICENSE).

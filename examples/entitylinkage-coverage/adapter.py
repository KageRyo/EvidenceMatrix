#!/usr/bin/env python3
"""Adapt deterministic EntityLinkage results to an EvidenceMatrix manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_LINKAGE_SCHEMA = "entitylinkage-results-v1"
_LINKAGE_STATUSES = {"resolved", "ambiguous", "unresolved", "not_applicable"}
_AVAILABILITIES = {"available", "unavailable", "not_in_release", "unknown"}
_DECLARED_STATUSES = {"mapping_gap", "not_applicable"}
_REVIEW_FIELDS = (
    "record_id",
    "source_id",
    "status",
    "normalized_record_name",
    "candidate_entity_ids",
    "reason_codes",
    "evidence",
)
_RESOLVED_FIELDS = ("entity_id", "source_id", "record_id")


class AdapterError(ValueError):
    """Raised when an input cannot be translated without changing its meaning."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AdapterError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, AdapterError) as error:
        raise AdapterError(f"cannot read {label} {path}: {error}") from error


def _object(value: Any, label: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise AdapterError(f"{label} must be a JSON object")
    unexpected = sorted(value.keys() - fields)
    missing = sorted(fields - value.keys())
    if unexpected:
        raise AdapterError(f"{label} has unknown field(s): {', '.join(unexpected)}")
    if missing:
        raise AdapterError(f"{label} is missing field(s): {', '.join(missing)}")
    return value


def _string(value: Any, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise AdapterError(f"{label} must be a non-empty string without surrounding whitespace")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise AdapterError(f"{label} must be a list")
    items = [_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len(items) != len(set(items)):
        raise AdapterError(f"{label} must not contain duplicates")
    return items


def _read_record_sources(path: Path) -> dict[str, str]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["record_id", "source_id"]:
                raise AdapterError("record-source CSV header must be exactly record_id,source_id")
            mapping: dict[str, str] = {}
            for line, row in enumerate(reader, start=2):
                if None in row or set(row) != {"record_id", "source_id"}:
                    raise AdapterError(
                        f"record-source CSV line {line} has an invalid number of columns"
                    )
                record_id = _string(row["record_id"], f"record-source CSV line {line} record_id")
                source_id = _string(row["source_id"], f"record-source CSV line {line} source_id")
                if record_id in mapping:
                    raise AdapterError(f"duplicate record-to-source mapping: {record_id!r}")
                mapping[record_id] = source_id
            return mapping
    except (OSError, UnicodeError, csv.Error) as error:
        raise AdapterError(f"cannot read record-source CSV {path}: {error}") from error


def _load_context(
    path: Path,
) -> tuple[list[str], dict[str, str], dict[tuple[str, str], dict[str, str]]]:
    context = _object(
        _read_json(path, "coverage context"),
        "coverage context",
        {"version", "entities", "sources", "coverage"},
    )
    if type(context["version"]) is not int or context["version"] != 1:
        raise AdapterError("coverage context version must be the integer 1")
    if not isinstance(context["entities"], list):
        raise AdapterError("coverage context entities must be a list")
    if not isinstance(context["sources"], list):
        raise AdapterError("coverage context sources must be a list")
    if not isinstance(context["coverage"], list):
        raise AdapterError("coverage context coverage must be a list")

    entity_ids: list[str] = []
    for index, value in enumerate(context["entities"]):
        item = _object(value, f"coverage context entities[{index}]", {"id"})
        entity_ids.append(_string(item["id"], f"coverage context entities[{index}].id"))
    if len(entity_ids) != len(set(entity_ids)):
        raise AdapterError("coverage context contains duplicate entity IDs")

    sources: dict[str, str] = {}
    for index, value in enumerate(context["sources"]):
        item = _object(value, f"coverage context sources[{index}]", {"id", "availability"})
        source_id = _string(item["id"], f"coverage context sources[{index}].id")
        availability = _string(
            item["availability"], f"coverage context sources[{index}].availability"
        )
        if availability not in _AVAILABILITIES:
            raise AdapterError(
                f"source {source_id!r} has unsupported availability {availability!r}"
            )
        if source_id in sources:
            raise AdapterError(f"coverage context contains duplicate source ID: {source_id!r}")
        sources[source_id] = availability

    declarations: dict[tuple[str, str], dict[str, str]] = {}
    for index, value in enumerate(context["coverage"]):
        item = _object(
            value,
            f"coverage context coverage[{index}]",
            {"entity", "source", "status", "reason"},
        )
        entity_id = _string(item["entity"], f"coverage context coverage[{index}].entity")
        source_id = _string(item["source"], f"coverage context coverage[{index}].source")
        status = _string(item["status"], f"coverage context coverage[{index}].status")
        reason = _string(item["reason"], f"coverage context coverage[{index}].reason")
        if entity_id not in entity_ids:
            raise AdapterError(f"coverage context references unknown entity: {entity_id!r}")
        if source_id not in sources:
            raise AdapterError(f"coverage context references unknown source: {source_id!r}")
        if status not in _DECLARED_STATUSES:
            raise AdapterError(
                f"coverage context status must be one of: {', '.join(sorted(_DECLARED_STATUSES))}"
            )
        if sources[source_id] in {"unavailable", "not_in_release"}:
            raise AdapterError(
                f"coverage declaration for {entity_id!r}/{source_id!r} conflicts with "
                f"source availability {sources[source_id]!r}"
            )
        pair = (entity_id, source_id)
        if pair in declarations:
            raise AdapterError(
                f"duplicate coverage context relationship: {entity_id!r}/{source_id!r}"
            )
        declarations[pair] = {"status": status, "reason": reason}

    return entity_ids, sources, declarations


def _load_linkage(path: Path, entity_ids: set[str]) -> list[dict[str, Any]]:
    payload = _object(
        _read_json(path, "EntityLinkage result"),
        "EntityLinkage result",
        {"schema_version", "tool_version", "unicode_version", "results"},
    )
    if payload["schema_version"] != _LINKAGE_SCHEMA:
        raise AdapterError(
            f"unsupported EntityLinkage schema_version: {payload['schema_version']!r}"
        )
    _string(payload["tool_version"], "EntityLinkage tool_version")
    _string(payload["unicode_version"], "EntityLinkage unicode_version")
    if not isinstance(payload["results"], list):
        raise AdapterError("EntityLinkage results must be a list")

    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    fields = {
        "record_id",
        "status",
        "entity_id",
        "candidate_entity_ids",
        "reason_codes",
        "normalized_record_name",
        "evidence",
    }
    for index, value in enumerate(payload["results"]):
        item = _object(value, f"EntityLinkage results[{index}]", fields)
        record_id = _string(item["record_id"], f"EntityLinkage results[{index}].record_id")
        status = _string(item["status"], f"EntityLinkage results[{index}].status")
        if status not in _LINKAGE_STATUSES:
            raise AdapterError(
                f"EntityLinkage record {record_id!r} has unsupported status {status!r}"
            )
        if record_id in seen_ids:
            raise AdapterError(f"duplicate EntityLinkage record ID: {record_id!r}")
        seen_ids.add(record_id)

        entity_id = item["entity_id"]
        if status == "resolved":
            entity_id = _string(entity_id, f"EntityLinkage record {record_id!r} entity_id")
            if entity_id not in entity_ids:
                raise AdapterError(
                    f"EntityLinkage record {record_id!r} resolved to unknown entity {entity_id!r}"
                )
        elif entity_id is not None:
            raise AdapterError(
                f"EntityLinkage record {record_id!r} with status {status!r} "
                "must not declare entity_id"
            )

        candidates = _string_list(
            item["candidate_entity_ids"],
            f"EntityLinkage record {record_id!r} candidate_entity_ids",
        )
        unknown_candidates = sorted(set(candidates) - entity_ids)
        if unknown_candidates:
            raise AdapterError(
                f"EntityLinkage record {record_id!r} has unknown candidate entity IDs: "
                + ", ".join(unknown_candidates)
            )
        reason_codes = _string_list(
            item["reason_codes"], f"EntityLinkage record {record_id!r} reason_codes"
        )
        if status == "resolved" and candidates != [entity_id]:
            raise AdapterError(
                f"resolved EntityLinkage record {record_id!r} must list only its resolved entity "
                "in candidate_entity_ids"
            )
        if status == "ambiguous" and len(candidates) < 2:
            raise AdapterError(
                f"ambiguous EntityLinkage record {record_id!r} must list at least two candidates"
            )
        if status in {"unresolved", "not_applicable"} and candidates:
            raise AdapterError(
                f"EntityLinkage record {record_id!r} with status {status!r} "
                "must not list candidates"
            )
        if status == "not_applicable" and not reason_codes:
            raise AdapterError(
                f"not_applicable EntityLinkage record {record_id!r} must include a reason code"
            )
        normalized_name = item["normalized_record_name"]
        if normalized_name is not None and type(normalized_name) is not str:
            raise AdapterError(
                f"EntityLinkage record {record_id!r} normalized_record_name "
                "must be a string or null"
            )
        if not isinstance(item["evidence"], list) or any(
            not isinstance(evidence, dict) for evidence in item["evidence"]
        ):
            raise AdapterError(
                f"EntityLinkage record {record_id!r} evidence must be a list of objects"
            )
        results.append(
            {
                **item,
                "record_id": record_id,
                "status": status,
                "entity_id": entity_id,
                "candidate_entity_ids": candidates,
                "reason_codes": reason_codes,
            }
        )
    return sorted(results, key=lambda item: item["record_id"])


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _coverage_yaml(
    entity_ids: list[str],
    source_availability: dict[str, str],
    declarations: dict[tuple[str, str], dict[str, str]],
    resolved_by_pair: dict[tuple[str, str], list[str]],
) -> str:
    rows: dict[tuple[str, str], dict[str, str]] = {
        pair: dict(declaration) for pair, declaration in declarations.items()
    }
    for pair in resolved_by_pair:
        rows[pair] = {"status": "supported", "reason": ""}

    lines = ["version: 1", "", "entities:"]
    lines.extend(f"  - id: {_yaml_string(entity_id)}" for entity_id in sorted(entity_ids))
    lines.extend(["", "sources:"])
    for source_id, availability in sorted(source_availability.items()):
        lines.extend(
            [
                f"  - id: {_yaml_string(source_id)}",
                f"    availability: {availability}",
            ]
        )
    lines.extend(["", "coverage:"])
    if not rows:
        lines[-1] = "coverage: []"
    else:
        for (entity_id, source_id), declaration in sorted(rows.items()):
            lines.extend(
                [
                    f"  - entity: {_yaml_string(entity_id)}",
                    f"    source: {_yaml_string(source_id)}",
                    f"    status: {declaration['status']}",
                ]
            )
            if declaration["reason"]:
                lines.append(f"    reason: {_yaml_string(declaration['reason'])}")
    return "\n".join(lines) + "\n"


def _review_csv(review_rows: list[dict[str, Any]]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=_REVIEW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in review_rows:
        writer.writerow(
            {
                "record_id": item["record_id"],
                "source_id": item["source_id"],
                "status": item["status"],
                "normalized_record_name": item["normalized_record_name"] or "",
                "candidate_entity_ids": _canonical_json(item["candidate_entity_ids"]),
                "reason_codes": _canonical_json(item["reason_codes"]),
                "evidence": _canonical_json(item["evidence"]),
            }
        )
    return stream.getvalue().encode("utf-8")


def _resolved_csv(rows: list[dict[str, str]]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=_RESOLVED_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def adapt(
    linkage_path: Path,
    record_sources_path: Path,
    context_path: Path,
) -> dict[str, bytes]:
    entity_ids, sources, declarations = _load_context(context_path)
    results = _load_linkage(linkage_path, set(entity_ids))
    record_sources = _read_record_sources(record_sources_path)

    result_ids = {item["record_id"] for item in results}
    mapping_ids = set(record_sources)
    missing_mappings = sorted(result_ids - mapping_ids)
    unknown_mappings = sorted(mapping_ids - result_ids)
    if missing_mappings:
        raise AdapterError("missing source mapping for record IDs: " + ", ".join(missing_mappings))
    if unknown_mappings:
        raise AdapterError(
            "source mapping references unknown record IDs: " + ", ".join(unknown_mappings)
        )

    resolved_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    resolved_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, Any]] = []
    for result in results:
        record_id = result["record_id"]
        source_id = record_sources[record_id]
        if source_id not in sources:
            raise AdapterError(f"record {record_id!r} maps to unknown source ID {source_id!r}")
        status = result["status"]
        if status == "resolved":
            entity_id = result["entity_id"]
            pair = (entity_id, source_id)
            resolved_by_pair[pair].append(record_id)
            resolved_rows.append(
                {"entity_id": entity_id, "source_id": source_id, "record_id": record_id}
            )
        else:
            review_rows.append({**result, "source_id": source_id})

    for pair in resolved_by_pair:
        if pair in declarations and declarations[pair]["status"] == "not_applicable":
            raise AdapterError(
                f"resolved evidence for {pair[0]!r}/{pair[1]!r} conflicts with not_applicable"
            )
        if sources[pair[1]] in {"unavailable", "not_in_release"}:
            raise AdapterError(
                f"resolved evidence for {pair[0]!r}/{pair[1]!r} conflicts with "
                f"source availability {sources[pair[1]]!r}"
            )

    resolved_rows.sort(key=lambda item: (item["entity_id"], item["source_id"], item["record_id"]))
    review_rows.sort(key=lambda item: item["record_id"])
    return {
        "coverage.yaml": _coverage_yaml(entity_ids, sources, declarations, resolved_by_pair).encode(
            "utf-8"
        ),
        "review.csv": _review_csv(review_rows),
        "resolved-records.csv": _resolved_csv(resolved_rows),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linkage", required=True, type=Path, help="EntityLinkage linkage.json")
    parser.add_argument(
        "--record-sources", required=True, type=Path, help="record_id-to-source_id CSV"
    )
    parser.add_argument("--context", required=True, type=Path, help="coverage context JSON")
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="directory for adapter outputs"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        outputs = adapt(args.linkage, args.record_sources, args.context)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in outputs.items():
            temporary = args.output_dir / f".{name}.tmp"
            temporary.write_bytes(content)
            temporary.replace(args.output_dir / name)
    except (AdapterError, OSError, ValueError) as error:
        print(f"entitylinkage-coverage-adapter: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

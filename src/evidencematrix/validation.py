"""Manifest validation and conversion into the public model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from evidencematrix.model import (
    COVERAGE_STATUS_ORDER,
    Coverage,
    CoverageStatus,
    Entity,
    Manifest,
    Source,
    SourceAvailability,
)


class ManifestError(ValueError):
    """Raised when an input manifest is malformed or internally inconsistent."""


def _mapping(value: Any, *, field: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{field} must be a mapping")
        return None
    if any(not isinstance(key, str) for key in value):
        errors.append(f"{field} keys must be strings")
        return None
    return value


def _check_fields(
    value: Mapping[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    field: str,
    errors: list[str],
) -> None:
    missing = sorted(required - value.keys())
    unexpected = sorted(value.keys() - allowed)
    if missing:
        errors.append(f"{field} is missing required field(s): {', '.join(missing)}")
    if unexpected:
        errors.append(f"{field} has unknown field(s): {', '.join(unexpected)}")


def _identifier(value: Any, *, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value or value.strip() != value:
        errors.append(f"{field} must be a non-empty string without surrounding whitespace")
        return None
    return value


def validate_document(document: Any) -> Manifest:
    """Validate a parsed manifest document and return immutable typed data."""

    errors: list[str] = []
    root = _mapping(document, field="manifest", errors=errors)
    if root is None:
        raise ManifestError("invalid manifest: " + "; ".join(errors))
    _check_fields(
        root,
        required={"version", "entities", "sources", "coverage"},
        allowed={"version", "entities", "sources", "coverage"},
        field="manifest",
        errors=errors,
    )

    version = root.get("version")
    if type(version) is not int or version != 1:
        errors.append("version must be the integer 1")

    raw_entities = root.get("entities")
    entities: list[Entity] = []
    entity_ids: set[str] = set()
    if not isinstance(raw_entities, list):
        errors.append("entities must be a list")
    else:
        for index, raw_entity in enumerate(raw_entities):
            field = f"entities[{index}]"
            entity = _mapping(raw_entity, field=field, errors=errors)
            if entity is None:
                continue
            _check_fields(entity, required={"id"}, allowed={"id"}, field=field, errors=errors)
            entity_id = _identifier(entity.get("id"), field=f"{field}.id", errors=errors)
            if entity_id is None:
                continue
            if entity_id in entity_ids:
                errors.append(f"duplicate entity id: {entity_id}")
            else:
                entity_ids.add(entity_id)
                entities.append(Entity(id=entity_id))

    raw_sources = root.get("sources")
    sources: list[Source] = []
    source_by_id: dict[str, Source] = {}
    if not isinstance(raw_sources, list):
        errors.append("sources must be a list")
    else:
        for index, raw_source in enumerate(raw_sources):
            field = f"sources[{index}]"
            source = _mapping(raw_source, field=field, errors=errors)
            if source is None:
                continue
            _check_fields(
                source,
                required={"id", "availability"},
                allowed={"id", "availability"},
                field=field,
                errors=errors,
            )
            source_id = _identifier(source.get("id"), field=f"{field}.id", errors=errors)
            availability_value = source.get("availability")
            try:
                availability = SourceAvailability(availability_value)
            except (ValueError, TypeError):
                errors.append(
                    f"{field}.availability must be one of: "
                    + ", ".join(item.value for item in SourceAvailability)
                )
                availability = None
            if source_id is None or availability is None:
                continue
            if source_id in source_by_id:
                errors.append(f"duplicate source id: {source_id}")
                continue
            parsed_source = Source(id=source_id, availability=availability)
            source_by_id[source_id] = parsed_source
            sources.append(parsed_source)

    raw_coverage = root.get("coverage")
    coverage: list[Coverage] = []
    seen_pairs: set[tuple[str, str]] = set()
    if not isinstance(raw_coverage, list):
        errors.append("coverage must be a list")
    else:
        for index, raw_record in enumerate(raw_coverage):
            field = f"coverage[{index}]"
            record = _mapping(raw_record, field=field, errors=errors)
            if record is None:
                continue
            _check_fields(
                record,
                required={"entity", "source", "status"},
                allowed={"entity", "source", "status", "reason"},
                field=field,
                errors=errors,
            )
            entity_id = _identifier(record.get("entity"), field=f"{field}.entity", errors=errors)
            source_id = _identifier(record.get("source"), field=f"{field}.source", errors=errors)
            try:
                status = CoverageStatus(record.get("status"))
            except (ValueError, TypeError):
                errors.append(
                    f"{field}.status is invalid; expected one of: "
                    + ", ".join(item.value for item in COVERAGE_STATUS_ORDER)
                )
                status = None
            reason = record.get("reason")
            if reason is not None and (
                not isinstance(reason, str) or not reason or reason.strip() != reason
            ):
                errors.append(f"{field}.reason must be a non-empty string when supplied")
                reason = None
            if status is CoverageStatus.SUPPORTED and reason is not None:
                errors.append(f"{field}.reason is only valid for non-supported coverage")
            if entity_id is None or source_id is None or status is None:
                continue
            if entity_id not in entity_ids:
                errors.append(f"{field} references unknown entity: {entity_id}")
            if source_id not in source_by_id:
                errors.append(f"{field} references unknown source: {source_id}")
            pair = (entity_id, source_id)
            if pair in seen_pairs:
                errors.append(f"duplicate coverage relationship: {entity_id} × {source_id}")
            else:
                seen_pairs.add(pair)
            source = source_by_id.get(source_id)
            if source is not None:
                conflicting_availability = {
                    CoverageStatus.SUPPORTED: {
                        SourceAvailability.UNAVAILABLE,
                        SourceAvailability.NOT_IN_RELEASE,
                    },
                    CoverageStatus.SOURCE_UNAVAILABLE: {
                        SourceAvailability.AVAILABLE,
                        SourceAvailability.NOT_IN_RELEASE,
                    },
                    CoverageStatus.SOURCE_NOT_IN_RELEASE: {
                        SourceAvailability.AVAILABLE,
                        SourceAvailability.UNAVAILABLE,
                    },
                }.get(status, set())
                if source.availability in conflicting_availability:
                    errors.append(
                        f"{field}.status {status.value} conflicts with source availability "
                        f"{source.availability.value}"
                    )
            coverage.append(
                Coverage(entity=entity_id, source=source_id, status=status, reason=reason)
            )

    if errors:
        raise ManifestError("invalid manifest: " + "; ".join(errors))
    return Manifest(
        version=version,
        entities=tuple(entities),
        sources=tuple(sources),
        coverage=tuple(coverage),
    )

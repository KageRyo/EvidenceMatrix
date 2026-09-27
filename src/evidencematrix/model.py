"""Typed, immutable data structures for coverage manifests and reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_IN_RELEASE = "not_in_release"
    UNKNOWN = "unknown"


class CoverageStatus(StrEnum):
    SUPPORTED = "supported"
    METADATA_GAP = "metadata_gap"
    MAPPING_GAP = "mapping_gap"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_NOT_IN_RELEASE = "source_not_in_release"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


COVERAGE_STATUS_ORDER = tuple(CoverageStatus)
UNRESOLVED_STATUSES = frozenset(
    {
        CoverageStatus.METADATA_GAP,
        CoverageStatus.MAPPING_GAP,
        CoverageStatus.SOURCE_UNAVAILABLE,
        CoverageStatus.SOURCE_NOT_IN_RELEASE,
        CoverageStatus.UNKNOWN,
    }
)


@dataclass(frozen=True, slots=True)
class Entity:
    id: str


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    availability: SourceAvailability


@dataclass(frozen=True, slots=True)
class Coverage:
    entity: str
    source: str
    status: CoverageStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Manifest:
    version: int
    entities: tuple[Entity, ...]
    sources: tuple[Source, ...]
    coverage: tuple[Coverage, ...]


@dataclass(frozen=True, slots=True)
class CoverageRecord:
    entity_id: str
    source_id: str
    source_availability: SourceAvailability
    status: CoverageStatus
    reason: str | None


@dataclass(frozen=True, slots=True)
class Summary:
    entity_count: int
    source_count: int
    relationship_count: int
    status_counts: dict[str, int]
    finding_count: int


@dataclass(frozen=True, slots=True)
class AuditReport:
    relationship_count: int
    status_counts: dict[str, int]
    finding_count: int
    findings: tuple[CoverageRecord, ...]

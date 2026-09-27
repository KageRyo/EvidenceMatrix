"""Pure entity-by-source coverage expansion and counting."""

from __future__ import annotations

from evidencematrix.model import (
    COVERAGE_STATUS_ORDER,
    UNRESOLVED_STATUSES,
    CoverageRecord,
    CoverageStatus,
    Manifest,
    SourceAvailability,
    Summary,
)


def build_matrix(manifest: Manifest) -> tuple[CoverageRecord, ...]:
    """Expand every entity/source pair, preserving explicit unknowns and gaps."""

    declarations = {(item.entity, item.source): item for item in manifest.coverage}
    records: list[CoverageRecord] = []
    for entity in sorted(manifest.entities, key=lambda item: item.id):
        for source in sorted(manifest.sources, key=lambda item: item.id):
            declaration = declarations.get((entity.id, source.id))
            if declaration is not None:
                status = declaration.status
                reason = declaration.reason
            elif source.availability is SourceAvailability.UNAVAILABLE:
                status = CoverageStatus.SOURCE_UNAVAILABLE
                reason = "source_declared_unavailable"
            elif source.availability is SourceAvailability.NOT_IN_RELEASE:
                status = CoverageStatus.SOURCE_NOT_IN_RELEASE
                reason = "source_declared_not_in_release"
            else:
                status = CoverageStatus.UNKNOWN
                reason = "coverage_not_declared"
            records.append(
                CoverageRecord(
                    entity_id=entity.id,
                    source_id=source.id,
                    source_availability=source.availability,
                    status=status,
                    reason=reason,
                )
            )
    return tuple(records)


def summarize_matrix(manifest: Manifest, matrix: tuple[CoverageRecord, ...]) -> Summary:
    """Count matrix rows by status; not-applicable rows are not audit findings."""

    counts = {status.value: 0 for status in COVERAGE_STATUS_ORDER}
    for record in matrix:
        counts[record.status.value] += 1
    return Summary(
        entity_count=len(manifest.entities),
        source_count=len(manifest.sources),
        relationship_count=len(matrix),
        status_counts=counts,
        finding_count=sum(counts[status.value] for status in UNRESOLVED_STATUSES),
    )

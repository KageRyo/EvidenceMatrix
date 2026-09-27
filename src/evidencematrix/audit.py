"""Coverage finding selection without subjective scoring."""

from __future__ import annotations

from evidencematrix.model import (
    COVERAGE_STATUS_ORDER,
    UNRESOLVED_STATUSES,
    AuditReport,
    CoverageRecord,
)


def audit_matrix(matrix: tuple[CoverageRecord, ...]) -> AuditReport:
    """Return unresolved relationships; supported and not-applicable rows are excluded."""

    counts = {status.value: 0 for status in COVERAGE_STATUS_ORDER}
    for record in matrix:
        counts[record.status.value] += 1
    findings = tuple(record for record in matrix if record.status in UNRESOLVED_STATUSES)
    return AuditReport(
        relationship_count=len(matrix),
        status_counts=counts,
        finding_count=len(findings),
        findings=findings,
    )

"""Command line interface for EvidenceMatrix."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from evidencematrix.audit import audit_matrix
from evidencematrix.matrix import build_matrix, summarize_matrix
from evidencematrix.output import (
    audit_to_dict,
    build_artifacts,
    summary_to_dict,
    write_artifacts,
)
from evidencematrix.parser import load_manifest
from evidencematrix.validation import ManifestError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidencematrix",
        description="Build deterministic entity-by-source coverage audits.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "build", "audit", "summary"):
        subparser = commands.add_parser(command)
        subparser.add_argument(
            "path", type=Path, help="manifest file or directory containing one manifest"
        )
        if command == "build":
            subparser.add_argument("--output", type=Path, default=Path("evidencematrix-output"))
        if command in {"audit", "summary"}:
            subparser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _status_text(counts: dict[str, int]) -> str:
    return "\n".join(f"{status}: {count}" for status, count in counts.items())


def _run(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.path)
    if args.command == "validate":
        print(f"valid: {args.path}")
        return 0

    matrix = build_matrix(manifest)
    summary = summarize_matrix(manifest, matrix)
    if args.command == "build":
        artifacts = build_artifacts(manifest, matrix, summary)
        paths = write_artifacts(artifacts, args.output)
        print(f"built {len(paths)} artifacts: {args.output}")
        return 0
    if args.command == "audit":
        report = audit_matrix(matrix)
        if args.format == "json":
            print(json.dumps(audit_to_dict(matrix), ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print(f"Relationships: {report.relationship_count}")
            print(f"Unresolved findings: {report.finding_count}")
            print(
                "\n".join(
                    f"{status}: {count}"
                    for status, count in report.status_counts.items()
                    if status not in {"supported", "not_applicable"}
                )
            )
            print(f"not_applicable (excluded): {report.status_counts['not_applicable']}")
        return 1 if report.finding_count else 0
    if args.command == "summary":
        if args.format == "json":
            print(
                json.dumps(summary_to_dict(summary), ensure_ascii=False, sort_keys=True, indent=2)
            )
        else:
            print(f"Entities: {summary.entity_count}")
            print(f"Sources: {summary.source_count}")
            print(f"Relationships: {summary.relationship_count}")
            print(_status_text(summary.status_counts))
            print(f"Unresolved findings: {summary.finding_count}")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command and return its documented process exit code."""

    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except (ManifestError, OSError) as exc:
        print(f"evidencematrix: error: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())

#!/usr/bin/env bash
set -euo pipefail

example_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -gt 1 ]]; then
  printf 'usage: %s [OUTPUT_DIR]\n' "$0" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  output_dir="$1"
else
  output_dir="$(mktemp -d "${TMPDIR:-/tmp}/entitylinkage-coverage.XXXXXX")"
fi
mkdir -p "$output_dir"

run_case() {
  local label="$1"
  local config="$2"
  local case_dir="$output_dir/$label"
  local linkage_dir="$case_dir/entitylinkage"
  local adapter_dir="$case_dir/adapter"
  local report_dir="$case_dir/evidencematrix"

  entitylinkage validate "$config"
  entitylinkage link "$config" --output "$linkage_dir"
  python "$example_dir/adapter.py" \
    --linkage "$linkage_dir/linkage.json" \
    --record-sources "$example_dir/record-sources.csv" \
    --context "$example_dir/coverage-context.json" \
    --output-dir "$adapter_dir"
  evidencematrix validate "$adapter_dir/coverage.yaml"
  evidencematrix build "$adapter_dir/coverage.yaml" --output "$report_dir"
  evidencematrix summary "$adapter_dir/coverage.yaml" --format json > "$case_dir/summary.json"

  local audit_status=0
  if evidencematrix audit "$adapter_dir/coverage.yaml" --format json > "$case_dir/audit.json"; then
    audit_status=0
  else
    audit_status=$?
  fi
  if [[ "$audit_status" -ne 1 ]]; then
    printf 'expected EvidenceMatrix audit exit code 1 for %s, got %s\n' \
      "$label" "$audit_status" >&2
    return 1
  fi
}

run_case before-review "$example_dir/entitylinkage.yaml"
run_case after-review "$example_dir/entitylinkage-reviewed.yaml"

python - "$output_dir" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected = {
    "before-review": {"supported": 2, "mapping_gap": 2, "not_applicable": 1, "unknown": 3},
    "after-review": {"supported": 3, "mapping_gap": 1, "not_applicable": 1, "unknown": 3},
}
for case, status_counts in expected.items():
    case_dir = root / case
    summary = json.loads((case_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["relationship_count"] == 16, (case, summary)
    for status, count in status_counts.items():
        assert summary["status_counts"][status] == count, (case, status, summary)

before = json.loads((root / "before-review/entitylinkage/linkage.json").read_text(encoding="utf-8"))
after = json.loads((root / "after-review/entitylinkage/linkage.json").read_text(encoding="utf-8"))
before_statuses = {item["record_id"]: item["status"] for item in before["results"]}
after_statuses = {item["record_id"]: item["status"] for item in after["results"]}
assert before_statuses["record-a-002"] == "ambiguous"
assert after_statuses["record-a-002"] == "resolved"
assert after_statuses["record-a-003"] == "unresolved"
assert after_statuses["record-b-002"] == "not_applicable"

with (root / "before-review/adapter/review.csv").open(encoding="utf-8", newline="") as stream:
    before_reviews = {row["record_id"]: row["status"] for row in csv.DictReader(stream)}
with (root / "after-review/adapter/review.csv").open(encoding="utf-8", newline="") as stream:
    after_reviews = {row["record_id"]: row["status"] for row in csv.DictReader(stream)}
assert before_reviews == {
    "record-a-002": "ambiguous",
    "record-a-003": "unresolved",
    "record-b-002": "not_applicable",
}
assert after_reviews == {
    "record-a-003": "unresolved",
    "record-b-002": "not_applicable",
}
print(f"integration example passed; reports are in {root}")
PY

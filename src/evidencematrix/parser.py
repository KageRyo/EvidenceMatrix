"""Offline YAML and JSON manifest loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from evidencematrix.model import Manifest
from evidencematrix.validation import ManifestError, validate_document


class _UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _manifest_path(path: Path) -> Path:
    if path.is_dir():
        candidates = sorted(
            candidate
            for candidate in path.iterdir()
            if candidate.is_file() and candidate.suffix.casefold() in {".yaml", ".yml", ".json"}
        )
        if len(candidates) != 1:
            raise ManifestError(
                "input directory must contain exactly one .yaml, .yml, or .json manifest; "
                f"found {len(candidates)}"
            )
        return candidates[0]
    if not path.is_file():
        raise ManifestError(f"input path is not a file or directory: {path}")
    if path.suffix.casefold() not in {".yaml", ".yml", ".json"}:
        raise ManifestError(f"manifest file must end in .yaml, .yml, or .json: {path.name}")
    return path


def _parse_text(text: str, *, suffix: str) -> Any:
    if suffix.casefold() == ".json":
        return json.loads(text, object_pairs_hook=_json_object)
    return yaml.load(text, Loader=_UniqueKeyLoader)


def load_manifest(path: str | Path) -> Manifest:
    """Load and validate one YAML or JSON manifest from a file or directory."""

    selected_path = _manifest_path(Path(path).expanduser())
    try:
        text = selected_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ManifestError(f"cannot read manifest {selected_path}: {exc}") from exc
    try:
        document = _parse_text(text, suffix=selected_path.suffix)
    except (json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
        raise ManifestError(f"cannot parse manifest {selected_path}: {exc}") from exc
    return validate_document(document)

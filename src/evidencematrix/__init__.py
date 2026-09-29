"""A deterministic source-coverage audit tool for multi-source datasets."""

from evidencematrix.matrix import build_matrix, summarize_matrix
from evidencematrix.model import CoverageStatus, SourceAvailability
from evidencematrix.parser import load_manifest
from evidencematrix.validation import ManifestError, validate_document

__all__ = [
    "CoverageStatus",
    "ManifestError",
    "SourceAvailability",
    "build_matrix",
    "load_manifest",
    "summarize_matrix",
    "validate_document",
]

__version__ = "0.1.1"

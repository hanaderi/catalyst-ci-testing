"""Test file discovery for YAML and Python test files."""

from __future__ import annotations

from pathlib import Path

import yaml

from .yaml_schema import YamlTestCase


def discover_test_files(
    path: Path,
    yaml_patterns: list[str] | None = None,
    py_patterns: list[str] | None = None,
) -> tuple[list[Path], list[Path]]:
    """Discover YAML and Python test files.

    Returns (yaml_files, py_files).
    """
    if yaml_patterns is None:
        yaml_patterns = ["**/*.test.yml", "**/*.test.yaml"]
    if py_patterns is None:
        py_patterns = ["**/test_*.py", "**/*_test.py"]

    yaml_files: list[Path] = []
    py_files: list[Path] = []

    if path.is_file():
        suffix = path.suffix
        if suffix in (".yml", ".yaml"):
            yaml_files.append(path)
        elif suffix == ".py":
            py_files.append(path)
        return yaml_files, py_files

    for pattern in yaml_patterns:
        yaml_files.extend(sorted(path.glob(pattern)))
    for pattern in py_patterns:
        py_files.extend(sorted(path.glob(pattern)))

    return yaml_files, py_files


def load_yaml_test_cases(path: Path) -> list[tuple[YamlTestCase, Path]]:
    """Load all test cases from a YAML file (supports multi-document YAML)."""
    content = path.read_text(encoding="utf-8")
    documents = list(yaml.safe_load_all(content))

    cases: list[tuple[YamlTestCase, Path]] = []
    for doc in documents:
        if doc is None:
            continue
        case = YamlTestCase.model_validate(doc)
        cases.append((case, path))

    return cases

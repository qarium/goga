from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from goga.manifest.project import Project


def _load_expected(case_dir: Path) -> list[dict]:
    expected_file = case_dir / ".expected.yaml"
    with open(expected_file) as f:
        data = yaml.safe_load(f)
    return data["errors"]


def _collect_cases(project_root: Path) -> list[Path]:
    if not project_root.is_dir():
        return []
    return sorted(
        d for d in project_root.rglob("*")
        if d.is_dir() and (d / ".expected.yaml").exists()
    )


@pytest.mark.parametrize(
    "case_dir",
    _collect_cases(Path(__file__).parent.parent.parent / ".project"),
    ids=lambda d: str(d.relative_to(Path(__file__).parent.parent.parent / ".project")),
)
def test_project_rules(case_dir: Path, project_root: Path) -> None:
    origin = os.getcwd()
    os.chdir(str(project_root))
    try:
        project = Project(path=".")
        project.load()

        expected_errors = _load_expected(case_dir)

        case_rel = os.path.normpath(case_dir.relative_to(project_root))
        case_errors = [
            e for e in project.errors if os.path.normpath(e.document.path) == case_rel
        ]
    finally:
        os.chdir(origin)

    unmatched: list[dict] = []
    remaining = list(case_errors)

    for expected in expected_errors:
        found = False
        for i, actual in enumerate(remaining):
            if (
                actual.rule == expected["rule"]
                and actual.message == expected["message"]
                and os.path.normpath(actual.document.path) == expected["document_path"]
                and actual.node.data == expected["node_data"]
            ):
                remaining.pop(i)
                found = True
                break
        if not found:
            unmatched.append(expected)

    assert not unmatched, (
        f"Unmatched expected errors ({len(unmatched)}):\n"
        + "\n".join(f"  rule={e['rule']!r}, message={e['message']!r}" for e in unmatched)
    )
    assert not remaining, (
        f"Unexpected actual errors ({len(remaining)}):\n"
        + "\n".join(f"  rule={e.rule!r}, message={e.message!r}" for e in remaining)
    )

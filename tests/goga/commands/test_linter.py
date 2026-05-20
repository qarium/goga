from __future__ import annotations

import os
from pathlib import Path

import click
from click.testing import CliRunner
from goga.commands import linter
from goga.commands.linter import linter as linter_cmd

VALID_CODEMANIFEST = """\
Imports:
  - Types:
      - MyHelper
    From: {child_path}

Usages: {}

Annotations: |
  Uses `MyHelper` here

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""

CHILD_CODEMANIFEST = """\
Usages: {}

Annotations: ""

---
"MyHelper()":
  location: helper.py
  annotations: |
    A helper

---
Author: Test
CreatedAt: 11/04/26
Description: Helper
"""

INVALID_CODEMANIFEST = """\
Imports:
  - Types:
      - NonExistent
    From: non/existent/path

Usages: {}

Annotations: ""

---
"MyClass()":
  location: myclass.py
  annotations: |
    A test class

---
Author: Test
CreatedAt: 11/04/26
Description: Test
"""


def _write_codemanifest(directory, content: str) -> None:
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def _setup_valid_project(tmp_path) -> str:
    project_dir = tmp_path / "valid_project"
    project_dir.mkdir()
    child_dir = project_dir / "helper"
    child_dir.mkdir()
    child_rel = "helper"
    manifest = VALID_CODEMANIFEST.replace("{child_path}", child_rel)
    _write_codemanifest(project_dir, manifest)
    _write_codemanifest(child_dir, CHILD_CODEMANIFEST)
    return str(project_dir)


def _run_linter(path: str) -> click.testing.Result:
    original_cwd = str(Path.cwd())
    try:
        runner = CliRunner()
        return runner.invoke(linter_cmd, [path])
    finally:
        os.chdir(original_cwd)


class TestFacadeAvailability:
    def test_import_linter_from_commands(self) -> None:
        assert linter is not None

    def test_linter_is_click_command(self) -> None:
        assert isinstance(linter_cmd, click.Command)


class TestApiShape:
    def test_linter_has_callback(self) -> None:
        assert linter_cmd.callback is not None

    def test_linter_has_path_argument(self) -> None:
        param_names = [p.name for p in linter_cmd.params]
        assert "path" in param_names

    def test_linter_path_default_is_dot(self) -> None:
        path_param = next(p for p in linter_cmd.params if p.name == "path")
        assert path_param.default == "."


class TestNegativeRun:
    def test_errors_produce_output(self, tmp_path) -> None:
        project_dir = tmp_path / "bad_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        assert result.output != ""

    def test_output_contains_rule_name(self, tmp_path) -> None:
        project_dir = tmp_path / "bad_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        assert "[import_has_valid_from_path]" in result.output


class TestEdgeNonExistentPath:
    def test_nonexistent_path_raises_error(self, tmp_path) -> None:
        nonexistent = str(tmp_path / "does_not_exist")
        result = _run_linter(nonexistent)
        assert result.exit_code != 0
        assert isinstance(result.exception, FileNotFoundError)


class TestErrorFormat:
    def test_bracketed_rule_name_first_line(self, tmp_path) -> None:
        project_dir = tmp_path / "fmt_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        lines = result.output.strip().splitlines()
        assert lines[0].startswith("[")
        assert "]" in lines[0]
        assert "import_has_valid_from_path" in lines[0]

    def test_arrow_with_doc_path(self, tmp_path) -> None:
        project_dir = tmp_path / "arrow_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        assert "-->" in result.output

    def test_yaml_data_with_6_space_indent(self, tmp_path) -> None:
        project_dir = tmp_path / "yaml_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        lines = result.output.splitlines()
        yaml_lines = [ln for ln in lines if ln.startswith("      ")]
        assert len(yaml_lines) > 0

    def test_error_format_structure(self, tmp_path) -> None:
        project_dir = tmp_path / "structure_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        lines = result.output.strip().splitlines()
        assert lines[0].startswith("[")
        assert "  -->" in result.output
        yaml_lines = [ln for ln in lines if ln.startswith("      ")]
        assert len(yaml_lines) > 0

    def test_separator_between_arrow_and_yaml(self, tmp_path) -> None:
        project_dir = tmp_path / "sep_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        lines = result.output.splitlines()
        # Find the arrow line, next non-empty line with 6-space indent should be ---
        arrow_idx = None
        for i, line in enumerate(lines):
            if line.startswith("  -->"):
                arrow_idx = i
                break
        assert arrow_idx is not None, "No arrow line found in output"
        # After arrow, the next line with 6-space indent should be ---
        after_arrow = lines[arrow_idx + 1 :]
        sep_line = next((ln for ln in after_arrow if ln.startswith("      ")), None)
        assert sep_line is not None, "No 6-space indented line after arrow"
        assert sep_line.strip() == "---", f"Expected '---' separator, got: {sep_line!r}"


class TestExitCodes:
    def test_invalid_project_exits_one(self, tmp_path) -> None:
        project_dir = tmp_path / "exit_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_linter(str(project_dir))

        assert result.exit_code == 1

    def test_valid_project_exits_zero(self, tmp_path) -> None:
        project_dir = _setup_valid_project(tmp_path)

        result = _run_linter(project_dir)

        assert result.exit_code == 0

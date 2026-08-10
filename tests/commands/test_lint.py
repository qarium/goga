from __future__ import annotations

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands import lint
from goga.commands.lint import lint as lint_cmd

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


MINIMAL_VALID_CODEMANIFEST = 'Usages: {}\nAnnotations: ""\n'


def _write_goga_config(directory, content: str) -> None:
    goga_dir = directory / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(content, encoding="utf-8")


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


def _run_lint(path: str) -> click.testing.Result:
    runner = CliRunner()
    return runner.invoke(lint_cmd, [path])


class TestFacadeAvailability:
    def test_import_lint_from_commands(self) -> None:
        assert lint is not None

    def test_lint_is_click_command(self) -> None:
        assert isinstance(lint_cmd, click.Command)

    def test_lint_imports_load_project_config(self) -> None:
        """lint imports load_project_config from goga.config (NEW lint -> config edge).

        The module is fetched via sys.modules because the package ``__init__``
        re-exports ``lint`` (the function), shadowing the submodule name.
        """
        import sys

        from goga.config import load_project_config

        lint_module = sys.modules["goga.commands.lint.lint"]
        assert hasattr(lint_module, "load_project_config")
        assert lint_module.load_project_config is load_project_config


class TestApiShape:
    def test_lint_has_callback(self) -> None:
        assert lint_cmd.callback is not None

    def test_lint_has_path_argument(self) -> None:
        param_names = [p.name for p in lint_cmd.params]
        assert "path" in param_names

    def test_lint_path_default_is_dot(self) -> None:
        path_param = next(p for p in lint_cmd.params if p.name == "path")
        assert path_param.default == "."


class TestNegativeRun:
    def test_errors_produce_output(self, tmp_path) -> None:
        project_dir = tmp_path / "bad_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        assert result.output != ""

    def test_output_contains_rule_name(self, tmp_path) -> None:
        project_dir = tmp_path / "bad_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        assert "[import_has_valid_from_path]" in result.output


class TestEdgeNonExistentPath:
    def test_nonexistent_path_raises_error(self, tmp_path) -> None:
        nonexistent = str(tmp_path / "does_not_exist")
        result = _run_lint(nonexistent)
        assert result.exit_code != 0
        assert isinstance(result.exception, FileNotFoundError)


class TestErrorFormat:
    def test_bracketed_rule_name_first_line(self, tmp_path) -> None:
        project_dir = tmp_path / "fmt_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        lines = result.output.strip().splitlines()
        assert lines[0].startswith("[")
        assert "]" in lines[0]
        assert "import_has_valid_from_path" in lines[0]

    def test_arrow_with_doc_path(self, tmp_path) -> None:
        project_dir = tmp_path / "arrow_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        assert "-->" in result.output

    def test_yaml_data_with_6_space_indent(self, tmp_path) -> None:
        project_dir = tmp_path / "yaml_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        lines = result.output.splitlines()
        yaml_lines = [ln for ln in lines if ln.startswith("      ")]
        assert len(yaml_lines) > 0

    def test_error_format_structure(self, tmp_path) -> None:
        project_dir = tmp_path / "structure_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        lines = result.output.strip().splitlines()
        assert lines[0].startswith("[")
        assert "  -->" in result.output
        yaml_lines = [ln for ln in lines if ln.startswith("      ")]
        assert len(yaml_lines) > 0

    def test_separator_between_arrow_and_yaml(self, tmp_path) -> None:
        project_dir = tmp_path / "sep_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

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


class TestSummary:
    def test_summary_output_valid_project(self, tmp_path) -> None:
        project_dir = _setup_valid_project(tmp_path)

        result = _run_lint(project_dir)

        assert "cells: 2 errors: 0" in result.output
        assert "goga lint" in result.output
        assert "-------------------------" in result.output
        assert result.exit_code == 0

    def test_summary_after_errors(self, tmp_path) -> None:
        project_dir = tmp_path / "bad_summary"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        assert "cells: 1 errors: 2" in result.output
        assert "goga lint" in result.output
        assert result.exit_code == 1


class TestSummaryBehavior:
    def test_summary_format_exact(self, tmp_path) -> None:
        project_dir = _setup_valid_project(tmp_path)

        result = _run_lint(project_dir)

        lines = result.output.splitlines()
        summary_lines = [ln for ln in lines if ln == "goga lint"]
        assert len(summary_lines) == 1
        idx = lines.index("goga lint")
        assert lines[idx + 1] == "-------------------------"
        assert lines[idx + 2] == "cells: 2 errors: 0"

    def test_summary_minimal_project_no_errors(self, tmp_path) -> None:
        empty_dir = tmp_path / "empty_project"
        empty_dir.mkdir()
        (empty_dir / "CODEMANIFEST").write_text(
            'Usages: {}\nAnnotations: ""\n',
            encoding="utf-8",
        )

        result = _run_lint(str(empty_dir))

        assert "cells: 1 errors: 0" in result.output
        assert "goga lint" in result.output
        assert result.exit_code == 0

    def test_empty_line_before_summary(self, tmp_path) -> None:
        project_dir = tmp_path / "empty_line_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        lines = result.output.splitlines()
        yaml_lines = [i for i, ln in enumerate(lines) if ln.startswith("      ")]
        assert len(yaml_lines) > 0
        last_yaml = yaml_lines[-1]
        assert lines[last_yaml + 1] == ""
        assert lines[last_yaml + 2] == "goga lint"


class TestExitCodes:
    def test_invalid_project_exits_one(self, tmp_path) -> None:
        project_dir = tmp_path / "exit_project"
        project_dir.mkdir()
        _write_codemanifest(project_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(project_dir))

        assert result.exit_code == 1

    def test_valid_project_exits_zero(self, tmp_path) -> None:
        project_dir = _setup_valid_project(tmp_path)

        result = _run_lint(project_dir)

        assert result.exit_code == 0


class TestIgnoreDerivation:
    def test_lint_derives_ignore_from_config(self, tmp_path) -> None:
        _write_goga_config(tmp_path, "language: python\nlint:\n  ignore:\n    - .venv/\n")
        _write_codemanifest(tmp_path, MINIMAL_VALID_CODEMANIFEST)
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        _write_codemanifest(venv_dir, INVALID_CODEMANIFEST)

        result = _run_lint(str(tmp_path))

        assert result.exit_code == 0
        assert ".venv" not in result.output

    def test_lint_runs_unfiltered_when_config_absent(self, tmp_path) -> None:
        _write_codemanifest(tmp_path, INVALID_CODEMANIFEST)

        result = _run_lint(str(tmp_path))

        assert result.exit_code == 1
        assert "FileNotFoundError" not in result.output

    def test_lint_unfiltered_when_lint_section_absent(self, tmp_path) -> None:
        _write_goga_config(tmp_path, "language: python\n")
        _write_codemanifest(tmp_path, INVALID_CODEMANIFEST)

        result = _run_lint(str(tmp_path))

        assert result.exit_code == 1
        assert "FileNotFoundError" not in result.output

    def test_lint_treats_invalid_config_as_unfiltered(self, tmp_path) -> None:
        _write_goga_config(tmp_path, "language: python: [unclosed")
        _write_codemanifest(tmp_path, INVALID_CODEMANIFEST)

        result = _run_lint(str(tmp_path))

        assert result.exit_code in (0, 1)
        assert "YAMLError" not in result.output


class TestCliAppIntegration:
    """Feature B wired end-to-end through the full ``goga`` CLI app.

    Task 4's ``TestIgnoreDerivation`` exercises the ``lint`` command *function*
    directly (``CliRunner().invoke(lint_cmd, ...)``). This class drives the real
    CLI entrypoint (``CliRunner().invoke(app, ["lint", ...])``) to verify the
    config -> ast -> lint chain is wired correctly through Click's group
    dispatch and the ``app`` facade.
    """

    def test_lint_app_end_to_end_ignores_directory(self, tmp_path) -> None:
        _write_goga_config(tmp_path, "language: python\nlint:\n  ignore:\n    - .venv/\n")
        _write_codemanifest(tmp_path, MINIMAL_VALID_CODEMANIFEST)
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        _write_codemanifest(venv_dir, INVALID_CODEMANIFEST)

        runner = CliRunner()
        result = runner.invoke(app, ["lint", str(tmp_path)])

        assert result.exit_code == 0
        assert ".venv" not in result.output

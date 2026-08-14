from __future__ import annotations

import importlib
import inspect
import sys
import types
from unittest import mock

import click
from click.testing import CliRunner
from goga.ast import AST
from goga.commands.tool import build_injections, tool

# Resolve the inner `tool.py` submodule via importlib. The facade `goga.commands.tool`
# re-exports the click Command `tool`, which shadows the submodule attribute in the
# package `__dict__`. On Python 3.10 `mock.patch("goga.commands.tool.tool.AST")` resolves
# the dotted path through sequential `getattr`, finds the Command where it expects the
# submodule, and raises `AttributeError`. Holding a direct reference to the module makes
# `mock.patch.object` work uniformly across Python versions.
tool_module = importlib.import_module("goga.commands.tool.tool")


class TestFacadeAccessible:
    def test_tool_facade_accessible(self) -> None:
        """The tool symbol is importable from goga.commands.tool."""
        assert tool is not None


class TestToolIsClickCommand:
    def test_tool_is_click_command(self) -> None:
        """The tool object is a click.BaseCommand instance."""
        assert isinstance(tool, click.Command)


class TestToolHasNameArgument:
    def test_tool_has_name_argument(self) -> None:
        """The tool command has a 'name' argument."""
        param_names = [p.name for p in tool.params]
        assert "name" in param_names


class TestToolSuccessfulInvocation:
    def test_tool_successful_invocation(self) -> None:
        """Calling tool with a valid package invokes its main with extra args."""
        captured: list[list[str]] = []

        dummy = types.ModuleType("goga_tool_example")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["example", "arg1", "--flag", "value"])

        assert result.exit_code == 0
        assert captured == [["arg1", "--flag", "value"]]


class TestToolWithNoArgs:
    def test_tool_with_no_args(self) -> None:
        """Calling tool with no extra args invokes main with an empty list."""
        captured: list[list[str]] = []

        dummy = types.ModuleType("goga_tool_empty")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["empty"])

        assert result.exit_code == 0
        assert captured == [[]]


class TestToolPackageNotFound:
    def test_tool_package_not_found(self) -> None:
        """Missing tool package shows a 'not found' error message.

        The import machinery sets `ModuleNotFoundError.name` to the module it
        could not resolve; for a genuinely absent top-level package that equals
        the package name. The mock reflects this so the "not found" branch is
        exercised truthfully (see
        ``test_found_package_with_import_failure_propagates_not_masked_as_not_found``
        for the package-found-but-import-broken case).
        """
        runner = CliRunner()
        with mock.patch.object(
            importlib,
            "import_module",
            side_effect=ModuleNotFoundError("No module named 'goga_tool_nonexistent'", name="goga_tool_nonexistent"),
        ):
            result = runner.invoke(tool, ["nonexistent"])

        assert result.exit_code != 0
        assert "goga_tool_nonexistent" in result.output
        assert "not found" in result.output.lower()


class TestToolNoMainFunction:
    def test_tool_no_main_function(self) -> None:
        """Tool package without a 'main' function shows an error message."""
        dummy = types.ModuleType("goga_tool_nomain")
        # Intentionally no 'main' attribute

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["nomain"])

        assert result.exit_code != 0
        assert "goga_tool_nomain" in result.output
        assert "main" in result.output


class TestToolHelpMessage:
    def test_tool_help_message(self) -> None:
        """The --help flag shows usage info with NAME header."""
        runner = CliRunner()
        result = runner.invoke(tool, ["--help"])

        assert result.exit_code == 0
        assert "NAME" in result.output


class TestBuildInjectionsFacadeExported:
    def test_build_injections_facade_exported(self) -> None:
        """build_injections is importable from the facade, callable, and in __all__."""
        # The module-level `from goga.commands.tool import build_injections, tool`
        # above exercises the facade export path; verify the symbols landed.
        assert callable(build_injections)

        # The goga.commands package shadows the `tool` submodule attribute with the
        # command, so reach the package module via sys.modules for its __all__.
        facade = sys.modules["goga.commands.tool"]
        assert "build_injections" in facade.__all__

        # Signature shape: exactly one parameter named 'main'.
        sig = inspect.signature(build_injections)
        assert list(sig.parameters) == ["main"]


class TestBuildInjectionsPositive:
    def test_build_injections_returns_ast_when_main_declares_ast(self, tmp_path, monkeypatch) -> None:
        """When main declares keyword-only ast, the loaded AST is injected."""
        (tmp_path / "CODEMANIFEST").write_text('Usages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        def f(argv, *, ast):
            return ast

        result = build_injections(f)

        assert result.keys() == {"ast"}
        assert isinstance(result["ast"], AST)
        # Verify .load() actually ran: a fresh AST has an empty tree.
        assert len(result["ast"].tree) >= 1


class TestBuildInjectionsNegative:
    def test_other_named_parameter_does_not_trigger_ast(self) -> None:
        """A keyword-only param not named 'ast' does not build the AST."""

        def f(argv, *, config): ...

        with mock.patch.object(tool_module, "AST") as mock_ast:
            result = build_injections(f)

        assert result == {}
        mock_ast.assert_not_called()


class TestBuildInjectionsEdge:
    def test_positional_only_ast_is_not_supplied(self) -> None:
        """A positional-only 'ast' is keyword-incapable and is not injected."""
        # The `/` marks parameters before it as positional-only; placing `ast`
        # before the marker makes it POSITIONAL_ONLY (keyword-incapable).

        def f(argv, ast, /): ...

        assert inspect.signature(f).parameters["ast"].kind == inspect.Parameter.POSITIONAL_ONLY

        with mock.patch.object(tool_module, "AST") as mock_ast:
            result = build_injections(f)

        assert result == {}
        mock_ast.assert_not_called()

    def test_var_positional_ast_is_not_supplied(self) -> None:
        """A VAR_POSITIONAL 'ast' (*ast) is keyword-incapable and is not injected."""

        def f(argv, *ast): ...

        assert inspect.signature(f).parameters["ast"].kind == inspect.Parameter.VAR_POSITIONAL

        with mock.patch.object(tool_module, "AST") as mock_ast:
            result = build_injections(f)

        assert result == {}
        mock_ast.assert_not_called()

    def test_var_keyword_ast_is_not_supplied(self) -> None:
        """A VAR_KEYWORD 'ast' (**ast) is keyword-incapable and is not injected."""

        def f(argv, **ast): ...

        assert inspect.signature(f).parameters["ast"].kind == inspect.Parameter.VAR_KEYWORD

        with mock.patch.object(tool_module, "AST") as mock_ast:
            result = build_injections(f)

        assert result == {}
        mock_ast.assert_not_called()

    def test_positional_or_keyword_ast_is_supplied(self, tmp_path, monkeypatch) -> None:
        """A positional-or-keyword 'ast' is keyword-capable and is injected."""
        (tmp_path / "CODEMANIFEST").write_text('Usages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        def f(argv, ast=None): ...

        result = build_injections(f)

        assert result.keys() == {"ast"}
        assert isinstance(result["ast"], AST)
        # Verify .load() actually ran: a fresh AST has an empty tree.
        assert len(result["ast"].tree) >= 1


class TestToolSurfaceRegression:
    def test_tool_accepts_name_and_variadic_args_surface(self) -> None:
        """The command surface is unchanged: `goga tool NAME [ARGS]...`."""
        assert tool.name == "tool"
        # NAME is the sole declared parameter and is required.
        assert [p.name for p in tool.params] == ["name"]
        assert tool.params[0].required
        # Variadic trailing ARGS are captured (not parsed as options).
        assert tool.context_settings["allow_extra_args"] is True

    def test_minimal_dummy_invocation_unchanged(self) -> None:
        """Invoking a minimal main(argv) dummy forwards argv unchanged (regression)."""
        captured: list[list[str]] = []
        dummy = types.ModuleType("goga_tool_min")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["min", "x", "y"])

        assert result.exit_code == 0
        assert captured == [["x", "y"]]


class TestToolAstInjection:
    def test_main_with_ast_receives_loaded_ast_as_kwarg(self, tmp_path, monkeypatch) -> None:
        """A main(argv, *, ast) receives argv plus the loaded AST as a keyword argument."""
        (tmp_path / "CODEMANIFEST").write_text('Usages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}

        def main(argv, *, ast):
            captured["argv"] = argv
            captured["ast"] = ast

        dummy = types.ModuleType("goga_tool_asttool")
        dummy.main = main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["asttool", "--flag", "value", "x"])

        assert result.exit_code == 0
        assert captured["argv"] == ["--flag", "value", "x"]
        captured_ast = captured["ast"]
        assert isinstance(captured_ast, AST)
        # Verify .load() actually ran: a fresh AST has an empty tree, and the
        # `hasattr` checks below would pass on an unloaded instance.
        assert len(captured_ast.tree) >= 1

    def test_argv_identical_for_both_entry_point_forms(self) -> None:
        """Both main(argv) and main(argv, *, ast) receive identical argv."""
        min_captured: list[list[str]] = []
        ext_captured: list[list[str]] = []

        min_dummy = types.ModuleType("goga_tool_min")

        def min_main(argv):
            min_captured.append(argv)

        min_dummy.main = min_main  # type: ignore[attr-defined]

        ext_dummy = types.ModuleType("goga_tool_ext")

        def ext_main(argv, *, ast):
            ext_captured.append(argv)

        ext_dummy.main = ext_main  # type: ignore[attr-defined]

        argv = ["--flag", "value", "x"]
        runner = CliRunner()
        # AST patched as a no-op stub so no filesystem load occurs for either form.
        with mock.patch.object(tool_module, "AST"):
            with mock.patch.object(importlib, "import_module", return_value=min_dummy):
                runner.invoke(tool, ["min", *argv])
            with mock.patch.object(importlib, "import_module", return_value=ext_dummy):
                runner.invoke(tool, ["ext", *argv])

        assert min_captured == [argv]
        assert ext_captured == [argv]

    def test_no_manifest_in_cwd_yields_empty_ast(self, tmp_path, monkeypatch) -> None:
        """A project root with no CODEMANIFEST yields an empty (but usable) AST."""
        # tmp_path has no CODEMANIFEST: the loader walks nothing and leaves the
        # tree/errors empty without raising.
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}

        def main(argv, *, ast):
            captured["ast"] = ast

        dummy = types.ModuleType("goga_tool_nomanifest")
        dummy.main = main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["nomanifest"])

        assert result.exit_code == 0
        captured_ast = captured["ast"]
        assert isinstance(captured_ast, AST)
        assert captured_ast.tree == []
        assert captured_ast.errors == []


class TestToolBackwardCompatibility:
    def test_main_without_ast_does_not_build_ast(self) -> None:
        """A main(argv) entry point never triggers AST construction."""
        captured: list[list[str]] = []
        dummy = types.ModuleType("goga_tool_notool")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with (
            mock.patch.object(tool_module, "AST") as mock_ast,
            mock.patch.object(importlib, "import_module", return_value=dummy),
        ):
            result = runner.invoke(tool, ["notool", "arg1"])

        assert result.exit_code == 0
        assert captured == [["arg1"]]
        mock_ast.assert_not_called()


class TestToolErrorBehaviorPreserved:
    def test_package_not_found_preserves_error_behavior(self) -> None:
        """Package-not-found still surfaces the 'not found' message and non-zero exit."""
        runner = CliRunner()
        with mock.patch.object(
            importlib,
            "import_module",
            side_effect=ModuleNotFoundError("No module named 'goga_tool_nonexistent'", name="goga_tool_nonexistent"),
        ):
            result = runner.invoke(tool, ["nonexistent"])

        assert result.exit_code != 0
        assert "goga_tool_nonexistent" in result.output
        assert "not found" in result.output.lower()

    def test_found_package_with_import_failure_propagates_not_masked_as_not_found(self) -> None:
        """A found package whose transitive import fails is NOT reported as 'not found'.

        Regression for the dispatcher conflating "package absent" with "package
        present but a transitive import inside it failed". ``import_module`` sets
        ``ModuleNotFoundError.name`` to the deeper missing module (here
        ``goga.init``), which differs from the tool package. The dispatcher must
        re-raise so the honest traceback surfaces, instead of the misleading
        "Tool package '...' not found" message.
        """
        runner = CliRunner()
        missing = ModuleNotFoundError("No module named 'goga.init'", name="goga.init")
        with mock.patch.object(importlib, "import_module", side_effect=missing):
            result = runner.invoke(tool, ["pybuggy"])

        # Re-raised: the original ModuleNotFoundError propagates (non-zero exit).
        assert result.exit_code != 0
        assert isinstance(result.exception, ModuleNotFoundError)
        assert result.exception.name == "goga.init"
        # Must NOT be misreported as 'not found'.
        assert "not found" not in result.output.lower()

    def test_missing_main_preserves_error_behavior(self) -> None:
        """A package without main still surfaces the 'main' message and non-zero exit."""
        dummy = types.ModuleType("goga_tool_nomain")
        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["nomain"])

        assert result.exit_code != 0
        assert "goga_tool_nomain" in result.output
        assert "main" in result.output


class TestToolAstPassthrough:
    def test_ast_errors_pass_through_when_manifests_invalid(self, tmp_path, monkeypatch) -> None:
        """Invalid manifests populate ast.errors but do not block dispatch or filter errors."""
        (tmp_path / "CODEMANIFEST").write_text('Imports: []\nUsages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        state: dict[str, object] = {}

        def main(argv, *, ast):
            state["invoked"] = True
            state["ast"] = ast

        dummy = types.ModuleType("goga_tool_passthru")
        dummy.main = main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["passthru"])

        assert result.exit_code == 0
        assert state.get("invoked") is True
        captured_ast = state["ast"]
        assert isinstance(captured_ast, AST)
        assert len(captured_ast.errors) > 0

    def test_no_extra_args_forwarded_as_empty_list(self) -> None:
        """No trailing args are forwarded to main as an empty list."""
        captured: list[list[str]] = []
        dummy = types.ModuleType("goga_tool_empty")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with (
            mock.patch.object(tool_module, "AST"),
            mock.patch.object(importlib, "import_module", return_value=dummy),
        ):
            result = runner.invoke(tool, ["empty"])

        assert result.exit_code == 0
        assert captured == [[]]


class TestToolManifestLoadFailure:
    def test_malformed_manifest_surfaces_clean_error(self, tmp_path, monkeypatch) -> None:
        """An unparseable manifest is reported as a clean error, not a traceback.

        Validation errors (`ast.errors`) pass through to the tool unchanged, but a
        manifest that cannot be parsed at all raises from `AST.load()` before
        `main` can run. The dispatcher surfaces this as a clean red message and a
        non-zero exit, matching its package-not-found and missing-main branches.
        """
        # An unknown header key triggers DocumentParseError inside Factory.create().
        (tmp_path / "CODEMANIFEST").write_text('BogusHeaderKey: x\nUsages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        state: dict[str, object] = {}

        def main(argv, *, ast):
            state["invoked"] = True

        dummy = types.ModuleType("goga_tool_broken")
        dummy.main = main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["broken"])

        assert result.exit_code != 0
        assert state.get("invoked") is not True
        assert "Failed to load project AST" in result.output

    def test_non_utf8_manifest_surfaces_clean_error(self, tmp_path, monkeypatch) -> None:
        """An unreadable (non-UTF-8) manifest is reported as a clean error.

        `Factory.create()` opens the manifest with `encoding="utf-8"`, so a file
        containing invalid bytes raises `UnicodeDecodeError` (a `ValueError`, not
        an `OSError`) from `AST.load()`. The dispatcher must surface this as the
        same clean red message and non-zero exit, not an uncaught traceback.
        """
        # Invalid UTF-8 bytes trigger UnicodeDecodeError inside Factory.create().
        (tmp_path / "CODEMANIFEST").write_bytes(b'Annotations: "\xff\xfe"\n')
        monkeypatch.chdir(tmp_path)

        state: dict[str, object] = {}

        def main(argv, *, ast):
            state["invoked"] = True

        dummy = types.ModuleType("goga_tool_unreadable")
        dummy.main = main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["unreadable"])

        assert result.exit_code != 0
        # The raw decode error must not escape as an uncaught traceback; the
        # clean-exit path raises click's Exit (a SystemExit subclass), which
        # CliRunner records here — it must not be the UnicodeDecodeError itself.
        assert not isinstance(result.exception, UnicodeDecodeError)
        assert state.get("invoked") is not True
        assert "Failed to load project AST" in result.output

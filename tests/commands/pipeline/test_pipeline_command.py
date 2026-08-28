"""Contract and logic tests for the five-form ``pipeline`` Click command.

These tests pin the click-command contract declared in
``goga/commands/pipeline/CODEMANIFEST`` for the entity
``pipeline(ctx, name, list_requested, info, extra_env, ...)``:

- a single ``click.Command`` (not a group)
- an optional positional ``name`` argument
- ``-l/--list`` (``list_requested``) and ``-i/--info`` (``info``) flags
- form validation (2.1-2.4) BEFORE any docker activity
- dispatch to ``run_pipeline_info_container`` (flat list / overview / card)
  or ``run_pipeline_container`` (run) via keyword args
- propagation of the container exit code through the click context

Both dispatch targets are mocked on the command module so these tests stay
focused on the click surface (argument parsing, form validation, dispatch
wiring, exit-code propagation) and do not depend on docker.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner

# Importing the module populates sys.modules; the import is also how the
# contract obligation ``from goga.commands.pipeline.pipeline import pipeline``
# is exercised. ``pipeline`` is the click command (re-exported identically by
# the package __init__, which would otherwise shadow the submodule name).
from goga.commands.pipeline.pipeline import pipeline

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules, mirroring the
# sibling test_pipeline.py module.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _write_config(tmp_path: Path, *, with_pipeline: bool = True) -> None:
    """Materialize a ``.goga/config.yml`` under ``tmp_path``.

    Args:
        tmp_path: Project root used as the working directory for the test.
        with_pipeline: When ``False`` the ``pipeline:`` block is omitted,
            producing a schema error (``pipeline`` section required) that the
            command surfaces as a ``click.ClickException``.
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "language: python",
        "image: qarium/goga:latest",
        "build:",
        "  task_executor:",
        "    agent: claude",
    ]
    if with_pipeline:
        lines += [
            "pipeline:",
            "  agent: claude",
        ]
    (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")


# --- Contract tests: -l/--list and -i/--info flags ---


class TestPipelineListInfoFlagContract:
    def test_pipeline_has_list_option(self) -> None:
        """The pipeline command registers a ``list_requested`` click Option (``-l/--list``)."""
        param_names = [p.name for p in pipeline.params]
        assert "list_requested" in param_names

    def test_pipeline_list_option_is_flag_and_defaults_false(self) -> None:
        """``-l/--list`` is a flag defaulting to False."""
        list_param = next(p for p in pipeline.params if p.name == "list_requested")
        assert isinstance(list_param, click.Option)
        assert list_param.is_flag is True
        assert list_param.default is False

    def test_pipeline_list_option_has_short_and_long_flags(self) -> None:
        """The registered forms are ``-l`` (short) and ``--list`` (long)."""
        list_param = next(p for p in pipeline.params if p.name == "list_requested")
        assert "-l" in list_param.opts
        assert "--list" in list_param.opts

    def test_pipeline_has_info_option(self) -> None:
        """The pipeline command registers an ``info`` click Option (``-i/--info``)."""
        param_names = [p.name for p in pipeline.params]
        assert "info" in param_names

    def test_pipeline_info_option_is_flag_and_defaults_false(self) -> None:
        """``-i/--info`` is a flag defaulting to False."""
        info_param = next(p for p in pipeline.params if p.name == "info")
        assert isinstance(info_param, click.Option)
        assert info_param.is_flag is True
        assert info_param.default is False

    def test_pipeline_info_option_has_short_and_long_flags(self) -> None:
        """The registered forms are ``-i`` (short) and ``--info`` (long)."""
        info_param = next(p for p in pipeline.params if p.name == "info")
        assert "-i" in info_param.opts
        assert "--info" in info_param.opts

    def test_pipeline_callback_has_list_requested_and_info_parameters(self) -> None:
        """The decorated callback exposes ``list_requested``/``info`` parameters."""
        parameters = pipeline.callback.__annotations__
        assert "list_requested" in parameters
        assert "info" in parameters

    def test_pipeline_callback_list_requested_and_info_annotations_are_bool(self) -> None:
        """Both callback parameters are typed ``bool``."""
        hints = typing.get_type_hints(pipeline.callback)
        assert hints["list_requested"] is bool
        assert hints["info"] is bool

    def test_help_lists_list_and_info_flags(self) -> None:
        """``--help`` advertises both new flags (short and long forms)."""
        runner = CliRunner()
        result = runner.invoke(pipeline, ["--help"])
        assert result.exit_code == 0
        assert "-l" in result.output
        assert "--list" in result.output
        assert "-i" in result.output
        assert "--info" in result.output


# --- Contract obligation ---


class TestPipelineCommandContract:
    def test_pipeline_is_importable_and_is_click_command(self) -> None:
        """``from goga.commands.pipeline.pipeline import pipeline`` succeeds; it is a click.Command."""
        from goga.commands.pipeline.pipeline import pipeline as imported

        assert imported is not None
        assert isinstance(imported, click.Command)
        # A single command, not a group — no ls/run subcommands (per the `click` practice).
        assert not isinstance(imported, click.Group)

    def test_pipeline_command_collects_extra_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The repeatable ``-e/--env`` option is collected and forwarded as ``extra_env``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(
                pipeline,
                ["deploy", "-e", "FOO=bar", "--env", "BAZ=qux"],
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["extra_env"] == ("FOO=bar", "BAZ=qux")
        assert mock_run.call_args.kwargs["name"] == "deploy"

    def test_pipeline_without_section_raises_click_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A config missing the ``pipeline`` block surfaces as the command None-guard ClickException."""
        _write_config(tmp_path, with_pipeline=False)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # standalone_mode=False propagates the ClickException as result.exception
        # instead of Click converting it to SystemExit during CLI handling.
        result = runner.invoke(pipeline, ["deploy"], standalone_mode=False)

        assert result.exit_code != 0
        assert isinstance(result.exception, click.ClickException)
        assert "pipeline section is required" in str(result.exception)


# --- Pipeline section None-guard (D4, step 1b) tests ---


class TestPipelineSectionGuard:
    """D4 — host-side None-guard: ClickException when the pipeline section is absent.

    The guard (Algorithm step 1b) runs right after ``load_project_config()`` and before
    any ``config.pipeline.*`` access or dispatch into a launcher, so a
    pipeline-less config produces a clean user-facing error + exit 1 in EVERY
    form (no AttributeError, no docker run). The same guard covers both
    launchers transitively: they are only reachable through this command, so a
    single check here is sufficient.
    """

    @staticmethod
    def _write_config_without_pipeline(tmp_path: Path) -> None:
        """Write a valid config that has NO pipeline section (only language+image+build)."""
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "language: python",
            "image: qarium/goga:latest",
            "build:",
            "  task_executor:",
            "    agent: claude",
        ]
        (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")

    def test_pipeline_command_raises_click_exception_when_pipeline_section_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flat list on a pipeline-less config surfaces as a ClickException (step 1b)."""
        self._write_config_without_pipeline(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["--list"])

        assert result.exit_code == 1
        assert "pipeline section is required" in result.output
        # Neither launcher ever starts on a pipeline-less config.
        mock_run.assert_not_called()
        mock_info.assert_not_called()

    def test_pipeline_command_run_mode_raises_when_pipeline_section_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Run mode on a pipeline-less config also surfaces as a ClickException (step 1b)."""
        self._write_config_without_pipeline(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 1
        assert "pipeline section is required" in result.output
        # Step 1b runs before dispatch, so no launcher is ever reached.
        mock_run.assert_not_called()
        mock_info.assert_not_called()


class TestPipelineAgentOptional:
    """pipeline.agent is OPTIONAL: an absent/empty agent is a valid state because
    the agent may be supplied per-stage by the workflow (the compiler composes
    each stage's ``command:`` override from the workflow agent name, and afm
    ≥0.4.15 honors per-stage commands over the global ``client.command``). A
    pipeline section without an agent therefore does NOT raise — the command
    proceeds and dispatches to the launcher, which omits the afm-config
    ``client.command`` so per-stage workflow agents (or afm's own defaults)
    cover the absent global default.
    """

    @staticmethod
    def _write_config_without_pipeline_agent(tmp_path: Path) -> None:
        """Write a valid config with a pipeline section but NO pipeline.agent."""
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "language: python",
            "image: qarium/goga:latest",
            "build:",
            "  task_executor:",
            "    agent: claude",
            "pipeline: {}",
        ]
        (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")

    def test_pipeline_command_proceeds_when_agent_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pipeline section without an agent proceeds and dispatches (agent optional)."""
        self._write_config_without_pipeline_agent(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        # The container IS launched on an agent-less config — the agent may come
        # from the workflow, so the launcher must not short-circuit.
        mock_run.assert_called_once()

    def test_pipeline_command_proceeds_in_flat_list_when_agent_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The flat-list form also proceeds without an agent (it never needed one)."""
        self._write_config_without_pipeline_agent(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info:
            result = runner.invoke(pipeline, ["--list"])

        assert result.exit_code == 0
        mock_info.assert_called_once()


# --- Logic tests: form validation (2.1-2.4, before any docker activity) ---


class TestPipelineFormValidation:
    @pytest.mark.parametrize(
        ("info", "update"),
        [(False, False), (True, False), (False, True), (True, True)],
        ids=["plain", "with_info", "with_update", "with_both"],
    )
    def test_pipeline_no_name_no_list_prints_exact_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        info: bool,
        update: bool,
    ) -> None:
        """``goga pipeline`` with no name and no ``--list`` exits 1 with the exact message.

        The message is byte-exact (AC text): a missing form must never reach
        docker — neither launcher is invoked, stdout carries nothing but the
        ClickException's ``Error:`` line, and ``-u`` (image refresh) is not run
        either. Parameterized over the adjacent flags (``-i``, ``-u``) to prove
        none of them open a docker side door around the form check.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        argv = []

        if info:
            argv.append("--info")

        if update:
            argv.append("-u")
        with (
            mock.patch.object(
                _pipeline_module,
                "run_pipeline_container",
                return_value=0,
            ) as mock_run,
            mock.patch.object(
                _pipeline_module,
                "run_pipeline_info_container",
                return_value=0,
            ) as mock_info,
        ):
            result = runner.invoke(pipeline, argv)

        assert result.exit_code == 1
        assert result.output == (
            'Error: Missing pipeline name. Use "goga pipeline --list" to list '
            "available pipelines, or provide a pipeline name.\n"
        )
        mock_run.assert_not_called()
        mock_info.assert_not_called()

    @pytest.mark.parametrize("info", [False, True], ids=["plain", "with_info"])
    def test_pipeline_list_and_name_are_mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, info: bool
    ) -> None:
        """``--list deploy`` exits 1 with the mutual-exclusion message; no launcher runs."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        argv = ["deploy", "--list"] + (["--info"] if info else [])
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, argv)

        assert result.exit_code == 1
        assert result.output == "Error: --list and a pipeline name are mutually exclusive\n"
        mock_run.assert_not_called()
        mock_info.assert_not_called()

    def test_pipeline_list_short_flag_equivalent_to_long(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``-l`` and ``--list`` dispatch identically (same kwargs, same exit code)."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        for flag in ("-l", "--list"):
            with mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info:
                result = runner.invoke(pipeline, [flag])

            assert result.exit_code == 0, f"failed for {flag}: {result.output}"
            assert mock_info.call_args.kwargs["name"] is None
            assert mock_info.call_args.kwargs["info"] is False

    def test_pipeline_info_short_flag_equivalent_to_long(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``-i`` and ``--info`` dispatch identically (same kwargs, same exit code)."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        for flag in ("-i", "--info"):
            with mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info:
                result = runner.invoke(pipeline, ["--list", flag])

            assert result.exit_code == 0, f"failed for {flag}: {result.output}"
            assert mock_info.call_args.kwargs["info"] is True

    def test_pipeline_card_form_validates_workflow_before_docker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``deploy --info -w ghost`` (file absent) exits 1 before any docker activity.

        The workflow existence check (step 2.4) was lifted into the form block
        so it covers the card form too — a typo'd workflow name must surface as
        a clean host-side message, with stdout empty (the ClickException writes
        to stderr only) and neither launcher invoked.
        """
        _write_config(tmp_path)
        # No .goga/workflows/ghost.yml on the host.
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["deploy", "--info", "--workflow", "ghost"], standalone_mode=False)

        assert result.exit_code != 0
        assert isinstance(result.exception, click.ClickException)
        assert str(result.exception).startswith("workflow 'ghost' not found at ")
        mock_run.assert_not_called()
        mock_info.assert_not_called()


# --- Logic tests: dispatch (the five forms) ---


class TestPipelineDispatchForms:
    @pytest.mark.parametrize(
        ("argv", "expected_name", "expected_info"),
        [
            (["--list"], None, False),
            (["--list", "--info"], None, True),
            (["deploy", "--info"], "deploy", True),
        ],
        ids=["flat-list", "overview", "card"],
    )
    def test_pipeline_dispatches_flat_list_overview_and_card(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        argv: list[str],
        expected_name: str | None,
        expected_info: bool,
    ) -> None:
        """The three info forms dispatch to ``run_pipeline_info_container`` with exact kwargs.

        Info forms receive hosts from the config ONLY (``--add-host`` is a
        deliberate no-op there) and never reach ``run_pipeline_container``.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=7) as mock_info,
        ):
            result = runner.invoke(pipeline, argv)

        assert result.exit_code == 7
        mock_run.assert_not_called()
        mock_info.assert_called_once()
        kwargs = mock_info.call_args.kwargs
        assert kwargs["name"] is expected_name
        assert kwargs["info"] is expected_info
        assert kwargs["hosts"] == {}
        assert kwargs["update"] is False
        # The flat list and overview never carry a workflow decision; the card
        # form forwards the flags as given (both unset here — in-container
        # auto-match).
        assert kwargs["workflow"] is None
        assert kwargs["no_workflow"] is False

    def test_pipeline_card_form_threads_workflow_flags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The card form forwards ``-w NAME`` / ``--no-workflow`` to the info launcher."""
        _write_config(tmp_path)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "hardening.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info:
            result = runner.invoke(pipeline, ["deploy", "--info", "-w", "hardening"])

        assert result.exit_code == 0
        assert mock_info.call_args.kwargs["workflow"] == "hardening"
        assert mock_info.call_args.kwargs["no_workflow"] is False

        with mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info:
            result = runner.invoke(pipeline, ["deploy", "--info", "--no-workflow"])

        assert result.exit_code == 0
        assert mock_info.call_args.kwargs["workflow"] is None
        assert mock_info.call_args.kwargs["no_workflow"] is True

    @pytest.mark.parametrize(
        ("argv", "form"),
        [
            (["--list", "-u"], "flat-list"),
            (["--list", "--info", "-u"], "overview"),
            (["deploy", "--info", "-u"], "card"),
        ],
    )
    def test_pipeline_info_forms_forward_update_in_every_form(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], form: str
    ) -> None:
        """``-u`` is forwarded as ``update=True`` in every info form; the launcher applies it."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info:
            result = runner.invoke(pipeline, argv)

        assert result.exit_code == 0, f"failed for {form}: {result.output}"
        assert mock_info.call_args.kwargs["update"] is True

    def test_pipeline_run_form_dispatches_full_shape(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The run form resolves proxy/hosts as before and dispatches to ``run_pipeline_container``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                pipeline,
                [
                    "deploy",
                    "--parallel",
                    "4",
                    "--skip",
                    "build",
                    "--add-host",
                    "db:10.0.0.1",
                ],
            )

        assert result.exit_code == 0
        mock_info.assert_not_called()
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs["name"] == "deploy"
        assert kwargs["proxy"] is None
        assert kwargs["hosts"] == {"db": "10.0.0.1"}
        assert kwargs["skip"] == ("build",)
        assert kwargs["parallel"] == 4

    def test_pipeline_info_forms_ignore_run_flags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Run flags are not forwarded into info forms; ``--clean`` deletes nothing.

        ``-p/-s/-c/-e/--proxy/--add-host`` are run-form surface: in the info
        forms they neither reach ``run_pipeline_info_container`` (its signature
        has no slot for them) nor leak into ``hosts`` (``--add-host`` is a
        deliberate no-op for info), and ``--clean`` never triggers the runtime
        dir wipe.
        """
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                pipeline,
                [
                    "--list",
                    "--info",
                    "--parallel",
                    "4",
                    "--skip",
                    "build",
                    "--clean",
                    "-e",
                    "K=V",
                    "--proxy",
                    "http://p",
                    "--add-host",
                    "db:10.0.0.1",
                ],
            )

        assert result.exit_code == 0
        mock_run.assert_not_called()
        mock_info.assert_called_once()
        # hosts come from the config only — the CLI --add-host entry is absent.
        assert mock_info.call_args.kwargs["hosts"] == {}


# --- Facade contract: goga/commands/pipeline exports the full contract API ---

# The seven names declared in the cell CODEMANIFEST — the pipeline command, the
# two container launchers, the two branch routines, and the two runtime-dir
# helpers (declared since the cell existed, exported since release 1.3.0; the
# slug transformer and the current-branch reader moved to goga.history with no
# re-export from their old location).
_PIPELINE_FACADE_ALL = [
    "check_branch_occupancy",
    "clean_pipeline_runtime_dir",
    "ensure_pipeline_branch",
    "pipeline",
    "resolve_pipeline_runtime_dir",
    "run_pipeline_container",
    "run_pipeline_info_container",
]


class TestCommandsFacadeExportsInfoLauncher:
    def test_commands_facade_exports_info_launcher(self) -> None:
        """The package facade defines all seven public names and lists them in ``__all__``.

        ``goga.commands.pipeline`` is shadowed on the ``goga.commands`` package
        by the pipeline Click command (see the module-level note above), so the
        facade module is resolved via ``sys.modules`` — the same identifier the
        ``from goga.commands.pipeline import ...`` obligation resolves through.
        """
        commands_facade = sys.modules["goga.commands.pipeline"]

        for name in _PIPELINE_FACADE_ALL:
            assert hasattr(commands_facade, name), f"{name} is not defined on goga.commands.pipeline"
            assert name in commands_facade.__all__, f"{name} is missing from goga.commands.pipeline.__all__"

    def test_commands_facade_all_is_alphabetical_and_complete(self) -> None:
        """``__all__`` holds exactly the seven names in alphabetical order."""
        commands_facade = sys.modules["goga.commands.pipeline"]
        assert commands_facade.__all__ == _PIPELINE_FACADE_ALL

    def test_cell_facades_export_full_contract_api(self) -> None:
        """Every declared contract name is importable from the cell facade root.

        The Python facade rule obliges ``goga.commands.pipeline`` to expose the
        full contract API: the command, both launchers, the two ``branch.py``
        routines, and the two runtime-dir helpers.
        """
        from goga.commands.pipeline import (
            check_branch_occupancy,
            clean_pipeline_runtime_dir,
            ensure_pipeline_branch,
            resolve_pipeline_runtime_dir,
            run_pipeline_container,
            run_pipeline_info_container,
        )
        from goga.commands.pipeline import (
            pipeline as pipeline_from_facade,
        )

        assert pipeline_from_facade is pipeline
        assert run_pipeline_container is not None
        assert run_pipeline_info_container is not None
        assert resolve_pipeline_runtime_dir is not None
        assert clean_pipeline_runtime_dir is not None
        assert check_branch_occupancy is not None
        assert ensure_pipeline_branch is not None
        assert sys.modules["goga.commands.pipeline"].__all__ == _PIPELINE_FACADE_ALL

    def test_commands_facade_info_launcher_is_importable_by_name(self) -> None:
        """The consumer form ``from goga.commands.pipeline import run_pipeline_info_container`` works."""
        from goga.commands.pipeline import run_pipeline_info_container as from_facade
        from goga.commands.pipeline.run_pipeline_info_container import (
            run_pipeline_info_container as from_module,
        )

        assert from_facade is from_module


# --- Logic tests: exit-code propagation ---


class TestPipelineCommandLogic:
    def test_pipeline_command_run_mode_passes_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A provided ``name`` is forwarded to ``run_pipeline_container(name=<name>)``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run:
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["name"] == "deploy"

    def test_pipeline_command_propagates_exit_code(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The container exit code is propagated via ``ctx.exit``."""
        _write_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=42):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 42

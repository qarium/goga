"""Contract and logic tests for the extended ``pipeline`` Click command surface.

These tests pin the click-command contract declared in
``goga/commands/pipeline/CODEMANIFEST`` for the extended entity
``pipeline(ctx, name, extra_env, proxy, add_host, clean, update)``:

- new ``--proxy``, ``--add-host`` (multiple), ``--clean``, ``--update/-u`` options
- the ``-t/--topic`` option (run form only): one Option with both forms
  binding the ``topic`` parameter; the guarded topic procedure runs after
  the step-2 validation and before any docker activity, echoes exactly one
  stdout line — the result line of ``switch_topic`` — and never forwards
  the topic into a launcher
- proxy resolution: ``--proxy`` wins over ``config.pipeline.proxy``
- hosts resolution: ``--add-host`` entries merge on top of
  ``config.pipeline.hosts`` (CLI overrides config on key conflict)
- dispatch semantics: the listing forms take hosts from the config only;
  the run form forwards ``clean``; both modes forward
  ``proxy``/``hosts``/``update``
- exit code propagated via ``ctx.exit``

The dispatch target ``run_pipeline_container`` is mocked so these tests stay
focused on the click surface and the host-side resolution logic, with no docker
dependency.

The integration block at the bottom drives the REAL ``switch_topic`` from the
topics domain through the real command surface, mocking the domain's git
boundary at its import points (the same wiring the topics cell tests use), to
verify the wiring the unit tests mock away.
"""

from __future__ import annotations

import inspect
import sys
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.pipeline import pipeline
from goga.commands.pipeline.pipeline import pipeline as pipeline_cmd
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig
from goga.history import current_year
from goga.topics import board as topics_board
from goga.topics import switching as topics_switching
from goga.topics.git import BranchRef

# goga.commands.pipeline.pipeline is shadowed in the package __init__ by the
# pipeline Click command, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules.
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]


def _make_config(
    *,
    pipeline_proxy: str | None = None,
    pipeline_hosts: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig, optionally with pipeline.proxy/hosts."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(
            agent="claude",
            proxy=pipeline_proxy,
            hosts=pipeline_hosts or {},
        ),
    )


# --- Contract tests ---


class TestPipelineDispatchContract:
    def test_pipeline_has_proxy_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "proxy" in param_names

    def test_pipeline_has_add_host_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "add_host" in param_names

    def test_pipeline_add_host_option_is_multiple(self) -> None:
        add_host_param = next(p for p in pipeline.params if p.name == "add_host")
        assert add_host_param.multiple is True

    def test_pipeline_has_clean_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "clean" in param_names

    def test_pipeline_clean_option_defaults_false(self) -> None:
        clean_param = next(p for p in pipeline.params if p.name == "clean")
        assert clean_param.is_flag is True
        assert clean_param.default is False

    def test_pipeline_has_update_option(self) -> None:
        param_names = [p.name for p in pipeline.params]
        assert "update" in param_names

    def test_pipeline_update_option_defaults_false(self) -> None:
        update_param = next(p for p in pipeline.params if p.name == "update")
        assert update_param.is_flag is True
        assert update_param.default is False

    def test_pipeline_update_has_short_flag(self) -> None:
        update_param = next(p for p in pipeline.params if p.name == "update")
        assert "-u" in update_param.opts

    def test_help_lists_new_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(pipeline, ["--help"])
        assert result.exit_code == 0
        output = result.output
        assert "--proxy" in output
        assert "--add-host" in output
        assert "--clean" in output
        assert "--update" in output
        assert "-u" in output


class TestPipelineTopicOptionContract:
    def test_pipeline_topic_option_contract_both_forms_one_option(self) -> None:
        """-t/--topic is a single Option binding ``topic``; both forms reach the procedure.

        The Option carries both forms (``set(param.opts)`` is exactly the pair),
        defaults to None, and is a plain string option (click renders the
        declared ``type=str`` as its canonical STRING param type). The callback
        declares ``topic: str | None`` directly after ``info`` (contract
        order), and ``--topic x NAME`` / ``-t x NAME`` reach ``switch_topic``
        with the same value.
        """
        topic_param = next(p for p in pipeline.params if p.name == "topic")
        assert set(topic_param.opts) == {"-t", "--topic"}
        assert topic_param.default is None
        assert topic_param.type is click.STRING

        parameters = list(inspect.signature(pipeline_cmd.callback).parameters)
        assert parameters.index("topic") == parameters.index("info") + 1
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["topic"] == str | None
        assert "branch" not in parameters

        config = _make_config()
        runner = CliRunner()
        for argv in (["--topic", "x", "my-pipeline"], ["-t", "x", "my-pipeline"]):
            with (
                mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
                mock.patch.object(_pipeline_module, "switch_topic", return_value="Switched to branch x") as mock_switch,
                mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0),
            ):
                result = runner.invoke(pipeline, argv)

            assert result.exit_code == 0
            mock_switch.assert_called_once_with("x")


# --- Logic tests (positive) ---


class TestPipelineDispatchLogic:
    def test_pipeline_dispatch_run_mode_with_clean(self) -> None:
        """Run mode forwards proxy/hosts/clean/update; exit code propagates via ctx.exit."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=42) as mock_run,
        ):
            result = runner.invoke(
                pipeline,
                [
                    "deploy",
                    "--proxy",
                    "http://corp:3128",
                    "--add-host",
                    "foo.local:127.0.0.1",
                    "--clean",
                ],
            )

        assert result.exit_code == 42
        mock_run.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=(),
            proxy="http://corp:3128",
            hosts={"foo.local": "127.0.0.1"},
            clean=True,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_proxy_none_falls_back_to_config(self) -> None:
        """When --proxy is absent, config.pipeline.proxy is forwarded."""
        config = _make_config(pipeline_proxy="http://from-config:3128")
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            name="deploy",
            config=config,
            extra_env=(),
            proxy="http://from-config:3128",
            hosts={},
            clean=False,
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
            parallel=None,
        )

    def test_pipeline_update_flag_forwarded(self) -> None:
        """--update/-u is forwarded as update=True in both modes."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["deploy", "-u"])

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["update"] is True


# --- Logic tests (edge) ---


class TestPipelineDispatchEdge:
    def test_pipeline_dispatch_list_form_ignores_clean(self) -> None:
        """The flat-list form never carries run state — --clean is not forwarded.

        Under the five-form contract a bare ``--clean`` names no form (step 2.2
        exits 1), and the listing forms dispatch to
        ``run_pipeline_info_container`` whose signature has no ``clean`` slot at
        all — the runtime dir is never wiped outside the run form. The former
        discovery-mode ``clean forced to False`` behavior lives here now.
        """
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, ["--list", "--clean"])

        assert result.exit_code == 0
        mock_info.assert_called_once_with(
            name=None,
            info=False,
            config=config,
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
        )

    def test_pipeline_add_host_merges_over_config(self) -> None:
        """--add-host entries merge on top of config.pipeline.hosts; CLI wins on conflict."""
        config = _make_config(pipeline_hosts={"a.local": "10.0.0.1"})
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                pipeline,
                [
                    "deploy",
                    "--add-host",
                    "a.local:192.168.1.1",
                    "--add-host",
                    "b.local:127.0.0.1",
                ],
            )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["hosts"] == {
            "a.local": "192.168.1.1",
            "b.local": "127.0.0.1",
        }

    @pytest.mark.parametrize("exit_code", [0, 1, 2, 42, 127, 130])
    def test_pipeline_propagates_exit_code(self, exit_code: int) -> None:
        """The container exit code is propagated via ctx.exit."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=exit_code),
        ):
            result = runner.invoke(pipeline, ["deploy"])

        assert result.exit_code == exit_code


class TestPipelineTopicRunForm:
    def test_pipeline_topic_option_switches_before_docker(self) -> None:
        """The topic procedure runs, echoes its one result line, then the container launches."""
        config = _make_config()
        switch_line = "Switched to branch feat/x"
        mock_switch = mock.Mock(return_value=switch_line)
        mock_run = mock.Mock(return_value=0)
        order = mock.Mock()
        order.attach_mock(mock_switch, "switch_topic")
        order.attach_mock(mock_run, "run_container")
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "switch_topic", mock_switch),
            mock.patch.object(_pipeline_module, "run_pipeline_container", mock_run),
        ):
            result = runner.invoke(pipeline, ["-t", "feat/x", "development"])

        assert result.exit_code == 0
        # Exactly one topic line on stdout, verbatim from switch_topic.
        assert result.stdout.count(switch_line) == 1
        mock_switch.assert_called_once_with("feat/x")
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["name"] == "development"
        # The switch precedes the docker activity, and the topic identifier
        # never crosses the docker boundary.
        assert order.method_calls[0] == mock.call.switch_topic("feat/x")
        assert order.method_calls[1][0] == "run_container"
        assert "topic" not in mock_run.call_args.kwargs
        assert "feat/x" not in mock_run.call_args.kwargs.values()

    @pytest.mark.parametrize(
        "argv",
        [
            ["-t", "x", "--list"],
            ["-t", "x", "--list", "--info"],
            ["-t", "x", "my-pipeline", "--info"],
        ],
        ids=["flat-list", "overview", "card"],
    )
    def test_pipeline_topic_ignored_in_list_and_info_forms(self, argv: list[str]) -> None:
        """The flat list, overview, and card forms ignore -t — no procedure, no line."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "switch_topic") as mock_switch,
            mock.patch.object(_pipeline_module, "run_pipeline_info_container", return_value=0) as mock_info,
        ):
            result = runner.invoke(pipeline, argv)

        assert result.exit_code == 0
        mock_switch.assert_not_called()
        mock_info.assert_called_once()
        assert "Switched to branch" not in result.stdout

    def test_pipeline_missing_name_with_topic_no_switch(self) -> None:
        """A step-2 form error exits 1 before any git action of the topic procedure."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "switch_topic") as mock_switch,
            mock.patch.object(_pipeline_module, "run_pipeline_container") as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "x"])

        assert result.exit_code == 1
        assert "Missing pipeline name" in result.output
        mock_switch.assert_not_called()
        mock_run.assert_not_called()

    def test_pipeline_has_no_branch_option(self) -> None:
        """-b is gone from the surface: unknown option, and absent from --help."""
        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "switch_topic") as mock_switch,
        ):
            result = runner.invoke(pipeline, ["-b", "x", "dev"])

        assert result.exit_code != 0
        mock_switch.assert_not_called()

        help_result = runner.invoke(pipeline, ["--help"])
        assert help_result.exit_code == 0
        assert "-b" not in help_result.output
        assert "--branch" not in help_result.output


# --- Integration tests (the real topics-domain switch through the real command) ---


def _trees_reader(trees: dict[str, list[str]]):
    """A ``read_ref_tree_paths`` stand-in answering by ref display name."""

    def read(ref: str, prefix: str) -> list[str]:
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _wire_topic_domain(
    monkeypatch: pytest.MonkeyPatch,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
) -> tuple[mock.Mock, mock.Mock, mock.Mock]:
    """Wire the REAL ``switch_topic`` to a canned git boundary.

    The resolution reads the scale, the ref inventory, the ref trees, and the
    current branch at their import points inside the topics domain (the same
    points the domain's own tests patch); the mutations are recording mocks.
    Only the topics facade stays real — exactly the wiring ``pipeline`` relies
    on through ``from ...topics import switch_topic``.

    Returns:
        The cleanliness probe, the local checkout, and the remote-tracking
        branch creation — all as recording mocks.
    """
    monkeypatch.setattr(topics_switching, "assemble_status_scale", _builtin_scale)
    monkeypatch.setattr(topics_switching, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(topics_switching, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(topics_board, "read_ref_tree_paths", _trees_reader(trees))

    cleanliness = mock.Mock(return_value=True)
    checkout = mock.Mock()
    creation = mock.Mock()
    monkeypatch.setattr(topics_switching, "is_working_tree_clean", cleanliness)
    monkeypatch.setattr(topics_switching, "checkout_local_branch", checkout)
    monkeypatch.setattr(topics_switching, "create_branch_from_remote_tracking", creation)
    return cleanliness, checkout, creation


def _builtin_scale():
    """The deterministic builtin scale for the resolution (no tool packages)."""
    from goga.history.statuses import Stage, StatusScale

    return StatusScale(
        stages=[
            Stage(name="empty", filepath=""),
            Stage(name="defined", filepath="prd.md"),
            Stage(name="discovered", filepath="adr.md"),
            Stage(name="backlog", filepath="task.md"),
            Stage(name="designed", filepath="arch.md"),
            Stage(name="specified", filepath="design.md"),
            Stage(name="planned", filepath="plan.md"),
            Stage(name="done", filepath="completed/plan.md"),
        ]
    )


class TestPipelineTopicIntegration:
    """Cross-entity: the real ``switch_topic`` from the topics domain through the real command.

    Only the domain's git boundary is canned, so these tests verify the wiring
    the unit tests mock away: the ``from ...topics import`` path, the run-form
    guard, the argument handed to the domain, and the ordering guarantee —
    step-2 validation, topic procedure, topic line, docker activity.
    """

    def test_pipeline_topic_flow_switches_and_launches(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Flow happy path: the domain switches, its line prints, the launcher runs topic-free."""
        monkeypatch.chdir(tmp_path)
        year = current_year()
        inventory = [
            BranchRef(name="main", remote=False),
            BranchRef(name="feat/a", remote=False),
        ]
        trees = {"feat/a": [f".goga/history/{year}/feat-a/plan.md"]}
        _cleanliness, checkout, _creation = _wire_topic_domain(monkeypatch, inventory, trees, "main")

        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "feat/a", "my-pipeline"])

        assert result.exit_code == 0
        assert "Switched to branch feat/a" in result.stdout
        checkout.assert_called_once_with("feat/a")
        assert mock_run.call_count == 1
        assert mock_run.call_args.kwargs["name"] == "my-pipeline"
        # The topic identifier never crosses the docker boundary.
        assert "topic" not in mock_run.call_args.kwargs
        assert "feat/a" not in mock_run.call_args.kwargs.values()

    def test_pipeline_topic_idempotent_host_skips_git_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Already on the host branch: the confirmation line prints and git is untouched."""
        monkeypatch.chdir(tmp_path)
        year = current_year()
        inventory = [BranchRef(name="feat/a", remote=False)]
        trees = {"feat/a": [f".goga/history/{year}/feat-a/plan.md"]}
        cleanliness, checkout, creation = _wire_topic_domain(monkeypatch, inventory, trees, "feat/a")

        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "feat/a", "my-pipeline"])

        assert result.exit_code == 0
        assert "Already on branch feat/a" in result.stdout
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        creation.assert_not_called()
        assert mock_run.call_count == 1

    def test_pipeline_topic_unresolved_identifier_aborts_before_docker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unresolved identifier: clean failure on stderr, exit 1, nothing launches."""
        monkeypatch.chdir(tmp_path)
        year = current_year()
        inventory = [BranchRef(name="main", remote=False)]
        trees = {"main": [f".goga/history/{year}/other/prd.md"]}
        cleanliness, checkout, _creation = _wire_topic_domain(monkeypatch, inventory, trees, "main")

        config = _make_config()
        runner = CliRunner()
        with (
            mock.patch.object(_pipeline_module, "load_project_config", return_value=config),
            mock.patch.object(_pipeline_module, "run_pipeline_container") as mock_run,
        ):
            result = runner.invoke(pipeline, ["-t", "nope", "my-pipeline"])

        assert result.exit_code == 1
        assert "no branch hosts 'nope'" in result.stderr
        assert "goga topics status" in result.stderr
        cleanliness.assert_not_called()
        checkout.assert_not_called()
        mock_run.assert_not_called()


class TestPipelineCallbackSignature:
    def test_pipeline_callback_has_new_parameters(self) -> None:
        """The decorated callback exposes proxy/add_host/clean/update parameters."""
        parameters = pipeline_cmd.callback.__annotations__
        assert "proxy" in parameters
        assert "add_host" in parameters
        assert "clean" in parameters
        assert "update" in parameters

    def test_pipeline_callback_declares_topic_not_branch(self) -> None:
        """The callback signature carries ``topic: str | None`` and no ``branch``."""
        hints = typing.get_type_hints(pipeline_cmd.callback)
        assert hints["topic"] == str | None
        assert "branch" not in hints

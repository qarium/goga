"""Contract and logic tests for ``run_pipeline_info_container``.

Pins the CODEMANIFEST contract of the host-side read-only docker launcher for
the three informational forms (flat list / overview / card):

- importable from ``goga.commands.pipeline.run_pipeline_info_container`` with
  the declared signature
  ``(name, info, config, hosts, update, workflow, no_workflow) -> int``
- the minimal docker shape holds in all three forms — no published port, no
  env-file, no afm-config tmpfile, no afm-state mount, no credential mounts,
  no caller-side signal handler
- the card argv carries the workflow decision exactly as given (``-w NAME``,
  ``--no-workflow``, or neither)
- ``docker_build_if_not_exist`` runs unconditionally; ``docker_update`` only in
  the flat list form (``info=False``)
- nothing is written on the host (no tmpfile, no env-file, no cleanup)

External boundaries (``DockerRunner``, the docker builders,
``load_home_config``, ``_check_docker``) are mocked on the attributes of the
real module ``goga.commands.pipeline.run_pipeline_info_container`` per the
established module pattern — never ``sys.modules`` shadowing.
"""

from __future__ import annotations

import inspect
import sys
import typing
from pathlib import Path
from unittest import mock

import pytest
from goga.commands.pipeline.run_pipeline_info_container import (
    run_pipeline_info_container as rpic,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# Resolve the real submodule via sys.modules (the package __init__ will bind the
# function name `run_pipeline_info_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpic_mod = sys.modules["goga.commands.pipeline.run_pipeline_info_container"]


def _make_config(image: str | None = "goga:test") -> ProjectConfig:
    """Build a minimal ProjectConfig with an image and a pipeline section."""
    return ProjectConfig(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude", env={}),
    )


def _install_happy_path(monkeypatch, exit_code: int = 0) -> dict[str, mock.Mock]:
    """Mock every external boundary to the happy path; return the mocks."""
    mocks: dict[str, mock.Mock] = {}
    mocks["runner_cls"] = mock.MagicMock()
    mocks["runner_instance"] = mocks["runner_cls"].return_value
    mocks["runner_instance"].run.return_value = exit_code
    mocks["build"] = mock.Mock()
    mocks["update"] = mock.Mock()
    mocks["home"] = mock.Mock()
    monkeypatch.setattr(_rpic_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpic_mod, "DockerRunner", mocks["runner_cls"])
    monkeypatch.setattr(_rpic_mod, "docker_build_if_not_exist", mocks["build"])
    monkeypatch.setattr(_rpic_mod, "docker_update", mocks["update"])
    monkeypatch.setattr(_rpic_mod, "load_home_config", mocks["home"])
    return mocks


def _snapshot_tree(root: Path) -> set[Path]:
    """Collect the set of all paths under ``root`` (recursive)."""
    return set(root.rglob("*"))


# --- Contract tests ---


class TestRunPipelineInfoContainerContract:
    def test_importable_from_declared_location(self) -> None:
        """The launcher is importable from ``run_pipeline_info_container.py``."""
        assert callable(_rpic_mod.run_pipeline_info_container)
        assert _rpic_mod.run_pipeline_info_container is rpic

    def test_signature_matches_contract(self) -> None:
        """The signature exposes exactly the seven declared parameters in order."""
        params = list(inspect.signature(rpic).parameters)
        assert params == [
            "name",
            "info",
            "config",
            "hosts",
            "update",
            "workflow",
            "no_workflow",
        ]

    def test_signature_annotations_match_contract(self) -> None:
        """Parameter and return annotations match the declared contract."""
        hints = typing.get_type_hints(rpic)
        assert hints["name"] == str | None
        assert hints["info"] is bool
        assert hints["hosts"] == dict[str, str]
        assert hints["update"] is bool
        assert hints["workflow"] == str | None
        assert hints["no_workflow"] is bool
        assert hints["return"] is int

    def test_no_pipeline_types_imported(self) -> None:
        """The docker boundary holds — no Type import from ``goga/pipeline``."""
        import goga.pipeline

        pipeline_types = [
            obj
            for obj in vars(goga.pipeline).values()
            if isinstance(obj, type) and getattr(obj, "__module__", "").startswith("goga.pipeline")
        ]
        leaked = [t for t in pipeline_types if any(obj is t for obj in vars(_rpic_mod).values())]
        assert not leaked, f"module must not hold a reference to pipeline Types: {leaked}"


# --- Logic tests ---


class TestFlatListArgv:
    def test_run_pipeline_info_container_composes_flat_list_argv(self, tmp_path: Path, monkeypatch) -> None:
        """Flat list: ``-m goga.pipeline list``; minimal shape; no refresh."""
        mocks = _install_happy_path(monkeypatch, exit_code=0)
        monkeypatch.chdir(tmp_path)

        result = rpic(
            name=None,
            info=False,
            config=_make_config(),
            hosts={"db": "10.0.0.1"},
            update=False,
            workflow=None,
            no_workflow=False,
        )

        assert result == 0
        args, kwargs = mocks["runner_instance"].run.call_args
        assert args[0] == ["-m", "goga.pipeline", "list"]
        assert "p" not in kwargs
        assert "env_file" not in kwargs
        assert kwargs["v"] == [f"{tmp_path.resolve()}:/workspace"]
        assert kwargs["add_host"] == ["db:10.0.0.1"]
        mocks["update"].assert_not_called()
        assert mocks["build"].called


class TestOverviewAndCardArgv:
    @pytest.mark.parametrize(
        ("name", "info", "workflow", "no_workflow", "expected"),
        [
            (
                None,
                True,
                None,
                False,
                ["-m", "goga.pipeline", "list", "--info"],
            ),
            (
                "deploy",
                True,
                "hardening",
                False,
                ["-m", "goga.pipeline", "run", "deploy", "--info", "-w", "hardening"],
            ),
            (
                "deploy",
                True,
                None,
                True,
                ["-m", "goga.pipeline", "run", "deploy", "--info", "--no-workflow"],
            ),
            # Card with neither flag — in-container auto-match (argv carries
            # the decision "as given", i.e. nothing).
            (
                "deploy",
                True,
                None,
                False,
                ["-m", "goga.pipeline", "run", "deploy", "--info"],
            ),
        ],
    )
    def test_run_pipeline_info_container_composes_overview_and_card_argv(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        monkeypatch,
        name,
        info,
        workflow,
        no_workflow,
        expected,
    ) -> None:
        """Overview/card argv composition per the contract step 3."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        result = rpic(
            name=name,
            info=info,
            config=_make_config(),
            hosts={},
            update=False,
            workflow=workflow,
            no_workflow=no_workflow,
        )

        assert result == 0
        args, _kwargs = mocks["runner_instance"].run.call_args
        assert args[0] == expected


class TestImageRefreshPolicy:
    def test_run_pipeline_info_container_refreshes_image_only_in_flat_list(self, tmp_path: Path, monkeypatch) -> None:
        """``docker_update`` runs only for the flat list; the safety net always runs."""
        monkeypatch.chdir(tmp_path)

        mocks = _install_happy_path(monkeypatch)
        rpic(None, False, _make_config(), {}, update=True, workflow=None, no_workflow=False)
        assert mocks["update"].called
        assert mocks["build"].called

        mocks = _install_happy_path(monkeypatch)
        rpic(None, True, _make_config(), {}, update=True, workflow=None, no_workflow=False)
        mocks["update"].assert_not_called()
        assert mocks["build"].called

        mocks = _install_happy_path(monkeypatch)
        rpic("deploy", True, _make_config(), {}, update=True, workflow=None, no_workflow=False)
        mocks["update"].assert_not_called()
        assert mocks["build"].called


class TestGuardChecks:
    def test_run_pipeline_info_container_requires_docker_and_image(self, tmp_path: Path, monkeypatch) -> None:
        """Missing docker then missing image raise ClickException before any launch."""
        import click

        monkeypatch.chdir(tmp_path)
        mocks = _install_happy_path(monkeypatch)

        monkeypatch.setattr(_rpic_mod, "_check_docker", lambda: False)
        with pytest.raises(click.ClickException, match="docker not found in PATH"):
            rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        monkeypatch.setattr(_rpic_mod, "_check_docker", lambda: True)
        with pytest.raises(click.ClickException, match=r"image in \.goga/config\.yml is not set"):
            rpic(None, False, _make_config(image=None), {}, update=False, workflow=None, no_workflow=False)

        mocks["runner_cls"].assert_not_called()

    def test_run_pipeline_info_container_broken_home_config(self, tmp_path: Path, monkeypatch) -> None:
        """A malformed ``~/.goga/config.yml`` surfaces as ClickException before launch."""
        import click

        monkeypatch.chdir(tmp_path)
        mocks = _install_happy_path(monkeypatch)
        mocks["home"].side_effect = ValueError("env must be a mapping")

        with pytest.raises(click.ClickException):
            rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        mocks["runner_cls"].assert_not_called()


class TestHostPurity:
    def test_run_pipeline_info_container_writes_no_host_files(self, tmp_path: Path, monkeypatch) -> None:
        """All three forms leave both the project dir and home dir untouched."""
        home = tmp_path / "home"
        home.mkdir()
        (home / ".goga").mkdir()
        (home / ".goga" / "config.yml").write_text("docker:\n  run: []\n  build: []\n")

        mocks = _install_happy_path(monkeypatch)
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.chdir(tmp_path)
        before_project = _snapshot_tree(tmp_path)
        before_home = _snapshot_tree(home)

        for name, info, workflow, no_workflow in [
            (None, False, None, False),
            (None, True, None, False),
            ("deploy", True, "hardening", False),
        ]:
            rpic(name, info, _make_config(), {}, update=True, workflow=workflow, no_workflow=no_workflow)

        assert _snapshot_tree(tmp_path) == before_project
        assert _snapshot_tree(home) == before_home
        assert mocks["runner_instance"].run.call_count == 3

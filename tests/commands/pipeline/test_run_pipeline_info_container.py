"""Contract and logic tests for ``run_pipeline_info_container``.

Pins the CODEMANIFEST contract of the host-side read-only docker launcher for
the three informational forms (flat list / overview / card):

- importable from ``goga.commands.pipeline.run_pipeline_info_container`` with
  the declared signature
  ``(name, info, config, hosts, update, workflow, no_workflow, skip) -> int``
- the minimal docker shape holds in all three forms — no published port, no
  env-file, no afm-config tmpfile, no afm-state mount, no credential mounts,
  no caller-side signal handler
- the card argv carries the workflow decision exactly as given (``-w NAME``,
  ``--no-workflow``, or neither) and one ``-s NAME`` per skip entry
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
from typing import Any, ClassVar, NamedTuple
from unittest import mock

import click
import pytest
from goga.commands.pipeline.run_pipeline_info_container import (
    run_pipeline_info_container as rpic,
)
from goga.config import ProjectConfig
from goga.docker._flags import translate_params

from tests.commands.pipeline.conftest import DirectSpawnPopen, make_config


class _InfoForm(NamedTuple):
    """One CLI form of the info launcher: the four selection flags of ``rpic``."""

    name: str | None
    info: bool
    workflow: str | None
    no_workflow: bool


# Resolve the real submodule via sys.modules (the package __init__ will bind the
# function name `run_pipeline_info_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpic_mod = sys.modules["goga.commands.pipeline.run_pipeline_info_container"]


def _make_config(image: str | None = "goga:test") -> ProjectConfig:
    """The shared factory under this file's image default."""
    return make_config(image=image)


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


@pytest.fixture(autouse=True)
def _no_ambient_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the ambient ``GOGA_PROFILE`` so each test owns its cargo explicitly."""
    monkeypatch.delenv("GOGA_PROFILE", raising=False)


# --- Contract tests ---


class TestRunPipelineInfoContainerContract:
    def test_importable_from_declared_location(self) -> None:
        """The launcher is importable from ``run_pipeline_info_container.py``."""
        assert callable(_rpic_mod.run_pipeline_info_container)
        assert _rpic_mod.run_pipeline_info_container is rpic

    def test_signature_matches_contract(self) -> None:
        """The signature exposes exactly the ten declared parameters in order."""
        params = list(inspect.signature(rpic).parameters)
        assert params == [
            "name",
            "info",
            "config",
            "hosts",
            "update",
            "workflow",
            "no_workflow",
            "profile",
            "skip",
            "home_profiles",
        ]

    def test_skip_defaults_to_empty_tuple(self) -> None:
        """``skip`` carries the Python-level default ``()`` — the listing dispatch relies on it."""
        param = inspect.signature(rpic).parameters["skip"]
        assert param.default == ()

    def test_signature_annotations_match_contract(self) -> None:
        """Parameter and return annotations match the declared contract."""
        hints = typing.get_type_hints(rpic)
        assert hints["name"] == str | None
        assert hints["info"] is bool
        assert hints["hosts"] == dict[str, str]
        assert hints["update"] is bool
        assert hints["workflow"] == str | None
        assert hints["no_workflow"] is bool
        assert hints["profile"] == str | None
        assert hints["skip"] == tuple[str, ...]
        assert hints["home_profiles"] == dict[str, dict[str, Any]] | None
        assert hints["return"] is int

    def test_profile_and_home_profiles_default_none(self) -> None:
        """``profile`` and ``home_profiles`` are optional — no cargo by default."""
        params = inspect.signature(rpic).parameters
        assert params["profile"].default is None
        assert params["home_profiles"].default is None

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

    def test_info_launcher_produces_no_file_roots(self, tmp_path: Path, monkeypatch) -> None:
        """No AFM_DOCKER_FILE_ROOTS — the minimal shape composes no env-file at all."""
        from goga.config import DockerArgsConfig, HomeConfig

        mocks = _install_happy_path(monkeypatch)
        home = HomeConfig(env={}, docker=DockerArgsConfig(run=[]))
        monkeypatch.setattr(_rpic_mod, "load_home_config", mock.Mock(return_value=home))
        monkeypatch.chdir(tmp_path)

        result = rpic(
            name=None,
            info=False,
            config=_make_config(),
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
        )

        assert result == 0
        args, kwargs = mocks["runner_instance"].run.call_args
        # The guarantee is structural: no env-file parameter exists to filter —
        # the variable cannot be produced, so the image's static ENV default
        # holds in the container.
        assert "env_file" not in kwargs
        # Rebuild the docker-run argv exactly as DockerRunner.run would:
        # params → flags via the shared rule, then extra_args, image, args.
        params = {key: value for key, value in kwargs.items() if key != "extra_args"}
        argv = [
            "docker",
            "run",
            *translate_params(params),
            *list(kwargs.get("extra_args") or []),
            mocks["runner_cls"].call_args.args[0],
            *args,
        ]
        assert "--env-file" not in argv
        assert not any("AFM_DOCKER_FILE_ROOTS" in token for token in argv)


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


class TestCardSkipArgv:
    def test_card_argv_carries_one_dash_s_per_skip(self, tmp_path: Path, monkeypatch) -> None:
        """One ``-s NAME`` per skip entry reaches the card argv, order preserved."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        result = rpic(
            name="deploy",
            info=True,
            config=_make_config(),
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
            skip=("a", "b"),
        )

        assert result == 0
        args, _kwargs = mocks["runner_instance"].run.call_args
        assert args[0] == [
            "-m",
            "goga.pipeline",
            "run",
            "deploy",
            "--info",
            "-s",
            "a",
            "-s",
            "b",
        ]

    def test_card_skip_appends_after_the_workflow_flags(self, tmp_path: Path, monkeypatch) -> None:
        """``-s`` entries follow the workflow decision in the card argv (exact order)."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        rpic(
            name="deploy",
            info=True,
            config=_make_config(),
            hosts={},
            update=False,
            workflow="hardening",
            no_workflow=False,
            skip=("build", "test"),
        )

        args, _kwargs = mocks["runner_instance"].run.call_args
        assert args[0] == [
            "-m",
            "goga.pipeline",
            "run",
            "deploy",
            "--info",
            "-w",
            "hardening",
            "-s",
            "build",
            "-s",
            "test",
        ]

    def test_empty_skip_yields_no_dash_s(self, tmp_path: Path, monkeypatch) -> None:
        """``skip=()`` composes no ``-s`` in the card form."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        rpic(
            name="deploy",
            info=True,
            config=_make_config(),
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
            skip=(),
        )
        card_args, _ = mocks["runner_instance"].run.call_args
        assert "-s" not in card_args[0]

    @pytest.mark.parametrize(
        ("name", "info", "expected"),
        [
            (None, False, ["-m", "goga.pipeline", "list"]),
            (None, True, ["-m", "goga.pipeline", "list", "--info"]),
        ],
        ids=["flat-list", "overview"],
    )
    def test_listing_argv_unchanged_and_skip_ignored(self, tmp_path: Path, monkeypatch, name, info, expected) -> None:
        """The listing forms never represent skip; their argv is exactly the form."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        rpic(
            name=name,
            info=info,
            config=_make_config(),
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
            skip=("ignored", "names"),
        )
        args, _ = mocks["runner_instance"].run.call_args
        assert args[0] == expected

    def test_listing_dispatch_omits_skip_via_the_default(self, tmp_path: Path, monkeypatch) -> None:
        """A caller passing no ``skip`` (the listing dispatch) relies on the ``()`` default."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        result = rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        assert result == 0
        args, _kwargs = mocks["runner_instance"].run.call_args
        assert args[0] == ["-m", "goga.pipeline", "list"]


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

    def test_run_pipeline_info_container_fatal_build_surfaces_clickexception(self, tmp_path: Path, monkeypatch) -> None:
        """A fatal first-run image build surfaces as ClickException; no container launches."""
        import click

        monkeypatch.chdir(tmp_path)
        mocks = _install_happy_path(monkeypatch)
        mocks["build"].side_effect = RuntimeError("docker build failed")

        with pytest.raises(click.ClickException, match="docker build failed"):
            rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        mocks["runner_cls"].assert_not_called()
        mocks["update"].assert_not_called()

    def test_run_pipeline_info_container_fatal_update_surfaces_clickexception(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A fatal image refresh in the flat list surfaces as ClickException; no container launches."""
        import click

        monkeypatch.chdir(tmp_path)
        mocks = _install_happy_path(monkeypatch)
        mocks["update"].side_effect = RuntimeError("docker pull failed")

        with pytest.raises(click.ClickException, match="docker pull failed"):
            rpic(None, False, _make_config(), {}, update=True, workflow=None, no_workflow=False)

        mocks["runner_cls"].assert_not_called()


class TestExitCodePropagation:
    @pytest.mark.parametrize(
        ("name", "info"),
        [(None, False), (None, True), ("deploy", True)],
        ids=["flat-list", "overview", "card"],
    )
    def test_run_pipeline_info_container_propagates_nonzero_exit_code(
        self, tmp_path: Path, monkeypatch, name, info
    ) -> None:
        """A non-zero container exit code is the launcher's return value in every info form."""
        _install_happy_path(monkeypatch, exit_code=7)
        monkeypatch.chdir(tmp_path)

        result = rpic(
            name=name,
            info=info,
            config=_make_config(),
            hosts={},
            update=False,
            workflow=None,
            no_workflow=False,
        )

        assert result == 7


class TestHomeDockerThreading:
    def test_run_pipeline_info_container_threads_home_docker_run_and_build(self, tmp_path: Path, monkeypatch) -> None:
        """``home.docker.run`` reaches ``DockerRunner.run`` as separate ``extra_args``; build reaches the builders."""
        from goga.config import DockerArgsConfig, HomeConfig

        monkeypatch.chdir(tmp_path)
        mocks = _install_happy_path(monkeypatch)
        home = HomeConfig(docker=DockerArgsConfig(run=["--network=host"], build=["--squash"]))
        monkeypatch.setattr(_rpic_mod, "load_home_config", mock.Mock(return_value=home))

        result = rpic(None, False, _make_config(), {}, update=True, workflow=None, no_workflow=False)

        assert result == 0
        kwargs = mocks["runner_instance"].run.call_args.kwargs
        # extra_args is a SEPARATE keyword — never folded into params.
        assert kwargs["extra_args"] == ["--network=host"]
        assert mocks["build"].call_args.kwargs["extra_args"] == ["--squash"]
        assert mocks["update"].call_args.kwargs["extra_args"] == ["--squash"]


class TestProfileCargoEnvFile:
    """The cargo rule: an env-file joins ONLY with profile cargo, exactly two lines."""

    HOME_BUNDLE: ClassVar[dict[str, dict[str, Any]]] = {"mixa": {"worker": {"agent": "codex"}}}

    def _install_env_file_capture(self, monkeypatch) -> dict[str, object]:
        """Install the happy-path mocks with the runner reading the cargo env-file.

        Returns a ``captured`` dict the mocked runner fills per call: the
        docker-run params under their own keys (``env_file`` present only
        with cargo) plus ``env_lines`` — the env-file lines read while the
        file still exists (the launcher unlinks it in its ``finally``), or
        None when no env-file was mounted. The caller invokes ``rpic`` after
        this install and asserts on the captured state.
        """
        mocks = _install_happy_path(monkeypatch)
        captured: dict[str, object] = {"env_lines": None}

        def _read_env_file(argv, extra_args=None, **params):
            captured.update(params)

            if "env_file" in params:
                captured["env_lines"] = Path(str(params["env_file"])).read_text().splitlines()

            return 0

        mocks["runner_instance"].run.side_effect = _read_env_file

        return captured

    def test_info_container_envfile_only_with_cargo(self, tmp_path: Path, monkeypatch) -> None:
        """No cargo → no env-file; ambient profile → exactly one line, never GOGA_WORKFLOW."""
        monkeypatch.chdir(tmp_path)

        # No cargo — the minimal read-only shape, no env-file parameter.
        captured = self._install_env_file_capture(monkeypatch)
        rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)
        assert "env_file" not in captured
        assert captured["env_lines"] is None

        # Ambient profile alone (empty bundle) — exactly the one profile line,
        # never GOGA_WORKFLOW (the card resolves its own workflow decision).
        captured = self._install_env_file_capture(monkeypatch)
        monkeypatch.setenv("GOGA_PROFILE", "mixa")
        rpic(
            "deploy",
            True,
            _make_config(),
            {},
            update=False,
            workflow="hardening",
            no_workflow=False,
            profile="mixa",
        )
        assert "env_file" in captured
        assert captured["env_lines"] == ["GOGA_PROFILE=mixa"]

    def test_bundle_only_cargo_writes_exactly_the_bundle_line(self, tmp_path: Path, monkeypatch) -> None:
        """A non-empty bundle with no ambient profile → exactly the GOGA_HOME_PROFILES line."""
        from goga.docker import encode_home_profiles

        monkeypatch.chdir(tmp_path)
        captured = self._install_env_file_capture(monkeypatch)

        rpic(
            "deploy",
            True,
            _make_config(),
            {},
            update=False,
            workflow="hardening",
            no_workflow=False,
            home_profiles=self.HOME_BUNDLE,
        )

        assert "env_file" in captured
        assert captured["env_lines"] == [f"GOGA_HOME_PROFILES={encode_home_profiles(self.HOME_BUNDLE)}"]

    def test_both_cargo_kinds_write_both_lines_in_order(self, tmp_path: Path, monkeypatch) -> None:
        """Ambient profile + bundle → exactly the two profile lines, profile first."""
        from goga.docker import encode_home_profiles

        monkeypatch.chdir(tmp_path)
        captured = self._install_env_file_capture(monkeypatch)
        monkeypatch.setenv("GOGA_PROFILE", "mixa")

        rpic(
            "deploy",
            True,
            _make_config(),
            {},
            update=False,
            workflow="hardening",
            no_workflow=False,
            home_profiles=self.HOME_BUNDLE,
        )

        assert captured["env_lines"] == [
            "GOGA_PROFILE=mixa",
            f"GOGA_HOME_PROFILES={encode_home_profiles(self.HOME_BUNDLE)}",
        ]

    def test_cargo_env_file_is_unlinked_after_launch(self, tmp_path: Path, monkeypatch) -> None:
        """The private cargo env-file is gone once the launcher returns."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_PROFILE", "mixa")
        captured = self._install_env_file_capture(monkeypatch)

        rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        assert not Path(str(captured["env_file"])).exists()

    def test_cargo_env_file_is_unlinked_when_the_launch_fails(self, tmp_path: Path, monkeypatch) -> None:
        """The leak-prevention invariant holds on the failure path too — a
        docker launch that raises still unlinks the secret-bearing env-file,
        and the failure propagates to the host command."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_PROFILE", "mixa")
        mocks = _install_happy_path(monkeypatch)
        mocks["runner_instance"].run.side_effect = RuntimeError("docker exploded")

        with pytest.raises(RuntimeError, match="docker exploded"):
            rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        env_file = mocks["runner_instance"].run.call_args.kwargs.get("env_file")
        assert env_file is not None
        assert not Path(str(env_file)).exists()

    def test_card_argv_carries_profile_only_when_set(self, tmp_path: Path, monkeypatch) -> None:
        """``--profile`` joins the card argv after the workflow decision, before -s."""
        mocks = _install_happy_path(monkeypatch)
        monkeypatch.chdir(tmp_path)

        rpic(
            "deploy",
            True,
            _make_config(),
            {},
            update=False,
            workflow="hardening",
            no_workflow=False,
            profile="mixa",
            skip=("build",),
        )

        args, _kwargs = mocks["runner_instance"].run.call_args
        argv = args[0]
        assert argv[argv.index("--profile") + 1] == "mixa"
        assert argv.index("--profile") > argv.index("-w")
        assert argv.index("--profile") < argv.index("-s")

        mocks = _install_happy_path(monkeypatch)
        rpic(
            "deploy",
            True,
            _make_config(),
            {},
            update=False,
            workflow=None,
            no_workflow=False,
        )
        args, _kwargs = mocks["runner_instance"].run.call_args
        assert "--profile" not in args[0]


class TestHostPurity:
    @pytest.mark.parametrize(
        "form",
        [
            _InfoForm(name=None, info=False, workflow=None, no_workflow=False),
            _InfoForm(name=None, info=True, workflow=None, no_workflow=False),
            _InfoForm(name="deploy", info=True, workflow="hardening", no_workflow=False),
        ],
        ids=["flat-list", "overview", "card"],
    )
    def test_run_pipeline_info_container_writes_no_host_files(
        self, tmp_path: Path, monkeypatch, form: _InfoForm
    ) -> None:
        """Each info form leaves both the project dir and home dir untouched."""
        home = tmp_path / "home"
        home.mkdir()
        (home / ".goga").mkdir()
        (home / ".goga" / "config.yml").write_text("docker:\n  run: []\n  build: []\n")

        mocks = _install_happy_path(monkeypatch)
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.chdir(tmp_path)
        before_project = _snapshot_tree(tmp_path)
        before_home = _snapshot_tree(home)

        rpic(
            form.name,
            form.info,
            _make_config(),
            {},
            update=True,
            workflow=form.workflow,
            no_workflow=form.no_workflow,
        )

        assert _snapshot_tree(tmp_path) == before_project
        assert _snapshot_tree(home) == before_home
        assert mocks["runner_instance"].run.call_count == 1


class TestDirectSubstrate:
    """The 7a branch: the same minimal read-only shape executed as a direct child.

    Inside the goga image (``GOGA_DOCKER=1``) the SAME ``_compose_argv``
    composition runs as a ``run_direct`` child — the profile cargo parsed
    into the child env layer instead of an env-file — with every
    docker-hosted step skipped (no docker-CLI check, no image guard, no
    image acquisition, no DockerRunner).
    """

    def _install_direct(self, monkeypatch, returncode: int = 0) -> tuple[DirectSpawnPopen, dict[str, mock.Mock]]:
        """Marker + spawn fake + the docker-boundary mocks (unused on this substrate)."""
        import goga.docker.runner

        monkeypatch.setenv("GOGA_DOCKER", "1")
        spawn = DirectSpawnPopen(returncode=returncode)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)
        return spawn, _install_happy_path(monkeypatch)

    def test_direct_spawns_python_argv_with_cargo_overlay(self, tmp_path: Path, monkeypatch) -> None:
        """The card form spawns the composed argv; the bundle cargo reaches the child env layer."""
        from goga.docker import encode_home_profiles

        monkeypatch.chdir(tmp_path)
        spawn, mocks = self._install_direct(monkeypatch, returncode=7)
        bundle = {"mixa": {"worker": {"agent": "codex"}}}

        result = rpic(
            "deploy",
            True,
            _make_config(),
            {},
            update=False,
            workflow="hardening",
            no_workflow=False,
            home_profiles=bundle,
        )

        assert result == 7
        assert len(spawn.calls) == 1
        argv, env = spawn.calls[0]
        # The SAME card argv as the docker substrate, prefixed with python3.
        assert argv == ["python3", "-m", "goga.pipeline", "run", "deploy", "--info", "-w", "hardening"]
        # The cargo lines parsed into the child env layer (run_direct overlays
        # them on the inherited environment) — never an env-file.
        assert env["GOGA_HOME_PROFILES"] == encode_home_profiles(bundle)
        # No docker machinery ran.
        mocks["runner_cls"].assert_not_called()
        mocks["build"].assert_not_called()
        mocks["update"].assert_not_called()

    def test_direct_without_cargo_passes_env_none(self, tmp_path: Path, monkeypatch) -> None:
        """No cargo (no ambient GOGA_PROFILE, empty bundle) → the child inherits the environment untouched."""
        monkeypatch.chdir(tmp_path)
        spawn, _ = self._install_direct(monkeypatch)

        result = rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

        assert result == 0
        assert len(spawn.calls) == 1
        argv, env = spawn.calls[0]
        assert argv == ["python3", "-m", "goga.pipeline", "list"]
        assert env is None

    def test_direct_skips_docker_check_and_image_guard(self, tmp_path: Path, monkeypatch) -> None:
        """A failing docker-CLI check and an unset image both pass on the direct substrate."""
        monkeypatch.chdir(tmp_path)
        spawn, mocks = self._install_direct(monkeypatch)
        monkeypatch.setattr(_rpic_mod, "_check_docker", lambda: False)

        result = rpic(None, False, _make_config(image=None), {}, update=False, workflow=None, no_workflow=False)

        assert result == 0
        assert spawn.called
        mocks["runner_cls"].assert_not_called()

    def test_direct_spawn_failure_is_clean_click_error(self, tmp_path: Path, monkeypatch) -> None:
        """A raw OSError from the spawn is wrapped by the caller (D5) — a clean ClickException.

        ``run_direct`` propagates a spawn ``OSError`` raw (its own contract
        test pins that); this launcher owns the wrapping, so a missing
        program token is the same clean error surface as every other
        failure of the informational forms — never a traceback.
        """
        import goga.docker.runner

        monkeypatch.chdir(tmp_path)
        self._install_direct(monkeypatch)

        def _raising_popen(argv: list[str], env: dict[str, str] | None = None) -> object:
            raise FileNotFoundError(f"No such file or directory: {argv[0]}")

        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", _raising_popen)

        with pytest.raises(click.ClickException, match="No such file or directory"):
            rpic(None, False, _make_config(), {}, update=False, workflow=None, no_workflow=False)

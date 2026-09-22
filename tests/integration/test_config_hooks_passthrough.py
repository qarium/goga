"""Integration: the config-amendment checkpoint over the nine host-side surfaces.

End-to-end passthrough and secrecy over the real platform: a real project
tree in ``tmp_path`` (a ``.goga/config.yml`` plus one CODEMANIFEST cell),
every command invoked via ``CliRunner`` twice — once with no tool packages
(the baseline: the delivery is unobservable — stderr empty, stdout the
pre-change snapshot, exit codes unchanged) and once with one forcing tool
installed (the effective run: stdout unchanged except where the effective
value IS the output — ``goga config`` prints the amended value — stderr
carrying exactly the summary lines, and the authored ``config.yml``
byte-identical after every run).

The surfaces whose outside-world boundary is docker, pip, git, or the
language dispatcher pin that boundary at its single import point — the
config load, the checkpoint delivery, the merge, and the consumer switch
all run for real.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.cli import app

# The import points of the mocked outside-world boundaries (the same pinning
# points the per-command checkpoint suites use).
_pipeline_module = sys.modules["goga.commands.pipeline.pipeline"]
_contract_module = sys.modules["goga.commands.contract.contract"]
_install_module = importlib.import_module("goga.commands.install.install")
_build_module = importlib.import_module("goga.commands.build.build")
_topics_module = sys.modules["goga.commands.topics.topics"]
_status_module = importlib.import_module("goga.usages.status.status")
_sync_module = importlib.import_module("goga.usages.sync.sync")

# The one authored configuration every surface of the tree shares. Every
# knob a forcing tool amends below is authored here first (a `force` beats
# the authored value; the authored file itself never changes).
CONFIG_YML = (
    "language: python\n"
    "image: qarium/goga:latest\n"
    "build:\n"
    "  agent: codex\n"
    "pipeline:\n"
    "  agent: claude\n"
    "tools:\n"
    "  afm: 1.0.x\n"
    "usages:\n"
    "  libs:\n"
    "    click:\n"
    "      git: https://example.com/click.git\n"
    "      ref: main\n"
    "topics:\n"
    "  base_ref: origin/authored\n"
)

# A minimal valid cell — `goga lint` validates it (0 errors, 1 cell) and
# `goga contract` resolves it as a document.
MINIMAL_CELL_MANIFEST = 'Usages: {}\nAnnotations: ""\n'


def _write_project_tree(tmp_path: Path) -> None:
    """Write the real project tree: the config plus one CODEMANIFEST cell."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    (goga_dir / "config.yml").write_text(CONFIG_YML, encoding="utf-8")

    cell = tmp_path / "cell_one"
    cell.mkdir()
    (cell / "CODEMANIFEST").write_text(MINIMAL_CELL_MANIFEST, encoding="utf-8")
    (cell / "__init__.py").write_text("", encoding="utf-8")


def _authored_bytes(tmp_path: Path) -> bytes:
    """Read the authored configuration file — the never-modified artifact."""
    return (tmp_path / ".goga" / "config.yml").read_bytes()


def _install_forcer(
    install_tool_package: Callable[..., object],
    path: str,
    value: object,
    intent: str = "force",
) -> None:
    """Install the one forcing tool — ``goga_tool_forcer`` -> tool ``forcer``.

    Args:
        install_tool_package: the boundary fixture installing the fake package.
        path: the configuration path the hook amends.
        value: the amendment value.
        intent: ``force`` (overwrites the authored value) or ``set`` (applies
            only on authored silence).
    """

    def register(hooks: object) -> None:
        def amend(context: object) -> None:
            getattr(context, intent)(path, value)  # type: ignore[attr-defined]

        hooks.subscribe("config", "amend_config", "forcing", amend)  # type: ignore[attr-defined]

    install_tool_package("goga_tool_forcer", register_hooks=register)


def _expected_summary(path: str, intent: str = "force") -> str:
    """The exact stderr of a one-amendment run: header plus one line, no value."""
    word = "set" if intent == "set" else "forced"
    return f"config amendments: 1 applied\n- forcer {word} {path}\n"


class TestConfigHooksPassthrough:
    """The nine host-side surfaces, baseline run vs effective run."""

    def test_lint_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Lint: unobservable baseline; the forced ignore filters nothing here."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        pin_package_environment({})
        baseline = runner.invoke(app, ["lint"])

        assert baseline.exit_code == 0, baseline.output
        assert baseline.stderr == ""
        assert baseline.stdout == (
            "\ngoga lint\n-------------------------\ncells: 1 errors: 0\n"
        )
        assert _authored_bytes(tmp_path) == authored

        pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
        _install_forcer(install_tool_package, "lint.ignore", [".venv/"])
        amended = runner.invoke(app, ["lint"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("lint.ignore")
        assert _authored_bytes(tmp_path) == authored

    def test_config_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Config: authored paths print authored values; the amended path the effective one."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        pin_package_environment({})
        baseline_lang = runner.invoke(app, ["config", "language"])
        baseline_agent = runner.invoke(app, ["config", "build.agent"])

        assert baseline_lang.exit_code == 0
        assert baseline_lang.stdout == "# language\npython\n"
        assert baseline_lang.stderr == ""
        assert baseline_agent.exit_code == 0
        assert baseline_agent.stdout == "# build.agent\ncodex\n"
        assert baseline_agent.stderr == ""
        assert _authored_bytes(tmp_path) == authored

        pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
        _install_forcer(install_tool_package, "build.agent", "claude")
        amended_lang = runner.invoke(app, ["config", "language"])
        amended_agent = runner.invoke(app, ["config", "build.agent"])

        # The untouched path prints the authored value; the amended path is
        # the one surface whose output IS the effective value.
        assert amended_lang.exit_code == 0
        assert amended_lang.stdout == baseline_lang.stdout
        assert amended_lang.stderr == _expected_summary("build.agent")
        assert amended_agent.exit_code == 0
        assert amended_agent.stdout == "# build.agent\nclaude\n"
        assert amended_agent.stderr == _expected_summary("build.agent")
        assert _authored_bytes(tmp_path) == authored

    def test_install_bulk_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Install (bulk): the pip argv gains the amended tool; stdout stays clean."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        pip_result = mock.MagicMock()
        pip_result.returncode = 0

        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=pip_result) as pip_mock,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            pin_package_environment({})
            baseline = runner.invoke(app, ["install"])

            assert baseline.exit_code == 0, baseline.output
            assert baseline.stderr == ""
            assert "goga-tool-afm~=1.0.0" in pip_mock.call_args[0][0]

            pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
            _install_forcer(install_tool_package, "tools.viewer", "1.x", intent="set")
            amended = runner.invoke(app, ["install"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("tools.viewer", intent="set")
        assert "goga-tool-viewer~=1.0" in pip_mock.call_args[0][0]
        assert _authored_bytes(tmp_path) == authored

    def test_contract_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Contract: the dispatcher receives the effective language; JSON identical."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        spy = mock.MagicMock(return_value=[])

        with mock.patch.object(_contract_module, "contract_logic", spy):
            pin_package_environment({})
            baseline = runner.invoke(app, ["contract", "cell_one"])

            assert baseline.exit_code == 0, baseline.output
            assert baseline.stderr == ""
            assert baseline.stdout == '{\n    "cell_one": {}\n}\n'
            assert spy.call_args.args[0] == "python"

            pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
            _install_forcer(install_tool_package, "language", "golang")
            amended = runner.invoke(app, ["contract", "cell_one"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("language")
        assert spy.call_args.args[0] == "golang"
        assert _authored_bytes(tmp_path) == authored

    def test_pipeline_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Pipeline: the launcher receives the effective config; value stays off stdout."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        with mock.patch.object(_pipeline_module, "run_pipeline_container", return_value=0) as run_mock:
            pin_package_environment({})
            baseline = runner.invoke(app, ["pipeline", "deploy"])

            assert baseline.exit_code == 0, baseline.output
            assert baseline.stderr == ""
            assert run_mock.call_args.kwargs["config"].pipeline.env == {}

            pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
            _install_forcer(
                install_tool_package, "pipeline.env.LOG_LEVEL", "DEBUG", intent="set"
            )
            amended = runner.invoke(app, ["pipeline", "deploy"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("pipeline.env.LOG_LEVEL", intent="set")
        assert run_mock.call_args.kwargs["config"].pipeline.env == {"LOG_LEVEL": "DEBUG"}
        assert "DEBUG" not in amended.stdout
        assert _authored_bytes(tmp_path) == authored

    def test_build_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Build: the docker launch targets the effective image; stdout unchanged."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        with (
            mock.patch.object(_build_module, "_check_docker", return_value=True),
            mock.patch.object(_build_module, "_read_git_config", return_value={}),
            mock.patch.object(
                _build_module, "_write_env_file", return_value=tmp_path / "env"
            ),
            mock.patch.object(_build_module, "docker_build_if_not_exist"),
            mock.patch.object(_build_module, "DockerRunner") as runner_mock,
        ):
            runner_mock.return_value.run.return_value = 0

            pin_package_environment({})
            baseline = runner.invoke(app, ["build", "--skip-manifest-check", "plan.md"])

            assert baseline.exit_code == 0, baseline.output
            assert baseline.stderr == ""
            assert runner_mock.call_args.args[0] == "qarium/goga:latest"

            pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
            _install_forcer(install_tool_package, "image", "qarium/goga:effective")
            amended = runner.invoke(app, ["build", "--skip-manifest-check", "plan.md"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("image")
        assert runner_mock.call_args.args[0] == "qarium/goga:effective"
        assert "qarium/goga:effective" not in amended.stdout
        assert _authored_bytes(tmp_path) == authored

    def test_topics_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Topics: the create step resolves the amended base; one line on stdout."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        with mock.patch.object(
            _topics_module, "create_topic", return_value="created X"
        ) as create_mock:
            pin_package_environment({})
            baseline = runner.invoke(
                app, ["topics", "create", "X", "--publish", "-t", "T"]
            )

            assert baseline.exit_code == 0, baseline.output
            assert baseline.stderr == ""
            assert baseline.stdout == "created X\n"
            assert create_mock.call_args.args[1] == "origin/authored"

            pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
            _install_forcer(install_tool_package, "topics.base_ref", "origin/amended")
            amended = runner.invoke(
                app, ["topics", "create", "X", "--publish", "-t", "T"]
            )

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("topics.base_ref")
        assert create_mock.call_args.args[1] == "origin/amended"
        assert _authored_bytes(tmp_path) == authored

    def test_usages_status_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Usages status: the fully real run — a new dep renders identically either way."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        pin_package_environment({})
        baseline = runner.invoke(app, ["usages", "status"])

        # The dep was never synced — `new` (exit 1 by the report's contract).
        assert baseline.exit_code == 1
        assert baseline.stderr == ""
        assert baseline.stdout == "libs/\n└── [+] click/\n"
        assert _authored_bytes(tmp_path) == authored

        pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
        _install_forcer(install_tool_package, "usages.libs.click.ref", "amended-ref")
        amended = runner.invoke(app, ["usages", "status"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("usages.libs.click.ref")
        # The amended ref never reaches any output surface — the report
        # renders the dep name and state only.
        assert "amended-ref" not in amended.stdout
        assert _authored_bytes(tmp_path) == authored

    def test_usages_sync_passthrough_and_effective_run(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Usages sync: the clone receives the effective ref; the authored file survives --force."""
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        with (
            mock.patch.object(
                _sync_module, "clone_repository", return_value=fake_repo
            ) as clone_mock,
            mock.patch.object(_sync_module, "deploy_usages"),
        ):
            pin_package_environment({})
            baseline = runner.invoke(app, ["usages", "sync", "--force"])

            assert baseline.exit_code == 0, baseline.output
            assert baseline.stderr == ""
            assert baseline.stdout == ""
            assert clone_mock.call_args.args == ("https://example.com/click.git", "main")

            pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
            _install_forcer(install_tool_package, "usages.libs.click.ref", "amended-ref")
            amended = runner.invoke(app, ["usages", "sync", "--force"])

        assert amended.exit_code == baseline.exit_code
        assert amended.stdout == baseline.stdout
        assert amended.stderr == _expected_summary("usages.libs.click.ref")
        assert clone_mock.call_args.args == ("https://example.com/click.git", "amended-ref")
        assert _authored_bytes(tmp_path) == authored

    def test_no_configuration_value_leaks_beyond_the_data_surfaces(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The amended values appear nowhere except the config value surface.

        One forcing tool amends three values at once; the three fully real
        data surfaces that do not print configuration values (`lint`,
        `usages status`, `usages sync` with its clone boundary pinned) carry
        no trace of any amended value on either stream — stderr is exactly
        the summary lines, stdout the unchanged baseline.
        """
        _write_project_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        authored = _authored_bytes(tmp_path)
        runner = CliRunner()

        pin_package_environment({})
        lint_baseline = runner.invoke(app, ["lint"])
        status_baseline = runner.invoke(app, ["usages", "status"])

        def register(hooks: object) -> None:
            def amend(context: object) -> None:
                context.force("build.agent", "claude")  # type: ignore[attr-defined]
                context.force("usages.libs.click.ref", "amended-ref")  # type: ignore[attr-defined]
                context.set("pipeline.env.LOG_LEVEL", "DEBUG")  # type: ignore[attr-defined]

            hooks.subscribe("config", "amend_config", "forcing", amend)  # type: ignore[attr-defined]

        pin_package_environment({"goga_tool_forcer": ["goga-tool-forcer"]})
        install_tool_package("goga_tool_forcer", register_hooks=register)

        amended_lint = runner.invoke(app, ["lint"])
        amended_status = runner.invoke(app, ["usages", "status"])

        values = ("claude", "amended-ref", "DEBUG")
        for result, baseline in (
            (amended_lint, lint_baseline),
            (amended_status, status_baseline),
        ):
            assert result.exit_code == baseline.exit_code
            assert result.stdout == baseline.stdout
            assert result.stderr == (
                "config amendments: 3 applied\n"
                "- forcer forced build.agent\n"
                "- forcer forced usages.libs.click.ref\n"
                "- forcer set pipeline.env.LOG_LEVEL\n"
            )
            for value in values:
                assert value not in result.stdout
                assert value not in result.stderr

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()
        with (
            mock.patch.object(_sync_module, "clone_repository", return_value=fake_repo) as clone_mock,
            mock.patch.object(_sync_module, "deploy_usages"),
        ):
            amended_sync = runner.invoke(app, ["usages", "sync", "--force"])

        assert amended_sync.exit_code == 0, amended_sync.output
        assert amended_sync.stdout == ""
        assert clone_mock.call_args.args == ("https://example.com/click.git", "amended-ref")
        for value in values:
            assert value not in amended_sync.stdout
            assert value not in amended_sync.stderr
        assert _authored_bytes(tmp_path) == authored

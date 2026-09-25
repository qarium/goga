"""Config-amendment checkpoint tests for the ``build`` command.

Pins the consumer-side delivery shape of the ``checkpoints`` practice: the
delivery joins the project-config load try (after the docker check; the home
configuration load stays authored-only), the summary lines print to stderr,
and every downstream field access — the guard, the image — addresses the
effective configuration. The platform boundary fixtures pin only the
installed-packages mapping and the ``sys.modules`` entry of the fake
``goga_tool_*`` package.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _write_two_part_config(tmp_path: Path) -> None:
    """Write a build-capable two-part ``.goga/config.yml`` under ``tmp_path``."""
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(
        yaml.dump(
            {
                "language": "python",
                "image": "qarium/goga:latest",
                "build": {"agent": "claude"},
                "pipeline": {"agent": "claude"},
            }
        )
    )


def _register_hardener(hooks: object) -> None:
    """Subscribe one hook that buffers an image amendment."""

    def harden(context: object) -> None:
        context.force("image", "qarium/goga:effective")  # type: ignore[attr-defined]

    hooks.subscribe("config", "amend_config", "hardening", harden)  # type: ignore[attr-defined]


class TestBuildConfigCheckpoint:
    def test_build_consumes_effective_config_and_prints_summary_to_stderr(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The docker launch targets the effective image.

        One run without tools (the baseline) and one with a forcing tool: the
        runner is constructed with the amended image, the summary line lands
        on stderr only, and stdout and exit code stay identical.
        """
        _write_two_part_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        def _fake_write_env(env, extra_env):
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            baseline = runner.invoke(build_cmd, ["--skip-manifest-check", "plan.md"])
            assert baseline.exit_code == 0, baseline.output
            assert mock_runner.call_args.args[0] == "qarium/goga:latest"

            pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})
            install_tool_package("goga_tool_hardener", register_hooks=_register_hardener)

            amended = runner.invoke(build_cmd, ["--skip-manifest-check", "plan.md"])

        assert amended.exit_code == 0, amended.output
        assert mock_runner.call_args.args[0] == "qarium/goga:effective"

        assert "- hardener forced image" in amended.stderr
        assert "- hardener forced image" not in amended.stdout
        assert amended.stdout == baseline.stdout
        assert amended.exit_code == baseline.exit_code

    def test_build_hard_checkpoint_failure_is_clean_error(
        self,
        tmp_path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the command: exit 1, clean message, no launch."""

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("config", "amend_config", "exploding", boom)  # type: ignore[attr-defined]

        _write_two_part_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_hardener": ["goga-tool-hardener"]})
        install_tool_package("goga_tool_hardener", register_hooks=register)

        runner = CliRunner()
        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = runner.invoke(build_cmd, ["--skip-manifest-check", "plan.md"])

        assert result.exit_code == 1
        assert "failed on config.amend_config" in result.output
        assert "Traceback" not in result.output
        mock_runner.return_value.run.assert_not_called()

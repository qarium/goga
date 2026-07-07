from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import click
import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.commands.build.build import _build_docker_cmd

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _write_goga_yml(
    tmp_path: Path,
    *,
    no_image: bool = False,
    build_proxy: str | None = None,
    build_hosts: dict[str, str] | None = None,
) -> None:
    """Write a minimal .goga/config.yml, optionally with build.proxy/hosts."""
    data: dict = {
        "language": "python",
        "image": "qarium/goga:latest",
        "build": {"task_executor": {"agent": "claude"}},
        "pipeline": {"agent": "claude"},
    }
    if no_image:
        del data["image"]
    if build_proxy is not None:
        data["build"]["proxy"] = build_proxy
    if build_hosts is not None:
        data["build"]["hosts"] = build_hosts
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _run_build_in_tmp(tmp_path, monkeypatch, args=None, *, skip_manifest_check=True):
    """Run the build command from tmp_path (cwd relocated for load_config)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = list(args or [])
    if skip_manifest_check:
        full_args = ["--skip-manifest-check", *full_args]
    return runner.invoke(build_cmd, full_args)


# --- Contract tests ---


class TestBuildProxyHostsUpdateContract:
    def test_build_has_proxy_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "proxy" in param_names

    def test_build_has_add_host_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "add_host" in param_names

    def test_build_add_host_option_is_multiple(self) -> None:
        add_host_param = next(p for p in build_cmd.params if p.name == "add_host")
        assert add_host_param.multiple is True

    def test_build_has_update_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "update" in param_names

    def test_build_update_option_defaults_false(self) -> None:
        update_param = next(p for p in build_cmd.params if p.name == "update")
        assert update_param.is_flag is True
        assert update_param.default is False

    def test_build_update_has_short_flag(self) -> None:
        update_param = next(p for p in build_cmd.params if p.name == "update")
        assert "-u" in update_param.opts

    def test_build_thirteen_options(self) -> None:
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 13

    def test_help_lists_new_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        assert result.exit_code == 0
        output = result.output
        assert "--proxy" in output
        assert "--add-host" in output
        assert "--update" in output
        assert "-u" in output


# --- Logic tests (positive) ---


class TestProxyResolution:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_build_cli_proxy_overrides_config(  # noqa: PLR0913
        self, mock_cmd, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, build_proxy="http://from-config:3128")
        mock_env.return_value = Path("/tmp/env")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["--proxy", "http://from-cli:8080", "plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert env_dict["HTTP_PROXY"] == "http://from-cli:8080"
        assert env_dict["HTTPS_PROXY"] == "http://from-cli:8080"
        assert env_dict["NO_PROXY"] == "localhost,127.0.0.1"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_build_proxy_none_falls_back_to_config(  # noqa: PLR0913
        self, mock_cmd, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, build_proxy="http://from-config:3128")
        mock_env.return_value = Path("/tmp/env")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert env_dict["HTTP_PROXY"] == "http://from-config:3128"
        assert env_dict["HTTPS_PROXY"] == "http://from-config:3128"
        assert env_dict["NO_PROXY"] == "localhost,127.0.0.1"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_build_no_proxy_vars_when_proxy_absent(  # noqa: PLR0913
        self, mock_cmd, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert "HTTP_PROXY" not in env_dict
        assert "HTTPS_PROXY" not in env_dict
        assert "NO_PROXY" not in env_dict


class TestAddHostResolution:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_add_host_single_colon_split(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, build_hosts={"existing.local": "10.0.0.1"})
        mock_env.return_value = Path("/tmp/env")
        # Isolate HOME so resolve_credential_mounts adds no mounts.
        monkeypatch.setenv("HOME", str(tmp_path))

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                [
                    "--add-host", "foo.local:127.0.0.1",
                    "--add-host", "existing.local:192.168.1.1",
                    "plan.md",
                ],
            )

        cmd = mock_popen.call_args[0][0]
        assert "--add-host" in cmd
        assert "foo.local:127.0.0.1" in cmd
        # CLI overrides config on key conflict: existing.local uses the CLI IP.
        assert "existing.local:192.168.1.1" in cmd
        assert "existing.local:10.0.0.1" not in cmd
        assert "10.0.0.1" not in cmd

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_add_host_merged_hosts_passed_to_build_cmd(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, build_hosts={"a.local": "10.0.0.1"})
        mock_env.return_value = Path("/tmp/env")
        monkeypatch.setenv("HOME", str(tmp_path))

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                ["--add-host", "b.local:127.0.0.1", "plan.md"],
            )

        # The merged host map surfaces in the assembled docker command.
        cmd = _build_docker_cmd(
            "plan.md",
            "qarium/goga:latest",
            Path("/tmp/env"),
            {},
            "test-build",
            {"a.local": "10.0.0.1", "b.local": "127.0.0.1"},
        )
        assert "--add-host" in cmd
        assert "a.local:10.0.0.1" in cmd
        assert "b.local:127.0.0.1" in cmd

    def test_build_docker_cmd_no_add_host_when_empty(self) -> None:
        cmd = _build_docker_cmd(
            "plan.md",
            "goga:latest",
            Path("/tmp/env"),
            {},
            "test-build",
            {},
        )
        assert "--add-host" not in cmd


class TestConditionalPull:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_build_update_false_skips_pull(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_build_mod, "_pull_image") as mock_pull,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_pull.assert_not_called()
        mock_popen.assert_called_once()

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_build_update_true_pulls_image(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_build_mod, "_pull_image") as mock_pull,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["--update", "plan.md"])

        mock_pull.assert_called_once_with("qarium/goga:latest")


# --- Logic tests (negative) ---


class TestBuildNegativeCases:
    def test_build_docker_missing_raises(self, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        with mock.patch.object(_build_mod, "_check_docker", return_value=False):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        assert result.exit_code == 1
        assert "docker not found" in result.output

    def test_build_image_none_raises(self, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, no_image=True)
        with mock.patch.object(_build_mod, "_check_docker", return_value=True):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        assert result.exit_code == 1
        assert "image in .goga/config.yml is not set" in result.output

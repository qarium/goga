from __future__ import annotations

from pathlib import Path
from unittest import mock

import click
import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _write_goga_yml(
    tmp_path: Path,
    *,
    no_image: bool = False,
    build_proxy: str | None = None,
    build_hosts: dict[str, str] | None = None,
    dockerfile: str | None = None,
) -> None:
    """Write a minimal .goga/config.yml, optionally with build.proxy/hosts/dockerfile."""
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
    if dockerfile is not None:
        data["dockerfile"] = dockerfile
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _run_build_in_tmp(tmp_path, monkeypatch, args=None, *, skip_manifest_check=True):
    """Run the build command from tmp_path (cwd relocated for load_project_config)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = list(args or [])
    if skip_manifest_check:
        full_args = ["--skip-manifest-check", *full_args]
    return runner.invoke(build_cmd, full_args)


def _patch_runner_ok():
    """Patch DockerRunner so .run captures (args, params) and returns 0.

    Returns the mock whose ``return_value.run`` records the launch call.
    """
    mock_runner = mock.patch.object(_build_mod, "DockerRunner")
    return mock_runner


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

    def test_build_fourteen_options(self) -> None:
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 14

    def test_help_lists_new_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        assert result.exit_code == 0
        output = result.output
        assert "--proxy" in output
        assert "--add-host" in output
        assert "--clean" in output
        assert "--update" in output
        assert "-u" in output


# --- Logic tests (positive) ---


class TestProxyResolution:
    """Proxy env-vars are resolved in the caller and reach the env-file content."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_cli_proxy_overrides_config(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, build_proxy="http://from-config:3128")
        mock_env.return_value = Path("/tmp/env")

        with _patch_runner_ok() as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["--proxy", "http://from-cli:8080", "plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert env_dict["HTTP_PROXY"] == "http://from-cli:8080"
        assert env_dict["HTTPS_PROXY"] == "http://from-cli:8080"
        assert env_dict["NO_PROXY"] == "localhost,127.0.0.1"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_proxy_none_falls_back_to_config(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, build_proxy="http://from-config:3128")
        mock_env.return_value = Path("/tmp/env")

        with _patch_runner_ok() as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert env_dict["HTTP_PROXY"] == "http://from-config:3128"
        assert env_dict["HTTPS_PROXY"] == "http://from-config:3128"
        assert env_dict["NO_PROXY"] == "localhost,127.0.0.1"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_no_proxy_vars_when_proxy_absent(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with _patch_runner_ok() as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert "HTTP_PROXY" not in env_dict
        assert "HTTPS_PROXY" not in env_dict
        assert "NO_PROXY" not in env_dict


class TestAddHostResolution:
    """Merged hosts reach params['add_host'] handed to DockerRunner.run."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_add_host_single_colon_split(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, build_hosts={"existing.local": "10.0.0.1"})
        mock_env.return_value = Path("/tmp/env")
        # Isolate HOME so resolve_credential_mounts adds no mounts.
        monkeypatch.setenv("HOME", str(tmp_path))

        with _patch_runner_ok() as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                [
                    "--add-host",
                    "foo.local:127.0.0.1",
                    "--add-host",
                    "existing.local:192.168.1.1",
                    "plan.md",
                ],
            )

        add_hosts = mock_runner.return_value.run.call_args.kwargs["add_host"]
        assert "foo.local:127.0.0.1" in add_hosts
        # CLI overrides config on key conflict: existing.local uses the CLI IP.
        assert "existing.local:192.168.1.1" in add_hosts
        assert "existing.local:10.0.0.1" not in add_hosts
        assert "10.0.0.1" not in add_hosts

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_add_host_merged_hosts_passed_to_runner_params(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, build_hosts={"a.local": "10.0.0.1"})
        mock_env.return_value = Path("/tmp/env")
        monkeypatch.setenv("HOME", str(tmp_path))

        with _patch_runner_ok() as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                ["--add-host", "b.local:127.0.0.1", "plan.md"],
            )

        add_hosts = mock_runner.return_value.run.call_args.kwargs["add_host"]
        assert "a.local:10.0.0.1" in add_hosts  # from config.build.hosts
        assert "b.local:127.0.0.1" in add_hosts  # from --add-host

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_no_add_host_when_empty(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        monkeypatch.setenv("HOME", str(tmp_path))

        with _patch_runner_ok() as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        add_hosts = mock_runner.return_value.run.call_args.kwargs["add_host"]
        assert add_hosts == []


class TestConditionalUpdate:
    """--update delegates to docker_update (build when dockerfile set, pull when None)."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_update_false_skips_docker_update(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with (
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            _patch_runner_ok() as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_update.assert_not_called()
        mock_runner.return_value.run.assert_called_once()

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_update_true_pulls_when_dockerfile_none(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with (
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            _patch_runner_ok() as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["--update", "plan.md"])

        # dockerfile is None here → docker_update delegates to the pull branch.
        # home.docker.build (empty for an absent home file) is forwarded as the
        # separate extra_args keyword (build branch only — ignored on the pull
        # branch, but still passed by the launcher).
        mock_update.assert_called_once_with("qarium/goga:latest", None, extra_args=[])
        mock_runner.return_value.run.assert_called_once()

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_update_with_dockerfile_calls_docker_update_build(
        self, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        """--update with a declared Dockerfile → docker_update(image, dockerfile) + DockerRunner(image)."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        mock_env.return_value = Path("/tmp/env")

        with (
            # docker_build_if_not_exist runs unconditionally before docker_update
            # and is not the subject of this test — mock it to avoid a real
            # docker build (it would otherwise shell out to a docker that is not
            # present in the test environment).
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            _patch_runner_ok() as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["--update", "plan.md"])

        # dockerfile is set → docker_update takes the build branch.
        # home.docker.build (empty for an absent home file) is forwarded as the
        # separate extra_args keyword (build branch only).
        mock_update.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=[])
        # DockerRunner is constructed with the config image.
        mock_runner.assert_called_once_with("qarium/goga:latest")
        mock_runner.return_value.run.assert_called_once()


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

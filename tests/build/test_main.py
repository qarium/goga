from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.build import __main__ as build_main_module
from goga.build.__main__ import main
from goga.config.hooks import AppliedAmendment, ConfigHooks, ConfigOverlay
from goga.config.project import BuildConfig, ProjectConfig


def _write_goga_yml(tmp_path: Path) -> None:
    data = {
        "language": "python",
        "build": {"agent": "claude"},
    }
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _project_config(agent: str | None) -> ProjectConfig:
    """Build a minimal project configuration around one build section."""
    return ProjectConfig(
        language="python",
        image=None,
        dockerfile=None,
        build=BuildConfig(agent=agent),
        pipeline=None,
    )


class TestMainConfigAmendContract:
    """Contract-surface lock: main() delivers the config amendment checkpoint.

    Steps 2-4 of the entrypoint contract — the authored load, the
    ``ConfigHooks`` delivery, the summary lines, and the handover of the
    overlay's effective configuration to ``build``.
    """

    def test_main_module_references_config_hooks_surface(self) -> None:
        """Contract: the entry module carries the amend surface (ConfigHooks)."""

        assert "ConfigHooks" in dir(build_main_module)

    def test_main_forwards_overlay_effective_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Contract: build receives the overlay's effective configuration, never the authored one."""

        monkeypatch.setenv("GOGA_DOCKER", "1")

        authored = _project_config(agent=None)
        effective = _project_config(agent="codex")
        overlay = ConfigOverlay(config=effective, applied=[])

        monkeypatch.setattr(build_main_module, "load_project_config", lambda: authored)

        def _amend(self: ConfigHooks, config: ProjectConfig) -> ConfigOverlay:
            return overlay

        monkeypatch.setattr(ConfigHooks, "amend_config", _amend)

        with (
            mock.patch.object(build_main_module, "build", return_value=0) as mock_build,
            mock.patch("sys.argv", ["goga.build", "plan.md"]),
        ):
            main()

        assert mock_build.call_count == 1
        assert mock_build.call_args[0][1] is effective


class TestMainConfigDelivery:
    """Steps 2-4 — the load-and-amend opening and its clean-error boundaries.

    Every scenario pins the container guard to a no-op and patches the four
    seams the design names — ``ensure_in_docker``, ``load_project_config``,
    ``ConfigHooks.amend_config``, and ``build`` on the entry module.
    """

    @staticmethod
    def _overlay(effective: ProjectConfig, applied: list[AppliedAmendment]) -> ConfigOverlay:
        """Build a real overlay around one effective configuration."""
        return ConfigOverlay(config=effective, applied=applied)

    def test_main_loads_amends_and_forwards_effective_config(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The amendment sets build.agent; build receives the EFFECTIVE config and returns its code."""

        monkeypatch.setattr(build_main_module, "ensure_in_docker", lambda: None)

        authored = _project_config(agent=None)
        effective = _project_config(agent="codex")
        overlay = self._overlay(effective, [AppliedAmendment(tool="tool", path="build.agent", intent="set")])

        monkeypatch.setattr(build_main_module, "load_project_config", lambda: authored)

        def _amend(self: ConfigHooks, config: ProjectConfig) -> ConfigOverlay:
            return overlay

        monkeypatch.setattr(ConfigHooks, "amend_config", _amend)

        with (
            mock.patch.object(build_main_module, "build", return_value=7) as mock_build,
            mock.patch("sys.argv", ["goga.build", "plan.md"]),
        ):
            exit_code = main()

        assert exit_code == 7
        assert mock_build.call_count == 1
        assert mock_build.call_args[0][0] == "plan.md"
        assert mock_build.call_args[0][1] is overlay.config
        cli_options = mock_build.call_args[0][2]
        assert cli_options["dry_run"] is False
        assert cli_options["skip_review"] is None

        captured = capsys.readouterr()
        assert "config amendments: 1 applied" in captured.err
        assert "- tool set build.agent" in captured.err

    def test_main_config_failure_exit_1_ralphex_never_launches(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A failed authored load is one clean stderr line, exit 1, no build launch."""

        monkeypatch.setattr(build_main_module, "ensure_in_docker", lambda: None)

        def _load() -> ProjectConfig:
            raise ValueError("bad mapping")

        monkeypatch.setattr(build_main_module, "load_project_config", _load)

        with (
            mock.patch.object(build_main_module, "build", return_value=0) as mock_build,
            mock.patch("sys.argv", ["goga.build", "plan.md"]),
        ):
            exit_code = main()

        assert exit_code == 1
        assert mock_build.call_count == 0

        captured = capsys.readouterr()
        assert "bad mapping" in captured.err
        assert "Traceback" not in captured.err

    def test_main_delivery_failure_exit_1_names_tool(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A failed amendment delivery is one clean stderr error naming the tool, exit 1."""

        monkeypatch.setattr(build_main_module, "ensure_in_docker", lambda: None)

        monkeypatch.setattr(
            build_main_module,
            "load_project_config",
            lambda: _project_config(agent="claude"),
        )
        monkeypatch.setattr(
            ConfigHooks,
            "amend_config",
            mock.MagicMock(side_effect=ValueError("toolB: hook failed on amend_config")),
        )

        with (
            mock.patch.object(build_main_module, "build", return_value=0) as mock_build,
            mock.patch("sys.argv", ["goga.build", "plan.md"]),
        ):
            exit_code = main()

        assert exit_code == 1
        assert mock_build.call_count == 0

        captured = capsys.readouterr()
        assert "toolB" in captured.err
        assert "amend_config" in captured.err
        assert "Traceback" not in captured.err


class TestMainEntry:
    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_returns_zero_on_success(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            assert main() == 0

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=1)
    def test_main_returns_nonzero_on_failure(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            assert main() == 1

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_calls_build_with_parsed_args(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-review", "--skip-manifest-check"]),
        ):
            main()

        call_args = mock_build.call_args
        assert call_args[0][0] == "plan.md"
        cli_options = call_args[0][2]
        assert cli_options["skip_review"] is True
        assert cli_options["skip_manifest_check"] is True

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_dry_run_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--dry-run", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["dry_run"] is True

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_session_timeout_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--session-timeout", "30m", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["session_timeout"] == "30m"

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_max_iterations_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--max-iterations", "10", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["max_iterations"] == 10

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_review_patience_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--review-patience", "5", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["review_patience"] == 5

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_base_ref_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--base-ref", "origin/1.2.x", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["base_ref"] == "origin/1.2.x"

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_base_ref_absent_defaults_none(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        # Key present, value None — the tri-state survives to the resolver,
        # which then falls through to build.review.base_ref.
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert "base_ref" in cli_options
        assert cli_options["base_ref"] is None

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_idle_timeout_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--idle-timeout", "1h", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["idle_timeout"] == "1h"

    def test_build_main_proceeds_after_guard_in_container(self, monkeypatch) -> None:
        monkeypatch.setenv("GOGA_DOCKER", "1")

        with (
            mock.patch("goga.build.__main__.build", return_value=42) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            assert main() == 42

        call_args = mock_build.call_args
        assert call_args[0][0] == "plan.md"
        cli_options = call_args[0][2]
        assert cli_options["skip_manifest_check"] is True

    def test_build_main_refuses_on_host(self, monkeypatch, capsys) -> None:
        monkeypatch.delenv("GOGA_DOCKER", raising=False)

        def _fail_if_called(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("build must not be called on the host")

        def _fail_config(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("load_project_config must not be called on the host")

        with (
            mock.patch("goga.build.__main__.build", side_effect=_fail_if_called) as mock_build,
            mock.patch("goga.build.__main__.load_project_config", side_effect=_fail_config) as mock_config,
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        assert mock_build.call_count == 0
        assert mock_config.call_count == 0
        assert "goga Docker image" in capsys.readouterr().err


class TestContract:
    """Contract-surface lock: the in-container guard is wired as step 0 of main()."""

    def test_main_accepts_skip_review_pair(self, monkeypatch) -> None:
        """Contract: --skip-review/--no-skip-review parse into one dest and land in cli_options."""

        monkeypatch.setenv("GOGA_DOCKER", "1")

        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check", "--skip-review"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["skip_review"] is True

    def test_main_calls_ensure_in_docker_first(self, monkeypatch) -> None:
        monkeypatch.setenv("GOGA_DOCKER", "1")

        call_order: list[str] = []

        def _record_ensure(*_args: object, **_kwargs: object) -> None:
            call_order.append("ensure_in_docker")

        def _record_build(*_args: object, **_kwargs: object) -> int:
            call_order.append("build")
            return 0

        with (
            mock.patch("goga.build.__main__.ensure_in_docker", side_effect=_record_ensure) as mock_ensure,
            mock.patch("goga.build.__main__.build", side_effect=_record_build),
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            main()

        assert mock_ensure.call_count == 1
        assert call_order == ["ensure_in_docker", "build"]

    def test_main_cli_options_contain_skip_review_key(self, monkeypatch) -> None:
        """Contract: cli_options always carries `skip_review` (None when neither flag is passed)."""

        monkeypatch.setenv("GOGA_DOCKER", "1")

        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert "skip_review" in cli_options
        assert cli_options["skip_review"] is None


class TestMainSkipReviewPair:
    """Tri-state --skip-review/--no-skip-review pair: None/True/False without parser conflicts."""

    @pytest.mark.parametrize(
        ("flag", "expected"),
        [("--skip-review", True), ("--no-skip-review", False), (None, None)],
    )
    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_skip_review_pair_tri_state(self, mock_build, mock_config, monkeypatch, flag, expected) -> None:
        argv = ["goga.build", "plan.md", "--skip-manifest-check"]

        if flag is not None:
            argv.append(flag)

        with (
            mock.patch.dict(os.environ, {"GOGA_DOCKER": "1"}),
            mock.patch("sys.argv", argv),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["skip_review"] is expected

    @mock.patch("goga.build.__main__.load_project_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_help_lists_both_flags(self, mock_build, mock_config, monkeypatch, capsys) -> None:
        monkeypatch.setenv("GOGA_DOCKER", "1")

        with (
            mock.patch("sys.argv", ["goga.build", "--help"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0
        help_text = capsys.readouterr().out
        assert "--skip-review" in help_text
        assert "--no-skip-review" in help_text


class TestCliOptionsSurface:
    """Contract: main() forwards exactly the nine live cli_options keys; the retired flags are parse errors."""

    def test_main_forwards_exactly_nine_cli_option_keys(self, monkeypatch) -> None:
        """Contract: cli_options carries the nine live keys and nothing else."""

        monkeypatch.setenv("GOGA_DOCKER", "1")

        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]),
        ):
            main()

        cli_options = mock_build.call_args[0][2]
        assert set(cli_options) == {
            "dry_run",
            "skip_manifest_check",
            "skip_review",
            "base_ref",
            "review_patience",
            "session_timeout",
            "idle_timeout",
            "wait",
            "max_iterations",
        }

    @pytest.mark.parametrize("flag", ["--worktree", "--skip-finalize"])
    def test_main_rejects_retired_flags(self, monkeypatch, flag) -> None:
        """Contract: --worktree/--skip-finalize exit with an argparse error and never reach build."""

        monkeypatch.setenv("GOGA_DOCKER", "1")

        with (
            mock.patch("goga.build.__main__.build", return_value=0) as mock_build,
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", flag]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2
        assert mock_build.call_count == 0

    def test_main_argparse_surface_matches_contract(self, monkeypatch) -> None:
        """The surface forwards the tri-state pair and the patience knob; the guard runs first."""

        call_order: list[str] = []
        forwarded: list[dict] = []

        def _record_ensure(*_args: object, **_kwargs: object) -> None:
            call_order.append("ensure_in_docker")

        def _capture_build(plan: str, config: object, cli_options: dict) -> int:
            call_order.append("build")
            forwarded.append(cli_options)
            return 0

        with (
            mock.patch("goga.build.__main__.ensure_in_docker", side_effect=_record_ensure),
            mock.patch("goga.build.__main__.build", side_effect=_capture_build),
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-review", "--review-patience", "3"]),
        ):
            main()

        assert forwarded[0]["skip_review"] is True
        assert forwarded[0]["review_patience"] == 3

        with (
            mock.patch("goga.build.__main__.ensure_in_docker", side_effect=_record_ensure),
            mock.patch("goga.build.__main__.build", side_effect=_capture_build),
            mock.patch("goga.build.__main__.load_project_config"),
            mock.patch("sys.argv", ["goga.build", "plan.md", "--no-skip-review"]),
        ):
            main()

        assert forwarded[1]["skip_review"] is False
        assert call_order == ["ensure_in_docker", "build", "ensure_in_docker", "build"]

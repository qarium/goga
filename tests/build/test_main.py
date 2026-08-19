from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.build.__main__ import main


def _write_goga_yml(tmp_path: Path) -> None:
    data = {
        "language": "python",
        "build": {"task_executor": {"agent": "claude"}},
    }
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


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
            mock.patch("sys.argv", ["goga.build", "plan.md", "--worktree", "--skip-manifest-check"]),
        ):
            main()

        call_args = mock_build.call_args
        assert call_args[0][0] == "plan.md"
        cli_options = call_args[0][2]
        assert cli_options["worktree"] is True
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
            mock.patch("sys.argv", ["goga.build", "plan.md", "--worktree"]),
        ):
            assert main() == 42

        call_args = mock_build.call_args
        assert call_args[0][0] == "plan.md"
        cli_options = call_args[0][2]
        assert cli_options["worktree"] is True

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

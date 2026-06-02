from __future__ import annotations

from pathlib import Path
from unittest import mock

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
    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_returns_zero_on_success(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]):
            assert main() == 0

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=1)
    def test_main_returns_nonzero_on_failure(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--skip-manifest-check"]):
            assert main() == 1

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_calls_build_with_parsed_args(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--worktree", "--skip-manifest-check"]):
            main()

        call_args = mock_build.call_args
        assert call_args[0][0] == "plan.md"
        cli_options = call_args[0][2]
        assert cli_options["worktree"] is True
        assert cli_options["skip_manifest_check"] is True

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_dry_run_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--dry-run", "--skip-manifest-check"]):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["dry_run"] is True

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_session_timeout_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--session-timeout", "30m", "--skip-manifest-check"]):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["session_timeout"] == "30m"

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_max_iterations_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--max-iterations", "10", "--skip-manifest-check"]):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["max_iterations"] == 10

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_review_patience_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--review-patience", "5", "--skip-manifest-check"]):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["review_patience"] == 5

    @mock.patch("goga.build.__main__.load_config")
    @mock.patch("goga.build.__main__.build", return_value=0)
    def test_main_idle_timeout_flag(self, mock_build, mock_config, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_goga_yml(tmp_path)

        with mock.patch("sys.argv", ["goga.build", "plan.md", "--idle-timeout", "1h", "--skip-manifest-check"]):
            main()

        cli_options = mock_build.call_args[0][2]
        assert cli_options["idle_timeout"] == "1h"

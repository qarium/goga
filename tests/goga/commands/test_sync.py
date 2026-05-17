from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands import sync as facade_sync
from goga.commands.sync import sync
from goga.sync.sync import (
    _extract_dep_name,
    _is_git_url,
    _prepare_clone_url,
)


class TestContract:
    def test_sync_is_click_command(self) -> None:
        assert isinstance(sync, click.Command)

    def test_sync_has_source_argument(self) -> None:
        params = {p.name: p for p in sync.params}
        assert "source" in params
        assert isinstance(params["source"], click.Argument)

    def test_sync_has_token_option(self) -> None:
        params = {p.name: p for p in sync.params}
        assert "token" in params
        assert params["token"].default is None

    def test_sync_has_branch_option(self) -> None:
        params = {p.name: p for p in sync.params}
        assert "branch" in params
        assert params["branch"].default is None

    def test_sync_importable_from_commands(self) -> None:
        assert facade_sync is sync


class TestIsGitUrl:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("http://example.com/repo", True),
            ("https://example.com/repo", True),
            ("git@github.com:user/repo.git", True),
            ("ssh://git@github.com/user/repo", True),
            ("/local/path", False),
            ("relative/path", False),
            ("HTTP://example.com/repo", False),
        ],
    )
    def test_sync_is_git_url_detects_protocols(self, source: str, expected: bool) -> None:
        assert _is_git_url(source) is expected


class TestExtractDepName:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("https://github.com/user/my-lib", "my-lib"),
            ("https://gitlab.com/org/repo.git", "repo"),
            ("git@github.com:user/project.git", "project"),
            ("ssh://git@github.com/user/repo", "repo"),
            ("http://example.com/lib", "lib"),
            ("https://github.com/user/repo/", "repo"),
        ],
    )
    def test_sync_extract_name_various_urls(self, source: str, expected: str) -> None:
        assert _extract_dep_name(source) == expected

    @pytest.mark.parametrize(
        "source",
        [
            "https://github.com/",
            "https://github.com",
            "git@github.com:user/.git",
            "https://github.com/user/..",
            "git@github.com:user/..",
        ],
    )
    def test_sync_extract_name_raises_value_error(self, source: str) -> None:
        with pytest.raises(ValueError, match="Cannot extract dependency name"):
            _extract_dep_name(source)

    def test_sync_extract_name_raises_value_error_for_git_at_without_colon(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract dependency name"):
            _extract_dep_name("git@something-without-colon")


class TestPrepareCloneUrl:
    @pytest.mark.parametrize(
        ("source", "token", "expected_in_url"),
        [
            ("https://github.com/user/repo", "ghp_xxx", "ghp_xxx@"),
            ("https://github.com/user/repo", None, "github.com/user/repo"),
            ("http://github.com/user/repo", "ghp_xxx", "http://github.com"),
            ("git@github.com:user/repo.git", "ghp_xxx", "git@github.com"),
        ],
    )
    def test_sync_prepare_clone_url_variants(self, source: str, token: str | None, expected_in_url: str) -> None:
        result = _prepare_clone_url(source, token)
        assert expected_in_url in result

    @pytest.mark.parametrize(
        ("source", "token"),
        [
            ("ssh://git@github.com/user/repo", "ghp_xxx"),
            ("git@github.com:user/repo.git", "ghp_xxx"),
            ("http://github.com/user/repo", "ghp_xxx"),
        ],
    )
    def test_sync_prepare_clone_url_does_not_inject_token_for_non_https(self, source: str, token: str) -> None:
        result = _prepare_clone_url(source, token)
        assert result == source
        assert token not in result

    def test_sync_prepare_clone_url_strips_existing_credentials(self) -> None:
        result = _prepare_clone_url("https://old_token@github.com/user/repo.git", "ghp_new")
        assert "ghp_new@" in result
        assert "old_token" not in result
        assert result == "https://ghp_new@github.com/user/repo.git"


class TestSyncLocal:
    def test_sync_local_path_syncs_usages(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_path / "my-lib"
        source.mkdir()
        (source / ".usages").mkdir()
        (source / ".usages" / "api.md").write_text("# API", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(sync, [str(source)])

        assert result.exit_code == 0
        assert "Synced my-lib" in result.output
        assert (tmp_path / ".goga" / "usages" / "deps" / "my-lib" / ".usages" / "api.md").read_text(
            encoding="utf-8"
        ) == "# API"

    def test_sync_local_multiple_usages_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / ".usages").mkdir()
        (project / ".usages" / "root.md").write_text("# Root", encoding="utf-8")
        sub = project / "sub"
        sub.mkdir()
        (sub / ".usages").mkdir()
        (sub / ".usages" / "sub.md").write_text("# Sub", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(sync, [str(project)])

        assert result.exit_code == 0
        assert "2 usages" in result.output
        assert (tmp_path / ".goga" / "usages" / "deps" / "project" / ".usages" / "root.md").exists()
        assert (tmp_path / ".goga" / "usages" / "deps" / "project" / "sub" / ".usages" / "sub.md").exists()

    def test_sync_local_path_not_exists(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(sync, [str(tmp_path / "nonexistent")])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_sync_local_no_usages_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "empty-lib"
        source.mkdir()
        runner = CliRunner()
        result = runner.invoke(sync, [str(source)])

        assert result.exit_code == 1
        assert "No .usages/" in result.output

    def test_sync_local_path_is_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not-a-dir.txt"
        file_path.write_text("hello", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(sync, [str(file_path)])

        assert result.exit_code == 1
        assert "not a directory" in result.output

    def test_sync_local_resolves_relative_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        lib = tmp_path / "my-lib"
        lib.mkdir()
        (lib / ".usages").mkdir()
        (lib / ".usages" / "api.md").write_text("# API", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(sync, ["my-lib"])

        assert result.exit_code == 0
        assert (tmp_path / ".goga" / "usages" / "deps" / "my-lib" / ".usages" / "api.md").exists()

    def test_sync_replaces_existing_dep(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_path / "my-lib"
        source.mkdir()
        usages = source / ".usages"
        usages.mkdir()

        deps = tmp_path / ".goga" / "usages" / "deps" / "my-lib" / ".usages"
        deps.mkdir(parents=True)
        (deps / "v1.md").write_text("# V1", encoding="utf-8")

        (usages / "v2.md").write_text("# V2", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(sync, [str(source)])

        assert result.exit_code == 0
        assert not (deps / "v1.md").exists()
        assert (deps / "v2.md").read_text(encoding="utf-8") == "# V2"

    def test_sync_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_path / "my-lib"
        source.mkdir()
        (source / ".usages").mkdir()
        (source / ".usages" / "api.md").write_text("# API", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        result1 = runner.invoke(sync, [str(source)])
        result2 = runner.invoke(sync, [str(source)])

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        content = (tmp_path / ".goga" / "usages" / "deps" / "my-lib" / ".usages" / "api.md").read_text(encoding="utf-8")
        assert content == "# API"

    def test_sync_local_empty_usages_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_path / "my-lib"
        source.mkdir()
        (source / ".usages").mkdir()

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(sync, [str(source)])

        assert result.exit_code == 0
        assert "1 usages" in result.output
        assert (tmp_path / ".goga" / "usages" / "deps" / "my-lib" / ".usages").is_dir()

    def test_sync_local_root_path_gives_empty_dep_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir("/")
        runner = CliRunner()
        result = runner.invoke(sync, ["/"])

        assert result.exit_code == 1
        assert "Cannot extract dependency name" in result.output

    def test_sync_local_os_error_during_copy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = tmp_path / "my-lib"
        source.mkdir()
        (source / ".usages").mkdir()

        monkeypatch.chdir(tmp_path)

        with mock.patch("shutil.copytree", side_effect=OSError("Permission denied")):
            runner = CliRunner()
            result = runner.invoke(sync, [str(source)])

        assert result.exit_code == 1
        assert "Sync failed" in result.output


class TestSyncGit:
    def test_sync_git_https_clones_and_syncs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".usages").mkdir()
        (repo / ".usages" / "api.md").write_text("# API", encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        clone_dirs: list[str] = []

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            clone_dirs.append(str(d))
            return str(d)

        def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            clone_dir = cmd[-1]
            shutil.copytree(str(repo), clone_dir, dirs_exist_ok=True)
            return mock.MagicMock()

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/user/repo.git"])

        assert result.exit_code == 0
        assert "Synced repo" in result.output
        assert (tmp_path / ".goga" / "usages" / "deps" / "repo" / ".usages" / "api.md").read_text(
            encoding="utf-8"
        ) == "# API"

    def test_sync_git_with_token_and_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".usages").mkdir()
        (repo / ".usages" / "api.md").write_text("# API", encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        captured_cmd: list[str] = []

        def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            captured_cmd.extend(cmd)
            clone_dir = cmd[-1]
            shutil.copytree(str(repo), clone_dir, dirs_exist_ok=True)
            return mock.MagicMock()

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/user/repo.git", "--token", "ghp_xxx", "--branch", "v2.0"])

        assert result.exit_code == 0
        assert "--branch" in captured_cmd
        assert "v2.0" in captured_cmd
        clone_idx = captured_cmd.index("clone")
        for arg in captured_cmd[clone_idx + 1 :]:
            if arg.startswith("https://"):
                url = arg
                break
        else:
            url = ""
        assert "ghp_xxx@" in url

    def test_sync_git_clone_fails(self, tmp_path: Path) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> None:
            err = subprocess.CalledProcessError(1, cmd)
            err.stderr = b"fatal: repository not found"
            raise err

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/user/bad-repo.git"])

        assert result.exit_code == 1
        assert "fatal:" in result.output

    def test_sync_git_clone_fails_token_not_leaked(self, tmp_path: Path) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> None:
            err = subprocess.CalledProcessError(1, cmd)
            err.stderr = b"fatal: unable to access 'https://ghp_secret@github.com/user/repo.git/'"
            raise err

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/user/repo.git", "--token", "ghp_secret"])

        assert result.exit_code == 1
        assert "ghp_secret" not in result.output
        assert "<TOKEN>" in result.output
        assert "fatal:" in result.output

    def test_sync_git_not_installed(self, tmp_path: Path) -> None:
        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch(
                "subprocess.run",
                side_effect=FileNotFoundError("git not found"),
            ),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/user/repo.git"])

        assert result.exit_code == 1
        assert "git" in result.output

    def test_sync_git_no_usages_in_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()

        monkeypatch.chdir(tmp_path)

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            clone_dir = cmd[-1]
            shutil.copytree(str(repo), clone_dir, dirs_exist_ok=True)
            return mock.MagicMock()

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/user/repo.git"])

        assert result.exit_code == 1
        assert "No .usages/" in result.output

    def test_sync_ssh_url_ignores_token(self, tmp_path: Path) -> None:
        captured_cmd: list[str] = []

        def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            captured_cmd.extend(cmd)
            return mock.MagicMock()

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            runner.invoke(sync, ["git@github.com:user/repo.git", "--token", "ghp_xxx"])

        url = captured_cmd[captured_cmd.index("clone") + 1]
        assert "ghp_xxx" not in url

    def test_sync_git_terminal_prompt_disabled(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".usages").mkdir()

        captured_env: dict[str, str] = {}

        def fake_mkdtemp() -> str:
            d = tmp_path / "tmp_clone"
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            if "env" in kwargs:
                captured_env.update(kwargs["env"])  # type: ignore[arg-type]
            clone_dir = cmd[-1]
            shutil.copytree(str(repo), clone_dir, dirs_exist_ok=True)
            return mock.MagicMock()

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree"),
        ):
            runner = CliRunner()
            runner.invoke(sync, ["https://github.com/user/repo.git"])

        assert "GIT_TERMINAL_PROMPT" in captured_env
        assert captured_env["GIT_TERMINAL_PROMPT"] == "0"

    def test_sync_tmp_dir_cleaned_up_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".usages").mkdir()

        monkeypatch.chdir(tmp_path)
        tmp_dir_path = tmp_path / "tmp_clone"

        def fake_mkdtemp() -> str:
            tmp_dir_path.mkdir(parents=True, exist_ok=True)
            return str(tmp_dir_path)

        def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            clone_dir = cmd[-1]
            shutil.copytree(str(repo), clone_dir, dirs_exist_ok=True)
            return mock.MagicMock()

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch("subprocess.run", side_effect=fake_run),
            mock.patch("shutil.rmtree") as mock_rmtree,
        ):
            runner = CliRunner()
            runner.invoke(sync, ["https://github.com/user/repo.git"])

        mock_rmtree.assert_any_call(tmp_dir_path, ignore_errors=True)

    def test_sync_tmp_dir_cleaned_up_on_failure(self, tmp_path: Path) -> None:
        tmp_dir_path = tmp_path / "tmp_clone"

        def fake_mkdtemp() -> str:
            tmp_dir_path.mkdir(parents=True, exist_ok=True)
            return str(tmp_dir_path)

        with (
            mock.patch("tempfile.mkdtemp", side_effect=fake_mkdtemp),
            mock.patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["git"]),
            ),
            mock.patch("shutil.rmtree") as mock_rmtree,
        ):
            runner = CliRunner()
            runner.invoke(sync, ["https://github.com/user/repo.git"])

        mock_rmtree.assert_called_once_with(tmp_dir_path, ignore_errors=True)

    def test_sync_git_invalid_url_no_dep_name(self, tmp_path: Path) -> None:
        with (
            mock.patch("shutil.rmtree") as mock_rmtree,
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["https://github.com/"])

        assert result.exit_code == 1
        assert "Cannot extract dependency name" in result.output
        mock_rmtree.assert_not_called()

    def test_sync_git_malformed_git_at_url(self, tmp_path: Path) -> None:
        with (
            mock.patch("shutil.rmtree") as mock_rmtree,
        ):
            runner = CliRunner()
            result = runner.invoke(sync, ["git@no-colon-here"])

        assert result.exit_code == 1
        assert "Cannot extract dependency name" in result.output
        mock_rmtree.assert_not_called()

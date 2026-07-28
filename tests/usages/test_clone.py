# tests/usages/test_clone.py — contract and logic tests for clone_repository

import inspect
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from goga.usages.sync.clone import clone_repository

# --- Contract tests ---


class TestCloneRepositoryContract:
    def test_importable_from_goga_usages_clone(self):
        """clone_repository is importable from goga.usages.sync.clone."""
        assert callable(clone_repository)

    def test_signature(self):
        """Signature is clone_repository(git: str, ref: str | None) -> Path."""
        sig = inspect.signature(clone_repository)

        params = list(sig.parameters)
        assert params == ["git", "ref"]

        assert sig.parameters["git"].annotation is str
        assert sig.parameters["ref"].annotation == (str | None)
        assert sig.parameters["ref"].default is inspect.Parameter.empty
        assert sig.return_annotation is Path


# --- Logic tests ---


class TestCloneRepositoryLogic:
    def test_clone_repository_invokes_git_and_returns_path(self, tmp_path):
        """Clone + checkout ref: two subprocess calls; GIT_TERMINAL_PROMPT=0; -C <tmp>."""
        clone_target = tmp_path / "clone"

        with (
            mock.patch("goga.usages.sync.clone.subprocess.run") as run_mock,
            mock.patch(
                "goga.usages.sync.clone.tempfile.mkdtemp",
                return_value=str(clone_target),
            ) as mkdtemp_mock,
        ):
            result = clone_repository("https://x/r.git", "main")

        assert isinstance(result, Path)
        assert result == clone_target
        mkdtemp_mock.assert_called_once()

        assert run_mock.call_count == 2

        # first call: git clone <url> <tmp> with GIT_TERMINAL_PROMPT=0
        first_args = run_mock.call_args_list[0].args[0]
        assert first_args[:2] == ["git", "clone"]
        assert first_args[2] == "https://x/r.git"
        assert first_args[3] == str(clone_target)
        assert run_mock.call_args_list[0].kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert run_mock.call_args_list[0].kwargs["check"] is True
        assert run_mock.call_args_list[0].kwargs["capture_output"] is True

        # second call: git -C <tmp> checkout <ref>
        assert run_mock.call_args_list[1].args[0][0] == "git"
        assert run_mock.call_args_list[1].args[0][1:3] == ["-C", str(clone_target)]
        assert run_mock.call_args_list[1].args[0][4] == "main"
        assert run_mock.call_args_list[1].kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_clone_repository_no_ref_skips_checkout(self, tmp_path):
        """ref=None → only the clone call; no checkout."""
        clone_target = tmp_path / "clone"

        with (
            mock.patch("goga.usages.sync.clone.subprocess.run") as run_mock,
            mock.patch(
                "goga.usages.sync.clone.tempfile.mkdtemp",
                return_value=str(clone_target),
            ),
        ):
            result = clone_repository("https://x/r.git", None)

        assert result == clone_target
        assert run_mock.call_count == 1
        assert run_mock.call_args_list[0].args[0][:2] == ["git", "clone"]
        assert run_mock.call_args_list[0].kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_clone_repository_propagates_git_missing(self, tmp_path):
        """FileNotFoundError (git binary missing) propagates; temp dir is removed."""
        clone_target = tmp_path / "clone"
        clone_target.mkdir()

        with (
            mock.patch(
                "goga.usages.sync.clone.subprocess.run",
                side_effect=FileNotFoundError,
            ),
            mock.patch(
                "goga.usages.sync.clone.tempfile.mkdtemp",
                return_value=str(clone_target),
            ),
            pytest.raises(FileNotFoundError),
        ):
            clone_repository("https://x/r.git", "main")

        # the temp dir this routine created is cleaned up on failure (no leak)
        assert not clone_target.exists()

    def test_clone_repository_propagates_called_process_error(self, tmp_path):
        """CalledProcessError (git exits non-zero) propagates; temp dir is removed."""
        clone_target = tmp_path / "clone"
        clone_target.mkdir()

        with (
            mock.patch(
                "goga.usages.sync.clone.subprocess.run",
                side_effect=subprocess.CalledProcessError(128, ["git", "clone", "https://x/r.git", str(clone_target)]),
            ),
            mock.patch(
                "goga.usages.sync.clone.tempfile.mkdtemp",
                return_value=str(clone_target),
            ),
            pytest.raises(subprocess.CalledProcessError),
        ):
            clone_repository("https://x/r.git", "main")

        assert not clone_target.exists()

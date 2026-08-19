from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
from goga.build import build
from goga.config import load_project_config


def _write_config(
    tmp_path: Path,
    *,
    agent: str = "claude",
    codex_review: bool | None = None,
    prompts_dir: str | None = None,
) -> None:
    """Materialize a .goga/config.yml under tmp_path with the requested schema."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "language: python",
        "image: goga:latest",
        "pipeline:",
        "  agent: claude",
        "build:",
        "  task_executor:",
        f"    agent: {agent}",
    ]
    if codex_review is not None:
        lines.append(f"  codex_review: {str(codex_review).lower()}")
    if prompts_dir is not None:
        lines.append(f"  prompts_dir: {prompts_dir}")

    (goga_dir / "config.yml").write_text("\n".join(lines) + "\n")


@contextmanager
def _mock_vendored_sources(tmp_path: Path):
    """Point the vendored ralphex defaults at synthetic tmp sources (external boundary)."""
    from goga.build import ralphex_runtime

    prompts_dir = tmp_path / "vendored-prompts"
    agents_dir = tmp_path / "vendored-agents"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "task.txt").write_text("# task prompt\n")
    (prompts_dir / "codex.txt").write_text("# codex review prompt\n")
    (prompts_dir / "review_first.txt").write_text("# first review prompt\n")
    (prompts_dir / "review_second.txt").write_text("# second review prompt\n")
    for role in ("quality", "implementation", "testing", "simplification", "documentation"):
        (agents_dir / f"{role}.txt").write_text(f"# {role} agent definition\n")

    with (
        mock.patch.object(ralphex_runtime, "_VENDORED_PROMPTS", prompts_dir),
        mock.patch.object(ralphex_runtime, "_VENDORED_AGENTS", agents_dir),
    ):
        yield


def _load_config(tmp_path: Path, monkeypatch):
    """Chdir into tmp_path and load the .goga/config.yml written there."""
    monkeypatch.chdir(tmp_path)
    return load_project_config()


def _init_git_repo(path: Path) -> None:
    """Initialize a throwaway git repo so git status works in manifest checks."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )


class TestBuildContract:
    def test_build_importable_from_facade(self) -> None:
        """build() is accessible from the goga.build facade."""
        assert callable(build)


class TestBuildWritesResolvedWrapper:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode", "mythical-agent"])
    def test_build_writes_resolved_wrapper_to_ralphex_config(
        self,
        tmp_path: Path,
        monkeypatch,
        agent: str,
    ) -> None:
        """build() writes the resolved wrapper path into .ralphex/config claude_command.

        Parameterization over arbitrary agent names pins both the absence of a
        whitelist and the absence of branching by agent name.
        """
        _write_config(tmp_path, agent=agent)
        config = _load_config(tmp_path, monkeypatch)
        cli_options = {"dry_run": True, "skip_manifest_check": True}

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            result = build("plan.md", config, cli_options)

        assert result == 0
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert f"claude_command = /home/goga/bin/{agent}-as-claude.sh" in config_text
        assert "claude-wrapper.sh" not in config_text
        assert "codex-wrapper.sh" not in config_text
        assert "codex_enabled = false" in config_text


class TestBuildRejectsUncommittedManifests:
    def test_build_rejects_uncommitted_manifests(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Uncommitted CODEMANIFEST files abort build before .ralphex is created."""
        _init_git_repo(tmp_path)
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        uncommitted_manifest = tmp_path / "goga" / "foo" / "CODEMANIFEST"
        uncommitted_manifest.parent.mkdir(parents=True)
        uncommitted_manifest.write_text("uncommitted")

        _write_config(tmp_path, agent="claude")
        config = _load_config(tmp_path, monkeypatch)
        cli_options = {"skip_manifest_check": False, "dry_run": True}

        result = build("plan.md", config, cli_options)

        assert result == 1
        assert not (tmp_path / ".ralphex").exists()


class TestBuildReturns1WhenRalphexMissing:
    def test_build_returns_1_when_ralphex_missing(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """A missing ralphex binary aborts the pass without invoking subprocess.call."""
        _write_config(tmp_path, agent="claude")
        config = _load_config(tmp_path, monkeypatch)

        def _fail(*args, **kwargs):
            pytest.fail("must not invoke subprocess.call")

        monkeypatch.setattr(subprocess, "call", _fail)
        cli_options = {"dry_run": False, "skip_manifest_check": True}

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=1) as mock_run,
        ):
            result = build("plan.md", config, cli_options)

        assert result == 1
        mock_run.assert_called_once()


class TestBuildMissingCustomPromptsDir:
    def test_build_missing_custom_prompts_dir_returns_1(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """A non-existent custom prompts_dir aborts the run: the sync contract
        requires the source to exist (the old silent skip is superseded)."""
        _write_config(tmp_path, agent="claude", prompts_dir="/nonexistent/prompts-path")
        config = _load_config(tmp_path, monkeypatch)
        cli_options = {"dry_run": True, "skip_manifest_check": True}

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, cli_options)

        assert result == 1
        mock_run.assert_not_called()
        # The failure happens before any .ralphex side effect.
        assert not (tmp_path / ".ralphex" / "prompts").exists()


class TestBuildCodexReviewMapping:
    def test_build_codex_review_maps_to_codex_enabled_true(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """BuildConfig.codex_review=True maps to codex_enabled = true in ralphex config."""
        _write_config(tmp_path, agent="claude", codex_review=True)
        config = _load_config(tmp_path, monkeypatch)
        cli_options = {"dry_run": True, "skip_manifest_check": True}

        with (
            _mock_vendored_sources(tmp_path),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            result = build("plan.md", config, cli_options)

        assert result == 0
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = true" in config_text

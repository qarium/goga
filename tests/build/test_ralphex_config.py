from __future__ import annotations

import inspect
import typing

import pytest
from goga.build.ralphex_config import write_ralphex_config
from goga.config import BuildConfig, TaskExecutorConfig


def _make_build_config(**kwargs) -> BuildConfig:
    task_executor = TaskExecutorConfig(agent=kwargs.pop("agent", "claude"), env={})
    return BuildConfig(task_executor=task_executor, **kwargs)


class TestWriteRalphexConfigContract:
    def test_write_ralphex_config_importable_from_module(self) -> None:
        assert callable(write_ralphex_config)

    def test_write_ralphex_config_has_correct_signature(self) -> None:
        sig = inspect.signature(write_ralphex_config)
        params = list(sig.parameters.keys())
        assert params == ["config", "wrapper_path"]

    def test_write_ralphex_config_config_param_type(self) -> None:
        from goga.config import BuildConfig

        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["config"] is BuildConfig

    def test_write_ralphex_config_wrapper_path_param_is_str(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["wrapper_path"] is str

    def test_write_ralphex_config_returns_none(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["return"] is type(None)

    def test_default_claude_args_constant_moved_to_module(self) -> None:
        from goga.build.ralphex_config import _DEFAULT_CLAUDE_ARGS

        assert _DEFAULT_CLAUDE_ARGS == "--dangerously-skip-permissions --output-format stream-json --verbose"


class TestWriteRalphexConfigLogic:
    def test_write_ralphex_config_writes_all_five_keys(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config(codex_review=True)

        write_ralphex_config(config, "/home/goga/bin/codex-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert "claude_args = --dangerously-skip-permissions --output-format stream-json --verbose" in config_text
        assert "codex_enabled = true" in config_text
        assert "preserve_anthropic_api_key = true" in config_text
        assert "move_plan_on_completion = false" in config_text

    def test_write_ralphex_config_fixed_key_order(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        keys = [line.split(" = ", 1)[0] for line in config_text.strip().splitlines() if " = " in line]
        assert keys == [
            "claude_command",
            "claude_args",
            "codex_enabled",
            "preserve_anthropic_api_key",
            "move_plan_on_completion",
        ]

    def test_write_ralphex_config_creates_ralphex_dir_when_missing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        assert (tmp_path / ".ralphex" / "config").is_file()

    def test_write_ralphex_config_file_ends_with_newline(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert config_text.endswith("\n")

    def test_write_ralphex_config_codex_false_default(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config(codex_review=None)

        write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in config_text

    def test_write_ralphex_config_second_call_rewrites(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")
        write_ralphex_config(config, "/home/goga/bin/codex-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" not in config_text

    def test_write_ralphex_config_accepts_project_config_build(self, tmp_path, monkeypatch) -> None:
        """The orchestrator passes `config.build` — a BuildConfig, not ProjectConfig."""
        monkeypatch.chdir(tmp_path)
        from goga.config import PipelineConfig, ProjectConfig

        project = ProjectConfig(
            lang="python",
            image="goga:latest",
            dockerfile=None,
            build=_make_build_config(),
            pipeline=PipelineConfig(agent="claude"),
        )

        write_ralphex_config(project.build, "/home/goga/bin/claude-as-claude.sh")

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" in config_text

    def test_write_ralphex_config_does_not_write_prompts_or_agents(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

        entries = {p.name for p in (tmp_path / ".ralphex").iterdir()}
        assert entries == {"config"}


@pytest.mark.parametrize(
    ("codex_review", "expected"),
    [(True, "true"), (False, "false"), (None, "false")],
)
def test_write_ralphex_config_codex_enabled_matrix(tmp_path, monkeypatch, codex_review, expected) -> None:
    monkeypatch.chdir(tmp_path)
    config = _make_build_config(codex_review=codex_review)

    write_ralphex_config(config, "/home/goga/bin/claude-as-claude.sh")

    config_text = (tmp_path / ".ralphex" / "config").read_text()
    assert f"codex_enabled = {expected}" in config_text

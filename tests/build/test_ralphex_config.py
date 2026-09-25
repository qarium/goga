from __future__ import annotations

import inspect
import typing
from pathlib import Path

import pytest
from goga.build.ralphex_config import write_ralphex_config
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig

WRAPPER_PATCH_TARGET = "goga.build.ralphex_config.resolve_wrapper_path"

WRAPPER = "/home/goga/bin/claude-as-claude.sh"


def _make_settings(
    strategy: str = "medium",
    additional_agent: str | None = None,
    finalize: str | None = None,
) -> RunSettings:
    """Baseline run plan; each scenario changes exactly the keys derived from it."""
    return RunSettings(
        skip=False,
        tasks=PassSettings(agent="claude", env={}),
        review=ReviewPassSettings(
            agent="claude",
            env={},
            strategy=strategy,
            finalize=finalize,
            additional=AdditionalReviewConfig(agent=additional_agent, patience=None, max_iterations=None),
        ),
    )


def _patch_additional_wrapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Patch wrapper resolution at its import point; every agent maps to one fixed tmp file."""
    additional_wrapper = tmp_path / "codex-as-claude.sh"
    additional_wrapper.write_text("#!/bin/sh\n")

    monkeypatch.setattr(WRAPPER_PATCH_TARGET, lambda _agent: str(additional_wrapper))
    return str(additional_wrapper)


class TestWriteRalphexConfigContract:
    def test_write_ralphex_config_importable_from_module(self) -> None:
        assert callable(write_ralphex_config)

    def test_write_ralphex_config_has_correct_signature(self) -> None:
        sig = inspect.signature(write_ralphex_config)
        params = list(sig.parameters.keys())
        assert params == ["settings", "wrapper_path"]

    def test_write_ralphex_config_settings_param_type(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["settings"] is RunSettings

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
    def test_write_ralphex_config_strategies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The strategy table: medium disables the external review; full with an additional
        agent routes it to the custom script; finalize gates the finalize flag."""
        monkeypatch.chdir(tmp_path)
        additional_wrapper = _patch_additional_wrapper(tmp_path, monkeypatch)

        write_ralphex_config(_make_settings(strategy="medium"), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in text
        assert "external_review_tool" not in text
        assert "custom_review_script" not in text
        assert "finalize_enabled" not in text

        write_ralphex_config(_make_settings(strategy="full", additional_agent="codex"), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "external_review_tool = custom" in text
        assert f"custom_review_script = {additional_wrapper}" in text
        assert "codex_enabled" not in text

        write_ralphex_config(_make_settings(finalize="Final pass: merge the review."), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "finalize_enabled = true" in text

        assert "move_plan_on_completion = false" in text
        assert "preserve_anthropic_api_key = true" in text
        assert f"claude_command = {WRAPPER}" in text

    def test_write_ralphex_config_short_with_additional_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Short engages the external review the same way as full."""
        monkeypatch.chdir(tmp_path)
        additional_wrapper = _patch_additional_wrapper(tmp_path, monkeypatch)

        write_ralphex_config(_make_settings(strategy="short", additional_agent="codex"), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "external_review_tool = custom" in text
        assert f"custom_review_script = {additional_wrapper}" in text
        assert "codex_enabled" not in text

    def test_write_ralphex_config_degenerate_additional_agent_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A None additional agent leaves both external keys unwritten — the ralphex default
        (codex) stays in force."""
        monkeypatch.chdir(tmp_path)
        _patch_additional_wrapper(tmp_path, monkeypatch)

        write_ralphex_config(_make_settings(strategy="full", additional_agent=None), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "external_review_tool" not in text
        assert "custom_review_script" not in text
        assert "codex_enabled" not in text

    def test_write_ralphex_config_medium_ignores_additional_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even a set additional agent writes no external key under medium — the surface is
        explicitly disabled there."""
        monkeypatch.chdir(tmp_path)
        _patch_additional_wrapper(tmp_path, monkeypatch)

        write_ralphex_config(_make_settings(strategy="medium", additional_agent="codex"), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in text
        assert "external_review_tool" not in text
        assert "custom_review_script" not in text

    def test_write_ralphex_config_fixed_key_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fixed block leads; the conditional keys follow in trace order."""
        monkeypatch.chdir(tmp_path)
        _patch_additional_wrapper(tmp_path, monkeypatch)

        settings = _make_settings(strategy="full", additional_agent="codex", finalize="Done.")
        write_ralphex_config(settings, WRAPPER)

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        keys = [line.split(" = ", 1)[0] for line in config_text.strip().splitlines() if " = " in line]
        assert keys == [
            "claude_command",
            "claude_args",
            "preserve_anthropic_api_key",
            "move_plan_on_completion",
            "external_review_tool",
            "custom_review_script",
            "finalize_enabled",
        ]

    def test_write_ralphex_config_medium_key_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The medium shape: the fixed block plus the explicit codex_enabled = false."""
        monkeypatch.chdir(tmp_path)

        write_ralphex_config(_make_settings(strategy="medium"), WRAPPER)

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        keys = [line.split(" = ", 1)[0] for line in config_text.strip().splitlines() if " = " in line]
        assert keys == [
            "claude_command",
            "claude_args",
            "preserve_anthropic_api_key",
            "move_plan_on_completion",
            "codex_enabled",
        ]

    def test_write_ralphex_config_creates_ralphex_dir_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        write_ralphex_config(_make_settings(), WRAPPER)

        assert (tmp_path / ".ralphex" / "config").is_file()

    def test_write_ralphex_config_file_ends_with_newline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        write_ralphex_config(_make_settings(), WRAPPER)

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert config_text.endswith("\n")

    def test_write_ralphex_config_second_call_rewrites_whole(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A two-pass run calls this twice with the same settings and a different wrapper —
        the file is rewritten whole, never merged into: the old wrapper and the old
        strategy-conditional keys are gone."""
        monkeypatch.chdir(tmp_path)
        _patch_additional_wrapper(tmp_path, monkeypatch)

        write_ralphex_config(_make_settings(strategy="medium"), WRAPPER)
        write_ralphex_config(
            _make_settings(strategy="full", additional_agent="codex"),
            "/home/goga/bin/codex-as-claude.sh",
        )

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert f"claude_command = {WRAPPER}" not in config_text
        assert "codex_enabled" not in config_text

    def test_write_ralphex_config_does_not_write_prompts_or_agents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only the config file is this routine's artifact — prompts/agents belong to the
        defaults sync."""
        monkeypatch.chdir(tmp_path)

        write_ralphex_config(_make_settings(), WRAPPER)

        entries = {p.name for p in (tmp_path / ".ralphex").iterdir()}
        assert entries == {"config"}

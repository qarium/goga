from __future__ import annotations

import inspect
import typing
from pathlib import Path

import pytest
from goga.build.ralphex_config import write_ralphex_config
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig

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


def _additional_wrapper(tmp_path: Path) -> str:
    """The generated additional-role closure path, as write_role_env_wrappers returns it."""
    additional_wrapper = tmp_path / "goga-build-env" / "additional.sh"
    additional_wrapper.parent.mkdir(parents=True, exist_ok=True)
    additional_wrapper.write_text("#!/bin/sh\n")

    return str(additional_wrapper)


class TestWriteRalphexConfigContract:
    def test_write_ralphex_config_importable_from_module(self) -> None:
        assert callable(write_ralphex_config)

    def test_write_ralphex_config_has_correct_signature(self) -> None:
        sig = inspect.signature(write_ralphex_config)
        params = list(sig.parameters.keys())
        assert params == ["settings", "wrapper_path", "additional_wrapper_path"]
        assert sig.parameters["additional_wrapper_path"].default is None

    def test_write_ralphex_config_settings_param_type(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["settings"] is RunSettings

    def test_write_ralphex_config_wrapper_path_param_is_str(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["wrapper_path"] is str

    def test_write_ralphex_config_additional_wrapper_path_param_type(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["additional_wrapper_path"] == str | None

    def test_write_ralphex_config_returns_none(self) -> None:
        hints = typing.get_type_hints(write_ralphex_config)
        assert hints["return"] is type(None)

    def test_default_claude_args_constant_moved_to_module(self) -> None:
        from goga.build.ralphex_config import _DEFAULT_CLAUDE_ARGS

        assert _DEFAULT_CLAUDE_ARGS == "--dangerously-skip-permissions --output-format stream-json --verbose"

    def test_module_resolves_no_wrapper_paths(self) -> None:
        """The wrapper targets arrive resolved — the routine never resolves an
        agent itself (that moved to write_role_env_wrappers)."""
        import goga.build.ralphex_config as module

        assert "resolve_wrapper_path" not in dir(module)


class TestWriteRalphexConfigLogic:
    @pytest.mark.parametrize(
        ("strategy", "with_wrapper", "finalize", "expected_keys", "absent_keys", "custom_script"),
        [
            pytest.param(
                "medium",
                True,
                None,
                ("codex_enabled = false",),
                ("external_review_tool", "custom_review_script", "finalize_enabled"),
                False,
                id="medium-disables-the-external-review",
            ),
            pytest.param(
                "full",
                True,
                None,
                ("external_review_tool = custom",),
                ("codex_enabled",),
                True,
                id="full-routes-the-additional-wrapper",
            ),
            pytest.param(
                "full",
                False,
                None,
                (),
                ("codex_enabled", "external_review_tool", "custom_review_script"),
                False,
                id="full-without-wrapper-keeps-the-ralphex-default",
            ),
            pytest.param(
                "medium",
                False,
                "Final pass: merge the review.",
                ("finalize_enabled = true", "codex_enabled = false"),
                (),
                False,
                id="finalize-gates-the-finalize-flag",
            ),
        ],
    )
    def test_write_ralphex_config_strategies(  # noqa: PLR0913, PLR0917 — the parametrized strategy columns
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
        with_wrapper: bool,
        finalize: str | None,
        expected_keys: tuple[str, ...],
        absent_keys: tuple[str, ...],
        custom_script: bool,
    ) -> None:
        """The strategy state table: medium disables the external review; full/short with
        an additional wrapper routes it to the custom script; no wrapper keeps the ralphex
        default; finalize gates the finalize flag."""
        monkeypatch.chdir(tmp_path)
        additional_wrapper = _additional_wrapper(tmp_path) if with_wrapper else None

        settings = _make_settings(strategy=strategy, finalize=finalize)
        write_ralphex_config(settings, WRAPPER, additional_wrapper)

        text = (tmp_path / ".ralphex" / "config").read_text()
        for expected in expected_keys:
            assert expected in text

        for absent in absent_keys:
            assert absent not in text

        if custom_script:
            assert f"custom_review_script = {additional_wrapper}" in text

        assert "move_plan_on_completion = false" in text
        assert "preserve_anthropic_api_key = true" in text
        assert f"claude_command = {WRAPPER}" in text

    def test_write_ralphex_config_short_with_additional_wrapper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Short engages the external review the same way as full."""
        monkeypatch.chdir(tmp_path)
        additional_wrapper = _additional_wrapper(tmp_path)

        write_ralphex_config(_make_settings(strategy="short"), WRAPPER, additional_wrapper)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "external_review_tool = custom" in text
        assert f"custom_review_script = {additional_wrapper}" in text
        assert "codex_enabled" not in text

    def test_write_ralphex_config_none_wrapper_leaves_ralphex_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A None additional wrapper path leaves both external keys unwritten — the
        ralphex default (codex) stays in force, even with an additional agent set."""
        monkeypatch.chdir(tmp_path)

        write_ralphex_config(_make_settings(strategy="full", additional_agent="codex"), WRAPPER)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "external_review_tool" not in text
        assert "custom_review_script" not in text
        assert "codex_enabled" not in text

    def test_write_ralphex_config_medium_ignores_additional_wrapper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even a given additional wrapper writes no external key under medium — the
        surface is explicitly disabled there."""
        monkeypatch.chdir(tmp_path)
        additional_wrapper = _additional_wrapper(tmp_path)

        write_ralphex_config(_make_settings(strategy="medium", additional_agent="codex"), WRAPPER, additional_wrapper)

        text = (tmp_path / ".ralphex" / "config").read_text()
        assert "codex_enabled = false" in text
        assert "external_review_tool" not in text
        assert "custom_review_script" not in text

    def test_write_ralphex_config_fixed_key_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The fixed block leads; the conditional keys follow in trace order."""
        monkeypatch.chdir(tmp_path)
        additional_wrapper = _additional_wrapper(tmp_path)

        settings = _make_settings(strategy="full", finalize="Done.")
        write_ralphex_config(settings, WRAPPER, additional_wrapper)

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

    def test_write_ralphex_config_medium_key_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_write_ralphex_config_file_ends_with_newline(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        additional_wrapper = _additional_wrapper(tmp_path)

        write_ralphex_config(_make_settings(strategy="medium"), WRAPPER)
        write_ralphex_config(
            _make_settings(strategy="full"),
            "/home/goga/bin/codex-as-claude.sh",
            additional_wrapper,
        )

        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert f"claude_command = {WRAPPER}" not in config_text
        assert "codex_enabled" not in config_text
        assert f"custom_review_script = {additional_wrapper}" in config_text

    def test_write_ralphex_config_does_not_write_prompts_or_agents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only the config file is this routine's artifact — prompts/agents belong to the
        defaults sync."""
        monkeypatch.chdir(tmp_path)

        write_ralphex_config(_make_settings(), WRAPPER)

        entries = {p.name for p in (tmp_path / ".ralphex").iterdir()}
        assert entries == {"config"}

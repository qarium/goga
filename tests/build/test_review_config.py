from __future__ import annotations

import dataclasses
import inspect
import typing
from pathlib import Path

import pytest
from goga.build.review_config import ROLE_WHITELIST, validate_review_config
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig

WRAPPER_PATCH_TARGET = "goga.build.review_config.resolve_wrapper_path"


def _make_settings(
    agent: str | None = "claude",
    env: dict[str, str] | None = None,
    roles: list[str] | None = None,
    strategy: str = "medium",
    additional_agent: str | None = None,
) -> RunSettings:
    """Clean baseline settings (skip False); each mutation below changes exactly one fact."""
    return RunSettings(
        skip=False,
        tasks=PassSettings(agent="claude", env={}),
        review=ReviewPassSettings(
            agent=agent,
            env=env if env is not None else {},
            roles=roles,
            strategy=strategy,
            additional=AdditionalReviewConfig(agent=additional_agent, patience=None, max_iterations=None),
        ),
    )


MISSING_WRAPPER = "/home/goga/bin/ghost-as-claude.sh"


def _patch_wrapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str) -> None:
    """Patch wrapper resolution: ``existing`` maps to a real tmp file, others to a missing path."""
    wrapper = tmp_path / f"{existing}-as-claude.sh"
    wrapper.write_text("#!/bin/sh\n")

    def fake_resolve(agent: str) -> str:
        return str(wrapper) if agent == existing else MISSING_WRAPPER

    monkeypatch.setattr(WRAPPER_PATCH_TARGET, fake_resolve)


class TestValidateReviewConfigContract:
    def test_validate_review_config_importable_from_module(self) -> None:
        assert callable(validate_review_config)

    def test_validate_review_config_has_correct_signature(self) -> None:
        sig = inspect.signature(validate_review_config)
        params = list(sig.parameters.keys())
        assert params == ["settings"]

    def test_validate_review_config_settings_param_type(self) -> None:
        hints = typing.get_type_hints(validate_review_config)
        assert hints["settings"] is RunSettings

    def test_validate_review_config_returns_none(self) -> None:
        hints = typing.get_type_hints(validate_review_config)
        assert hints["return"] is type(None)

    def test_role_whitelist_is_frozenset_of_five_names(self) -> None:
        assert isinstance(ROLE_WHITELIST, frozenset)
        assert set(ROLE_WHITELIST) == {
            "quality",
            "implementation",
            "testing",
            "simplification",
            "documentation",
        }


class TestValidateReviewConfigLogic:
    def test_validate_review_config_accepts_clean_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A clean resolved plan passes every check — the review wrapper exists via the patch."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(env={"X": "1"}, roles=["quality"])

        assert validate_review_config(settings) is None

    @pytest.mark.parametrize(
        ("settings", "match"),
        [
            pytest.param(_make_settings(roles=["auditor"]), "auditor", id="unknown-role"),
            pytest.param(
                _make_settings(env={"X": "1"}, agent=None),
                r"env requires a review agent",
                id="env-without-agent",
            ),
            pytest.param(
                _make_settings(agent="ghost"),
                r"ghost-as-claude\.sh \(agent 'ghost'\)",
                id="missing-review-wrapper",
            ),
            pytest.param(_make_settings(strategy="fast"), "fast", id="unknown-strategy"),
        ],
    )
    def test_validate_review_config_rejects_bad_fields(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        settings: RunSettings,
        match: str,
    ) -> None:
        """Each mutation raises ValueError naming the invalid value."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        with pytest.raises(ValueError, match=match):
            validate_review_config(settings)

    @pytest.mark.parametrize(
        "settings",
        [
            pytest.param(_make_settings(roles=["auditor"]), id="unknown-role"),
            pytest.param(_make_settings(env={"X": "1"}, agent=None), id="env-without-agent"),
            pytest.param(_make_settings(agent="ghost"), id="missing-review-wrapper"),
            pytest.param(_make_settings(strategy="fast"), id="unknown-strategy"),
        ],
    )
    def test_validate_review_config_skipped_variant_of_every_mutation_returns_none(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        settings: RunSettings,
    ) -> None:
        """A skipped run validates nothing — every mutation returns None under skip=True."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        assert validate_review_config(dataclasses.replace(settings, skip=True)) is None

    def test_validate_review_config_rejects_missing_additional_wrapper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under full with an additional agent, its wrapper is resolved and existence-checked
        the same way — the error names the additional agent and its path."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(strategy="full", additional_agent="codex")

        with pytest.raises(ValueError, match=r"ghost-as-claude\.sh \(agent 'codex'\)"):
            validate_review_config(settings)

        assert validate_review_config(dataclasses.replace(settings, skip=True)) is None

    def test_validate_review_config_no_resolved_agent_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The degenerate in-container case: no agent at all resolved (empty env, so the env
        gate stays silent) — resolve_wrapper_path(None) must never build a nonsense path."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(agent=None, env={})

        with pytest.raises(ValueError, match=r"no review agent resolved: set build\.agent or build\.review\.agent"):
            validate_review_config(settings)

    def test_validate_review_config_env_gate_names_new_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The env gate message points at the live config key build.review.agent."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(env={"X": "1"}, agent=None)

        with pytest.raises(ValueError, match=r"set build\.review\.agent"):
            validate_review_config(settings)

    def test_validate_review_config_medium_never_checks_additional_wrapper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Medium disables the external review — the additional wrapper is never resolved,
        so a missing one passes clean (codex_enabled = false parity)."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(strategy="medium", additional_agent="ghost")

        assert validate_review_config(settings) is None

    def test_validate_review_config_short_with_existing_additional_wrapper_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Short always engages the external review — an existing additional wrapper passes."""
        _patch_wrapper(tmp_path, monkeypatch, existing="codex")

        settings = _make_settings(agent="codex", strategy="short", additional_agent="codex")

        assert validate_review_config(settings) is None

    @pytest.mark.parametrize("roles", [None, []])
    def test_validate_review_config_none_and_empty_roles_no_iteration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roles: list[str] | None
    ) -> None:
        """No declared roles means nothing to check against the whitelist."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        assert validate_review_config(_make_settings(roles=roles)) is None

    def test_validate_review_config_roles_before_env_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The role check runs first — an unknown role raises even when the env gate would too."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(roles=["auditor"], env={"X": "1"}, agent=None)

        with pytest.raises(ValueError, match="auditor"):
            validate_review_config(settings)

    def test_validate_review_config_env_gate_before_wrapper_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The env gate sits between the roles and the wrapper check: env + no agent reports
        the env gate, not the wrapper resolution."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(env={"X": "1"}, agent=None)

        with pytest.raises(ValueError, match=r"env requires a review agent"):
            validate_review_config(settings)

    def test_validate_review_config_review_wrapper_before_additional_wrapper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both wrappers missing under short — the review-agent wrapper is reported first."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(agent="ghost", strategy="short", additional_agent="specter")

        with pytest.raises(ValueError, match=r"ghost-as-claude\.sh \(agent 'ghost'\)"):
            validate_review_config(settings)

    def test_validate_review_config_strategy_check_last(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown strategy never engages the additional-wrapper check (short always,
        full only with an additional agent) — the strategy error is what surfaces."""
        _patch_wrapper(tmp_path, monkeypatch, existing="claude")

        settings = _make_settings(strategy="fast", additional_agent="ghost")

        with pytest.raises(ValueError, match="fast"):
            validate_review_config(settings)

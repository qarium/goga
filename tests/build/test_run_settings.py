"""Contract and logic tests for the entities declared in
``goga/build/CODEMANIFEST`` with ``location: run_settings.py``:

- ``RunSettings(skip, tasks, review)`` — the resolved run plan of a single
  build
- ``PassSettings(agent, env, ...)`` — the resolved tasks-pass part
- ``PassSettings::ReviewPassSettings(...)`` — the resolved review-pass part
  (a concretization of the base pass part)
- ``resolve_run_settings(config, cli_options)`` — the pure resolver applying
  CLI > config > default > omit precedence and root→review inheritance

Supported data only — no mocks, no filesystem: the resolver is a pure
function of the two-part configuration and the CLI options dictionary.
"""

from __future__ import annotations

import dataclasses

from goga.build.run_settings import (
    PassSettings,
    ReviewPassSettings,
    RunSettings,
    resolve_run_settings,
)
from goga.config import AdditionalReviewConfig, BuildConfig, ReviewConfig

from tests.conftest import is_kw_only_dataclass

SETTINGS_TYPES: tuple[type, ...] = (RunSettings, PassSettings, ReviewPassSettings)


def _field_names(cls: type) -> list[str]:
    """Declared field names of ``cls``, inheritance order included."""
    return [field.name for field in dataclasses.fields(cls)]


# --- Contract tests ---


class TestRunSettingsContract:
    def test_resolver_and_value_objects_are_importable(self) -> None:
        """The four names live on the ``goga.build.run_settings`` module."""
        import goga.build.run_settings as module

        for name in ("resolve_run_settings", "RunSettings", "PassSettings", "ReviewPassSettings"):
            assert hasattr(module, name)

    def test_value_objects_are_kw_only_and_frozen(self) -> None:
        """Immutable kw_only value objects per the ``conventions`` practice."""
        for cls in SETTINGS_TYPES:
            assert dataclasses.is_dataclass(cls)
            assert is_kw_only_dataclass(cls)
            assert cls.__dataclass_params__.frozen

    def test_review_pass_settings_is_a_pass_settings_concretization(self) -> None:
        """``ReviewPassSettings`` extends the base pass part, frozen over frozen."""
        assert issubclass(ReviewPassSettings, PassSettings)

    def test_field_sets_match_the_contract(self) -> None:
        """Exact field sets: the run plan triple, the base pass part, the review concretization."""
        assert _field_names(RunSettings) == ["skip", "tasks", "review"]
        assert _field_names(PassSettings) == [
            "agent",
            "env",
            "max_iterations",
            "session_timeout",
            "idle_timeout",
            "wait",
        ]
        assert _field_names(ReviewPassSettings) == [
            "agent",
            "env",
            "max_iterations",
            "session_timeout",
            "idle_timeout",
            "wait",
            "roles",
            "base_ref",
            "strategy",
            "finalize",
            "additional",
        ]


# --- Logic tests ---


class TestResolveRunSettings:
    def test_resolve_run_settings_full_inheritance(self) -> None:
        """Root values flow into the review part; strategy defaults to medium."""
        config = BuildConfig(
            agent="claude",
            env={"A": "1"},
            max_iterations=9,
            session_timeout="30m",
            idle_timeout="5m",
            wait="1m",
            review=ReviewConfig(
                skip=None,
                agent=None,
                env={},
                roles=["quality"],
                base_ref="main",
                strategy=None,
                finalize=None,
                additional=AdditionalReviewConfig(agent=None, patience=3, max_iterations=None),
                session_timeout=None,
                idle_timeout=None,
                wait=None,
            ),
        )

        settings = resolve_run_settings(config, {})

        assert settings.review.agent == "claude"
        assert settings.review.strategy == "medium"
        assert settings.review.additional.agent == "claude"
        assert settings.review.additional.patience == 3
        assert settings.review.env == {}
        assert settings.review.base_ref == "main"

        assert settings.skip is False
        assert settings.tasks.agent == "claude"
        assert settings.tasks.env == {"A": "1"}
        assert settings.tasks.max_iterations == 9
        assert settings.tasks.session_timeout == "30m"
        assert settings.tasks.idle_timeout == "5m"
        assert settings.tasks.wait == "1m"
        assert settings.review.session_timeout == "30m"
        assert settings.review.idle_timeout == "5m"
        assert settings.review.wait == "1m"
        assert settings.review.max_iterations is None
        assert settings.review.roles == ["quality"]
        assert settings.review.finalize is None

    def test_resolve_run_settings_cli_overrides_and_tri_state(self) -> None:
        """CLI wins over config on every knob; the tri-state skip resolves False."""
        config = BuildConfig(
            agent="claude",
            env={},
            max_iterations=5,
            session_timeout="30m",
            review=ReviewConfig(
                skip=True,
                agent="codex",
                session_timeout="10m",
            ),
        )

        settings = resolve_run_settings(config, {"skip_review": False, "session_timeout": "99m"})

        assert settings.skip is False
        assert settings.review.session_timeout == "99m"
        assert settings.review.agent == "codex"
        assert settings.tasks.session_timeout == "99m"
        assert settings.tasks.max_iterations == 5

        unoverridden = resolve_run_settings(config, {})

        assert unoverridden.skip is True
        assert unoverridden.review.session_timeout == "10m"
        assert unoverridden.tasks.session_timeout == "30m"

    def test_resolve_run_settings_review_absent(self) -> None:
        """An absent review part resolves with step-0 semantics; [] travels verbatim."""
        config = BuildConfig(agent="claude", env={}, max_iterations=5, review=None)

        settings = resolve_run_settings(config, {})

        assert settings.review.additional.agent == "claude"
        assert settings.review.additional.patience is None
        assert settings.review.additional.max_iterations is None
        assert settings.review.roles is None
        assert settings.skip is False
        assert settings.review.agent == "claude"
        assert settings.review.env == {}
        assert settings.review.strategy == "medium"

        with_empty_roles = resolve_run_settings(
            BuildConfig(agent="claude", review=ReviewConfig(roles=[])), {}
        )

        assert with_empty_roles.review.roles == []
        assert with_empty_roles.review.additional.agent == "claude"

    def test_resolve_run_settings_base_ref_normalization(self) -> None:
        """A padded CLI base_ref strips; whitespace-only CLI counts as unset."""
        config = BuildConfig(agent="claude", review=ReviewConfig(base_ref="main"))

        padded = resolve_run_settings(config, {"base_ref": "  release/1.3.0  "})

        assert padded.review.base_ref == "release/1.3.0"

        blank = resolve_run_settings(config, {"base_ref": "   "})

        assert blank.review.base_ref == "main"

        absent = resolve_run_settings(config, {})

        assert absent.review.base_ref == "main"

    def test_resolve_run_settings_env_and_patience_precedence(self) -> None:
        """The review env never inherits the root env; patience is CLI > config verbatim."""
        config = BuildConfig(
            agent="claude",
            env={"ROOT": "secret"},
            review=ReviewConfig(
                env={"REVIEW": "layer"},
                additional=AdditionalReviewConfig(agent="cursor", patience=1, max_iterations=4),
            ),
        )

        settings = resolve_run_settings(config, {"review_patience": 0})

        assert settings.tasks.env == {"ROOT": "secret"}
        assert settings.review.env == {"REVIEW": "layer"}
        assert settings.review.additional.agent == "cursor"
        assert settings.review.additional.patience == 0
        assert settings.review.additional.max_iterations == 4

        from_config = resolve_run_settings(config, {})

        assert from_config.review.additional.patience == 1

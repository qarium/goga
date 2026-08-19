from __future__ import annotations

import inspect
import typing
from pathlib import Path

import pytest
from goga.build.review_config import ROLE_WHITELIST, validate_review_config
from goga.build.review_options import ReviewOptions
from goga.config import BuildConfig, TaskExecutorConfig


def _make_build_config(task_agent: str = "claude", **kwargs) -> BuildConfig:
    task_executor = TaskExecutorConfig(agent=task_agent, env={})
    return BuildConfig(task_executor=task_executor, **kwargs)


class TestValidateReviewConfigContract:
    def test_validate_review_config_importable_from_module(self) -> None:
        assert callable(validate_review_config)

    def test_validate_review_config_has_correct_signature(self) -> None:
        sig = inspect.signature(validate_review_config)
        params = list(sig.parameters.keys())
        assert params == ["config", "review"]

    def test_validate_review_config_config_param_type(self) -> None:
        hints = typing.get_type_hints(validate_review_config)
        assert hints["config"] is BuildConfig

    def test_validate_review_config_review_param_type(self) -> None:
        hints = typing.get_type_hints(validate_review_config)
        assert hints["review"] is ReviewOptions

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
    def test_validate_review_config_passes_whitelist_roles(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent=None, roles=["quality", "testing"], two_pass=False)

        validate_review_config(config, review)

    def test_validate_review_config_unknown_role_raises(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent=None, roles=["bogus"], two_pass=False)

        with pytest.raises(ValueError, match="bogus"):
            validate_review_config(config, review)

    def test_validate_review_config_unknown_role_message_lists_whitelist(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent=None, roles=["bogus"], two_pass=False)

        with pytest.raises(ValueError, match=r"quality.*simplification"):
            validate_review_config(config, review)

    def test_validate_review_config_missing_review_wrapper_raises(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent="ghost", roles=None, two_pass=True)

        with pytest.raises(ValueError, match=r"ghost-as-claude\.sh"):
            validate_review_config(config, review)

    def test_validate_review_config_missing_review_wrapper_message_names_agent(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent="ghost", roles=None, two_pass=True)

        with pytest.raises(ValueError, match="ghost"):
            validate_review_config(config, review)

    def test_validate_review_config_existing_wrapper_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wrapper = tmp_path / "codex-as-claude.sh"
        wrapper.write_text("#!/bin/sh\n")
        monkeypatch.setattr("goga.build.review_config.resolve_wrapper_path", lambda _agent: str(wrapper))

        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent="codex", roles=None, two_pass=True)

        validate_review_config(config, review)

    def test_validate_review_config_skipped_run_no_checks(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=True, roles=["bogus"], review_agent="ghost", two_pass=True)

        validate_review_config(config, review)

    @pytest.mark.parametrize("roles", [None, []])
    def test_validate_review_config_none_and_empty_roles_no_iteration(self, roles: list[str] | None) -> None:
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent=None, roles=roles, two_pass=False)

        validate_review_config(config, review)

    def test_validate_review_config_all_whitelist_roles_pass(self) -> None:
        config = _make_build_config()
        review = ReviewOptions(
            skip=False,
            review_agent=None,
            roles=["quality", "implementation", "testing", "simplification", "documentation"],
            two_pass=False,
        )

        validate_review_config(config, review)

    def test_validate_review_config_checks_roles_before_wrapper(self, tmp_path: Path) -> None:
        """The role check runs first — an unknown role raises even when two_pass would also fail."""
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent="ghost", roles=["bogus"], two_pass=True)

        with pytest.raises(ValueError, match="bogus"):
            validate_review_config(config, review)

    def test_validate_review_config_no_two_pass_skips_wrapper_check(self) -> None:
        """two_pass False never resolves the wrapper — the task executor stays out of scope."""
        config = _make_build_config()
        review = ReviewOptions(skip=False, review_agent="ghost", roles=None, two_pass=False)

        validate_review_config(config, review)

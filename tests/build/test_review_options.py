from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest
from goga.build.review_options import ReviewOptions, resolve_review_options
from goga.config import BuildConfig, ReviewExecutorConfig, TaskExecutorConfig


def _make_build_config(**kwargs) -> BuildConfig:
    task_executor = TaskExecutorConfig(agent=kwargs.pop("task_agent", "claude"), env={})
    return BuildConfig(task_executor=task_executor, **kwargs)


class TestReviewOptionsContract:
    def test_both_names_importable_from_module(self) -> None:
        assert callable(resolve_review_options)
        assert inspect.isclass(ReviewOptions)

    def test_resolve_review_options_has_correct_signature(self) -> None:
        sig = inspect.signature(resolve_review_options)
        params = list(sig.parameters.keys())
        assert params == ["config", "cli_options"]

    def test_resolve_review_options_config_param_type(self) -> None:
        hints = typing.get_type_hints(resolve_review_options)
        assert hints["config"] is BuildConfig

    def test_resolve_review_options_cli_options_param_is_dict(self) -> None:
        hints = typing.get_type_hints(resolve_review_options)
        assert hints["cli_options"] is dict

    def test_resolve_review_options_returns_review_options(self) -> None:
        hints = typing.get_type_hints(resolve_review_options)
        assert hints["return"] is ReviewOptions

    def test_review_options_declared_fields(self) -> None:
        fields = {f.name for f in dataclasses.fields(ReviewOptions)}
        assert fields == {"skip", "review_agent", "roles", "two_pass", "review_env", "base_ref", "patience"}

    def test_review_options_field_types(self) -> None:
        hints = typing.get_type_hints(ReviewOptions)
        assert hints["skip"] is bool
        assert hints["review_agent"] == str | None
        assert hints["roles"] == list[str] | None
        assert hints["two_pass"] is bool
        assert hints["review_env"] == dict[str, str]
        assert hints["base_ref"] == str | None
        assert hints["patience"] == int | None

    def test_review_options_declared_fields_include_review_env(self) -> None:
        """`review_env` is the fifth field, required — no default factory."""
        names = [f.name for f in dataclasses.fields(ReviewOptions)]
        assert names == ["skip", "review_agent", "roles", "two_pass", "review_env", "base_ref", "patience"]
        env_field = next(f for f in dataclasses.fields(ReviewOptions) if f.name == "review_env")
        assert env_field.default is dataclasses.MISSING
        assert env_field.default_factory is dataclasses.MISSING

    def test_review_options_is_kw_only_and_frozen(self) -> None:
        """kw_only is enforced: positional construction is rejected."""
        assert ReviewOptions.__dataclass_params__.frozen is True
        with pytest.raises(TypeError):
            ReviewOptions(False, None, None, False, {})  # type: ignore[misc]

    def test_review_options_declares_base_ref_and_patience_fields(self) -> None:
        assert {"base_ref", "patience"} <= set(ReviewOptions.__dataclass_fields__)

    def test_resolve_review_options_docstring_lists_three_keys(self) -> None:
        """The docstring names the three cli_options keys; the old one-key wording is gone."""
        doc = resolve_review_options.__doc__ or ""

        for key in ("skip_review", "base_ref", "review_patience"):
            assert key in doc
        assert "only `skip_review` is read" not in doc


class TestResolveReviewOptionsLogic:
    @pytest.mark.parametrize("cli", [None, True, False])
    @pytest.mark.parametrize("config_skip", [None, True, False])
    def test_resolve_review_options_full_tri_state_matrix(self, cli, config_skip) -> None:
        review_executor = None if config_skip is None else ReviewExecutorConfig(skip=config_skip)
        config = _make_build_config(review_executor=review_executor)

        result = resolve_review_options(config, {"skip_review": cli})

        expected = cli if cli is not None else (config_skip if config_skip is not None else False)
        assert result.skip is expected

    def test_resolve_review_options_cli_overrides_config(self) -> None:
        config = _make_build_config(review_executor=ReviewExecutorConfig(skip=True))

        result = resolve_review_options(config, {"skip_review": False})

        assert result.skip is False

    def test_resolve_review_options_two_pass_when_agents_differ(self) -> None:
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="codex", roles=["quality"]),
        )

        result = resolve_review_options(config, {})

        assert result.two_pass is True
        assert result.review_agent == "codex"
        assert result.roles == ["quality"]
        assert result.skip is False

    def test_resolve_review_options_same_agents_single_pass(self) -> None:
        config = _make_build_config(
            task_agent="claude",
            review_executor=ReviewExecutorConfig(agent="claude"),
        )

        result = resolve_review_options(config, {})

        assert result.two_pass is False

    def test_resolve_review_options_no_review_executor_defaults(self) -> None:
        config = _make_build_config(review_executor=None)

        result = resolve_review_options(config, {})

        assert result == ReviewOptions(skip=False, review_agent=None, roles=None, two_pass=False, review_env={})

    def test_resolve_review_options_empty_roles_verbatim(self) -> None:
        config = _make_build_config(review_executor=ReviewExecutorConfig(roles=[]))

        result = resolve_review_options(config, {})

        assert result.roles == []

    def test_resolve_review_options_two_pass_independent_of_skip(self) -> None:
        config = _make_build_config(
            task_agent="claude",
            review_executor=ReviewExecutorConfig(skip=True, agent="codex"),
        )

        result = resolve_review_options(config, {})

        assert result.two_pass is True
        assert result.skip is True

    def test_review_options_is_frozen(self) -> None:
        options = ReviewOptions(skip=False, review_agent=None, roles=None, two_pass=False, review_env={})

        with pytest.raises(dataclasses.FrozenInstanceError):
            options.skip = True

    def test_resolve_review_options_env_nonempty_same_agent_two_pass(self) -> None:
        """A non-empty review env induces two_pass even when both agents match."""
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", env={"M": "r"}),
        )

        result = resolve_review_options(config, {"skip_review": None})

        assert result.two_pass is True
        assert result.review_agent == "claude"
        assert result.review_env == {"M": "r"}

    def test_resolve_review_options_env_equal_to_task_env_still_two_pass(self) -> None:
        """Induction checks non-emptiness, not dictionary equality with task env."""
        config = BuildConfig(
            task_executor=TaskExecutorConfig(agent="claude", env={"M": "r"}),
            review_executor=ReviewExecutorConfig(agent="claude", env={"M": "r"}),
        )

        result = resolve_review_options(config, {})

        assert result.two_pass is True
        assert result.review_env == {"M": "r"}

    def test_resolve_review_options_env_empty_same_agent_single_pass(self) -> None:
        """An empty review env keeps the single-pass path for matching agents."""
        config = _make_build_config(
            task_agent="claude",
            review_executor=ReviewExecutorConfig(agent="claude", env={}),
        )

        result = resolve_review_options(config, {})

        assert result.two_pass is False
        assert result.review_env == {}

    def test_resolve_review_options_env_without_agent_single_pass(self) -> None:
        """A non-empty env without an agent does NOT induce two_pass — the
        formula requires an agent; the env-without-agent misconfiguration is
        the consumer's gate (validate_review_config), not this reduction."""
        config = _make_build_config(
            task_agent="claude",
            review_executor=ReviewExecutorConfig(env={"X": "y"}),
        )

        result = resolve_review_options(config, {})

        assert result.two_pass is False
        assert result.review_agent is None
        assert result.review_env == {"X": "y"}

    def test_resolve_review_options_base_ref_cli_overrides_config(self) -> None:
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", base_ref="origin/main"),
        )

        result = resolve_review_options(config, {"base_ref": "origin/1.2.x"})

        assert result.base_ref == "origin/1.2.x"

    def test_resolve_review_options_base_ref_from_config_when_cli_absent(self) -> None:
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", base_ref="origin/1.2.x"),
        )

        result = resolve_review_options(config, {})

        assert result.base_ref == "origin/1.2.x"

    def test_resolve_review_options_patience_cli_overrides_config(self) -> None:
        """Pins the naming split: the cli_options KEY is review_patience,
        the ReviewOptions FIELD is patience."""
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", patience=3),
        )

        result = resolve_review_options(config, {"review_patience": 7})

        assert result.patience == 7

    def test_resolve_review_options_base_ref_empty_whitespace_resolves_unset(self) -> None:
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", base_ref="   "),
        )

        result = resolve_review_options(config, {})

        assert result.base_ref is None

    @pytest.mark.parametrize(
        ("config_base_ref", "cli_options"),
        [
            ("  origin/1.2.x  ", {}),
            (None, {"base_ref": " origin/1.2.x "}),
        ],
        ids=["config-source", "cli-source"],
    )
    def test_resolve_review_options_base_ref_padded_value_stripped(self, config_base_ref, cli_options) -> None:
        """Exact equality — an implementation that only checks emptiness
        without assigning the stripped value fails."""
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", base_ref=config_base_ref),
        )

        result = resolve_review_options(config, cli_options)

        assert result.base_ref == "origin/1.2.x"

    def test_resolve_review_options_base_ref_empty_cli_means_unset_not_fallback(self) -> None:
        """An explicitly empty CLI value does NOT fall through to the config."""
        config = _make_build_config(
            review_executor=ReviewExecutorConfig(agent="claude", base_ref="origin/main"),
        )

        result = resolve_review_options(config, {"base_ref": ""})

        assert result.base_ref is None

    def test_resolve_review_options_no_review_executor_leaves_scoped_none(self) -> None:
        config = _make_build_config(review_executor=None)

        result = resolve_review_options(config, {})

        assert result.base_ref is None
        assert result.patience is None

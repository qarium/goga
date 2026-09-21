"""Contract and logic tests for the entity declared in
``goga/build/CODEMANIFEST`` with ``location: pass_options.py``:

- ``compose_pass_options(settings, stage)`` — the pure composer mapping the
  resolved run plan onto the ralphex options of one pass

Supported data only — no mocks, no filesystem: the composer is a pure
function of the resolved ``RunSettings`` and the stage name.
"""

from __future__ import annotations

import dataclasses
import sys

import goga.ralphex  # noqa: F401 — imported for the side effect registering the submodule
import pytest
from goga.build.pass_options import compose_pass_options
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig

# goga.ralphex.run_ralphex is shadowed in the package __init__ by the
# run_ralphex function, so `import goga.ralphex.run_ralphex as ...` returns
# the function, not the module. Resolve the real module via sys.modules —
# the mirror of tests/ralphex/test_run_ralphex.py.
_launcher = sys.modules["goga.ralphex.run_ralphex"]


def _run_settings(
    strategy: str = "medium",
    tasks: PassSettings | None = None,
    base_ref: str | None = None,
    patience: int | None = None,
    additional_max_iterations: int | None = None,
) -> RunSettings:
    """A resolved run plan with the knobs one composition assertion varies."""
    return RunSettings(
        tasks=tasks if tasks is not None else PassSettings(),
        review=ReviewPassSettings(
            strategy=strategy,
            base_ref=base_ref,
            additional=AdditionalReviewConfig(
                agent="claude",
                patience=patience,
                max_iterations=additional_max_iterations,
            ),
        ),
    )


# --- Contract tests ---


class TestComposePassOptionsContract:
    def test_composer_is_importable_from_its_module(self) -> None:
        """``compose_pass_options`` lives on the ``goga.build.pass_options`` module."""
        import goga.build.pass_options as module

        assert hasattr(module, "compose_pass_options")

    def test_composition_returns_a_plain_dict(self) -> None:
        """The composition is a plain ``dict``, not a mapping proxy or subclass."""
        settings = _run_settings()

        assert type(compose_pass_options(settings, "tasks")) is dict
        assert type(compose_pass_options(settings, "review")) is dict

    def test_every_emitted_key_maps_to_a_launcher_flag(self) -> None:
        """The emitted key universe is exactly the ``run_ralphex`` option-table key set."""
        launcher_keys = {key for key, _flag in _launcher._BOOL_FLAGS + _launcher._SCALAR_FLAGS}
        emitted = set()

        for stage in ("tasks", "review"):
            for strategy in ("full", "medium", "short"):
                settings = dataclasses.replace(
                    _run_settings(
                        strategy=strategy,
                        tasks=PassSettings(
                            session_timeout="30m",
                            idle_timeout="5m",
                            wait="1m",
                            max_iterations=9,
                        ),
                        base_ref="main",
                        patience=0,
                        additional_max_iterations=0,
                    ),
                    review=ReviewPassSettings(
                        strategy=strategy,
                        base_ref="main",
                        session_timeout="30m",
                        idle_timeout="5m",
                        wait="1m",
                        additional=AdditionalReviewConfig(agent="claude", patience=0, max_iterations=0),
                    ),
                )

                options = compose_pass_options(settings, stage)

                assert set(options) <= launcher_keys
                emitted |= set(options)

        assert emitted == launcher_keys


# --- Logic tests ---


class TestComposePassOptions:
    def test_compose_pass_options_tasks(self) -> None:
        """The tasks stage carries the mode flag and the resolved tasks knobs only."""
        settings = _run_settings(
            tasks=PassSettings(session_timeout="30m", max_iterations=9),
            base_ref="main",
            patience=0,
        )

        options = compose_pass_options(settings, "tasks")

        assert options == {"tasks_only": True, "session_timeout": "30m", "max_iterations": 9}

    def test_compose_pass_options_review_medium_and_short(self) -> None:
        """The review stage binds its mode flag to the strategy and keeps zero values."""
        settings = dataclasses.replace(
            _run_settings(
                strategy="medium",
                tasks=PassSettings(session_timeout="30m", max_iterations=9),
                base_ref="main",
                patience=0,
            ),
            review=ReviewPassSettings(
                strategy="medium",
                base_ref="main",
                session_timeout="30m",
                additional=AdditionalReviewConfig(agent="claude", patience=0, max_iterations=None),
            ),
        )

        options = compose_pass_options(settings, "review")

        assert options["review"] is True
        assert "external_only" not in options
        assert options["base_ref"] == "main"
        assert options["session_timeout"] == "30m"
        assert options["review_patience"] == 0
        assert "max_external_iterations" not in options
        assert "max_iterations" not in options

        with_external_cap = _run_settings(
            strategy="medium",
            base_ref="main",
            patience=0,
            additional_max_iterations=4,
        )

        assert compose_pass_options(with_external_cap, "review")["max_external_iterations"] == 4

        short = compose_pass_options(_run_settings(strategy="short", base_ref="main", patience=0), "review")

        assert short["external_only"] is True
        assert "review" not in short

    def test_unset_knobs_stay_absent(self) -> None:
        """An all-unset plan composes to exactly one mode flag per stage."""
        settings = _run_settings()

        assert compose_pass_options(settings, "tasks") == {"tasks_only": True}
        assert compose_pass_options(settings, "review") == {"review": True}

    def test_external_zero_values_travel_verbatim(self) -> None:
        """patience 0 and max_external_iterations 0 are meaningful and kept."""
        settings = _run_settings(strategy="short", patience=0, additional_max_iterations=0)

        options = compose_pass_options(settings, "review")

        assert options["review_patience"] == 0
        assert options["max_external_iterations"] == 0

    def test_unknown_stage_raises(self) -> None:
        """A stage outside {tasks, review} is rejected naming the stage."""
        settings = _run_settings()

        with pytest.raises(ValueError, match="unknown build pass stage: combined"):
            compose_pass_options(settings, "combined")

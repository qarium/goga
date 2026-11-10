"""Contract and logic tests for the bridged emission surface declared in
``goga/pipeline/hooks/CODEMANIFEST`` — the two soft methods of
``PipelineHooks``:

- ``emit_run_event(action, context)`` — deliver a caller-built ``RunEvent``
  to the subscribers of a bridged run-level action
- ``emit_stage_event(action, context)`` — deliver a caller-built
  ``StageEvent`` to the subscribers of a bridged stage-level action

Unlike the composed notifications (``emit_run_created`` /
``emit_run_completed``) the bridged methods build no context: the afm
bridge parses the payload and hands the fact bundle over. The delivery
runs for real over the platform boundary fixtures of the zone test
package — the registry, the registrars, and the read-only views execute
the actual platform code.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import pytest
from goga.pipeline.hooks import PipelineHooks, RunEvent, RunIdentity, StageEvent, StageTransition


def _stage_event() -> StageEvent:
    """The stage-level context composed from the design's afm payload facts."""
    return StageEvent(
        pipeline="deploy",
        run=RunIdentity(
            run_id="run-42",
            run_dir="/home/goga/pipeline/runs/run-42",
            root_dir="/workspace",
            resumed=False,
        ),
        stage=StageTransition(
            id="build",
            name="Build",
            from_status="approved",
            to_status="executing",
            phase="execution",
        ),
        event_id="run-42:transition:7: stage_execution_started",
        occurred_at="2026-10-21T12:00:00Z",
    )


def _run_event() -> RunEvent:
    """The run-level context composed from the design's afm payload facts."""
    return RunEvent(
        pipeline="deploy",
        run=RunIdentity(
            run_id="run-42",
            run_dir="/home/goga/pipeline/runs/run-42",
            root_dir="/workspace",
            resumed=True,
        ),
        event_id="run-42:lifecycle:flow_resumed",
        occurred_at="2026-10-21T12:05:00Z",
        reason="operator request",
    )


# --- Contract tests ---


class TestBridgedSurfaceContract:
    def test_bridged_methods_carry_the_declared_signatures(self) -> None:
        """``(action: str, context: RunEvent | StageEvent) -> None`` — one method per context type."""
        run_hints = get_type_hints(PipelineHooks.emit_run_event)
        stage_hints = get_type_hints(PipelineHooks.emit_stage_event)

        assert list(inspect.signature(PipelineHooks.emit_run_event).parameters) == ["self", "action", "context"]
        assert run_hints["action"] is str
        assert run_hints["context"] is RunEvent
        assert run_hints["return"] is type(None)

        assert list(inspect.signature(PipelineHooks.emit_stage_event).parameters) == ["self", "action", "context"]
        assert stage_hints["action"] is str
        assert stage_hints["context"] is StageEvent
        assert stage_hints["return"] is type(None)

    def test_construction_stays_cheap_registry_unset(self) -> None:
        """A fresh surface carries no registry — the build waits for the first emission."""
        assert PipelineHooks()._registry is None


# --- Logic tests — the real platform over the boundary fixtures ---


class TestBridgedEmissions:
    def test_emit_stage_event_delivers_shared_read_only_context(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two tools read one shared context behind per-subscription read-only views.

        ``captured is context`` is asserted nowhere on purpose: the
        subscriber receives the platform's ``_DeliveryProxy``, never the
        raw instance — the shared-instance rule is observable through the
        nested-fact identity. The write probe assigns on the delivered
        view itself: a nested write such as ``context.stage.name = "x"``
        would resolve ``stage`` through the proxy onto the raw dataclass
        and mutate it silently.
        """
        pin_package_environment(
            {"goga_tool_reporter": ["goga-tool-reporter"], "goga_tool_mirror": ["goga-tool-mirror"]}
        )
        delivered: dict[str, object] = {}
        write_errors: dict[str, type[BaseException] | None] = {}

        def register_reporter(hooks: object) -> None:
            def notify(context: object) -> None:
                delivered["reporter"] = context

                try:
                    context.reason = "x"  # the probe target: a DIRECT assignment on the delivered view
                    write_errors["reporter"] = None
                except AttributeError as error:
                    write_errors["reporter"] = type(error)

            hooks.subscribe("pipeline", "stage_execution_started", "notify", notify)  # type: ignore[attr-defined]

        def register_mirror(hooks: object) -> None:
            def notify(context: object) -> None:
                delivered["mirror"] = context

                try:
                    context.reason = "x"  # the probe target: a DIRECT assignment on the delivered view
                    write_errors["mirror"] = None
                except AttributeError as error:
                    write_errors["mirror"] = type(error)

            hooks.subscribe("pipeline", "stage_execution_started", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_reporter", register_hooks=register_reporter)
        install_tool_package("goga_tool_mirror", register_hooks=register_mirror)

        context = _stage_event()

        result = PipelineHooks().emit_stage_event("stage_execution_started", context)

        reporter_ctx = delivered["reporter"]
        mirror_ctx = delivered["mirror"]

        # Nested facts read through the proxies are the very same objects.
        assert reporter_ctx.stage is context.stage
        assert mirror_ctx.stage is context.stage
        assert reporter_ctx.stage is mirror_ctx.stage
        assert reporter_ctx.stage.name == "Build"
        assert mirror_ctx.event_id == "run-42:transition:7: stage_execution_started"
        assert write_errors["reporter"] is AttributeError
        assert write_errors["mirror"] is AttributeError
        assert result is None  # fire-and-forget — nothing collected, nothing returned

    def test_emit_run_event_unknown_action_raises_clean_error(self, pin_package_environment) -> None:
        """An undeclared address is a clean error of the emitting side."""
        pin_package_environment({})

        with pytest.raises(ValueError, match="unknown hook action"):
            PipelineHooks().emit_run_event("not_an_action", _run_event())

    def test_bridged_surface_registry_built_once_per_process(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Both bridged emissions of one surface share the single registry build."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def notify(context: object) -> None:
                return None

            hooks.subscribe("pipeline", "run_resumed", "notify", notify)  # type: ignore[attr-defined]
            hooks.subscribe("pipeline", "stage_paused", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        hooks = PipelineHooks()
        hooks.emit_run_event("run_resumed", _run_event())
        hooks.emit_stage_event("stage_paused", _stage_event())

        assert boundary.call_count == 1

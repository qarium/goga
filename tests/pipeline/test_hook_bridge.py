"""Contract and logic tests for the afm lifecycle-hook bridge declared in
``goga/pipeline/CODEMANIFEST`` — the four routines of ``hook_bridge.py``:

- ``map_event_action(event)`` — resolve one afm event name to its bridged
  pipeline action, or ``None`` outside the curated vocabulary
- ``build_run_event(payload)`` / ``build_stage_event(payload)`` — compose
  the bridged contexts from the parsed afm payload
- ``run_hook()`` — the process entry: filter, parse, build, emit, exit

The bridge tests manipulate the two process inputs directly — the event
name via ``monkeypatch.setenv("AFM_HOOK_EVENT", ...)`` and the payload via
``monkeypatch.setattr("sys.stdin", io.StringIO(...))`` — and run the
platform for real over the boundary fixtures of the pipeline test package.
The process-level fast-path subprocess proof lives in this suite as well
(the import discipline the bridge module top is contractually held to).
"""

from __future__ import annotations

import inspect
import io
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from goga.pipeline import hook_bridge
from goga.pipeline.hooks import RunIdentity


def _stage_payload() -> dict[str, object]:
    """The stage-level payload shaped exactly as afm writes it (design, verbatim)."""
    return {
        "schema_version": 1,
        "event_id": "run-42:transition:7: stage_execution_started",
        "event": "stage_execution_started",
        "occurred_at": "2026-10-21T12:00:00Z",
        "flow": {
            "name": "deploy",
            "run_id": "run-42",
            "resumed": False,
            "run_dir": "/home/goga/pipeline/runs/run-42",
            "root_dir": "/workspace",
        },
        "stage": {"id": "build", "name": "Build", "from": "approved", "to": "executing", "phase": "execution"},
    }


def _run_payload() -> dict[str, object]:
    """The run-level payload shaped exactly as afm writes it — no stage block."""
    return {
        "schema_version": 1,
        "event_id": "run-42:lifecycle:flow_resumed",
        "event": "flow_resumed",
        "occurred_at": "2026-10-21T12:05:00Z",
        "flow": {
            "name": "deploy",
            "run_id": "run-42",
            "resumed": True,
            "run_dir": "/home/goga/pipeline/runs/run-42",
            "root_dir": "/workspace",
        },
        "reason": "operator request",
    }


# --- Contract tests ---


class TestHookBridgeContract:
    def test_the_four_routines_are_defined_on_the_module(self) -> None:
        """The bridge module exposes exactly the four declared routine names."""
        for name in ("run_hook", "map_event_action", "build_run_event", "build_stage_event"):
            assert callable(getattr(hook_bridge, name))

    def test_the_four_routines_carry_the_declared_signatures(self) -> None:
        """``(event: str) -> str | None``, ``(payload: dict[str, Any]) -> RunEvent | StageEvent``, ``() -> int``."""
        map_signature = inspect.signature(hook_bridge.map_event_action)

        assert list(map_signature.parameters) == ["event"]
        assert map_signature.parameters["event"].annotation == "str"
        assert map_signature.return_annotation == "str | None"

        run_builder = inspect.signature(hook_bridge.build_run_event)

        assert list(run_builder.parameters) == ["payload"]
        assert run_builder.parameters["payload"].annotation == "dict[str, Any]"
        assert run_builder.return_annotation == "RunEvent"

        stage_builder = inspect.signature(hook_bridge.build_stage_event)

        assert list(stage_builder.parameters) == ["payload"]
        assert stage_builder.parameters["payload"].annotation == "dict[str, Any]"
        assert stage_builder.return_annotation == "StageEvent"

        hook_entry = inspect.signature(hook_bridge.run_hook)

        assert list(hook_entry.parameters) == []
        assert hook_entry.return_annotation == "int"

    def test_module_top_is_stdlib_only(self) -> None:
        """Importing the bridge module introduces no platform module into ``sys.modules``.

        Measured in a fresh child. The parent facades still carry the
        platform statically (the root facade goes lazy in a later task of
        this feature), so the child first imports ``goga`` to settle the
        parents, evicts every ``goga.hooks`` / ``goga.pipeline.hooks``
        module the static chain loaded, and only then imports the bridge:
        a platform module reappearing in ``sys.modules`` proves the bridge
        module top reached for the platform; an empty list proves it
        stdlib-only.
        """
        child = """
import sys

import goga

prefixes = ("goga.hooks", "goga.pipeline.hooks")
for name in [module for module in sys.modules if module.startswith(prefixes)]:
    del sys.modules[name]

import goga.pipeline.hook_bridge

print(sorted(module for module in sys.modules if module.startswith(prefixes)))
"""
        result = subprocess.run([sys.executable, "-c", child], check=False, capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[]"


# --- Logic tests — the curated vocabulary ---


class TestMapEventAction:
    @pytest.mark.parametrize(
        ("event", "action"),
        [
            ("stage_planning_started", "stage_planning_started"),
            ("stage_plan_ready", "stage_plan_ready"),
            ("stage_approved", "stage_approved"),
            ("stage_revision_started", "stage_revision_started"),
            ("stage_execution_started", "stage_execution_started"),
            ("stage_question_asked", "stage_question_asked"),
            ("stage_question_answered", "stage_question_answered"),
            ("stage_retry_scheduled", "stage_retry_scheduled"),
            ("stage_retry_started", "stage_retry_started"),
            ("stage_paused", "stage_paused"),
            ("stage_resumed", "stage_resumed"),
            ("stage_finished", "stage_finished"),
            ("stage_failed", "stage_failed"),
            ("flow_resumed", "run_resumed"),
            ("flow_interrupted", "run_interrupted"),
        ],
    )
    def test_map_event_action_resolves_the_curated_vocabulary(self, event: str, action: str) -> None:
        """The thirteen stage names bridge verbatim; the two run-level names normalize."""
        assert hook_bridge.map_event_action(event) == action

    @pytest.mark.parametrize(
        "event",
        [
            "flow_started",
            "flow_finished",
            "flow_failed",
            "stage_script_started",
            "stage_script_after_finished",
            "agent_action",
            "script_output",
            "",
            "not_an_event",
        ],
    )
    def test_map_event_action_returns_none_outside_the_curated_vocabulary(self, event: str) -> None:
        """afm's flow boundaries, script events, internal names, and unknowns stay unbridged."""
        assert hook_bridge.map_event_action(event) is None


# --- Logic tests — the context builders (mock-free record tests) ---


class TestBuildContexts:
    def test_build_stage_event_composes_the_transition_context(self) -> None:
        """The design payload composes the exact transition context — nothing invented, nothing attached."""
        context = hook_bridge.build_stage_event(_stage_payload())

        assert context.pipeline == "deploy"
        assert context.run == RunIdentity(
            run_id="run-42",
            run_dir="/home/goga/pipeline/runs/run-42",
            root_dir="/workspace",
            resumed=False,
        )
        assert context.stage.from_status == "approved"
        assert context.stage.to_status == "executing"
        assert context.stage.id == "build"
        assert context.stage.name == "Build"
        assert context.stage.phase == "execution"
        assert context.event_id == "run-42:transition:7: stage_execution_started"
        assert context.occurred_at == "2026-10-21T12:00:00Z"
        assert context.reason == ""  # absent in the payload — the only default
        assert not hasattr(context, "schema_version")
        assert not hasattr(context, "event")

    def test_build_stage_event_carries_empty_phase_when_afm_omits_it(self) -> None:
        """Live afm v1.2.17 omits ``phase`` on the start/retry transitions — it lands ``""``, not a failure."""
        stage = {key: value for key, value in _stage_payload()["stage"].items() if key != "phase"}

        context = hook_bridge.build_stage_event({**_stage_payload(), "stage": stage})

        assert context.stage.phase == ""
        assert context.stage.to_status == "executing"  # the transition facts still carry

    def test_build_run_event_composes_the_run_context(self) -> None:
        """The run-level builder carries the flow facts and the reason verbatim."""
        context = hook_bridge.build_run_event(_run_payload())

        assert context.pipeline == "deploy"
        assert context.run == RunIdentity(
            run_id="run-42",
            run_dir="/home/goga/pipeline/runs/run-42",
            root_dir="/workspace",
            resumed=True,
        )
        assert context.event_id == "run-42:lifecycle:flow_resumed"
        assert context.occurred_at == "2026-10-21T12:05:00Z"
        assert context.reason == "operator request"
        assert not hasattr(context, "stage")
        assert not hasattr(context, "schema_version")


# --- Logic tests — the process entry over the two process inputs ---


class TestRunHook:
    def test_run_hook_bridges_a_curated_stage_event_end_to_end(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
        capsys,
    ) -> None:
        """Env → filter → stdin → builder → emission: one subscribed tool receives the context."""
        pin_package_environment({"goga_tool_reporter": ["goga-tool-reporter"]})
        captured: dict[str, object] = {}

        def register(hooks: object) -> None:
            def notify(context: object) -> None:
                captured["context"] = context

            hooks.subscribe("pipeline", "stage_execution_started", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_reporter", register_hooks=register)

        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_execution_started")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_stage_payload())))

        result = hook_bridge.run_hook()

        assert result == 0
        assert captured["context"].pipeline == "deploy"
        assert captured["context"].stage.to_status == "executing"
        assert capsys.readouterr().out == ""  # the happy path prints nothing

    def test_run_hook_non_curated_event_exits_zero_without_reading_stdin(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
    ) -> None:
        """The fast path: exit 0 before any platform import, stdin unread, registry never built."""

        class _UntouchableStdin:
            def read(self, *_args: object) -> str:
                raise AssertionError("stdin must stay unread on a non-curated event")

        boundary = pin_package_environment({})

        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_script_started")
        monkeypatch.setattr(sys, "stdin", _UntouchableStdin())

        result = hook_bridge.run_hook()

        assert result == 0
        assert boundary.call_count == 0  # the enumeration never ran — no registry was built

    @pytest.mark.parametrize("stdin_text", ["{not json", ""], ids=["malformed", "empty"])
    def test_run_hook_damaged_stdin_returns_nonzero_with_clean_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        capsys,
        stdin_text: str,
    ) -> None:
        """Damaged and empty stdin travel the same JSONDecodeError path — a clean one-line error."""
        pin_package_environment({})

        monkeypatch.setenv("AFM_HOOK_EVENT", "flow_resumed")
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))

        result = hook_bridge.run_hook()

        captured = capsys.readouterr()

        assert result == 1
        assert "Error:" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize(
        "payload",
        [
            {key: value for key, value in _stage_payload().items() if key != "flow"},
            {**_stage_payload(), "flow": "not-a-dict"},
        ],
        ids=["absent", "not-a-dict"],
    )
    def test_run_hook_missing_flow_block_returns_nonzero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        capsys,
        payload: dict[str, object],
    ) -> None:
        """A payload without a usable flow block is a bridge-internal failure naming it."""
        pin_package_environment({})

        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_finished")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

        result = hook_bridge.run_hook()

        captured = capsys.readouterr()

        assert result == 1
        assert "flow block" in captured.err
        assert "Traceback" not in captured.err

    def test_run_hook_missing_stage_block_returns_nonzero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        capsys,
    ) -> None:
        """A stage-level event always carries a stage block — its absence is a named failure."""
        pin_package_environment({})

        payload = {key: value for key, value in _stage_payload().items() if key != "stage"}

        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_paused")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

        result = hook_bridge.run_hook()

        assert result == 1
        assert "stage block" in capsys.readouterr().err

    def test_run_hook_missing_event_fact_names_the_fact(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        capsys,
    ) -> None:
        """A missing required event fact is a clean failure naming exactly the fact."""
        pin_package_environment({})

        payload = {key: value for key, value in _run_payload().items() if key != "occurred_at"}

        monkeypatch.setenv("AFM_HOOK_EVENT", "flow_interrupted")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

        result = hook_bridge.run_hook()

        assert result == 1
        assert "occurred_at" in capsys.readouterr().err

    def test_run_hook_non_object_json_is_a_bridge_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        capsys,
    ) -> None:
        """A JSON array on stdin parses but is not an event payload — a named failure."""
        pin_package_environment({})

        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_finished")
        monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))

        result = hook_bridge.run_hook()

        assert result == 1
        assert "not a JSON object" in capsys.readouterr().err

    def test_run_hook_null_reason_lands_as_empty_string(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A JSON ``null`` reason lands ``""`` — the ``or ""`` read, not a carried ``None``."""
        pin_package_environment({"goga_tool_reporter": ["goga-tool-reporter"]})
        captured: dict[str, object] = {}

        def register(hooks: object) -> None:
            def notify(context: object) -> None:
                captured["context"] = context

            hooks.subscribe("pipeline", "run_resumed", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_reporter", register_hooks=register)

        monkeypatch.setenv("AFM_HOOK_EVENT", "flow_resumed")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({**_run_payload(), "reason": None})))

        result = hook_bridge.run_hook()

        assert result == 0
        assert captured["context"].reason == ""

    def test_run_hook_stage_event_without_phase_exits_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
        capsys,
    ) -> None:
        """A curated start/retry transition (live payloads carry no phase) bridges cleanly."""
        pin_package_environment({"goga_tool_reporter": ["goga-tool-reporter"]})
        captured: dict[str, object] = {}

        def register(hooks: object) -> None:
            def notify(context: object) -> None:
                captured["context"] = context

            hooks.subscribe("pipeline", "stage_execution_started", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_reporter", register_hooks=register)

        stage = {key: value for key, value in _stage_payload()["stage"].items() if key != "phase"}
        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_execution_started")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({**_stage_payload(), "stage": stage})))

        result = hook_bridge.run_hook()

        assert result == 0
        assert captured["context"].stage.phase == ""
        assert capsys.readouterr() == ("", "")

    def test_run_hook_subscriber_failure_and_empty_registry_exit_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
        capsys,
        caplog,
    ) -> None:
        """Observer semantics: a raising subscriber warns inside the platform; an empty registry is a no-op."""
        pin_package_environment({"goga_tool_boom": ["goga-tool-boom"]})

        def register(hooks: object) -> None:
            def notify(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("pipeline", "stage_paused", "notify", notify)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_boom", register_hooks=register)

        monkeypatch.setenv("AFM_HOOK_EVENT", "stage_paused")
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_stage_payload())))

        with caplog.at_level(logging.WARNING):
            result = hook_bridge.run_hook()

        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]

        assert result == 0
        assert "Error:" not in capsys.readouterr().err
        assert len(warnings) == 1
        assert "stage_paused" in warnings[0].getMessage()
        assert "boom" in warnings[0].getMessage()

        pin_package_environment({})

        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_stage_payload())))

        result = hook_bridge.run_hook()

        assert result == 0
        assert capsys.readouterr() == ("", "")


# --- Integration — the process-level proofs (real children, no mocks) ---


def _hook_child_code() -> str:
    """Build the child source driving ``python -m goga.pipeline hook`` via runpy.

    Returns:
        The Python source of the probe child: run the package entrypoint
        with ``hook`` as the subcommand, catch the resulting
        ``SystemExit``, and print the exit code followed by the platform
        modules (``goga.hooks`` / ``goga.pipeline.hooks`` trees) the
        process ended up carrying.
    """
    return (
        "import runpy\n"
        "import sys\n"
        "\n"
        'sys.argv = ["goga.pipeline", "hook"]\n'
        "code = 0\n"
        "try:\n"
        '    runpy.run_module("goga.pipeline", run_name="__main__")\n'
        "except SystemExit as reason:\n"
        "    code = reason.code\n"
        "print(code)\n"
        'print(sorted(m for m in sys.modules if m == "goga.hooks" or m.startswith("goga.hooks.")\n'
        '             or m == "goga.pipeline.hooks" or m.startswith("goga.pipeline.hooks.")))\n'
    )


def _spawn_hook_process(event: str, stdin_text: str | None) -> subprocess.CompletedProcess[str]:
    """Spawn one real afm-shaped hook process — the exact launch shape afm uses.

    Args:
        event: The ``AFM_HOOK_EVENT`` value the child sees.
        stdin_text: The payload text piped to the child; ``None`` leaves
            stdin at ``DEVNULL`` — the non-curated shape never reads it.

    Returns:
        The completed child process — stdout carries the exit code and
        the platform-module list of the probe.
    """
    repo_root = Path(__file__).resolve().parents[2]

    stream: dict[str, object] = {"stdin": subprocess.DEVNULL} if stdin_text is None else {"input": stdin_text}

    return subprocess.run(
        [sys.executable, "-c", _hook_child_code()],
        env={**os.environ, "GOGA_DOCKER": "1", "AFM_HOOK_EVENT": event, "PYTHONPATH": str(repo_root)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        **stream,
    )


class TestHookProcessIntegration:
    """Fresh-process proofs over the real entrypoint — the process shape afm spawns per event.

    The tests above drive ``run_hook`` in-process over pinned package
    environments; these probes spawn real children running
    ``python -m goga.pipeline hook`` so the import discipline of the
    whole chain — root facade, cell facade, ``cli``, bridge module top —
    is measured exactly as afm measures it, with the machine's own
    package environment (no tool packages installed here).
    """

    def test_run_hook_platform_free_fast_path(self) -> None:
        """A non-curated event exits 0 with no platform module ever imported (design, verbatim)."""
        result = _spawn_hook_process("stage_script_started", None)

        assert result.returncode == 0, result.stderr

        lines = result.stdout.strip().splitlines()

        assert lines[0] == "0"
        assert lines[1] == "[]"  # no goga.hooks / goga.pipeline.hooks module in sys.modules

    def test_run_hook_curated_event_bridges_in_a_real_process(self) -> None:
        """Env → filter → stdin → builder → emission through the real process shape."""
        result = _spawn_hook_process("stage_execution_started", json.dumps(_stage_payload()))

        assert result.returncode == 0, result.stderr

        lines = result.stdout.strip().splitlines()

        assert result.stderr == ""  # the happy path renders nothing — the exit code says zero alone
        assert lines[0] == "0"
        assert "goga.pipeline.hooks.events" in lines[1]  # the emission surface really loaded and ran

"""Operation-level tests for the ``run_pipeline`` Routine through the hooks zone.

The run form composes through the pipeline hooks zone: the amendment facts
resolve in the routine (the identity from one ``parse_dsl`` header read, the
decision from the kind-derivation matrix, the work identity from the branch
and its hosting topic directory), the amendment is delivered between the
skip merge and the compilation, the composition and the statuses build from
the same compilation the run executes, and the two notifications fire around
the runner launch — the creation immediately before it, the completion on
every launch-attempt return path with the statuses recomputed at the moment.

The scenarios run the real platform over the boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by ``tests/pipeline/conftest.py``):
the registry, the delivery, and the emissions execute the actual platform
code, with only the module boundaries mocked — ``compile_flow`` /
``run_flow`` / ``resolve_current_branch_name`` on the run module (tmp dirs
are not repos) — per the design's General Setup. History trees are real
``.goga/history/<year>/<slug>/`` structures built under ``current_year()``
(never a hardcoded year literal), so the suite survives a year boundary.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from goga.history import current_year
from goga.pipeline import run_pipeline
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    FlowStage,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
)
from goga.pipeline.hooks import (
    CompositionStage,
    PipelineHooks,
    PipelineIdentity,
    WorkflowDecision,
    WorkflowOverlay,
    WorkIdentity,
)
from goga.pipeline.workflow import WorkflowSyntaxError

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The minimal real pipeline file of every scenario — a valid header (the
# step-8 fact resolution parses it via parse_dsl) and one authored stage.
_PIPELINE_YML = """\
name: Deploy
description: Deploy pipeline
---

build:
  title: Build
"""


@pytest.fixture
def afm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AFM_DIR at a tmp dir and return the resolved path.

    Mirrored from ``tests/pipeline/test_run_pipeline.py`` — flow_path inside
    run_pipeline is ``afm_dir / "flow.yml"`` and ``runtime_dir`` is its posix
    string, so returning the resolved value lets the event-fact assertions
    compare against exactly what run_pipeline builds.
    """
    directory = (tmp_path / ".afm").resolve()
    monkeypatch.setenv("AFM_DIR", str(directory))
    return directory


def _write_pipeline(project_dir: Path, name: str = "deploy") -> Path:
    """Write the minimal deploy pipeline file and return its path."""
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{name}.yml"
    path.write_text(_PIPELINE_YML)
    return path


def _documents() -> tuple[PipelineDocument, FlowDocument]:
    """The documents tuple the mocked ``compile_flow`` returns.

    One compiled ``build`` stage so the composition fact is non-trivial: the
    run derives ``CompositionStage(id="build", title="Build")`` from it via
    ``order_stages``.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="Deploy", description="Deploy pipeline"),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(
        name="Deploy",
        description="Deploy pipeline",
        stages=[FlowStage(id="build", name="Build", depends_on=None, fields={})],
    )
    return (pipeline_doc, flow_doc)


def _write_topic(cwd: Path, slug: str) -> Path:
    """Build a real topic tree ``.goga/history/<current_year()>/<slug>/`` with todo.md."""
    topic_dir = cwd / ".goga" / "history" / current_year() / slug
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "todo.md").write_text("todo\n")
    return topic_dir


def _isolate_workflow_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the three workflow/skip env inputs for a deterministic resolution."""
    monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
    monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)
    monkeypatch.delenv("GOGA_SKIP_STAGES", raising=False)


def _install_events_tool(
    pin_package_environment,
    install_tool_package,
    recorded: dict[str, Any],
    events: list[str],
    amend: Any | None = None,
) -> None:
    """Pin the package environment and install one tool recording both run events.

    The tool subscribes ``run_created`` and ``run_completed`` and stores the
    received read-only contexts in ``recorded`` (the facts a hook observes),
    appending to ``events`` so orderings are falsifiable. ``amend`` optionally
    adds an ``amend_workflow`` subscription (e.g. a loud canary or a
    contribution).
    """
    pin_package_environment({"goga_tool_demo": ["demo-dist"]})

    def register(hooks: object) -> None:
        def on_created(self: object, context: object) -> None:
            events.append("created")
            recorded["created"] = context

        def on_completed(self: object, context: object) -> None:
            events.append("completed")
            recorded["completed"] = context

        hooks.subscribe("pipeline", "run_created", "notify", on_created)  # type: ignore[attr-defined]
        hooks.subscribe("pipeline", "run_completed", "notify", on_completed)  # type: ignore[attr-defined]
        if amend is not None:
            hooks.subscribe("pipeline", "amend_workflow", "amend", amend)  # type: ignore[attr-defined]

    install_tool_package("goga_tool_demo", register_hooks=register)


# --- Contract tests — the new import wiring ---


class TestRunPipelineHooksWiringContract:
    def test_module_imports_the_zone_checkpoint_surface(self) -> None:
        """The run module imports PipelineHooks & co. from the ``.hooks`` zone."""
        assert _run_pipeline_module.PipelineHooks is PipelineHooks
        assert _run_pipeline_module.PipelineIdentity is PipelineIdentity
        assert _run_pipeline_module.WorkflowDecision is WorkflowDecision
        assert _run_pipeline_module.WorkflowOverlay is WorkflowOverlay
        assert _run_pipeline_module.WorkIdentity is WorkIdentity
        assert _run_pipeline_module.CompositionStage is CompositionStage

    def test_module_imports_the_history_fact_resolvers(self) -> None:
        """The run module imports the four history names from ``..history``."""
        from goga.history import (
            assemble_status_scale,
            resolve_current_branch_name,
            resolve_topic_dir,
            resolve_topic_status,
        )

        assert _run_pipeline_module.assemble_status_scale is assemble_status_scale
        assert _run_pipeline_module.resolve_current_branch_name is resolve_current_branch_name
        assert _run_pipeline_module.resolve_topic_dir is resolve_topic_dir
        assert _run_pipeline_module.resolve_topic_status is resolve_topic_status


# --- Logic tests — the design scenarios over the real platform ---


class TestRunPipelineEventSequence:
    # The fixture lists are the scenarios' real dependencies (tmp layout + the
    # platform boundary factories) — the design's General Setup fixes them.
    def test_run_pipeline_full_event_sequence_around_launch(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Facts resolve, the layer composes, and both events bracket the launch.

        No workflow file exists (silent-miss — the layer stays active onto the
        empty base); the tool subscribes only the two notifications, so the
        amendment is the passthrough and ``compile_flow`` receives ``None``.
        The run returns run_flow's exit code; the creation fires before the
        launch with the composition and statuses of the compiled moment.
        """
        recorded: dict[str, Any] = {}
        events: list[str] = []
        _install_events_tool(pin_package_environment, install_tool_package, recorded, events)
        _isolate_workflow_env(monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)
        _write_topic(isolated_cwd, "feature-demo")

        def _run(*args: object, **kwargs: object) -> int:
            events.append("run")
            return 3

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", side_effect=_run),
        ):
            result = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 3
        created = recorded["created"]
        assert created.pipeline.name == "deploy"
        assert created.decision.kind == "silent-miss"
        assert created.composition == [CompositionStage(id="build", title="Build")]
        assert created.statuses == ["todo"]
        assert created.runtime_dir == afm_dir.as_posix()
        assert created.work == WorkIdentity(branch="feature-demo", slug="feature-demo", year=current_year())
        assert recorded["completed"].exit_code == 3
        # The silent-miss amendment was the passthrough onto the empty base.
        assert created.workflow is None
        assert mock_compile.call_args.kwargs["workflow"] is None
        # created recorded before run_flow called, completed after.
        assert events == ["created", "run", "completed"]

    def test_spawn_failure_still_emits_completion_with_code(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A 127 spawn failure is a return code — the completion still fires with it."""
        recorded: dict[str, Any] = {}
        events: list[str] = []
        _install_events_tool(pin_package_environment, install_tool_package, recorded, events)
        _isolate_workflow_env(monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)
        _write_topic(isolated_cwd, "feature-demo")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=127),
        ):
            result = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 127
        assert recorded["completed"].exit_code == 127
        assert events == ["created", "completed"]  # completed recorded after created

    def test_missing_pipeline_and_structural_error_fire_no_events(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Both pre-checkpoint failure paths return/raise before any event fires."""
        recorded: dict[str, Any] = {}
        events: list[str] = []
        _install_events_tool(pin_package_environment, install_tool_package, recorded, events)
        _isolate_workflow_env(monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
        ):
            result = run_pipeline("nope", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 1  # return 1 at discovery — checkpoints unreached
        assert events == []
        assert recorded == {}
        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()

        # Case B — a malformed resolved workflow-file: WorkflowSyntaxError
        # propagates from resolve_workflow, before the delivery.
        workflows_dir = isolated_cwd / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "custom.yml").write_text("bogus_key: value\n")
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "custom")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
            pytest.raises(WorkflowSyntaxError, match="unknown key in workflow"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert events == []
        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()


class TestRunPipelineWorkIdentity:
    def test_work_identity_unknown_branch_and_empty_slug_guard(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A None branch reads "unknown"; an unsluggable branch is guarded branch-only.

        Case A — detached HEAD / missing git: the literal "unknown" branch
        hosts no topic directory, so the branch-only form. Case B — a fully
        non-ASCII branch (every character drops, the slug is empty) makes
        resolve_topic_dir raise ValueError; the guard absorbs it and the form
        stays branch-only. Neither case is an error — events still fire.
        """
        recorded: dict[str, Any] = {}
        events: list[str] = []
        _install_events_tool(pin_package_environment, install_tool_package, recorded, events)
        _isolate_workflow_env(monkeypatch)

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)

        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: None)
        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        work = recorded["created"].work
        assert (work.branch, work.slug, work.year) == ("unknown", None, None)

        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "Ветка")
        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        work = recorded["created"].work
        assert work.branch == "Ветка"
        assert work.slug is None
        assert work.year is None
        # No exception; events still fired on both runs.
        assert events == ["created", "completed", "created", "completed"]


class TestRunPipelineDecisionMatrix:
    def test_workflow_decision_kind_derivation_matrix(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Every env configuration derives its (kind, workflow_name) exactly.

        disabled wins; a resolved document under an explicit name is
        "explicit"; under no name "auto-match"; a missing document (explicit
        or auto miss) is a silent miss. Observed through the recorded
        creation facts of each run.
        """
        recorded: dict[str, Any] = {}
        events: list[str] = []
        _install_events_tool(pin_package_environment, install_tool_package, recorded, events)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)
        workflows_dir = isolated_cwd / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("prompt: ci\n")

        def _run_once() -> None:
            recorded.clear()
            with (
                mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
                mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
            ):
                run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        def _assert_decision(label: str, expected: tuple[str, str | None]) -> None:
            decision = recorded["created"].decision
            assert (decision.kind, decision.workflow_name) == expected, label

        # Auto-miss first — the basename file does not exist yet.
        _isolate_workflow_env(monkeypatch)
        _run_once()
        _assert_decision("auto-miss", ("silent-miss", None))

        # Auto-match hit — the basename file now exists.
        (workflows_dir / "deploy.yml").write_text("prompt: authored\n")
        _isolate_workflow_env(monkeypatch)
        _run_once()
        _assert_decision("auto-match hit", ("auto-match", "deploy"))

        # Explicit name that resolves — and one that does not.
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "ci")
        _run_once()
        _assert_decision("explicit hit", ("explicit", "ci"))

        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "ghost")
        _run_once()
        _assert_decision("explicit miss", ("silent-miss", None))

        # Disabled wins over everything.
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "ignored")
        monkeypatch.setenv("GOGA_WORKFLOW_DISABLED", "1")
        _run_once()
        _assert_decision("disabled", ("disabled", None))


class TestRunPipelineAmendmentAndStatuses:
    def test_disabled_decision_skips_delivery_compiles_raw_and_still_emits(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A disabled decision delivers nothing, compiles raw, still emits both events.

        The tool's amendment hook fails loudly when called, so a clean return
        proves the delivery never ran. The auto-match workflow exists — the
        disable must win — and the overlay is the passthrough of the empty
        base, so ``compile_flow`` receives ``workflow=None``.
        """
        recorded: dict[str, Any] = {}
        events: list[str] = []

        def canary(self: object, context: object) -> None:
            raise AssertionError("amend hook must not run for a disabled decision")

        _install_events_tool(pin_package_environment, install_tool_package, recorded, events, amend=canary)

        monkeypatch.setenv("GOGA_WORKFLOW_DISABLED", "1")
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)
        monkeypatch.delenv("GOGA_SKIP_STAGES", raising=False)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)
        workflows_dir = isolated_cwd / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "deploy.yml").write_text("prompt: authored\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            result = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 0
        assert recorded["created"].decision.kind == "disabled"
        assert recorded["created"].provenance == []
        assert mock_compile.call_args.kwargs["workflow"] is None
        assert events == ["created", "completed"]  # no "amend" entry — both events fired

    def test_statuses_recomputed_at_completion_and_branch_only_stays_empty(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Hosting: statuses recompute at the completion moment; branch-only: none, no scale.

        The hosting run starts at ``todo``; the fake run writes
        ``completed/plan.md``, which outranks ``todo.md`` in the scale, so the
        completion emission reports ``done`` — the maximal-present recompute
        at the moment. The branch-only run (a branch hosting no topic) keeps
        ``[]`` at both moments and never assembles the scale: the enumeration
        boundary reads exactly once — the pipeline registry build alone.
        """
        recorded: dict[str, Any] = {}
        events: list[str] = []
        _install_events_tool(pin_package_environment, install_tool_package, recorded, events)
        _isolate_workflow_env(monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)
        topic_dir = _write_topic(isolated_cwd, "feature-demo")

        def _run_writes_done(*args: object, **kwargs: object) -> int:
            events.append("run")
            completed_dir = topic_dir / "completed"
            completed_dir.mkdir()
            (completed_dir / "plan.md").write_text("plan\n")
            return 0

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", side_effect=_run_writes_done),
        ):
            result = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 0
        assert recorded["created"].statuses == ["todo"]
        assert recorded["completed"].statuses == ["done"]

        # Branch-only — a fresh boundary pin counts from zero; the branch
        # hosts no topic directory, so no scale assembly ever runs.
        branch_recorded: dict[str, Any] = {}
        branch_events: list[str] = []
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_branch(hooks: object) -> None:
            def on_created(self: object, context: object) -> None:
                branch_events.append("created")
                branch_recorded["created"] = context

            def on_completed(self: object, context: object) -> None:
                branch_events.append("completed")
                branch_recorded["completed"] = context

            hooks.subscribe("pipeline", "run_created", "notify", on_created)  # type: ignore[attr-defined]
            hooks.subscribe("pipeline", "run_completed", "notify", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_branch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "solo-branch")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            result = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 0
        assert branch_recorded["created"].statuses == []
        assert branch_recorded["completed"].statuses == []
        assert branch_events == ["created", "completed"]
        assert boundary.call_count == 1  # only the pipeline registry build

    def test_emit_soft_failure_warns_and_never_affects_exit_code(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A failing run_completed hook warns; the run's exit code is unaffected."""
        recorded: dict[str, Any] = {}
        events: list[str] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def on_created(self: object, context: object) -> None:
                events.append("created")
                recorded["created"] = context

            def on_completed(self: object, context: object) -> None:
                events.append("completed")
                raise RuntimeError("boom")

            hooks.subscribe("pipeline", "run_created", "notify", on_created)  # type: ignore[attr-defined]
            hooks.subscribe("pipeline", "run_completed", "notify", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)
        _isolate_workflow_env(monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
            caplog.at_level(logging.WARNING),
        ):
            result = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert result == 0
        assert events == ["created", "completed"]  # the launch happened, the emission ran
        assert "demo" in caplog.text
        assert "run_completed" in caplog.text
        assert "boom" in caplog.text

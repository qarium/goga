"""Whole-feature Part C integration: the two ``resolve_project_name`` data flows.

Consolidated cross-part verification that the moved-and-re-exported
``resolve_project_name`` (now in the ``goga/config/git`` leaf cell, re-exported on
the ``goga/config`` facade) threads its tolerant ``name | None`` result through
both consumers:

- **Flow C1 — pipeline description prefix.** ``run_pipeline`` step 7 calls
  ``resolve_project_name()`` and forwards the result to ``compile_flow(...,
  project_name=...)`` so the compiled flow-file description gets a
  ``[<project-name>]`` prefix (``None`` ⇒ no prefix).
- **Flow C2 — onboarding image-name default.** ``Questionnaire.ask_goga_config``
  Dockerfile branch calls ``resolve_project_name()`` and derives the built-image
  default ``f"{name}:latest"`` (or ``None`` when unresolved) before offering it
  via the two-mode ``ask_image_name(language=None, default=...)``.

Both flows mock ``resolve_project_name`` on its owning module (per ``convention``
— mock the call, never invoke the real git subprocess) and assert the value
reaches the downstream consumer unchanged. The tolerance (``None`` ⇒ no prefix
/ no suggestion) is exercised for each flow.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar
from unittest import mock

# The owning module of resolve_project_name (used to mock the call in BOTH
# flows — the pipeline and onboarding consumers each re-import the name, so each
# is patched on its own importing module).
import goga.config.git.identity as _identity_module
import pytest
from goga.onboarding import questionnaire as qmod
from goga.pipeline import run_pipeline
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
)

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


def _fake_documents(project_name: str | None) -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, capturing the
    forwarded ``project_name`` in the flow description (mirroring how the
    compiler would prefix it)."""
    description = "d" if project_name is None else f"[{project_name}] d"
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description=description),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description=description, stages=[])
    return (pipeline_doc, flow_doc)


def _write_pipeline(directory: Path, name: str = "deploy") -> None:
    """Create an empty pipeline file so name resolution matches it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yml").write_text("pipeline")


class TestFlowC1PipelinePrefix:
    """Flow C1 — pipeline description prefix.

    ``run_pipeline`` derives the in-container project name from the git origin
    remote URL via ``resolve_project_name`` (step 7) and forwards it to
    ``compile_flow(..., project_name=...)``. ``None`` simply means no prefix.
    The value threaded into ``compile_flow`` is exactly what
    ``resolve_project_name`` returned.
    """

    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        return project_dir

    def test_c1_name_threaded_to_compile_flow_as_prefix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_project_name → 'widget' → compile_flow(project_name='widget')."""
        project_dir = self._setup(tmp_path, monkeypatch)
        # Patch on run_pipeline's importing module (the name it bound at import).
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: "widget")

        with (
            mock.patch.object(
                _run_pipeline_module, "compile_flow", return_value=_fake_documents("widget")
            ) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert mock_compile.call_args.kwargs["project_name"] == "widget"

    def test_c1_none_threaded_to_compile_flow_means_no_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """resolve_project_name → None → compile_flow(project_name=None) (no prefix)."""
        project_dir = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: None)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(None)) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert mock_compile.call_args.kwargs["project_name"] is None

    def test_c1_tolerant_missing_git_yields_none_and_run_completes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The underlying routine never raises — a missing git binary / no origin
        surfaces as None, so run_pipeline still completes (prefix simply absent).

        This drives the REAL ``resolve_project_name`` (not mocked) with a mocked
        ``subprocess.run`` raising FileNotFoundError, asserting the tolerance
        contract at the boundary the consumer depends on.
        """
        project_dir = self._setup(tmp_path, monkeypatch)
        # Restore the real (imported) routine; patch the subprocess it calls.
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", _identity_module.resolve_project_name)

        def raise_filenotfound(_argv, **_kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'git'")

        monkeypatch.setattr(_identity_module.subprocess, "run", raise_filenotfound)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(None)) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        # tolerance: None reached compile_flow, run_flow ran, exit 0.
        assert mock_compile.call_args.kwargs["project_name"] is None
        assert exit_code == 0


class TestFlowC2OnboardingDefault:
    """Flow C2 — onboarding image-name default.

    Drives the REAL ``Questionnaire.ask_goga_config`` Dockerfile branch (not a
    hand-mirrored copy of its formula) so the test asserts the production wiring
    of ``resolve_project_name`` → ``ask_image_name(language=None, default=...)``
    through the code path a consumer actually runs. ``resolve_project_name`` is
    mocked on its owning module (per ``convention`` — never invoke the real git
    subprocess); the offered default is exactly ``f"{name}:latest"`` when a name
    resolves and is absent (image required) when it does not.
    """

    _CONFIRMS: ClassVar[list[bool]] = [
        False,  # Download base convention?
        False,  # Add codemanifest usages?
        False,  # Add codemanifest annotations?
        True,  # Configure a build agent?
        True,  # Create Dockerfile?
        False,  # Set suggested task env variables?
        False,  # Add custom task env variable?
        True,  # Configure a pipeline agent?
        False,  # Set suggested pipeline env variables?
        False,  # Add custom pipeline env variable?
    ]

    def _run_goga_config(self, resolve_return, built_image_reply, monkeypatch, tmp_path):
        """Drive ``ask_goga_config`` to its Dockerfile branch; capture the offered
        built-image default and return the resulting :class:`GogaConfigAnswers`."""
        # ask_goga_config() short-circuits to None when .goga/config.yml exists;
        # the repo CWD contains the goga project's own config.yml, so run in a
        # clean tmp_path (no config.yml) to reach the Dockerfile branch.
        monkeypatch.chdir(tmp_path)
        captured: dict = {}

        def fake_image_prompt(message, *args, **kwargs):
            if message == "Built image name":
                captured["default"] = kwargs.get("default")
                return built_image_reply
            return "default-placeholder"

        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "Dockerfile",  # dockerfile path
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "claude",  # pipeline agent
            ]
        )

        def prompt_router(message, *args, **kwargs):
            if message == "Built image name":
                return fake_image_prompt(message, *args, **kwargs)
            return next(prompts)

        monkeypatch.setattr(qmod, "resolve_project_name", lambda: resolve_return)
        with (
            mock.patch("click.prompt", side_effect=prompt_router),
            mock.patch("click.confirm", side_effect=iter(self._CONFIRMS)),
        ):
            result = qmod.Questionnaire().ask_goga_config()

        return result, captured

    def test_c2_name_offers_name_latest_as_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_project_name → 'widget' → ask_image_name offered 'widget:latest'."""
        result, captured = self._run_goga_config("widget", "widget:latest", monkeypatch, tmp_path)

        assert captured["default"] == "widget:latest"
        assert result.image == "widget:latest"
        assert result.dockerfile_path == "Dockerfile"

    def test_c2_none_offers_no_default_image_required(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_project_name → None → ask_image_name called with no default (image required)."""
        result, captured = self._run_goga_config(None, "provided-image:latest", monkeypatch, tmp_path)

        assert captured["default"] is None
        assert result.image == "provided-image:latest"


class TestFacadeSingleEntryPoint:
    """The facade re-export is the single consumer entry point: both the
    pipeline and onboarding consumers import ``resolve_project_name`` from
    ``goga.config`` (the facade), which pulls it from ``goga.config.git``.
    A mock placed on the owning module propagates to the facade and both
    consumers' imported references resolve to the same routine.
    """

    def test_facade_and_git_and_identity_are_one_object(self) -> None:
        """The facade re-export is the routine defined in ``goga.config.git.identity``."""
        from goga.config import resolve_project_name as facade
        from goga.config.git import resolve_project_name as git_pkg
        from goga.config.git.identity import resolve_project_name as identity

        assert facade is git_pkg is identity

    def test_pipeline_consumer_bound_name_is_the_facade_routine(self) -> None:
        """run_pipeline's imported ``resolve_project_name`` is the facade routine."""
        assert _run_pipeline_module.resolve_project_name is _identity_module.resolve_project_name

    def test_onboarding_consumer_bound_name_is_the_facade_routine(self) -> None:
        """questionnaire's imported ``resolve_project_name`` is the facade routine."""
        assert qmod.resolve_project_name is _identity_module.resolve_project_name

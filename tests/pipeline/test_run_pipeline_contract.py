from __future__ import annotations

import inspect
import sys
import typing
from pathlib import Path
from unittest import mock

import pytest
from goga.docker import encode_home_profiles
from goga.pipeline import run_pipeline

from tests.pipeline.conftest import fake_documents, write_pipeline

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


class TestRunPipelineWorkflowContract:
    """Contract: run_pipeline forwards a ``workflow=`` kwarg to compile_flow.

    The public signature is ``(name, project_dir, user_dir, port, workflow,
    no_workflow, skip, parallel)`` — the workflow decision and the skip names
    arrive as explicit parameters (never from the environment; ``AFM_DIR`` is
    the only environment read of run coordination), and ``parallel`` is an
    optional concurrency cap threaded to ``run_flow``. compile_flow always
    receives a ``workflow`` keyword argument (``None`` when nothing resolved, or
    a ``WorkflowDocument`` when a workflow-file resolved).
    """

    def test_run_pipeline_signature_has_workflow_skip_and_parallel(self) -> None:
        """run_pipeline exposes (name, project_dir, user_dir, port, workflow, no_workflow, profile, skip, parallel).

        The workflow decision (``workflow``/``no_workflow``), the profile
        activation channel (``profile``), and the skip names (``skip``) are
        optional keywords inserted before ``parallel``; the defaults are
        ``None``/``False``/``None``/``None``/``None``.
        """
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)

        assert parameters == [
            "name",
            "project_dir",
            "user_dir",
            "port",
            "workflow",
            "no_workflow",
            "profile",
            "skip",
            "parallel",
        ]
        assert signature.parameters["workflow"].default is None
        assert signature.parameters["no_workflow"].default is False
        assert signature.parameters["profile"].default is None
        assert signature.parameters["skip"].default is None
        assert signature.parameters["parallel"].default is None

    def test_run_pipeline_parameter_annotations_match_contract(self) -> None:
        """The inserted parameters carry the contract annotations verbatim."""
        hints = typing.get_type_hints(run_pipeline)

        assert hints["workflow"] == str | None
        assert hints["no_workflow"] is bool
        assert hints["profile"] == str | None
        assert hints["skip"] == list[str] | None
        assert hints["parallel"] == int | None

    def test_run_pipeline_forwards_none_workflow_when_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No workflow parameter and no basename file → compile_flow receives workflow=None."""
        monkeypatch.chdir(tmp_path)
        afm_dir = (tmp_path / ".afm").resolve()
        monkeypatch.setenv("AFM_DIR", str(afm_dir))

        project_dir = tmp_path / "pipelines"
        write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        # compile_flow always receives a workflow= kwarg; here it is None.
        assert "workflow" in mock_compile.call_args.kwargs
        assert mock_compile.call_args.kwargs["workflow"] is None


class TestRunPipelineDelegatesWorkflowResolution:
    """Contract: step 6 delegates to the shared ``resolve_workflow`` rule set.

    The private ``_resolve_workflow`` helper was REMOVED; its parameterized
    contract lives in ``goga/pipeline/resolve_workflow.py`` (Task 2).
    ``run_pipeline`` receives the CLI decision as explicit parameters
    (``no_workflow`` > ``workflow``) and hands it to the shared resolver as
    ``(pipeline_name, workflow_name, no_workflow)`` — the same entry point
    ``describe_pipeline`` uses with its own parameters.
    """

    def test_run_pipeline_signature_unchanged(self) -> None:
        """The public signature stays the 9-parameter contract (name … parallel)."""
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)
        assert parameters == [
            "name",
            "project_dir",
            "user_dir",
            "port",
            "workflow",
            "no_workflow",
            "profile",
            "skip",
            "parallel",
        ]
        assert signature.parameters["parallel"].default is None

    def test_run_pipeline_module_has_no_private_resolver(self) -> None:
        """The private _resolve_workflow helper no longer exists on the module."""
        assert not hasattr(_run_pipeline_module, "_resolve_workflow")

    def test_apply_skip_stages_signature_unchanged(self) -> None:
        """apply_skip_stages keeps the (workflow, skip_stages) signature — logic untouched."""
        from goga.pipeline import apply_skip_stages

        parameters = list(inspect.signature(apply_skip_stages).parameters)
        assert parameters == ["workflow", "skip_stages"]

    def test_resolve_workflow_signature_unchanged(self) -> None:
        """resolve_workflow keeps the (pipeline_name, workflow_name, no_workflow, channels) signature.

        The three activation channels (``cli_profile``, ``env_profile``,
        ``home_profiles``) are optional keywords defaulting to ``None`` — the
        run coordination and the card forward them; the resolution rule set
        itself is unchanged.
        """
        from goga.pipeline import resolve_workflow

        signature = inspect.signature(resolve_workflow)
        parameters = list(signature.parameters)
        assert parameters == [
            "pipeline_name",
            "workflow_name",
            "no_workflow",
            "cli_profile",
            "env_profile",
            "home_profiles",
        ]
        assert signature.parameters["cli_profile"].default is None
        assert signature.parameters["env_profile"].default is None
        assert signature.parameters["home_profiles"].default is None

    def test_run_pipeline_forwards_the_activation_channels(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The run coordination threads the profile flag, the env value, and the decoded bundle into the resolver.

        ``profile="mixa"`` (the CLI channel) plus a non-empty ambient
        ``GOGA_PROFILE`` and a non-empty ``GOGA_HOME_PROFILES`` bundle reach
        ``resolve_workflow`` as its three channel parameters — observed on the
        real resolver over a patched module attribute recording the call.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))
        monkeypatch.setenv("GOGA_PROFILE", "ambient")
        monkeypatch.setenv("GOGA_HOME_PROFILES", encode_home_profiles({"x": {"k": "v"}}))
        project_dir = tmp_path / "pipelines"
        write_pipeline(project_dir)

        recorded: dict[str, object] = {}

        def _fake_resolve(pipeline_name: str, workflow_name: str | None, no_workflow: bool, *channels: object) -> None:
            recorded["args"] = (pipeline_name, workflow_name, no_workflow, *channels)

        monkeypatch.setattr(_run_pipeline_module, "resolve_workflow", _fake_resolve)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="hard", profile="mixa")

        assert recorded["args"] == ("deploy", "hard", False, "mixa", "ambient", {"x": {"k": "v"}})


class TestRunPipelineActivationSurfaceContract:
    """Contract: the profile activation context of the 23-step algorithm.

    Step 8 decodes the ``GOGA_HOME_PROFILES`` bundle (``decode_home_profiles``
    from the docker facade) and reads ``GOGA_PROFILE`` once, feeding both into
    the workflow resolution together with the ``profile`` parameter; step 14
    applies the per-stage env wrappers (``apply_stage_env_wrappers``) after the
    compilation; step 19 composes the launch layer over the WIDENED engine set
    (the five launch-mechanics keys plus the four goga carriage keys) and adds
    ``GOGA_PROFILE=<effective>`` when a profile resolved. The environment
    reads of the whole path are exactly four.
    """

    def test_run_pipeline_module_references_the_activation_surface(self) -> None:
        """The run module imports decode_home_profiles and apply_stage_env_wrappers."""
        assert hasattr(_run_pipeline_module, "decode_home_profiles")
        assert hasattr(_run_pipeline_module, "apply_stage_env_wrappers")

    def test_run_pipeline_engine_key_set_is_widened(self) -> None:
        """The engine drop set carries the five launch keys plus the four goga carriage keys."""
        keys = _run_pipeline_module._ENGINE_ENV_KEYS

        assert keys >= {"AFM_DIR", "AFM_DOCKER_FILE_ROOTS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}
        assert keys >= {"GOGA_PROFILE", "GOGA_WORKFLOW", "GOGA_HOME_PROFILES", "GOGA_EXTRA_ENV"}
        assert len(keys) == 9

    def test_run_pipeline_reads_exactly_four_environment_variables(self) -> None:
        """The whole run path performs exactly the four contract environment reads.

        Source inspection: every ``os.environ`` occurrence of the module is one
        of ``AFM_DIR``, ``GOGA_EXTRA_ENV``, ``GOGA_PROFILE``,
        ``GOGA_HOME_PROFILES`` — and there are exactly four occurrences. The
        workflow decision, the profile flag, and the skip names arrive as
        parameters.
        """
        source = Path(_run_pipeline_module.__file__).read_text()

        assert source.count("os.environ") == 4
        assert 'os.environ.get("AFM_DIR")' in source
        assert 'os.environ.get("GOGA_EXTRA_ENV", "")' in source
        assert 'os.environ.get("GOGA_PROFILE")' in source
        assert 'os.environ.get("GOGA_HOME_PROFILES", "")' in source

    def test_run_pipeline_delegates_workflow_resolution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The parameter decision drives the shared resolver — an explicit name resolves its file.

        The resolver runs for real (no internal seam): ``workflow="hardening"``
        reaches it and the resolved document is what ``compile_flow`` receives —
        the delegation is observed on the run's own output, not on a patched
        call shape.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))
        project_dir = tmp_path / "pipelines"
        write_pipeline(project_dir)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "hardening.yml").write_text("prompt: hardening prompt\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="hardening")

        workflow = mock_compile.call_args.kwargs["workflow"]
        assert workflow is not None
        assert workflow.prompt == "hardening prompt"

    def test_run_pipeline_disabled_nulls_the_explicit_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """no_workflow=True → the name is nulled before resolution — nothing resolves.

        The disabled priority is enforced in the input (workflow_name=None) as
        well as inside the rule set (no_workflow=True) — double protection.
        Observed on the real resolver: the named workflow-file exists and would
        resolve, yet ``compile_flow`` receives ``workflow=None``.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))
        project_dir = tmp_path / "pipelines"
        write_pipeline(project_dir)
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "hardening.yml").write_text("prompt: must not resolve\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321, workflow="hardening", no_workflow=True)

        assert mock_compile.call_args.kwargs["workflow"] is None


class TestRunPipelineProjectNameContract:
    """Contract: run_pipeline forwards a ``project_name=`` kwarg to compile_flow.

    The project name is derived in-container from the git origin remote URL via
    :func:`resolve_project_name` (step 7) and passed to :func:`compile_flow` so the
    compiled flow-file description gets a ``[<project-name>]`` prefix (Part 2). It
    is OUTPUT-only context — never a ``run_pipeline`` parameter — and mirrors the
    ``root_dir`` pattern: derived from the environment, never read from config, and
    ``resolve_project_name`` never raises (``None`` simply means no prefix).
    """

    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """chdir into tmp_path, set AFM_DIR, and write a matching pipeline file."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))
        project_dir = tmp_path / "pipelines"
        write_pipeline(project_dir)
        return project_dir

    def test_run_pipeline_forwards_resolved_project_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_project_name() → "widget" → compile_flow receives project_name="widget"."""
        project_dir = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: "widget")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        # compile_flow receives project_name= as a separate keyword, matching the
        # value resolve_project_name() returned at step 7.
        assert "project_name" in mock_compile.call_args.kwargs
        assert mock_compile.call_args.kwargs["project_name"] == "widget"

    def test_run_pipeline_forwards_none_project_name_when_unresolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """resolve_project_name() → None → compile_flow receives project_name=None (no prefix)."""
        project_dir = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: None)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert mock_compile.call_args.kwargs["project_name"] is None

    def test_run_pipeline_calls_resolve_project_name_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_pipeline invokes resolve_project_name() exactly once (step 7)."""
        project_dir = self._setup(tmp_path, monkeypatch)

        calls = []

        def fake_resolve() -> str | None:
            calls.append(True)
            return "widget"

        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", fake_resolve)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert len(calls) == 1


class TestRunPipelineConfigSurfaceContract:
    """Contract: run_pipeline opens with the in-container configuration load-and-amend.

    The signature is UNCHANGED — ``(name, project_dir, user_dir, port,
    workflow, no_workflow, skip, parallel)`` — while the module surface
    grows the load-and-amend names (``load_project_config`` from the config
    facade, ``ConfigHooks`` from the config hooks zone) and the launch-layer
    names (``decode_extra_env`` from the docker facade, ``write_afm_config``
    from the afm-config module). Contract-level checks only: the behavior
    (call order, exit codes, layer composition) is locked by the logic tests
    of ``test_run_pipeline.py``.
    """

    def test_run_pipeline_signature_unchanged_with_config_surface(self) -> None:
        """The public signature stays the 9-parameter contract shape."""
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)

        assert parameters == [
            "name",
            "project_dir",
            "user_dir",
            "port",
            "workflow",
            "no_workflow",
            "profile",
            "skip",
            "parallel",
        ]

    def test_run_pipeline_module_references_the_load_and_amend_surface(self) -> None:
        """The run module imports load_project_config and ConfigHooks.

        The module-object attribute form (never a ``sys.modules`` assertion —
        process-global and order-dependent): the two names the 21-step
        contract's steps 1-2 consume must be part of the module surface.
        """
        assert hasattr(_run_pipeline_module, "load_project_config")
        assert hasattr(_run_pipeline_module, "ConfigHooks")

    def test_run_pipeline_module_references_the_launch_layer_surface(self) -> None:
        """The run module imports decode_extra_env and write_afm_config.

        Step 14 consumes ``write_afm_config``; step 17 consumes
        ``decode_extra_env`` — both must be part of the module surface.
        """
        assert hasattr(_run_pipeline_module, "decode_extra_env")
        assert hasattr(_run_pipeline_module, "write_afm_config")

    def test_run_pipeline_source_consumes_the_effective_configuration(self) -> None:
        """Steps 14 and 17 read the EFFECTIVE configuration of the overlay.

        The pipeline agent and the pipeline task env travel through
        ``config.pipeline`` — the effective configuration variable the
        load-and-amend produces — never a bare ``authored`` read.
        """
        source = Path(_run_pipeline_module.__file__).read_text()

        assert "write_afm_config(config.pipeline.agent)" in source
        assert "config.pipeline.env" in source


class TestRunPipelineImportsResolveProjectNameFromConfig:
    """Contract: run_pipeline sources resolve_project_name from goga.config.

    The local ``def resolve_project_name`` was REMOVED from
    ``run_pipeline.py`` (Part C). The routine now lives in the ``goga/config/git``
    leaf cell and is re-exported on the ``goga/config`` facade; ``run_pipeline``
    imports it via ``from ..config import resolve_project_name``. The step-7 call
    shape ``resolve_project_name()`` is unchanged, but the symbol is no longer
    defined locally — importing ``run_pipeline`` pulls in ``goga.config.git.identity``.
    """

    def test_resolve_project_name_importable_from_facade(self) -> None:
        """from goga.config import resolve_project_name resolves to a callable."""
        from goga.config import resolve_project_name

        assert callable(resolve_project_name)

    def test_run_pipeline_callable(self) -> None:
        """from goga.pipeline.run_pipeline import run_pipeline is callable."""
        assert callable(run_pipeline)

    def test_no_local_definition_in_run_pipeline_source(self) -> None:
        """resolve_project_name is NOT defined locally in run_pipeline.py.

        The function moved to ``goga/config/git``; the local ``def`` block was
        deleted, leaving only the import at the module top.
        """
        source = Path(_run_pipeline_module.__file__).read_text()
        assert "def resolve_project_name" not in source

    def test_importing_run_pipeline_pulls_goga_config_git_identity(self) -> None:
        """Importing run_pipeline loads the goga.config.git.identity owning module.

        After the swap, ``run_pipeline.py`` imports ``resolve_project_name`` from
        ``..config`` (the facade), which re-exports it from ``.git.identity`` —
        so the owning module lands in ``sys.modules`` once ``run_pipeline`` is
        imported.
        """
        # run_pipeline is already imported at module top; ensure the owning module
        # is registered in sys.modules as a consequence of the facade re-export.
        assert "goga.config.git.identity" in sys.modules

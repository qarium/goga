"""Shared fixtures and scaffolding of the ``tests/pipeline`` package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
    PipelineRoles,
)

from tests.hooks.conftest import install_tool_package, pin_package_environment

__all__ = ["install_tool_package", "pin_package_environment"]

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The four materialized afm prompt-file stems. The first three resolve from the
# overridable roles (planner/executor/reviewer) via translate_role; summary is a
# separate, always-default channel. These are output-side afm names, not role
# aliases — run_pipeline materializes exactly these four files.
PROMPT_STEMS: tuple[str, ...] = ("planning", "implementation", "review", "summary")


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """chdir into tmp_path — the workflows root resolves to ``<tmp>/.goga/workflows``."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def afm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AFM_DIR at a tmp dir and return the resolved path.

    flow_path inside run_pipeline is ``afm_dir / "flow.yml"`` and the runtime
    fact carries its posix string. Returning the resolved value lets
    assertions compare against exactly what run_pipeline builds (it resolves
    AFM_DIR internally). The directory itself is not created here — the
    wiring tests mock compile_flow, so its parent-must-exist precondition
    never fires; the real-compile tests create it explicitly.
    """
    directory = (tmp_path / ".afm").resolve()
    monkeypatch.setenv("AFM_DIR", str(directory))
    return directory


@pytest.fixture
def _empty_package_environment(pin_package_environment) -> None:
    """Pin the package environment empty for the modules opting in via ``usefixtures``.

    The card and CLI paths build the real registry through the amendment
    layer, so an unpinned environment would make the composed output depend
    on the machine's installed ``goga_tool_*`` packages. Tests that install a
    tool pin their own environment on top — the later pin wins.
    """
    pin_package_environment({})


def write_pipeline(directory: Path, name: str = "deploy") -> None:
    """Create a minimal valid pipeline file so name resolution matches it.

    The fact-resolution step parses the file via ``parse_dsl`` (the header
    read), so the fixture text must be valid DSL — string name/description
    in the header and a ``---`` body separator.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yml").write_text("name: Deploy\ndescription: d\n---\n\nbuild:\n  title: Build\n")


def fake_documents(roles: PipelineRoles | None = None) -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, for mock wiring.

    Shared by the run-path wiring tests and the materialization tests so they
    exercise the same unpack shape. ``roles`` defaults to None (no header
    block), which makes materialization fall back to the package defaults.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d", roles=roles),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def write_defaults(defaults_dir: Path, stems: tuple[str, ...] = PROMPT_STEMS) -> None:
    """Write ``default <stem>\\n`` prompt files for the given stems into defaults_dir."""
    defaults_dir.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        (defaults_dir / f"{stem}.md").write_text(f"default {stem}\n")


def patch_defaults(monkeypatch: pytest.MonkeyPatch, defaults_dir: Path) -> None:
    """Redirect run_pipeline's default-prompt resolver at a tmp defaults dir."""
    monkeypatch.setattr(_run_pipeline_module, "_resolve_defaults_dir", lambda: defaults_dir)

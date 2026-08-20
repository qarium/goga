"""Contract and logic tests for the ``describe_pipelines`` Routine.

The pipeline cell's CODEMANIFEST declares ``describe_pipelines`` as the
composer of the pipeline overview: every discovered pipeline paired with the
description from its DSL header. It reuses the ``list_pipelines`` discovery
contract unchanged (no extra filtering, no reordering) and only reads each
discovered file's header via ``parse_dsl`` — no compilation.

Failure semantics are all-or-nothing: the first damaged file (unreadable,
structurally invalid, non-YAML) aborts the whole overview. There are no
partial lists, no silent skips, and no placeholder markers — the consumer
(``pipeline_cli``) renders the error.

Fixtures mirror the design's General Setup: ``deploy.yml`` (STAGES format),
``feature.yml`` (PHASES format), ``release.yml`` (empty body ``{}``).
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import get_type_hints

import pytest
import yaml
from goga.pipeline.compiler import StructuralError
from goga.pipeline.describe_pipelines import describe_pipelines
from goga.pipeline.list_pipelines import list_pipelines
from goga.pipeline.pipeline_entry import PipelineSource
from goga.pipeline.pipeline_summary import PipelineSummary

# General Setup fixtures (STAGES / PHASES / empty-body DSL files).
_DEPLOY_YML = """\
name: Deploy
description: Deploy the service
---

build:
  title: Build
test:
  title: Test
  depends_on:
    - build
"""

_FEATURE_YML = """\
name: Goga feature
description: Implement a feature
---

- name: propose
  title: Propose
- name: accept
  title: Accept Result
"""

# An empty mapping body is valid for ``parse_dsl`` (``compile_flow`` is the one
# that rejects empty bodies) — a valid fixture for the overview.
_RELEASE_YML = """\
name: Release
description: Cut a release
---

{}
"""


def _write_pipeline(directory: Path, name: str, text: str) -> Path:
    """Write a pipeline-file into ``directory`` and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yml"
    path.write_text(text)
    return path


class TestDescribePipelinesContract:
    def test_describe_pipelines_is_importable_from_module(self) -> None:
        """The routine lives at its declared location ``goga.pipeline.describe_pipelines``."""
        import goga.pipeline.describe_pipelines as module

        assert module.describe_pipelines is describe_pipelines

    def test_describe_pipelines_signature(self) -> None:
        """Signature: (project_dir: Path, user_dir: Path) -> list[PipelineSummary]."""
        signature = inspect.signature(describe_pipelines)
        # The module uses ``from __future__ import annotations``, so raw
        # annotations are strings — resolve them through get_type_hints.
        hints = get_type_hints(describe_pipelines)

        assert list(signature.parameters) == ["project_dir", "user_dir"]
        assert hints["project_dir"] is Path
        assert hints["user_dir"] is Path
        assert hints["return"] == list[PipelineSummary]


class TestDescribePipelinesLogic:
    def test_describe_pipelines_returns_summaries_in_discovery_order(self, tmp_path: Path) -> None:
        """Summaries follow ``list_pipelines`` order; name is the stem, not the header name."""
        project_dir = tmp_path / "project_pipelines"
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_pipeline(project_dir, "feature", _FEATURE_YML)
        _write_pipeline(user_dir, "release", _RELEASE_YML)

        summaries = describe_pipelines(project_dir, user_dir)

        assert [summary.name for summary in summaries] == ["deploy", "feature", "release"]
        assert summaries[0].source is PipelineSource.PROJECT
        assert summaries[1].source is PipelineSource.PROJECT
        assert summaries[2].source is PipelineSource.USER
        # The name is the discovered stem, never the authored header name.
        assert summaries[0].name == "deploy"
        assert summaries[0].description == "Deploy the service"
        assert summaries[1].description == "Implement a feature"
        assert summaries[2].description == "Cut a release"
        assert all(isinstance(summary, PipelineSummary) for summary in summaries)

    def test_describe_pipelines_project_wins_on_name_conflict(self, tmp_path: Path) -> None:
        """A name present in both directories yields one PROJECT summary with the project description."""
        project_dir = tmp_path / "project_pipelines"
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_pipeline(user_dir, "deploy", _DEPLOY_YML.replace("Deploy the service", "User deploy"))

        summaries = describe_pipelines(project_dir, user_dir)

        # Name-conflict collapse is inherited from ``list_pipelines`` — one
        # entry, project source, project description.
        assert len(summaries) == 1
        assert summaries[0].name == "deploy"
        assert summaries[0].source is PipelineSource.PROJECT
        assert summaries[0].description == "Deploy the service"

    def test_describe_pipelines_empty_description_is_preserved(self, tmp_path: Path) -> None:
        """An explicitly empty header description survives — there is no falsy filter."""
        project_dir = tmp_path / "project_pipelines"
        # Quoted so YAML parses an empty *string*; a bare ``description:`` is
        # null, which ``parse_dsl`` rejects as "header missing name/description".
        empty_description = _DEPLOY_YML.replace("description: Deploy the service", 'description: ""')
        _write_pipeline(project_dir, "deploy", empty_description)

        summaries = describe_pipelines(project_dir, tmp_path / "user_pipelines")

        assert summaries[0].description == ""

    def test_describe_pipelines_aborts_on_damaged_yaml(self, tmp_path: Path) -> None:
        """A non-YAML body aborts the overview before any later file is processed (no partial list).

        The broken YAML sits in the body segment (after the ``---`` line) so
        the failure comes from the YAML parser itself; a broken header segment
        would fail ``_split_segments`` first with a ``StructuralError``.
        """
        from unittest import mock

        import goga.pipeline.describe_pipelines as module

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", "name: Deploy\ndescription: d\n---\n:\n  [broken\n")
        _write_pipeline(project_dir, "feature", _FEATURE_YML)

        with (
            mock.patch.object(module, "parse_dsl", wraps=module.parse_dsl) as spy,
            pytest.raises(yaml.YAMLError),
        ):
            describe_pipelines(project_dir, tmp_path / "user_pipelines")

        # ``feature`` (sorted after ``deploy``) was never read — the first
        # damaged file aborts the whole overview.
        assert spy.call_count == 1

    def test_describe_pipelines_aborts_on_structural_error(self, tmp_path: Path) -> None:
        """A file without the ``---`` separator aborts the overview with a readable StructuralError."""
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", "name: Deploy\ndescription: no separator\n")

        with pytest.raises(StructuralError, match="missing body separator"):
            describe_pipelines(project_dir, tmp_path / "user_pipelines")

    def test_describe_pipelines_aborts_on_unreadable_file(self, tmp_path: Path) -> None:
        """An unreadable (permission-denied) file aborts the overview with OSError.

        Skipped when running as root — root bypasses file permission bits, so
        the chmod would not produce the failure under test.
        """
        if os.geteuid() == 0:  # pragma: no cover - skip when chmod is not enforced
            pytest.skip("permission-based unreadability cannot be reproduced as root")

        project_dir = tmp_path / "project_pipelines"
        path = _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        path.chmod(0)

        try:
            with pytest.raises(PermissionError):
                describe_pipelines(project_dir, tmp_path / "user_pipelines")
        finally:
            path.chmod(0o644)

    def test_describe_pipelines_empty_when_directories_missing(self, tmp_path: Path) -> None:
        """Missing source directories are treated as empty — an empty overview, no error."""
        summaries = describe_pipelines(tmp_path / "project_pipelines", tmp_path / "user_pipelines")

        assert summaries == []

    def test_describe_pipelines_writes_nothing(self, tmp_path: Path) -> None:
        """The overview is read-only — the source tree is byte-identical before and after."""
        project_dir = tmp_path / "project_pipelines"
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_pipeline(user_dir, "release", _RELEASE_YML)

        before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

        describe_pipelines(project_dir, user_dir)

        after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
        assert after == before

    def test_describe_pipelines_matches_list_pipelines_discovery(self, tmp_path: Path) -> None:
        """Discovery is delegated, not re-implemented: names/sources mirror ``list_pipelines`` exactly."""
        project_dir = tmp_path / "project_pipelines"
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_pipeline(user_dir, "acme:deploy", _RELEASE_YML)
        _write_pipeline(user_dir, "notes", _FEATURE_YML)

        summaries = describe_pipelines(project_dir, user_dir)
        entries = list_pipelines(project_dir, user_dir)

        assert [(s.name, s.source) for s in summaries] == [(e.name, e.source) for e in entries]

"""Shipped-workflow load guard — every project workflow-file must load.

The map-form assistants hard transition turned the old list form into a hard
``WorkflowSyntaxError``, and the repo's own ``.goga/workflows/refinement.yml``
was stranded in the list form once — ``goga pipeline run refinement`` failed
before compilation while the whole test suite stayed green (the shipped-asset
guards cover ``goga/assets/pipelines/*.yml``, never the project workflows).
This guard loads every ``.goga/workflows/*.yml`` through the real chain
(profile peek/activate/resolve, render, parse) so an authoring-form
transition cannot strand a shipped workflow again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.pipeline.workflow import load_workflow

# The workflows live in the repository's project ``.goga`` tree, not inside
# the ``goga`` package, so resolve the repo root from this test file's
# location regardless of the current working directory / test root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS_DIR = _REPO_ROOT / ".goga" / "workflows"

_SHIPPED_WORKFLOWS = sorted(_WORKFLOWS_DIR.glob("*.yml"))


def test_shipped_workflow_assets_exist() -> None:
    """The project workflows directory carries the six canonical workflow-files.

    Guards against the workflows path moving unnoticed (which would silently
    turn the parametrized load test into a no-op over an empty collection).
    """
    names = {path.name for path in _SHIPPED_WORKFLOWS}

    assert names == {"development.yml", "refinement.yml", "sync.yml", "bugfix.yml", "patch.yml", "review.yml"}


@pytest.mark.parametrize("workflow_path", _SHIPPED_WORKFLOWS, ids=lambda path: path.name)
def test_every_shipped_workflow_loads(workflow_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every shipped workflow-file loads through the whole chain without raising.

    ``load_workflow`` resolves profiles from ``<cwd>/.goga/profiles`` and the
    workflow templates interpolate profile data, so the process CWD moves to
    the repository root for the duration of the load.
    """
    monkeypatch.chdir(_REPO_ROOT)

    loaded = load_workflow(workflow_path, None, None, None)

    assert loaded.document.stages

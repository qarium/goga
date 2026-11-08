"""Project-pipeline compile guard — every ``.goga/pipelines/*.yml`` must compile cleanly.

The shipped-asset twin (``test_shipped_pipelines_compile.py``) covers
``goga/assets/pipelines/``; this guard covers the project-level pipeline-files
of THIS repository (``<repo>/.goga/pipelines/``), which the shipped guard never
sees. Two properties are pinned per file: it compiles end-to-end, and its
header carries only keys the DSL header parser reads — ``_parse_header``
silently drops unknown header keys, so a typo'd key (``repetable`` for
``repeatable``) would otherwise ship as a no-op with the intended flag never
reaching the compiled flow.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from goga.pipeline.compiler import compile_flow

# The repository root (this test lives at <root>/tests/pipeline/compiler/).
_REPO_ROOT = Path(__file__).resolve().parents[3]

_PROJECT_PIPELINES_DIR = _REPO_ROOT / ".goga" / "pipelines"

_PROJECT_PIPELINES = sorted(_PROJECT_PIPELINES_DIR.glob("*.yml"))

# The complete key set ``_parse_header`` reads from a header segment; anything
# else is dropped without an error (only legacy ``agents`` is hard-rejected).
_KNOWN_HEADER_KEYS = {"name", "description", "roles", "repeatable"}


def _raw_header_keys(pipeline_path: Path) -> set[str]:
    """Split the header segment and return its raw YAML keys (typo detection)."""
    text = pipeline_path.read_text()
    parts = re.split(r"^---\r?$", text, maxsplit=1, flags=re.MULTILINE)

    assert len(parts) >= 2, f"{pipeline_path.name}: missing body separator"

    header = yaml.safe_load(parts[0])

    assert isinstance(header, dict), f"{pipeline_path.name}: header is not a mapping"

    return set(header)


def test_project_pipeline_files_exist() -> None:
    """The project pipelines directory carries at least one pipeline-file.

    Guards against the directory moving unnoticed (which would silently turn
    the parametrized compile test into a no-op over an empty collection).
    """
    assert _PROJECT_PIPELINES, f"no pipeline-files found under {_PROJECT_PIPELINES_DIR}"


def test_every_project_pipeline_compiles_with_known_header_keys(tmp_path: Path) -> None:
    """Every project pipeline-file compiles and authors only header keys the parser reads."""
    for pipeline_path in _PROJECT_PIPELINES:
        flow_path = tmp_path / (pipeline_path.stem + "-flow.yml")

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        assert flow_path.exists()
        assert flow_doc.stages
        assert pipeline_doc.header.name

        unknown = _raw_header_keys(pipeline_path) - _KNOWN_HEADER_KEYS
        assert not unknown, (
            f"{pipeline_path.name}: unknown header keys {sorted(unknown)} are silently "
            f"dropped by the DSL header parser; valid keys: {sorted(_KNOWN_HEADER_KEYS)}"
        )

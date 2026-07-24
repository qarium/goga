"""Shipped-pipeline compile guard — every asset pipeline-file must compile.

The authoring-side stage-body field for interactivity is ``communication`` (the
afm output field ``interactive`` is output-only and rejected on the input side).
A shipped pipeline-file that re-introduces an authoring ``interactive:`` (or the
legacy ``agents:``) would make ``compile_flow`` raise ``StructuralError`` and
break ``goga pipeline run``. This guard compiles every pipeline-file under
``goga/assets/pipelines/*.yml`` end-to-end so such a regression is caught here
rather than at runtime in the container.
"""

from __future__ import annotations

from pathlib import Path

import goga
from goga.pipeline.compiler import compile_flow

# The assets live inside the ``goga`` package directory, so resolve them from the
# package ``__file__`` regardless of the current working directory / test root.
_ASSETS_DIR = Path(goga.__file__).resolve().parent / "assets" / "pipelines"

_SHIPPED_PIPELINES = sorted(_ASSETS_DIR.glob("*.yml"))


def test_shipped_pipeline_assets_exist() -> None:
    """The assets directory carries the four canonical pipeline-files.

    Guards against the assets path moving unnoticed (which would silently turn
    the parametrized compile test into a no-op over an empty collection).
    """
    names = {path.name for path in _SHIPPED_PIPELINES}

    assert names == {"feature.yml", "bugfix.yml", "patch.yml", "review.yml"}


def test_every_shipped_pipeline_compiles(tmp_path: Path) -> None:
    """Every shipped pipeline-file compiles via ``compile_flow`` without raising.

    Asserts each file parses, is reconstructed into canonical-key-order stages
    (authoring ``communication`` → output ``interactive``), and serializes — i.e.
    no authoring ``interactive``/legacy ``agents`` key slipped back into a
    shipped asset.
    """
    assert _SHIPPED_PIPELINES, "no shipped pipeline-files found under goga/assets/pipelines"

    for pipeline_path in _SHIPPED_PIPELINES:
        flow_path = tmp_path / (pipeline_path.stem + "-flow.yml")

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        # The flow-file is written as a side effect and carries at least one stage.
        assert flow_path.exists()
        assert flow_doc.stages
        assert pipeline_doc.header.name

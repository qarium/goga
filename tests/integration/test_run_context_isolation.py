"""Isolation guarantees of the shared in-container run-context scaffolding.

The ``in_container_pipeline_run_context`` fixture (``tests/integration/conftest.py``)
is the seam every end-to-end run-path suite of this zone opts into: it relocates the
fixed in-container home-path constants of the run chain into the pytest tmp tree so
no test writes the real home. One relocation was historically missed — the afm skin
base — which made the whole zone pass on a machine with a writable ``/home/goga``
while failing on CI (whose user home lives elsewhere), and silently materialized the
skin into the real home along the way. These tests pin the isolation property itself,
so a dropped relocation fails on ANY host, not only on the CI one.
"""

from __future__ import annotations

import sys
from pathlib import Path


class TestInContainerPipelineRunContext:
    def test_skin_materialization_stays_in_tmp_tree(self, in_container_pipeline_run_context: Path) -> None:
        afm_skin_module = sys.modules["goga.pipeline.afm_skin"]

        materialized = afm_skin_module.materialize_afm_skin()

        base = afm_skin_module._SKINS_TARGET_BASE

        assert base == in_container_pipeline_run_context / ".afm-home" / "skins"
        assert materialized == base / "goga"
        assert (materialized / "index.css").is_file()

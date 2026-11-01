"""Contract-surface lock of ``apply_stage_env_wrappers`` — facade and API shape."""

from __future__ import annotations

import inspect
from pathlib import Path

import goga.pipeline


class TestContract:
    """Contract-surface lock: facade accessibility and API shape."""

    def test_importable_from_facade(self) -> None:
        from goga.pipeline import apply_stage_env_wrappers

        assert callable(apply_stage_env_wrappers)

    def test_in_facade_all(self) -> None:
        assert "apply_stage_env_wrappers" in goga.pipeline.__all__

    def test_signature_matches_contract(self) -> None:
        from goga.pipeline import apply_stage_env_wrappers

        signature = inspect.signature(apply_stage_env_wrappers)

        assert list(signature.parameters) == ["stages", "workflow", "global_agent", "flow_path"]

        for name in signature.parameters:
            assert signature.parameters[name].default is inspect.Parameter.empty

    def test_parameter_annotations_match_contract(self) -> None:
        from goga.pipeline import apply_stage_env_wrappers

        signature = inspect.signature(apply_stage_env_wrappers)

        assert signature.parameters["stages"].annotation == "list[FlowStage]"
        assert signature.parameters["workflow"].annotation == "WorkflowDocument | None"
        assert signature.parameters["global_agent"].annotation == "str | None"
        assert signature.parameters["flow_path"].annotation == "Path"

    def test_return_annotation_matches_contract(self) -> None:
        from goga.pipeline import apply_stage_env_wrappers

        signature = inspect.signature(apply_stage_env_wrappers)

        assert signature.return_annotation == "list[FlowStage]"

    def test_module_carries_the_base_constant(self) -> None:
        from goga.pipeline import stage_env_wrappers

        # The tests relocate the wrapper base by rebinding the runtime
        # constant, so the shipped default is locked against the module source.
        source = Path(stage_env_wrappers.__file__).read_text()
        assert '_WRAPPER_BASE = Path("/tmp/goga-stage-env")' in source

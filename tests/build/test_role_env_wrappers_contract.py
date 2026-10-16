"""Contract-surface lock of ``write_role_env_wrappers`` — facade and API shape."""

from __future__ import annotations

import inspect
from pathlib import Path

import goga.build


class TestContract:
    """Contract-surface lock: facade accessibility and API shape."""

    def test_importable_from_facade(self) -> None:
        from goga.build import write_role_env_wrappers

        assert callable(write_role_env_wrappers)

    def test_in_facade_all(self) -> None:
        assert "write_role_env_wrappers" in goga.build.__all__

    def test_signature_matches_contract(self) -> None:
        from goga.build import write_role_env_wrappers

        signature = inspect.signature(write_role_env_wrappers)

        assert list(signature.parameters) == ["settings", "cli_entries"]

        assert signature.parameters["settings"].default is inspect.Parameter.empty
        assert signature.parameters["cli_entries"].default is inspect.Parameter.empty

    def test_parameter_annotations_match_contract(self) -> None:
        from goga.build import write_role_env_wrappers

        signature = inspect.signature(write_role_env_wrappers)

        assert signature.parameters["settings"].annotation == "RunSettings"
        assert signature.parameters["cli_entries"].annotation == "dict[str, str]"

    def test_return_annotation_matches_contract(self) -> None:
        from goga.build import write_role_env_wrappers

        signature = inspect.signature(write_role_env_wrappers)

        assert signature.return_annotation == "dict[str, Path]"

    def test_module_carries_the_base_constant(self) -> None:
        from goga.build import role_env_wrappers

        # The zone-wide wrapper-base relocation rebinds the runtime constant,
        # so the shipped default is locked against the module source itself.
        source = Path(role_env_wrappers.__file__).read_text()
        assert '_WRAPPER_BASE = Path("/tmp/goga-build-env")' in source

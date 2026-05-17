from __future__ import annotations

import inspect
import typing

from goga.schema import schema


class TestSchemaContract:
    def test_schema_importable_from_facade(self) -> None:
        assert callable(schema)

    def test_schema_has_correct_signature(self) -> None:
        sig = inspect.signature(schema)
        params = list(sig.parameters.keys())
        assert params == ["cells", "max_depth", "depends_on"]

    def test_schema_cells_param_type(self) -> None:
        hints = typing.get_type_hints(schema)
        assert hints["cells"] == list[str]

    def test_schema_max_depth_param_type(self) -> None:
        hints = typing.get_type_hints(schema)
        assert hints["max_depth"] == int | None

    def test_schema_depends_on_param_type(self) -> None:
        hints = typing.get_type_hints(schema)
        assert hints["depends_on"] == list[str]

    def test_schema_returns_str(self) -> None:
        hints = typing.get_type_hints(schema)
        assert hints["return"] is str

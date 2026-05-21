"""Contract tests for goga.contract entities."""

import importlib
from dataclasses import fields

import pytest
from goga.contract import (
    BaseContract,
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
    python_contract,
)


class TestFacadeAvailability:
    """Contract: entities must be importable from the package facade."""

    def test_base_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "BaseContract")
        assert mod.BaseContract is BaseContract

    def test_python_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "python_contract")
        assert mod.python_contract is python_contract

    def test_base_contract_has_name_field(self):
        assert hasattr(BaseContract, "name")

    def test_base_contract_has_signature_field(self):
        assert hasattr(BaseContract, "signature")

    def test_base_contract_has_contract_field(self):
        item = BaseContract()
        assert hasattr(item, "contract")

    def test_base_contract_fields_are_str(self):
        field_map = {f.name: f.type for f in fields(BaseContract)}
        assert field_map["name"] is str
        assert field_map["signature"] is str

    def test_base_contract_kw_only(self):
        with pytest.raises(TypeError):
            BaseContract("positional_name", "positional_sig")

    def test_entity_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "EntityContract")
        assert mod.EntityContract is EntityContract

    def test_routine_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "RoutineContract")
        assert mod.RoutineContract is RoutineContract

    def test_property_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "PropertyContract")
        assert mod.PropertyContract is PropertyContract

    def test_method_contract_importable_from_facade(self):
        mod = importlib.import_module("goga.contract")
        assert hasattr(mod, "MethodContract")
        assert mod.MethodContract is MethodContract


class TestBaseContractCreation:
    """Behavioral: BaseContract dataclass creation and defaults."""

    def test_base_contract_creation_with_values(self):
        item = BaseContract(name="test", signature="(x: int) -> str")
        assert item.name == "test"
        assert item.signature == "(x: int) -> str"
        assert item.contract == "test(x: int) -> str"

    def test_base_contract_default_values(self):
        item = BaseContract()
        assert item.name == ""
        assert item.signature == ""
        assert item.contract == ""


class TestPropertyContractFacade:
    """Contract tests: facade availability and contract format."""

    def test_property_contract_format_arrow(self) -> None:
        """PropertyContract.contract must be 'name -> signature'."""
        pc = PropertyContract(name="items", signature="list[str]")
        assert pc.contract == "items -> list[str]"


class TestBaseContractRegression:
    """Regression: BaseContract format must remain 'name{signature}'."""

    def test_base_contract_format_unchanged(self) -> None:
        bc = BaseContract(name="foo", signature="(x: int) -> str")
        assert bc.contract == "foo(x: int) -> str"


class TestMethodContractRegression:
    """Regression: MethodContract format must remain base 'name{signature}'."""

    def test_method_contract_format_unchanged(self) -> None:
        mc = MethodContract(name="calc", signature="(x: int) -> int")
        assert mc.contract == "calc(x: int) -> int"


class TestEntityContractRegression:
    """Regression: EntityContract format must remain base 'name{signature}'."""

    def test_entity_contract_format_unchanged(self) -> None:
        ec = EntityContract(name="Service", signature="(x: int)", properties=[], methods=[])
        assert ec.contract == "Service(x: int)"


class TestRoutineContractRegression:
    """Regression: RoutineContract format must remain base 'name{signature}'."""

    def test_routine_contract_format_unchanged(self) -> None:
        rc = RoutineContract(name="helper", signature="(x: str) -> bool")
        assert rc.contract == "helper(x: str) -> bool"


class TestPropertyContractLogic:
    """Logic tests: edge cases for PropertyContract."""

    def test_empty_signature_edge_case(self) -> None:
        """Empty signature produces 'name -> '."""
        pc = PropertyContract(name="value", signature="")
        assert pc.contract == "value -> "

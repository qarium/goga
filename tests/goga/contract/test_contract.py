"""Contract tests for goga.contract entities."""

from goga.contract import (
    BaseContract,
    EntityContract,
    MethodContract,
    PropertyContract,
    RoutineContract,
)


class TestPropertyContractFacade:
    """Contract tests: facade availability and contract format."""

    def test_property_contract_importable(self) -> None:
        """PropertyContract must be importable from goga.contract."""
        assert PropertyContract is not None

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

    def test_base_post_init_not_called(self) -> None:
        """PropertyContract must NOT use BaseContract format."""
        pc = PropertyContract(name="x", signature="int")
        # Base format would be "xint"; arrow format is "x -> int"
        assert pc.contract != f"{pc.name}{pc.signature}"
        assert " -> " in pc.contract

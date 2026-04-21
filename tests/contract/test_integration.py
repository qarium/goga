"""Integration tests for goga.contract package."""

import json

from goga.contract import EntityContract, RoutineContract, python_contract


class TestSelfReference:
    """python_contract extracts the facade of its own package."""

    def test_self_contract_contains_base_contract(self):
        result = python_contract("goga/contract")
        names = [item.name for item in result]
        assert "BaseContract" in names

    def test_self_contract_contains_python_contract(self):
        result = python_contract("goga/contract")
        names = [item.name for item in result]
        assert "python_contract" in names

    def test_self_contract_base_contract_is_entity(self):
        result = python_contract("goga/contract")
        base = next(item for item in result if item.name == "BaseContract")
        assert isinstance(base, EntityContract)

    def test_self_contract_python_contract_is_routine(self):
        result = python_contract("goga/contract")
        fn = next(item for item in result if item.name == "python_contract")
        assert isinstance(fn, RoutineContract)


class TestRealPackageExtraction:
    """python_contract extracts facade from a real project submodule."""

    def test_ast_factory_has_factory(self):
        result = python_contract("goga/ast/factory")
        assert len(result) > 0
        names = [item.name for item in result]
        assert "Factory" in names

    def test_ast_factory_all_items_have_name_and_signature(self):
        result = python_contract("goga/ast/factory")
        for item in result:
            assert item.name != ""
            assert item.signature != ""


class TestSignatureFormatMatchesContractFormat:
    """Result is serializable to contract_format: [{"name": "...", "signature": "..."}]."""

    def test_result_serializable_to_json(self):
        result = python_contract("goga/contract")
        data = [{"name": item.name, "signature": item.signature} for item in result]
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        assert parsed == data

"""Contract and behavioral tests for kotlin_contract — Kotlin package facade extraction via tree-sitter."""

import importlib.util

import pytest
from goga.contract import EntityContract, RoutineContract

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_kotlin") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter-kotlin not installed",
)


class TestKotlinContractFacade:
    """Contract tests: kotlin_contract is importable and callable."""

    def test_kotlin_contract_importable_from_subcell(self):
        from goga.contract.kotlin import kotlin_contract

        assert callable(kotlin_contract)

    def test_kotlin_contract_importable_from_facade(self):
        from goga.contract import kotlin_contract

        assert callable(kotlin_contract)

    @requires_tree_sitter
    def test_kotlin_returns_list(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        result = kotlin_contract(str(tmp_path))
        assert isinstance(result, list)
        assert result == []


@requires_tree_sitter
class TestKotlinContractExtractsExportedClass:
    def test_kotlin_extracts_exported_class(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "UserService.kt").write_text(
            "class UserService(val name: String) {\n"
            "    fun greet(): String = \"Hello $name\"\n"
            "}\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        svc = entities[0]
        assert svc.name == "UserService"
        assert svc.signature == "(name: String)"
        method_names = [m.name for m in svc.methods]
        assert "greet" in method_names


@requires_tree_sitter
class TestKotlinContractExtractsDataClass:
    def test_kotlin_extracts_data_class(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Point.kt").write_text("data class Point(val x: Double, val y: Double)\n")
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        point = entities[0]
        assert point.name == "Point"
        assert point.signature == "(x: Double, y: Double)"
        assert len(point.methods) == 0


@requires_tree_sitter
class TestKotlinContractExtractsTopLevelFunction:
    def test_kotlin_extracts_top_level_function(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Utils.kt").write_text(
            "fun formatName(firstName: String, lastName: String): String "
            '= "$firstName $lastName"\n'
        )
        result = kotlin_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "formatName"
        assert result[0].signature == "(firstName: String, lastName: String) -> String"


@requires_tree_sitter
class TestKotlinContractExtractsObjectDeclaration:
    def test_kotlin_extracts_object_declaration(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Config.kt").write_text(
            "object Config {\n"
            "    val host: String = \"localhost\"\n"
            "    fun load(): Config = this\n"
            "}\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        config = entities[0]
        assert config.name == "Config"
        assert config.signature == "()"


@requires_tree_sitter
class TestKotlinContractAttachesExtensionFunctions:
    def test_kotlin_attaches_extension_functions(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "User.kt").write_text(
            "class User\n\nfun User.greet(): String = \"Hello\"\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        user = entities[0]
        assert user.name == "User"
        method_names = [m.name for m in user.methods]
        assert "greet" in method_names


@requires_tree_sitter
class TestKotlinContractNullableTypes:
    def test_kotlin_nullable_types_in_signature(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Repo.kt").write_text(
            "class Repo {\n"
            "    fun find(id: String): String? = null\n"
            "}\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        repo = entities[0]
        find_method = next(m for m in repo.methods if m.name == "find")
        assert "String?" in find_method.signature


@requires_tree_sitter
class TestKotlinContractExtractsSealedClass:
    def test_kotlin_extracts_sealed_class(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Result.kt").write_text("sealed class Result\n")
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        assert entities[0].name == "Result"


@requires_tree_sitter
class TestKotlinContractIgnoresCompanionObject:
    def test_kotlin_ignores_companion_object(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Factory.kt").write_text(
            "class Factory {\n"
            "    companion object {\n"
            "        fun create(): Factory = Factory()\n"
            "    }\n"
            "}\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        factory = entities[0]
        assert factory.name == "Factory"
        method_names = [m.name for m in factory.methods]
        assert "create" not in method_names


@requires_tree_sitter
class TestKotlinContractIgnoresInternal:
    def test_kotlin_ignores_internal_class(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Internal.kt").write_text("internal class InternalService\n")
        result = kotlin_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestKotlinContractIgnoresPrivateFunction:
    def test_kotlin_ignores_private_function(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Hidden.kt").write_text("private fun secret(): String = \"shh\"\n")
        result = kotlin_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestKotlinContractEmptyDirectory:
    def test_kotlin_empty_directory(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        result = kotlin_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestKotlinContractEmptyFile:
    def test_kotlin_empty_file(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "empty.kt").write_text("")
        result = kotlin_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestKotlinContractStableOrder:
    def test_kotlin_stable_order(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Order.kt").write_text(
            "fun Zebra() {}\n\nfun Alpha() {}\n\nfun Middle() {}\n"
        )
        result1 = kotlin_contract(str(tmp_path))
        result2 = kotlin_contract(str(tmp_path))
        names1 = [r.name for r in result1]
        names2 = [r.name for r in result2]
        assert names1 == ["Alpha", "Middle", "Zebra"]
        assert names1 == names2


@requires_tree_sitter
class TestKotlinContractMultipleFilesMerged:
    def test_kotlin_multiple_files_merged(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "funcs.kt").write_text("fun hello(): String = \"hi\"\n")
        (tmp_path / "types.kt").write_text("data class Item(val name: String)\n")
        result = kotlin_contract(str(tmp_path))
        names = [r.name for r in result]
        assert "hello" in names
        assert "Item" in names


@requires_tree_sitter
class TestKotlinContractClassWithNullableParams:
    def test_kotlin_class_with_nullable_params(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Service.kt").write_text(
            "class Service(val host: String?, val port: Int?)\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        service = entities[0]
        assert service.name == "Service"
        assert "String?" in service.signature
        assert "Int?" in service.signature


@requires_tree_sitter
class TestKotlinContractNullableExtensionFunction:
    def test_kotlin_nullable_receiver_extension_attached(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Utils.kt").write_text(
            "class User\n\nfun User?.orDefault(): String = this ?: \"default\"\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        user = entities[0]
        assert user.name == "User"
        method_names = [m.name for m in user.methods]
        assert "orDefault" in method_names
        # Should NOT appear as a top-level routine
        routines = [r for r in result if isinstance(r, RoutineContract)]
        assert len(routines) == 0


@requires_tree_sitter
class TestKotlinContractExtractsInterface:
    def test_kotlin_extracts_interface(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Repo.kt").write_text(
            "interface Repository {\n"
            "    fun save(data: String)\n"
            "    fun load(id: String): String?\n"
            "}\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        repo = entities[0]
        assert repo.name == "Repository"


@requires_tree_sitter
class TestKotlinContractExtractsAnnotationClass:
    def test_kotlin_extracts_annotation_class(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "Annotations.kt").write_text("annotation class Fancy\n")
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        assert entities[0].name == "Fancy"
        assert entities[0].signature == "()"


@requires_tree_sitter
class TestKotlinContractMixedDeclarationsInOneFile:
    """Integration: multiple declaration types in a single .kt file are correctly separated."""

    def test_kotlin_mixed_declarations_in_one_file(self, tmp_path):
        from goga.contract.kotlin import kotlin_contract

        (tmp_path / "App.kt").write_text(
            "class UserService(val name: String) {\n"
            "    fun greet(): String = \"Hello\"\n"
            "}\n\n"
            "object Config {\n"
            "    val host: String = \"localhost\"\n"
            "    fun load(): Config = this\n"
            "}\n\n"
            "fun formatName(first: String, last: String): String = \"$first $last\"\n"
        )
        result = kotlin_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        routines = [r for r in result if isinstance(r, RoutineContract)]
        entity_names = {e.name for e in entities}
        assert "UserService" in entity_names
        assert "Config" in entity_names
        assert len(routines) == 1
        assert routines[0].name == "formatName"
        # UserService should have greet method
        user_svc = next(e for e in entities if e.name == "UserService")
        assert any(m.name == "greet" for m in user_svc.methods)

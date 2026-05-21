"""Contract and behavioral tests for swift_contract — Swift package facade extraction via tree-sitter."""

import importlib.util

import pytest
from goga.contract import EntityContract, RoutineContract

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_swift") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter-swift not installed",
)


class TestSwiftContractFacade:
    """Contract tests: swift_contract is importable and callable."""

    def test_swift_contract_importable_from_subcell(self):
        from goga.contract.swift import swift_contract

        assert callable(swift_contract)

    def test_swift_contract_importable_from_facade(self):
        from goga.contract import swift_contract

        assert callable(swift_contract)

    @requires_tree_sitter
    def test_swift_returns_list(self, tmp_path):
        from goga.contract.swift import swift_contract

        result = swift_contract(str(tmp_path))
        assert isinstance(result, list)
        assert result == []


@requires_tree_sitter
class TestSwiftContractExtractsPublicClass:
    def test_swift_extracts_public_class(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Server.swift").write_text(
            "public class Server {\n"
            "    public init(host: String, port: Int) {}\n"
            "    public func start() -> Bool { return true }\n"
            "    public var name: String = \"\"\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        svc = entities[0]
        assert svc.name == "Server"
        assert svc.signature == "(host: String, port: Int)"
        method_names = [m.name for m in svc.methods]
        assert "start" in method_names
        prop_names = [p.name for p in svc.properties]
        assert "name" in prop_names


@requires_tree_sitter
class TestSwiftContractExtractsPublicEnum:
    def test_swift_extracts_public_enum(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Status.swift").write_text(
            "public enum Status {\n"
            "    case active\n"
            "    case inactive\n"
            "    case pending\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        status = entities[0]
        assert status.name == "Status"
        assert status.signature == "()"
        prop_names = [p.name for p in status.properties]
        assert "active" in prop_names
        assert "inactive" in prop_names
        assert "pending" in prop_names
        assert len(status.methods) == 0


@requires_tree_sitter
class TestSwiftContractExtractsPublicStruct:
    def test_swift_extracts_public_struct(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Point.swift").write_text(
            "public struct Point {\n"
            "    public var x: Double = 0\n"
            "    public var y: Double = 0\n"
            "    public init(x: Double, y: Double) {}\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        point = entities[0]
        assert point.name == "Point"
        assert point.signature == "(x: Double, y: Double)"


@requires_tree_sitter
class TestSwiftContractExtractsPublicFunction:
    def test_swift_extracts_public_function(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Utils.swift").write_text(
            'public func greet(name: String) -> String { return name }\n'
        )
        result = swift_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "greet"
        assert result[0].signature == "(name: String) -> String"


@requires_tree_sitter
class TestSwiftContractExtractsProtocol:
    def test_swift_extracts_protocol(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Handler.swift").write_text(
            "public protocol Handler {\n"
            "    func process(data: String) -> Bool\n"
            "    func cleanup()\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        handler = entities[0]
        assert handler.name == "Handler"
        assert handler.signature == "()"
        assert len(handler.properties) == 0
        method_names = [m.name for m in handler.methods]
        assert "process" in method_names
        assert "cleanup" in method_names


@requires_tree_sitter
class TestSwiftContractOptionalTypes:
    def test_swift_optional_types_in_signature(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Repo.swift").write_text(
            "public class Repo {\n"
            '    public func find(id: String) -> String? { return nil }\n'
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        repo = entities[0]
        find_method = next(m for m in repo.methods if m.name == "find")
        assert "String?" in find_method.signature


@requires_tree_sitter
class TestSwiftContractExternalParamNames:
    def test_swift_function_external_param_names(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Config.swift").write_text(
            "public func configure(with host: String, port: Int) {}\n"
        )
        result = swift_contract(str(tmp_path))
        assert len(result) == 1
        func = result[0]
        assert func.name == "configure"
        assert "with host: String" in func.signature
        assert "port: Int" in func.signature


@requires_tree_sitter
class TestSwiftContractExtractsPublicActor:
    def test_swift_extracts_public_actor(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Worker.swift").write_text(
            "public actor Worker {\n"
            "    public func process() {}\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        worker = entities[0]
        assert worker.name == "Worker"
        method_names = [m.name for m in worker.methods]
        assert "process" in method_names


@requires_tree_sitter
class TestSwiftContractFailableInit:
    def test_swift_failable_init(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Parser.swift").write_text(
            "public class Parser {\n"
            "    public init?(path: String) {}\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        parser_entity = entities[0]
        assert parser_entity.name == "Parser"
        assert parser_entity.signature == "(path: String)"


@requires_tree_sitter
class TestSwiftContractComputedProperty:
    def test_swift_computed_property_type(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "User.swift").write_text(
            "public class User {\n"
            '    public var displayName: String { return "" }\n'
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        user = entities[0]
        prop = next(p for p in user.properties if p.name == "displayName")
        assert prop.signature == "String"


@requires_tree_sitter
class TestSwiftContractNonPublicInitSkipped:
    def test_swift_non_public_init_skipped(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Service.swift").write_text(
            "public class Service {\n"
            "    private init(host: String, port: Int) {}\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        svc = entities[0]
        assert svc.name == "Service"
        assert svc.signature == "()"


@requires_tree_sitter
class TestSwiftContractIgnoresInternal:
    def test_swift_ignores_internal_decl(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Internal.swift").write_text("class InternalService {}\n")
        result = swift_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestSwiftContractIgnoresExtension:
    def test_swift_ignores_extension(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Ext.swift").write_text(
            "extension String {\n"
            "    public func greet() {}\n"
            "}\n"
        )
        result = swift_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestSwiftContractEmptyDirectory:
    def test_swift_empty_directory(self, tmp_path):
        from goga.contract.swift import swift_contract

        result = swift_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestSwiftContractEmptyFile:
    def test_swift_empty_file(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "empty.swift").write_text("")
        result = swift_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestSwiftContractStableOrder:
    def test_swift_stable_order(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "Order.swift").write_text(
            "public func Zebra() {}\n\n"
            "public func Alpha() {}\n\n"
            "public func Middle() {}\n"
        )
        result1 = swift_contract(str(tmp_path))
        result2 = swift_contract(str(tmp_path))
        names1 = [r.name for r in result1]
        names2 = [r.name for r in result2]
        assert names1 == ["Alpha", "Middle", "Zebra"]
        assert names1 == names2


@requires_tree_sitter
class TestSwiftContractMultipleFilesMerged:
    def test_swift_multiple_files_merged(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "funcs.swift").write_text(
            'public func hello() -> String { return "hi" }\n'
        )
        (tmp_path / "types.swift").write_text("public struct Item {}\n")
        result = swift_contract(str(tmp_path))
        names = [r.name for r in result]
        assert "hello" in names
        assert "Item" in names


@requires_tree_sitter
class TestSwiftContractOpenClassIncluded:
    def test_swift_open_class_included(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "BaseView.swift").write_text("open class BaseView {}\n")
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        assert entities[0].name == "BaseView"


@requires_tree_sitter
class TestSwiftContractMixedDeclarationsInOneFile:
    """Integration: multiple declaration types in a single .swift file are correctly separated."""

    def test_swift_mixed_declarations_in_one_file(self, tmp_path):
        from goga.contract.swift import swift_contract

        (tmp_path / "App.swift").write_text(
            "public class Server {\n"
            "    public init(host: String) {}\n"
            "    public func start() -> Bool { return true }\n"
            "}\n\n"
            "public struct Point {\n"
            "    public var x: Double = 0\n"
            "}\n\n"
            "public protocol Handler {\n"
            "    func process(data: String) -> Bool\n"
            "}\n\n"
            "public func greet(name: String) -> String { return name }\n"
        )
        result = swift_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        routines = [r for r in result if isinstance(r, RoutineContract)]
        entity_names = {e.name for e in entities}
        assert "Server" in entity_names
        assert "Point" in entity_names
        assert "Handler" in entity_names
        assert len(routines) == 1
        assert routines[0].name == "greet"
        # Server should have start method
        server = next(e for e in entities if e.name == "Server")
        assert any(m.name == "start" for m in server.methods)
        # Handler should only have methods, no properties
        handler = next(e for e in entities if e.name == "Handler")
        assert len(handler.properties) == 0
        assert any(m.name == "process" for m in handler.methods)

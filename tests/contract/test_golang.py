"""Contract and behavioral tests for golang_contract — Go package facade extraction via tree-sitter."""

import importlib.util

import pytest
from goga.contract import EntityContract, RoutineContract

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_go") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter not installed",
)


class TestGolangContractFacade:
    """Contract tests: golang_contract is importable and callable."""

    def test_importable_from_subcell(self):
        from goga.contract.golang import golang_contract

        assert callable(golang_contract)

    def test_importable_from_facade(self):
        from goga.contract import golang_contract

        assert callable(golang_contract)

    @requires_tree_sitter
    def test_returns_list(self, tmp_path):
        from goga.contract.golang import golang_contract

        result = golang_contract(str(tmp_path))
        assert isinstance(result, list)

    @requires_tree_sitter
    def test_accepts_single_string_arg(self, tmp_path):
        from goga.contract.golang import golang_contract

        golang_contract(str(tmp_path))


@requires_tree_sitter
class TestGolangContractExtractsExportedFunction:
    def test_extracts_exported_function(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "service.go").write_text(
            'package cell\n\nfunc Hello(name string) string {\n    return "Hello " + name\n}\n'
        )
        result = golang_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "Hello"
        assert result[0].signature == "(name: string) -> string"


@requires_tree_sitter
class TestGolangContractExtractsStructWithFieldsAndMethods:
    def test_extracts_struct_with_fields_and_methods(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "model.go").write_text(
            "package cell\n\ntype Server struct {\n    Name string\n    Port int\n}\n"
        )
        (tmp_path / "methods.go").write_text(
            "package cell\n\nfunc (s *Server) Start() error {\n    return nil\n}\n\n"
            "func (s *Server) Stop() {\n}\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        server = entities[0]
        assert server.name == "Server"
        assert len(server.properties) == 2
        prop_names = [p.name for p in server.properties]
        assert "Name" in prop_names
        assert "Port" in prop_names
        name_prop = next(p for p in server.properties if p.name == "Name")
        assert name_prop.signature == "string"
        assert len(server.methods) == 2
        start = next(m for m in server.methods if m.name == "Start")
        assert start.signature == "() -> error"
        stop = next(m for m in server.methods if m.name == "Stop")
        assert stop.signature == "()"
        method_names = [m.name for m in server.methods]
        assert "Start" in method_names
        assert "Stop" in method_names


@requires_tree_sitter
class TestGolangContractExtractsInterface:
    def test_extracts_interface(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "api.go").write_text(
            "package cell\n\ntype Handler interface {\n    Serve(data string) error\n    Close()\n}\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        handler = entities[0]
        assert handler.name == "Handler"
        assert len(handler.methods) == 2
        method_names = [m.name for m in handler.methods]
        assert "Serve" in method_names
        assert "Close" in method_names


@requires_tree_sitter
class TestGolangContractIgnoresUnexported:
    def test_ignores_unexported(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "internal.go").write_text(
            "package cell\n\nfunc helper(x int) int {\n    return x\n}\n\n"
            "type privateStruct struct {\n    field string\n}\n"
        )
        result = golang_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestGolangContractIgnoresTestFiles:
    def test_ignores_test_files(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "service.go").write_text(
            'package cell\n\nfunc Hello() string {\n    return "hi"\n}\n'
        )
        (tmp_path / "service_test.go").write_text(
            "package cell\n\nfunc TestHello(t *testing.T) {\n    // test\n}\n"
        )
        result = golang_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "Hello"


@requires_tree_sitter
class TestGolangContractMultipleFilesMerged:
    def test_multiple_files_merged(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "funcs.go").write_text(
            "package cell\n\nfunc Create(name string) error {\n    return nil\n}\n"
        )
        (tmp_path / "types.go").write_text(
            "package cell\n\ntype Config struct {\n    Name string\n}\n"
        )
        result = golang_contract(str(tmp_path))
        names = [r.name for r in result]
        assert "Config" in names
        assert "Create" in names


@requires_tree_sitter
class TestGolangContractNoGoFiles:
    def test_no_go_files(self, tmp_path):
        from goga.contract.golang import golang_contract

        result = golang_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestGolangContractEmptyGoFile:
    def test_empty_go_file(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "empty.go").write_text("package cell\n")
        result = golang_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestGolangContractFunctionNoParamsNoReturn:
    def test_function_no_params_no_return(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "simple.go").write_text("package cell\n\nfunc DoNothing() {\n}\n")
        result = golang_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "DoNothing"
        assert result[0].signature == "()"


@requires_tree_sitter
class TestGolangContractValueAndPointerReceiver:
    def test_value_and_pointer_receiver(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "mixed.go").write_text(
            "package cell\n\n"
            "type Data struct {\n    Value int\n}\n\n"
            "func (d Data) GetValue() int {\n    return d.Value\n}\n\n"
            "func (d *Data) SetValue(v int) {\n    d.Value = v\n}\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        data = entities[0]
        method_names = [m.name for m in data.methods]
        assert "GetValue" in method_names
        assert "SetValue" in method_names


@requires_tree_sitter
class TestGolangContractStableOrder:
    def test_stable_order(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "order.go").write_text(
            "package cell\n\nfunc Zebra() {}\n\nfunc Alpha() {}\n\nfunc Middle() {}\n"
        )
        result1 = golang_contract(str(tmp_path))
        result2 = golang_contract(str(tmp_path))
        names1 = [r.name for r in result1]
        names2 = [r.name for r in result2]
        assert names1 == ["Alpha", "Middle", "Zebra"]
        assert names1 == names2


@requires_tree_sitter
class TestGolangContractMixedExportedFields:
    def test_only_exported_fields_included(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "mixed.go").write_text(
            "package cell\n\ntype Mixed struct {\n"
            "    Exported string\n"
            "    unexported int\n"
            "}\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        mixed = entities[0]
        assert len(mixed.properties) == 1
        assert mixed.properties[0].name == "Exported"
        assert mixed.properties[0].signature == "string"


@requires_tree_sitter
class TestGolangContractVariadicParams:
    def test_variadic_params_included(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "varargs.go").write_text(
            "package cell\n\nfunc Sum(nums ...int) int {\n    return 0\n}\n"
        )
        result = golang_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "Sum"
        assert "nums" in result[0].signature


@requires_tree_sitter
class TestGolangContractGroupedParams:
    def test_grouped_params_all_names_extracted(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "shared.go").write_text(
            "package cell\n\nfunc Swap(a, b int) (int, int) {\n    return b, a\n}\n"
        )
        result = golang_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "Swap"
        assert "a: int" in result[0].signature
        assert "b: int" in result[0].signature


@requires_tree_sitter
class TestGolangContractGroupedTypeDeclarations:
    def test_grouped_type_block_all_extracted(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "types.go").write_text(
            "package cell\n\ntype (\n"
            "    Server struct { Name string }\n"
            "    Handler interface { Serve() }\n"
            ")\n"
        )
        result = golang_contract(str(tmp_path))
        names = [r.name for r in result]
        assert "Server" in names
        assert "Handler" in names


@requires_tree_sitter
class TestGolangContractIgnoresUnexportedMethods:
    def test_unexported_methods_excluded(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "svc.go").write_text(
            "package cell\n\ntype Server struct { Name string }\n\n"
            "func (s *Server) Hello() string { return \"hi\" }\n\n"
            "func (s *Server) privateHelper() string { return \"secret\" }\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        server = entities[0]
        method_names = [m.name for m in server.methods]
        assert "Hello" in method_names
        assert "privateHelper" not in method_names


@requires_tree_sitter
class TestGolangContractGenericReceiver:
    def test_methods_attached_to_generic_struct(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "generic.go").write_text(
            "package cell\n\n"
            "type Container[T any] struct {\n    Value T\n}\n\n"
            "func (c *Container[T]) Get() T {\n    return c.Value\n}\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        container = entities[0]
        assert container.name == "Container"
        method_names = [m.name for m in container.methods]
        assert "Get" in method_names


@requires_tree_sitter
class TestGolangContractMethodsOnlyAttachToStructs:
    def test_methods_not_attached_to_interface(self, tmp_path):
        from goga.contract.golang import golang_contract

        (tmp_path / "iface.go").write_text(
            "package cell\n\n"
            "type Handler interface {\n    Serve()\n}\n\n"
            "func (h Handler) DoWork() {}\n"
        )
        result = golang_contract(str(tmp_path))
        entities = [r for r in result if isinstance(r, EntityContract)]
        assert len(entities) == 1
        handler = entities[0]
        assert handler.name == "Handler"
        method_names = [m.name for m in handler.methods]
        assert "Serve" in method_names
        assert "DoWork" not in method_names

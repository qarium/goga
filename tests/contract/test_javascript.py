"""Contract and behavioral tests for javascript_contract — JavaScript module facade extraction via tree-sitter."""

import importlib.util

import pytest
from goga.contract import EntityContract, RoutineContract

HAS_TREE_SITTER = importlib.util.find_spec("tree_sitter_javascript") is not None

requires_tree_sitter = pytest.mark.skipif(
    not HAS_TREE_SITTER,
    reason="tree-sitter-javascript not installed",
)


class TestJavascriptContractFacade:
    """Contract tests: javascript_contract is importable and callable."""

    def test_javascript_contract_importable_from_subcell(self):
        from goga.contract.javascript import javascript_contract

        assert callable(javascript_contract)

    def test_javascript_contract_returns_list(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        result = javascript_contract(str(tmp_path))
        assert isinstance(result, list)


@requires_tree_sitter
class TestJavascriptContractSignature:
    def test_javascript_contract_accepts_single_string_arg(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        javascript_contract(str(tmp_path))


@requires_tree_sitter
class TestExtractsExportedFunction:
    def test_extracts_exported_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export function hello(name) {\n  return name;\n}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "hello"
        assert result[0].signature == "(name)"


@requires_tree_sitter
class TestExtractsExportedFunctionWithJsdoc:
    def test_extracts_exported_function_with_jsdoc(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/**\n * @param {string} name\n * @returns {number}\n */\n"
            "export function calculate(name) {\n  return 42;\n}\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert isinstance(routine, RoutineContract)
        assert routine.name == "calculate"
        assert routine.signature == "(name: string) -> number"


@requires_tree_sitter
class TestExtractsExportedClass:
    def test_extracts_exported_class(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export class Server {\n  constructor(host) {}\n  start() {}\n}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        assert isinstance(entity, EntityContract)
        assert entity.name == "Server"
        assert entity.signature == "()"
        assert len(entity.methods) == 2
        method_names = [m.name for m in entity.methods]
        assert "constructor" in method_names
        assert "start" in method_names


@requires_tree_sitter
class TestExtractsClassWithFields:
    def test_extracts_class_with_fields(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/**\n * @type {string}\n */\n"
            "export class Config {\n"
            "  /** @type {number} */\n"
            "  port;\n"
            "  /** @type {string} */\n"
            "  host;\n"
            "}\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        assert isinstance(entity, EntityContract)
        assert entity.name == "Config"
        prop_names = [p.name for p in entity.properties]
        assert "port" in prop_names
        assert "host" in prop_names
        port_prop = next(p for p in entity.properties if p.name == "port")
        assert port_prop.signature == "number"


@requires_tree_sitter
class TestCommonjsObjectExports:
    def test_commonjs_object_exports(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = {\n  create(name) {},\n  destroy() {},\n};\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 2
        names = [r.name for r in result]
        assert "create" in names
        assert "destroy" in names
        for r in result:
            assert isinstance(r, RoutineContract)


@requires_tree_sitter
class TestCommonjsIdentifierExport:
    def test_commonjs_identifier_export(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("function helper(x) {}\nmodule.exports = helper;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "helper"
        assert result[0].signature == "(x)"


@requires_tree_sitter
class TestNamedReexport:
    def test_named_reexport(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("function foo() {}\nfunction bar() {}\nexport { foo, bar };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 2
        names = [r.name for r in result]
        assert "foo" in names
        assert "bar" in names


@requires_tree_sitter
class TestNamedReexportWithAlias:
    def test_named_reexport_with_alias(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("function foo() {}\nexport { foo as bar };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "bar"


@requires_tree_sitter
class TestStableOrder:
    def test_stable_order(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "export function zebra() {}\nexport function alpha() {}\nexport function middle() {}\n"
        )
        result1 = javascript_contract(str(tmp_path))
        result2 = javascript_contract(str(tmp_path))
        names1 = [r.name for r in result1]
        names2 = [r.name for r in result2]
        assert names1 == ["alpha", "middle", "zebra"]
        assert names1 == names2


@requires_tree_sitter
class TestExportDefaultClass:
    def test_export_default_class(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default class {\n  constructor(x) {}\n}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "default"


@requires_tree_sitter
class TestExportDefaultFunction:
    def test_export_default_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default function() {}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "default"


@requires_tree_sitter
class TestNoIndexJs:
    def test_no_index_js(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        result = javascript_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestEmptyIndexJs:
    def test_empty_index_js(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("")
        result = javascript_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestNoExports:
    def test_no_exports(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("function internal(x) {}\nclass Private {}\n")
        result = javascript_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestPrivateClassMembersExcluded:
    def test_private_class_members_excluded(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export class MyClass {\n  #privateMethod() {}\n  publicMethod() {}\n}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        method_names = [m.name for m in entity.methods]
        assert "publicMethod" in method_names
        assert "privateMethod" not in method_names


@requires_tree_sitter
class TestExportDefaultIdentifierSkipped:
    def test_export_default_identifier_skipped(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const foo = 42;\nexport default foo;\n")
        result = javascript_contract(str(tmp_path))
        assert result == []


@requires_tree_sitter
class TestFunctionWithDefaultParams:
    def test_function_with_default_params(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export function configure(host, port = 8080) {}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert "host" in routine.signature
        assert "port" in routine.signature


@requires_tree_sitter
class TestClassNoJsdocEmptyTypes:
    def test_class_no_jsdoc_empty_types(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export class Data {\n  value;\n}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        assert len(entity.properties) == 1
        assert entity.properties[0].name == "value"
        assert entity.properties[0].signature == ""


@requires_tree_sitter
class TestMixedEsmAndCommonjs:
    def test_mixed_esm_and_commonjs(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export function main() {}\nmodule.exports.fallback = function() {};\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        names = [r.name for r in result]
        assert "main" in names
        assert "fallback" not in names


@requires_tree_sitter
class TestParamWithoutJsdoc:
    def test_param_without_jsdoc(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("/**\n * @param {string} name\n */\nexport function greet(name, age) {}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert "name: string" in routine.signature
        assert "age" in routine.signature


@requires_tree_sitter
class TestExportDefaultArrowFunction:
    def test_export_default_arrow_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default (x) => x;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "default"
        assert "x" in result[0].signature

    def test_export_default_arrow_function_with_jsdoc(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/**\n * @param {string} x\n * @returns {number}\n */\nexport default (x) => x;\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert routine.name == "default"
        assert "x: string" in routine.signature
        assert "-> number" in routine.signature


@requires_tree_sitter
class TestVariableDeclaratorReexport:
    def test_const_function_reexport(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const handler = function(x) { return x; };\nexport { handler };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "handler"
        assert "x" in result[0].signature

    def test_const_function_reexport_with_jsdoc(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/**\n * @param {string} x\n * @returns {boolean}\n */\nconst handler = (x) => x;\nexport { handler };\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert "x: string" in routine.signature
        assert "-> boolean" in routine.signature

    def test_const_class_reexport(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const App = class { run() {} };\nexport { App };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "App"
        assert len(result[0].methods) == 1
        assert result[0].methods[0].name == "run"


@requires_tree_sitter
class TestCommonjsPairNodes:
    def test_commonjs_pair_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = {\n  handler: function(x) { return x; },\n};\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "handler"
        assert "x" in result[0].signature


@requires_tree_sitter
class TestGeneratorFunction:
    def test_export_generator_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export function* generate(n) {}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "generate"
        assert "n" in result[0].signature


@requires_tree_sitter
class TestClassAliasReexport:
    def test_export_class_with_alias(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("class Foo { run() {} }\nexport { Foo as Bar };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "Bar"
        assert len(result[0].methods) == 1
        assert result[0].methods[0].name == "run"


@requires_tree_sitter
class TestCommonjsClassExport:
    def test_commonjs_class_identifier_export(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("class Database { connect() {} }\nmodule.exports = Database;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "Database"
        assert len(result[0].methods) == 1
        assert result[0].methods[0].name == "connect"


@requires_tree_sitter
class TestRestParameters:
    def test_rest_parameter_extracted(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export function log(message, ...args) {}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert "message" in routine.signature
        assert "...args" in routine.signature


@requires_tree_sitter
class TestDestructuredParameters:
    def test_destructured_parameter_extracted(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export function configure({ host, port }) {}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert "{ host, port }" in routine.signature


@requires_tree_sitter
class TestArrowWithoutParens:
    def test_arrow_single_param_no_parens(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default x => x;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "default"
        assert "(x)" in result[0].signature

    def test_arrow_single_param_no_parens_via_reexport(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const double = x => x * 2;\nexport { double };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "double"
        assert "(x)" in result[0].signature


@requires_tree_sitter
class TestExportDefaultAnonymousGenerator:
    def test_export_default_generator_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default function*() { yield 1; }\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "default"

    def test_export_default_generator_with_params(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default function*(items) { yield items; }\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert "(items)" in result[0].signature


@requires_tree_sitter
class TestCommonJSDirectArrowExport:
    def test_module_exports_arrow_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = (x) => x;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "default"
        assert "(x)" in result[0].signature

    def test_module_exports_arrow_no_parens(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = x => x;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "default"
        assert "(x)" in result[0].signature


@requires_tree_sitter
class TestCommonJSDirectClassExport:
    def test_module_exports_anonymous_class(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = class { connect() {} };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "default"
        assert len(result[0].methods) == 1
        assert result[0].methods[0].name == "connect"

    def test_module_exports_named_class_expression(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = class App { run() {} };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "default"


@requires_tree_sitter
class TestShorthandPropertyIdentifier:
    def test_commonjs_shorthand_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("function foo() {}\nmodule.exports = { foo };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "foo"

    def test_commonjs_shorthand_variable(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const handler = (x) => x;\nmodule.exports = { handler };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], RoutineContract)
        assert result[0].name == "handler"
        assert "(x)" in result[0].signature


@requires_tree_sitter
class TestNamedDefaultExport:
    def test_export_default_named_function(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default function myFunc(x) { return x; }\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "default"
        assert "(x)" in result[0].signature

    def test_export_default_named_class(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export default class MyApp { run() {} }\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "default"


@requires_tree_sitter
class TestRestParameterJsdoc:
    def test_rest_param_with_jsdoc_type(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/**\n"
            " * @param {string} message\n"
            " * @param {...any} args\n"
            " * @returns {void}\n"
            " */\n"
            "export function log(message, ...args) {}\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        routine = result[0]
        assert "message: string" in routine.signature
        assert "...args: ...any" in routine.signature
        assert "-> void" in routine.signature


@requires_tree_sitter
class TestNestedJsdocTypes:
    def test_nested_object_type(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "export class Config {\n  /** @type {{host: string, port: number}} */\n  config;\n}\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        assert len(entity.properties) == 1
        assert entity.properties[0].signature == "{host: string, port: number}"

    def test_generic_type(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/** @returns {Array<{id: number}>} */\nexport function list() { return []; }\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert "Array<{id: number}>" in result[0].signature


@requires_tree_sitter
class TestEntityMethodPropertySorting:
    def test_methods_sorted_within_entity(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("export class Svc {\n  zeta() {}\n  alpha() {}\n  beta() {}\n}\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        names = [m.name for m in entity.methods]
        assert names == ["alpha", "beta", "zeta"]

    def test_properties_sorted_within_entity(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "export class Config {\n  /** @type {string} */\n  z;\n  /** @type {number} */\n  a;\n}\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        entity = result[0]
        names = [p.name for p in entity.properties]
        assert names == ["a", "z"]


@requires_tree_sitter
class TestCommonJsVariableDeclaratorClass:
    def test_commonjs_identifier_variable_class_expression(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const App = class { run() {} };\nmodule.exports = App;\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "App"
        assert len(result[0].methods) == 1
        assert result[0].methods[0].name == "run"

    def test_commonjs_shorthand_variable_class_expression(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("const Svc = class { start() {} };\nmodule.exports = { Svc };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "Svc"


@requires_tree_sitter
class TestCommonJsShorthandClassDeclaration:
    def test_commonjs_shorthand_class_declaration(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "class MyService { start() {} stop() {} }\nmodule.exports = { MyService };\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "MyService"
        assert len(result[0].methods) == 2


@requires_tree_sitter
class TestJsdocThroughRegularComment:
    def test_jsdoc_found_past_regular_comment(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/**\n"
            " * @param {string} x\n"
            " * @returns {number}\n"
            " */\n"
            "// some note\n"
            "export function foo(x) { return 42; }\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert "(x: string) -> number" in result[0].signature


@requires_tree_sitter
class TestDeeplyNestedJsdocTypes:
    def test_two_levels_nested_type(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text(
            "/** @param {{config: {host: string, port: number}}} opts */\nexport function connect(opts) {}\n"
        )
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert "{config: {host: string, port: number}}" in result[0].signature


@requires_tree_sitter
class TestCommonJsQuotedStringKeys:
    def test_commonjs_quoted_key(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = { 'create': function() {} };\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "create"

    def test_commonjs_double_quoted_key(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text('module.exports = { "destroy": function() {} };\n')
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert result[0].name == "destroy"


@requires_tree_sitter
class TestCommonJsPairClassExpression:
    def test_commonjs_pair_class_expression(self, tmp_path):
        from goga.contract.javascript import javascript_contract

        (tmp_path / "index.js").write_text("module.exports = {\n  Database: class { connect() {} },\n};\n")
        result = javascript_contract(str(tmp_path))
        assert len(result) == 1
        assert isinstance(result[0], EntityContract)
        assert result[0].name == "Database"
        assert len(result[0].methods) == 1
        assert result[0].methods[0].name == "connect"

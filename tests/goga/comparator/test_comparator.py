"""Tests for goga.comparator.compare routine."""

import inspect
import sys
from textwrap import dedent

from goga.ast.nodes import (
    BodyNode,
    DocumentRoot,
    EntityTypeNode,
    MethodNode,
    PropertyNode,
    RoutineTypeNode,
)
from goga.comparator import compare


class TestCompareFacade:
    """Contract tests — verify compare is importable and has correct signature."""

    def test_compare_importable_from_facade(self) -> None:
        from goga.comparator import compare as _compare  # noqa: PLC0415

        assert callable(_compare)

    def test_compare_signature(self) -> None:
        from goga.comparator import compare as _compare  # noqa: PLC0415
        sig = inspect.signature(_compare)
        params = list(sig.parameters.keys())
        assert params == ["tree", "paths"]
        assert sig.parameters["paths"].default is None

    def test_compare_empty_tree_returns_empty_dict(self) -> None:
        result = compare([])
        assert result == {}


def _make_doc(
    path: str,
    entities: list[EntityTypeNode] | None = None,
    routines: list[RoutineTypeNode] | None = None,
    children: list[DocumentRoot] | None = None,
) -> DocumentRoot:
    body = BodyNode(root=None, entities=entities or [], routines=routines or [])
    return DocumentRoot(path=path, body=body, children=children or [])


def _make_entity(
    name: str,
    signature: str = "()",
    methods: list[MethodNode] | None = None,
    properties: list[PropertyNode] | None = None,
    mutations: list[tuple[str, str]] | None = None,
) -> EntityTypeNode:
    return EntityTypeNode(
        root=None,
        name=name,
        signature=signature,
        methods=methods or [],
        properties=properties or [],
        mutations=mutations or [],
    )


def _make_routine(name: str, signature: str = "() -> None") -> RoutineTypeNode:
    return RoutineTypeNode(root=None, name=name, signature=signature)


def _make_method(name: str, signature: str = "()") -> MethodNode:
    return MethodNode(root=None, name=name, signature=signature)


def _make_property(name: str, type_str: str = "str") -> PropertyNode:
    return PropertyNode(root=None, name=name, type=type_str)


class TestCompareSingleCellWithEntitiesAndRoutines:
    """Positive: single cell with CODEMANIFEST entity+routine and matching Python package."""

    def test_compare_single_cell_with_entities_and_routines(self, tmp_path) -> None:
        cell_name = "testcell"
        cell_dir = tmp_path / cell_name
        cell_dir.mkdir()
        (cell_dir / "__init__.py").write_text(
            dedent("""\
                class MyEntity:
                    def __init__(self, x: int) -> None: ...
                    def do_stuff(self) -> str: ...

                    @property
                    def val(self) -> int: ...

                def my_routine() -> None: ...

                __all__ = ["MyEntity", "my_routine"]
            """)
        )
        parent = str(tmp_path)
        sys.path.insert(0, parent)
        try:
            doc = _make_doc(
                cell_name,
                entities=[
                    _make_entity(
                        "MyEntity",
                        "(x: int)",
                        methods=[_make_method("do_stuff", "(self) -> str")],
                        properties=[_make_property("val", "int")],
                    )
                ],
                routines=[_make_routine("my_routine", "() -> None")],
            )

            result = compare([doc], paths=[cell_name])

            assert cell_name in result
            cell_result = result[cell_name]
            assert "codemanifest" in cell_result
            assert "source" in cell_result

            cm = cell_result["codemanifest"]
            assert "MyEntity" in cm
            assert "my_routine" in cm
            entity = cm["MyEntity"]
            assert "()" in entity
            assert entity["()"] == "(x: int)"
            assert entity["methods"] == {"do_stuff": "(self) -> str"}
            assert entity["properties"] == {"val": "int"}

            src = cell_result["source"]
            assert "MyEntity" in src
            assert "my_routine" in src
            assert src["my_routine"] == "() -> None"
            entity_src = src["MyEntity"]
            assert entity_src["()"] == "(x: int) -> None"
            assert entity_src["methods"] == {"do_stuff": "() -> str"}
            assert entity_src["properties"] == {"val": "int"}
        finally:
            sys.path.remove(parent)
            sys.modules.pop(cell_name, None)


class TestCompareEntityWithMutations:
    """Positive: entity with mutations inherits methods from base."""

    def test_compare_entity_with_mutations(self, tmp_path) -> None:
        base_name = "basecell"
        derived_name = "derivedcell"
        base_dir = tmp_path / base_name
        base_dir.mkdir()
        derived_dir = tmp_path / derived_name
        derived_dir.mkdir()

        base_dir.mkdir(exist_ok=True)
        (base_dir / "__init__.py").write_text(
            dedent("""\
                class BaseClass:
                    def foo(self) -> None: ...
                    def bar(self) -> int: ...
                __all__ = ["BaseClass"]
            """)
        )
        (derived_dir / "__init__.py").write_text(
            dedent(f"""\
                import {base_name}
                class DerivedClass({base_name}.BaseClass):
                    def bar(self) -> str: ...
                    def baz(self) -> None: ...
                __all__ = ["DerivedClass"]
            """)
        )
        parent = str(tmp_path)
        sys.path.insert(0, parent)
        try:
            base_doc = _make_doc(
                base_name,
                entities=[
                    _make_entity(
                        "BaseClass",
                        "()",
                        methods=[
                            _make_method("foo", "()"),
                            _make_method("bar", "() -> int"),
                        ],
                    )
                ],
            )
            derived_doc = _make_doc(
                derived_name,
                entities=[
                    _make_entity(
                        "BaseClass::DerivedClass",
                        "()",
                        methods=[
                            _make_method("bar", "() -> str"),
                            _make_method("baz", "()"),
                        ],
                        mutations=[("BaseClass", base_name)],
                    )
                ],
            )

            result = compare([base_doc, derived_doc], paths=[derived_name])

            assert derived_name in result
            cm = result[derived_name]["codemanifest"]
            assert "DerivedClass" in cm
            assert "BaseClass" not in cm
            entity = cm["DerivedClass"]
            methods = entity["methods"]
            assert "foo" in methods
            assert methods["foo"] == "()"
            assert methods["bar"] == "() -> str"
            assert "baz" in methods
        finally:
            sys.path.remove(parent)
            sys.modules.pop(base_name, None)
            sys.modules.pop(derived_name, None)


class TestCompareAllCellsNoPaths:
    """Positive: all cells returned when paths is empty."""

    def test_compare_all_cells_no_paths(self, tmp_path) -> None:
        cells = ["cell_a", "cell_b", "cell_c"]
        for name in cells:
            d = tmp_path / name
            d.mkdir()
            (d / "__init__.py").write_text("__all__ = []\n")

        parent = str(tmp_path)
        sys.path.insert(0, parent)
        try:
            docs = [
                _make_doc(name, entities=[_make_entity("E", "()")])
                for name in cells
            ]
            result = compare(docs, paths=[])

            for name in cells:
                assert name in result
                assert "codemanifest" in result[name]
                assert result[name]["codemanifest"] == {"E": {"()": "()", "methods": {}, "properties": {}}}
                assert result[name]["source"] == {}
        finally:
            sys.path.remove(parent)
            for name in cells:
                sys.modules.pop(name, None)


class TestCompareMissingPythonPackage:
    """Negative: cell with CODEMANIFEST but no Python package returns empty source."""

    def test_compare_missing_python_package(self) -> None:
        doc = _make_doc(
            "nonexistent_cell",
            entities=[_make_entity("SomeEntity", "()")],
        )
        result = compare([doc], paths=["nonexistent_cell"])

        assert "nonexistent_cell" in result
        assert result["nonexistent_cell"]["source"] == {}
        assert result["nonexistent_cell"]["codemanifest"] != {}


class TestCompareEntityNoMutations:
    """Edge: entity with empty mutations list includes only own methods/properties."""

    def test_compare_entity_no_mutations(self) -> None:
        doc = _make_doc(
            "cell",
            entities=[
                _make_entity(
                    "SimpleEntity",
                    "()",
                    methods=[_make_method("own_method", "()")],
                    properties=[_make_property("own_prop", "int")],
                    mutations=[],
                )
            ],
        )
        result = compare([doc], paths=["cell"])

        cm = result["cell"]["codemanifest"]["SimpleEntity"]
        assert cm["methods"] == {"own_method": "()"}
        assert cm["properties"] == {"own_prop": "int"}


class TestCompareEmptyMethodsProperties:
    """Edge: entity with no methods and no properties includes empty dicts."""

    def test_compare_empty_methods_properties(self) -> None:
        doc = _make_doc(
            "cell",
            entities=[_make_entity("EmptyEntity", "()")],
        )
        result = compare([doc], paths=["cell"])

        entity = result["cell"]["codemanifest"]["EmptyEntity"]
        assert entity["methods"] == {}
        assert entity["properties"] == {}


class TestCompareNestedChildren:
    """Positive: compare iterates nested child documents."""

    def test_compare_includes_children_in_result(self) -> None:
        parent = _make_doc("parent", entities=[_make_entity("ParentEntity", "()")])
        child = _make_doc(
            "parent/child",
            entities=[_make_entity("ChildEntity", "()")],
        )
        grandchild = _make_doc(
            "parent/child/grandchild",
            routines=[_make_routine("child_routine", "() -> str")],
        )
        parent.children = [child]
        child.children = [grandchild]

        result = compare([parent])

        assert "parent" in result
        assert "parent/child" in result
        assert "parent/child/grandchild" in result
        assert "ParentEntity" in result["parent"]["codemanifest"]
        assert "ChildEntity" in result["parent/child"]["codemanifest"]
        assert "child_routine" in result["parent/child/grandchild"]["codemanifest"]


class TestCompareMultiLevelMutations:
    """Positive: three-level mutation chain inherits methods through all levels."""

    def test_compare_multi_level_mutation_chain(self, tmp_path) -> None:
        grandparent_dir = tmp_path / "gp"
        grandparent_dir.mkdir()
        (grandparent_dir / "__init__.py").write_text(
            dedent("""\
                class GrandParent:
                    def alpha(self) -> None: ...
                __all__ = ["GrandParent"]
            """)
        )

        parent_dir = tmp_path / "par"
        parent_dir.mkdir()
        (parent_dir / "__init__.py").write_text(
            dedent("""\
                import gp
                class Parent(gp.GrandParent):
                    def beta(self) -> int: ...
                __all__ = ["Parent"]
            """)
        )

        child_dir = tmp_path / "ch"
        child_dir.mkdir()
        (child_dir / "__init__.py").write_text(
            dedent("""\
                import par
                class Child(par.Parent):
                    def gamma(self) -> str: ...
                __all__ = ["Child"]
            """)
        )

        parent = str(tmp_path)
        sys.path.insert(0, parent)
        try:
            gp_doc = _make_doc(
                "gp",
                entities=[
                    _make_entity("GrandParent", "()", methods=[_make_method("alpha", "()")]),
                ],
            )
            par_doc = _make_doc(
                "par",
                entities=[
                    _make_entity(
                        "GrandParent::Parent",
                        "()",
                        methods=[_make_method("beta", "() -> int")],
                        mutations=[("GrandParent", "gp")],
                    ),
                ],
            )
            ch_doc = _make_doc(
                "ch",
                entities=[
                    _make_entity(
                        "Parent::Child",
                        "()",
                        methods=[_make_method("gamma", "() -> str")],
                        mutations=[("Parent", "par")],
                    ),
                ],
            )

            result = compare([gp_doc, par_doc, ch_doc], paths=["ch"])

            cm = result["ch"]["codemanifest"]["Child"]
            methods = cm["methods"]
            assert "alpha" in methods
            assert methods["alpha"] == "()"
            assert "beta" in methods
            assert methods["beta"] == "() -> int"
            assert "gamma" in methods
            assert methods["gamma"] == "() -> str"
        finally:
            sys.path.remove(parent)
            sys.modules.pop("gp", None)
            sys.modules.pop("par", None)
            sys.modules.pop("ch", None)


class TestCompareMethodOverride:
    """Positive: derived entity's method overrides base entity's method."""

    def test_compare_method_override_in_mutation(self, tmp_path) -> None:
        base_dir = tmp_path / "basecell"
        base_dir.mkdir()
        (base_dir / "__init__.py").write_text(
            dedent("""\
                class Shared:
                    def common(self) -> int: ...
                    def base_only(self) -> str: ...
                __all__ = ["Shared"]
            """)
        )

        derived_dir = tmp_path / "derivedcell"
        derived_dir.mkdir()
        (derived_dir / "__init__.py").write_text(
            dedent("""\
                import basecell
                class Derived(basecell.Shared):
                    def common(self) -> float: ...
                __all__ = ["Derived"]
            """)
        )

        parent = str(tmp_path)
        sys.path.insert(0, parent)
        try:
            base_doc = _make_doc(
                "basecell",
                entities=[
                    _make_entity(
                        "Shared",
                        "()",
                        methods=[
                            _make_method("common", "() -> int"),
                            _make_method("base_only", "() -> str"),
                        ],
                    ),
                ],
            )
            derived_doc = _make_doc(
                "derivedcell",
                entities=[
                    _make_entity(
                        "Shared::Derived",
                        "()",
                        methods=[_make_method("common", "() -> float")],
                        mutations=[("Shared", "basecell")],
                    ),
                ],
            )

            result = compare([base_doc, derived_doc], paths=["derivedcell"])

            cm = result["derivedcell"]["codemanifest"]["Derived"]
            methods = cm["methods"]
            assert methods["common"] == "() -> float"
            assert methods["base_only"] == "() -> str"
        finally:
            sys.path.remove(parent)
            sys.modules.pop("basecell", None)
            sys.modules.pop("derivedcell", None)


class TestComparePropertyInheritance:
    """Positive: entity with mutations inherits properties from base."""

    def test_compare_property_inheritance(self, tmp_path) -> None:
        base_name = "basecell"
        derived_name = "derivedcell"
        base_dir = tmp_path / base_name
        base_dir.mkdir()
        derived_dir = tmp_path / derived_name
        derived_dir.mkdir()

        base_dir.mkdir(exist_ok=True)
        (base_dir / "__init__.py").write_text(
            dedent("""\
                class BaseClass:
                    @property
                    def base_prop(self) -> str: ...
                __all__ = ["BaseClass"]
            """)
        )
        (derived_dir / "__init__.py").write_text(
            dedent(f"""\
                import {base_name}
                class DerivedClass({base_name}.BaseClass):
                    @property
                    def own_prop(self) -> int: ...
                __all__ = ["DerivedClass"]
            """)
        )
        parent = str(tmp_path)
        sys.path.insert(0, parent)
        try:
            base_doc = _make_doc(
                base_name,
                entities=[
                    _make_entity(
                        "BaseClass",
                        "()",
                        properties=[_make_property("base_prop", "str")],
                    )
                ],
            )
            derived_doc = _make_doc(
                derived_name,
                entities=[
                    _make_entity(
                        "BaseClass::DerivedClass",
                        "()",
                        properties=[_make_property("own_prop", "int")],
                        mutations=[("BaseClass", base_name)],
                    )
                ],
            )

            result = compare([base_doc, derived_doc], paths=[derived_name])

            assert derived_name in result
            cm = result[derived_name]["codemanifest"]["DerivedClass"]
            assert cm["properties"] == {"base_prop": "str", "own_prop": "int"}
        finally:
            sys.path.remove(parent)
            sys.modules.pop(base_name, None)
            sys.modules.pop(derived_name, None)


class TestCompareMutationNonexistentPath:
    """Edge: entity mutation referencing a document path not in lookup."""

    def test_compare_mutation_nonexistent_path(self) -> None:
        doc = _make_doc(
            "cell",
            entities=[
                _make_entity(
                    "Base::Derived",
                    "()",
                    methods=[_make_method("own_method", "()")],
                    mutations=[("Base", "nonexistent_path")],
                )
            ],
        )
        result = compare([doc], paths=["cell"])

        cm = result["cell"]["codemanifest"]["Derived"]
        assert cm["methods"] == {"own_method": "()"}
        assert cm["properties"] == {}

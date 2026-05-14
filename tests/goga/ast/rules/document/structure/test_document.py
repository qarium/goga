from __future__ import annotations

import inspect
from typing import ClassVar

from goga.ast.nodes.body import BodyNode, EntityTypeNode, MethodNode, RoutineTypeNode
from goga.ast.nodes.common import AnnotationsNode
from goga.ast.nodes.document import DocumentNode, DocumentRoot
from goga.ast.nodes.header import HeaderNode, ImportsNode, ImportTypeItemNode
from goga.ast.rules.base.document import DocumentRule
from goga.ast.rules.document.structure.document import (
    EntitiesAndRoutinesHasNotConflicts,
    EntityHasOnlyValidKeys,
    LocationIsRequired,
    ReturnTypeHasLink,
    RoutineHasOnlyValidKeys,
    SignatureIsValid,
)


class TestContract:
    """Contract tests — verify all 6 classes exist, inherit DocumentRule, have correct check signature."""

    CLASSES: ClassVar[list[type]] = [
        EntitiesAndRoutinesHasNotConflicts,
        EntityHasOnlyValidKeys,
        RoutineHasOnlyValidKeys,
        SignatureIsValid,
        ReturnTypeHasLink,
        LocationIsRequired,
    ]

    def test_all_classes_importable(self):
        for cls in self.CLASSES:
            assert callable(cls), f"{cls.__name__} is not callable"

    def test_all_inherit_document_rule(self):
        for cls in self.CLASSES:
            assert issubclass(cls, DocumentRule), f"{cls.__name__} does not inherit DocumentRule"

    def test_check_signature(self):
        for cls in self.CLASSES:
            sig = inspect.signature(cls.check)
            params = list(sig.parameters)
            assert params == ["self", "node"], f"{cls.__name__}.check signature mismatch"
            assert sig.return_annotation == "list[DocumentRuleError]"

    def test_check_returns_list(self):
        root = DocumentRoot(path="test.md")
        node = DocumentNode(root=root)
        for cls in self.CLASSES:
            instance = cls()
            result = instance.check(node)
            assert isinstance(result, list), f"{cls.__name__}.check must return list"

    def test_module_location(self):
        for cls in self.CLASSES:
            assert cls.__module__ == "goga.ast.rules.document.structure.document", (
                f"{cls.__name__} has wrong module: {cls.__module__}"
            )


class TestEntitiesAndRoutinesHasNotConflicts:
    """EntitiesAndRoutinesHasNotConflicts: names must not conflict with imported type names."""

    def test_entity_conflict_with_import(self):
        import_item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        entity = EntityTypeNode(name="Foo")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "entity_conflict" in errors[0].message.lower() or "same name" in errors[0].message.lower()

    def test_routine_conflict_with_import(self):
        import_item = ImportTypeItemNode(type_name={"Bar"}, from_path="baz")
        routine = RoutineTypeNode(name="Bar")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "routine_conflict" in errors[0].message.lower() or "same name" in errors[0].message.lower()

    def test_embedded_entity_skipped(self):
        import_item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar")
        entity = EntityTypeNode(name="Foo", embedded=True)
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        assert rule.check(node) == []

    def test_embedded_routine_skipped(self):
        import_item = ImportTypeItemNode(type_name={"Bar"}, from_path="baz")
        routine = RoutineTypeNode(name="Bar", embedded=True)
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        assert rule.check(node) == []

    def test_no_conflicts_returns_empty(self):
        import_item = ImportTypeItemNode(type_name={"OtherType"}, from_path="bar")
        entity = EntityTypeNode(name="MyEntity")
        routine = RoutineTypeNode(name="MyRoutine")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(entities=[entity], routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        assert rule.check(node) == []

    def test_import_with_alias_no_conflict(self):
        import_item = ImportTypeItemNode(type_name={"Foo"}, from_path="bar", alias="BarFoo")
        entity = EntityTypeNode(name="Foo")
        root = DocumentRoot(
            path="test.md",
            header=_make_header(imports=ImportsNode(types=[import_item])),
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        assert rule.check(node) == []

    def test_no_imports_returns_empty(self):
        entity = EntityTypeNode(name="Foo")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntitiesAndRoutinesHasNotConflicts()
        assert rule.check(node) == []


class TestEntityHasOnlyValidKeys:
    """EntityHasOnlyValidKeys: entity entries must only contain valid keys."""

    def test_unknown_key_returns_error(self):
        entity = EntityTypeNode(name="Foo", data={"location": "foo.py", "extra": "bad"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntityHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "unknown_keys" in errors[0].message.lower() or "unknown" in errors[0].message.lower()

    def test_valid_keys_returns_empty(self):
        entity = EntityTypeNode(
            name="Foo",
            data={"location": "foo.py", "annotations": "", "properties": [], "methods": []},
        )
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntityHasOnlyValidKeys()
        assert rule.check(node) == []

    def test_multiple_unknown_keys(self):
        entity = EntityTypeNode(name="Foo", data={"extra1": "a", "extra2": "b"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = EntityHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "extra1" in errors[0].message
        assert "extra2" in errors[0].message


class TestRoutineHasOnlyValidKeys:
    """RoutineHasOnlyValidKeys: routine entries must only contain valid keys."""

    def test_unknown_key_returns_error(self):
        routine = RoutineTypeNode(name="Bar", data={"location": "bar.py", "extra": "bad"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = RoutineHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "unknown_keys" in errors[0].message.lower() or "unknown" in errors[0].message.lower()

    def test_valid_keys_returns_empty(self):
        routine = RoutineTypeNode(name="Bar", data={"location": "bar.py", "annotations": ""})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = RoutineHasOnlyValidKeys()
        assert rule.check(node) == []

    def test_multiple_unknown_keys(self):
        routine = RoutineTypeNode(name="Bar", data={"extra1": "a", "extra2": "b"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = RoutineHasOnlyValidKeys()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "extra1" in errors[0].message
        assert "extra2" in errors[0].message


class TestSignatureIsValid:
    """SignatureIsValid: signatures must match '(...)' or '(...) -> ...' format."""

    def test_invalid_format_returns_error(self):
        entity = EntityTypeNode(name="Foo", signature="bad signature")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "format" in errors[0].message.lower() or "invalid" in errors[0].message.lower()

    def test_empty_signature_returns_error(self):
        entity = EntityTypeNode(name="Foo", signature="")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "empty" in errors[0].message.lower()

    def test_valid_signature_no_return(self):
        entity = EntityTypeNode(name="Foo", signature="(param: Type)")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        assert rule.check(node) == []

    def test_valid_signature_with_return(self):
        entity = EntityTypeNode(name="Foo", signature="(param: Type) -> rv:Result")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        assert rule.check(node) == []

    def test_valid_empty_params(self):
        entity = EntityTypeNode(name="Foo", signature="()")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        assert rule.check(node) == []

    def test_routine_signature_checked(self):
        routine = RoutineTypeNode(name="Bar", signature="bad")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_method_signature_checked(self):
        method = MethodNode(name="m1", signature="invalid")
        entity = EntityTypeNode(name="Foo", signature="(x: int)", methods=[method])
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_embedded_entity_skipped(self):
        entity = EntityTypeNode(name="Foo", signature="bad", embedded=True)
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        assert rule.check(node) == []

    def test_embedded_routine_skipped(self):
        routine = RoutineTypeNode(name="Bar", signature="bad", embedded=True)
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = SignatureIsValid()
        assert rule.check(node) == []


class TestReturnTypeHasLink:
    """ReturnTypeHasLink: return type must have a link label (-> label:Type)."""

    def test_missing_link_returns_error(self):
        entity = EntityTypeNode(name="Foo", signature="(x: int) -> Result")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "missing_link" in errors[0].message.lower() or "missing a semantic label" in errors[0].message.lower()

    def test_valid_link_returns_empty(self):
        entity = EntityTypeNode(name="Foo", signature="(x: int) -> rv:Result")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        assert rule.check(node) == []

    def test_no_return_returns_empty(self):
        entity = EntityTypeNode(name="Foo", signature="(x: int)")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        assert rule.check(node) == []

    def test_method_missing_link(self):
        method = MethodNode(name="m1", signature="() -> int")
        entity = EntityTypeNode(name="Foo", signature="(x: int) -> rv:Result", methods=[method])
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_routine_missing_link(self):
        routine = RoutineTypeNode(name="Bar", signature="() -> int")
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        errors = rule.check(node)
        assert len(errors) == 1

    def test_embedded_entity_skipped(self):
        entity = EntityTypeNode(name="Foo", signature="() -> int", embedded=True)
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        assert rule.check(node) == []

    def test_embedded_routine_skipped(self):
        routine = RoutineTypeNode(name="Bar", signature="() -> int", embedded=True)
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = ReturnTypeHasLink()
        assert rule.check(node) == []


class TestLocationIsRequired:
    """LocationIsRequired: non-embedded entities and routines must have location with extension, no '/'."""

    def test_missing_location_returns_error(self):
        entity = EntityTypeNode(name="Foo", data={})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "missing" in errors[0].message.lower()

    def test_empty_location_returns_error(self):
        entity = EntityTypeNode(name="Foo", data={"location": ""})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "missing" in errors[0].message.lower()

    def test_no_extension_returns_error(self):
        entity = EntityTypeNode(name="Foo", data={"location": "foo"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "extension" in errors[0].message.lower()

    def test_contains_path_separator_returns_error(self):
        entity = EntityTypeNode(name="Foo", data={"location": "path/to/foo.py"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "directory" in errors[0].message.lower() or "path" in errors[0].message.lower()

    def test_valid_location_returns_empty(self):
        entity = EntityTypeNode(name="Foo", data={"location": "foo.py"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []

    def test_routine_missing_location(self):
        routine = RoutineTypeNode(name="Bar", data={})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "missing" in errors[0].message.lower()

    def test_routine_valid_location(self):
        routine = RoutineTypeNode(name="Bar", data={"location": "bar.py"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []

    def test_embedded_entity_skipped(self):
        entity = EntityTypeNode(name="Foo", data={}, embedded=True)
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []

    def test_embedded_routine_skipped(self):
        routine = RoutineTypeNode(name="Bar", data={}, embedded=True)
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []

    def test_both_path_and_extension_errors(self):
        entity = EntityTypeNode(name="Foo", data={"location": "path/to/foo"})
        root = DocumentRoot(
            path="test.md",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 2


class TestLocationIsRequiredExtra:
    """Extra cases from old test_location_is_required.py."""

    def test_dotfile_location_valid(self):
        entity = EntityTypeNode(name="DotEntity", data={"location": ".gitignore"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []

    def test_multi_dot_location_valid(self):
        entity = EntityTypeNode(name="CompEntity", data={"location": "my.component.py"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []

    def test_trailing_dot_error(self):
        entity = EntityTypeNode(name="DotEntity", data={"location": "entity."})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "without file extension" in errors[0].message

    def test_only_dot_error(self):
        entity = EntityTypeNode(name="DotOnlyEntity", data={"location": "."})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "without file extension" in errors[0].message

    def test_parent_directory_path_error(self):
        entity = EntityTypeNode(name="ParentEntity", data={"location": "../entity.py"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "containing directory path" in errors[0].message

    def test_routine_with_path_contains_path_error(self):
        routine = RoutineTypeNode(name="sub_tools", data={"location": "sub/tools.py"})
        root = DocumentRoot(path="my_doc", body=BodyNode(routines=[routine]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "containing directory path" in errors[0].message

    def test_routine_without_extension_error(self):
        routine = RoutineTypeNode(name="routinescript", data={"location": "routinescript"})
        root = DocumentRoot(path="my_doc", body=BodyNode(routines=[routine]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "without file extension" in errors[0].message

    def test_multiple_entities_some_missing_location(self):
        good = EntityTypeNode(name="GoodEntity", data={"location": "entity.py"})
        bad = EntityTypeNode(name="BadEntity")
        ugly = EntityTypeNode(name="UglyEntity", data={"location": ""})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[good, bad, ugly]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 2
        assert errors[0].rule == "location_is_required"
        assert "BadEntity" in errors[0].message
        assert errors[1].rule == "location_is_required"
        assert "UglyEntity" in errors[1].message

    def test_empty_document_no_error(self):
        root = DocumentRoot(path="my_doc")
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        assert rule.check(node) == []


def _make_header(data=None, imports=None, annotations=None):
    return HeaderNode(
        data=data or {},
        imports=imports or ImportsNode(),
        annotations=annotations or AnnotationsNode(root=None),
    )

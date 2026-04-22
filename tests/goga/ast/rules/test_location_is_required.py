"""Contract and logic tests for LocationIsRequired rule."""

from goga.ast.errors import DocumentRuleError
from goga.ast.nodes import (
    BodyNode,
    DocumentNode,
    DocumentRoot,
    EntityTypeNode,
    RoutineTypeNode,
)
from goga.ast.rules import LocationIsRequired
from goga.ast.rules.document import DocumentRule


class TestLocationIsRequiredContract:
    def test_inherits_from_document_rule(self):
        assert issubclass(LocationIsRequired, DocumentRule)

    def test_default_name(self):
        rule = LocationIsRequired()
        assert rule.name == "location_is_required"


class TestLocationIsRequiredPositive:
    def test_entity_with_location_no_error(self):
        entity = EntityTypeNode(name="GoodEntity", data={"location": "entity.py"})
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []

    def test_routine_with_location_no_error(self):
        routine = RoutineTypeNode(name="good_routine", data={"location": "tools.py"})
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []

    def test_empty_document_no_error(self):
        root = DocumentRoot(path="my_doc")
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []


class TestLocationIsRequiredNegative:
    def test_entity_without_location_returns_error(self):
        entity = EntityTypeNode(name="BadEntity")
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "location_is_required"
        assert errors[0].message == (
            "Type 'BadEntity' in 'my_doc' is missing required 'location' — specify the source file"
        )

    def test_routine_without_location_returns_error(self):
        routine = RoutineTypeNode(name="bad_routine")
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "location_is_required"
        assert errors[0].message == (
            "Type 'bad_routine' in 'my_doc' is missing required 'location' — specify the source file"
        )


class TestLocationIsRequiredFormatLogic:
    """Logic tests for format validation — positive, negative, and edge cases."""

    # Positive
    def test_dotfile_location_valid(self):
        entity = EntityTypeNode(name="DotEntity", data={"location": ".gitignore"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []

    def test_multi_dot_location_valid(self):
        entity = EntityTypeNode(
            name="CompEntity", data={"location": "my.component.py"}
        )
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []

    # Negative
    def test_path_in_location_contains_path_error(self):
        entity = EntityTypeNode(name="PathEntity", data={"location": "dir/entity.py"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Type 'PathEntity' in 'my_doc' has location 'dir/entity.py'"
            " containing directory path"
            " — use a plain filename without directories"
        )

    def test_no_extension_error(self):
        entity = EntityTypeNode(name="NoExtEntity", data={"location": "entityfile"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Type 'NoExtEntity' in 'my_doc' has location 'entityfile'"
            " without file extension"
            " — use format 'filename.ext'"
        )

    def test_trailing_dot_error(self):
        entity = EntityTypeNode(name="DotEntity", data={"location": "entity."})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].message == (
            "Type 'DotEntity' in 'my_doc' has location 'entity.'"
            " without file extension"
            " — use format 'filename.ext'"
        )

    def test_path_and_no_extension_both_errors(self):
        entity = EntityTypeNode(name="PathNoExtEntity", data={"location": "dir/file"})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 2
        assert "containing directory path" in errors[0].message
        assert "without file extension" in errors[1].message

    def test_only_dot_error(self):
        entity = EntityTypeNode(name="DotOnlyEntity", data={"location": "."})
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "without file extension" in errors[0].message

    # Edge: routines
    def test_routine_with_path_contains_path_error(self):
        routine = RoutineTypeNode(
            name="sub_tools", data={"location": "sub/tools.py"}
        )
        root = DocumentRoot(path="my_doc", body=BodyNode(routines=[routine]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "containing directory path" in errors[0].message

    def test_routine_without_extension_error(self):
        routine = RoutineTypeNode(
            name="routinescript", data={"location": "routinescript"}
        )
        root = DocumentRoot(path="my_doc", body=BodyNode(routines=[routine]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "without file extension" in errors[0].message

    # Edge: parent directory
    def test_parent_directory_path_contains_path_error(self):
        entity = EntityTypeNode(
            name="ParentEntity", data={"location": "../entity.py"}
        )
        root = DocumentRoot(path="my_doc", body=BodyNode(entities=[entity]))
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert "containing directory path" in errors[0].message


class TestLocationIsRequiredEdgeCases:
    def test_entity_with_empty_string_location_returns_error(self):
        entity = EntityTypeNode(name="MyEntity", data={"location": ""})
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 1
        assert errors[0].rule == "location_is_required"
        assert errors[0].message == (
            "Type 'MyEntity' in 'my_doc' is missing required 'location'"
            " — specify the source file"
        )

    def test_embedded_entity_without_location_skipped(self):
        entity = EntityTypeNode(name="SomeEntity", embedded=True)
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(entities=[entity]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []

    def test_embedded_routine_without_location_skipped(self):
        routine = RoutineTypeNode(name="SomeRoutine", embedded=True)
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(routines=[routine]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert errors == []

    def test_multiple_entities_some_missing_location(self):
        good = EntityTypeNode(name="GoodEntity", data={"location": "entity.py"})
        bad = EntityTypeNode(name="BadEntity")
        ugly = EntityTypeNode(name="UglyEntity", data={"location": ""})
        root = DocumentRoot(
            path="my_doc",
            body=BodyNode(entities=[good, bad, ugly]),
        )
        node = DocumentNode(root=root)
        rule = LocationIsRequired()
        errors = rule.check(node)
        assert len(errors) == 2
        assert errors[0].rule == "location_is_required"
        assert "BadEntity" in errors[0].message
        assert errors[1].rule == "location_is_required"
        assert "UglyEntity" in errors[1].message

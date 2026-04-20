"""Contract tests for the goga.ast.visitor package."""

from goga.ast.errors import DocumentRuleError
from goga.ast.nodes import (
    DocumentNode,
    DocumentRoot,
    HeaderNode,
    ImportsNode,
    ImportTypeItemNode,
)
from goga.ast.rules import DocumentRule, ImportsCanNotBeEmpty
from goga.ast.visitor import Visitor

# ---------------------------------------------------------------------------
# 1. Facade: Visitor is importable from the visitor package
# ---------------------------------------------------------------------------


def test_visitor_class_importable():
    """Visitor must be importable from the visitor facade."""
    assert isinstance(Visitor, type)


# ---------------------------------------------------------------------------
# 2. Constructor stores document
# ---------------------------------------------------------------------------


class TestVisitorConstructor:
    def test_document_property_stores_provided_root(self):
        root = DocumentRoot(path="/test/doc.cm")
        visitor = Visitor(document=root)
        assert visitor.document is root

    def test_document_property_returns_document_root(self):
        visitor = Visitor(document=DocumentRoot())
        assert isinstance(visitor.document, DocumentRoot)


# ---------------------------------------------------------------------------
# 3. analyze() with no rules returns empty list
# ---------------------------------------------------------------------------


class TestVisitorAnalyze:
    def test_analyze_no_rules_returns_empty_list(self):
        visitor = Visitor(document=DocumentRoot())
        errors = visitor.analyze(rules=[])
        assert errors == []

    def test_analyze_with_passing_rules_returns_empty_list(self):
        root = DocumentRoot(
            header=HeaderNode(imports=ImportsNode(items=[ImportTypeItemNode(type_name={"Foo"}, from_path="bar")]))
        )
        visitor = Visitor(document=root)
        rule = ImportsCanNotBeEmpty()
        errors = visitor.analyze(rules=[rule])
        assert errors == []

    def test_analyze_with_failing_rule_returns_errors(self):
        root = DocumentRoot(header=HeaderNode(data={"Imports": []}, imports=ImportsNode(items=[])))
        visitor = Visitor(document=root)
        rule = ImportsCanNotBeEmpty()
        errors = visitor.analyze(rules=[rule])
        assert len(errors) == 1
        assert isinstance(errors[0], DocumentRuleError)
        assert errors[0].rule == "imports_can_not_be_empty"

    def test_analyze_with_multiple_rules_aggregates_errors(self):
        root = DocumentRoot(header=HeaderNode(data={"Imports": []}, imports=ImportsNode(items=[])))
        visitor = Visitor(document=root)

        class AlwaysFailRule(DocumentRule):
            def __init__(self) -> None:
                super().__init__(name="always_fail")

            def check(self, node: DocumentNode) -> list[DocumentRuleError]:
                return [
                    DocumentRuleError(
                        message="fail",
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                ]

        rule1 = AlwaysFailRule()
        rule2 = ImportsCanNotBeEmpty()
        errors = visitor.analyze(rules=[rule1, rule2])
        assert len(errors) == 2
        assert all(isinstance(e, DocumentRuleError) for e in errors)

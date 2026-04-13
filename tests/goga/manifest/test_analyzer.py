"""Contract tests for the goga.manifest.analyzer package."""

from goga.manifest.analyzer import Analyzer
from goga.manifest.errors import ProjectRuleError
from goga.manifest.nodes import (
    DocumentRoot,
    HeaderNode,
    ImportItemNode,
    ImportsNode,
)
from goga.manifest.rules import ImportsHasNotCyclicalDeps, ProjectRule

# ---------------------------------------------------------------------------
# 1. Facade: Analyzer is importable
# ---------------------------------------------------------------------------


def test_analyzer_importable():
    """Analyzer must be importable from the analyzer facade."""
    assert isinstance(Analyzer, type)


# ---------------------------------------------------------------------------
# 2. tree property stores the provided list
# ---------------------------------------------------------------------------


class TestAnalyzerTree:
    def test_tree_property_returns_provided_list(self):
        docs = [DocumentRoot(), DocumentRoot()]
        analyzer = Analyzer(tree=docs)
        assert analyzer.tree is docs

    def test_tree_property_with_empty_list(self):
        analyzer = Analyzer(tree=[])
        assert analyzer.tree == []


# ---------------------------------------------------------------------------
# 3. analyze() with no rules returns empty errors list
# ---------------------------------------------------------------------------


class TestAnalyzerNoRules:
    def test_analyze_no_rules_returns_empty(self):
        docs = [DocumentRoot(), DocumentRoot()]
        analyzer = Analyzer(tree=docs)
        result = analyzer.analyze(rules=[])
        assert result == []


# ---------------------------------------------------------------------------
# 4. analyze() with passing rules returns empty errors list
# ---------------------------------------------------------------------------


class TestAnalyzerPassingRules:
    def test_analyze_passing_rules_returns_empty(self):
        doc1 = DocumentRoot(
            path="/project/a.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"X"}, from_path="/project/b.cm")])),
        )
        doc2 = DocumentRoot(
            path="/project/b.cm",
            header=HeaderNode(imports=ImportsNode(items=[])),
        )
        tree = [doc1, doc2]
        rule = ImportsHasNotCyclicalDeps(tree=tree)
        analyzer = Analyzer(tree=tree)
        result = analyzer.analyze(rules=[rule])
        assert result == []


# ---------------------------------------------------------------------------
# 5. analyze() with failing rules returns ProjectRuleError instances
# ---------------------------------------------------------------------------


class TestAnalyzerFailingRules:
    def test_analyze_failing_rules_returns_errors(self):
        doc1 = DocumentRoot(
            path="/project/a.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"X"}, from_path="/project/b.cm")])),
        )
        doc2 = DocumentRoot(
            path="/project/b.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"Y"}, from_path="/project/a.cm")])),
        )
        tree = [doc1, doc2]
        rule = ImportsHasNotCyclicalDeps(tree=tree)
        analyzer = Analyzer(tree=tree)
        result = analyzer.analyze(rules=[rule])
        assert len(result) > 0
        for error in result:
            assert isinstance(error, ProjectRuleError)


# ---------------------------------------------------------------------------
# 6. analyze() with multiple rules on multiple documents aggregates all errors
# ---------------------------------------------------------------------------


class _AlwaysFailRule(ProjectRule):
    """A helper rule that always produces one error per document."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="always_fail")

    def check(self, document: DocumentRoot) -> list[ProjectRuleError]:
        return [
            ProjectRuleError(
                message=f"Always fails for {document.path}",
                rule=self.name,
                document=document,
                node=None,
            )
        ]


class TestAnalyzerAggregation:
    def test_multiple_rules_multiple_docs_aggregates(self):
        doc_a = DocumentRoot(path="/project/a.cm")
        doc_b = DocumentRoot(path="/project/b.cm")
        tree = [doc_a, doc_b]

        rule1 = _AlwaysFailRule(tree=tree)
        rule2 = _AlwaysFailRule(tree=tree)

        analyzer = Analyzer(tree=tree)
        result = analyzer.analyze(rules=[rule1, rule2])

        # 2 rules x 2 documents = 4 errors
        assert len(result) == 4
        for error in result:
            assert isinstance(error, ProjectRuleError)
            assert error.rule == "always_fail"

    def test_mixed_pass_fail_aggregates_only_failures(self):
        doc_no_cycle = DocumentRoot(
            path="/project/x.cm",
            header=HeaderNode(imports=ImportsNode(items=[ImportItemNode(type_name={"X"}, from_path="/project/y.cm")])),
        )
        doc_unused = DocumentRoot(
            path="/project/y.cm",
            header=HeaderNode(imports=ImportsNode(items=[])),
        )
        tree = [doc_no_cycle, doc_unused]

        # ImportsHasNotCyclicalDeps passes for doc_no_cycle, no imports in doc_unused
        cycle_rule = ImportsHasNotCyclicalDeps(tree=tree)
        always_fail = _AlwaysFailRule(tree=tree)

        analyzer = Analyzer(tree=tree)
        result = analyzer.analyze(rules=[cycle_rule, always_fail])

        # cycle_rule produces 0 errors, always_fail produces 2 errors
        assert len(result) == 2
        for error in result:
            assert isinstance(error, ProjectRuleError)
            assert error.rule == "always_fail"

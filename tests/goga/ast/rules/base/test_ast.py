from __future__ import annotations

import goga.ast.rules as facade
import pytest
from goga.ast.rules.base.ast import ASTRule


class TestContract:
    """Contract tests — verify ASTRule is accessible and conforms to API."""

    def test_accessible_from_base_ast(self) -> None:
        assert ASTRule is not None

    def test_accessible_from_facade(self) -> None:
        assert facade.ASTRule is ASTRule

    def test_initialization(self) -> None:
        rule = ASTRule(tree=[], name="ast_test")
        assert rule.name == "ast_test"
        assert rule.tree == []

    def test_name_property(self) -> None:
        rule = ASTRule(tree=[], name="my_ast_rule")
        assert rule.name == "my_ast_rule"

    def test_tree_property(self) -> None:
        rule = ASTRule(tree=[], name="test")
        assert rule.tree == []

    def test_check_raises_not_implemented(self) -> None:
        rule = ASTRule(tree=[], name="test")
        with pytest.raises(NotImplementedError):
            rule.check(object())  # type: ignore[arg-type]


class TestLogic:
    """Logical tests — verify ASTRule behavior and edge cases."""

    def test_tree_returns_list(self) -> None:
        rule = ASTRule(tree=[], name="test")
        assert isinstance(rule.tree, list)

    def test_name_has_no_setter(self) -> None:
        rule = ASTRule(tree=[], name="test")
        with pytest.raises(AttributeError):
            rule.name = "new_name"  # type: ignore[misc]

    def test_tree_has_no_setter(self) -> None:
        rule = ASTRule(tree=[], name="test")
        with pytest.raises(AttributeError):
            rule.tree = []  # type: ignore[misc]

    def test_empty_tree(self) -> None:
        rule = ASTRule(tree=[], name="test")
        assert rule.tree == []

    def test_tree_with_multiple_roots(self) -> None:
        roots = [object(), object()]
        rule = ASTRule(tree=roots, name="test")  # type: ignore[arg-type]
        assert rule.tree == roots
        assert len(rule.tree) == 2

    def test_name_returns_str(self) -> None:
        rule = ASTRule(tree=[], name="test")
        assert isinstance(rule.name, str)

    def test_name_empty_string(self) -> None:
        rule = ASTRule(tree=[], name="")
        assert rule.name == ""

    def test_name_unicode(self) -> None:
        rule = ASTRule(tree=[], name="правило_🔑")
        assert rule.name == "правило_🔑"

    def test_different_instances_independent(self) -> None:
        rule_a = ASTRule(tree=[], name="a")
        rule_b = ASTRule(tree=[], name="b")
        assert rule_a.name != rule_b.name

from __future__ import annotations

import goga.ast.rules as facade
import pytest
from goga.ast.rules.base.document import DocumentRule


class TestContract:
    """Contract tests — verify DocumentRule is accessible and conforms to API."""

    def test_accessible_from_base_document(self) -> None:
        assert DocumentRule is not None

    def test_accessible_from_facade(self) -> None:
        assert facade.DocumentRule is DocumentRule

    def test_initialization(self) -> None:
        rule = DocumentRule(name="test")
        assert rule.name == "test"

    def test_name_property(self) -> None:
        rule = DocumentRule(name="my_rule")
        assert rule.name == "my_rule"

    def test_check_raises_not_implemented(self) -> None:
        rule = DocumentRule(name="test")
        with pytest.raises(NotImplementedError):
            rule.check(object())  # type: ignore[arg-type]


class TestLogic:
    """Logical tests — verify DocumentRule behavior and edge cases."""

    def test_name_returns_str(self) -> None:
        rule = DocumentRule(name="test")
        assert isinstance(rule.name, str)

    def test_name_empty_string(self) -> None:
        rule = DocumentRule(name="")
        assert rule.name == ""

    def test_name_unicode(self) -> None:
        rule = DocumentRule(name="правило_🔑")
        assert rule.name == "правило_🔑"

    def test_name_long_string(self) -> None:
        long_name = "a" * 1000
        rule = DocumentRule(name=long_name)
        assert rule.name == long_name

    def test_name_has_no_setter(self) -> None:
        rule = DocumentRule(name="test")
        with pytest.raises(AttributeError):
            rule.name = "new_name"  # type: ignore[misc]

    def test_different_instances_independent(self) -> None:
        rule_a = DocumentRule(name="a")
        rule_b = DocumentRule(name="b")
        assert rule_a.name != rule_b.name

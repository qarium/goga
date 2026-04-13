"""Contract tests for goga.manifest.errors package.

Verifies facade availability, inheritance, properties, and __str__
formatting for all error classes.
"""

import pytest
from goga.manifest.errors import (
    BaseCodemanifestError,
    ManifestParseError,
    ManifestRuleError,
    ProjectRuleError,
)
from goga.manifest.nodes import DocumentNode, DocumentRoot

# ---------------------------------------------------------------------------
# 1. Facade availability
# ---------------------------------------------------------------------------


class TestFacadeAvailability:
    """All 4 error classes must be importable from the package facade."""

    def test_all_classes_exposed(self) -> None:
        exposed = [
            BaseCodemanifestError,
            ManifestParseError,
            ManifestRuleError,
            ProjectRuleError,
        ]
        for cls in exposed:
            assert cls is not None


# ---------------------------------------------------------------------------
# 2. BaseCodemanifestError
# ---------------------------------------------------------------------------


class TestBaseCodemanifestError:
    def test_inherits_from_exception(self) -> None:
        assert issubclass(BaseCodemanifestError, Exception)

    def test_message_in_args(self) -> None:
        err = BaseCodemanifestError("something went wrong")
        assert "something went wrong" in err.args

    def test_message_property(self) -> None:
        err = BaseCodemanifestError("oops")
        assert err.message == "oops"

    def test_can_be_raised_and_caught_as_exception(self) -> None:
        with pytest.raises(Exception, match="boom"):
            raise BaseCodemanifestError("boom")


# ---------------------------------------------------------------------------
# 3. ManifestParseError
# ---------------------------------------------------------------------------


class TestManifestParseError:
    def test_inherits_from_base(self) -> None:
        assert issubclass(ManifestParseError, BaseCodemanifestError)

    def test_filepath_property(self) -> None:
        err = ManifestParseError("bad parse", "/tmp/manifest.yaml")
        assert err.filepath == "/tmp/manifest.yaml"

    def test_message_works_correctly(self) -> None:
        err = ManifestParseError("bad parse", "/tmp/manifest.yaml")
        assert err.message == "bad parse"


# ---------------------------------------------------------------------------
# 4. ManifestRuleError
# ---------------------------------------------------------------------------


class TestManifestRuleError:
    def test_inherits_from_base(self) -> None:
        assert issubclass(ManifestRuleError, BaseCodemanifestError)

    def test_rule_property(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("violation", "RULE-001", doc, node)
        assert err.rule == "RULE-001"

    def test_document_property(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("violation", "RULE-001", doc, node)
        assert err.document is doc

    def test_node_property(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("violation", "RULE-001", doc, node)
        assert err.node is node

    def test_str_contains_error(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("bad rule", "RULE-001", doc, node)
        text = str(err)
        assert "Error:" in text

    def test_str_contains_rule(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("bad rule", "RULE-001", doc, node)
        text = str(err)
        assert "Rule:" in text

    def test_str_contains_path(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("bad rule", "RULE-001", doc, node)
        text = str(err)
        assert "Path:" in text

    def test_str_contains_node(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("bad rule", "RULE-001", doc, node)
        text = str(err)
        assert "Node:" in text

    def test_str_path_is_directory_portion(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ManifestRuleError("bad rule", "RULE-001", doc, node)
        text = str(err)
        assert "/project/docs" in text


# ---------------------------------------------------------------------------
# 5. ProjectRuleError
# ---------------------------------------------------------------------------


class TestProjectRuleError:
    def test_inherits_from_base(self) -> None:
        assert issubclass(ProjectRuleError, BaseCodemanifestError)

    def test_rule_property(self) -> None:
        err = ProjectRuleError("violation", "PR-001", None, None)
        assert err.rule == "PR-001"

    def test_document_none(self) -> None:
        err = ProjectRuleError("violation", "PR-001", None, None)
        assert err.document is None

    def test_node_none(self) -> None:
        err = ProjectRuleError("violation", "PR-001", None, None)
        assert err.node is None

    def test_document_and_node_present(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ProjectRuleError("violation", "PR-001", doc, node)
        assert err.document is doc
        assert err.node is node

    def test_str_no_path_when_document_none(self) -> None:
        err = ProjectRuleError("no doc", "PR-001", None, None)
        text = str(err)
        assert "* Path:" not in text

    def test_str_no_node_when_node_none(self) -> None:
        err = ProjectRuleError("no node", "PR-001", None, None)
        text = str(err)
        assert "* Node:" not in text

    def test_str_has_path_when_document_present(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ProjectRuleError("with doc", "PR-001", doc, node)
        text = str(err)
        assert "Path:" in text

    def test_str_has_node_when_node_present(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        err = ProjectRuleError("with node", "PR-001", doc, node)
        text = str(err)
        assert "Node:" in text

    def test_str_format_same_as_manifest_rule_error_when_both_present(self) -> None:
        doc = DocumentRoot(path="/project/docs/spec.goga")
        node = DocumentNode()
        project_err = ProjectRuleError("full info", "PR-001", doc, node)
        text = str(project_err)
        assert "Error:" in text
        assert "Rule:" in text
        assert "Path:" in text
        assert "Node:" in text

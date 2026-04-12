"""Contract tests for goga.codemanifest.nodes package.

Verifies facade availability, API shape, defaults, and inheritance
for all node dataclasses.
"""

from goga.codemanifest.nodes import (
    AnnotationsNode,
    BodyNode,
    DocumentNode,
    DocumentRoot,
    EntityTypeNode,
    FooterNode,
    HeaderNode,
    ImportItemNode,
    ImportsNode,
    MethodNode,
    Node,
    PropertyNode,
    RoutineTypeNode,
    UsageItemNode,
    UsagesNode,
)

# ---------------------------------------------------------------------------
# 1. Facade availability
# ---------------------------------------------------------------------------


class TestFacadeAvailability:
    """All public node classes must be importable from the package facade."""

    def test_all_classes_exposed(self) -> None:
        exposed = [
            Node,
            DocumentRoot,
            DocumentNode,
            AnnotationsNode,
            HeaderNode,
            ImportsNode,
            ImportItemNode,
            UsagesNode,
            UsageItemNode,
            BodyNode,
            RoutineTypeNode,
            EntityTypeNode,
            MethodNode,
            PropertyNode,
            FooterNode,
        ]
        for cls in exposed:
            assert cls is not None


# ---------------------------------------------------------------------------
# 2. Node base class
# ---------------------------------------------------------------------------


class TestNode:
    def test_defaults(self) -> None:
        node = Node()
        assert node.parent is None
        assert node.data == {}

    def test_set_parent_and_data(self) -> None:
        child = Node()
        parent = Node()
        child.parent = parent
        child.data = {"key": "value"}
        assert child.parent is parent
        assert child.data == {"key": "value"}


# ---------------------------------------------------------------------------
# 3. DocumentRoot
# ---------------------------------------------------------------------------


class TestDocumentRoot:
    def test_extends_node(self) -> None:
        assert issubclass(DocumentRoot, Node)

    def test_defaults(self) -> None:
        root = DocumentRoot()
        assert root.path == ""
        assert root.links == {}
        assert root.embeddings == []
        assert isinstance(root.header, HeaderNode)
        assert isinstance(root.body, BodyNode)
        assert isinstance(root.footer, FooterNode)
        assert root.types == {}
        assert root.children == []

    def test_header_body_footer_are_distinct_instances(self) -> None:
        a = DocumentRoot()
        b = DocumentRoot()
        assert a.header is not b.header
        assert a.body is not b.body
        assert a.footer is not b.footer

    def test_embeddings_default_empty_list(self) -> None:
        root = DocumentRoot()
        assert root.embeddings == []
        assert isinstance(root.embeddings, list)

    def test_embeddings_is_list_of_tuples(self) -> None:
        root = DocumentRoot(embeddings=[("key1", "val1"), ("key2", "val2")])
        assert root.embeddings == [("key1", "val1"), ("key2", "val2")]
        assert all(isinstance(item, tuple) and len(item) == 2 for item in root.embeddings)

    def test_embeddings_independent_per_instance(self) -> None:
        a = DocumentRoot()
        b = DocumentRoot()
        a.embeddings.append(("x", "y"))
        assert a.embeddings == [("x", "y")]
        assert b.embeddings == []


# ---------------------------------------------------------------------------
# 4. DocumentNode
# ---------------------------------------------------------------------------


class TestDocumentNode:
    def test_extends_node(self) -> None:
        assert issubclass(DocumentNode, Node)

    def test_root_default_none(self) -> None:
        node = DocumentNode()
        assert node.root is None


# ---------------------------------------------------------------------------
# 5. AnnotationsNode
# ---------------------------------------------------------------------------


class TestAnnotationsNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(AnnotationsNode, DocumentNode)

    def test_defaults(self) -> None:
        node = AnnotationsNode()
        assert node.url is None
        assert node.filepath is None
        assert node.links == []
        assert node.text == ""


# ---------------------------------------------------------------------------
# 6. HeaderNode
# ---------------------------------------------------------------------------


class TestHeaderNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(HeaderNode, DocumentNode)

    def test_defaults(self) -> None:
        header = HeaderNode()
        assert isinstance(header.imports, ImportsNode)
        assert isinstance(header.usages, UsagesNode)
        assert header.types == []


# ---------------------------------------------------------------------------
# 7. ImportsNode / ImportItemNode
# ---------------------------------------------------------------------------


class TestImportsNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(ImportsNode, DocumentNode)

    def test_defaults(self) -> None:
        node = ImportsNode()
        assert node.items == []


class TestImportItemNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(ImportItemNode, DocumentNode)

    def test_defaults(self) -> None:
        node = ImportItemNode()
        assert node.type_name == set()
        assert node.from_path == ""
        assert node.alias == ""

    def test_type_name_is_set(self) -> None:
        node = ImportItemNode(type_name={"Foo", "Bar"})
        assert isinstance(node.type_name, set)
        assert node.type_name == {"Foo", "Bar"}


# ---------------------------------------------------------------------------
# 8. UsagesNode / UsageItemNode
# ---------------------------------------------------------------------------


class TestUsagesNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(UsagesNode, DocumentNode)

    def test_defaults(self) -> None:
        node = UsagesNode()
        assert node.items == []


class TestUsageItemNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(UsageItemNode, DocumentNode)

    def test_defaults(self) -> None:
        node = UsageItemNode()
        assert node.name == ""
        assert isinstance(node.annotations, AnnotationsNode)


# ---------------------------------------------------------------------------
# 9. BodyNode
# ---------------------------------------------------------------------------


class TestBodyNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(BodyNode, DocumentNode)

    def test_defaults(self) -> None:
        body = BodyNode()
        assert body.types == {}
        assert body.entities == []
        assert body.routines == []


# ---------------------------------------------------------------------------
# 10. RoutineTypeNode
# ---------------------------------------------------------------------------


class TestRoutineTypeNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(RoutineTypeNode, DocumentNode)

    def test_defaults(self) -> None:
        node = RoutineTypeNode()
        assert node.name == ""
        assert node.signature == ""
        assert node.location == ""
        assert isinstance(node.annotations, AnnotationsNode)
        assert node.embedded is False


# ---------------------------------------------------------------------------
# 11. EntityTypeNode
# ---------------------------------------------------------------------------


class TestEntityTypeNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(EntityTypeNode, DocumentNode)

    def test_defaults(self) -> None:
        node = EntityTypeNode()
        assert node.name == ""
        assert node.signature == ""
        assert node.location == ""
        assert isinstance(node.annotations, AnnotationsNode)
        assert node.embedded is False
        assert node.properties == []
        assert node.methods == []
        assert node.mutations == []


# ---------------------------------------------------------------------------
# 12. MethodNode / PropertyNode
# ---------------------------------------------------------------------------


class TestMethodNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(MethodNode, DocumentNode)

    def test_defaults(self) -> None:
        node = MethodNode()
        assert node.name == ""
        assert node.signature == ""
        assert isinstance(node.annotations, AnnotationsNode)


class TestPropertyNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(PropertyNode, DocumentNode)

    def test_defaults(self) -> None:
        node = PropertyNode()
        assert node.name == ""
        assert node.type == ""
        assert isinstance(node.annotations, AnnotationsNode)


# ---------------------------------------------------------------------------
# 13. FooterNode
# ---------------------------------------------------------------------------


class TestFooterNode:
    def test_extends_document_node(self) -> None:
        assert issubclass(FooterNode, DocumentNode)

    def test_defaults(self) -> None:
        footer = FooterNode()
        assert footer.author == ""
        assert footer.created_at == ""
        assert footer.description == ""

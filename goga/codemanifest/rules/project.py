from __future__ import annotations

from typing import TYPE_CHECKING

from goga.codemanifest.errors import ProjectRuleError

if TYPE_CHECKING:
    from goga.codemanifest.nodes import DocumentRoot


class ProjectRule:
    """Base class for project-level rules."""

    def __init__(self, tree: list[DocumentRoot], name: str) -> None:
        self._name = name
        self._tree = tree

    @property
    def name(self) -> str:
        return self._name

    @property
    def tree(self) -> list[DocumentRoot]:
        return self._tree

    def check(self, document: DocumentRoot) -> list[ProjectRuleError]:
        raise NotImplementedError


class ImportsHasNotCyclicalDepsRule(ProjectRule):
    """Rule: imports must not form cycles across documents."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="imports_has_not_cyclical_deps")

    def check(self, document: DocumentRoot) -> list[ProjectRuleError]:
        # Build a map of resolved path -> set of resolved import paths
        import_map: dict[str, set[str]] = {}
        for doc in self._tree:
            doc_path = doc.path
            import_paths: set[str] = set()
            for item in doc.header.imports.items:
                import_paths.add(item.from_path)
            import_map[doc_path] = import_paths

        errors: list[ProjectRuleError] = []
        doc_path = document.path

        for item in document.header.imports.items:
            imported_path = item.from_path
            # Check if the imported document also imports from the current document's path
            if imported_path in import_map and doc_path in import_map[imported_path]:
                errors.append(
                    ProjectRuleError(
                        message=(
                            f"Cyclical dependency detected: "
                            f"'{doc_path}' imports from '{imported_path}' "
                            f"which also imports from '{doc_path}'"
                        ),
                        rule=self.name,
                        document=document,
                        node=item,
                    )
                )

        return errors


class AllUsagesIsUsed(ProjectRule):
    """Rule: every usage declared in the header must appear in at least one annotation."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="all_usages_is_used")

    def check(self, document: DocumentRoot) -> list[ProjectRuleError]:
        usage_names = [item.name for item in document.header.usages.items]

        if not usage_names:
            return []

        # Collect all annotation texts from the document
        annotation_texts: list[str] = []

        # Header annotations
        annotation_texts.append(document.header.annotations.text)

        # Body entity annotations
        for entity in document.body.entities:
            annotation_texts.append(entity.annotations.text)
            for method in entity.methods:
                annotation_texts.append(method.annotations.text)
            for prop in entity.properties:
                annotation_texts.append(prop.annotations.text)

        # Body routine annotations
        for routine in document.body.routines:
            annotation_texts.append(routine.annotations.text)

        combined_text = " ".join(annotation_texts)

        errors: list[ProjectRuleError] = []
        for usage_name in usage_names:
            if usage_name not in combined_text:
                errors.append(
                    ProjectRuleError(
                        message=f"Usage '{usage_name}' is declared but not used in any annotation",
                        rule=self.name,
                        document=document,
                        node=None,
                    )
                )

        return errors

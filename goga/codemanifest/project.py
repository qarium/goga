from __future__ import annotations

import os

from goga.codemanifest.analyzer import Analyzer
from goga.codemanifest.errors import ManifestRuleError, ProjectRuleError
from goga.codemanifest.factory import Factory
from goga.codemanifest.nodes import DocumentRoot, EntityTypeNode, RoutineTypeNode
from goga.codemanifest.rules import (
    AllUsagesIsUsed,
    AnnotationLinksExists,
    EmbeddedEntityCanNotHasMutations,
    EmbeddedTypeHasLowLevel,
    EntitiesAndRoutinesHasNotConflicts,
    ImportHasNotDuplicate,
    ImportHasTypeRule,
    ImportHasValidFromPathRule,
    ImportsCanNotBeEmptyRule,
    ImportsHasNotCyclicalDepsRule,
    MutationExists,
    MutationIsValid,
    ReturnTypeHasLink,
    UsageLinksHasNotConflicts,
)
from goga.codemanifest.visitor import Visitor


def _flatten_tree(tree: list[DocumentRoot]) -> list[DocumentRoot]:
    """Flatten the document tree recursively, collecting all DocumentRoot instances."""
    result: list[DocumentRoot] = []
    for root in tree:
        result.append(root)
        result.extend(_flatten_tree(root.children))
    return result


class Project:
    """Facade for loading and validating a CODEMANIFEST project tree."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._tree: list[DocumentRoot] = []
        self._errors: list[ProjectRuleError | ManifestRuleError] = []
        self._index: dict[str, DocumentRoot] = {}

    @property
    def path(self) -> str:
        return self._path

    @property
    def tree(self) -> list[DocumentRoot]:
        return self._tree

    @property
    def errors(self) -> list[ProjectRuleError | ManifestRuleError]:
        return self._errors

    def load(self) -> None:
        """Load the document tree from the filesystem and run all rules."""
        self._tree = []
        self._errors = []
        self._index = {}

        # Map from directory path to its DocumentRoot (for parent-child wiring)
        loaded: dict[str, DocumentRoot] = {}

        # Walk directories top-down so parents are loaded before children
        for dirpath, _dirnames, filenames in os.walk(self._path):
            if "CODEMANIFEST" not in filenames:
                continue

            dirpath_str = dirpath if isinstance(dirpath, str) else str(dirpath)

            # Find the closest parent that has a CODEMANIFEST
            parent_doc: DocumentRoot | None = None
            check_dir = os.path.dirname(dirpath_str)
            while check_dir >= self._path:
                if check_dir in loaded:
                    parent_doc = loaded[check_dir]
                    break
                check_dir = os.path.dirname(check_dir)

            factory = Factory(dirpath_str)
            document_root = factory.create(parent=parent_doc)

            loaded[dirpath_str] = document_root

            if parent_doc is None:
                # Top-level document
                self._tree.append(document_root)
            else:
                # Nested document — add as child of parent
                parent_doc.children.append(document_root)

        # Build normalized path index for O(1) lookup
        self._index = {os.path.normpath(os.path.abspath(k)): v for k, v in loaded.items()}

        # Deferred routing: reclassify embedded entities whose original type is a routine
        all_documents = _flatten_tree(self._tree)
        self._reclassify_embedded_types(all_documents)

        # Apply document-level rules via Visitor
        document_rules = [
            ImportsCanNotBeEmptyRule(),
            ImportHasTypeRule(),
            ImportHasValidFromPathRule(),
            ImportHasNotDuplicate(),
            AllUsagesIsUsed(),
            AnnotationLinksExists(),
            UsageLinksHasNotConflicts(),
            EntitiesAndRoutinesHasNotConflicts(),
            MutationExists(),
            MutationIsValid(),
            ReturnTypeHasLink(),
            EmbeddedEntityCanNotHasMutations(),
        ]

        for doc in all_documents:
            visitor = Visitor(doc)
            self._errors.extend(visitor.analyze(document_rules))

        # Apply project-level rules via Analyzer
        project_rules = [
            ImportsHasNotCyclicalDepsRule(all_documents),
            EmbeddedTypeHasLowLevel(all_documents),
        ]

        analyzer = Analyzer(all_documents)
        self._errors.extend(analyzer.analyze(project_rules))

    @staticmethod
    def _reclassify_embedded_types(all_documents: list[DocumentRoot]) -> None:
        """Reclassify embedded entities whose original type is a routine.

        Factory creates all embedded types as EntityTypeNode. After all documents
        are loaded, this method finds the original type definition and reclassifies
        entities whose original is a routine into RoutineTypeNode.
        """
        # Build lookup: type name -> (is_routine, is_entity) from non-embedded definitions
        routine_names: set[str] = set()
        entity_names: set[str] = set()
        for doc in all_documents:
            for entity in doc.body.entities:
                if not entity.embedded:
                    entity_names.add(entity.name)
            for routine in doc.body.routines:
                if not routine.embedded:
                    routine_names.add(routine.name)

        for doc in all_documents:
            to_remove: list[EntityTypeNode] = []
            for entity in doc.body.entities:
                if entity.embedded and entity.name in routine_names and entity.name not in entity_names:
                    to_remove.append(entity)

            for entity in to_remove:
                doc.body.entities.remove(entity)
                doc.body.routines.append(
                    RoutineTypeNode(
                        name=entity.name,
                        signature=entity.signature,
                        location=entity.location,
                        annotations=entity.annotations,
                        embedded=True,
                        data=entity.data,
                        parent=entity.parent,
                        root=entity.root,
                    )
                )

    def codemanifest(self, path: str) -> DocumentRoot:
        """Look up a DocumentRoot by its directory path at O(1)."""
        resolved = os.path.normpath(os.path.abspath(path))
        if resolved not in self._index:
            raise KeyError(f"Document not found for path: {path}")
        return self._index[resolved]

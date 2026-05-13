from __future__ import annotations

import os
from pathlib import Path

from .analyzer import Analyzer
from .errors import ASTRuleError, DocumentNotFoundError, DocumentRuleError
from .factory import Factory
from .nodes import DocumentRoot, EntityTypeNode, RoutineTypeNode
from .rules import (
    AllUsagesIsUsed,
    AnnotationLinksExists,
    EmbeddedEntityCanNotHasMutations,
    EmbeddedTypeHasLowLevel,
    EntitiesAndRoutinesHasNotConflicts,
    EntityHasOnlyValidKeys,
    ImportHasNotDuplicate,
    ImportHasValidFromPath,
    ImportIsUsed,
    ImportItemIsValid,
    ImportsCanNotBeEmpty,
    ImportsHasNotCyclicalDeps,
    ImportsHasOnlyValidKeys,
    ImportTypeExists,
    ImportUsageExists,
    LocationIsRequired,
    MutationExists,
    MutationIsValid,
    ReturnTypeHasLink,
    RoutineHasOnlyValidKeys,
    SignatureIsValid,
    UsageFilepathExists,
    UsageLinksHasNotConflicts,
    UsageUrlIsAccessible,
)
from .visitor import Visitor


def _flatten_tree(tree: list[DocumentRoot]) -> list[DocumentRoot]:
    """Flatten the document tree recursively, collecting all DocumentRoot instances."""
    result: list[DocumentRoot] = []
    for root in tree:
        result.append(root)
        result.extend(_flatten_tree(root.children))
    return result


class AST:
    """Facade for loading and validating a CODEMANIFEST AST tree."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._tree: list[DocumentRoot] = []
        self._errors: list[ASTRuleError | DocumentRuleError] = []
        self._index: dict[str, DocumentRoot] = {}

    @property
    def path(self) -> str:
        return self._path

    @property
    def tree(self) -> list[DocumentRoot]:
        return self._tree

    @property
    def errors(self) -> list[ASTRuleError | DocumentRuleError]:
        return self._errors

    def load(self) -> None:
        """Load the document tree from the filesystem and run all rules."""
        self._tree = []
        self._errors = []
        self._index = {}
        self._path = os.path.normpath(os.path.relpath(self._path))

        # Map from directory path to its DocumentRoot (for parent-child wiring)
        loaded: dict[str, DocumentRoot] = {}

        # Walk directories top-down so parents are loaded before children
        for dirpath, dirnames, filenames in os.walk(self._path):
            # Skip .project test fixture directories (exact match, not substring)
            dirnames[:] = [d for d in dirnames if d != ".project"]
            if "CODEMANIFEST" not in filenames:
                continue

            dirpath_str = os.path.normpath(dirpath)

            # Find the closest parent that has a CODEMANIFEST
            parent_doc: DocumentRoot | None = None
            check_dir = str(Path(dirpath_str).parent)
            while check_dir >= self._path:
                if check_dir in loaded:
                    parent_doc = loaded[check_dir]
                    break
                prev = check_dir
                check_dir = str(Path(check_dir).parent)
                if check_dir == prev:
                    break

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
        self._index = {str(Path(k).resolve()): v for k, v in loaded.items()}

        # Deferred routing: reclassify embedded entities whose original type is a routine
        all_documents = _flatten_tree(self._tree)
        self._reclassify_embedded_types(all_documents)

        # Apply document-level rules via Visitor
        document_rules = [
            ImportsCanNotBeEmpty(),
            ImportHasValidFromPath(),
            ImportItemIsValid(),
            ImportHasNotDuplicate(),
            AllUsagesIsUsed(),
            AnnotationLinksExists(),
            UsageLinksHasNotConflicts(),
            EntitiesAndRoutinesHasNotConflicts(),
            MutationExists(),
            MutationIsValid(),
            ReturnTypeHasLink(),
            EmbeddedEntityCanNotHasMutations(),
            ImportsHasOnlyValidKeys(),
            ImportUsageExists(),
            EntityHasOnlyValidKeys(),
            RoutineHasOnlyValidKeys(),
            ImportIsUsed(),
            SignatureIsValid(),
            LocationIsRequired(),
            UsageFilepathExists(),
            UsageUrlIsAccessible(),
        ]

        for doc in all_documents:
            visitor = Visitor(doc)
            self._errors.extend(visitor.analyze(document_rules))

        # Apply AST-level rules via Analyzer
        ast_rules = [
            ImportsHasNotCyclicalDeps(all_documents),
            EmbeddedTypeHasLowLevel(all_documents),
            ImportTypeExists(all_documents),
        ]

        analyzer = Analyzer(all_documents)
        self._errors.extend(analyzer.analyze(ast_rules))

    @staticmethod
    def _reclassify_embedded_types(all_documents: list[DocumentRoot]) -> None:
        """Resolve embedded types using originals from the document tree.

        Factory adds embedded entities/routines to body with data from the current document.
        This method enriches each embedded node with metadata from its original (non-embedded)
        definition: signature, annotations, properties, methods, and recalculated location.
        Factory-provided mutations and data are preserved for rule validation.

        If the original type is a different kind (entity vs routine), the embedded node
        is moved to the correct list.
        """
        # Build lookup: type name -> original (non-embedded) node
        entity_by_name: dict[str, EntityTypeNode] = {}
        routine_by_name: dict[str, RoutineTypeNode] = {}
        for doc in all_documents:
            for entity in doc.body.entities:
                if not entity.embedded and entity.name not in entity_by_name:
                    entity_by_name[entity.name] = entity
            for routine in doc.body.routines:
                if not routine.embedded and routine.name not in routine_by_name:
                    routine_by_name[routine.name] = routine

        for doc in all_documents:
            AST._reclassify_entities(doc, entity_by_name, routine_by_name)
            AST._reclassify_routines(doc, entity_by_name, routine_by_name)

    @staticmethod
    def _reclassify_entities(
        doc: DocumentRoot,
        entity_by_name: dict[str, EntityTypeNode],
        routine_by_name: dict[str, RoutineTypeNode],
    ) -> None:
        """Reclassify embedded entities: enrich from originals or move to routines."""
        entities_to_move: list[EntityTypeNode] = []
        entities_to_keep: list[EntityTypeNode] = []

        for entity in doc.body.entities:
            if not entity.embedded:
                entities_to_keep.append(entity)
                continue
            if entity.name in routine_by_name:
                entities_to_move.append(entity)
            elif entity.name in entity_by_name:
                original = entity_by_name[entity.name]
                entity.signature = original.signature
                entity.annotations = original.annotations
                entity.properties = original.properties
                entity.methods = original.methods
                entity.location = str(Path(original.root.path) / original.location)
                entities_to_keep.append(entity)
            else:
                entities_to_keep.append(entity)

        doc.body.entities = entities_to_keep

        for entity in entities_to_move:
            original = routine_by_name[entity.name]
            doc.body.routines.append(
                RoutineTypeNode(
                    name=entity.name,
                    signature=original.signature,
                    location=str(Path(original.root.path) / original.location),
                    annotations=original.annotations,
                    embedded=True,
                    data=entity.data,
                    parent=doc.body,
                    root=doc,
                )
            )

    @staticmethod
    def _reclassify_routines(
        doc: DocumentRoot,
        entity_by_name: dict[str, EntityTypeNode],
        routine_by_name: dict[str, RoutineTypeNode],
    ) -> None:
        """Reclassify embedded routines: enrich from originals or move to entities."""
        routines_to_move: list[RoutineTypeNode] = []
        routines_to_keep: list[RoutineTypeNode] = []

        for routine in doc.body.routines:
            if not routine.embedded:
                routines_to_keep.append(routine)
                continue
            if routine.name in entity_by_name:
                routines_to_move.append(routine)
            elif routine.name in routine_by_name:
                original = routine_by_name[routine.name]
                routine.signature = original.signature
                routine.annotations = original.annotations
                routine.location = str(Path(original.root.path) / original.location)
                routines_to_keep.append(routine)
            else:
                routines_to_keep.append(routine)

        doc.body.routines = routines_to_keep

        for routine in routines_to_move:
            original = entity_by_name[routine.name]
            doc.body.entities.append(
                EntityTypeNode(
                    name=routine.name,
                    signature=original.signature,
                    location=str(Path(original.root.path) / original.location),
                    annotations=original.annotations,
                    properties=original.properties,
                    methods=original.methods,
                    embedded=True,
                    mutations=[],  # embedded routine has no mutations
                    data=routine.data,
                    parent=doc.body,
                    root=doc,
                )
            )

    def document(self, path: str) -> DocumentRoot:
        """Look up a DocumentRoot by its directory path at O(1)."""
        resolved = str(Path(path).resolve())
        if resolved not in self._index:
            raise DocumentNotFoundError(f"Document not found for path: {path}")
        return self._index[resolved]

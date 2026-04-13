from __future__ import annotations

import os
from pathlib import Path

from .analyzer import Analyzer
from .errors import ManifestRuleError, ProjectRuleError
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
    ImportHasType,
    ImportHasValidFromPath,
    ImportsCanNotBeEmpty,
    ImportsHasNotCyclicalDeps,
    ImportsHasOnlyValidKeys,
    ImportTypeExists,
    MutationExists,
    MutationIsValid,
    ReturnTypeHasLink,
    RoutineHasOnlyValidKeys,
    UsageLinksHasNotConflicts,
)
from .visitor import Visitor


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
        self._path = os.path.normpath(os.path.relpath(self._path))

        # Map from directory path to its DocumentRoot (for parent-child wiring)
        loaded: dict[str, DocumentRoot] = {}

        # Walk directories top-down so parents are loaded before children
        for dirpath, _dirnames, filenames in os.walk(self._path):
            if "CODEMANIFEST" not in filenames:
                continue

            dirpath_str = dirpath if isinstance(dirpath, str) else str(dirpath)

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
            ImportHasType(),
            ImportHasValidFromPath(),
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
            EntityHasOnlyValidKeys(),
            RoutineHasOnlyValidKeys(),
        ]

        for doc in all_documents:
            visitor = Visitor(doc)
            self._errors.extend(visitor.analyze(document_rules))

        # Apply project-level rules via Analyzer
        project_rules = [
            ImportsHasNotCyclicalDeps(all_documents),
            EmbeddedTypeHasLowLevel(all_documents),
            ImportTypeExists(all_documents),
        ]

        analyzer = Analyzer(all_documents)
        self._errors.extend(analyzer.analyze(project_rules))

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
            # Collect entities to move from entities to routines
            entities_to_move: list[EntityTypeNode] = []
            entities_to_keep: list[EntityTypeNode] = []

            for entity in doc.body.entities:
                if not entity.embedded:
                    entities_to_keep.append(entity)
                    continue
                if entity.name in routine_by_name:
                    # Original is routine, embedded is in entities — move to routines
                    entities_to_move.append(entity)
                elif entity.name in entity_by_name:
                    # Same type — enrich from original
                    original = entity_by_name[entity.name]
                    entity.signature = original.signature
                    entity.annotations = original.annotations
                    entity.properties = original.properties
                    entity.methods = original.methods
                    entity.location = os.path.join(original.root.path, original.location)
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
                        location=os.path.join(original.root.path, original.location),
                        annotations=original.annotations,
                        embedded=True,
                        data=entity.data,
                        parent=doc.body,
                        root=doc,
                    )
                )

            # Collect routines to move from routines to entities
            routines_to_move: list[RoutineTypeNode] = []
            routines_to_keep: list[RoutineTypeNode] = []

            for routine in doc.body.routines:
                if not routine.embedded:
                    routines_to_keep.append(routine)
                    continue
                if routine.name in entity_by_name:
                    # Original is entity, embedded is in routines — move to entities
                    routines_to_move.append(routine)
                elif routine.name in routine_by_name:
                    # Same type — enrich from original
                    original = routine_by_name[routine.name]
                    routine.signature = original.signature
                    routine.annotations = original.annotations
                    routine.location = os.path.join(original.root.path, original.location)
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
                        location=os.path.join(original.root.path, original.location),
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

    def codemanifest(self, path: str) -> DocumentRoot:
        """Look up a DocumentRoot by its directory path at O(1)."""
        resolved = str(Path(path).resolve())
        if resolved not in self._index:
            raise KeyError(f"Document not found for path: {path}")
        return self._index[resolved]

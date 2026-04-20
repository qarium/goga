from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ASTRuleError

if TYPE_CHECKING:
    from ..nodes import DocumentRoot


class ASTRule:
    """Base class for AST-level rules."""

    def __init__(self, tree: list[DocumentRoot], name: str) -> None:
        self._name = name
        self._tree = tree

    @property
    def name(self) -> str:
        return self._name

    @property
    def tree(self) -> list[DocumentRoot]:
        return self._tree

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        raise NotImplementedError


class ImportsHasNotCyclicalDeps(ASTRule):
    """Rule: imports must not form cycles across documents."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="imports_has_not_cyclical_deps")

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        # Build a map of resolved path -> set of resolved import paths
        import_map: dict[str, set[str]] = {}
        for doc in self._tree:
            doc_path = doc.path
            import_paths: set[str] = set()
            for item in doc.header.imports.types + doc.header.imports.usages:
                import_paths.add(item.from_path)
            import_map[doc_path] = import_paths

        errors: list[ASTRuleError] = []
        doc_path = document.path

        for item in document.header.imports.types + document.header.imports.usages:
            imported_path = item.from_path
            # Check if the imported document also imports from the current document's path
            if imported_path in import_map and doc_path in import_map[imported_path]:
                errors.append(
                    ASTRuleError(
                        message=f"Cyclical import: package '{doc_path}' and '{imported_path}' import from each other",
                        rule=self.name,
                        document=document,
                        node=item,
                    )
                )

        return errors


class ImportTypeExists(ASTRule):
    """Rule: every imported type must exist in the target document."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="import_type_exists")

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        errors: list[ASTRuleError] = []

        # Build O(1) lookup: doc path -> DocumentRoot
        path_lookup: dict[str, DocumentRoot] = {str(Path(doc.path).resolve()): doc for doc in self._tree}

        for item in document.header.imports.types:
            from_path = item.from_path

            # Skip if from_path does not exist on filesystem
            if not Path(from_path).exists():
                continue

            target_doc = path_lookup.get(str(Path(from_path).resolve()))
            if target_doc is None:
                continue

            # Collect all available type names in the target document
            entity_names = {entity.name for entity in target_doc.body.entities}
            routine_names = {routine.name for routine in target_doc.body.routines}
            header_type_names = set(target_doc.header.types)
            available_names = entity_names | routine_names | header_type_names

            for type_name in item.type_name:
                if type_name not in available_names:
                    errors.append(
                        ASTRuleError(
                            message=(
                                f"Type '{type_name}' imported from '{from_path}'"
                                f" is not defined in that package's CODEMANIFEST"
                            ),
                            rule=self.name,
                            document=document,
                            node=item,
                        )
                    )

        return errors


class EmbeddedTypeHasLowLevel(ASTRule):
    """Rule: embedded types must be defined in documents lower in the file hierarchy."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="embedded_type_has_low_level")

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:  # noqa: C901
        errors: list[ASTRuleError] = []
        current_path = os.path.normpath(document.path)

        # Collect all embedded entities and routines from the document body
        embedded_entities = [e for e in document.body.entities if e.embedded]
        embedded_routines = [r for r in document.body.routines if r.embedded]

        # Build a lookup: type name -> document that defines it
        type_source: dict[str, DocumentRoot] = {}
        for doc in self._tree:
            for entity in doc.body.entities:
                if not entity.embedded:
                    type_source[entity.name] = doc
            for routine in doc.body.routines:
                if not routine.embedded:
                    type_source[routine.name] = doc

        for entity in embedded_entities:
            source_doc = type_source.get(entity.name)
            if source_doc is not None:
                source_path = os.path.normpath(source_doc.path)
                if not source_path.startswith(current_path + os.sep):
                    errors.append(
                        ASTRuleError(
                            message=(
                                f"Embedded entity '{entity.name}' comes from '{source_path}',"
                                f" but can only be embedded from packages nested below '{current_path}'"
                            ),
                            rule=self.name,
                            document=document,
                            node=entity,
                        )
                    )

        for routine in embedded_routines:
            source_doc = type_source.get(routine.name)
            if source_doc is not None:
                source_path = os.path.normpath(source_doc.path)
                if not source_path.startswith(current_path + os.sep):
                    errors.append(
                        ASTRuleError(
                            message=(
                                f"Embedded routine '{routine.name}' comes from '{source_path}',"
                                f" but can only be embedded from packages nested below '{current_path}'"
                            ),
                            rule=self.name,
                            document=document,
                            node=routine,
                        )
                    )

        return errors

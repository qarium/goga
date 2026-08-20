from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ...errors import ASTRuleError
from ..base.ast import ASTRule

if TYPE_CHECKING:
    from ...nodes import DocumentRoot


class ImportsHasNotCyclicalDeps(ASTRule):
    """Rule: imports must not form cycles across documents."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="imports_has_not_cyclical_deps")

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        """Detect cyclic import dependencies between documents.

        Args:
            document: Document root to validate against the full tree.

        Returns:
            Errors for import paths that form a cycle with the current document.
        """
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
            if imported_path in import_map and doc_path in import_map[imported_path]:
                errors.append(
                    ASTRuleError(
                        message=(f"Cyclical import: package '{doc_path}' and '{imported_path}' import from each other"),
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
        """Validate that imported types exist in their target documents.

        Args:
            document: Document root to validate against the full tree.

        Returns:
            Errors for imported types missing from the source package.
        """
        errors: list[ASTRuleError] = []

        path_lookup: dict[str, DocumentRoot] = {str(Path(doc.path).resolve()): doc for doc in self._tree}

        for item in document.header.imports.types:
            from_path = item.from_path

            if not Path(from_path).exists():
                continue

            target_doc = path_lookup.get(str(Path(from_path).resolve()))
            if target_doc is None:
                continue

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


def _is_nested_below(source_path: str, current_path: str) -> bool:
    """Check that a normalized source path lies strictly below the current package.

    Args:
        source_path: Normalized path of the package providing the embedded type.
        current_path: Normalized path of the package declaring the embedding.

    Returns:
        True when the source package is nested strictly below the current one.
    """
    if current_path == ".":
        escapes_root = source_path in (".", "..") or source_path.startswith(".." + os.sep)

        return not escapes_root and not Path(source_path).is_absolute()

    return source_path.startswith(current_path + os.sep)


class EmbeddedTypeHasLowLevel(ASTRule):
    """Rule: embedded types must be defined in documents lower in the file hierarchy."""

    def __init__(self, tree: list[DocumentRoot]) -> None:
        super().__init__(tree=tree, name="embedded_type_has_low_level")

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:  # noqa: C901
        """Validate that embedded types originate from packages nested below the current one.

        Args:
            document: Document root to validate against the full tree.

        Returns:
            Errors for embedded types sourced from invalid locations.
        """
        errors: list[ASTRuleError] = []
        current_path = os.path.normpath(document.path)

        embedded_entities = [e for e in document.body.entities if e.embedded]
        embedded_routines = [r for r in document.body.routines if r.embedded]

        # Resolve sources through import declarations first
        import_source: dict[str, str] = {}
        for item in document.header.imports.types:
            for type_name in item.type_name:
                import_source[type_name] = os.path.normpath(item.from_path)

        # Fallback: global name map for types not resolved via imports
        type_source: dict[str, DocumentRoot] = {}
        for doc in self._tree:
            for entity in doc.body.entities:
                if not entity.embedded:
                    type_source[entity.name] = doc
            for routine in doc.body.routines:
                if not routine.embedded:
                    type_source[routine.name] = doc

        def _resolve_source(name: str) -> str | None:
            """Resolve a type name to its source path via imports or global name map."""
            if name in import_source:
                return import_source[name]
            source_doc = type_source.get(name)
            if source_doc is not None:
                return os.path.normpath(source_doc.path)
            return None

        for entity in embedded_entities:
            source_path = _resolve_source(entity.name)
            if source_path is not None and not _is_nested_below(source_path, current_path):
                errors.append(
                    ASTRuleError(
                        message=(
                            f"Embedded entity '{entity.name}' comes from"
                            f" '{source_path}', but can only be embedded from"
                            f" packages nested below '{current_path}'"
                        ),
                        rule=self.name,
                        document=document,
                        node=entity,
                    )
                )

        for routine in embedded_routines:
            source_path = _resolve_source(routine.name)
            if source_path is not None and not _is_nested_below(source_path, current_path):
                errors.append(
                    ASTRuleError(
                        message=(
                            f"Embedded routine '{routine.name}' comes from"
                            f" '{source_path}', but can only be embedded from"
                            f" packages nested below '{current_path}'"
                        ),
                        rule=self.name,
                        document=document,
                        node=routine,
                    )
                )

        return errors

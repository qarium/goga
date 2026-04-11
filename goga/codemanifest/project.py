from __future__ import annotations

import os

from goga.codemanifest.analyzer import Analyzer
from goga.codemanifest.errors import ManifestRuleError, ProjectRuleError
from goga.codemanifest.factory import Factory
from goga.codemanifest.nodes import DocumentRoot
from goga.codemanifest.rules import (
    AllUsagesIsUsed,
    ImportHasTypeRule,
    ImportHasValidFromPathRule,
    ImportsCanNotBeEmptyRule,
    ImportsHasNotCyclicalDepsRule,
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

        # Apply document-level rules via Visitor
        document_rules = [
            ImportsCanNotBeEmptyRule(),
            ImportHasTypeRule(),
            ImportHasValidFromPathRule(),
        ]

        all_documents = _flatten_tree(self._tree)
        for doc in all_documents:
            visitor = Visitor(doc)
            self._errors.extend(visitor.analyze(document_rules))

        # Apply project-level rules via Analyzer
        project_rules = [
            ImportsHasNotCyclicalDepsRule(all_documents),
            AllUsagesIsUsed(all_documents),
        ]

        analyzer = Analyzer(all_documents)
        self._errors.extend(analyzer.analyze(project_rules))

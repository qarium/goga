from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import requests

from ....errors import DocumentRuleError
from ....nodes.header import ImportTypeItemNode, ImportUsageItemNode
from ...base.document import DocumentRule

if TYPE_CHECKING:
    from ....nodes import DocumentNode

_OK_STATUS = 200
_METHOD_NOT_ALLOWED = 405
_REQUEST_TIMEOUT = 5


class AllUsagesIsUsed(DocumentRule):
    """Rule: every usage declared in the header must appear in links of at least one AnnotationsNode."""

    def __init__(self) -> None:
        super().__init__(name="all_usages_is_used")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that every declared usage is referenced by at least one annotation link.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for declared but unused usages.
        """
        usage_names = [item.name for item in node.root.header.usages.items]
        if not usage_names:
            return []

        all_links: set[str] = set()

        all_links.update(node.root.header.annotations.links)

        for usage_item in node.root.header.usages.items:
            all_links.update(usage_item.annotations.links)

        for entity in node.root.body.entities:
            all_links.update(entity.annotations.links)
            for method in entity.methods:
                all_links.update(method.annotations.links)
            for prop in entity.properties:
                all_links.update(prop.annotations.links)

        for routine in node.root.body.routines:
            all_links.update(routine.annotations.links)

        errors: list[DocumentRuleError] = []
        for usage_name in usage_names:
            if usage_name not in all_links:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Usage '{usage_name}' is declared but not referenced in any annotation"
                            f" — either use it or remove the declaration"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )

        return errors


class UsageFilepathExists(DocumentRule):
    """Rule: every usage with a filepath must point to an existing file within the project root."""

    def __init__(self) -> None:
        super().__init__(name="usage_filepath_exists")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that usage filepaths exist within the project usages directory.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for usage filepaths that are out of scope or missing.
        """
        errors: list[DocumentRuleError] = []
        cwd = Path.cwd().resolve()

        for item in node.root.header.usages.items:
            filepath = item.annotations.filepath
            if not filepath:
                continue
            if item.annotations.url:
                continue

            if not filepath.startswith(".goga/usages/"):
                errors.append(
                    DocumentRuleError(
                        message=f"Usage '{item.name}' filepath '{filepath}' is not built from '.goga/usages/'",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            resolved = Path(filepath).resolve()
            usages_dir = (cwd / ".goga" / "usages").resolve()
            if not resolved.is_relative_to(usages_dir):
                errors.append(
                    DocumentRuleError(
                        message=f"Usage '{item.name}' filepath '{filepath}' is not built from the root of the project",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )
                continue

            if not resolved.exists():
                errors.append(
                    DocumentRuleError(
                        message=f"Usage '{item.name}' filepath '{filepath}' does not exist on filesystem",
                        rule=self.name,
                        document=node.root,
                        node=item,
                    )
                )

        return errors


class UsageUrlIsAccessible(DocumentRule):
    """Rule: every usage with a URL must be accessible via HTTP (status 200)."""

    def __init__(self) -> None:
        super().__init__(name="usage_url_is_accessible")
        self._url_cache: dict[str, None | tuple[str, int | object]] = {}

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that usage URLs are reachable over HTTP.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for usage URLs that are not accessible.
        """
        errors: list[DocumentRuleError] = []

        for item in node.root.header.usages.items:
            url = item.annotations.url
            if not url:
                continue
            if item.annotations.filepath:
                continue

            errors.extend(self._check_url(item, url, node.root))

        return errors

    def _check_url(self, item, url: str, document) -> list[DocumentRuleError]:
        """Check a single URL using cached outcomes to avoid duplicate requests."""
        if url in self._url_cache:
            return self._outcome_to_errors(self._url_cache[url], item, url, document)

        outcome = self._http_check(url)
        self._url_cache[url] = outcome
        return self._outcome_to_errors(outcome, item, url, document)

    def _http_check(self, url: str) -> None | tuple[str, int | object]:
        """Perform an HTTP HEAD check and return None or an error outcome tuple."""
        try:
            response = requests.head(url, timeout=_REQUEST_TIMEOUT)
            if response.status_code == _METHOD_NOT_ALLOWED:
                return self._check_via_get(url)
            if response.status_code != _OK_STATUS:
                return ("http", response.status_code)
            return None
        except requests.exceptions.RequestException as e:
            return ("error", e)
        except Exception as e:
            return ("error", e)

    def _check_via_get(self, url: str) -> None | tuple[str, int | object]:
        """Fallback HTTP GET check when HEAD is not allowed."""
        try:
            response = requests.get(url, timeout=_REQUEST_TIMEOUT)
            if response.status_code != _OK_STATUS:
                return ("http", response.status_code)
        except Exception as e:
            return ("error", e)
        return None

    def _outcome_to_errors(self, outcome, item, url: str, document) -> list[DocumentRuleError]:
        """Convert an HTTP outcome tuple into a list of rule errors."""
        if outcome is None:
            return []
        kind, detail = outcome
        if kind == "http":
            return [self._not_accessible(item, url, detail, document)]
        return [self._request_failed(item, url, detail, document)]

    def _not_accessible(self, item, url: str, status_code: int, document) -> DocumentRuleError:
        """Build an error for a URL that returned a non-200 HTTP status."""
        return DocumentRuleError(
            message=f"Usage '{item.name}' URL '{url}' returned HTTP {status_code} — expected {_OK_STATUS}",
            rule=self.name,
            document=document,
            node=item,
        )

    def _request_failed(self, item, url: str, reason, document) -> DocumentRuleError:
        """Build an error for a URL that failed with a transport-level exception."""
        return DocumentRuleError(
            message=f"Usage '{item.name}' URL '{url}' request failed: {reason!s}",
            rule=self.name,
            document=document,
            node=item,
        )


class UsageLinksHasNotConflicts(DocumentRule):
    """Rule: usage names must not conflict with import type names (without alias) or entity/routine names."""

    def __init__(self) -> None:
        super().__init__(name="usage_links_has_not_conflicts")

    def check(self, node: DocumentNode) -> list[DocumentRuleError]:
        """Validate that usage names do not conflict with imported or entity/routine names.

        Args:
            node: Document node wrapping the root to validate.

        Returns:
            Errors for usage names that collide with other declarations.
        """
        usage_names = [item.name for item in node.root.header.usages.items]
        if not usage_names:
            return []

        type_names_without_alias = self._collect_import_type_names(node)
        entity_names = self._collect_entity_routine_names(node)
        return self._check_conflicts(node, usage_names, type_names_without_alias, entity_names)

    def _collect_import_type_names(self, node: DocumentNode) -> set[str]:
        """Collect imported type names that have no alias."""
        names: set[str] = set()
        for import_item in node.root.header.imports.types + node.root.header.imports.usages:
            if import_item.alias:
                continue
            if isinstance(import_item, ImportTypeItemNode):
                names.update(import_item.type_name)
            elif isinstance(import_item, ImportUsageItemNode):
                names.update(import_item.usage_name)
        return names

    def _collect_entity_routine_names(self, node: DocumentNode) -> dict[str, str]:
        """Collect non-embedded entity and routine names mapped to their kind."""
        names: dict[str, str] = {}
        for entity in node.root.body.entities:
            if not entity.embedded:
                names[entity.name] = "entity"
        for routine in node.root.body.routines:
            if not routine.embedded:
                names[routine.name] = "routine"
        return names

    def _check_conflicts(
        self,
        node: DocumentNode,
        usage_names: list[str],
        type_names_without_alias: set[str],
        entity_names: dict[str, str],
    ) -> list[DocumentRuleError]:
        """Check usage names against imported and entity/routine names for conflicts."""
        errors: list[DocumentRuleError] = []
        for name in usage_names:
            if name in type_names_without_alias:
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Usage key '{name}' conflicts with imported name '{name}'"
                            f" — rename the usage or use an alias in Imports"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )
            if name in entity_names:
                kind = entity_names[name]
                errors.append(
                    DocumentRuleError(
                        message=(
                            f"Usage key '{name}' conflicts with {kind} '{name}' — rename the usage to avoid ambiguity"
                        ),
                        rule=self.name,
                        document=node.root,
                        node=node,
                    )
                )

        return errors

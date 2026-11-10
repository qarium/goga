"""Facade contract lock of the document rules aggregation cell.

The ``goga/ast/rules/document`` CODEMANIFEST declares the aggregation
facade: every rule of the five rule zones re-exported as-is via
embedding. ``DocumentRule`` stays in its own cell facade
(``goga.ast.rules.base``) — it is a zone input, not a zone product, so it
is not part of this facade.
"""

from __future__ import annotations

import goga.ast.rules.document as document_facade
import goga.ast.rules.document.annotations as annotations_zone
import goga.ast.rules.document.imports as imports_zone
import goga.ast.rules.document.mutation as mutation_zone
import goga.ast.rules.document.structures as structures_zone
import goga.ast.rules.document.usages as usages_zone

AGGREGATED_NAMES = [
    "AllUsagesIsUsed",
    "AnnotationLinksExists",
    "EmbeddedEntityCanNotHasMutations",
    "EntitiesAndRoutinesHasNotConflicts",
    "EntityHasOnlyValidKeys",
    "ImportHasNotDuplicate",
    "ImportHasValidFromPath",
    "ImportIsUsed",
    "ImportItemIsValid",
    "ImportUsageExists",
    "ImportsCanNotBeEmpty",
    "ImportsHasOnlyValidKeys",
    "LocationIsRequired",
    "MutationExists",
    "MutationIsValid",
    "ReturnTypeHasLink",
    "RoutineHasOnlyValidKeys",
    "SignatureIsValid",
    "UsageFilepathExists",
    "UsageLinksHasNotConflicts",
    "UsageUrlIsAccessible",
]


class TestDocumentFacade:
    def test_facade_all_is_exact_contract_set(self) -> None:
        """__all__ carries exactly the 21 aggregated rule names."""
        assert document_facade.__all__ == AGGREGATED_NAMES

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention (uppercase first)."""
        assert document_facade.__all__ == sorted(document_facade.__all__)

    def test_every_name_resolves_on_the_package(self) -> None:
        """Every facade name is defined on the package."""
        for name in AGGREGATED_NAMES:
            assert hasattr(document_facade, name), f"{name} is not defined on goga.ast.rules.document"

    def test_reexports_are_identical_to_zone_objects(self) -> None:
        """The aggregation re-exports the zone objects themselves, not copies."""
        assert document_facade.AnnotationLinksExists is annotations_zone.AnnotationLinksExists
        assert document_facade.ImportIsUsed is imports_zone.ImportIsUsed
        assert document_facade.MutationIsValid is mutation_zone.MutationIsValid
        assert document_facade.SignatureIsValid is structures_zone.SignatureIsValid
        assert document_facade.AllUsagesIsUsed is usages_zone.AllUsagesIsUsed

    def test_document_rule_is_not_part_of_this_facade(self) -> None:
        """DocumentRule belongs to goga.ast.rules.base — not to the zone product facade."""
        import goga.ast.rules.base as base_zone

        assert "DocumentRule" not in document_facade.__all__
        assert "DocumentRule" in base_zone.__all__

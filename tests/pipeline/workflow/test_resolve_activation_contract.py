"""Contract tests for the ``resolve_activation`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
three-parameter signature (``cli_profile``, ``env_profile``,
``workflow_default`` — no defaults), and the ``str | None`` return contract.
These tests pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

from goga.pipeline.workflow import resolve_activation


class TestResolveActivationContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_resolve_activation_importable_from_facade(self) -> None:
        """resolve_activation is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.resolve_activation is resolve_activation
        assert "resolve_activation" in facade.__all__

    def test_resolve_activation_signature_declares_three_channels(self) -> None:
        """The signature declares exactly cli_profile, env_profile, workflow_default — no defaults."""
        parameters = inspect.signature(resolve_activation).parameters

        assert list(parameters) == ["cli_profile", "env_profile", "workflow_default"]
        assert all(parameter.default is inspect.Parameter.empty for parameter in parameters.values())

    def test_resolve_activation_return_annotation_is_str_or_none(self) -> None:
        """The return annotation is ``str | None`` — the effective name or absence."""
        hints = get_type_hints(resolve_activation)

        assert hints["return"] == str | None

    def test_resolve_activation_pure_first_non_empty_semantics(self) -> None:
        """The routine folds channels strongest-first and returns None when all are unset."""
        assert resolve_activation("cli", "env", "default") == "cli"
        assert resolve_activation(None, None, None) is None

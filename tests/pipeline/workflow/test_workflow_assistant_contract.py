"""Contract tests for the ``WorkflowAssistant`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
eight declared properties in the fixed canonical order (``name``, ``prompt``,
``skills``, ``agent``, ``delegate``, ``env``, ``gate``, ``when``), the exact
defaults (``name`` required; ``delegate=False``; ``gate=False``;
``when="checkpoints"``; the four absence fields ``None``), and kw_only
construction. These tests pin the contract surface — behavior lives in the
logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowAssistant

from tests.conftest import is_kw_only_dataclass


class TestWorkflowAssistantContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_assistant_importable_from_facade(self) -> None:
        """WorkflowAssistant is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowAssistant is WorkflowAssistant
        assert "WorkflowAssistant" in facade.__all__

    def test_workflow_assistant_is_kw_only_dataclass(self) -> None:
        """Every field of WorkflowAssistant is keyword-only."""
        assert is_kw_only_dataclass(WorkflowAssistant)

    def test_workflow_assistant_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — eight parameters, name required.

        name, prompt, skills, agent, delegate, env, gate, when in the declared
        order; ``name`` has no default (the model is nameless otherwise), the
        absence fields default to ``None``, the empty defaults materialize
        ``False``/``False``/``"checkpoints"``, and the annotations pin the
        declared types.
        """
        parameters = list(inspect.signature(WorkflowAssistant).parameters.values())
        empty = inspect.Parameter.empty

        assert [parameter.name for parameter in parameters] == [
            "name",
            "prompt",
            "skills",
            "agent",
            "delegate",
            "env",
            "gate",
            "when",
        ]
        assert [parameter.default for parameter in parameters] == [
            empty,
            None,
            None,
            None,
            False,
            None,
            False,
            "checkpoints",
        ]
        assert [parameter.annotation for parameter in parameters] == [
            "str",
            "str | None",
            "list[str] | None",
            "str | None",
            "bool",
            "dict[str, str] | None",
            "bool",
            "str",
        ]

    def test_workflow_assistant_field_order_fixed(self) -> None:
        """Field order is fixed across all eight fields (the dataclass ordering rule)."""
        names = [field.name for field in fields(WorkflowAssistant)]

        assert names == [
            "name",
            "prompt",
            "skills",
            "agent",
            "delegate",
            "env",
            "gate",
            "when",
        ]

    def test_workflow_assistant_name_is_required(self) -> None:
        """Constructing without ``name`` raises TypeError — the one required field."""
        with pytest.raises(TypeError):
            WorkflowAssistant()  # type: ignore[call-arg]

    def test_workflow_assistant_constructible_kw_only(self) -> None:
        """WorkflowAssistant is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowAssistant("reviewer")  # type: ignore[misc]

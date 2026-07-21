"""Workflow cell — declarative parser of project-level workflow-files.

Reads a workflow-file, validates its structure (known keys, field types, loop
counts), and returns a :class:`WorkflowDocument` carrying declarative
instructions for the compiler. The cell is intentionally declarative: it does
not know about the compiler or any compiler-level concept.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. With the parser landed, the contract names ``parse_workflow``,
``WorkflowDocument``, and ``WorkflowStage`` are re-exported here, alongside the
``WorkflowSyntaxError`` structural-error type (mirroring the compiler cell's
``StructuralError`` re-export).
"""

from .parse_workflow import WorkflowSyntaxError, parse_workflow
from .workflow_document import WorkflowDocument
from .workflow_extend_stage import WorkflowExtendStage
from .workflow_stage import WorkflowStage

__all__: list[str] = [
    "WorkflowDocument",
    "WorkflowExtendStage",
    "WorkflowStage",
    "WorkflowSyntaxError",
    "parse_workflow",
]

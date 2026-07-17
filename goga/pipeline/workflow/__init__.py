"""Workflow cell — declarative parser of project-level workflow-files.

Reads a workflow-file, validates its structure (known keys, field types, loop
counts), and returns a :class:`WorkflowDocument` carrying declarative
instructions for the compiler. The cell is intentionally declarative: it does
not know about the compiler or any compiler-level concept.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. Once all entity tasks land, the contract names ``parse_workflow``,
``WorkflowDocument``, and ``WorkflowStage`` are re-exported here.
"""

__all__: list[str] = []

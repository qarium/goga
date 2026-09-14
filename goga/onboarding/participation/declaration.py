"""The session declaration surface of one tool.

The entity declared in the cell CODEMANIFEST with ``location: declaration.py``:
the moment-one surface ``ToolDeclaration``. The surface is delivered to one
tool's declare-session hook — the invitation marker and the buffer of the
declared questions and skip paths. A hook of a non-invited tool returns
immediately; the buffered data is read by the engine after the delivery of
the moment completes.
"""

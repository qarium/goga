"""The tool-config reading cell — the read side of the tool-config standard.

The cell owns the standardized path composition of one tool config file and
its raw passthrough load: ``.goga/tools/<tool>/<filename>`` read back with
no interpretation — the content belongs to the tool that owns it. The
onboarding engine is the single writer of the same standard.
"""

from .loader import load_tool_config

__all__ = ["load_tool_config"]

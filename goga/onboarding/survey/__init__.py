"""Survey cell — the survey of the onboarding session.

The owner of the core question tree, the session plan assembly with the
tool question blocks, the application of skip requests, and the
interactive run. The survey is interactive on the host through the click
practice; the core sections are conditional on the filesystem state.
Questions are declarative data — the engine asks them itself; a tool hook
is never called to survey.
"""

from .core import core_questions
from .plan import SessionPlan, apply_skips, assemble_session_plan

__all__: list[str] = ["SessionPlan", "apply_skips", "assemble_session_plan", "core_questions"]

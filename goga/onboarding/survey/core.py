"""The core question tree of the onboarding session.

The entity declared in the cell CODEMANIFEST with ``location: core.py``:
the tree builder ``core_questions``. The builder composes the eight core
sections in survey order — the language choice, the base-convention gate,
the codemanifest entries, the build and pipeline executors, the docker
image decision, the tools collection, and the usages records — with the
image hints completed from the runtime minor tag, never a hardcoded one.
"""

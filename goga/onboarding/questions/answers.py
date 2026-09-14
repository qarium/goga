"""The session answer space of the onboarding session.

The entity declared in the cell CODEMANIFEST with ``location: answers.py``:
the accumulator ``SessionAnswers``. The space is the single mutable
accumulator of one run — every answer, core and tool, lands here exactly
once. The structure is nested mappings keyed by question ids — groups hold
mappings, no dotted keys are ever stored.
"""

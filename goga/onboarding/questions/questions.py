"""The question records of the onboarding session.

The entities declared in the cell CODEMANIFEST with ``location: questions.py``:
the question record ``Question`` and the nesting node ``QuestionGroup``. The
records are immutable declarative data of the survey — rendering the question
and validating the answer value belong to the survey engine. The kind fixes
the parameterization; the tree path of a node — the ids from the root to the
node joined by dots — addresses the node in skip requests and answer paths.
"""

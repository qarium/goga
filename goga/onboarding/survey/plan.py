"""The session plan layer of the survey.

The entities declared in the cell CODEMANIFEST with ``location: plan.py``:
the plan record ``SessionPlan`` and the two plan routines
``assemble_session_plan`` and ``apply_skips``. Assembly joins the core
tree with the tool question blocks in one root under the reserved-name
and local-name guards; skip application resolves every declared path and
removes the addressed subtrees as one order-independent set.
"""

"""The artifact generator of the onboarding session.

The entities declared in the cell CODEMANIFEST with ``location: generator.py``:
the generator ``FileGenerator`` and the report record ``CreatedFile``. The
generator writes every artifact of the session from the committed answer
space and the committed tool contributions — the project config, the
Dockerfile, the base conventions download, and the tool config files — and
reports the created files with attribution. An existing .goga/config.yml is
never rewritten: whoever created it first wins.
"""

"""Generator cell — the artifact generation of the onboarding session.

The owner of every artifact write of the run: the project config, the
Dockerfile, the base conventions download, and the tool config files —
generated from the committed answer space and the committed tool
contributions, and reported with attribution. An existing .goga/config.yml
is never rewritten: whoever created it first wins.
"""

from .generator import CreatedFile, FileGenerator

__all__: list[str] = ["CreatedFile", "FileGenerator"]

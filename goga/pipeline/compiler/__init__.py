"""Compiler cell — pure transformer from goga DSL pipeline-files to afm flow-files.

Built incrementally: each entity task adds its module's import and ``__all__`` entry.
Once all entity tasks land, all 12 contract names are re-exported here.
"""

from .body_format import BodyFormat

__all__: list[str] = [
    "BodyFormat",
]

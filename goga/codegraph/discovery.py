"""Source discovery — the deterministic path-only walk of the project tree.

Finds the analyzable source files of the configured language: the exact
relative ignore entries prune directories and skip files (the same normpath
mechanics as lint — a trailing slash is insignificant), the idiomatic
per-language test files are always skipped, and only the language's primary
extension is kept. Discovery works on paths only — no file content is read
here.
"""

from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path

_EXTENSIONS: dict[str, str] = {
    "python": ".py",
    "golang": ".go",
    "javascript": ".js",
    "kotlin": ".kt",
    "swift": ".swift",
}

_TEST_PATTERNS: dict[str, str] = {
    "python": "test_*.py",
    "golang": "*_test.go",
    "javascript": "*.test.js",
    "kotlin": "*Test.kt",
    "swift": "*Tests.swift",
}


def discover_sources(language: str, ignore: list[str]) -> list[Path]:
    """Walk the project tree and return the analyzable source files of the language.

    Args:
        language: The single configured language — python, golang,
            javascript, kotlin, swift.
        ignore: Exact relative paths excluded from the walk; a trailing
            slash is insignificant (normpath semantics, the same mechanics
            as lint) and an ignored directory prunes its whole subtree.

    Returns:
        The source files of the language relative to the project root, in
        deterministic walk order.

    Raises:
        ValueError: When the language is not supported.
    """
    if language not in _EXTENSIONS:
        raise ValueError(f"unsupported language: {language!r}; expected one of {sorted(_EXTENSIONS)}")

    extension = _EXTENSIONS[language]
    test_pattern = _TEST_PATTERNS[language]
    ignore_set = {os.path.normpath(entry) for entry in ignore}

    files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk("."):
        dirnames.sort()

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if os.path.normpath(os.path.relpath(Path(dirpath, dirname))) not in ignore_set
        ]

        for name in sorted(filenames):
            relative = os.path.normpath(os.path.relpath(Path(dirpath, name)))

            if relative in ignore_set:
                continue

            if fnmatch(name, test_pattern):
                continue

            if Path(name).suffix == extension:
                files.append(Path(relative))

    return files

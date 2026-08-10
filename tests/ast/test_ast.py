"""Contract and logic tests for the AST ``ignore`` directory-pruning feature.

Covers the ``AST(path, ignore=...)`` constructor parameter and the
``load()`` directory-pruning behaviour: exact normalized relative-path match
(trailing separator insignificant, glob NOT interpreted), additive to the
built-in ``.project`` skip, and backward-compatible default of ``None``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from goga.ast import AST
from goga.ast.ast import _flatten_tree
from goga.ast.errors import DocumentNotFoundError

# Minimal but parseable CODEMANIFEST content (header-only doc). The Factory
# parses the first YAML document as the header (valid keys: Imports/Usages/
# Annotations) and tolerates missing body/footer sections, so this loads
# cleanly as a document regardless of the surrounding tree.
_MIN_CM = "Annotations: |\n  Minimal cell for AST tests.\n"


def _make_cell(directory: Path, content: str | None = None) -> None:
    """Create a directory containing a minimally-valid CODEMANIFEST file."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "CODEMANIFEST").write_text(content or _MIN_CM, encoding="utf-8")


def _has_doc(ast_obj: AST, path: Path) -> bool:
    """Return True when a document was loaded for ``path`` (resolves to O(1))."""
    try:
        ast_obj.document(str(path))
    except DocumentNotFoundError:
        return False
    return True


def _doc_paths(ast_obj: AST) -> list[str]:
    """Return normalized paths of every loaded document (flattened tree)."""
    return [os.path.normpath(d.path) for d in _flatten_tree(ast_obj.tree)]


# ---------------------------------------------------------------------------
# STEP 1 — Contract tests (API shape)
# ---------------------------------------------------------------------------


class TestAstIgnoreContract:
    def test_ast_accepts_ignore_keyword(self, tmp_path: Path) -> None:
        ast_obj = AST(str(tmp_path), ignore=[".venv/"])

        assert ast_obj._ignore == [".venv/"]

    def test_ast_backward_compatible_no_ignore(self, tmp_path: Path) -> None:
        ast_obj = AST(str(tmp_path))

        assert ast_obj._ignore is None


# ---------------------------------------------------------------------------
# STEP 4 — Logic tests (directory pruning)
# ---------------------------------------------------------------------------


class TestAstUnaffectedConsumers:
    def test_ast_default_loads_full_tree_for_consumers(self, tmp_path: Path) -> None:
        """Default ``ignore=None`` loads the full tree (schema/review/contract gate).

        Unaffected consumers (``schema``/``review``/``contract``) call ``AST(".")``
        with no ``ignore``; the default ``ignore=None`` must leave traversal
        unfiltered so every directory — including ``.venv`` — is loaded. This is
        the Design Flow C "unaffected consumers" regression gate.
        """
        _make_cell(tmp_path)
        venv = tmp_path / ".venv"
        _make_cell(venv)

        ast_obj = AST(str(tmp_path))  # default ignore=None
        ast_obj.load()

        # The .venv document IS loaded under the default (no filtering).
        assert _has_doc(ast_obj, venv)
        assert any(Path(p).name == ".venv" for p in _doc_paths(ast_obj))


class TestAstIgnorePruning:
    def test_ast_skips_ignored_directory(self, tmp_path: Path) -> None:
        _make_cell(tmp_path)
        venv = tmp_path / ".venv"
        kept = tmp_path / "kept"
        _make_cell(venv)
        _make_cell(kept)

        ast_obj = AST(str(tmp_path), ignore=[".venv/"])
        ast_obj.load()

        assert not _has_doc(ast_obj, venv)
        assert _has_doc(ast_obj, kept)

    def test_ast_ignore_none_is_unfiltered(self, tmp_path: Path) -> None:
        _make_cell(tmp_path)
        venv = tmp_path / ".venv"
        kept = tmp_path / "kept"
        _make_cell(venv)
        _make_cell(kept)

        ast_obj = AST(str(tmp_path))  # no ignore — backward-compat regression gate
        ast_obj.load()

        assert _has_doc(ast_obj, venv)
        assert _has_doc(ast_obj, kept)

    def test_ast_ignore_trailing_slash_matches_bare_name(self, tmp_path: Path) -> None:
        _make_cell(tmp_path)
        venv = tmp_path / ".venv"
        _make_cell(venv)

        ast_obj = AST(str(tmp_path), ignore=[".venv"])  # no trailing slash
        ast_obj.load()

        assert not _has_doc(ast_obj, venv)

    def test_ast_ignore_glob_does_not_match(self, tmp_path: Path) -> None:
        _make_cell(tmp_path)
        realdir = tmp_path / "realdir"
        _make_cell(realdir)

        ast_obj = AST(str(tmp_path), ignore=["*"])  # glob not interpreted
        ast_obj.load()

        assert _has_doc(ast_obj, realdir)

    def test_ast_ignore_nested_path_only_matches_exact(self, tmp_path: Path) -> None:
        _make_cell(tmp_path)
        top_venv = tmp_path / ".venv"
        nested_venv = tmp_path / "a" / "b" / ".venv"
        _make_cell(top_venv)
        _make_cell(nested_venv)

        ast_obj = AST(str(tmp_path), ignore=[".venv"])  # exact full relative path
        ast_obj.load()

        assert not _has_doc(ast_obj, top_venv)
        assert _has_doc(ast_obj, nested_venv)

    def test_ast_ignore_multisegment_relative_path_prunes(self, tmp_path: Path) -> None:
        """A multi-segment ignore entry prunes the matching nested directory.

        ``ignore=["sub/dep"]`` prunes ``sub/dep`` while leaving the sibling
        ``sub/keep`` loaded. The matching expression compares the full
        normalized relative path, so this would break if matching degraded to
        a basename check — the single-segment tests above cannot detect that.
        """
        _make_cell(tmp_path)
        nested = tmp_path / "sub" / "dep"
        sibling = tmp_path / "sub" / "keep"
        _make_cell(nested)
        _make_cell(sibling)

        ast_obj = AST(str(tmp_path), ignore=["sub/dep"])
        ast_obj.load()

        assert not _has_doc(ast_obj, nested)
        assert _has_doc(ast_obj, sibling)

    def test_ast_ignore_is_additive_to_project_skip(self, tmp_path: Path) -> None:
        _make_cell(tmp_path)
        project = tmp_path / ".project"
        venv = tmp_path / ".venv"
        _make_cell(project)
        _make_cell(venv)

        ast_obj = AST(str(tmp_path), ignore=[".venv"])
        ast_obj.load()

        assert not _has_doc(ast_obj, project)  # built-in .project skip preserved
        assert not _has_doc(ast_obj, venv)  # additive ignore
        assert _doc_paths(ast_obj)  # root doc still loaded


if __name__ == "__main__":
    pytest.main([__file__, "-x"])

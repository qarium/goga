# tests/usages/test_clean.py — contract and logic tests for clean_usages_dir

import inspect
from pathlib import Path

import pytest
from goga.usages.sync.clean import clean_usages_dir

# --- Contract tests ---


class TestCleanUsagesDirContract:
    def test_importable_from_goga_usages_clean(self):
        """clean_usages_dir is importable from goga.usages.sync.clean."""
        assert callable(clean_usages_dir)

    def test_signature(self):
        """Signature is clean_usages_dir(usages_root: Path) -> int."""
        sig = inspect.signature(clean_usages_dir)

        params = list(sig.parameters)
        assert params == ["usages_root"]

        assert sig.parameters["usages_root"].annotation is Path
        assert sig.return_annotation is int


# --- Logic tests ---


class TestCleanUsagesDirLogic:
    def test_clean_usages_dir_preserves_cooks_and_files(self, tmp_path):
        """Subdirectories except cooks are removed; root files (md and other) and cooks are kept."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()

        # preserved: cooks dir + two root files (one .md, one not)
        (usages_root / "cooks" / "keep.md").mkdir(parents=True)
        (usages_root / "root.md").write_text("root")
        (usages_root / "notes.txt").write_text("notes")

        # removed: two non-cooks subdirectories
        (usages_root / "libs" / "click").mkdir(parents=True)
        (usages_root / "libs" / "click" / "a.md").write_text("a")
        (usages_root / "stale").mkdir()
        (usages_root / "stale" / "x.md").write_text("x")

        removed = clean_usages_dir(usages_root)

        assert removed == 2

        # cooks preserved verbatim
        assert (usages_root / "cooks" / "keep.md").exists()

        # both root files preserved regardless of extension
        assert (usages_root / "root.md").exists()
        assert (usages_root / "notes.txt").exists()

        # subdirectories removed
        assert not (usages_root / "libs").exists()
        assert not (usages_root / "stale").exists()

    def test_clean_usages_dir_missing_root_creates_and_returns_zero(self, tmp_path):
        """A missing usages_root is created (empty) and reports zero removals."""
        usages_root = tmp_path / "absent"

        assert not usages_root.exists()

        result = clean_usages_dir(usages_root)

        assert result == 0
        assert usages_root.exists()
        assert list(usages_root.iterdir()) == []

    def test_clean_usages_dir_idempotent(self, tmp_path):
        """A second call on an already-cleaned root removes nothing."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        (usages_root / "libs").mkdir()

        first = clean_usages_dir(usages_root)
        second = clean_usages_dir(usages_root)

        assert first == 1
        assert second == 0


# --- Edge cases ---


@pytest.mark.parametrize("filename", ["readme.md", "config.yml", "data.json"])
def test_clean_usages_dir_preserves_root_files_of_any_extension(tmp_path, filename):
    """Every file directly in usages_root is preserved, regardless of extension."""
    usages_root = tmp_path / "usages"
    usages_root.mkdir()
    (usages_root / filename).write_text("keep")

    removed = clean_usages_dir(usages_root)

    assert removed == 0
    assert (usages_root / filename).exists()

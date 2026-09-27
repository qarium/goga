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
        """Signature is clean_usages_dir(usages_root: Path, group=None, dep=None) -> int."""
        sig = inspect.signature(clean_usages_dir)

        params = list(sig.parameters)
        assert params == ["usages_root", "group", "dep"]

        assert sig.parameters["usages_root"].annotation is Path
        assert sig.parameters["group"].default is None
        assert sig.parameters["dep"].default is None
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


# --- Filtered clean tests ---


def _seed_tree(usages_root: Path) -> None:
    """Seed two groups, each with two deps, plus cooks and a root file."""
    (usages_root / "libs" / "click" / "a.md").mkdir(parents=True)
    (usages_root / "libs" / "structlog" / "b.md").mkdir(parents=True)
    (usages_root / "apps" / "common" / "c.md").mkdir(parents=True)
    (usages_root / "apps" / "web" / "d.md").mkdir(parents=True)
    (usages_root / "cooks" / "keep.md").mkdir(parents=True)
    (usages_root / "root.md").write_text("root")


class TestCleanUsagesDirFiltered:
    def test_group_filter_removes_only_that_group(self, tmp_path):
        """`group` removes the whole group subtree; other groups and cooks stay."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        _seed_tree(usages_root)

        removed = clean_usages_dir(usages_root, group="apps")

        assert removed == 1
        assert not (usages_root / "apps").exists()
        assert (usages_root / "libs" / "click" / "a.md").exists()
        assert (usages_root / "libs" / "structlog" / "b.md").exists()
        assert (usages_root / "cooks" / "keep.md").exists()
        assert (usages_root / "root.md").exists()

    def test_group_and_dep_filters_remove_exact_target(self, tmp_path):
        """`group` + `dep` remove exactly `<group>/<dep>`; the dep sibling stays."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        _seed_tree(usages_root)

        removed = clean_usages_dir(usages_root, group="libs", dep="click")

        assert removed == 1
        assert not (usages_root / "libs" / "click").exists()
        assert (usages_root / "libs" / "structlog" / "b.md").exists()
        assert (usages_root / "apps" / "common" / "c.md").exists()
        assert (usages_root / "cooks" / "keep.md").exists()

    def test_dep_filter_removes_dep_under_every_group(self, tmp_path):
        """`dep` without `group` removes `<g>/<dep>` for every group on disk."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        (usages_root / "libs" / "click" / "a.md").mkdir(parents=True)
        (usages_root / "apps" / "click" / "b.md").mkdir(parents=True)
        (usages_root / "apps" / "web" / "c.md").mkdir(parents=True)
        (usages_root / "cooks" / "keep.md").mkdir(parents=True)

        removed = clean_usages_dir(usages_root, dep="click")

        assert removed == 2
        assert not (usages_root / "libs" / "click").exists()
        assert not (usages_root / "apps" / "click").exists()
        assert (usages_root / "apps" / "web" / "c.md").exists()
        assert (usages_root / "libs").exists()
        assert (usages_root / "cooks" / "keep.md").exists()

    def test_dep_filter_never_descends_into_cooks(self, tmp_path):
        """A dep named like a cooks subdir never removes anything under cooks."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        (usages_root / "libs" / "click" / "a.md").mkdir(parents=True)
        (usages_root / "cooks" / "click" / "keep.md").mkdir(parents=True)

        removed = clean_usages_dir(usages_root, dep="click")

        assert removed == 1
        assert not (usages_root / "libs" / "click").exists()
        assert (usages_root / "cooks" / "click" / "keep.md").exists()

    def test_group_filter_named_cooks_is_a_noop(self, tmp_path):
        """The cooks guard holds even when a filter names cooks explicitly."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        (usages_root / "cooks" / "keep.md").mkdir(parents=True)
        (usages_root / "libs" / "click").mkdir(parents=True)

        assert clean_usages_dir(usages_root, group="cooks") == 0
        assert clean_usages_dir(usages_root, group="cooks", dep="keep.md") == 0
        assert (usages_root / "cooks" / "keep.md").exists()
        assert (usages_root / "libs" / "click").exists()

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"group": "absent"}, id="absent-group"),
            pytest.param({"dep": "absent"}, id="absent-dep"),
            pytest.param({"group": "absent", "dep": "absent"}, id="absent-both"),
        ],
    )
    def test_filter_matching_nothing_is_a_noop(self, tmp_path, kwargs):
        """A filter matching no existing directory removes nothing, no error."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        _seed_tree(usages_root)

        removed = clean_usages_dir(usages_root, **kwargs)

        assert removed == 0
        assert (usages_root / "libs" / "click" / "a.md").exists()
        assert (usages_root / "apps" / "web" / "d.md").exists()

    def test_filter_naming_a_root_file_never_touches_it(self, tmp_path):
        """Removal targets directories only — a root file with the filter name stays."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        (usages_root / "libs.md").write_text("a root file, not a group")
        (usages_root / "libs" / "click").mkdir(parents=True)

        assert clean_usages_dir(usages_root, group="libs.md") == 0
        assert (usages_root / "libs.md").read_text() == "a root file, not a group"
        assert (usages_root / "libs" / "click").exists()

    def test_filtered_clean_idempotent(self, tmp_path):
        """A second filtered call on the already-removed target removes nothing."""
        usages_root = tmp_path / "usages"
        usages_root.mkdir()
        (usages_root / "libs" / "click").mkdir(parents=True)

        first = clean_usages_dir(usages_root, group="libs", dep="click")
        second = clean_usages_dir(usages_root, group="libs", dep="click")

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

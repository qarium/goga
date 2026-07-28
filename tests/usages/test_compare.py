# tests/usages/test_compare.py — contract and logic tests for compare.py primitives

import hashlib
import importlib
import inspect
import itertools
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from goga.config import DepConfig
from goga.usages.status import DepStatus, EntryChange, EntryKind, EntryStatus, UsageState
from goga.usages.status.compare import _aggregate_dir, _diff_entries, compute_dep_status, hash_tree

# Resolve the inner ``compare.py`` submodule via importlib so ``mock.patch.object``
# patches the lookup site ``compute_dep_status`` uses for ``clone_repository`` /
# ``deploy_usages`` (the names imported into compare.py's own namespace).
_compare_mod = importlib.import_module("goga.usages.status.compare")

# --- contract tests: hash_tree ---


class TestHashTree:
    def test_hash_tree_importable(self):
        """hash_tree is importable from goga.usages.status.compare."""
        from goga.usages.status import compare as compare_mod

        assert hasattr(compare_mod, "hash_tree")
        assert compare_mod.hash_tree is hash_tree

    def test_hash_tree_signature(self):
        """hash_tree signature is (root: Path) -> dict[str, str]."""
        sig = inspect.signature(hash_tree)
        assert list(sig.parameters) == ["root"]
        assert sig.parameters["root"].annotation == Path
        assert sig.return_annotation == dict[str, str]

    # --- logic tests: regular files and empty trees ---

    def test_hash_tree_regular_file(self, tmp_path):
        """A regular file is keyed by its relative posix path and hashed by content."""
        (tmp_path / "a.txt").write_text("hello")
        hashes = hash_tree(tmp_path)
        assert hashes == {"a.txt": hashlib.sha256(b"hello").hexdigest()}

    def test_hash_tree_nested_regular_file_key_is_posix(self, tmp_path):
        """A nested file's key is its slash-joined relative posix path."""
        nested = tmp_path / "docs" / "sub"
        nested.mkdir(parents=True)
        (nested / "c.md").write_text("z")
        hashes = hash_tree(tmp_path)
        assert hashes == {"docs/sub/c.md": hashlib.sha256(b"z").hexdigest()}

    def test_hash_tree_empty_directory(self):
        """An empty directory yields an empty hash map."""
        assert hash_tree(Path("/nonexistent-status-probe")) == {}

    def test_hash_tree_is_deterministic_across_identical_trees(self, tmp_path):
        """Two structurally-identical trees produce identical maps regardless of names."""
        one = tmp_path / "one"
        two = tmp_path / "two"
        for root in (one, two):
            (root / "docs").mkdir(parents=True)
            (root / "docs" / "a.md").write_text("aa")
            (root / "b.md").write_text("bb")
        assert hash_tree(one) == hash_tree(two)

    # --- logic tests: symlinks ---

    def test_hash_tree_symlink_to_file_hashed_by_readlink_target(self, tmp_path):
        """A symlink is hashed by its readlink target string, not by the target's content."""
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "link.txt").symlink_to("a.txt")
        hashes = hash_tree(tmp_path)
        assert hashes["link.txt"] == hashlib.sha256(b"a.txt").hexdigest()
        # it is NOT the hash of the linked file's content
        assert hashes["link.txt"] != hashlib.sha256(b"hello").hexdigest()

    def test_hash_tree_dangling_symlink_hashes_like_live_with_same_target(self, tmp_path):
        """A dangling symlink and a live symlink with the same target string hash identically."""
        live_dir = tmp_path / "live"
        dead_dir = tmp_path / "dead"
        live_dir.mkdir()
        dead_dir.mkdir()
        (live_dir / "a.txt").write_text("hello")
        (live_dir / "link.txt").symlink_to("a.txt")  # live: target exists
        (dead_dir / "link.txt").symlink_to("a.txt")  # dangling: target absent
        live_hashes = hash_tree(live_dir)
        dead_hashes = hash_tree(dead_dir)
        assert live_hashes["link.txt"] == dead_hashes["link.txt"]
        assert live_hashes["link.txt"] == hashlib.sha256(b"a.txt").hexdigest()

    def test_hash_tree_symlink_to_dir_hashed_by_readlink_without_descending(self, tmp_path):
        """A symlink to a directory is hashed by readlink and is not descended into."""
        (tmp_path / "realdir").mkdir()
        (tmp_path / "realdir" / "x.md").write_text("z")
        (tmp_path / "linkdir").symlink_to("realdir")
        hashes = hash_tree(tmp_path)
        assert hashes["linkdir"] == hashlib.sha256(b"realdir").hexdigest()
        # the linked directory's contents must NOT be aggregated
        assert "linkdir/x.md" not in hashes


# --- logic tests: _aggregate_dir ---


class TestAggregateDir:
    def test_aggregate_all_unchanged(self):
        """Every member unchanged -> unchanged."""
        assert _aggregate_dir([EntryChange.unchanged, EntryChange.unchanged]) is EntryChange.unchanged

    def test_aggregate_all_added(self):
        """Every member added -> added (remote-only directory)."""
        assert _aggregate_dir([EntryChange.added, EntryChange.added]) is EntryChange.added

    def test_aggregate_all_removed(self):
        """Every member removed -> removed (local-only directory)."""
        assert _aggregate_dir([EntryChange.removed]) is EntryChange.removed

    def test_aggregate_mixed_is_modified(self):
        """Any mix of verdicts -> modified."""
        assert _aggregate_dir([EntryChange.unchanged, EntryChange.added]) is EntryChange.modified
        assert _aggregate_dir([EntryChange.added, EntryChange.removed]) is EntryChange.modified
        assert _aggregate_dir([EntryChange.modified, EntryChange.unchanged]) is EntryChange.modified

    @pytest.mark.parametrize(
        "order",
        list(itertools.permutations([EntryChange.added, EntryChange.removed, EntryChange.unchanged])),
    )
    def test_aggregate_is_order_independent(self, order):
        """Only the set of verdicts matters, not their order."""
        assert _aggregate_dir(list(order)) is EntryChange.modified


# --- logic tests: _diff_entries ---


class TestDiffEntries:
    def test_diff_all_matching_files_are_unchanged(self):
        """Files present in both with equal hashes are unchanged; root files add no dir entry."""
        expected = {"a.md": "h1", "b.md": "h2"}
        local = {"a.md": "h1", "b.md": "h2"}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="a.md", kind=EntryKind.file, change=EntryChange.unchanged),
            EntryStatus(path="b.md", kind=EntryKind.file, change=EntryChange.unchanged),
        ]

    def test_diff_differing_file_is_modified(self):
        """A file present in both with differing hashes is modified."""
        expected = {"a.md": "h1"}
        local = {"a.md": "hX"}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="a.md", kind=EntryKind.file, change=EntryChange.modified),
        ]

    def test_diff_expected_only_file_is_added(self):
        """A file present in expected but absent locally is added (the bug root cause)."""
        expected = {"a.md": "h1"}
        local: dict[str, str] = {}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="a.md", kind=EntryKind.file, change=EntryChange.added),
        ]

    def test_diff_local_only_file_is_removed(self):
        """A file present locally but absent from expected is removed."""
        expected: dict[str, str] = {}
        local = {"a.md": "h1"}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="a.md", kind=EntryKind.file, change=EntryChange.removed),
        ]

    def test_diff_remote_only_folder_is_added_not_out_of_date(self):
        """A folder present only in expected rolls up to added, not modified/out_of_date."""
        expected = {"new/x.md": "h1"}
        local: dict[str, str] = {}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="new", kind=EntryKind.dir, change=EntryChange.added),
            EntryStatus(path="new/x.md", kind=EntryKind.file, change=EntryChange.added),
        ]

    def test_diff_local_only_folder_is_removed(self):
        """A folder present only in local rolls up to removed."""
        expected: dict[str, str] = {}
        local = {"gone/y.md": "h1"}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="gone", kind=EntryKind.dir, change=EntryChange.removed),
            EntryStatus(path="gone/y.md", kind=EntryKind.file, change=EntryChange.removed),
        ]

    def test_diff_mixed_folder_is_modified(self):
        """A folder with a mix of verdicts rolls up to modified."""
        # docs/a.md unchanged, docs/b.md differs -> docs is modified.
        expected = {"docs/a.md": "h1", "docs/b.md": "h2"}
        local = {"docs/a.md": "h1", "docs/b.md": "hX"}
        result = _diff_entries(expected, local)
        by_path = {e.path: e for e in result}
        assert by_path["docs"].kind is EntryKind.dir
        assert by_path["docs"].change is EntryChange.modified
        assert by_path["docs/a.md"].change is EntryChange.unchanged
        assert by_path["docs/b.md"].change is EntryChange.modified

    def test_diff_all_matching_nested_folder_is_unchanged(self):
        """A nested folder whose every file matches rolls up to unchanged."""
        expected = {"docs/d.md": "h2"}
        local = {"docs/d.md": "h2"}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="docs", kind=EntryKind.dir, change=EntryChange.unchanged),
            EntryStatus(path="docs/d.md", kind=EntryKind.file, change=EntryChange.unchanged),
        ]

    def test_diff_multiple_folders_independent(self):
        """Sibling folders are aggregated independently and sorted by path."""
        expected = {"a.md": "h1", "docs/d.md": "h2"}
        local = {"a.md": "hX", "docs/d.md": "h2"}
        assert _diff_entries(expected, local) == [
            EntryStatus(path="a.md", kind=EntryKind.file, change=EntryChange.modified),
            EntryStatus(path="docs", kind=EntryKind.dir, change=EntryChange.unchanged),
            EntryStatus(path="docs/d.md", kind=EntryKind.file, change=EntryChange.unchanged),
        ]

    def test_diff_returns_list_of_entry_status(self):
        """The result is a list of EntryStatus with valid kinds and changes."""
        result = _diff_entries({"a.md": "h"}, {"a.md": "h"})
        assert isinstance(result, list)
        assert all(isinstance(e, EntryStatus) for e in result)
        assert all(e.kind in (EntryKind.file, EntryKind.dir) for e in result)
        assert all(e.change in tuple(EntryChange) for e in result)

    def test_diff_is_sorted_by_path(self):
        """Entries are sorted by path (files and dirs interleaved)."""
        result = _diff_entries({"z.md": "h", "a/b.md": "h"}, {"z.md": "h", "a/b.md": "h"})
        assert [e.path for e in result] == ["a", "a/b.md", "z.md"]

    def test_diff_role_swap_mirrors_added_and_removed(self):
        """Swapping expected/local mirrors the diff: ``added`` <-> ``removed`` while
        ``modified``/``unchanged`` stay. The set-based classification is otherwise
        deterministic in the input dict ordering (the final sort is by path)."""
        expected = {"a.md": "h1", "b.md": "h2", "docs/c.md": "h3"}
        local = {"a.md": "h1", "b.md": "hX", "gone/y.md": "h9"}
        forward = {e.path: e.change for e in _diff_entries(expected, local)}
        mirror = {e.path: e.change for e in _diff_entries(local, expected)}
        # unchanged and modified are role-symmetric
        assert forward["a.md"] is mirror["a.md"] is EntryChange.unchanged
        assert forward["b.md"] is mirror["b.md"] is EntryChange.modified
        # added <-> removed (expected-only docs/c.md; local-only gone/)
        assert forward["docs/c.md"] is EntryChange.added
        assert mirror["docs/c.md"] is EntryChange.removed
        assert forward["docs"] is EntryChange.added
        assert mirror["docs"] is EntryChange.removed
        assert forward["gone/y.md"] is EntryChange.removed
        assert mirror["gone/y.md"] is EntryChange.added
        assert forward["gone"] is EntryChange.removed
        assert mirror["gone"] is EntryChange.added


# --- helpers for compute_dep_status logic tests ---


def _make_fake_clone(root: Path, files: dict[str, str]) -> Path:
    """Build a throwaway fake clone under ``root`` with the given repo-relative files.

    Mirrors the ``make_repo`` fixture but is a self-contained throwaway (it is the
    path ``compute_dep_status`` will ``rmtree`` as ``temp#1``).
    """
    root.mkdir(parents=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


def _make_target(parent: Path, files: dict[str, str]) -> Path:
    """Build the on-disk synced target tree under ``parent/target``."""
    target = parent / "target"
    target.mkdir(parents=True)
    for rel, content in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return target


# --- contract tests: compute_dep_status ---


class TestComputeDepStatus:
    def test_compute_dep_status_importable(self):
        """compute_dep_status is importable from goga.usages.status.compare."""
        from goga.usages.status import compare as compare_mod

        assert hasattr(compare_mod, "compute_dep_status")
        assert compare_mod.compute_dep_status is compute_dep_status

    def test_compute_dep_status_signature(self):
        """Signature is (group: str, dep: str, depcfg: DepConfig, target: Path) -> DepStatus."""
        sig = inspect.signature(compute_dep_status)
        params = list(sig.parameters)
        assert params == ["group", "dep", "depcfg", "target"]
        assert sig.parameters["group"].annotation is str
        assert sig.parameters["dep"].annotation is str
        assert sig.parameters["depcfg"].annotation is DepConfig
        assert sig.parameters["target"].annotation is Path
        assert sig.return_annotation is DepStatus


# --- logic tests: compute_dep_status ---


class TestComputeDepStatusLogic:
    def test_compute_dep_status_up_to_date(self, tmp_path):
        """Identical rebuilt-expected and local trees → state is up_to_date."""
        fake_repo = _make_fake_clone(tmp_path / "clone", {".usages/click.md": "C1"})
        target = _make_target(tmp_path, {"click.md": "C1"})
        depcfg = DepConfig(git="https://x/click.git", ref="main")
        with mock.patch.object(_compare_mod, "clone_repository", return_value=fake_repo):
            result = compute_dep_status("libs", "click", depcfg, target)
        assert result.state is UsageState.up_to_date
        assert result.group == "libs"
        assert result.dep == "click"
        assert result.entries == [EntryStatus(path="click.md", kind=EntryKind.file, change=EntryChange.unchanged)]

    def test_compute_dep_status_out_of_date(self, tmp_path):
        """Differing local tree → state is out_of_date; entries mark the differing file modified."""
        fake_repo = _make_fake_clone(tmp_path / "clone", {".usages/click.md": "REMOTE"})
        target = _make_target(tmp_path, {"click.md": "LOCAL"})
        depcfg = DepConfig(git="https://x/click.git")
        with mock.patch.object(_compare_mod, "clone_repository", return_value=fake_repo):
            result = compute_dep_status("libs", "click", depcfg, target)
        assert result.state is UsageState.out_of_date
        assert result.entries == [EntryStatus(path="click.md", kind=EntryKind.file, change=EntryChange.modified)]

    def test_compute_dep_status_cleans_both_temp_dirs(self, tmp_path, monkeypatch):
        """Both temp#1 (clone) and temp#2 (expected) are cleaned on success AND on deploy failure."""
        # Spy on tempfile.mkdtemp to capture temp#2's path (the only mkdtemp call in
        # the compare path — clone_repository is mocked, deploy_usages uses mkdir).
        created_expected: list[Path] = []
        real_mkdtemp = tempfile.mkdtemp

        def spy_mkdtemp(*args, **kwargs):
            created = Path(real_mkdtemp(*args, **kwargs))
            created_expected.append(created)
            return created

        monkeypatch.setattr(tempfile, "mkdtemp", spy_mkdtemp)
        depcfg = DepConfig(git="https://x/click.git")
        target = _make_target(tmp_path, {"click.md": "C1"})

        # --- success path: clone + deploy succeed → both temps cleaned ---
        ok_repo = _make_fake_clone(tmp_path / "ok", {".usages/click.md": "C1"})
        with mock.patch.object(_compare_mod, "clone_repository", return_value=ok_repo):
            result = compute_dep_status("libs", "click", depcfg, target)
        assert result.state is UsageState.up_to_date
        assert len(created_expected) == 1  # temp#2 was created...
        assert not ok_repo.exists()  # temp#1 cleaned
        assert not created_expected[0].exists()  # ...temp#2 cleaned

        # --- deploy-failure path: deploy_usages raises → both temps STILL cleaned ---
        created_expected.clear()
        fail_repo = _make_fake_clone(tmp_path / "fail", {".usages/click.md": "C1"})
        with (
            mock.patch.object(_compare_mod, "clone_repository", return_value=fail_repo),
            mock.patch.object(_compare_mod, "deploy_usages", side_effect=OSError("boom")),
            pytest.raises(OSError, match="boom"),
        ):
            compute_dep_status("libs", "click", depcfg, target)
        assert len(created_expected) == 1  # temp#2 was created before deploy raised...
        assert not fail_repo.exists()  # temp#1 cleaned
        assert not created_expected[0].exists()  # ...temp#2 cleaned

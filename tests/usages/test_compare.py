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
from goga.usages.status import DepStatus, FolderStatus, UsageState
from goga.usages.status.compare import _rollup_folders, compute_dep_status, hash_tree

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


# --- logic tests: _rollup_folders ---


class TestRollupFolders:
    def test_rollup_all_matching_root_folder_is_up_to_date(self):
        """A root-level folder where every file matches is up_to_date."""
        expected = {"a.md": "h1", "b.md": "h2"}
        local = {"a.md": "h1", "b.md": "h2"}
        assert _rollup_folders(expected, local) == [
            FolderStatus(path="", state=UsageState.up_to_date),
        ]

    def test_rollup_differing_file_marks_root_folder_out_of_date(self):
        """A differing file marks its folder out_of_date."""
        expected = {"a.md": "h1", "b.md": "h2"}
        local = {"a.md": "h1", "b.md": "hX"}
        assert _rollup_folders(expected, local) == [
            FolderStatus(path="", state=UsageState.out_of_date),
        ]

    def test_rollup_mixed_files_in_one_folder_is_sticky_out_of_date(self):
        """A matching file does not roll a differing folder back to up_to_date (sticky)."""
        # a.md matches; b.md differs — the folder is still out_of_date.
        expected = {"a.md": "h1", "b.md": "h2"}
        local = {"a.md": "h1", "b.md": "hX"}
        result = _rollup_folders(expected, local)
        assert result == [FolderStatus(path="", state=UsageState.out_of_date)]

    def test_rollup_missing_file_marks_folder_out_of_date(self):
        """A file present in expected but absent locally marks its folder out_of_date."""
        expected = {"a.md": "h1"}
        local: dict[str, str] = {}
        assert _rollup_folders(expected, local) == [
            FolderStatus(path="", state=UsageState.out_of_date),
        ]

    def test_rollup_extra_file_marks_folder_out_of_date(self):
        """A file present locally but absent from expected marks its folder out_of_date."""
        expected: dict[str, str] = {}
        local = {"a.md": "h1"}
        assert _rollup_folders(expected, local) == [
            FolderStatus(path="", state=UsageState.out_of_date),
        ]

    def test_rollup_multiple_folders_sorted_and_independent(self):
        """Folders are sorted by path and assessed independently."""
        expected = {"a.md": "h1", "docs/d.md": "h2"}
        local = {"a.md": "hX", "docs/d.md": "h2"}
        assert _rollup_folders(expected, local) == [
            FolderStatus(path="", state=UsageState.out_of_date),
            FolderStatus(path="docs", state=UsageState.up_to_date),
        ]

    def test_rollup_returns_list_of_folder_status(self):
        """The result is a list of FolderStatus with the restricted folder states."""
        result = _rollup_folders({"a.md": "h"}, {"a.md": "h"})
        assert isinstance(result, list)
        assert all(isinstance(fs, FolderStatus) for fs in result)
        assert all(
            fs.state in (UsageState.up_to_date, UsageState.out_of_date)
            for fs in result
        )

    @pytest.mark.parametrize("swap", [False, True])
    def test_rollup_is_order_independent(self, swap):
        """The sticky fold is commutative: any key iteration order yields the same result."""
        expected = {"a.md": "h1", "b.md": "h2", "docs/c.md": "h3", "docs/d.md": "h4"}
        local = {"a.md": "h1", "b.md": "hX", "docs/c.md": "h3"}
        # local-first vs expected-first changes the set union's operand order; the
        # sticky out_of_date assignment makes the fold order-independent regardless.
        (left, right) = (local, expected) if swap else (expected, local)
        keys = list(left.keys() | right.keys())

        def fold(order):
            folders: dict[str, UsageState] = {}
            for key in order:
                parent = Path(key).parent
                folder = "" if str(parent) == "." else str(parent)
                ok = (
                    key in expected
                    and key in local
                    and expected[key] == local[key]
                )
                if not ok:
                    folders[folder] = UsageState.out_of_date
                else:
                    folders.setdefault(folder, UsageState.up_to_date)
            return tuple(sorted(folders.items()))

        outcomes = {fold(list(p)) for p in itertools.permutations(keys)}
        assert len(outcomes) == 1  # every permutation agrees
        actual = [(fs.path, fs.state) for fs in _rollup_folders(expected, local)]
        assert actual == list(fold(keys))


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
        assert result.folders == [FolderStatus(path="", state=UsageState.up_to_date)]

    def test_compute_dep_status_out_of_date(self, tmp_path):
        """Differing local tree → state is out_of_date; folders reflect the differing file."""
        fake_repo = _make_fake_clone(tmp_path / "clone", {".usages/click.md": "REMOTE"})
        target = _make_target(tmp_path, {"click.md": "LOCAL"})
        depcfg = DepConfig(git="https://x/click.git")
        with mock.patch.object(_compare_mod, "clone_repository", return_value=fake_repo):
            result = compute_dep_status("libs", "click", depcfg, target)
        assert result.state is UsageState.out_of_date
        assert result.folders == [FolderStatus(path="", state=UsageState.out_of_date)]

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

# tests/usages/test_deploy.py — contract and logic tests for deploy_usages

import inspect
from pathlib import Path

import pytest
from goga.usages.deploy import deploy_usages

# --- Contract tests ---


class TestDeployUsagesContract:
    def test_importable_from_goga_usages_deploy(self):
        """deploy_usages is importable from goga.usages.deploy."""
        assert callable(deploy_usages)

    def test_deploy_signature_has_root_param(self):
        """Signature is deploy_usages(source_repo: Path, target_dir: Path, root: str | None = None) -> int."""
        sig = inspect.signature(deploy_usages)

        params = list(sig.parameters)
        assert params == ["source_repo", "target_dir", "root"]

        assert sig.parameters["source_repo"].annotation is Path
        assert sig.parameters["target_dir"].annotation is Path
        assert sig.parameters["root"].annotation == (str | None)
        assert sig.parameters["root"].default is None
        assert sig.return_annotation is int


# --- Logic tests ---


class TestDeployUsagesLogic:
    def test_deploy_root_walks_from_subpath(self, tmp_path):
        """root limits the walk to source_repo/root; .usages land at origin-relative paths.

        The three AC-mappings (verbatim from the contract):
        - folder/cell_1/cell_2/.usages                     -> cell_1/cell_2
        - folder/subfolder/cell_1/cell_2/.usages           -> subfolder/cell_1/cell_2
        - folder/subfolder/cell_1/another_folder/cell_2/.usages -> subfolder/cell_1/another_folder/cell_2
        and an out-of-root OTHER/.usages is never deployed.
        """
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / "folder" / "cell_1" / "cell_2" / ".usages" / "a.md").mkdir(parents=True)
        (clone / "folder" / "subfolder" / "cell_1" / "cell_2" / ".usages" / "b.md").mkdir(parents=True)
        (clone / "folder" / "subfolder" / "cell_1" / "another_folder" / "cell_2" / ".usages" / "c.md").mkdir(
            parents=True
        )
        # Out-of-root .usages — root="folder" excludes this sibling.
        (clone / "OTHER" / ".usages" / "ignore.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(clone, target, "folder")

        assert count == 3
        assert (target / "cell_1" / "cell_2" / "a.md").exists()
        assert (target / "subfolder" / "cell_1" / "cell_2" / "b.md").exists()
        assert (target / "subfolder" / "cell_1" / "another_folder" / "cell_2" / "c.md").exists()
        assert not (target / "ignore.md").exists()
        # .usages segment dropped from every destination path
        assert not (target / ".usages").exists()

    def test_deploy_root_none_walks_from_repo_root(self, tmp_path):
        """root=None (default) walks from the clone root (back-compat origin)."""
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".usages" / "r.md").mkdir(parents=True)
        (clone / "src" / "c" / ".usages" / "x.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(clone, target, None)

        assert count == 2
        assert (target / "r.md").exists()
        assert (target / "src" / "c" / "x.md").exists()

    def test_deploy_root_usages_at_origin_copies_to_target_root(self, tmp_path):
        """A .usages directly in the walk origin copies into the target root (empty <rel>)."""
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / "folder" / ".usages" / "r.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(clone, target, "folder")

        assert count == 1
        assert (target / "r.md").exists()
        # .usages is dropped and 'folder' is the origin, not a destination segment
        assert not (target / "folder").exists()

    def test_deploy_origin_without_usages_returns_zero_and_creates_empty_target(self, tmp_path):
        """An origin with no .usages anywhere -> count 0; empty target created."""
        clone = tmp_path / "clone"
        clone.mkdir()
        # non-usages content only, no .usages anywhere
        (clone / "src" / "main.py").mkdir(parents=True)

        target = tmp_path / "target"

        result = deploy_usages(clone, target, None)

        assert result == 0
        assert target.exists()
        assert target.is_dir()
        assert list(target.iterdir()) == []

    def test_deploy_single_usages_not_at_origin_not_flattened(self, tmp_path):
        """A single .usages NOT at the origin is NOT flattened — breaking-change guard.

        Replaces the old smoothing behavior (a single .usages flattened into the
        target root). Now it lands at its origin-relative path.
        """
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / "src" / "c" / ".usages" / "x.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(clone, target, None)

        assert count == 1
        assert (target / "src" / "c" / "x.md").exists()
        # NOT flattened into the target root
        assert not (target / "x.md").exists()

    def test_deploy_usages_multiple_preserves_hierarchy(self, tmp_path):
        """Multiple .usages (root=None) preserve full hierarchy (incl. non-cell dirs); .usages dropped everywhere."""
        source_repo = tmp_path / "clone"
        source_repo.mkdir()
        # .usages at repo root
        (source_repo / ".usages" / "root.md").mkdir(parents=True)
        # .usages nested under non-cell intermediates src/a and src/b
        (source_repo / "src" / "a" / ".usages" / "a.md").mkdir(parents=True)
        (source_repo / "src" / "b" / ".usages" / "b.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(source_repo, target)

        assert count == 3
        # root .usages copies to target root
        assert (target / "root.md").exists()
        # nested .usages preserve src/a and src/b; .usages segment dropped
        assert (target / "src" / "a" / "a.md").exists()
        assert (target / "src" / "b" / "b.md").exists()
        # .usages never appears as a segment in destination
        assert not (target / ".usages").exists()
        assert not (target / "src" / "a" / ".usages").exists()

    def test_deploy_usages_skips_vcs_dirs(self, tmp_path):
        """VCS dirs (.git/.hg/.svn) are skipped during discovery and copying."""
        source_repo = tmp_path / "clone"
        source_repo.mkdir()
        (source_repo / ".usages" / "real.md").mkdir(parents=True)
        # .git with a fake .usages inside that must NOT be discovered or copied
        (source_repo / ".git" / ".usages" / "secret.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(source_repo, target)

        assert count == 1
        assert (target / "real.md").exists()
        # .git never copied into target
        assert not (target / ".git").exists()

    def test_deploy_usages_does_not_delete_target(self, tmp_path):
        """A pre-existing target is not deleted; existing files survive deploy."""
        source_repo = tmp_path / "clone"
        source_repo.mkdir()
        (source_repo / ".usages" / "new.md").mkdir(parents=True)

        target = tmp_path / "target"
        target.mkdir()
        (target / "preexisting.md").write_text("keep me")

        count = deploy_usages(source_repo, target)

        assert count == 1
        # both pre-existing and newly deployed files present
        assert (target / "preexisting.md").exists()
        assert (target / "new.md").exists()

    def test_deploy_usages_copies_symlinks_verbatim_not_dereferenced(self, tmp_path):
        """Symlinks inside .usages are copied as links, never dereferenced.

        The cloned repo is untrusted third-party content; dereferencing a
        symlink (e.g. one pointing at ``~/.ssh/id_rsa``) would copy the
        *contents* of the link target into the synced output (local-file
        disclosure). The link is preserved verbatim instead.
        """
        source_repo = tmp_path / "clone"
        source_repo.mkdir()
        (source_repo / ".usages").mkdir()
        # Sensitive file OUTSIDE the deployed .usages tree.
        secret = tmp_path / "secret.txt"
        secret.write_text("TOPSECRET")
        # Symlink inside .usages pointing at the out-of-tree file.
        (source_repo / ".usages" / "leak").symlink_to(secret)

        target = tmp_path / "target"

        count = deploy_usages(source_repo, target)

        assert count == 1
        leaked = target / "leak"
        # Copied verbatim as a symlink (not dereferenced into a regular file)...
        assert leaked.is_symlink()
        # ...still pointing at the original, out-of-tree target, whose contents
        # were therefore never duplicated into the sync output.
        assert leaked.readlink() == secret


# --- Negative tests (root resolves to a missing path or a file) ---


class TestDeployUsagesNegative:
    def test_deploy_root_missing_raises(self, tmp_path):
        """A root that does not exist under the clone raises BEFORE the target is created."""
        clone = tmp_path / "clone"
        clone.mkdir()
        # clone exists but clone/folder/ does not
        target = tmp_path / "target"

        with pytest.raises((FileNotFoundError, NotADirectoryError)):
            deploy_usages(clone, target, "folder")

        # origin verified BEFORE target.mkdir — target left untouched
        assert not target.exists()

    def test_deploy_root_is_file_raises(self, tmp_path):
        """A root that resolves to a regular file (not a directory) raises."""
        clone = tmp_path / "clone"
        clone.mkdir()
        # clone/folder is a regular file, not a directory
        (clone / "folder").write_text("not a dir")

        target = tmp_path / "target"

        with pytest.raises((FileNotFoundError, NotADirectoryError)):
            deploy_usages(clone, target, "folder")

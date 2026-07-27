# tests/usages/test_deploy.py — contract and logic tests for deploy_usages

import inspect
from pathlib import Path

from goga.usages.deploy import deploy_usages

# --- Contract tests ---


class TestDeployUsagesContract:
    def test_importable_from_goga_usages_deploy(self):
        """deploy_usages is importable from goga.usages.deploy."""
        assert callable(deploy_usages)

    def test_signature(self):
        """Signature is deploy_usages(source_repo: Path, target_dir: Path) -> int."""
        sig = inspect.signature(deploy_usages)

        params = list(sig.parameters)
        assert params == ["source_repo", "target_dir"]

        assert sig.parameters["source_repo"].annotation is Path
        assert sig.parameters["target_dir"].annotation is Path
        assert sig.return_annotation is int


# --- Logic tests ---


class TestDeployUsagesLogic:
    def test_deploy_usages_single_flattens(self, tmp_path):
        """Exactly one .usages → its contents (files + subdirs) flatten into target."""
        source_repo = tmp_path / "clone"
        source_repo.mkdir()
        (source_repo / ".usages" / "click.md").mkdir(parents=True)
        (source_repo / ".usages" / "sub" / "x.md").mkdir(parents=True)

        target = tmp_path / "target"

        count = deploy_usages(source_repo, target)

        assert count == 1
        assert (target / "click.md").exists()
        assert (target / "sub" / "x.md").exists()
        # .usages segment dropped from destination
        assert not (target / ".usages").exists()

    def test_deploy_usages_multiple_preserves_hierarchy(self, tmp_path):
        """Multiple .usages → preserve full hierarchy (incl. non-cell dirs); drop .usages everywhere."""
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
        # root .usages flattened to target root
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

    def test_deploy_usages_zero_usages_returns_zero_and_creates_empty_target(self, tmp_path):
        """A clone without any .usages → count 0; empty target created."""
        source_repo = tmp_path / "clone"
        source_repo.mkdir()
        # some non-usages content, no .usages anywhere
        (source_repo / "src" / "main.py").mkdir(parents=True)

        target = tmp_path / "target"

        result = deploy_usages(source_repo, target)

        assert result == 0
        assert target.exists()
        assert list(target.iterdir()) == []

# tests/usages/test_integration.py — cross-entity integration tests for sync orchestration

from pathlib import Path
from unittest import mock

import pytest
from goga.usages.sync import sync

_GOOD_AND_BAD_DEPS = (
    "usages:\n  libs:\n    good:\n      git: https://x/good.git\n    bad:\n      git: https://x/bad.git\n"
)


class TestSyncIntegration:
    def test_flow_b_force_cleans_stale_and_deploys_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """Flow B: force clears stale subdirs (keeps cooks + root files), clone+deploy run."""
        repo = make_repo(
            "click",
            {".usages/click.md": "click", ".usages/sub/x.md": "x"},
        )
        write_config(
            "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n",
        )

        usages_root = tmp_path / ".goga" / "usages"
        (usages_root / "libs" / "click").mkdir(parents=True)  # existing target
        (usages_root / "cooks").mkdir(parents=True)  # preserved verbatim
        (usages_root / "cooks" / "k.md").write_text("cook")
        (usages_root / "root.md").write_text("root")  # root file preserved
        (usages_root / "stale").mkdir()  # stale subdir → removed
        (usages_root / "stale" / "x.md").write_text("stale")

        monkeypatch.chdir(tmp_path)

        with patch_clone({"https://x/click.git": repo}):
            result = sync(force=True)

        assert result == 0
        # real deploy_usages flattened the single .usages into the target
        assert (usages_root / "libs" / "click" / "click.md").read_text() == "click"
        assert (usages_root / "libs" / "click" / "sub" / "x.md").read_text() == "x"
        assert not (usages_root / "libs" / "click" / ".usages").exists()
        # real clean_usages_dir kept cooks + root file, removed stale
        assert (usages_root / "cooks" / "k.md").read_text() == "cook"
        assert (usages_root / "root.md").read_text() == "root"
        assert not (usages_root / "stale").exists()

    def test_flow_a_incremental_first_deploys_second_is_noop(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """Flow A: first sync deploys the dep; second sync is a no-op (target exists)."""
        repo = make_repo("another", {".usages/a.md": "a"})
        write_config(
            "usages:\n  libs:\n    another:\n      git: https://x/another.git\n",
        )
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"

        # first incremental sync deploys the dep for real
        with patch_clone({"https://x/another.git": repo}):
            result1 = sync()

        assert result1 == 0
        assert (usages_root / "libs" / "another" / "a.md").read_text() == "a"

        # second incremental sync: target now exists → clone/deploy not invoked
        with (
            mock.patch("goga.usages.sync.clone_repository") as clone_mock,
            mock.patch("goga.usages.sync.deploy_usages") as deploy_mock,
        ):
            result2 = sync()

        assert result2 == 0
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_flow_c_no_usages_reads_only_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ):
        """Flow C: config without usages → only reads config; no git/FS side effects."""
        write_config(None)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch("goga.usages.sync.clone_repository") as clone_mock,
            mock.patch("goga.usages.sync.deploy_usages") as deploy_mock,
            mock.patch("goga.usages.sync.clean_usages_dir") as clean_mock,
        ):
            result = sync()

        assert result == 0
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()
        clean_mock.assert_not_called()
        assert not (tmp_path / ".goga" / "usages").exists()

    def test_best_effort_good_dep_synced_when_bad_dep_clone_fails(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """Best-effort: bad dep's clone CalledProcessError → good synced, exit 1."""
        good_repo = make_repo("good", {".usages/g.md": "good"})
        write_config(_GOOD_AND_BAD_DEPS)
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"

        with patch_clone(
            {"https://x/good.git": good_repo},
            failing={"https://x/bad.git"},
        ):
            result = sync()

        assert result == 1
        # good dep synced on disk despite bad dep's clone failure
        assert (usages_root / "libs" / "good" / "g.md").read_text() == "good"
        assert not (usages_root / "libs" / "bad").exists()
        # no clone temp dirs leak: the failed clone is self-cleaned and the
        # successful clone is cleaned by sync's finally block
        assert list((tmp_path / "clones").iterdir()) == []

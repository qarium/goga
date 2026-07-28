# tests/usages/test_integration.py — cross-entity integration tests for sync orchestration

import importlib
from pathlib import Path
from unittest import mock

import pytest
from goga.usages.sync import sync

# Resolve the inner ``sync.py`` submodule via importlib. The facade ``goga.usages``
# re-exports the ``sync`` function, which shadows the submodule attribute in the
# package ``__dict__``. On Python 3.10
# ``mock.patch("goga.usages.sync.clone_repository")`` resolves the dotted path
# through sequential ``getattr``, finds the function where it expects the
# submodule, and raises ``AttributeError``. Holding a direct reference to the
# module makes ``mock.patch.object`` work uniformly across Python versions.
_sync_mod = importlib.import_module("goga.usages.sync.sync")

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
        # the .usages sits at the repo-root walk origin, so it copies into the
        # target root (empty <rel>); no smoothing — nested .usages preserve hierarchy
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
            mock.patch.object(_sync_mod, "clone_repository") as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
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
            mock.patch.object(_sync_mod, "clone_repository") as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
            mock.patch.object(_sync_mod, "clean_usages_dir") as clean_mock,
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


class TestSyncIntegrationRootFlow:
    """End-to-end verification that a declared usages dep ``root`` flows from
    ``.goga/config.yml`` through ``load_project_config`` → ``DepConfig.root`` →
    ``sync`` → ``deploy_usages`` and lands at deterministic origin-relative paths.

    Git is mocked (``patch_clone``); ``clean_usages_dir`` and ``deploy_usages``
    run for real against the filesystem (shared ``make_repo``/``write_config``/
    ``patch_clone`` fixtures in ``conftest.py``).
    """

    def test_root_subpath_honored_end_to_end(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A dep declaring ``root: folder`` walks only from ``clone/folder`` and lands
        at the three AC-mappings' origin-relative paths (``.usages`` segment dropped);
        the out-of-root sibling is never deployed; ``sync`` returns ``0``.
        """
        repo = make_repo(
            "click",
            {
                "folder/cell_1/cell_2/.usages/a.md": "a",
                "folder/subfolder/cell_1/cell_2/.usages/b.md": "b",
                "folder/subfolder/cell_1/another_folder/cell_2/.usages/c.md": "c",
                # out-of-root: under OTHER/, not folder/ — excluded by root
                "OTHER/.usages/ignore.md": "ignore",
            },
        )
        write_config(
            "usages:\n  libs:\n    click:\n      git: https://x/c.git\n      root: folder\n",
        )

        usages_root = tmp_path / ".goga" / "usages"
        click = usages_root / "libs" / "click"

        monkeypatch.chdir(tmp_path)

        with patch_clone({"https://x/c.git": repo}):
            result = sync(force=True)

        assert result == 0
        # the three AC-mappings (origin = clone/folder, .usages segment dropped):
        assert (click / "cell_1" / "cell_2" / "a.md").read_text() == "a"
        assert (click / "subfolder" / "cell_1" / "cell_2" / "b.md").read_text() == "b"
        assert (click / "subfolder" / "cell_1" / "another_folder" / "cell_2" / "c.md").read_text() == "c"
        # out-of-root sibling never deployed; .usages segment never appears in dest
        assert not (click / "ignore.md").exists()
        assert not (click / ".usages").exists()

    def test_no_root_deploys_from_repo_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """Back-compat: a dep without ``root:`` walks from the clone root (mirrors
        ``test_deploy_root_none_walks_from_repo_root`` through the real ``sync``).
        """
        repo = make_repo(
            "another",
            {
                ".usages/r.md": "r",
                "src/c/.usages/x.md": "x",
            },
        )
        write_config(
            "usages:\n  libs:\n    another:\n      git: https://x/another.git\n",
        )

        usages_root = tmp_path / ".goga" / "usages"
        monkeypatch.chdir(tmp_path)

        with patch_clone({"https://x/another.git": repo}):
            result = sync(force=True)

        assert result == 0
        # repo-root .usages → target root; nested .usages preserves src/c
        assert (usages_root / "libs" / "another" / "r.md").read_text() == "r"
        assert (usages_root / "libs" / "another" / "src" / "c" / "x.md").read_text() == "x"

    def test_missing_root_is_best_effort_exit_one_other_deps_run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A dep whose ``root`` resolves to a missing path under the clone makes
        ``deploy_usages`` raise; best-effort ``sync`` logs the per-dep failure,
        sets ``exit_code=1``, and still syncs the other dep. No clone temp dirs leak.
        """
        good_repo = make_repo("good", {".usages/g.md": "good"})
        # repo exists but has no `nope/` subdir → deploy_usages(root="nope") raises
        bad_repo = make_repo("bad", {".usages/other.md": "other"})
        write_config(
            "usages:\n"
            "  libs:\n"
            "    good:\n"
            "      git: https://x/good.git\n"
            "    click:\n"
            "      git: https://x/c.git\n"
            "      root: nope\n",
        )

        usages_root = tmp_path / ".goga" / "usages"
        monkeypatch.chdir(tmp_path)

        with patch_clone({"https://x/good.git": good_repo, "https://x/c.git": bad_repo}):
            result = sync()

        assert result == 1
        # other dep still synced (best-effort continuation)
        assert (usages_root / "libs" / "good" / "g.md").read_text() == "good"
        # failed dep left no target behind (origin verified before target.mkdir)
        assert not (usages_root / "libs" / "click").exists()
        # both clone temp dirs cleaned (success via finally; failure via finally too)
        assert list((tmp_path / "clones").iterdir()) == []

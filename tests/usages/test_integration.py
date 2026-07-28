# tests/usages/test_integration.py — cross-entity integration tests for sync orchestration

import importlib
from pathlib import Path
from unittest import mock

import pytest
from goga.usages.status import EntryChange, UsageState, status
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


# A single declared dep (click) used by the up_to_date / out_of_date scenarios.
_CLICK_DEP_BLOCK = "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n"

_GOOD_AND_BAD_STATUS_DEPS = (
    "usages:\n"
    "  libs:\n"
    "    good:\n"
    "      git: https://x/good.git\n"
    "    bad:\n"
    "      git: https://x/bad.git\n"
)


class TestStatusIntegration:
    """End-to-end status checks: real clone (mocked git) -> real deploy -> real
    ``hash_tree`` -> compare, against an on-disk synced target.

    Git is mocked (``patch_clone``); ``deploy_usages`` and ``hash_tree`` run for
    real against the filesystem (shared ``make_repo``/``write_config``/
    ``patch_clone`` fixtures). The on-disk target mirrors what ``sync`` produces:
    ``deploy_usages`` drops the ``.usages`` segment, so a synced file sits at the
    target root (not under a ``.usages/`` subdir).
    """

    def test_status_dep_up_to_date(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A synced tree matching the remote -> ``up_to_date``, exit 0."""
        repo = make_repo("click", {".usages/click.md": "C1"})
        write_config(_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        target = tmp_path / ".goga" / "usages" / "libs" / "click"
        target.mkdir(parents=True)
        (target / "click.md").write_text("C1")  # matches the remote deployment

        with patch_clone({"https://x/click.git": repo}):
            report = status()

        assert len(report.deps) == 1
        assert report.deps[0].state is UsageState.up_to_date
        assert report.exit_code == 0

    def test_status_dep_out_of_date(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A synced tree differing from the remote -> ``out_of_date``, exit 1."""
        repo = make_repo("click", {".usages/click.md": "C2"})
        write_config(_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        target = tmp_path / ".goga" / "usages" / "libs" / "click"
        target.mkdir(parents=True)
        (target / "click.md").write_text("C1")  # local C1 vs remote C2

        with patch_clone({"https://x/click.git": repo}):
            report = status()

        assert report.deps[0].state is UsageState.out_of_date
        assert report.exit_code == 1
        # the differing root-level file is classified modified (not collapsed into
        # an out_of_date folder roll-up).
        entries = {entry.path: entry for entry in report.deps[0].entries}
        assert entries["click.md"].change is EntryChange.modified

    def test_status_dep_remote_only_folder_is_added(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A folder present on the remote but absent locally is ``added`` (not
        ``out_of_date``) — the regression this change fixes. The matching sibling
        file stays ``unchanged``; the dep itself is ``out_of_date`` because the
        trees differ.
        """
        repo = make_repo("click", {".usages/click.md": "C1", ".usages/new/x.md": "X1"})
        write_config(_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        target = tmp_path / ".goga" / "usages" / "libs" / "click"
        target.mkdir(parents=True)
        (target / "click.md").write_text("C1")  # matches; the `new/` folder is absent locally

        with patch_clone({"https://x/click.git": repo}):
            report = status()

        assert report.deps[0].state is UsageState.out_of_date
        assert report.exit_code == 1
        entries = {entry.path: entry for entry in report.deps[0].entries}
        # the remote-only folder rolls up to `added`, NOT out_of_date/modified
        assert entries["new"].kind.value == "dir"
        assert entries["new"].change is EntryChange.added
        assert entries["new/x.md"].change is EntryChange.added
        # the matching sibling file is unaffected
        assert entries["click.md"].change is EntryChange.unchanged

    def test_status_clone_failure_yields_error_dep_best_effort(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A clone failure is best-effort: the bad dep -> ``error`` (credential-free,
        no entries) while the good dep is still checked; exit 1; no clone temp dirs
        leak.
        """
        good_repo = make_repo("good", {".usages/g.md": "good"})
        write_config(_GOOD_AND_BAD_STATUS_DEPS)
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"
        # both targets exist so compute_dep_status runs for both; the good dep's
        # target matches its remote -> up_to_date.
        good_target = usages_root / "libs" / "good"
        good_target.mkdir(parents=True)
        (good_target / "g.md").write_text("good")
        (usages_root / "libs" / "bad").mkdir(parents=True)

        with patch_clone({"https://x/good.git": good_repo}, failing={"https://x/bad.git"}):
            report = status()

        assert report.exit_code == 1
        by_dep = {dep.dep: dep for dep in report.deps}
        assert by_dep["good"].state is UsageState.up_to_date
        assert by_dep["bad"].state is UsageState.error
        assert by_dep["bad"].entries == []
        assert by_dep["bad"].error == "failed to check usages status for libs/bad"
        # credential-free: the failed git URL never leaks into the error message
        assert "https://x/bad.git" not in by_dep["bad"].error
        # no clone temp dirs leak: the failed clone self-cleans, the successful
        # clone is cleaned by compute_dep_status's outer finally block
        assert list((tmp_path / "clones").iterdir()) == []

    def test_status_dep_with_root_honored_up_to_date(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ):
        """A dep declaring ``root: folder`` rebuilds its expected tree only from
        ``clone/folder`` — mirroring what ``sync`` deployed — so a target matching
        that in-root deployment is ``up_to_date``; the out-of-root sibling never
        affects the comparison. Regression guard: if ``depcfg.root`` were ever
        dropped from the status rebuild, the expected tree would gain the
        ``folder/`` prefix plus the out-of-root files, flipping this to
        ``out_of_date``.
        """
        repo = make_repo(
            "click",
            {
                "folder/cell_1/cell_2/.usages/a.md": "a",
                "folder/subfolder/.usages/b.md": "b",
                # out-of-root: under OTHER/, excluded by root
                "OTHER/.usages/ignore.md": "ignore",
            },
        )
        write_config(
            "usages:\n  libs:\n    click:\n      git: https://x/c.git\n      root: folder\n",
        )
        monkeypatch.chdir(tmp_path)

        target = tmp_path / ".goga" / "usages" / "libs" / "click"
        # mirror what sync(force=True) deploys from clone/folder (.usages dropped)
        (target / "cell_1" / "cell_2").mkdir(parents=True)
        (target / "cell_1" / "cell_2" / "a.md").write_text("a")
        (target / "subfolder").mkdir(parents=True)
        (target / "subfolder" / "b.md").write_text("b")

        with patch_clone({"https://x/c.git": repo}):
            report = status()

        assert report.deps[0].state is UsageState.up_to_date
        assert report.exit_code == 0

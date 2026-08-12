# tests/usages/test_sync.py — contract and logic tests for the sync orchestrator

import importlib
import inspect
from pathlib import Path
from unittest import mock

import pytest
from goga.usages import sync as facade_sync
from goga.usages.sync import sync

# Resolve the inner ``sync.py`` submodule via importlib. The facade ``goga.usages``
# re-exports the ``sync`` function, which shadows the submodule attribute in the
# package ``__dict__``. On Python 3.10
# ``mock.patch("goga.usages.sync.clone_repository")`` resolves the dotted path
# through sequential ``getattr``, finds the function where it expects the
# submodule, and raises ``AttributeError``. Holding a direct reference to the
# module makes ``mock.patch.object`` work uniformly across Python versions.
_sync_mod = importlib.import_module("goga.usages.sync.sync")

# --- helpers ---


def _write_config(project_dir: Path, *, usages_block: str | None) -> None:
    """Write a ``.goga/config.yml``; ``usages_block`` None omits the usages section."""
    goga = project_dir / ".goga"
    goga.mkdir(exist_ok=True)
    parts = [
        "language: python",
        "image: qarium/foo:1.0",
        "pipeline:",
        "  agent: claude",
        "build:",
        "  task_executor:",
        "    agent: claude",
    ]
    if usages_block is not None:
        parts.append(usages_block)
    (goga / "config.yml").write_text("\n".join(parts) + "\n")


_CLICK_DEP_BLOCK = "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n"

_DEP_BLOCK_WITH_ROOT = (
    "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n      root: docs\n"
)

# Two groups (``libs``, ``apps``), each with a ``common`` dep so a ``dep``-only
# filter can be observed crossing group boundaries; ``libs`` also has ``click``
# so a ``group`` filter narrows to one group's deps.
_MULTI_GROUP_DEP_BLOCK = (
    "usages:\n"
    "  libs:\n"
    "    click:\n"
    "      git: https://x/click.git\n"
    "      ref: main\n"
    "    common:\n"
    "      git: https://x/common.git\n"
    "      ref: main\n"
    "  apps:\n"
    "    common:\n"
    "      git: https://x/common.git\n"
    "      ref: main\n"
)


# --- contract tests ---


class TestSyncContract:
    def test_importable_from_goga_usages_sync(self):
        """sync is importable from goga.usages.sync."""
        assert callable(sync)

    def test_importable_from_facade(self):
        """sync is the same object exported by the goga.usages facade."""
        assert sync is facade_sync

    def test_signature(self):
        """Signature is sync(force: bool = False, group=None, dep=None) -> int."""
        sig = inspect.signature(sync)
        params = list(sig.parameters)
        assert params == ["force", "group", "dep"]
        assert sig.parameters["force"].annotation is bool
        assert sig.parameters["force"].default is False
        assert sig.parameters["group"].default is None
        assert sig.parameters["dep"].default is None
        assert sig.return_annotation is int


# --- logic tests ---


class TestSyncLogic:
    @pytest.mark.parametrize(
        "usages_block",
        [
            pytest.param(None, id="absent-section"),
            pytest.param("usages: {}", id="present-empty"),
        ],
    )
    def test_sync_usages_none_or_empty_returns_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        usages_block: str | None,
    ):
        """Flow C: no usages (None or {}) → exit 0; clean/clone/deploy not called."""
        _write_config(tmp_path, usages_block=usages_block)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_sync_mod, "clean_usages_dir") as clean_mock,
            mock.patch.object(_sync_mod, "clone_repository") as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync()

        assert result == 0
        clean_mock.assert_not_called()
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_sync_incremental_skips_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Flow A: existing target dir → skip; clone/deploy not called."""
        _write_config(tmp_path, usages_block=_CLICK_DEP_BLOCK)
        # pre-create the target so incremental skips it
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_sync_mod, "clone_repository") as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync()

        assert result == 0
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_sync_force_cleans_and_resyncs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Flow B: force cleans stale dirs (keeps cooks), then clone+deploy run."""
        _write_config(tmp_path, usages_block=_CLICK_DEP_BLOCK)

        usages_root = tmp_path / ".goga" / "usages"
        (usages_root / "libs" / "click").mkdir(parents=True)  # existing target
        (usages_root / "cooks").mkdir(parents=True)  # preserved verbatim
        (usages_root / "cooks" / "k.md").write_text("cook")
        (usages_root / "stale").mkdir()  # stale subdir → removed by clean
        (usages_root / "stale" / "x.md").write_text("stale")

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True)

        assert result == 0
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        # deploy received the clone path, the group/dep target, and depcfg.root
        # (None here — this dep declares no root → walk from clone root)
        deploy_mock.assert_called_once_with(
            fake_repo,
            Path(".goga/usages/libs/click"),
            None,
        )

        # cooks preserved, stale removed (real clean_usages_dir ran)
        assert (usages_root / "cooks" / "k.md").read_text() == "cook"
        assert not (usages_root / "stale").exists()

    def test_sync_per_dep_failure_sets_exit_code_one(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Best-effort: a clone failure sets exit_code=1 without aborting."""
        _write_config(tmp_path, usages_block=_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(
            _sync_mod,
            "clone_repository",
            side_effect=Exception("boom"),
        ) as clone_mock:
            result = sync()

        assert result == 1
        clone_mock.assert_called_once_with("https://x/click.git", "main")

    def test_sync_deploy_failure_sets_exit_code_one_and_cleans_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Clone succeeds but deploy fails → exit 1; cloned repo is cleaned up.

        Exercises the path where ``repo`` is assigned (clone returned a real
        path) and ``deploy_usages`` subsequently raises, so the ``finally``
        block runs cleanup of a non-None repo.
        """
        _write_config(tmp_path, usages_block=_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        cloned_repo = tmp_path / "cloned"
        cloned_repo.mkdir()

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=cloned_repo,
            ) as clone_mock,
            mock.patch.object(
                _sync_mod,
                "deploy_usages",
                side_effect=OSError("deploy boom"),
            ) as deploy_mock,
        ):
            result = sync()

        assert result == 1
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        # deploy was still called with depcfg.root threaded through (None here)
        deploy_mock.assert_called_once_with(
            cloned_repo,
            Path(".goga/usages/libs/click"),
            None,
        )
        # finally cleaned up the successfully cloned repo despite deploy failing
        assert not cloned_repo.exists()

    def test_sync_threads_root_to_deploy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A dep declaring ``root: docs`` threads it verbatim into deploy (3rd arg).

        ``sync`` does not resolve or validate ``root`` — it passes ``depcfg.root``
        straight through; ``deploy_usages`` owns resolution. Here the clone is
        mocked and deploy is mocked, so we only assert the threaded value.
        """
        _write_config(tmp_path, usages_block=_DEP_BLOCK_WITH_ROOT)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True)

        assert result == 0
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        # root="docs" threaded as the third positional argument, verbatim
        deploy_mock.assert_called_once_with(
            fake_repo,
            Path(".goga/usages/libs/click"),
            "docs",
        )

    def test_sync_group_filter_syncs_only_matching_group(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """``group="libs"`` syncs only the ``libs`` group (its ``click`` + ``common``)."""
        _write_config(tmp_path, usages_block=_MULTI_GROUP_DEP_BLOCK)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True, group="libs", dep=None)

        assert result == 0
        # only the two deps under ``libs`` are synced; ``apps/common`` is skipped
        assert clone_mock.call_count == 2
        clone_mock.assert_any_call("https://x/click.git", "main")
        clone_mock.assert_any_call("https://x/common.git", "main")
        deploy_targets = {call.args[1] for call in deploy_mock.call_args_list}
        assert deploy_targets == {
            Path(".goga/usages/libs/click"),
            Path(".goga/usages/libs/common"),
        }
        assert Path(".goga/usages/apps/common") not in deploy_targets

    def test_sync_dep_filter_applies_across_all_groups(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """``dep="common"`` (no group) syncs ``common`` in every group."""
        _write_config(tmp_path, usages_block=_MULTI_GROUP_DEP_BLOCK)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True, group=None, dep="common")

        assert result == 0
        # ``common`` in both ``libs`` and ``apps``; ``libs/click`` is skipped
        assert clone_mock.call_count == 2
        # every call targets the ``common`` dep's git URL (never ``click``)
        assert {call.args for call in clone_mock.call_args_list} == {
            ("https://x/common.git", "main")
        }
        deploy_targets = {call.args[1] for call in deploy_mock.call_args_list}
        assert deploy_targets == {
            Path(".goga/usages/libs/common"),
            Path(".goga/usages/apps/common"),
        }
        assert Path(".goga/usages/libs/click") not in deploy_targets

    def test_sync_group_and_dep_filter_narrows_to_one_dep(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """``group="libs", dep="click"`` syncs exactly ``libs/click``."""
        _write_config(tmp_path, usages_block=_MULTI_GROUP_DEP_BLOCK)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True, group="libs", dep="click")

        assert result == 0
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        deploy_mock.assert_called_once_with(
            fake_repo,
            Path(".goga/usages/libs/click"),
            None,
        )

    def test_sync_filter_matching_nothing_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A filter matching no dep → exit 0 (nothing to sync, not an error)."""
        _write_config(tmp_path, usages_block=_MULTI_GROUP_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_sync_mod, "clone_repository") as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True, group="nope", dep=None)

        assert result == 0
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_sync_force_with_filter_wipes_non_matching_then_reclones_only_matching(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """``force`` + filter: ``clean_usages_dir`` is unconditional (per the
        ``sync`` CODEMANIFEST step 4), so previously-synced NON-matching targets
        are removed from disk; only the matching deps are then re-cloned/deployed.

        Pins the designed ``force``+filter composition (design Edge Case:
        "``clean_usages_dir`` still wipes, but only matching deps are re-cloned")
        against a future change that would silently scope the clean to the filter.
        """
        _write_config(tmp_path, usages_block=_MULTI_GROUP_DEP_BLOCK)

        usages_root = tmp_path / ".goga" / "usages"
        # Pre-existing synced trees for BOTH a matching and a non-matching dep.
        (usages_root / "libs" / "click").mkdir(parents=True)
        (usages_root / "libs" / "click" / "old.md").write_text("old")
        (usages_root / "apps" / "common").mkdir(parents=True)  # NON-matching → wiped
        (usages_root / "apps" / "common" / "old.md").write_text("old")
        (usages_root / "cooks").mkdir(parents=True)  # preserved verbatim
        (usages_root / "cooks" / "k.md").write_text("cook")

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()

        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(
                _sync_mod,
                "clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch.object(_sync_mod, "deploy_usages") as deploy_mock,
        ):
            result = sync(force=True, group="libs", dep="click")

        assert result == 0
        # only the matching dep is re-cloned/deployed
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        deploy_mock.assert_called_once_with(fake_repo, Path(".goga/usages/libs/click"), None)
        # clean ran for real: the non-matching ``apps/common`` tree is GONE
        assert not (usages_root / "apps" / "common").exists()
        assert not (usages_root / "apps").exists()
        # cooks is preserved (clean never touches it)
        assert (usages_root / "cooks" / "k.md").read_text() == "cook"

# tests/usages/test_sync.py — contract and logic tests for the sync orchestrator

import inspect
from pathlib import Path
from unittest import mock

import pytest
from goga.usages import sync as facade_sync
from goga.usages.sync import sync

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


_CLICK_DEP_BLOCK = (
    "usages:\n"
    "  libs:\n"
    "    click:\n"
    "      git: https://x/click.git\n"
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
        """Signature is sync(force: bool = False) -> int."""
        sig = inspect.signature(sync)
        params = list(sig.parameters)
        assert params == ["force"]
        assert sig.parameters["force"].annotation is bool
        assert sig.parameters["force"].default is False
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
            mock.patch("goga.usages.sync.clean_usages_dir") as clean_mock,
            mock.patch("goga.usages.sync.clone_repository") as clone_mock,
            mock.patch("goga.usages.sync.deploy_usages") as deploy_mock,
        ):
            result = sync()

        assert result == 0
        clean_mock.assert_not_called()
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_sync_incremental_skips_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Flow A: existing target dir → skip; clone/deploy not called."""
        _write_config(tmp_path, usages_block=_CLICK_DEP_BLOCK)
        # pre-create the target so incremental skips it
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch("goga.usages.sync.clone_repository") as clone_mock,
            mock.patch("goga.usages.sync.deploy_usages") as deploy_mock,
        ):
            result = sync()

        assert result == 0
        clone_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_sync_force_cleans_and_resyncs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
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
            mock.patch(
                "goga.usages.sync.clone_repository",
                return_value=fake_repo,
            ) as clone_mock,
            mock.patch("goga.usages.sync.deploy_usages") as deploy_mock,
        ):
            result = sync(force=True)

        assert result == 0
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        # deploy received the clone path and the group/dep target
        deploy_mock.assert_called_once_with(
            fake_repo,
            Path(".goga/usages/libs/click"),
        )

        # cooks preserved, stale removed (real clean_usages_dir ran)
        assert (usages_root / "cooks" / "k.md").read_text() == "cook"
        assert not (usages_root / "stale").exists()

    def test_sync_per_dep_failure_sets_exit_code_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Best-effort: a clone failure sets exit_code=1 without aborting."""
        _write_config(tmp_path, usages_block=_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        with mock.patch(
            "goga.usages.sync.clone_repository",
            side_effect=Exception("boom"),
        ) as clone_mock:
            result = sync()

        assert result == 1
        clone_mock.assert_called_once_with("https://x/click.git", "main")

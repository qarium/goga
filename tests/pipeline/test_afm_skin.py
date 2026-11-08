"""Contract and logic tests of ``goga.pipeline.afm_skin``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from goga.pipeline import materialize_afm_skin

from tests.pipeline.conftest import patch_skin_source, write_skin

# goga.pipeline.afm_skin is resolved through sys.modules for direct attribute
# patching, mirroring the afm_config precedent. Per
# [[feedback_mock_patch_module_shadowing]].
_afm_skin_module = sys.modules["goga.pipeline.afm_skin"]


@pytest.fixture
def skin_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the fixed skins-base constant into the tmp tree.

    The materializer writes at ``/home/goga/.afm/skins`` — a container-only
    path. The fixed base constant is patched (never the filesystem root), so
    the materialized skin lands under pytest's tmp_path instead.
    """
    base = tmp_path / ".afm-home" / "skins"
    monkeypatch.setattr(_afm_skin_module, "_SKINS_TARGET_BASE", base)
    return base


@pytest.fixture
def packaged_skin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the packaged-dir resolver at a tmp source and seed it with one file."""
    source = tmp_path / "packaged-skin"
    write_skin(source, names=("index.css",))
    patch_skin_source(monkeypatch, source)
    return source


class TestMaterializeAfmSkinContract:
    """Contract: the facade surface and the fixed materialization target."""

    def test_materialize_afm_skin_importable_from_facade(self) -> None:
        """materialize_afm_skin is importable from the goga.pipeline facade."""
        assert materialize_afm_skin is not None

    def test_materialize_afm_skin_copies_packaged_files_flat(
        self, skin_base: Path, packaged_skin: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The packaged skin files land verbatim under <base>/goga/ — a flat copy."""
        write_skin(packaged_skin, names=("goga.css", "favicon.png", "title.txt"))

        result = materialize_afm_skin()

        assert result == skin_base / "goga"
        assert sorted(entry.name for entry in result.iterdir()) == [
            "favicon.png",
            "goga.css",
            "index.css",
            "title.txt",
        ]
        assert (result / "index.css").read_text() == "skin index.css\n"

    def test_materialize_afm_skin_resolves_the_packaged_directory(self) -> None:
        """The source resolver addresses the in-package assets directory.

        The packaged skin ships inside the installed goga package at
        ``goga/assets/afm/skin`` — resolved relative to the module, holding
        regardless of CWD/AFM_DIR.
        """
        resolved = _afm_skin_module._resolve_packaged_skin_dir()

        assert resolved == Path(_afm_skin_module.__file__).resolve().parent.parent / "assets" / "afm" / "skin"
        assert resolved.is_dir()
        assert (resolved / "index.css").is_file()
        assert (resolved / "title.txt").read_text() == "Goga"


class TestMaterializeAfmSkinLogic:
    """Logic: idempotency, reset semantics, and the pre-run error."""

    def test_repeated_materialization_resets_the_target(self, packaged_skin: Path) -> None:
        """A re-run wipes the target first — a stale file never lingers."""
        first = materialize_afm_skin()
        (first / "stale.css").write_text("stale\n")

        second = materialize_afm_skin()

        assert second == first
        assert sorted(entry.name for entry in second.iterdir()) == ["index.css"]

    def test_missing_packaged_skin_raises_before_touching_target(
        self, skin_base: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing packaged skin is a strict pre-run error — the target stays untouched."""
        patch_skin_source(monkeypatch, tmp_path / "absent-skin")

        with pytest.raises(ValueError, match=r"packaged goga skin is missing or empty"):
            materialize_afm_skin()

        assert not skin_base.exists()

    def test_empty_packaged_skin_raises_before_touching_target(
        self, skin_base: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A packaged skin directory without regular files is the same pre-run error."""
        empty = tmp_path / "empty-skin"
        empty.mkdir()
        patch_skin_source(monkeypatch, empty)

        with pytest.raises(ValueError, match=r"packaged goga skin is missing or empty"):
            materialize_afm_skin()

        assert not skin_base.exists()

    def test_existing_skin_survives_a_failed_validation(
        self, skin_base: Path, tmp_path: Path, packaged_skin: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed re-materialization never wipes the previously materialized skin.

        Validate-all precedes wipe-and-write: a package that lost its skin
        directory leaves the working skin of the previous launch in place.
        """
        materialize_afm_skin()

        patch_skin_source(monkeypatch, tmp_path / "absent-skin")

        with pytest.raises(ValueError, match=r"packaged goga skin is missing or empty"):
            materialize_afm_skin()

        assert (skin_base / "goga" / "index.css").read_text() == "skin index.css\n"

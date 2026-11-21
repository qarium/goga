"""Contract and logic tests for the two archive routines declared in
``goga/commands/runtime/CODEMANIFEST`` and colocated in
``goga/commands/runtime/archive.py``:

- ``resolve_archive_destination(archive_stem: str, output: str | None = None) -> Path``
- ``package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> Path``

The resolver is pure validation — nothing is written, every refusal is a
``click.ClickException`` clean error. The packager is the one effectful
entity of the feature: it writes exactly the single archive file, leaves
the source tree untouched, and keeps no partial file on failure (the
guarded cleanup — unlink only after a successful open).
"""

from __future__ import annotations

import inspect
import tarfile
import typing
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.commands.runtime import package_runtime_archive, resolve_archive_destination

# --- Contract tests ---


class TestArchiveContract:
    def test_both_routines_importable_from_facade(self) -> None:
        """Both archive routines are importable from the goga.commands.runtime facade."""
        assert callable(resolve_archive_destination)
        assert callable(package_runtime_archive)

    def test_resolve_archive_destination_signature(self) -> None:
        """resolve_archive_destination(archive_stem: str, output: str | None = None) -> Path."""
        sig = inspect.signature(resolve_archive_destination)
        assert list(sig.parameters) == ["archive_stem", "output"]
        assert sig.parameters["archive_stem"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert sig.parameters["output"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert sig.parameters["output"].default is None
        hints = typing.get_type_hints(resolve_archive_destination)
        assert hints["return"] is Path
        assert hints["archive_stem"] is str
        assert hints["output"] == typing.Optional[str]

    def test_package_runtime_archive_signature(self) -> None:
        """package_runtime_archive(target_dir: Path, wrapper_root: str, destination: Path) -> Path."""
        sig = inspect.signature(package_runtime_archive)
        assert list(sig.parameters) == ["target_dir", "wrapper_root", "destination"]
        for name in sig.parameters:
            assert sig.parameters[name].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(package_runtime_archive)
        assert hints["return"] is Path
        assert hints["target_dir"] is Path
        assert hints["wrapper_root"] is str
        assert hints["destination"] is Path


# --- Logic tests ---


class TestResolveArchiveDestinationLogic:
    @pytest.mark.parametrize(
        ("case", "output"),
        [
            ("default-absent", None),
            ("default-exists", None),
            ("explicit-relative", "custom.tar.gz"),
            ("explicit-existing-file", "existing.tar.gz"),
            ("explicit-directory", "subdir"),
            ("explicit-missing-parent", "no/such/dir/a.tar.gz"),
            ("explicit-empty-string", ""),
        ],
    )
    def test_resolve_archive_destination_matrix(
        self, case: str, output: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The destination-semantics boundary table: default collision, relative
        resolution, overwrite intent, directory/missing-parent refusals.

        The empty-string row pins the documented edge: ``Path("")`` normalizes
        to ``.`` and joins onto the cwd itself, which ``is_dir()`` — a clean
        existing-directory error, consistent with the explicit semantics.
        """
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)

        stem = "goga-runtime-build-main"
        if case == "default-exists":
            (work / f"{stem}.tar.gz").write_text("TAKEN")
        existing = work / "existing.tar.gz"
        existing.write_text("PRE-EXISTING")
        (work / "subdir").mkdir()

        expected_by_case = {
            "default-absent": work / f"{stem}.tar.gz",
            "explicit-relative": work / "custom.tar.gz",
            "explicit-existing-file": existing,
        }

        if case in expected_by_case:
            assert resolve_archive_destination(stem, output) == expected_by_case[case]
        else:
            with pytest.raises(click.ClickException):
                resolve_archive_destination(stem, output)

    def test_resolve_archive_destination_writes_nothing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The resolver is validation only — no file or directory is ever created."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)

        resolve_archive_destination("goga-runtime-build-main")
        resolve_archive_destination("goga-runtime-build-main", "custom.tar.gz")

        assert list(work.iterdir()) == []


class TestPackageRuntimeArchiveLogic:
    def test_package_runtime_archive_wrapper_root_layout(self, tmp_path: Path) -> None:
        """The archive holds the full tree under the single wrapper root.

        Also pins the read-only source guarantee: the target's contents are
        unchanged by packaging (the archive is the only new artifact).
        """
        target = tmp_path / "target"
        (target / "sub").mkdir(parents=True)
        (target / "a.txt").write_text("hello")
        (target / "sub" / "b.log").write_text("log")
        destination = tmp_path / "out" / "archive.tar.gz"
        destination.parent.mkdir()
        source_snapshot = sorted(str(path.relative_to(target)) for path in target.rglob("*"))

        result = package_runtime_archive(target, wrapper_root="goga-runtime-build-main", destination=destination)

        assert result == destination
        assert destination.is_file()

        with tarfile.open(destination) as tar:
            names = tar.getnames()

        assert names[0] == "goga-runtime-build-main"
        assert "goga-runtime-build-main/a.txt" in names
        assert "goga-runtime-build-main/sub/b.log" in names
        assert sorted(str(path.relative_to(target)) for path in target.rglob("*")) == source_snapshot
        assert (target / "a.txt").read_text() == "hello"

    def test_package_runtime_archive_failure_leaves_no_partial(self, tmp_path: Path) -> None:
        """A mid-packaging failure removes the partial archive and propagates."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("hello")
        destination = tmp_path / "partial.tar.gz"

        with (
            mock.patch.object(tarfile.TarFile, "add", side_effect=OSError("mid-packaging failure")),
            pytest.raises(OSError, match="mid-packaging failure"),
        ):
            package_runtime_archive(target, wrapper_root="root", destination=destination)

        assert not destination.exists()

    def test_package_runtime_archive_open_failure_keeps_preexisting_file(self, tmp_path: Path) -> None:
        """A failure before the destination opens never deletes a pre-existing file.

        The destination is pre-created with content and made read-only in a
        writable directory (the explicit -o overwrite scenario): open raises
        PermissionError before any data, the guarded cleanup does not unlink,
        and the original content survives.
        """
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("hello")
        destination = tmp_path / "taken.tar.gz"
        destination.write_text("ORIGINAL")
        destination.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                package_runtime_archive(target, wrapper_root="root", destination=destination)
        finally:
            destination.chmod(0o644)

        assert destination.exists()
        assert destination.read_text() == "ORIGINAL"

    def test_package_runtime_archive_symlinks_preserved(self, tmp_path: Path) -> None:
        """Symlinks land as symlinks — no dereference."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.txt").write_text("hello")
        (target / "link").symlink_to("a.txt")
        destination = tmp_path / "syms.tar.gz"

        package_runtime_archive(target, wrapper_root="root", destination=destination)

        with tarfile.open(destination) as tar:
            assert tar.getmember("root/link").issym()

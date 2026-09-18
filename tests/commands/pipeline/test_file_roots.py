"""Unit tests for the afm file-manager roots producer (``file_roots`` module).

Mirrors the structure of ``goga/commands/pipeline/file_roots.py``: the contract
class pins the signatures, the frozen record shape, and the kw-only required
fields; ``TestCollectFileRoots`` and ``TestEncodeFileRoots`` cover the pure
composition and canonical encoding routines with filesystem fixtures under
``tmp_path`` (no mocks — the single monkeypatched ``Path`` seam exists only for
the inaccessible-host-path case, where chmod 0000 would not reliably produce
EACCES under a root CI user). The byte-exact base64 fixtures pin the canonical
form: ``,``/``:`` separators without spaces, the fixed key order, literal UTF-8
(``ensure_ascii=False``), and preserved standard-base64 padding.
"""

from __future__ import annotations

import base64
import dataclasses
import inspect
import json
import sys
import typing
from pathlib import Path

import pytest
from goga.commands.pipeline.file_roots import FileRoot, collect_file_roots, encode_file_roots

# Resolve the real submodule via sys.modules — `goga.commands.pipeline` binds a
# click Command of the same name on its parent package, so string-based
# monkeypatch paths walking through the package do not resolve (same idiom as
# test_run_pipeline_container.py).
_fr_mod = sys.modules["goga.commands.pipeline.file_roots"]

_PROJECT_ROOT = FileRoot(
    id="project",
    label="project",
    container_path="/workspace",
    mount_read_only=False,
    kind="project",
)

# Byte-exact canonical fixtures (verified against design.md at plan-compile
# time): compact UTF-8 JSON -> one standard-base64 line with padding.
_PROJECT_ONLY_VALUE = (
    "eyJ2ZXJzaW9uIjoxLCJyb290cyI6W3siaWQiOiJwcm9qZWN0IiwibGFiZWwiOiJwcm9qZWN0IiwiY29udGFpbmVyX3Bh"
    "dGgiOiIvd29ya3NwYWNlIiwibW91bnRfcmVhZF9vbmx5IjpmYWxzZSwia2luZCI6InByb2plY3QifV19"
)
_TWO_ROOTS_VALUE = (
    "eyJ2ZXJzaW9uIjoxLCJyb290cyI6W3siaWQiOiJwcm9qZWN0IiwibGFiZWwiOiJwcm9qZWN0IiwiY29udGFpbmVyX3Bh"
    "dGgiOiIvd29ya3NwYWNlIiwibW91bnRfcmVhZF9vbmx5IjpmYWxzZSwia2luZCI6InByb2plY3QifSx7ImlkIjoiaG9t"
    "ZS1nb2dhLWRhdGEiLCJsYWJlbCI6Ii9ob21lL2dvZ2EvZGF0YSIsImNvbnRhaW5lcl9wYXRoIjoiL2hvbWUvZ29nYS9k"
    "YXRhIiwibW91bnRfcmVhZF9vbmx5Ijp0cnVlLCJraW5kIjoiZXh0cmEifV19"
)
_EMPTY_VALUE = "eyJ2ZXJzaW9uIjoxLCJyb290cyI6W119"
_NON_ASCII_VALUE = (
    "eyJ2ZXJzaW9uIjoxLCJyb290cyI6W3siaWQiOiJwcm9qZWN0IiwibGFiZWwiOiJwcm9qZWN0IiwiY29udGFpbmVyX3Bh"
    "dGgiOiIvd29ya3NwYWNlIiwibW91bnRfcmVhZF9vbmx5IjpmYWxzZSwia2luZCI6InByb2plY3QifSx7ImlkIjoiaG9t"
    "ZS1nb2dhLdC00LDQvdC90YvQtSIsImxhYmVsIjoiL2hvbWUvZ29nYS/QtNCw0L3QvdGL0LUiLCJjb250YWluZXJfcGF0"
    "aCI6Ii9ob21lL2dvZ2Ev0LTQsNC90L3Ri9C1IiwibW91bnRfcmVhZF9vbmx5IjpmYWxzZSwia2luZCI6ImV4dHJhIn1d"
    "fQ=="
)


def _decode(value: str) -> dict:
    """Decode an AFM_DOCKER_FILE_ROOTS value into its payload dict."""
    return json.loads(base64.b64decode(value))


# --- Contract tests ---


class TestFileRootsContract:
    def test_signatures_and_frozen_record_match_contract(self) -> None:
        """Signatures, field set/order, kw-only required fields, and immutability match the contract."""
        assert list(inspect.signature(collect_file_roots).parameters) == ["tokens"]
        collect_hints = typing.get_type_hints(collect_file_roots)
        assert collect_hints["tokens"] == list[str]
        assert collect_hints["return"] == list[FileRoot]

        assert list(inspect.signature(encode_file_roots).parameters) == ["roots"]
        encode_hints = typing.get_type_hints(encode_file_roots)
        assert encode_hints["roots"] == list[FileRoot]
        assert encode_hints["return"] is str

        assert [f.name for f in dataclasses.fields(FileRoot)] == [
            "id",
            "label",
            "container_path",
            "mount_read_only",
            "kind",
        ]
        assert all(f.kw_only and f.default is dataclasses.MISSING for f in dataclasses.fields(FileRoot))

        root = FileRoot(
            id="home-goga-data",
            label="/home/goga/data",
            container_path="/home/goga/data",
            mount_read_only=True,
            kind="extra",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            root.id = "x"

    def test_importable_from_facade_and_declared_location(self) -> None:
        """All three names are importable from the package facade; the module lives at its declared location."""
        from goga.commands.pipeline import FileRoot as facade_FileRoot
        from goga.commands.pipeline import collect_file_roots as facade_collect_file_roots
        from goga.commands.pipeline import encode_file_roots as facade_encode_file_roots

        assert facade_FileRoot is FileRoot
        assert facade_collect_file_roots is collect_file_roots
        assert facade_encode_file_roots is encode_file_roots
        assert sys.modules["goga.commands.pipeline.file_roots"].__file__.endswith(
            "goga/commands/pipeline/file_roots.py"
        )


# --- collect_file_roots ---


class TestCollectFileRoots:
    def test_collect_file_roots_with_directory_mount(self, tmp_path: Path) -> None:
        """An existing host directory mounted via -v becomes one extra root after the project root."""
        (tmp_path / "data").mkdir()

        roots = collect_file_roots(["-v", f"{tmp_path}/data:/home/goga/data"])

        assert len(roots) == 2
        assert roots[0] == FileRoot(
            id="project",
            label="project",
            container_path="/workspace",
            mount_read_only=False,
            kind="project",
        )
        assert roots[1].id == "home-goga-data"
        assert roots[1].label == "/home/goga/data"
        assert roots[1].container_path == "/home/goga/data"
        assert roots[1].mount_read_only is False
        assert roots[1].kind == "extra"

    def test_collect_file_roots_read_only_mode(self, tmp_path: Path) -> None:
        """The third :ro/:rw mode segment maps onto mount_read_only (exact segment match)."""
        (tmp_path / "ro").mkdir()
        (tmp_path / "rw").mkdir()
        (tmp_path / "roz").mkdir()

        roots = collect_file_roots(
            [
                "-v",
                f"{tmp_path}/ro:/mnt/ro:ro",
                "-v",
                f"{tmp_path}/rw:/mnt/rw:rw",
                "-v",
                f"{tmp_path}/roz:/mnt/roz:ro,z",
            ],
        )

        assert {r.container_path: r.mount_read_only for r in roots[1:]} == {
            "/mnt/ro": True,
            "/mnt/rw": False,
            "/mnt/roz": True,
        }

    def test_collect_file_roots_long_volume_forms(self, tmp_path: Path) -> None:
        """--volume VALUE and --volume=VALUE are recognized like the short -v form."""
        (tmp_path / "d").mkdir()

        roots = collect_file_roots(
            ["--volume", f"{tmp_path}/d:/a", f"--volume={tmp_path}/d:/b"],
        )

        assert [r.container_path for r in roots[1:]] == ["/a", "/b"]

    def test_collect_file_roots_empty_tokens(self) -> None:
        """No docker.run tokens still yield the project-only list — the variable is written on EVERY run launch."""
        roots = collect_file_roots([])

        assert roots == [
            FileRoot(
                id="project",
                label="project",
                container_path="/workspace",
                mount_read_only=False,
                kind="project",
            )
        ]

    def test_collect_file_roots_skips_named_volume_file_missing(self, tmp_path: Path) -> None:
        """Named volumes, file mounts, missing paths, and unrelated flags never become roots."""
        (tmp_path / "file.txt").write_text("x")

        roots = collect_file_roots(
            [
                "-v",
                "mydata:/mnt/named",
                "-v",
                f"{tmp_path}/file.txt:/mnt/file",
                "-v",
                f"{tmp_path}/missing:/mnt/missing",
                "--network=host",
                "-e",
                "X=Y",
            ]
        )

        assert [r.container_path for r in roots] == ["/workspace"]

    def test_collect_file_roots_dangling_and_malformed(self) -> None:
        """Dangling flags, anonymous volumes, >3-part values, and empty values are skipped without exceptions."""
        roots = collect_file_roots(
            ["-v", "--volume", "-v", "/ctr", "-v", "a:b:c:d", "-v", "", "-v"],
        )

        assert [r.container_path for r in roots] == ["/workspace"]

    def test_collect_file_roots_supersedes_duplicate_container_path(self, tmp_path: Path) -> None:
        """A later declaration into the same container path replaces the record AND its position/fields."""
        (tmp_path / "one").mkdir()
        (tmp_path / "two").mkdir()

        roots = collect_file_roots(
            ["-v", f"{tmp_path}/one:/mnt/x:ro", "-v", f"{tmp_path}/two:/mnt/x"],
        )

        assert [r.container_path for r in roots] == ["/workspace", "/mnt/x"]
        assert roots[1].mount_read_only is False

    def test_collect_file_roots_non_directory_supersedes_root(self, tmp_path: Path) -> None:
        """A later non-root-yielding declaration (named volume) shadows an earlier root on the same path."""
        (tmp_path / "d").mkdir()

        roots = collect_file_roots(["-v", f"{tmp_path}/d:/mnt/x", "-v", "vol:/mnt/x"])

        assert [r.container_path for r in roots] == ["/workspace"]

    def test_collect_file_roots_id_never_collides_with_project(self, tmp_path: Path) -> None:
        """An extra root whose sanitized base is "project" gets the sha256-suffixed id."""
        (tmp_path / "p").mkdir()

        roots = collect_file_roots(["-v", f"{tmp_path}/p:/project"])

        ids = [r.id for r in roots]
        assert len(set(ids)) == len(ids)
        assert roots[1].id == "project-ea0135bc"
        assert roots[1].id != "project"

    def test_collect_file_roots_root_mount_point_maps_to_a_valid_id(self, tmp_path: Path) -> None:
        """A container path of `/` never yields the empty id — it maps to `root`."""
        (tmp_path / "all").mkdir()

        roots = collect_file_roots(["-v", f"{tmp_path}/all:/"])

        assert [r.id for r in roots] == ["project", "root"]
        assert roots[1].container_path == "/"

    def test_collect_file_roots_root_id_collides_with_a_root_subpath_mount(self, tmp_path: Path) -> None:
        """/ and /root both map to the `root` base — the second gets the sha256 suffix."""
        (tmp_path / "all").mkdir()
        (tmp_path / "home").mkdir()

        roots = collect_file_roots(
            [
                "-v",
                f"{tmp_path}/all:/",
                "-v",
                f"{tmp_path}/home:/root",
            ]
        )

        assert [r.id for r in roots] == ["project", "root", "root-94a6b447"]

    def test_collect_file_roots_id_unique_on_sanitization_collision(self, tmp_path: Path) -> None:
        """Two container paths sanitizing to the same base get distinct ids (second gets the sha256 suffix)."""
        (tmp_path / "goga" / "data").mkdir(parents=True)
        (tmp_path / "goga-data").mkdir()

        roots = collect_file_roots(
            [
                "-v",
                f"{tmp_path}/goga/data:/home/goga/data",
                "-v",
                f"{tmp_path}/goga-data:/home/goga-data",
            ]
        )

        ids = [r.id for r in roots[1:]]
        assert ids == ["home-goga-data", "home-goga-data-96b6889c"]
        assert len(set(ids)) == 2

    def test_collect_file_roots_deterministic(self, tmp_path: Path) -> None:
        """Identical tokens produce an identical list — including order and ids — on every call."""
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        tokens = ["-v", f"{tmp_path}/a:/mnt/a", "-v", f"{tmp_path}/b:/mnt/b"]

        assert collect_file_roots(tokens) == collect_file_roots(tokens)

    def test_collect_file_roots_relative_host_path(self, tmp_path: Path, monkeypatch) -> None:
        """A relative host path is resolved from the launcher CWD — the same directory docker CLI resolves from."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "rel").mkdir()

        roots = collect_file_roots(["-v", "./rel:/mnt/rel"])

        assert roots[1].container_path == "/mnt/rel"

    def test_collect_file_roots_inaccessible_host_path_is_skipped(self, monkeypatch) -> None:
        """An OSError from the host probe is swallowed by _host_is_dir — the launcher never tracebacks on -v /root/... .

        chmod 0000 is not a reliable EACCES source under a root CI user, so the
        module-level ``Path`` seam is replaced with a stub whose ``is_dir``
        raises ``PermissionError`` (an ``OSError`` subclass).
        """

        class UnreachablePath:
            def __init__(self, path: str) -> None:
                self._path = path

            def is_dir(self) -> bool:
                raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(_fr_mod, "Path", UnreachablePath)

        roots = collect_file_roots(["-v", "/root/secrets:/mnt/secret"])

        assert [r.container_path for r in roots] == ["/workspace"]

    def test_collect_file_roots_symlink_to_directory(self, tmp_path: Path) -> None:
        """Path.is_dir() follows symlinks — a symlink to a directory counts as one (docker resolves it too)."""
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)

        roots = collect_file_roots(["-v", f"{link}:/mnt/link"])

        assert roots[1].container_path == "/mnt/link"


# --- encode_file_roots ---


class TestEncodeFileRoots:
    def test_encode_file_roots_project_only_canonical(self) -> None:
        """The project-only list encodes to the byte-exact canonical fixture with a round-trippable payload."""
        value = encode_file_roots([_PROJECT_ROOT])

        assert value == _PROJECT_ONLY_VALUE
        payload = _decode(value)
        assert payload == {
            "version": 1,
            "roots": [
                {
                    "id": "project",
                    "label": "project",
                    "container_path": "/workspace",
                    "mount_read_only": False,
                    "kind": "project",
                }
            ],
        }
        assert list(payload["roots"][0]) == ["id", "label", "container_path", "mount_read_only", "kind"]

    def test_encode_file_roots_deterministic_and_two_roots(self) -> None:
        """Repeated calls give the identical string, and the two-roots list matches the byte-exact fixture."""
        roots = [
            _PROJECT_ROOT,
            FileRoot(
                id="home-goga-data",
                label="/home/goga/data",
                container_path="/home/goga/data",
                mount_read_only=True,
                kind="extra",
            ),
        ]

        first = encode_file_roots(roots)
        second = encode_file_roots(roots)

        assert first == second
        assert first == _TWO_ROOTS_VALUE

    def test_encode_file_roots_empty_list(self) -> None:
        """The empty list still encodes a valid payload (collect always returns the project root in practice)."""
        assert encode_file_roots([]) == _EMPTY_VALUE

    def test_encode_file_roots_non_ascii_literal_utf8(self) -> None:
        """Non-ASCII field values stay literal UTF-8 (ensure_ascii=False) — pinned byte-exact."""
        roots = [
            _PROJECT_ROOT,
            FileRoot(
                id="home-goga-данные",
                label="/home/goga/данные",
                container_path="/home/goga/данные",
                mount_read_only=False,
                kind="extra",
            ),
        ]

        value = encode_file_roots(roots)

        assert value == _NON_ASCII_VALUE

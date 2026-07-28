import itertools
import os
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect HOME to a tmp dir so no test writes to the real ~/.goga/.

    Path.home() and Path.expanduser() both resolve through os.environ["HOME"]
    on POSIX, so setting HOME covers every code path that derives the user's
    home directory. Tests that need a specific HOME value still win: their own
    monkeypatch.setenv / mock.patch calls run after this autouse fixture and
    override it.
    """
    home = tmp_path / ".pytest_home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent / ".project"


@contextmanager
def cwd(path):
    original = Path.cwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(original))


# --- shared cell-level usages fixtures (used by tests/usages and tests/commands) ---

_CONFIG_HEADER = [
    "language: python",
    "image: qarium/foo:1.0",
    "pipeline:",
    "  agent: claude",
    "build:",
    "  task_executor:",
    "    agent: claude",
]


@pytest.fixture
def make_repo(tmp_path: Path):
    """Factory: build a fake git repo under ``tmp_path`` with the given files.

    ``files`` maps a repo-relative path to its text content (e.g.
    ``{".usages/click.md": "..."}``). Returns the created repo root. The repo
    persists for the test (only the *clone* copies are cleaned up by ``sync``).
    """

    def _make(name: str, files: dict[str, str]) -> Path:
        root = tmp_path / "repos" / name
        root.mkdir(parents=True)
        for rel, content in files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return root

    return _make


@pytest.fixture
def write_config(tmp_path: Path):
    """Factory: write ``.goga/config.yml`` into ``tmp_path`` (the project CWD).

    Pass a ``usages`` YAML block string, or ``None`` to omit the section.
    Returns ``tmp_path`` (the project root tests ``chdir`` into).
    """

    def _write(usages_block: str | None) -> Path:
        goga = tmp_path / ".goga"
        goga.mkdir(exist_ok=True)
        parts = list(_CONFIG_HEADER)
        if usages_block is not None:
            parts.append(usages_block)
        (goga / "config.yml").write_text("\n".join(parts) + "\n")
        return tmp_path

    return _write


@pytest.fixture
def patch_clone(tmp_path: Path):
    """Factory: context manager mocking ``clone_repository``'s git subprocess.

    Only the git boundary (``goga.usages.sync.clone.subprocess.run`` and
    ``tempfile.mkdtemp``) is mocked — ``clean_usages_dir`` and ``deploy_usages``
    run for real against the filesystem. ``sources`` maps each declared git URL
    to a local fake-repo path that is copied into the clone temp dir; URLs in
    ``failing`` raise ``subprocess.CalledProcessError`` on the clone command.
    """

    counter = itertools.count()

    @contextmanager
    def _patch(
        sources: dict[str, Path],
        *,
        failing: set[str] | None = None,
    ) -> Iterator[None]:
        failing_urls = failing or set()

        def mkdtemp_side_effect() -> str:
            clone_dir = tmp_path / "clones" / f"clone_{next(counter)}"
            clone_dir.mkdir(parents=True)
            return str(clone_dir)

        def run_side_effect(cmd: list[str], *args: object, **kwargs: object) -> None:
            if "clone" in cmd:
                url = cmd[2]
                target = Path(cmd[3])
                if url in failing_urls:
                    raise subprocess.CalledProcessError(128, cmd)
                shutil.copytree(sources[url], target, dirs_exist_ok=True)
            # checkout command: no-op in the mock

        with (
            mock.patch(
                "goga.usages.sync.clone.subprocess.run",
                side_effect=run_side_effect,
            ),
            mock.patch(
                "goga.usages.sync.clone.tempfile.mkdtemp",
                side_effect=mkdtemp_side_effect,
            ),
        ):
            yield

    return _patch

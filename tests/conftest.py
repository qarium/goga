import os
from contextlib import contextmanager
from pathlib import Path

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

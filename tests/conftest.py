import os
from contextlib import contextmanager
from pathlib import Path

import pytest


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

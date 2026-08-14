from __future__ import annotations

import pytest


@pytest.fixture
def _clean_cwd(tmp_path, monkeypatch) -> None:
    """Run each survey test in a clean dir without .goga/config.yml.

    ask_goga_config() short-circuits to None when .goga/config.yml exists.
    The repository CWD already contains .goga/config.yml (the goga project's
    own config), and there is no autouse chdir in the shared conftest (it
    redirects only HOME). Without this, every survey test would skip the
    survey and fail its assertions. monkeypatch.chdir restores the original
    CWD automatically on teardown.
    """
    monkeypatch.chdir(tmp_path)

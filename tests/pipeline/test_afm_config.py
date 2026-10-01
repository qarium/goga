"""Contract and logic tests of ``goga.pipeline.afm_config``."""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest
import yaml
from goga.pipeline import write_afm_config

# goga.pipeline.afm_config is shadowed in the package __init__ by the
# write_afm_config function, so a string-based mock.patch path walking through
# it fails on Python 3.10. Resolve the real module via sys.modules and patch its
# attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_afm_config_module = sys.modules["goga.pipeline.afm_config"]


class TestWriteAfmConfigContract:
    """Contract: the facade surface and signature of ``write_afm_config``."""

    def test_write_afm_config_importable_from_facade(self) -> None:
        """write_afm_config is importable from the goga.pipeline facade."""
        assert write_afm_config is not None

    def test_write_afm_config_signature_matches_contract(self) -> None:
        """write_afm_config exposes the (agent) -> Path signature."""
        signature = inspect.signature(write_afm_config)
        parameters = list(signature.parameters)

        assert parameters == ["agent"]

        agent_annotation = signature.parameters["agent"].annotation
        assert agent_annotation == "str | None" or agent_annotation == str | None
        assert signature.parameters["agent"].default is inspect.Parameter.empty

        return_annotation = signature.return_annotation
        assert return_annotation == "Path" or return_annotation is Path


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the fixed home-path constant into the tmp tree.

    The routine writes at ``/home/goga/.afm/config.yaml`` — a container-only
    path. The fixed-path constant is patched (never the filesystem root), so
    the written document lands under pytest's tmp_path instead.
    """
    path = tmp_path / ".afm" / "config.yaml"
    monkeypatch.setattr(_afm_config_module, "_AFM_CONFIG_PATH", path)
    return path


class TestWriteAfmConfigLogic:
    """Logic: the authored document, the agent optionality, and the failure mode."""

    def test_write_afm_config_with_agent_writes_resolved_wrapper_and_static_fields(self, config_path: Path) -> None:
        """A resolved agent yields client.command plus the four static fields."""
        written = write_afm_config("codex")

        assert written == config_path

        data = yaml.safe_load(config_path.read_text())
        assert data == {
            "client": {"command": "/home/goga/bin/codex-as-claude.sh"},
            "theme": "goga",
            "open_browser": False,
            "proxy": {"enabled": False},
            "prompts_dir": "/home/goga/pipeline/prompts",
        }
        assert "/home/goga/bin/" in data["client"]["command"]

    def test_write_afm_config_without_agent_omits_client_block(self, config_path: Path) -> None:
        """No agent omits client entirely — a null command is never written."""
        write_afm_config(None)

        data = yaml.safe_load(config_path.read_text())

        assert "client" not in data
        assert set(data) == {"theme", "open_browser", "proxy", "prompts_dir"}

    def test_write_afm_config_rewrites_whole_file_idempotently(self, config_path: Path) -> None:
        """Each invocation rewrites the whole document — stale keys disappear."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("stale: true\n")

        write_afm_config("claude")
        first = yaml.safe_load(config_path.read_text())
        assert "stale" not in first

        write_afm_config("claude")
        second = yaml.safe_load(config_path.read_text())

        assert second == first
        assert set(second) == {"client", "theme", "open_browser", "proxy", "prompts_dir"}

    def test_write_afm_config_unwritable_home_raises_oserror(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unwritable home raises OSError with no partial write and no output."""
        if os.getuid() == 0:
            pytest.skip("root bypasses directory permissions")

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.parent.chmod(0o500)

        try:
            with pytest.raises(OSError, match="Permission denied"):
                write_afm_config("codex")
        finally:
            config_path.parent.chmod(0o700)

        assert not config_path.exists()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

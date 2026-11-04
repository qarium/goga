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

# goga's observer hook registration — the fixed D2 entry the composed content
# additionally carries in the global ``hooks`` layer.
_OBSERVER_HOOK = {
    "id": "goga",
    "events": "all",
    "command": "python3 -m goga.pipeline hook",
    "inherit_env": True,
}


class TestWriteAfmConfigContract:
    """Contract: the facade surface and signature of ``write_afm_config``."""

    def test_write_afm_config_importable_from_facade(self) -> None:
        """write_afm_config is importable from the goga.pipeline facade."""
        assert write_afm_config is not None

    def test_write_afm_config_signature_matches_contract(self) -> None:
        """write_afm_config exposes the (agent, flow, workflow) -> Path signature."""
        signature = inspect.signature(write_afm_config)
        parameters = list(signature.parameters)

        assert parameters == ["agent", "flow", "workflow"]

        agent_annotation = signature.parameters["agent"].annotation
        assert agent_annotation == "str | None" or agent_annotation == str | None
        assert signature.parameters["agent"].default is inspect.Parameter.empty

        assert signature.parameters["flow"].default is None
        assert signature.parameters["workflow"].default is None

        return_annotation = signature.return_annotation
        assert return_annotation == "Path" or return_annotation is Path

    def test_write_afm_config_static_fields_carry_six_entries(self, config_path: Path) -> None:
        """The written config parses as YAML carrying the SIX static fields.

        ``add_stage.enabled false`` — the disabled dashboard stage-addition —
        and ``skin_dir`` — the engine's custom skin directory, served
        wholesale as the active skin while it holds ``index.css`` — join the
        four pre-existing statics, written unconditionally on every launch
        (the stage set presented to the engine stays exactly the compiled
        pipeline; the skin is materialized there by the run coordination;
        ``theme`` only names the engine-builtin fallback skin).
        """
        write_afm_config(None)

        data = yaml.safe_load(config_path.read_text())

        assert data["theme"] == "goga"
        assert data["open_browser"] is False
        assert data["proxy"] == {"enabled": False}
        assert data["prompts_dir"] == "/home/goga/pipeline/prompts"
        assert data["add_stage"] == {"enabled": False}
        assert data["skin_dir"] == "/home/goga/.afm/skins/goga"
        assert set(data) == {
            "theme",
            "open_browser",
            "proxy",
            "prompts_dir",
            "add_stage",
            "skin_dir",
            "hooks",
            "collaboration",
        }

    def test_write_afm_config_without_documents_writes_collaboration_head(self, config_path: Path) -> None:
        """No flow/workflow still writes the collaboration section head.

        ``runtime_context: wrapper`` is a static delivery decision — every
        command the engine spawns is an as-claude wrapper — so the section
        writes on every launch; only the profiles and the task budget are
        document-derived.
        """
        write_afm_config(None)

        data = yaml.safe_load(config_path.read_text())

        assert data["collaboration"] == {"runtime_context": "wrapper"}


class TestWriteAfmConfigLogic:
    """Logic: the authored document, the agent optionality, and the failure mode."""

    def test_write_afm_config_with_agent_writes_resolved_wrapper_and_static_fields(self, config_path: Path) -> None:
        """A resolved agent yields client.command plus the six static fields."""
        written = write_afm_config("codex")

        assert written == config_path

        data = yaml.safe_load(config_path.read_text())
        assert data == {
            "client": {"command": "/home/goga/bin/codex-as-claude.sh"},
            "theme": "goga",
            "open_browser": False,
            "proxy": {"enabled": False},
            "prompts_dir": "/home/goga/pipeline/prompts",
            "add_stage": {"enabled": False},
            "skin_dir": "/home/goga/.afm/skins/goga",
            "hooks": [_OBSERVER_HOOK],
            "collaboration": {"runtime_context": "wrapper"},
        }
        assert "/home/goga/bin/" in data["client"]["command"]

    def test_write_afm_config_without_agent_omits_client_block(self, config_path: Path) -> None:
        """No agent omits client entirely — a null command is never written."""
        write_afm_config(None)

        data = yaml.safe_load(config_path.read_text())

        assert "client" not in data
        assert set(data) == {
            "theme",
            "open_browser",
            "proxy",
            "prompts_dir",
            "add_stage",
            "skin_dir",
            "hooks",
            "collaboration",
        }

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
        assert set(second) == {
            "client",
            "theme",
            "open_browser",
            "proxy",
            "prompts_dir",
            "add_stage",
            "skin_dir",
            "hooks",
            "collaboration",
        }

    def test_write_afm_config_registers_the_observer_hook(self, config_path: Path) -> None:
        """The composed content carries goga's observer hook entry in the hooks layer.

        The entry is a fixed constant — ``id: goga``, ``events: all``, the
        bridge command, ``inherit_env: true`` — with ``timeout`` / ``retries``
        intentionally omitted (afm ``omitempty`` defaults: 30 s / 0) and no
        ``env`` map; the four static launcher fields and the resolved client
        command stay intact.
        """
        write_afm_config("codex")

        parsed = yaml.safe_load(config_path.read_text())

        assert parsed["hooks"] == [
            {
                "id": "goga",
                "events": "all",
                "command": "python3 -m goga.pipeline hook",
                "inherit_env": True,
            }
        ]
        assert set(parsed["hooks"][0]) == {"id", "events", "command", "inherit_env"}
        assert parsed["client"]["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert parsed["theme"] == "goga"
        assert parsed["open_browser"] is False
        assert parsed["proxy"] == {"enabled": False}
        assert parsed["prompts_dir"] == "/home/goga/pipeline/prompts"

    def test_write_afm_config_registers_the_observer_hook_without_agent(self, config_path: Path) -> None:
        """The agentless form still registers the hook — the bridge is agent-independent."""
        write_afm_config(None)

        parsed = yaml.safe_load(config_path.read_text())

        assert "client" not in parsed
        assert parsed["hooks"] == [_OBSERVER_HOOK]

    def test_write_afm_config_hook_entry_never_duplicates(self, config_path: Path) -> None:
        """Two consecutive invocations leave exactly one observer entry."""
        write_afm_config("codex")
        write_afm_config("codex")

        parsed = yaml.safe_load(config_path.read_text())

        assert len(parsed["hooks"]) == 1

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

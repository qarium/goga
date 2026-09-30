"""End-to-end integration tests for the resolved wrapper path flow.

These stitch together the cross-cell path of the ``unified-agent-wrappers-
resolution`` migration on the two-part build model. A single leaf routine —
``resolve_wrapper_path`` in ``goga/agents/wrapper`` — is re-exported through
the ``goga.agents`` facade and consumed by both host-side launchers:

    goga/agents/wrapper/resolve.py  (leaf)
        -> goga/agents/__init__.py  (facade re-export)
            -> goga/build/build.py            (per-pass executor wrappers)
            -> goga/commands/pipeline/...     (writes afm-config tmpfile client.command)

The integration boundary is the facade import
``from goga.agents import resolve_wrapper_path``: each consumer resolves the
bare agent name from its own config block (``build.agent`` /
``build.review.agent`` / ``pipeline.agent``) and writes the resulting absolute
path into a different config surface. The build consumer resolves one wrapper
per pass of the always-two-pass cycle — the tasks pass under the root agent,
the review pass under the review agent, or under the additional agent when the
strategy is short — so the per-pass wrapper sequence and the final
``.ralphex/config`` are verified together with the pipeline-side surface.

The docker/subprocess boundary is mocked per
``[[feedback_mock_patch_module_shadowing]]``: the package ``__init__`` re-exports
submodule functions, which shadows string-based ``mock.patch`` paths, so the
real modules are resolved via ``sys.modules`` and patched by attribute.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import NamedTuple
from unittest import mock

import pytest
from goga.agents import resolve_wrapper_path
from goga.build import build
from goga.build.build_pass import write_ralphex_config as _real_write_ralphex_config
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import load_project_config
from goga.ralphex.run_ralphex import _build_command

# goga.commands.pipeline.run_pipeline_container shadows its submodule name in the
# package __init__, so resolve the real module via sys.modules for
# monkeypatching host-side helpers.
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]

_AFM_MOUNT_SUFFIX = ":/home/goga/.afm/config.yaml:ro"


def _load_config(tmp_path: Path, monkeypatch) -> object:
    """Chdir into tmp_path and load the .goga/config.yml written there."""
    monkeypatch.chdir(tmp_path)
    return load_project_config()


def _capture_afm_config_popen(captured: dict) -> object:
    """Build a subprocess.Popen side effect that reads the afm-config tmpfile.

    The afm-config host path is extracted from the run-mode docker command's
    ``-v <host>:/home/goga/.afm/config.yaml:ro`` argument and read back into
    ``captured['afm_content']`` before the mocked process returns — capturing the
    real file content written by the integrated ``_write_afm_config_tmpfile``
    call.
    """
    mock_proc = mock.Mock()
    mock_proc.wait.return_value = 0

    def popen_side_effect(cmd, *args, **kwargs):
        for i, arg in enumerate(cmd):
            if arg == "-v" and i + 1 < len(cmd) and cmd[i + 1].endswith(_AFM_MOUNT_SUFFIX):
                host = cmd[i + 1][: -len(_AFM_MOUNT_SUFFIX)]
                captured["afm_content"] = Path(host).read_text()
                break
        return mock_proc

    return popen_side_effect


# --- build consumer: per-pass executor wrappers and .ralphex/config ---


class _PassCase(NamedTuple):
    """One per-pass wrapper scenario: the review section and the wrapper sequence it yields."""

    review_section: dict
    expected_wrappers: list[str]


class TestBuildResolvedPathFlow:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_build_resolved_path_matches_resolve_wrapper_path(
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        agent: str,
    ) -> None:
        """build() writes the resolve_wrapper_path(agent) value into claude_command."""
        write_goga_config(agent=agent, image="goga:latest")
        config = _load_config(tmp_path, monkeypatch)
        cli_options = {"dry_run": True, "skip_manifest_check": True}

        wrapper = tmp_path / f"{agent}-as-claude.sh"
        wrapper.write_text("#!/bin/sh\n")

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            result = build("plan.md", config, cli_options)

        assert result == 0
        config_text = (tmp_path / ".ralphex" / "config").read_text()

        # The facade is the single source of truth: claude_command must equal
        # exactly what resolve_wrapper_path returns for this agent.
        for line in config_text.splitlines():
            if line.startswith("claude_command = "):
                claude_command = line[len("claude_command = ") :]
                assert claude_command == resolve_wrapper_path(agent)
                return
        pytest.fail("claude_command line not found in .ralphex/config")

    @pytest.mark.parametrize(
        "case",
        [
            # medium (the default strategy): tasks pass under the root agent,
            # review pass under the review agent.
            _PassCase(
                review_section={"agent": "codex"},
                expected_wrappers=[
                    "/home/goga/bin/claude-as-claude.sh",
                    "/home/goga/bin/codex-as-claude.sh",
                ],
            ),
            # short: the review pass is the external-only pass carried by the
            # additional agent's wrapper.
            _PassCase(
                review_section={
                    "agent": "codex",
                    "strategy": "short",
                    "additional": {"agent": "cursor", "patience": 2},
                },
                expected_wrappers=[
                    "/home/goga/bin/claude-as-claude.sh",
                    "/home/goga/bin/cursor-as-claude.sh",
                ],
            ),
        ],
        ids=["medium-review-agent", "short-additional-agent"],
    )
    def test_wrapper_resolved_per_pass(
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        case: _PassCase,
    ) -> None:
        """Each pass resolves its own executor wrapper; the final .ralphex/config
        carries the last pass's wrapper."""
        write_goga_config(agent="claude", image="goga:latest", review=case.review_section)
        config = _load_config(tmp_path, monkeypatch)
        Path("plan.md").write_text("# plan\n")

        review_wrapper = tmp_path / "codex-as-claude.sh"
        review_wrapper.write_text("#!/bin/sh\n")
        wrappers: list[str] = []

        def _record(settings, wrapper_path):
            wrappers.append(wrapper_path)
            return _real_write_ralphex_config(settings, wrapper_path)

        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(review_wrapper)),
            mock.patch("goga.build.build_pass.write_ralphex_config", side_effect=_record),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            result = build("plan.md", config, {"skip_manifest_check": True})

        assert result == 0

        # The always-two-pass cycle writes one config per pass, wrapper of that
        # pass; the sequence follows the per-stage agent resolution.
        assert mock_run.call_count == 2
        assert wrappers == case.expected_wrappers

        # The mode flags follow the strategy: --review for medium, -e for short.
        second_options = mock_run.call_args_list[1].args[1]
        if case.review_section.get("strategy") == "short":
            assert second_options["external_only"] is True
            assert "review" not in second_options
            assert _build_command("plan.md", second_options)[4:6] == ["-e", "--review-patience"]
        else:
            assert second_options["review"] is True

        # The final pass config carries the last pass's executor wrapper.
        config_text = (tmp_path / ".ralphex" / "config").read_text()
        assert f"claude_command = {case.expected_wrappers[-1]}" in config_text


# --- pipeline consumer: afm-config tmpfile client.command ---


class TestPipelineResolvedPathFlow:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_pipeline_resolved_path_matches_resolve_wrapper_path(
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        agent: str,
    ) -> None:
        """The afm-config client.command equals resolve_wrapper_path(agent)."""
        write_goga_config(agent=agent, image="goga:latest")
        config = _load_config(tmp_path, monkeypatch)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured: dict = {}
        popen_side_effect = _capture_afm_config_popen(captured)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run"),
        ):
            result = rpc("deploy", config, ())

        assert result == 0
        assert "afm_content" in captured, "afm-config tmpfile was not captured"

        expected = resolve_wrapper_path(agent)
        assert captured["afm_content"] == (
            f"client:\n  command: {expected}\ntheme: goga\nopen_browser: false\n"
            "proxy:\n  enabled: false\nprompts_dir: /home/goga/pipeline/prompts\n"
        )


# --- cross-consumer consistency ---


class TestResolvedPathConsistency:
    @pytest.mark.parametrize("agent", ["claude", "codex", "opencode"])
    def test_resolved_path_consistent_between_build_and_pipeline(
        self,
        tmp_path: Path,
        monkeypatch,
        write_goga_config,
        mock_vendored_sources,
        agent: str,
    ) -> None:
        """For the same agent, both consumers write the identical wrapper path."""
        write_goga_config(agent=agent, image="goga:latest")
        config = _load_config(tmp_path, monkeypatch)

        # --- build side: capture .ralphex/config claude_command ---
        build_options = {"dry_run": True, "skip_manifest_check": True}
        wrapper = tmp_path / f"{agent}-as-claude.sh"
        wrapper.write_text("#!/bin/sh\n")
        with (
            mock_vendored_sources(),
            mock.patch("goga.build.review_config.resolve_wrapper_path", return_value=str(wrapper)),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            build_result = build("plan.md", config, build_options)
        assert build_result == 0
        build_config_text = (tmp_path / ".ralphex" / "config").read_text()
        build_path: str | None = None
        for line in build_config_text.splitlines():
            if line.startswith("claude_command = "):
                build_path = line[len("claude_command = ") :]
                break
        assert build_path is not None, "claude_command line not found in .ralphex/config"

        # build() may have created .ralphex/; the pipeline side is docker-bound and
        # does not touch it, so no cleanup is needed between the two invocations.

        # --- pipeline side: capture afm-config client.command ---
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "docker_update", lambda *_: None)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

        captured: dict = {}
        popen_side_effect = _capture_afm_config_popen(captured)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run"),
        ):
            pipeline_result = rpc("deploy", config, ())
        assert pipeline_result == 0
        assert "afm_content" in captured, "afm-config tmpfile was not captured"

        # afm content is "client:\n  command: <path>\ntheme: goga\n..." — client is
        # a nested YAML map; read the command value (2nd line) to compare the
        # wrapper path against the build side.
        afm_lines = captured["afm_content"].splitlines()
        assert afm_lines[0] == "client:"
        assert afm_lines[1].startswith("  command: ")
        pipeline_path = afm_lines[1][len("  command: ") :]

        # Both consumers, driven by the same facade import, agree on the path and
        # match the canonical absolute convention.
        assert build_path == pipeline_path
        assert build_path == f"/home/goga/bin/{agent}-as-claude.sh"

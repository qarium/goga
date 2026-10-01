"""End-to-end session tests — the invited-tool feature through the CLI.

The whole runtime composition of the design drives for real: the CLI
invitation flags, the dedup, both tool participation moments, the survey,
the committed amendments, the generation, and the attributed file report.
The environment boundary is pinned exactly as the hooks platform tests pin
it — the installed-distributions mapping and the ``sys.modules`` entry of
one fake ``goga_tool_*`` package whose facade subscribes both onboarding
actions (the ``pin_package_environment`` factory plus the local install
fixture below); the registry build, the registration, the per-tool
delivery, the survey, and the generator run for real. The filesystem
boundary is pinned by the ``_isolate_cwd`` autouse fixture of the shared
``tests/conftest.py`` — the CWD is a clean tmp dir with no
``.goga/config.yml``.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner
from goga.commands.init import init as init_cli
from goga.onboarding.generator import FileGenerator
from goga.onboarding.participation import ToolParticipation
from goga.onboarding.questions import Question, SessionAnswers

# The fake tool identity and its top-level module name — the identity is
# environment-assigned: the goga_tool_ prefix drops, underscores become
# hyphens.
_TOOL = "my-tool"
_TOOL_MODULE = "goga_tool_my_tool"

# The hook-body shape of the fake package — context first, optional self.
_Hook = Callable[..., None]
_InstallTool = Callable[[_Hook | None, _Hook | None], None]

# The full survey walked with the least input: the language choice, every
# confirm gate declined, the offered pull-image default accepted, the
# invited tool's token answered.
_FULL_SESSION_INPUTS = [
    "python",  # the language choice
    "n",  # the base-convention gate
    "n",  # the codemanifest usages collection
    "n",  # the codemanifest annotations
    "n",  # the build agent gate
    "n",  # the Dockerfile gate — the pull branch runs
    "",  # the pulled image — the offered hint default
    "n",  # the pipeline agent gate
    "n",  # the tools collection gate
    "n",  # the usages records gate
    "t0",  # the invited tool's token
]


def _declare_token(context: Any) -> None:
    """Declare the standard block of the fake tool — one token input."""
    if not context.invited:
        return
    context.declare(Question(id="token", kind="input", prompt="Service token"))


def _amend_service(context: Any) -> None:
    """Contribute the standard amendment — the tools record and one config file."""
    if not context.invited:
        return
    context.answer("tools", {_TOOL: "latest"})
    context.write_config("service.yml", {"token_source": "env"})


@pytest.fixture
def install_tool(
    monkeypatch: pytest.MonkeyPatch,
    pin_package_environment: Callable[[dict[str, list[str]]], mock.MagicMock],
) -> _InstallTool:
    """Install the fake ``my-tool`` package subscribed to the onboarding actions.

    The standard fake declares the token input and contributes the tools
    record plus one service config; a test overrides either hook body (or
    passes None to leave that action unsubscribed). The enumeration boundary
    is pinned to the single fake identity — the registry build, the
    registration, and the per-tool delivery run for real.

    Args:
        monkeypatch: The pytest patcher restoring the boundary on teardown.

    Returns:
        The installing factory: the declare and amend hook bodies in, None out.
    """

    def _install(declare: _Hook | None = _declare_token, amend: _Hook | None = _amend_service) -> None:
        def register_hooks(hooks: Any) -> None:
            if declare is not None:
                hooks.subscribe("onboarding", "declare_session", "declare", declare)
            if amend is not None:
                hooks.subscribe("onboarding", "amend_config", "amend", amend)

        module = ModuleType(_TOOL_MODULE)
        module.register_hooks = register_hooks

        monkeypatch.setitem(sys.modules, _TOOL_MODULE, module)
        pin_package_environment({_TOOL_MODULE: [f"goga-tool-{_TOOL}"]})

    return _install


class TestInvitedToolSession:
    """The invited-tool session end to end — through the real CLI command."""

    def test_init_full_session_with_invited_tool(self, install_tool: _InstallTool) -> None:
        """Invitation → dedup → both moments → survey → amendments → attributed report."""
        install_tool()

        result = CliRunner().invoke(
            init_cli,
            ["-t", _TOOL, "-t", _TOOL],
            input="\n".join(_FULL_SESSION_INPUTS) + "\n",
        )

        assert result.exit_code == 0, result.output

        cfg = yaml.safe_load(Path(".goga/config.yml").read_text(encoding="utf-8"))
        assert cfg["language"] == "python"
        assert cfg["tools"] == {"my-tool": "latest"}
        # The offered image default follows the selected language's family
        # (the tag tracks the installed goga minor line).
        assert cfg["image"].startswith("qarium/goga-python-3.14:")

        assert Path(".goga/tools/my-tool/service.yml").exists()
        assert "(tool: my-tool)" in result.output

    def test_tool_failure_never_changes_exit_code(
        self,
        install_tool: _InstallTool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A crashing amend hook drops the tool's contribution — the session still exits 0."""

        def amend_boom(context: Any) -> None:
            raise RuntimeError("amend boom")

        install_tool(amend=amend_boom)

        with caplog.at_level(logging.WARNING):
            result = CliRunner().invoke(
                init_cli,
                ["-t", _TOOL],
                input="\n".join(_FULL_SESSION_INPUTS) + "\n",
            )

        assert result.exit_code == 0, result.output
        assert Path(".goga/config.yml").is_file()
        assert not Path(".goga/tools/my-tool").exists()
        dropped = [r for r in caplog.records if r.message == "tool dropped from onboarding"]
        assert any(r.tool == _TOOL and "amend boom" in r.reason for r in dropped)

    def test_bad_buffered_config_file_never_changes_exit_code(
        self,
        install_tool: _InstallTool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A buffered escape name and an unserializable payload drop their files — the session still exits 0."""

        def amend_bad_files(context: Any) -> None:
            if not context.invited:
                return
            deep: dict = {}
            current = deep
            for _ in range(50_000):
                current["n"] = {}
                current = current["n"]
            context.answer("tools", {_TOOL: "latest"})
            context.write_config("../../escape.yml", {"a": 1})
            context.write_config("bad.yml", deep)
            context.write_config("service.yml", {"token_source": "env"})

        install_tool(amend=amend_bad_files)

        with caplog.at_level(logging.WARNING):
            result = CliRunner().invoke(
                init_cli,
                ["-t", _TOOL],
                input="\n".join(_FULL_SESSION_INPUTS) + "\n",
            )

        assert result.exit_code == 0, result.output
        assert Path(".goga/config.yml").is_file()
        assert Path(".goga/tools/my-tool/service.yml").is_file()
        assert not Path(".goga/tools/my-tool/bad.yml").exists()
        assert not (Path.cwd().parent.parent / "escape.yml").exists()
        assert "(tool: my-tool)" in result.output
        rejected = [r for r in caplog.records if r.message == "rejected the config file"]
        assert any(r.tool == _TOOL and "escape.yml" in r.reason for r in rejected)
        not_written = [r for r in caplog.records if r.message == "config file not written"]
        assert any(r.tool == _TOOL and r.file == "bad.yml" for r in not_written)

    def test_skip_of_base_image_collapses_dockerfile_branch(self, install_tool: _InstallTool) -> None:
        """A tool-declared skip of the base image collapses the FROM — no Dockerfile, no config field."""

        def declare_skip(context: Any) -> None:
            if not context.invited:
                return
            context.skip("docker_image.base_image")

        install_tool(declare=declare_skip, amend=None)

        inputs = [
            "python",  # the language choice
            "n",  # the base-convention gate
            "n",  # the codemanifest usages collection
            "n",  # the codemanifest annotations
            "n",  # the build agent gate
            "y",  # the Dockerfile gate — accepted
            "",  # the Dockerfile path — the .goga/Dockerfile default
            "my-app:latest",  # the built image name
            "n",  # the pipeline agent gate
            "n",  # the tools collection gate
            "n",  # the usages records gate
        ]

        result = CliRunner().invoke(init_cli, ["-t", _TOOL], input="\n".join(inputs) + "\n")

        assert result.exit_code == 0, result.output
        assert "Base image" not in result.output

        cfg = yaml.safe_load(Path(".goga/config.yml").read_text(encoding="utf-8"))
        assert cfg["image"] == "my-app:latest"
        assert "dockerfile" not in cfg
        assert "base_image" not in cfg
        assert not Path(".goga/Dockerfile").exists()


class TestStagedCommit:
    """The staged-commit story end to end — the cross-entity negative trace."""

    def test_failing_hook_discards_files_with_amendments(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A hook that buffers then raises leaves nothing behind — the core config still stands."""

        def amend_boom(context: Any) -> None:
            context.answer("tools", {"my-tool": "latest"})
            context.write_config("x.yml", {"a": 1})
            raise RuntimeError("crash")

        def register_hooks(hooks: Any) -> None:
            hooks.subscribe("onboarding", "amend_config", "a1", amend_boom)

        pin_package_environment({"goga_tool_my_tool": ["goga-tool-my-tool"]})
        install_tool_package("goga_tool_my_tool", register_hooks=register_hooks)

        answers = SessionAnswers()
        answers.record("language", "python")

        with caplog.at_level(logging.WARNING):
            contributions = ToolParticipation(invited=["my-tool"]).collect_contributions(answers)

        FileGenerator().generate(answers, [])

        assert contributions == []
        assert "tools" not in answers.snapshot()
        assert not Path(".goga/tools").exists()

        cfg = yaml.safe_load(Path(".goga/config.yml").read_text(encoding="utf-8"))
        assert cfg == {"language": "python"}
        dropped = [r for r in caplog.records if r.message == "tool dropped from onboarding"]
        assert any(r.tool == "my-tool" for r in dropped)

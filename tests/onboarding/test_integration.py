"""End-to-end session tests — the invited-tool feature through the CLI.

The whole runtime composition of the design drives for real: the CLI
invitation flags, the dedup, both tool participation moments, the survey,
the committed amendments, the generation, and the attributed file report.
The environment boundary is pinned exactly as the hooks platform tests pin
it — the installed-distributions mapping and the ``sys.modules`` entry of
one fake ``goga_tool_*`` package whose facade subscribes both onboarding
actions; the registry build, the registration, the per-tool delivery, the
survey, and the generator run for real. The filesystem boundary is pinned
by the ``_clean_cwd`` fixture of this test directory.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from goga.commands.init import init as init_cli
from goga.onboarding.questions import Question

# The attribute the enumeration reads — the single enumeration mock point
# (mirrors the hooks test directory; conftest fixtures do not cross test
# directories).
_ENUMERATION_TARGET = "goga.hooks.tools.packages.packages_distributions"

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

# Every test of this file operates on the filesystem state of a clean
# project dir — the repo CWD carries the goga project's own .goga/.
pytestmark = pytest.mark.usefixtures("_clean_cwd")


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
def install_tool(monkeypatch: pytest.MonkeyPatch) -> _InstallTool:
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
        monkeypatch.setattr(_ENUMERATION_TARGET, lambda: {_TOOL_MODULE: [f"goga-tool-{_TOOL}"]})

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
        assert any(_TOOL in record.message for record in caplog.records)

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

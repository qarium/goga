from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.hooks.conftest import install_tool_package, pin_package_environment

__all__ = ["install_tool_package", "pin_package_environment"]


def write_codemanifest(directory: Path, content: str) -> None:
    """Write ``content`` as the ``CODEMANIFEST`` of ``directory``."""
    (directory / "CODEMANIFEST").write_text(content, encoding="utf-8")


def write_goga_yml(tmp_path: Path, data: dict) -> Path:
    """Dump ``data`` as the ``.goga/config.yml`` under ``tmp_path``; return ``tmp_path``."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(yaml.dump(data))
    return tmp_path


def minimal_two_part_data() -> dict:
    """The minimal two-part config mapping (top-level image, build, pipeline)."""
    return {
        "language": "python",
        "image": "qarium/goga:latest",
        "build": {"agent": "claude"},
        "pipeline": {"agent": "claude"},
    }


def register_amendment_hook(hooks: object, amendment: Callable[[object], None], *, label: str = "hardening") -> None:
    """Subscribe one ``config.amend_config`` hook running ``amendment``.

    The common checkpoint-test shape across the command suites: the amendment
    callback (``context.force`` / ``context.set`` / ``context.contribute`` — the
    genuinely test-specific part) is provided by the caller; the subscription
    topic, event, and label stay identical everywhere.
    """
    hooks.subscribe("config", "amend_config", label, amendment)  # type: ignore[attr-defined]


@pytest.fixture
def empty_package_environment(pin_package_environment: Callable[[dict[str, list[str]]], Any]) -> None:
    """Pin the package environment empty.

    Every successful command run delivers its amendment checkpoint through the
    real registry, so an unpinned environment would make the command output
    depend on the machine's installed ``goga_tool_*`` packages. Tests that
    install a tool pin their own environment on top — the later pin wins.
    """
    pin_package_environment({})


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    """Minimal .goga/config.yml in tmp_path (two-part build root)."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    config_file = goga_dir / "config.yml"
    config_file.write_text("language: python\nbuild:\n  agent: claude\npipeline:\n  agent: claude\n")
    return tmp_path


@pytest.fixture
def full_config(tmp_path: Path) -> Path:
    """Full .goga/config.yml with all options (two-part build + build.review)."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    config_file = goga_dir / "config.yml"
    config_file.write_text(
        "language: python\n"
        "commands:\n  test: pytest\n"
        "build:\n"
        "  agent: claude\n"
        "  env:\n"
        "    API_KEY: sk-xxx\n"
        "    MODEL: claude-sonnet-4-6\n"
        "  session_timeout: '30m'\n"
        "  idle_timeout: '1h'\n"
        "  wait: '5m'\n"
        "  max_iterations: 10\n"
        "  prompts_dir: /custom/prompts\n"
        "  agents_dir: /custom/agents\n"
        "  review:\n"
        "    skip: true\n"
        "    strategy: short\n"
        "    base_ref: origin/1.2.x\n"
        "    additional:\n"
        "      patience: 3\n"
        "pipeline:\n"
        "  agent: claude\n"
        "  env:\n"
        "    API_KEY: sk-xxx\n"
    )
    return tmp_path


@pytest.fixture
def usages_config(tmp_path: Path) -> Path:
    """Config with a usages section for dataclass-aware rendering tests.

    Contains two deps under one group: ``click`` (git + ref) and ``another``
    (git only, ref defaults to None) to exercise nested ``DepConfig`` rendering
    on the leaf / group / whole-section levels.
    """
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    config_file = goga_dir / "config.yml"
    config_file.write_text(
        "language: python\n"
        "usages:\n"
        "  libs:\n"
        "    click:\n"
        "      git: https://example.com/click.git\n"
        "      ref: main\n"
        "    another:\n"
        "      git: https://example.com/another.git\n"
    )
    return tmp_path

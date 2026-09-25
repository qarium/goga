from pathlib import Path

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    """Minimal .goga/config.yml in tmp_path (two-part build root)."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    config_file = goga_dir / "config.yml"
    config_file.write_text(
        "language: python\nbuild:\n  agent: claude\npipeline:\n  agent: claude\n"
    )
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

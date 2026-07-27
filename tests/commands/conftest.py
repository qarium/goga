from pathlib import Path

import pytest


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    """Minimal .goga/config.yml in tmp_path."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    config_file = goga_dir / "config.yml"
    config_file.write_text(
        "language: python\nbuild:\n  task_executor:\n    agent: claude\npipeline:\n  agent: claude\n"
    )
    return tmp_path


@pytest.fixture
def full_config(tmp_path: Path) -> Path:
    """Full .goga/config.yml with all options."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir()
    config_file = goga_dir / "config.yml"
    config_file.write_text(
        "language: python\n"
        "commands:\n  test: pytest\n"
        "build:\n"
        "  task_executor:\n"
        "    agent: claude\n"
        "    env:\n"
        "      API_KEY: sk-xxx\n"
        "      MODEL: claude-sonnet-4-6\n"
        "  worktree: true\n"
        "  skip_finalize: false\n"
        "  session_timeout: '30m'\n"
        "  idle_timeout: '1h'\n"
        "  wait: '5m'\n"
        "  max_iterations: 10\n"
        "  review_patience: 3\n"
        "  prompts_dir: /custom/prompts\n"
        "  agents_dir: /custom/agents\n"
        "  codex_review: true\n"
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

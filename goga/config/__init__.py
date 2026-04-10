from pathlib import Path

import yaml

from .prompts import (
    resolve_agents_source,
    resolve_prompts_source,
    sync_defaults,
)

GOGA_CONFIG_DIR = ".goga"


def resolve_config_dir(build_cfg: dict) -> str:
    """return ralphex config dir from build config or default."""
    return build_cfg.get("config_dir") or GOGA_CONFIG_DIR


def load_config(project_dir: Path | None = None) -> dict:
    """load goga.yml from project root (current directory)."""
    base = Path(project_dir) if project_dir else Path.cwd()
    config_path = base / "goga.yml"

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def get_build_config(project_dir: Path | None = None) -> dict:
    """return build section from goga.yml with defaults."""
    cfg = load_config(project_dir)
    build = cfg.get("build", {})

    return {
        "worktree": build.get("worktree", False),
        "session_timeout": build.get("session_timeout", ""),
        "idle_timeout": build.get("idle_timeout", ""),
        "wait": build.get("wait", ""),
        "skip_finalize": build.get("skip_finalize", False),
        "max_iterations": build.get("max_iterations", 0),
        "review_patience": build.get("review_patience", 0),
        "config_dir": build.get("config_dir", ""),
        "prompts_dir": build.get("prompts_dir", ""),
    }


__all__ = [
    "get_build_config",
    "resolve_config_dir",
    "resolve_agents_source",
    "resolve_prompts_source",
    "sync_defaults",
]

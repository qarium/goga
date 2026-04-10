import shutil
from pathlib import Path

DEFAULTS_DIR = Path(__file__).parent / "defaults" / "prompts"
DEFAULTS_AGENTS_DIR = Path(__file__).parent / "defaults" / "agents"


def resolve_config_dir(build_cfg: dict) -> str:
    """return ralphex config dir from build config or default."""
    return build_cfg.get("config_dir") or ".goga"


def resolve_prompts_source(build_cfg: dict) -> Path:
    """return prompts source dir from build config or goga built-in defaults."""
    prompts_dir = build_cfg.get("prompts_dir", "")
    return Path(prompts_dir) if prompts_dir else DEFAULTS_DIR


def resolve_agents_source(build_cfg: dict) -> Path:
    """return agents source dir from build config or goga built-in defaults."""
    agents_dir = build_cfg.get("agents_dir", "")
    return Path(agents_dir) if agents_dir else DEFAULTS_AGENTS_DIR


def _sync_dir(source: Path, target: Path) -> None:
    """copy files from source to target, never overwriting existing files."""
    if not source.exists() or not any(source.iterdir()):
        return

    target.mkdir(parents=True, exist_ok=True)
    for f in source.iterdir():
        if f.is_file() and not (target / f.name).exists():
            shutil.copy2(f, target / f.name)


def sync_defaults(build_cfg: dict, config_dir: Path) -> None:
    """copy goga default prompts and agents to config_dir for ralphex to pick up.

    existing files in target are never overwritten.
    """
    _sync_dir(resolve_prompts_source(build_cfg), config_dir / "prompts")
    _sync_dir(resolve_agents_source(build_cfg), config_dir / "agents")

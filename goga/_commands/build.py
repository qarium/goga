import shutil
import subprocess
import sys
from pathlib import Path

import click

from goga.config import (
    get_build_config,
    resolve_agents_source,
    resolve_config_dir,
    resolve_prompts_source,
    sync_defaults,
)


def build_ralphex_args(build_cfg: dict, config_dir: str) -> list[str]:
    """convert build config section to ralphex CLI flags."""
    args = ["--config-dir", config_dir]

    if build_cfg.get("worktree"):
        args.append("--worktree")
    if build_cfg.get("skip_finalize"):
        args.append("--skip-finalize")

    for key, flag in [
        ("session_timeout", "--session-timeout"),
        ("idle_timeout", "--idle-timeout"),
        ("wait", "--wait"),
    ]:
        val = build_cfg.get(key, "")
        if val:
            args.extend([flag, str(val)])

    for key, flag in [
        ("max_iterations", "--max-iterations"),
        ("review_patience", "--review-patience"),
    ]:
        val = build_cfg.get(key, 0)
        if val:
            args.extend([flag, str(val)])

    return args


@click.command()
@click.option("--dry-run", is_flag=True, help="show command without executing")
def build(dry_run: bool) -> None:
    """run plan through ralphex."""
    build_cfg = get_build_config()
    config_dir = resolve_config_dir(build_cfg)

    args = ["ralphex", *build_ralphex_args(build_cfg, config_dir)]

    if dry_run:
        click.echo(f"prompts source: {resolve_prompts_source(build_cfg)}")
        click.echo(f"agents source: {resolve_agents_source(build_cfg)}")
        click.echo(f"config-dir: {config_dir}")
        click.echo(" ".join(args))
        return

    ralphex = shutil.which("ralphex")
    if not ralphex:
        click.echo("error: ralphex not found in PATH", err=True)
        sys.exit(1)

    sync_defaults(build_cfg, Path(config_dir))
    sys.exit(subprocess.call(args))

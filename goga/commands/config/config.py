from __future__ import annotations

from dataclasses import asdict, is_dataclass

import click
import yaml

from goga.config import load_config

_ALIAS_MAP: dict[str, str] = {"language": "lang"}
_NOT_FOUND = object()


def _resolve_option(config: object, option: str) -> object:
    """Traverse config by dot-notation path, returning the resolved value.

    Returns _NOT_FOUND sentinel if any attribute in the path does not exist.
    """
    parts = option.split(".")
    if parts[0] in _ALIAS_MAP:
        parts[0] = _ALIAS_MAP[parts[0]]

    current = config
    for part in parts:
        if isinstance(current, dict):
            if part.startswith("_") or part not in current:
                return _NOT_FOUND
            current = current[part]
        elif hasattr(current, "__dict__") or is_dataclass(current):
            if part.startswith("_"):
                return _NOT_FOUND
            try:
                current = getattr(current, part)
            except AttributeError:
                return _NOT_FOUND
        else:
            return _NOT_FOUND
    return current


def _output_value(value: object) -> None:
    """Output a value to stdout, formatting by type."""
    if value is None:
        click.echo("null")
    elif isinstance(value, (bool, str, int)):
        click.echo(str(value))
    elif isinstance(value, dict) or is_dataclass(value):
        data = asdict(value) if is_dataclass(value) else value
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}
        yaml_str = yaml.dump(
            data,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            indent=2,
        )
        click.echo(yaml_str.rstrip())
    else:
        click.echo(str(value))


@click.command()
@click.argument("options", nargs=-1, required=True)
@click.pass_context
def config(ctx: click.Context, options: tuple[str, ...]) -> None:
    """Read and output configuration options from .goga/config.yml."""
    try:
        cfg = load_config()
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    for i, option in enumerate(options):
        if i > 0:
            click.echo()
        value = _resolve_option(cfg, option)
        if value is _NOT_FOUND:
            click.echo(f"Option not found: {option}", err=True)
            ctx.exit(1)
        click.echo(f"# {option}")
        _output_value(value)

from __future__ import annotations

from dataclasses import asdict, is_dataclass

import click
import yaml

from ...config import load_project_config

_ALIAS_MAP: dict[str, str] = {"language": "lang"}
_NOT_FOUND = object()


class _DataclassDumper(yaml.Dumper):
    """Scoped YAML dumper that renders dataclass instances as clean mappings.

    Extends the `beautiful_yaml` practice with a dataclass-aware representer so
    that dataclass instances nested inside dicts (e.g. a usages group or the
    whole usages section, where values are ``DepConfig``) render as YAML
    mappings instead of the default ``!!python/object:`` tag / a
    ``RepresenterError``. The conversion is scoped to this subclass: nothing is
    registered on the global ``yaml.Dumper``, so other ``yaml.dump`` calls are
    unaffected.
    """

    def represent_data(self, data: object) -> object:
        """Serialize ``data``, converting dataclass instances to mappings.

        ``None``-valued fields are dropped to match the top-level dict filtering
        in :func:`_output_value` and keep the rendered YAML free of noise.

        Args:
            data: The value being serialized.

        Returns:
            The YAML node representing ``data``.
        """
        if is_dataclass(data) and not isinstance(data, type):
            data = {k: v for k, v in asdict(data).items() if v is not None}
        return super().represent_data(data)


def _resolve_option(config: object, option: str) -> object:
    """Traverse config by dot-notation path and return the resolved value.

    Args:
        config: The root configuration object to traverse.
        option: Dot-notation path identifying the option to resolve.

    Returns:
        The resolved value, or the `_NOT_FOUND` sentinel if any attribute in
        the path does not exist.
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
    """Output a value to stdout, formatting it according to its type.

    Args:
        value: The value to render. Dicts and dataclasses are emitted as YAML,
            scalars as plain strings, and `None` as the literal "null".
    """
    if value is None:
        click.echo("null")
    elif isinstance(value, (bool, str, int)):
        click.echo(str(value))
    elif isinstance(value, dict) or is_dataclass(value):
        # Dataclass instances (top-level or nested) are converted to clean
        # mappings by ``_DataclassDumper``, which also drops ``None`` fields.
        # Plain dicts are filtered here so top-level ``None`` entries are dropped.
        data = value
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}
        yaml_str = yaml.dump(
            data,
            Dumper=_DataclassDumper,
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
    """Read and output configuration options from .goga/config.yml.

    Args:
        ctx: Click execution context used to control process exit codes.
        options: One or more dot-notation option paths to resolve and print.

    Raises:
        click.ClickException: When the configuration file cannot be loaded or
            parsed.
    """
    try:
        cfg = load_project_config()
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

from __future__ import annotations

from dataclasses import asdict, is_dataclass

import click
import yaml

from ...config import load_project_config
from ...config.hooks import ConfigHooks

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

    Each positional argument is a dot-notation option path (e.g. ``build.proxy``)
    resolved against the project config and printed to stdout.
    """
    try:
        authored = load_project_config()
        # The config-amendment checkpoint joins the load inside the try: a
        # hard checkpoint failure is the same clean error as a failed load.
        overlay = ConfigHooks().amend_config(config=authored)
    except (FileNotFoundError, KeyError, ValueError, ImportError, yaml.YAMLError) as exc:
        # ImportError — a broken tool package facade during the registry
        # build — is the same clean error, never a raw traceback.
        raise click.ClickException(str(exc)) from exc

    # The summary lines go to stderr — stdout stays the data-clean value
    # surface (headers + effective values only).
    for line in overlay.summary_lines:
        click.echo(line, err=True)

    for i, option in enumerate(options):
        if i > 0:
            click.echo()
        value = _resolve_option(overlay.config, option)
        if value is _NOT_FOUND:
            click.echo(f"Option not found: {option}", err=True)
            ctx.exit(1)
        click.echo(f"# {option}")
        _output_value(value)

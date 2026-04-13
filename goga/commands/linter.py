from __future__ import annotations

import os

import click
import yaml

from ..manifest import Project


@click.command()
@click.argument("path", default=".")
def linter(path: str) -> None:
    """Validate CODEMANIFEST files in the project."""
    os.chdir(path)

    project = Project(".")
    project.load()

    for error in project.errors:
        rule_line = click.style(f"[{error.rule}]", fg="red")
        click.echo(f"{rule_line} {error.message}")

        doc_path = getattr(error.document, "path", None) if error.document else None
        if doc_path is not None:
            click.echo(f"  --> {doc_path}")

        if error.node is not None and hasattr(error.node, "data") and error.node.data is not None:
            yaml_str = yaml.dump(
                error.node.data,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
                indent=2,
            )
            for line in yaml_str.splitlines():
                click.echo(f"      {line}")

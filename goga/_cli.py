import click

from .commands.build import build


@click.group()
def main() -> None:
    """goga — code lifecycle management CLI."""


main.add_command(build)

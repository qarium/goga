from __future__ import annotations

import click

from goga.init.answers import GogaConfigAnswers, InitAnswers

_IMAGE_MAP: dict[str, list[str]] = {
    "python": [
        "qarium/goga-python-3.10:1.0",
        "qarium/goga-python-3.11:1.0",
        "qarium/goga-python-3.12:1.0",
        "qarium/goga-python-3.13:1.0",
        "qarium/goga-python-3.14:1.0",
    ],
    "golang": [
        "qarium/goga-golang-1.23:1.0",
        "qarium/goga-golang-1.24:1.0",
        "qarium/goga-golang-1.25:1.0",
        "qarium/goga-golang-1.26:1.0",
    ],
}

_LANGUAGES = ["python", "golang", "kotlin", "swift", "javascript"]

_AGENT_ENV_MAP: dict[str, list[str]] = {
    "claude": [
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_BASE_URL",
    ],
}


class Questionnaire:
    """Interactive questionnaire for project initialization."""

    def __init__(self) -> None:
        pass

    def ask(self) -> InitAnswers:
        """Run full questionnaire and return collected answers."""
        click.echo("=== Goga Project Initialization ===")
        click.echo("This wizard will help you set up a new goga project.\n")
        config = self.ask_goga_config()
        return InitAnswers(goga_config=config)

    def ask_goga_config(self) -> GogaConfigAnswers:  # noqa: C901, PLR0912
        """Run questionnaire for .goga/config.yml creation."""
        click.echo("Collecting .goga/config.yml settings...\n")

        # 1. Language
        click.echo("--- Project Language ---")
        click.echo("Select the primary programming language for your project.")
        language: str = click.prompt(
            "Language",
            type=click.Choice(_LANGUAGES),
        )

        # 2. Convention download
        codemanifest_usages: dict | None = None
        codemanifest_annotations: str | None = None
        click.echo("\n--- Base Convention ---")
        click.echo("Download the default code conventions for your language?")
        if click.confirm("Download base convention"):
            codemanifest_usages = {"conventions": ".goga/usages/conventions.md"}
            codemanifest_annotations = (
                "Use `conventions` for code writing rules and testing."
            )

        # 3. Additional codemanifest usages
        click.echo("\n--- Codemanifest Usages ---")
        click.echo("Add additional codemanifest usages (code practices documentation).")
        if click.confirm("Add codemanifest usages?", default=False):
            if codemanifest_usages is None:
                codemanifest_usages = {}
            while True:
                name = click.prompt("Usage name")
                if name in codemanifest_usages:
                    click.echo(f'Usage "{name}" already exists, skipping.')
                else:
                    path = click.prompt("Usage value")
                    codemanifest_usages[name] = path
                if not click.confirm("Add another codemanifest usage?", default=False):
                    break

        # 4. Additional codemanifest annotations
        click.echo("\n--- Codemanifest Annotations ---")
        click.echo("Add custom codemanifest annotations (global directives for AI agent).")
        if click.confirm("Add codemanifest annotations?", default=False):
            custom = click.prompt("Annotations")
            if codemanifest_annotations is not None:
                codemanifest_annotations = codemanifest_annotations + "\n" + custom
            else:
                codemanifest_annotations = custom

        # 5. Agent
        click.echo("\n--- AI Agent ---")
        click.echo("Select the AI agent that will build implementation.")
        agent: str = click.prompt(
            "Agent",
            type=click.Choice(["claude"]),
        )

        # 6. Docker image
        click.echo("\n--- Docker Image ---")
        click.echo("Select the Docker image for the build implementation.")
        images = _IMAGE_MAP.get(language)
        if images is not None:
            click.echo("Available images:")
            for img in images:
                click.echo(f"  - {img}")
            image: str = click.prompt("Docker image", default=images[-1])
        else:
            image = click.prompt("Docker image")

        # 7. Custom Dockerfile
        click.echo("\n--- Custom Dockerfile ---")
        click.echo("Create a custom Dockerfile for the build implementation?")
        dockerfile_path: str | None = None
        if click.confirm("Create Dockerfile?", default=False):
            dockerfile_path = click.prompt("Dockerfile path", default="Dockerfile")

        # 8. Environment variables
        click.echo("\n--- Environment Variables ---")
        click.echo("Configure environment variables for the build implementation.")
        env: dict = {}

        suggested_keys = _AGENT_ENV_MAP.get(agent, [])
        if suggested_keys:
            click.echo("Suggested env keys for selected agent:")
            for key in suggested_keys:
                click.echo(f"  - {key}")
            if click.confirm("Set suggested env variables?", default=False):
                for key in suggested_keys:
                    value = click.prompt(f"  {key}")
                    env[key] = value

        while click.confirm("Add custom environment variable?", default=False):
            key = click.prompt("Env key")
            value = click.prompt("Env value")
            env[key] = value

        return GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            env=env,
            dockerfile_path=dockerfile_path,
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
        )

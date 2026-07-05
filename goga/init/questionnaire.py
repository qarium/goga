from __future__ import annotations

import click

from .answers import GogaConfigAnswers, InitAnswers

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
    "javascript": [
        "qarium/goga-node-22:1.0",
        "qarium/goga-node-24:1.0",
    ],
    "kotlin": [
        "qarium/goga-kotlin-2.0:1.0",
        "qarium/goga-kotlin-2.1:1.0",
        "qarium/goga-kotlin-2.2:1.0",
        "qarium/goga-kotlin-2.3:1.0",
    ],
    "swift": [
        "qarium/goga-swift-6.0:1.0",
        "qarium/goga-swift-6.1:1.0",
        "qarium/goga-swift-6.2:1.0",
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
    "codex": [
        "CODEX_MODEL",
    ],
}


def _collect_agent_env(agent: str) -> dict | None:
    """Collect environment variables for an agent.

    Proposes keys from `_AGENT_ENV_MAP` for the given agent, then optionally
    collects arbitrary KEY=VALUE pairs. Returns None when nothing is collected.
    """
    env: dict | None = None

    suggested_keys = _AGENT_ENV_MAP.get(agent, [])
    if suggested_keys:
        click.echo("Suggested env keys for selected agent:")
        for key in suggested_keys:
            click.echo(f"  - {key}")
        if click.confirm("Set suggested env variables?", default=False):
            env = {}
            for key in suggested_keys:
                value = click.prompt(f"  {key}")
                env[key] = value

    if click.confirm("Add custom environment variable?", default=False):
        if env is None:
            env = {}
        while True:
            key = click.prompt("Env key")
            value = click.prompt("Env value")
            env[key] = value
            if not click.confirm("Add another?", default=False):
                break

    return env


class Questionnaire:
    """Interactive questionnaire for project initialization."""

    def ask(self) -> InitAnswers:
        """Run full questionnaire and return collected answers.

        Returns:
            InitAnswers container with the collected goga config payload.
        """
        click.echo("=== Goga Project Initialization ===")
        click.echo("This wizard will help you set up a new goga project.\n")
        config = self.ask_goga_config()
        return InitAnswers(goga_config=config)

    def ask_goga_config(self) -> GogaConfigAnswers:  # noqa: C901, PLR0912, PLR0915
        """Run questionnaire for .goga/config.yml creation.

        Returns:
            GogaConfigAnswers with all collected goga config fields.
        """
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
            codemanifest_annotations = "Use `conventions` for code writing rules and testing."

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
            type=click.Choice(["claude", "codex"]),
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

        # 8. Environment variables (task_executor)
        click.echo("\n--- Environment Variables ---")
        click.echo("Configure environment variables for the build implementation.")
        env: dict | None = _collect_agent_env(agent)

        # 9. Pipeline agent (defaults to the build agent from step 5)
        click.echo("\n--- Pipeline Agent ---")
        click.echo("Select the AI agent that will run pipelines (afm client.command).")
        pipeline_agent: str = click.prompt(
            "Pipeline agent",
            type=click.Choice(["claude", "codex"]),
            default=agent,
        )

        # 10. Pipeline environment variables
        click.echo("\n--- Pipeline Environment Variables ---")
        click.echo("Configure environment variables for the pipeline implementation.")
        pipeline_env: dict | None = _collect_agent_env(pipeline_agent)

        return GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            pipeline_agent=pipeline_agent,
            pipeline_env=pipeline_env,
            env=env,
            dockerfile_path=dockerfile_path,
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
        )
